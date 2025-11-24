# 🤖 FOR NEXT AGENT - CRITICAL FILES & ARCHITECTURE

**Last Updated**: 2025-11-24
**Token Limit Warning**: Original session running out - use this guide to continue work

---

## 🎯 ARCHITECTURE CLARITY

### **Go = Enrichment & API Handling**
- Go gathers information from external APIs
- MusicBrainz → Wikidata → Wikipedia pipeline
- Go does NOT generate AI responses
- Go returns JSON data to Rust coordinator

### **Python = AI Response Generation ONLY**
- Python receives enrichment data from Go (via Rust)
- Python calls AI models (Phi-3, Gemini)
- Python formats the response
- Python does NOT handle APIs or enrichment

### **Rust = Orchestration**
- Coordinates between Go, Python, and web UI
- Manages sessions, config, caching
- Routes queries to appropriate handlers

---

## 📁 CRITICAL FILES - PRIORITY ORDER

### 🔴 **HIGHEST PRIORITY** - Needs Immediate Fix

#### 1. `go/frankgo.go` (Go enrichment handler)
**Why Critical:** Enrichment queries are FAILING - this breaks everything

**Current Problem:**
```go
// Line ~50-80 (music_query function)
// Query comes in as: "what was eminems last album?"
// Goes directly to MusicBrainz with typos/punctuation
// Result: 404 errors, no data returned
```

**What Needs Fixing:**
```go
func cleanMusicQuery(query string) string {
    // 1. Remove question marks and punctuation
    query = strings.TrimRight(query, "?!.,")

    // 2. Extract actual artist name from question
    // "what was eminems last album?" → "eminem"
    // Use simple keyword extraction or regex

    // 3. Fix common misspellings
    // "eminems" → "eminem"
    // "beatles" → "the beatles"

    // 4. Trim and lowercase
    query = strings.TrimSpace(strings.ToLower(query))

    return query
}
```

**Where to Look:**
- Function: `go_music_query()` (exported to Rust via CGO)
- API call: `fmt.Sprintf("https://musicbrainz.org/ws/2/artist/?query=%s&fmt=json", ...)`
- Add `cleanMusicQuery()` BEFORE the API call

**Test Cases:**
```go
// Should all work after fix:
"eminems last album?"      → "eminem"
"the beatles"              → "the beatles"
"taylor swift albums"      → "taylor swift"
"mike jones?"              → "mike jones"
```

---

#### 2. `python/ai_gateway.py` (AI response generation)
**Why Critical:** Even when Go returns data, responses are generic

**Current Functions:**
- `generate_response()` - For Phi-3 local model
- `generate_response_with_model()` - For Gemini/other models
- `_generate_with_gemini()` - Gemini API handler
- `_generate_with_phi3()` - Phi-3 handler

**What Works:**
- ✅ Clean output (no debug headers)
- ✅ Error filtering from enrichment
- ✅ Multi-part Gemini responses

**What Needs Work:**
- ❌ Better prompts when enrichment is empty
- ❌ Use enrichment data more effectively when available

**Lines to Check:**
- Line 283-341: `generate_response()` function
- Line 344-392: `generate_response_with_model()` function
- Line 360-368: System prompt construction

**Improvement Needed:**
```python
# Around line 360
if not context_items:
    # Add instruction for when NO enrichment data available
    prompt += """
    No external data was found for this query.
    Provide a helpful response using your general knowledge,
    or politely explain what information you would need.
    """
else:
    # When enrichment IS available, use it better
    prompt += """
    Use the provided context to give a detailed, accurate response.
    """
```

---

### 🟡 **MEDIUM PRIORITY** - Architecture/Coordination

#### 3. `rust/src/coordinator.rs` (Orchestration)
**What It Does:**
- Receives query from web UI
- Classifies intent (Music, Sports, General, etc.)
- Calls Go for enrichment
- Passes enrichment + query to Python
- Returns response to web UI

