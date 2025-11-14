"""
Room WebSocket Handler
Receives events from hang-bot and sends commands
Processes with AI Hub intelligence
Ported from Node.js version
"""

import json
from typing import Dict, List, Any, Optional
from collections import defaultdict
import asyncio

from fastapi import WebSocket, WebSocketDisconnect
from services.wikipedia_service import get_song_info
from config import settings

# Will import providers at runtime to avoid circular dependencies
_providers_cache = None


class RoomState:
    """Room state management"""
    def __init__(self):
        self.current_track: Optional[Dict] = None
        self.history: List[Dict] = []
        self.users: List[Dict] = []
        self.waitlist: List[Dict] = []
        self.conversation_states: Dict[str, Dict] = {}  # userId -> last query
        self.chat_history: List[Dict] = []  # Chat history for AI context
        self.bot_user_id: Optional[str] = None  # Bot's user ID to ignore own messages


async def get_providers():
    """Lazy load providers to avoid circular imports"""
    global _providers_cache
    if _providers_cache is None:
        from providers.cloud.gemini_provider import GeminiProvider
        from providers.cloud.openai_provider import OpenAIProvider
        from providers.cloud.claude_provider import ClaudeProvider
        
        # Import the get_phi3_instance function from main
        try:
            from main import get_phi3_instance
            phi3 = await get_phi3_instance()
        except Exception as e:
            print(f"[ROOM_WS] Could not load Phi-3: {e}")
            phi3 = None
        
        _providers_cache = {
            "gemini": GeminiProvider(settings.GEMINI_API_KEY),
            "openai": OpenAIProvider(settings.OPENAI_API_KEY),
            "claude": ClaudeProvider(settings.CLAUDE_API_KEY),
            "phi3": phi3,
        }
    return _providers_cache


def get_keywords() -> List[str]:
    """Get trigger keywords from settings"""
    raw = (settings.BOT_KEYWORDS or "").strip()
    if not raw:
        return []
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def contains_keyword(text: str) -> bool:
    """Check if text contains any trigger keyword"""
    text_l = (text or "").lower()
    for k in get_keywords():
        if k and k in text_l:
            return True
    return False


def format_track_info(song_info: Dict) -> str:
    """
    Format track info for chat
    
    Args:
        song_info: Song information dictionary
        
    Returns:
        Formatted message string
    """
    msg = f"{song_info.get('title', 'Unknown')} by {song_info.get('artist', 'Unknown')}"
    
    if song_info.get('album'):
        msg += f" from {song_info['album']}"
    if song_info.get('released'):
        msg += f" ({song_info['released']})"
    if song_info.get('isCover'):
        msg += f" - Cover of {song_info.get('coverOriginalArtist')}'s version"
    if song_info.get('genreCombined'):
        msg += f"\nGenres: {song_info['genreCombined']}"
    if song_info.get('summary'):
        msg += f"\n\n{song_info['summary']}"
    
    return msg


async def enrich_track(title: str, artist: str) -> Dict[str, Any]:
    """
    Quick enrichment helper for WebSocket
    Returns basic track info from Wikipedia
    
    Args:
        title: Track title
        artist: Artist name
        
    Returns:
        Dict with song info and formatted text
    """
    try:
        song_info = await get_song_info(title, artist)
        return {
            'song': song_info,
            'formatted': format_track_info(song_info) if song_info else 'No info found.'
        }
    except Exception as e:
        print(f"[ROOM_WS] Error enriching track: {e}")
        return {'formatted': 'Error fetching track info.'}


def update_room_state(state: RoomState, event: Dict):
    """
    Update room state from incoming event
    
    Args:
        state: RoomState instance
        event: Event data
    """
    event_type = event.get('type')
    data = event.get('data', {})
    
    if event_type == 'ROOM_STATE':
        # Initial state from bot
        if 'currentTrack' in data:
            state.current_track = data['currentTrack']
        if 'history' in data:
            state.history = data['history']
        if 'users' in data:
            state.users = data['users']
        if 'waitlist' in data:
            state.waitlist = data['waitlist']
        print(f"[ROOM_WS] Room state initialized: {len(state.users)} users")
    
    elif event_type == 'TRACK_ADVANCE':
        # New song playing
        state.current_track = data
        state.history.insert(0, data)
        if len(state.history) > 50:
            state.history.pop()
        print(f"[ROOM_WS] Track: '{data.get('title')}' by {data.get('artist')}")
    
    elif event_type == 'USER_JOIN':
        user_id = data.get('userId')
        if not any(u.get('userId') == user_id for u in state.users):
            state.users.append(data)
    
    elif event_type == 'USER_LEAVE':
        user_id = data.get('userId')
        state.users = [u for u in state.users if u.get('userId') != user_id]
    
    elif event_type == 'WAITLIST_UPDATE':
        state.waitlist = data.get('waitlist', [])


