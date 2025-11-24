# Quick Start Guide

## Start the Server

```powershell
cd rust
cargo run -- --mode web
```

Then open: **http://127.0.0.1:3000**

---

## What Just Got Added

✅ **Session Management** - Conversations auto-delete after 15 seconds
✅ **Clean Responses** - No more debug headers in chat
✅ **Fixed Gemini Error** - Multi-part responses now work
✅ **Better Models UI** - Organized by speed/cost
✅ **Longer Responses** - Max tokens increased 512→1024

---

## Test It

1. **Chat Tab** - Send "hey" → Should get friendly response
2. **Models Tab** - See categorized Gemini models at top
3. **Logs Tab** - Watch for session IDs like `[session:abc12345]`
4. **Wait 15 seconds** - Check logs for session cleanup

---

## Known Issue: Enrichment Needs Work

Responses are generic because:
- MusicBrainz queries fail with typos
- Question marks break queries
- No fallback when enrichment fails

**See `docs/RECENT_CHANGES.md` for detailed fix plan**

---

## File Summary

- **RECENT_CHANGES.md** - Complete implementation details & fixes
- **go/frankgo.go** - [NEEDS FIX] Clean queries before MusicBrainz
- **python/ai_gateway.py** - [DONE] Clean output + better prompts
- **rust/src/session.rs** - [NEW] Session management
- **rust/src/web.rs** - [DONE] Integrated sessions
