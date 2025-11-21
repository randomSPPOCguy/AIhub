use anyhow::{Context, Result};
use chrono::{Duration, Utc};
use parking_lot::Mutex;
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use std::env;
use std::path::{Path, PathBuf};
use std::sync::Arc;

#[derive(Clone)]
pub struct CacheStore {
    conn: Arc<Mutex<Connection>>,
    default_ttl: Duration,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CacheRecord {
    pub key: String,
    pub payload: serde_json::Value,
}

impl CacheStore {
    pub fn initialize() -> Result<Self> {
        let path = env::var("FRANK_CACHE_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("cache.sqlite3"));
        Self::new(path)
    }

    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self> {
        if let Some(parent) = path.as_ref().parent() {
            if !parent.as_os_str().is_empty() {
                std::fs::create_dir_all(parent)?;
            }
        }
        let conn = Connection::open(path)?;
        run_migrations(&conn)?;
        Ok(Self {
            conn: Arc::new(Mutex::new(conn)),
            default_ttl: Duration::minutes(30),
        })
    }

    pub fn get(&self, key: &str) -> Result<Option<CacheRecord>> {
        let now = Utc::now();
        let mut guard = self.conn.lock();
        let record = guard
            .query_row(
                "SELECT payload FROM enrichment_cache WHERE key = ?1 AND expires_at > ?2",
                params![key, now.timestamp()],
                |row| {
                    let payload: String = row.get(0)?;
                    Ok(CacheRecord {
                        key: key.to_owned(),
                        payload: serde_json::from_str(&payload)
                            .context("failed parsing cached payload")?,
                    })
                },
            )
            .optional()?;
        Ok(record)
    }

    pub fn set<V: Serialize>(&self, key: &str, payload: &V, ttl: Option<Duration>) -> Result<()> {
        let expires_at = Utc::now() + ttl.unwrap_or(self.default_ttl);
        let mut guard = self.conn.lock();
        guard.execute(
            "REPLACE INTO enrichment_cache (key, payload, expires_at) VALUES (?1, ?2, ?3)",
            params![key, serde_json::to_string(payload)?, expires_at.timestamp()],
        )?;
        Ok(())
    }

    pub fn purge_expired(&self) -> Result<()> {
        let mut guard = self.conn.lock();
        guard.execute(
            "DELETE FROM enrichment_cache WHERE expires_at <= ?1",
            params![Utc::now().timestamp()],
        )?;
        Ok(())
    }
}

fn run_migrations(conn: &Connection) -> Result<()> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let schema_path = manifest_dir
        .parent()
        .map(|parent| parent.join("sql").join("schema.sql"))
        .context("cannot locate sql/schema.sql")?;
    let schema =
        std::fs::read_to_string(&schema_path).with_context(|| format!("reading {schema_path:?}"))?;
    conn.execute_batch(&schema)?;
    Ok(())
}
