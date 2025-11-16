/**
 * Room WebSocket - Receives events from hang-bot and sends commands
 * 
 * Receives ALL room events via WebSocket
 * Processes with AI Hub intelligence
 * Sends commands back to bot
 */

import { WebSocketServer } from 'ws';
import { getSongInfo, getAlbumInfo, getArtistInfo } from '../services/wikipedia.js';
import { mbSearchRecording, sleep } from '../services/musicbrainz.js';

const log = (msg) => console.log(`[ROOM_WS] ${msg}`);

/**
 * Quick enrichment helper for WebSocket
 * Returns basic track info from Wikipedia
 */
async function enrichTrack(title, artist) {
  try {
    const songInfo = await getSongInfo(title, artist);
    return {
      song: songInfo,
      formatted: songInfo ? formatTrackInfo(songInfo) : 'No info found.'
    };
  } catch (error) {
    log(`Error enriching track: ${error.message}`);
    return { formatted: 'Error fetching track info.' };
  }
}

/**
 * Format track info for chat
 */
function formatTrackInfo(songInfo) {
  let msg = `${songInfo.title || 'Unknown'} by ${songInfo.artist || 'Unknown'}`;
  
  if (songInfo.album) msg += ` from ${songInfo.album}`;
  if (songInfo.released) msg += ` (${songInfo.released})`;
  if (songInfo.isCover) msg += ` - Cover of ${songInfo.coverOriginalArtist}'s version`;
  if (songInfo.genres?.length) msg += `\nGenres: ${songInfo.genres.join(', ')}`;
  if (songInfo.summary) msg += `\n\n${songInfo.summary}`;
  
  return msg;
}

/**
 * Setup WebSocket server for room events
 */
export function setupRoomWebSocket(server) {
  const wss = new WebSocketServer({ 
    server, 
    path: '/ws/room',
    clientTracking: true
  });

  log('WebSocket server initialized at /ws/room');

  wss.on('connection', (ws, req) => {
    log(`Bot connected from ${req.socket.remoteAddress}`);

    // Store room state for this connection
    const roomState = {
      currentTrack: null,
      history: [],
      users: [],
      waitlist: [],
      conversationStates: new Map() // userId -> last query
    };

    ws.on('message', async (data) => {
      try {
        const event = JSON.parse(data.toString());
        log(`Received: ${event.type}`);

        // Update room state
        updateRoomState(roomState, event);

        // Process event and generate commands
        const commands = await processEvent(event, roomState);

        // Send commands back to bot
        for (const cmd of commands) {
          ws.send(JSON.stringify(cmd));
          log(`Sent command: ${cmd.type}`);
        }

      } catch (error) {
        console.error(`[ROOM_WS] Error processing event: ${error.message}`);
      }
    });

    ws.on('close', () => {
      log('Bot disconnected');
    });

    ws.on('error', (error) => {
      console.error(`[ROOM_WS] WebSocket error: ${error.message}`);
    });
  });

  return wss;
}

/**
 * Update room state from incoming event
 */
function updateRoomState(state, event) {
  switch (event.type) {
    case 'ROOM_STATE':
      // Initial state from bot
      Object.assign(state, event.data);
      log(`Room state initialized: ${state.users?.length || 0} users`);
      break;

    case 'TRACK_ADVANCE':
      // New song playing
      state.currentTrack = event.data;
      state.history.unshift(event.data);
      if (state.history.length > 50) state.history.pop();
      log(`Track: "${event.data.title}" by ${event.data.artist}`);
      break;

    case 'USER_JOIN':
      if (!state.users.find(u => u.userId === event.data.userId)) {
        state.users.push(event.data);
      }
      break;

    case 'USER_LEAVE':
      state.users = state.users.filter(u => u.userId !== event.data.userId);
      break;

    case 'WAITLIST_UPDATE':
      state.waitlist = event.data.waitlist;
      break;
  }
}

/**
 * Process event and generate commands for bot
 */