**Current Flow:**
```rust
handle_query_internal() {
    1. Classify intent (Music/Sports/General)
    2. Match intent:
       - Music → call go.music_query()
       - Sports → call go.sports_query()
       - General → skip external enrichment
    3. Call python.enrich_entity() (Wikipedia/Wikidata)
    4. Combine all enrichment data
    5. Call python.generate_response()
    6. Return result
}
```

**Lines to Know:**
- Line 78-138: `handle_query_internal()` - Main orchestration
- Line 85-109: Intent matching and Go calls
- Line 118-124: Enrichment aggregation
- Line 126-135: Python AI call

**No Changes Needed Right Now** - Works correctly once Go/Python fixed

---

#### 4. `rust/src/session.rs` (Session management)
**What It Does:**
- Creates unique session ID for each user
- Stores conversation history per session
- Auto-deletes after 15 seconds of inactivity
- Background cleanup task runs every 5 seconds

**Status:** ✅ WORKING - No changes needed

**How It Works:**
```rust
SessionManager::new(15) // 15 = timeout seconds
  ↓
get_or_create_session() // Returns session with UUID
  ↓
add_message() // Stores user/assistant messages
  ↓
Background task every 5 seconds:
  cleanup_expired() // Deletes sessions older than 15s
```

---

#### 5. `rust/src/web.rs` (Web server & API)
**What It Does:**
- HTTP endpoints for chat, models, settings
- Handles session IDs from frontend
- Calls coordinator for AI responses
- Returns JSON to browser

**Critical Endpoint:**
```rust
// Line 321-489: chat_endpoint()
POST /api/chat
Request:  { message: "hello", session_id: "optional-uuid" }
Response: { success: true, response: "AI text", session_id: "uuid" }
```

**Status:** ✅ WORKING - Session integration complete

---

### 🟢 **LOW PRIORITY** - UI & Config

#### 6. `rust/static/index.html` (Frontend)
**What Changed:**
- Session ID tracking (line 253)
- Sends session_id with each message (line 320)
- Clears session on "Clear Chat" (line 301)
- Improved Models tab UI (line 379-473)

**Status:** ✅ WORKING

---

#### 7. `rust/src/config.rs` (Configuration)
**What Changed:**
- Default max_tokens: 512 → 1024
- Better system prompt (conversational)
- Temperature: 0.7 (unchanged)

**Status:** ✅ WORKING

---

## 🔧 WHAT TO FIX NEXT (Step-by-Step)

### Step 1: Fix Go Query Cleaning (30 min)

**File:** `go/frankgo.go`
**Function:** `go_music_query()`

```go
// ADD THIS FUNCTION:
func cleanMusicQuery(query string) string {
    // Remove trailing punctuation
    query = strings.TrimRight(query, "?!.,;:")

    // Remove common question words
    questionWords := []string{"what was", "what is", "who is", "tell me about"}
    lowerQuery := strings.ToLower(query)
    for _, qw := range questionWords {
        lowerQuery = strings.Replace(lowerQuery, qw, "", -1)
    }

    // Trim and return
    return strings.TrimSpace(lowerQuery)
}

// THEN IN go_music_query():
func go_music_query(query *C.char, resultBuf *C.char, bufSize C.int) C.int {
    q := C.GoString(query)

    // ADD THIS LINE:
    cleanedQuery := cleanMusicQuery(q)

    // Use cleanedQuery in API call:
    url := fmt.Sprintf("https://musicbrainz.org/ws/2/artist/?query=%s&fmt=json",
        url.QueryEscape(cleanedQuery))

    // ... rest of function
}
```

**Test:**
```bash
# After fix, test these:
cargo run -- --mode web
# Then in browser chat:
"what was eminems last album?"
"the beatles"
"mike jones?"
```

---

### Step 2: Improve Python Fallbacks (15 min)

**File:** `python/ai_gateway.py`
**Function:** `generate_response_with_model()` (line 344)

```python
# Around line 360, UPDATE THIS:
if not context_items:
    # No enrichment data available
    base_prompt = system_prompt if system_prompt else """You are a friendly AI assistant.
The information retrieval system didn't find specific data for this query.
Please provide a helpful response using your general knowledge, or ask clarifying questions."""
else:
    # Enrichment data available
    base_prompt = system_prompt if system_prompt else """You are a friendly AI assistant.
Use the provided context information to give a detailed, accurate response."""
```

