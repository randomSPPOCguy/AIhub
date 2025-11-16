CREATE TABLE IF NOT EXISTS plays (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  played_at_utc TEXT NOT NULL,
  room_id TEXT,
  username TEXT,
  user_id TEXT,
  artist TEXT,
  title TEXT,
  album TEXT,
  year INTEGER,
  genre TEXT,
  provider TEXT,
  source TEXT
);

CREATE INDEX IF NOT EXISTS idx_plays_time ON plays(played_at_utc);
CREATE INDEX IF NOT EXISTS idx_plays_artist_title ON plays(artist, title);

CREATE TABLE IF NOT EXISTS facts (
  play_id INTEGER PRIMARY KEY REFERENCES plays(id) ON DELETE CASCADE,
  wiki_title TEXT,
  wiki_url TEXT,
  discogs_id TEXT,
  discogs_type TEXT,
  mb_artist_id TEXT,
  mb_releasegroup_count INTEGER,
  cover_url TEXT
);

CREATE TABLE IF NOT EXISTS api_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key_hash TEXT NOT NULL UNIQUE,
  label TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_used_at TEXT,
  revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hub_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL UNIQUE,
  username TEXT,
  tone_preference TEXT,          -- snarky | neutral | positive
  favorite_genres TEXT,          -- JSON-encoded array
  favorite_artists TEXT,         -- JSON-encoded array
  notes TEXT,
  current_mood TEXT,             -- negative | neutral | positive
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
