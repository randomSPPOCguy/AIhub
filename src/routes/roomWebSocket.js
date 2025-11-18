/**
 * Room WebSocket - Receives events from hang-bot and sends commands
 * 
 * Receives ALL room events via WebSocket
 * Processes with AI Hub intelligence
 * Sends commands back to bot
 */

import { WebSocketServer } from "ws";
import { getSongInfo, getAlbumInfo, getArtistInfo } from "../services/wikipedia.js";
import { mbSearchRecording, sleep } from "../services/musicbrainz.js";
import { logger } from "../utils/logger.js";

const wsInfo = (message, meta) => logger.info(`[ROOM_WS] ${message}`, meta);
const wsWarn = (message, meta) => logger.warn(`[ROOM_WS] ${message}`, meta);
const wsError = (message, meta) => logger.error(`[ROOM_WS] ${message}`, meta);
const wsDebug = (message, meta) => logger.debug(`[ROOM_WS] ${message}`, meta);

/**
 * Quick enrichment helper for WebSocket
 * Returns basic track info from Wikipedia
 */
async function enrichTrack(title, artist) {
  try {
    const songInfo = await getSongInfo(title, artist);
    return {
      song: songInfo,
      formatted: songInfo ? formatTrackInfo(songInfo) : "No info found."
    };
  } catch (error) {
    wsWarn(`Error enriching track: ${error.message}`);
    return { formatted: "Error fetching track info." };
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
    path: "/ws/room",
    clientTracking: true
  });

  wsInfo("WebSocket server initialized", { path: "/ws/room" });

  wss.on("connection", (ws, req) => {
    wsInfo("Room bot connected", { remoteAddress: req.socket.remoteAddress });

    // Store room state for this connection
    const roomState = {
      currentTrack: null,
      history: [],
      users: [],
      waitlist: [],
      conversationStates: new Map() // userId -> last query
    };

    ws.on("message", async (data) => {
      try {
        const event = JSON.parse(data.toString());
        wsDebug("Received room event", { type: event.type });

        // Update room state
        updateRoomState(roomState, event);

        // Process event and generate commands
        const commands = await processEvent(event, roomState);

        // Send commands back to bot
        for (const cmd of commands) {
          ws.send(JSON.stringify(cmd));
          wsDebug("Sent command to bot", { type: cmd.type });
        }

      } catch (error) {
        wsError("Error processing room event", { error: error.message });
      }
    });

    ws.on("close", () => {
      wsInfo("Room bot disconnected");
    });

    ws.on("error", (error) => {
      wsError("Room WebSocket error", { error: error.message });
    });
  });

  return wss;
}

/**
 * Update room state from incoming event
 */
function updateRoomState(state, event) {
  switch (event.type) {
    case "ROOM_STATE":
      // Initial state from bot
      Object.assign(state, event.data);
      wsInfo("Room state initialized", { users: state.users?.length || 0 });
      break;

    case "TRACK_ADVANCE":
      // New song playing
      state.currentTrack = event.data;
      state.history.unshift(event.data);
      if (state.history.length > 50) state.history.pop();
      wsInfo("Track changed", {
        title: event.data.title,
        artist: event.data.artist
      });
      break;

    case "USER_JOIN":
      if (!state.users.find((u) => u.userId === event.data.userId)) {
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

    case "VOTE":
      // Track voting patterns (no immediate action, just log for learning)
      wsDebug("Vote received", {
        user: event.data.username,
        direction: event.data.direction === 1 ? "woot" : "meh"
      });
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
      wsError("Error getting detailed info", { error: error.message });
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
      wsInfo("Enriching track for chat prompt", { title, artist });

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
      wsError("Error enriching track for chat response", { error: error.message });
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
  wsInfo("New track announced", {
    title: data.title,
    artist: data.artist,
    dj: data.djUsername
  });

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