---

### Step 3: Test Everything (20 min)

**Test Plan:**

1. **Music Queries:**
   ```
   "eminem" ✓
   "eminems last album?" ✓
   "the beatles" ✓
   "taylor swift" ✓
   ```

2. **General Queries:**
   ```
   "what is python programming?" ✓
   "tell me a joke" ✓
   "hey" ✓
   ```

3. **Session Tests:**
   ```
   - Send message → Note session ID in logs
   - Wait 15 seconds → Check logs for cleanup
   - Send another message → Should get new session ID
   ```

4. **Check Logs Tab:**
   ```
   [WebUI] Chat message [session:abc12345]: hello
   [AIHub] Response generated [session:abc12345]
   [Session] Cleaned up 1 expired session(s)  ← Should see this
   ```

---

## 🗺️ DATA FLOW DIAGRAM

```
User Types Query
       ↓
[Frontend] index.html
       ↓ (POST /api/chat with session_id)
[Backend] web.rs → chat_endpoint()
       ↓
[Session] Get or create session
       ↓
[Coordinator] coordinator.rs → handle_query_internal()
       ↓
[Intent] Classify: Music/Sports/General
       ↓
[Go] frankgo.go → go_music_query()
       ↓ (Query MusicBrainz API)
[Enrichment] Returns JSON data or error
       ↓
[Python] ai_gateway.py → generate_response_with_model()
       ↓ (Call Gemini/Phi-3 with enrichment)
[AI Model] Generates response text
       ↓
[Session] Store message in history
       ↓
[Frontend] Display response
       ↓
After 15s inactivity:
[Session] Background cleanup deletes session
```

---

## 📝 QUICK COMMANDS

```powershell
# Start server
cd rust
cargo run -- --mode web

# Check compilation
cargo check

# View logs
# Open http://127.0.0.1:3000 → LOGS tab

# Test MusicBrainz directly
curl "https://musicbrainz.org/ws/2/artist/?query=eminem&fmt=json"

# Rebuild Go library
cd rust
cargo clean
cargo build
```

---

## 🚨 IMPORTANT NOTES FOR AGENTS

1. **Go Language** = All enrichment & API calls
   - File: `go/frankgo.go`
   - Exports: `go_music_query()`, `go_sports_query()`
   - Called from: `rust/src/ffi.rs` via CGO

2. **Python Language** = AI response generation only
   - File: `python/ai_gateway.py`
   - Functions: `generate_response()`, `generate_response_with_model()`
   - Models: Phi-3 (local), Gemini (cloud)

3. **Rust Language** = Orchestration, web server, sessions
   - Coordinator: `rust/src/coordinator.rs`
   - Web server: `rust/src/web.rs`
   - Sessions: `rust/src/session.rs`

4. **Session Cleanup**
   - Happens automatically every 5 seconds
   - Deletes sessions inactive for 15+ seconds
   - Check logs to verify: `[Session] Cleaned up X expired session(s)`

5. **Response Format**
   - Web UI: `clean_output=true` (just AI text)
   - TUI: `clean_output=false` (debug headers + data)

---

## 📚 RELATED DOCS

- **RECENT_CHANGES.md** - Detailed implementation notes
- **QUICK_START.md** - How to run & test
- **docs/architecture/PROJECT_SPEC.md** - Full architecture
- **docs/user-guide/SETUP.md** - Setup instructions

---

## ✅ COMPLETION CHECKLIST

- [ ] Read this entire file
- [ ] Fix `go/frankgo.go` query cleaning
- [ ] Update `python/ai_gateway.py` prompts
- [ ] Test music queries (eminem, beatles, etc.)
- [ ] Test general queries (python, jokes)
- [ ] Verify sessions auto-delete after 15s
- [ ] Check LOGS tab for session cleanup messages
- [ ] Update this file with any new findings

---

**Remember:**
- **Go** gathers the data
- **Python** generates the response
- **Rust** coordinates everything
- **Sessions** auto-cleanup after 15 seconds