async def handle_chat_message(data: Dict, room_state: RoomState) -> List[Dict]:
    """
    Handle chat messages - respond to music questions and keywords
    
    Args:
        data: Chat message data
        room_state: RoomState instance
        
    Returns:
        List of command dictionaries to send
    """
    commands = []
    text = data.get('text', '').strip()
    text_lower = text.lower()
    user_id = data.get('userId')
    username = data.get('username', 'User')
    
    # Ignore bot's own messages
    if room_state.bot_user_id and user_id == room_state.bot_user_id:
        return commands
    
    # Add to chat history for AI context
    room_state.chat_history.append({"role": "user", "content": text})
    if len(room_state.chat_history) > settings.DEFAULT_HISTORY_LIMIT * 2:
        room_state.chat_history = room_state.chat_history[-settings.DEFAULT_HISTORY_LIMIT * 2:]
    
    # Check for "tell me more" escalation
    user_state = room_state.conversation_states.get(user_id)
    if 'tell me more' in text_lower and user_state:
        # User wants detailed info about last query
        try:
            enriched = await enrich_track(user_state['title'], user_state['artist'])
            
            # TODO: Send to Gemini Flash for detailed narrative
            # For now, just send the summary
            commands.append({
                'type': 'POST_CHAT',
                'data': {
                    'message': f"Detailed info:\n{enriched.get('song', {}).get('summary', 'No additional details available.')}"
                }
            })
            
            # Clear state after escalation
            del room_state.conversation_states[user_id]
        except Exception as e:
            print(f"[ROOM_WS] Error getting detailed info: {e}")
        return commands
    
    # Check if asking about current track
    is_current_track_question = any(phrase in text_lower for phrase in [
        'tell me about',
        'what song',
        'this song',
        'current song',
        'whats playing',
        "what's playing",
        'now playing'
    ])
    
    if is_current_track_question and room_state.current_track:
        try:
            title = room_state.current_track.get('title')
            artist = room_state.current_track.get('artist')
            print(f"[ROOM_WS] Enriching: '{title}' by {artist}")
            
            enriched = await enrich_track(title, artist)
            
            # Build simple response
            response = enriched.get('formatted', 'No information available.')
            
            # Add "tell me more" prompt
            response += "\n\nSay 'tell me more' for the full story."
            
            commands.append({
                'type': 'POST_CHAT',
                'data': {'message': response}
            })
            
            # Store state for potential escalation
            room_state.conversation_states[user_id] = {
                'title': title,
                'artist': artist,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Clean up old states (> 10 minutes)
            current_time = asyncio.get_event_loop().time()
            expired = [uid for uid, state in room_state.conversation_states.items()
                      if current_time - state.get('timestamp', 0) > 600]
            for uid in expired:
                del room_state.conversation_states[uid]
        
        except Exception as e:
            print(f"[ROOM_WS] Error enriching track: {e}")
            commands.append({
                'type': 'POST_CHAT',
                'data': {'message': "Sorry, I couldn't fetch info for this track."}
            })
        return commands
    
    # Check for keyword triggers (general AI chat)
    if contains_keyword(text):
        print(f"[ROOM_WS] Keyword detected in message from {username}: {text[:50]}...")
        try:
            # Get available providers
            providers = await get_providers()
            
            # Try providers in order of preference (Phi-3 as fallback)
            provider_order = ["gemini", "openai", "claude", "phi3"]
            response_content = None
            used_provider = None
            
            for provider_name in provider_order:
                provider = providers.get(provider_name)
                if provider and provider.is_configured():
                    try:
                        # Prepare messages with personality and history
                        messages = []
                        if settings.DEFAULT_PERSONALITY:
                            messages.append({"role": "system", "content": settings.DEFAULT_PERSONALITY})
                        
                        # Add recent chat history (limit to last few messages for context)
                        recent_history = room_state.chat_history[-6:]
                        messages.extend(recent_history)
                        
                        # Call the AI (reduced tokens for faster responses)
                        print(f"[ROOM_WS] Calling {provider_name} for response...")
                        response = await provider.chat(
                            messages=messages,
                            temperature=0.7,
                            max_tokens=75  # Reduced from 300 for snappy chat responses
                        )
                        
                        response_content = response.get("content")
                        used_provider = provider_name
                        print(f"[ROOM_WS] Got response from {provider_name}")
                        break
                    except Exception as e:
                        print(f"[ROOM_WS] {provider_name} failed: {e}")
                        continue
            
            if response_content:
                # Add assistant response to history
                room_state.chat_history.append({"role": "assistant", "content": response_content})
                
                # Send response to room
                commands.append({
                    'type': 'POST_CHAT',
                    'data': {'message': response_content}
                })
                print(f"[ROOM_WS] Sending AI response using {used_provider}")
            else:
                print("[ROOM_WS] No configured AI provider available")
                commands.append({
                    'type': 'POST_CHAT',
                    'data': {'message': "Sorry, no AI providers are currently available."}
                })
        
        except Exception as e:
            print(f"[ROOM_WS] Error generating AI response: {e}")
            import traceback
            traceback.print_exc()
    
    return commands


async def handle_track_advance(data: Dict, room_state: RoomState) -> List[Dict]:
    """
    Handle new track playing
    
    Args:
        data: Track data
        room_state: RoomState instance
        
    Returns:
        List of command dictionaries to send
    """
    commands = []
    
    # Could implement:
    # - Auto-announce track info
    # - Predict next song based on history
    # - Auto-queue predicted song
    
    # For now, just log
    print(f"[ROOM_WS] New track: '{data.get('title')}' by {data.get('artist')} (DJ: {data.get('djUsername')})")
    
    return commands


async def process_event(event: Dict, room_state: RoomState) -> List[Dict]:
    """
    Process event and generate commands for bot
    
    Args:
        event: Event data
        room_state: RoomState instance
        
    Returns:
        List of command dictionaries to send
    """
    commands = []
    event_type = event.get('type')
    
    if event_type == 'CHAT_MESSAGE':
        # Check if user is asking about music
        chat_commands = await handle_chat_message(event.get('data', {}), room_state)
        commands.extend(chat_commands)
    
    elif event_type == 'TRACK_ADVANCE':
        # New song playing - could trigger auto-response or prediction
        track_commands = await handle_track_advance(event.get('data', {}), room_state)
        commands.extend(track_commands)
    
    elif event_type == 'VOTE':
        # Track voting patterns (no immediate action, just log for learning)
        data = event.get('data', {})
        direction = 'woot' if data.get('direction') == 1 else 'meh'
        print(f"[ROOM_WS] Vote from {data.get('username')}: {direction}")
    
    return commands


async def websocket_room_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint handler for room events
    
    Args:
        websocket: FastAPI WebSocket connection
    """
    await websocket.accept()
    print(f"[ROOM_WS] Bot connected from {websocket.client.host if websocket.client else 'unknown'}")
    
    # Create room state for this connection
    room_state = RoomState()
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            event = json.loads(data)
            print(f"[ROOM_WS] Received: {event.get('type')}")
            
            # Update room state
            update_room_state(room_state, event)
            
            # Process event and generate commands
            commands = await process_event(event, room_state)
            
            # Send commands back to bot
            for cmd in commands:
                await websocket.send_json(cmd)
                print(f"[ROOM_WS] Sent command: {cmd.get('type')}")
    
    except WebSocketDisconnect:
        print("[ROOM_WS] Bot disconnected")
    except Exception as e:
        print(f"[ROOM_WS] Error: {e}")
        await websocket.close()


def setup_room_websocket(app):
    """
    Setup WebSocket endpoint on FastAPI app
    
    Args:
        app: FastAPI application instance
    """
    @app.websocket("/ws/room")
    async def websocket_room(websocket: WebSocket):
        await websocket_room_endpoint(websocket)
    
    print("[ROOM_WS] WebSocket endpoint registered at /ws/room")

