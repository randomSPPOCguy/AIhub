"""
Music Information Processor
============================
Uses Phi-3 Mini to process Wikipedia and MusicBrainz data,
then passes summarized info to main AI provider (Gemini).
"""

import logging
from typing import Dict, Optional
try:
    from providers.local_model_provider import LocalModelProvider
    LOCAL_MODEL_AVAILABLE = True
except Exception as e:
    LOCAL_MODEL_AVAILABLE = False
    print("Warning: Local model provider not available:", str(e))
    
from providers.cloud.gemini_provider import GeminiProvider
from providers.cloud.claude_provider import ClaudeProvider
from providers.cloud.openai_provider import OpenAIProvider
import aiohttp
from config import settings

logger = logging.getLogger(__name__)

class MusicInfoProcessor:
    """Orchestrates music info lookup and AI processing"""
    
    def __init__(self):
        # Local model for processing API data
        self.local_model = None
        if settings.USE_PHI3_FOR_INFO and LOCAL_MODEL_AVAILABLE:
            try:
                self.local_model = LocalModelProvider()
            except Exception as e:
                logger.error(f"Failed to load local model: {e}")
                logger.info("Falling back to manual formatting")
        
        # Main AI provider for chat
        provider_name = settings.GEMINI_API_KEY and 'gemini' or settings.CLAUDE_API_KEY and 'claude' or 'openai'
        if settings.GEMINI_API_KEY:
            self.main_ai = GeminiProvider(settings.GEMINI_API_KEY)
        elif settings.CLAUDE_API_KEY:
            self.main_ai = ClaudeProvider(settings.CLAUDE_API_KEY)
        elif settings.OPENAI_API_KEY:
            self.main_ai = OpenAIProvider(settings.OPENAI_API_KEY)
        else:
            raise ValueError("No API keys configured!")
        
        logger.info("Music Info Processor initialized")
        logger.info(f"   Local AI: {'Enabled' if self.local_model else 'Disabled (manual formatting)'}")
        logger.info(f"   Main AI: {provider_name.upper()}")
    
    async def get_wikipedia_summary(self, query: str) -> str:
        """Fetch Wikipedia summary"""
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('extract', '')
            return ""
        except Exception as e:
            logger.error(f"Wikipedia error: {e}")
            return ""
    
    async def get_musicbrainz_info(self, artist: str, title: str) -> Dict:
        """Fetch MusicBrainz metadata"""
        try:
            url = f"https://musicbrainz.org/ws/2/recording/?query=artist:{artist}%20AND%20recording:{title}&fmt=json&limit=1"
            headers = {"User-Agent": "AIHub/1.0"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('recordings'):
                            rec = data['recordings'][0]
                            return {
                                'year': rec.get('first-release-date', 'Unknown')[:4],
                                'genres': [tag['name'] for tag in rec.get('tags', [])[:3]],
                                'type': rec.get('releases', [{}])[0].get('release-group', {}).get('primary-type', 'Unknown')
                            }
            return {}
        except Exception as e:
            logger.error(f"MusicBrainz error: {e}")
            return {}
    
    async def process_now_playing(self, song_data: Dict) -> str:
        """
        Process currently playing song information
        
        Args:
            song_data: {
                'artist': str,
                'title': str,
                'album': str (optional)
            }
            
        Returns:
            Formatted info summary
        """
        artist = song_data.get('artist', '')
        title = song_data.get('title', '')
        album = song_data.get('album', '')
        
        logger.info(f"🎵 Processing: {artist} - {title}")
        
        # Fetch data from APIs
        wiki_data = await self.get_wikipedia_summary(f"{artist} {album}" if album else artist)
        mb_data = await self.get_musicbrainz_info(artist, album if album else title)
        
        if self.local_model:
            # Use local model to process and summarize API data
            logger.info("Using local model to process info...")
            summary = await self.local_model.process_music_info(song_data, wiki_data, mb_data)
        else:
            # Manual formatting if local model disabled
            summary = self._manual_format(song_data, wiki_data, mb_data)
        
        return summary
    
    async def chat_with_context(self, user_message: str, song_context: Optional[str] = None) -> str:
        """
        Chat using main AI with optional song context
        
        Args:
            user_message: User's chat message
            song_context: Optional song info from local model
            
        Returns:
            AI response
        """
        messages = []
        
        if song_context:
            messages.append({
                "role": "system",
                "content": f"Current song context:\n{song_context}\n\nUse this info to answer questions about the music."
            })
        
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return await self.main_ai.chat(messages)
    
    def _manual_format(self, song_data: Dict, wiki: str, mb: Dict) -> str:
        """Fallback formatting without local model"""
        return f"""Song: {song_data.get('title')}
Artist: {song_data.get('artist')}
Album: {song_data.get('album', 'Unknown')}
Year: {mb.get('year', 'Unknown')}
Genres: {', '.join(mb.get('genres', [])) if mb.get('genres') else 'Unknown'}

{wiki[:200] if wiki else 'No additional info available.'}..."""
