/// Configuration management for Project Frank
/// Handles model selection, API keys, and user preferences

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelConfig {
    pub name: String,
    pub model_type: ModelType,
    pub enabled: bool,
    pub last_used: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ModelType {
    LocalHuggingFace {
        model_id: String,
        downloaded: bool,
    },
    CloudOpenAI {
        api_key: Option<String>,
        model_name: String,
    },
    CloudGemini {
        api_key: Option<String>,
        model_name: String,
    },
    CloudHuggingFace {
        api_key: String,
        model_id: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub selected_model: Option<String>,
    pub models: Vec<ModelConfig>,
    pub openai_api_key: Option<String>,
    pub gemini_api_key: Option<String>,
    pub hf_api_key: Option<String>,
    pub temperature: f32,
    pub max_tokens: u32,
    pub system_prompt: String,
    pub gemini_active_model: Option<String>,
    pub gemini_active_label: Option<String>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            selected_model: Some("Phi-3 Mini (Local)".to_string()),
            models: vec![
                // Local models (no API key needed)
                ModelConfig {
                    name: "Phi-3 Mini (Local)".to_string(),
                    model_type: ModelType::LocalHuggingFace {
                        model_id: "microsoft/Phi-3-mini-4k-instruct".to_string(),
                        downloaded: false,
                    },
                    enabled: true,
                    last_used: None,
                },
                ModelConfig {
                    name: "Llama 3.2 1B (Local)".to_string(),
                    model_type: ModelType::LocalHuggingFace {
                        model_id: "meta-llama/Llama-3.2-1B-Instruct".to_string(),
                        downloaded: false,
                    },
                    enabled: true,
                    last_used: None,
                },
                ModelConfig {
                    name: "TinyLlama (Local)".to_string(),
                    model_type: ModelType::LocalHuggingFace {
                        model_id: "TinyLlama/TinyLlama-1.1B-Chat-v1.0".to_string(),
                        downloaded: false,
                    },
                    enabled: true,
                    last_used: None,
                },
                // Cloud models (require API keys)
                ModelConfig {
                    name: "GPT-4 Turbo (OpenAI)".to_string(),
                    model_type: ModelType::CloudOpenAI {
                        api_key: std::env::var("OPENAI_API_KEY").ok(),
                        model_name: "gpt-4-turbo-preview".to_string(),
                    },
                    enabled: std::env::var("OPENAI_API_KEY").is_ok(),
                    last_used: None,
                },
                ModelConfig {
                    name: "GPT-3.5 Turbo (OpenAI)".to_string(),
                    model_type: ModelType::CloudOpenAI {
                        api_key: std::env::var("OPENAI_API_KEY").ok(),
                        model_name: "gpt-3.5-turbo".to_string(),
                    },
                    enabled: std::env::var("OPENAI_API_KEY").is_ok(),
                    last_used: None,
                },
                ModelConfig {
                    name: "Gemini 2.0 Flash (Google)".to_string(),
                    model_type: ModelType::CloudGemini {
                        api_key: std::env::var("GEMINI_API_KEY").ok(),
                        model_name: "gemini-2.0-flash-exp".to_string(),
                    },
                    enabled: std::env::var("GEMINI_API_KEY").is_ok(),
                    last_used: None,
                },
                ModelConfig {
                    name: "Gemini 1.5 Pro (Google)".to_string(),
                    model_type: ModelType::CloudGemini {
                        api_key: std::env::var("GEMINI_API_KEY").ok(),
                        model_name: "gemini-1.5-pro-latest".to_string(),
                    },
                    enabled: std::env::var("GEMINI_API_KEY").is_ok(),
                    last_used: None,
                },
                ModelConfig {
                    name: "Gemini 1.5 Flash (Google)".to_string(),
                    model_type: ModelType::CloudGemini {
                        api_key: std::env::var("GEMINI_API_KEY").ok(),
                        model_name: "gemini-1.5-flash-latest".to_string(),
                    },
                    enabled: std::env::var("GEMINI_API_KEY").is_ok(),
                    last_used: None,
                },
                ModelConfig {
                    name: "Gemini Pro (Google)".to_string(),
                    model_type: ModelType::CloudGemini {
                        api_key: std::env::var("GEMINI_API_KEY").ok(),
                        model_name: "gemini-1.0-pro".to_string(),
                    },
                    enabled: std::env::var("GEMINI_API_KEY").is_ok(),
                    last_used: None,
                },
            ],
            openai_api_key: std::env::var("OPENAI_API_KEY").ok(),
            gemini_api_key: std::env::var("GEMINI_API_KEY").ok(),
            hf_api_key: std::env::var("HUGGINGFACE_API_KEY").ok(),
            temperature: 0.7,
            max_tokens: 1024,
            system_prompt: "You are a friendly and knowledgeable AI assistant. Have natural conversations with users about any topic. Be helpful, engaging, and provide complete responses.".to_string(),
            gemini_active_model: None,
            gemini_active_label: None,
        }
    }
}

