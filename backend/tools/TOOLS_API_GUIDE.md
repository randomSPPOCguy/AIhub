# AI Hub Information Tools
## Wikipedia & MusicBrainz Integration

### Overview
The AI Hub now has tools that can fetch real-time information about artists, albums, and music:

- **Wikipedia**: Get summaries about artists, bands, albums
- **MusicBrainz**: Fetch metadata (album year, genres, artist info)
- **Genre Normalization**: Standardize genre labels

### API Endpoints

#### 1. Wikipedia Search
```
POST /api/tools/wikipedia/search
```

**Request:**
```json
{
  "query": "Led Zeppelin",
  "sentences": 3
}
```

**Response:**
```json
{
  "title": "Led Zeppelin",
  "summary": "Led Zeppelin were an English rock band...",
  "url": "https://en.wikipedia.org/wiki/Led_Zeppelin"
}
```

#### 2. MusicBrainz Lookup
```
POST /api/tools/musicbrainz/lookup
```

**Request:**
```json
{
  "artist": "Pink Floyd",
  "album": "The Dark Side of the Moon"
}
```

**Response:**
```json
{
  "artist": "Pink Floyd",
  "album": "The Dark Side of the Moon",
  "year": 1973,
  "genre": ["progressive rock", "psychedelic rock", "art rock"],
  "source": "musicbrainz"
}
```

#### 3. Genre Normalization
```
GET /api/tools/genres/normalize?genre=alt-rock
```

**Response:**
```json
{
  "input": "alt-rock",
  "normalized": "Alternative Rock",
  "category": "Rock",
  "tags": ["rock", "alternative"]
}
```

### Testing

**Terminal #1: Start AI Hub with tools**
```powershell
cd C:\Users\markq\bot\ai_hub
python run.py
```

**Terminal #2: Test the tools**
```powershell
cd C:\Users\markq\bot\ai_hub
python test_tools.py
```

### Future Enhancements

1. **Tool Integration with AI Chat**
   - Allow AI to automatically call these tools when answering questions
   - Example: "What year was Dark Side of the Moon released?" → AI calls MusicBrainz

2. **Consistent Genre Labels**
   - Build a database of artist → primary genre mappings
   - Use MusicBrainz + manual curation for accuracy

3. **Additional Sources**
   - Last.fm API for listening stats
   - Discogs for detailed discography
   - Spotify API for popularity metrics

### Usage in Bot

The bot can now ask the AI Hub to fetch information:

```python
# Example: Get album info before queueing
async def get_album_info(artist: str, album: str):
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            "http://localhost:8000/api/tools/musicbrainz/lookup",
            json={"artist": artist, "album": album}
        )
        return await response.json()
```

This provides the AI with factual, real-time data instead of relying on training data!
