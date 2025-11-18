# AIhub Enrichment Service

Standalone FastAPI service that provides structured enrichment data for subjects (artists, topics, etc.) by querying external providers (Wikipedia, MusicBrainz) with caching, retries, and graceful fallbacks.

## Overview

This service implements the Phase 1 enrichment service as specified in the Project Frank planner. It exposes a `POST /enrich` endpoint that accepts text and optional room context, then returns structured enrichment data including subjects, keywords, facts, and sources.

## Features

- **Wikipedia Provider**: Basic search + summary + URL lookup
- **MusicBrainz Provider**: Artist lookup by name with strict 1 req/sec rate limiting
- **In-Memory LRU Cache**: TTL-based caching (~5 minutes default)
- **Structured Logging**: JSON-formatted logs with trace_id, latency, cache status
- **Graceful Error Handling**: Always returns 200 with partial data, never crashes
- **Retry Logic**: Exponential backoff + jitter for provider calls

## Setup

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
cd python_enrichment
pip install -r requirements.txt
```

### Running the Service

```bash
uvicorn app:app --reload --port 8001
```

Or using Python directly:

```bash
python app.py
```

The service will start on `http://localhost:8001` by default.

## Configuration

Configuration is managed via environment variables. You can set these in your `config.env` file at the project root, or as environment variables.

### Environment Variables

- `ENRICH_PORT` (default: `8001`) - Port to run the service on
- `ENRICH_HOST` (default: `0.0.0.0`) - Host to bind to
- `ENRICH_WIKIPEDIA_ENABLED` (default: `true`) - Enable/disable Wikipedia provider
- `ENRICH_MUSICBRAINZ_ENABLED` (default: `true`) - Enable/disable MusicBrainz provider
- `ENRICH_CACHE_TTL_SECS` (default: `300`) - Cache TTL in seconds (5 minutes)
- `ENRICH_REQUEST_TIMEOUT_SECS` (default: `2.0`) - Request timeout per provider call
- `ENRICH_MAX_RETRIES` (default: `2`) - Maximum retries for provider calls

## API Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0",
  "service": "enrichment"
}
```

### POST /enrich

Enrich text with structured data from external providers.

**Request Body:**
```json
{
  "trace_id": "optional-uuid",
  "text": "who produced this track?",
  "room": {
    "id": "room-id-optional",
    "topic": "hip hop",
    "now_playing": {
      "artist": "Kendrick Lamar",
      "track": "Alright"
    }
  },
  "hints": {
    "language": "en",
    "max_latency_ms": 200,
    "providers": ["wikipedia", "musicbrainz"]
  }
}
```

**Response:**
```json
{
  "version": "1.0",
  "trace_id": "uuid-or-null",
  "subjects": [{
    "name": "Kendrick Lamar",
    "type": "artist",
    "ids": {
      "musicbrainz": "uuid-optional"
    },
    "urls": {
      "wikipedia": "https://en.wikipedia.org/wiki/Kendrick_Lamar",
      "musicbrainz": "https://musicbrainz.org/artist/..."
    }
  }],
  "keywords": [
    "kendrick lamar",
    "hip hop",
    "compton"
  ],
  "facts": [
    "Kendrick Lamar is an American rapper from Compton."
  ],
  "sources": [{
    "provider": "wikipedia",
    "url": "https://en.wikipedia.org/wiki/Kendrick_Lamar",
    "title": "Kendrick Lamar",
    "language": "en"
  }],
  "meta": {
    "confidence": 0.92,
    "cache_status": "miss",
    "enrichment_time_ms": 145.5,
    "partial": false
  }
}
```

## Example Usage

### Using curl

```bash
curl -X POST http://localhost:8001/enrich \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Tell me about Kendrick Lamar",
    "room": {
      "now_playing": {
        "artist": "Kendrick Lamar",
        "track": "Alright"
      }
    },
    "hints": {
      "language": "en",
      "providers": ["wikipedia", "musicbrainz"]
    }
  }'
```

### Using Python

```python
import httpx

response = httpx.post(
    "http://localhost:8001/enrich",
    json={
        "text": "Tell me about Kendrick Lamar",
        "room": {
            "now_playing": {
                "artist": "Kendrick Lamar",
                "track": "Alright"
            }
        }
    }
)
data = response.json()
print(data)
```

## Project Structure

```
python_enrichment/
├── app.py                 # FastAPI entrypoint
├── models.py              # Pydantic request/response models
├── cache.py               # In-memory LRU cache
├── config.py              # Environment variable parsing
├── logging.py             # Structured logging helpers
├── providers/
│   ├── __init__.py
│   ├── wikipedia.py       # Wikipedia provider
│   └── musicbrainz.py     # MusicBrainz provider
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Error Handling

The service is designed to be resilient:

- If one provider fails, data from other providers is still returned
- If all providers fail, an empty enrichment is returned with `meta.partial = true` and low confidence
- All errors are logged but never cause the service to crash
- The service always returns HTTP 200 with valid JSON

## Caching

The service uses an in-memory LRU cache with TTL:

- Cache keys are normalized: `"{type}:{normalized_name}:{language}"`
- Default TTL is 5 minutes (configurable via `ENRICH_CACHE_TTL_SECS`)
- Cache status is reported in `meta.cache_status`: `"hit"`, `"miss"`, or `"partial"`

## Logging

Logs are structured as JSON and include:

- `timestamp`: ISO 8601 timestamp
- `level`: Log level (INFO, WARNING, ERROR)
- `trace_id`: Request trace ID
- `provider`: Provider name (when applicable)
- `latency_ms`: Request latency in milliseconds
- `cache_status`: Cache hit/miss status
- `partial`: Whether enrichment is partial
- `error`: Error message (when applicable)

## Rate Limiting

- **MusicBrainz**: Strictly enforced 1 request per second
- **Wikipedia**: No explicit rate limiting (relies on retries and timeouts)

## Future Enhancements

This is Phase 1 implementation. Future phases may include:

- Redis-based L2 cache
- Additional providers (Wikidata, Discogs, etc.)
- More sophisticated confidence scoring
- Request deduplication
- Predictive cache warming
- Circuit breakers for providers

## License

Part of the AIhub project.

