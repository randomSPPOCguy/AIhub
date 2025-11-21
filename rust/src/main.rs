use project_frank::api_chain::PythonBridge;
use project_frank::cache::CacheStore;
use project_frank::ffi::{CppBridge, GoBridge};
use project_frank::intent::{Intent, IntentClassifier};
use project_frank::nlg_processor;
use project_frank::tui;
use anyhow::{Context, Result};
use serde_json::Value;

fn main() -> Result<()> {
    let mut coordinator = AppCoordinator::new()?;
    tui::run(&mut coordinator)
}

pub struct AppCoordinator {
    cache: CacheStore,
    python: PythonBridge,
    go: GoBridge,
    cpp: CppBridge,
    classifier: IntentClassifier,
}

impl AppCoordinator {
    pub fn new() -> Result<Self> {
        Ok(Self {
            cache: CacheStore::initialize().context("initializing cache")?,
            python: PythonBridge::new().context("initializing python bridge")?,
            go: GoBridge,
            cpp: CppBridge,
            classifier: IntentClassifier,
        })
    }

    fn request_enrichment(&self, key: &str, entity: &str, entity_type: &str) -> Result<Value> {
        if let Some(cached) = self.cache.get(key)? {
            return Ok(cached.payload);
        }
        let enrichment = self.python.enrich_entity(entity, entity_type)?;
        self.cache.set(key, &enrichment, None)?;
        Ok(enrichment)
    }
}

impl tui::QueryEngine for AppCoordinator {
    fn handle_query(&mut self, query: &str) -> Result<String> {
        self.cache.purge_expired().ok();

        let intent = self.classifier.classify(query);
        let mut enrichment_chunks = Vec::new();
        let mut sources = Vec::new();

        match intent {
            Intent::Music => {
                if let Ok(payload) = self.go.music_query(query) {
                    enrichment_chunks.push(payload.clone());
                    sources.push("Go:music".into());
                }
            }
            Intent::Sports => {
                if let Ok(payload) = self.go.sports_query(query) {
                    enrichment_chunks.push(payload.clone());
                    sources.push("Go:sports".into());
                }
            }
            Intent::Game => {
                if let Ok(payload) = self.cpp.game_query(query) {
                    enrichment_chunks.push(payload.clone());
                    sources.push("C++:game".into());
                }
                if let Ok(status) = self.cpp.discord_status() {
                    enrichment_chunks.push(status);
                    sources.push("C++:discord".into());
                }
            }
            Intent::General => {}
        }

        let entity_type = match intent {
            Intent::Music => "artist",
            Intent::Sports => "team",
            Intent::Game => "franchise",
            Intent::General => "topic",
        };

        let cache_key = format!("enrich::{entity_type}::{query}");
        if let Ok(enriched) = self.request_enrichment(&cache_key, query, entity_type) {
            if let Ok(pretty) = serde_json::to_string_pretty(&enriched) {
                enrichment_chunks.push(pretty);
                sources.push("Python:enrichment".into());
            }
        }

        let response = self
            .python
            .generate_response(query, &enrichment_chunks)
            .unwrap_or_else(|_| {
                nlg_processor::fallback_response(&nlg_processor::NlgRequest {
                    query,
                    enrichment: &enrichment_chunks,
                    sources: &sources,
                })
            });

        Ok(response)
    }
}
