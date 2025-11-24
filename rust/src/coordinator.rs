use anyhow::{Context, Result};
use crate::api_chain::PythonBridge;
use crate::cache::CacheStore;
use crate::ffi::{CppBridge, GoBridge};
use crate::intent::{Intent, IntentClassifier};
use crate::nlg_processor;
use crate::tui::QueryEngine;
use serde_json::Value;

/// Central orchestrator that coordinates enrichment pipelines and LLM calls.
pub struct AppCoordinator {
    pub cache: CacheStore,
    pub python: PythonBridge,
    pub go: GoBridge,
    pub cpp: CppBridge,
    pub classifier: IntentClassifier,
}

impl AppCoordinator {
    pub fn new() -> Result<Self> {
        let python = PythonBridge::new().context("initializing python bridge")?;
        // Pre-warm the Phi-3 model at startup to avoid first-query latency
        eprintln!("Warming up the Phi-3 model (first run may take a minute)...");
        match python.warmup_model() {
            Ok(msg) => eprintln!("{}", msg),
            Err(e) => eprintln!("Model warmup warning: {}", e),
        }

        Ok(Self {
            cache: CacheStore::initialize().context("initializing cache")?,
            python,
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

impl QueryEngine for AppCoordinator {
    fn handle_query(&mut self, query: &str) -> Result<String> {
        self.handle_query_internal(query, false)
    }

    fn handle_query_with_model(
        &mut self,
        query: &str,
        model_type: &str,
        model_name: &str,
        api_key: &str,
        temperature: f32,
        max_tokens: u32,
        system_prompt: &str,
        clean_output: bool,
    ) -> Result<String> {
        self.handle_query_with_model_internal(
            query,
            model_type,
            model_name,
            api_key,
            temperature,
            max_tokens,
            system_prompt,
            clean_output,
        )
    }
}

impl AppCoordinator {
    /// Handle a query with clean output option (for web UI)
    pub fn handle_query_clean(&mut self, query: &str, clean_output: bool) -> Result<String> {
        self.handle_query_internal(query, clean_output)
    }

    fn handle_query_internal(&mut self, query: &str, clean_output: bool) -> Result<String> {
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
            .generate_response(query, &enrichment_chunks, clean_output)
            .unwrap_or_else(|_| {
                nlg_processor::fallback_response(&nlg_processor::NlgRequest {
                    query,
                    enrichment: &enrichment_chunks,
                    sources: &sources,
                })
            });

        Ok(response)
    }

    fn handle_query_with_model_internal(
        &mut self,
        query: &str,
        model_type: &str,
        model_name: &str,
        api_key: &str,
        temperature: f32,
        max_tokens: u32,
        system_prompt: &str,
        clean_output: bool,
    ) -> Result<String> {
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
            .generate_response_with_model(
                query,
                &enrichment_chunks,
                model_type,
                model_name,
                api_key,
                temperature,
                max_tokens,
                system_prompt,
                clean_output,
            )
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