async function processEvent(event, roomState) {
  const commands = [];

  switch (event.type) {
    case 'CHAT_MESSAGE':
      // Check if user is asking about music
      const chatCommands = await handleChatMessage(event.data, roomState);
      commands.push(...chatCommands);
      break;

    case 'TRACK_ADVANCE':
      // New song playing - could trigger auto-response or prediction
      const trackCommands = await handleTrackAdvance(event.data, roomState);
      commands.push(...trackCommands);
      break;

    case 'VOTE':
      // Track voting patterns (no immediate action, just log for learning)
      log(`Vote from ${event.data.username}: ${event.data.direction === 1 ? 'woot' : 'meh'}`);
      break;
  }

  return commands;
}

/**
 * Handle chat messages - respond to music questions
 */
async function handleChatMessage(data, roomState) {
  const commands = [];
  const text = data.text.toLowerCase().trim();

  // Check for "tell me more" escalation
  const userState = roomState.conversationStates.get(data.userId);
  if (text.includes('tell me more') && userState) {
    // User wants detailed info about last query
    try {
      const enriched = await enrichTrack(userState.title, userState.artist);
      
      // TODO: Send to Gemini Flash for detailed narrative
      // For now, just send the summary
      commands.push({
        type: 'POST_CHAT',
        data: { 
          message: `Detailed info:\n${enriched.song?.summary || 'No additional details available.'}` 
        }
      });

      // Clear state after escalation
      roomState.conversationStates.delete(data.userId);
    } catch (error) {
      console.error(`[ROOM_WS] Error getting detailed info: ${error.message}`);
    }
    return commands;
  }

  // Check if asking about current track
  const isCurrentTrackQuestion = 
    text.includes('tell me about') ||
    text.includes('what song') ||
    text.includes('this song') ||
    text.includes('current song') ||
    text.includes('whats playing') ||
    text.includes('what\'s playing') ||
    text.includes('now playing');

  if (isCurrentTrackQuestion && roomState.currentTrack) {
    try {
      const { title, artist } = roomState.currentTrack;
      log(`Enriching: "${title}" by ${artist}`);

      const enriched = await enrichTrack(title, artist);

      // Build simple response (Phi-3 will process this in future)
      let response = enriched.formatted || buildSimpleResponse(enriched);
      
      // Add "tell me more" prompt
      response += "\n\nSay 'tell me more' for the full story.";

      commands.push({
        type: 'POST_CHAT',
        data: { message: response }
      });

      // Store state for potential escalation
      roomState.conversationStates.set(data.userId, {
        title,
        artist,
        timestamp: Date.now()
      });

      // Clean up old states (> 10 minutes)
      for (const [userId, state] of roomState.conversationStates.entries()) {
        if (Date.now() - state.timestamp > 600000) {
          roomState.conversationStates.delete(userId);
        }
      }

    } catch (error) {
      console.error(`[ROOM_WS] Error enriching track: ${error.message}`);
      commands.push({
        type: 'POST_CHAT',
        data: { message: `Sorry, I couldn't fetch info for this track.` }
      });
    }
  }

  return commands;
}

/**
 * Handle new track playing
 */
async function handleTrackAdvance(data, roomState) {
  const commands = [];

  // Could implement:
  // - Auto-announce track info
  // - Predict next song based on history
  // - Auto-queue predicted song

  // For now, just log
  log(`New track: "${data.title}" by ${data.artist} (DJ: ${data.djUsername})`);

  return commands;
}

/**
 * Build simple response from enriched data (fallback if formatted not available)
 */
function buildSimpleResponse(enriched) {
  if (!enriched.song) return 'No information available.';

  const parts = [
    `${enriched.song.title} by ${enriched.song.artist}`,
    enriched.song.album ? `Album: ${enriched.song.album}` : null,
    enriched.song.released ? `Released: ${enriched.song.released}` : null,
    enriched.song.genreCombined ? `Genres: ${enriched.song.genreCombined}` : null,
    enriched.song.length ? `Duration: ${enriched.song.length}` : null
  ].filter(Boolean);

  return parts.join('\n');
}
