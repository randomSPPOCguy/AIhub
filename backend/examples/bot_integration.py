"""
Example: Integrating AI Hub with a Discord/Music Bot
Demonstrates how to use AI Hub in your chatbot applications
"""
import asyncio
from typing import Dict, List
import aiohttp


class MusicBotAI:
    """
    Example AI integration for a music bot (like your turntable.fm bot)
    
    This shows how to add AI-powered features to your existing bot:
    - Music recommendations
    - Chat responses
    - User interaction
    """
    
    def __init__(self, ai_hub_url: str = "http://localhost:8000"):
        self.ai_hub_url = ai_hub_url
        self.user_conversations: Dict[str, List[Dict]] = {}
        self.system_prompt = """You are a friendly music bot DJ assistant. 
You help users discover music, chat about songs, and create a fun atmosphere.
Keep responses casual and concise (1-2 sentences usually).
Show enthusiasm for music!"""
    
    async def get_ai_response(
        self,
        user_id: str,
        message: str,
        provider: str = "gemini",
        use_context: bool = True
    ) -> str:
        """
        Get AI response for a user message
        
        Args:
            user_id: Unique user identifier
            message: User's message
            provider: AI provider to use (gemini/openai/claude)
            use_context: Whether to maintain conversation history
        """
        # Initialize conversation history for new users
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = [
                {"role": "system", "content": self.system_prompt}
            ]
        
        # Build messages
        messages = self.user_conversations[user_id].copy() if use_context else [
            {"role": "system", "content": self.system_prompt}
        ]
        messages.append({"role": "user", "content": message})
        
        # Call AI Hub
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.ai_hub_url}/api/chat",
                json={
                    "provider": provider,
                    "messages": messages,
                    "temperature": 0.8,
                    "max_tokens": 150
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ai_response = data['content']
                    
                    # Update conversation history
                    if use_context:
                        self.user_conversations[user_id].append(
                            {"role": "user", "content": message}
                        )
                        self.user_conversations[user_id].append(
                            {"role": "assistant", "content": ai_response}
                        )
                        
                        # Keep only last 10 exchanges (20 messages)
                        if len(self.user_conversations[user_id]) > 21:  # +1 for system
                            self.user_conversations[user_id] = (
                                [self.user_conversations[user_id][0]] +  # Keep system
                                self.user_conversations[user_id][-20:]    # Last 20 messages
                            )
                    
                    return ai_response
                else:
                    error_data = await response.json()
                    raise Exception(f"AI Hub error: {error_data.get('detail')}")
    
    async def get_music_recommendation(
        self,
        context: str,
        provider: str = "claude"
    ) -> str:
        """Get music recommendation based on context"""
        prompt = f"""Based on this context: {context}
        
Recommend ONE song (include artist and song name).
Keep it brief and explain why in one sentence."""
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.ai_hub_url}/api/chat",
                json={
                    "provider": provider,
                    "messages": [
                        {"role": "system", "content": "You are a music recommendation expert."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.9,
                    "max_tokens": 100
                }
            ) as response:
                data = await response.json()
                return data['content']
    
    async def analyze_song(
        self,
        song_name: str,
        artist: str,
        provider: str = "openai"
    ) -> str:
        """Get brief analysis/facts about a song"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.ai_hub_url}/api/chat",
                json={
                    "provider": provider,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Give me one interesting fact about '{song_name}' by {artist} in 1-2 sentences."
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 80
                }
            ) as response:
                data = await response.json()
                return data['content']
    
    def clear_user_context(self, user_id: str):
        """Clear conversation history for a user"""
        if user_id in self.user_conversations:
            del self.user_conversations[user_id]


# Example usage with your bot
async def example_bot_integration():
    """
    Example showing how to integrate with your existing bot
    """
    bot_ai = MusicBotAI()
    
    # Simulate different bot events
    
    # 1. User asks a question
    print("=== User Chat ===")
    response = await bot_ai.get_ai_response(
        user_id="user123",
        message="What genre is good for working out?"
    )
    print(f"Bot: {response}\n")
    
    # 2. Follow-up question (with context)
    response = await bot_ai.get_ai_response(
        user_id="user123",
        message="Give me an example"
    )
    print(f"Bot: {response}\n")
    
    # 3. Song recommendation
    print("=== Music Recommendation ===")
    recommendation = await bot_ai.get_music_recommendation(
        context="User is studying late at night and needs focus"
    )
    print(f"Recommendation: {recommendation}\n")
    
    # 4. Song analysis (when a song starts playing)
    print("=== Song Analysis ===")
    analysis = await bot_ai.analyze_song(
        song_name="Bohemian Rhapsody",
        artist="Queen"
    )
    print(f"Fun fact: {analysis}\n")
    
    # 5. Different user interaction
    print("=== Different User ===")
    response = await bot_ai.get_ai_response(
        user_id="user456",
        message="Is this bot any good?",
        provider="claude"  # Try different provider
    )
    print(f"Bot: {response}\n")


# Example: Integration with WebSocket bot (like your turntable.fm bot)
class WebSocketBotWithAI:
    """
    Example integration with WebSocket-based bot
    """
    
    def __init__(self):
        self.ai = MusicBotAI()
    
    async def handle_message(self, event_data: dict):
        """Handle incoming WebSocket message"""
        event_type = event_data.get('type')
        
        if event_type == 'chat':
            # User sent a chat message
            user_id = event_data['user_id']
            username = event_data['username']
            message = event_data['message']
            
            # Check if message is directed at bot
            if '@bot' in message.lower() or message.startswith('!'):
                # Get AI response
                clean_message = message.replace('@bot', '').replace('!', '').strip()
                
                try:
                    response = await self.ai.get_ai_response(
                        user_id=user_id,
                        message=clean_message,
                        provider="gemini"  # Fast and free
                    )
                    
                    # Send response back (your send_chat method)
                    print(f"Send to room: @{username} {response}")
                    
                except Exception as e:
                    print(f"AI error: {e}")
        
        elif event_type == 'song_start':
            # New song started playing
            song_name = event_data.get('song_name')
            artist = event_data.get('artist')
            
            # Occasionally share a fun fact (10% chance)
            import random
            if random.random() < 0.1:
                try:
                    fact = await self.ai.analyze_song(song_name, artist)
                    print(f"Send to room: 🎵 {fact}")
                except Exception as e:
                    print(f"Song analysis error: {e}")


# Advanced example: Provider fallback
async def example_smart_routing():
    """
    Example: Try providers in order until one works
    """
    bot_ai = MusicBotAI()
    providers = ["gemini", "openai", "claude"]
    
    message = "What's a good song for a rainy day?"
    
    for provider in providers:
        try:
            response = await bot_ai.get_ai_response(
                user_id="test_user",
                message=message,
                provider=provider
            )
            print(f"✓ {provider}: {response}")
            break
        except Exception as e:
            print(f"✗ {provider} failed: {e}")
            continue


# Example: Rate limiting (important for production!)
class RateLimitedBotAI(MusicBotAI):
    """
    Extended version with rate limiting
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_last_request = {}
        self.cooldown_seconds = 3  # 3 seconds between requests per user
    
    async def get_ai_response(self, user_id: str, message: str, **kwargs):
        """Rate-limited version"""
        import time
        
        # Check cooldown
        now = time.time()
        if user_id in self.user_last_request:
            elapsed = now - self.user_last_request[user_id]
            if elapsed < self.cooldown_seconds:
                remaining = self.cooldown_seconds - elapsed
                raise Exception(f"Please wait {remaining:.1f}s before next request")
        
        # Update timestamp
        self.user_last_request[user_id] = now
        
        # Call parent method
        return await super().get_ai_response(user_id, message, **kwargs)


if __name__ == "__main__":
    # Run examples
    print("🤖 AI Hub Bot Integration Examples\n")
    print("Make sure AI Hub is running: python run.py\n")
    print("="*60 + "\n")
    
    asyncio.run(example_bot_integration())
    
    print("\n" + "="*60)
    print("\n💡 Integration Tips:")
    print("  1. Use Gemini for fast, free responses")
    print("  2. Use Claude for better conversation quality")
    print("  3. Implement rate limiting to prevent abuse")
    print("  4. Keep conversation history for context")
    print("  5. Add error handling and fallback providers")
