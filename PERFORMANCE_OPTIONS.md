# Project Frank - Performance Options Analysis

## Current Bottleneck: ONNX Model Inference (11 seconds)

### Option 1: Keep Current Setup (FREE, PRIVATE, SLOW)
**Pros:**
- 100% private - data never leaves your machine
- Zero API costs
- Full control over model

**Cons:**
- 11 second response time (CANNOT hit 1-3s target)
- Limited model quality (phi-3-mini is small)

**When to choose:** Privacy and cost are more important than speed

---

### Option 2: Switch to Cloud API (FAST, COSTS MONEY)
**Recommended: OpenAI GPT-4o-mini or Anthropic Claude Haiku**

**Pros:**
- ✅ 1-3 second response time (MEETS YOUR TARGET)
- ✅ Much better quality responses
- ✅ No GPU/hardware requirements
- ✅ Enrichment cache still works (saves on tokens)

**Cons:**
- Costs ~$0.001-0.003 per request (~$1-3 per 1000 requests)
- Data sent to external API (less privacy)
- Requires API key and internet connection

**Cost estimate for 1000 requests/day:**
- GPT-4o-mini: ~$3-5/month
- Claude Haiku: ~$2-4/month

**When to choose:** Speed and quality are critical, willing to pay small monthly fee

---

### Option 3: Smaller Local Model (FASTER, LOWER QUALITY)
**Use Llama 3.2 1B or Phi-3.5-mini-instruct (quantized)**

**Pros:**
- ✅ 3-5 second response time (closer to target)
- Free and private
- Lower hardware requirements

**Cons:**
- Worse quality than current model
- Still slower than cloud APIs
- May give incomplete/incorrect responses

**When to choose:** Want to stay local but need speed improvement

---

### Option 4: Hybrid Approach (RECOMMENDED FOR PROJECT FRANK)
**Local ONNX for general chat + Cloud API for enriched queries**

**Pros:**
- ✅ Fast responses (1-3s) for important queries
- ✅ Privacy for casual chat
- ✅ Cost-effective (only pay for enriched queries)
- ✅ Best of both worlds

**Cons:**
- More complex setup
- Still has API costs (but lower)

**Implementation:**
- Casual chat: "hey bot how are you?" → Local ONNX (11s, but doesn't matter)
- Important queries: "what was eminem's last album?" → Cloud API (1-3s)

---

## Information Gathering: Language Recommendations

### Current Stack: Python ✅ KEEP IT
**Why Python is PERFECT for enrichment:**
- Excellent Wikipedia/Wikidata/MusicBrainz libraries
- Fast async HTTP with httpx/aiohttp
- Great for NLP and data processing
- Easy to maintain and extend

**Don't switch to another language** - Python is optimal here.

---

### Add Persistent SQLite Cache (CRITICAL IMPROVEMENT)

**Current:** In-memory cache (lost on restart)
**Proposed:** SQLite persistent cache

**Performance improvement:**
- First query: 1.5s (fetch from Wikipedia/MusicBrainz)
- Cached query: <100ms (read from SQLite)

**Database Schema:**
```sql
CREATE TABLE enrichment_cache (
    cache_key TEXT PRIMARY KEY,
    entity_type TEXT,
    entity_name TEXT,
    full_data JSON,
    facts JSON,
    sources JSON,
    created_at INTEGER,
    expires_at INTEGER
);

CREATE INDEX idx_entity ON enrichment_cache(entity_type, entity_name);
```

---

## Recommended Stack for Project Frank

### Information Gathering (Python) ✅
- **Language:** Python 3.11+
- **Framework:** FastAPI (current)
- **APIs:** Wikipedia, Wikidata, MusicBrainz
- **Caching:** SQLite + in-memory
- **Performance:** 100ms (cached) to 1.5s (fresh)

### Information Output (Choose One)

#### A. Local Model (Current)
- **Language:** Python with ONNX Runtime
- **Performance:** 11 seconds
- **Cost:** Free
- **Use case:** Privacy-focused, cost-sensitive

#### B. Cloud API (Recommended)
- **Language:** Node.js or Python
- **Provider:** OpenAI or Anthropic
- **Performance:** 1-3 seconds ✅
- **Cost:** $3-5/month for moderate use
- **Use case:** Speed and quality are priorities

### Core Server (Node.js) ✅
- **Language:** Node.js (current)
- **Why:** Excellent for API routing, WebSockets, real-time
- **Keep it:** No need to change

---

## Final Recommendation for 1-3 Second Target

**To hit your 1-3 second goal, you MUST use a cloud API:**

1. ✅ Add persistent SQLite cache (reduces enrichment to <100ms for cached)
2. ✅ Switch to OpenAI GPT-4o-mini or Anthropic Claude Haiku
3. ✅ Keep Python enrichment service (it's already fast)

**Alternative (if staying local):**
- Use smaller model (Phi-3.5-mini quantized 4-bit)
- Accept 3-5 second response time (best you can do locally)
- Focus on making enrichment super rich to compensate for speed

---

## Next Steps

1. **Decide on model strategy** (cloud vs local)
2. **Implement SQLite enrichment cache** (I'll help with this)
3. **Fix AI prompt issues** (stop saying "from information given")
4. **Expand Wikidata fetching** (get full artist/album/song data)
5. **Update README and create ISSUES.md**
6. **Commit to GitHub branch**

**What's your choice for the model?** This determines our next steps.