impl AppConfig {
    pub fn load() -> Result<Self> {
        let config_path = Self::config_path();

        let mut config = if config_path.exists() {
            let contents = fs::read_to_string(&config_path)?;
            serde_json::from_str(&contents)?
        } else {
            Self::default()
        };

        // Always merge environment variables on load
        config.merge_env_vars();

        if config.selected_model.is_none() {
            if let Some(local) = config
                .models
                .iter()
                .find(|m| matches!(m.model_type, ModelType::LocalHuggingFace { .. }))
            {
                config.selected_model = Some(local.name.clone());
            }
        }

        Ok(config)
    }

    /// Merge API keys from environment variables
    fn merge_env_vars(&mut self) {
        // Update API keys from environment
        if let Ok(key) = std::env::var("GEMINI_API_KEY") {
            self.gemini_api_key = Some(key.clone());
            // Update all Gemini models
            for model in &mut self.models {
                if let ModelType::CloudGemini { api_key, .. } = &mut model.model_type {
                    *api_key = Some(key.clone());
                    model.enabled = true;
                }
            }
        }

        if let Ok(key) = std::env::var("OPENAI_API_KEY") {
            self.openai_api_key = Some(key.clone());
            // Update all OpenAI models
            for model in &mut self.models {
                if let ModelType::CloudOpenAI { api_key, .. } = &mut model.model_type {
                    *api_key = Some(key.clone());
                    model.enabled = true;
                }
            }
        }

        if let Ok(key) = std::env::var("HUGGINGFACE_API_KEY") {
            self.hf_api_key = Some(key);
        }
    }

    pub fn save(&self) -> Result<()> {
        let config_path = Self::config_path();

        if let Some(parent) = config_path.parent() {
            fs::create_dir_all(parent)?;
        }

        let contents = serde_json::to_string_pretty(self)?;
        fs::write(config_path, contents)?;
        Ok(())
    }

    fn config_path() -> PathBuf {
        let mut path = dirs::config_dir().unwrap_or_else(|| PathBuf::from("."));
        path.push("project-frank");
        path.push("config.json");
        path
    }

    pub fn set_selected_model(&mut self, model_name: String) {
        self.selected_model = Some(model_name.clone());

        // Update last_used timestamp
        if let Some(model) = self.models.iter_mut().find(|m| m.name == model_name) {
            model.last_used = Some(chrono::Utc::now().to_rfc3339());
        }
    }

    pub fn set_gemini_selection(&mut self, model_id: String, label: String) {
        self.gemini_active_model = Some(model_id.clone());
        self.gemini_active_label = Some(label.clone());

        for model in &mut self.models {
            if let ModelType::CloudGemini { model_name, .. } = &mut model.model_type {
                *model_name = model_id.clone();
            }
        }
    }

    pub fn active_gemini_model(&self, fallback: &str) -> String {
        self.gemini_active_model
            .clone()
            .unwrap_or_else(|| fallback.to_string())
    }

    pub fn get_selected_model(&self) -> Option<&ModelConfig> {
        if let Some(ref name) = self.selected_model {
            self.models.iter().find(|m| &m.name == name)
        } else {
            None
        }
    }

    pub fn get_available_models(&self) -> Vec<&ModelConfig> {
        self.models.iter().filter(|m| m.enabled).collect()
    }

    pub fn set_api_key(&mut self, provider: &str, key: String) {
        match provider {
            "openai" => {
                self.openai_api_key = Some(key.clone());
                // Update all OpenAI models
                for model in &mut self.models {
                    if let ModelType::CloudOpenAI { api_key, .. } = &mut model.model_type {
                        *api_key = Some(key.clone());
                        model.enabled = true;
                    }
                }
            }
            "gemini" => {
                self.gemini_api_key = Some(key.clone());
                // Update all Gemini models
                for model in &mut self.models {
                    if let ModelType::CloudGemini { api_key, .. } = &mut model.model_type {
                        *api_key = Some(key.clone());
                        model.enabled = true;
                    }
                }
            }
            "huggingface" => {
                self.hf_api_key = Some(key);
            }
            _ => {}
        }
    }

    pub fn mark_model_downloaded(&mut self, model_name: &str) {
        if let Some(model) = self.models.iter_mut().find(|m| m.name == model_name) {
            if let ModelType::LocalHuggingFace { downloaded, .. } = &mut model.model_type {
                *downloaded = true;
            }
        }
    }

    pub fn set_temperature(&mut self, temp: f32) {
        self.temperature = temp.clamp(0.0, 2.0);
    }

    pub fn set_max_tokens(&mut self, tokens: u32) {
        self.max_tokens = tokens.min(4096);
    }

    pub fn set_system_prompt(&mut self, prompt: String) {
        self.system_prompt = prompt;
    }
}
