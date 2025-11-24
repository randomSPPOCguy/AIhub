/// Web server for Project Frank
/// Provides HTTP and WebSocket interface for the AI hub

use anyhow::Result as AnyResult;
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    response::{Html, Response},
    routing::{get, post},
    Json, Router,
};
use futures_util::{SinkExt, StreamExt};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use tokio::sync::RwLock;

use crate::config::{AppConfig, ModelType};
use crate::coordinator::AppCoordinator;
use crate::navigation::{LogEntry, LogLevel, NavigationState};
use crate::session::SessionManager;
use crate::tui::QueryEngine;

#[derive(Clone)]
pub struct AppState {
    pub nav_state: Arc<RwLock<NavigationState>>,
    pub coordinator: Arc<Mutex<AppCoordinator>>,
    pub sessions: Arc<SessionManager>,
}

#[derive(Debug, Serialize, Deserialize)]
struct CommandResponse {
    success: bool,
    message: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct StateResponse {
    current_hub: String,
    config: AppConfig,
    logs: Vec<LogEntry>,
}

#[derive(Debug, Serialize)]
struct GeminiCatalogResponse {
    success: bool,
    message: String,
    models: Vec<GeminiModelInfo>,
}

#[derive(Debug, Serialize)]
struct GeminiModelInfo {
    id: String,
    display_name: String,
    description: Option<String>,
    input_tokens: Option<u32>,
    output_tokens: Option<u32>,
    generation_methods: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct GeminiApiList {
    models: Option<Vec<GeminiApiModel>>,
}

#[derive(Debug, Deserialize)]
struct GeminiApiModel {
    name: String,
    #[serde(rename = "displayName")]
    display_name: Option<String>,
    description: Option<String>,
    #[serde(rename = "inputTokenLimit")]
    input_token_limit: Option<u32>,
    #[serde(rename = "outputTokenLimit")]
    output_token_limit: Option<u32>,
    #[serde(rename = "supportedGenerationMethods")]
    supported_generation_methods: Option<Vec<String>>,
}

pub async fn run_server() -> anyhow::Result<()> {
    let nav_state = NavigationState::new()?;
    let coordinator = AppCoordinator::new()?;

    // Create session manager with configurable timeout (default 600s)
    let timeout_secs: i64 = std::env::var("AIHUB_SESSION_TIMEOUT_SECS")
        .ok()
        .and_then(|s| s.parse::<i64>().ok())
        .filter(|v| *v > 0 && *v <= 86400)
        .unwrap_or(600);
    let sessions = Arc::new(SessionManager::new(timeout_secs));

    // Start background cleanup task
    sessions.clone().start_cleanup_task();

    let state = AppState {
        nav_state: Arc::new(RwLock::new(nav_state)),
        coordinator: Arc::new(Mutex::new(coordinator)),
        sessions,
    };

    // Add welcome log
    {
        let mut nav = state.nav_state.write().await;
        nav.add_log(
            "WebServer".to_string(),
            LogLevel::Success,
            "Project Frank web server started with session management".to_string(),
        );
    }

    let app = Router::new()
        .route("/", get(index_handler))
        .route("/api/state", get(get_state))
        .route("/api/chat", post(chat_endpoint))
        .route("/api/models", get(get_models))
        .route("/api/models/select", post(select_model))
        .route("/api/models/gemini/catalog", get(get_gemini_catalog))
        .route("/api/models/gemini/select", post(select_gemini_model))
        .route("/api/settings", get(get_settings))
        .route("/api/settings", post(update_settings))
        .route("/api/logs", get(get_logs))
        .route("/ws", get(websocket_handler))
        .with_state(state);

    let addr = "127.0.0.1:3000";
    let listener = tokio::net::TcpListener::bind(addr).await?;

    println!("Project Frank Web UI running at http://{}", addr);
    println!("Open your browser and navigate to the URL above.");
    println!("Press Ctrl+C to stop the server.");

    axum::serve(listener, app).await?;
    Ok(())
}

async fn index_handler() -> Html<String> {
    let html = std::fs::read_to_string("static/index.html")
        .unwrap_or_else(|e| format!("<h1>Error loading page</h1><p>Error: {}</p><p>Current dir: {:?}</p>", e, std::env::current_dir()));
    Html(html)
}

async fn get_state(State(state): State<AppState>) -> Json<StateResponse> {
    let nav = state.nav_state.read().await;
    Json(StateResponse {
        current_hub: format!("{:?}", nav.current_hub),
        config: nav.config.clone(),
        logs: nav.logs.clone(),
    })
}

async fn get_models(State(state): State<AppState>) -> Json<Vec<crate::config::ModelConfig>> {
    let nav = state.nav_state.read().await;
    Json(nav.config.models.clone())
}

async fn get_settings(State(state): State<AppState>) -> Json<AppConfig> {
    let nav = state.nav_state.read().await;
    Json(nav.config.clone())
}

#[derive(Debug, Deserialize)]
struct UpdateSettingsRequest {
    temperature: Option<f32>,
    max_tokens: Option<u32>,
    system_prompt: Option<String>,
}

#[derive(Debug, Deserialize)]
struct SelectModelRequest {
    model_name: String,
}

#[derive(Debug, Deserialize)]
struct GeminiSelectionRequest {
    model_id: String,
    display_name: String,
}

async fn update_settings(
    State(state): State<AppState>,
    Json(req): Json<UpdateSettingsRequest>,
) -> Json<CommandResponse> {
    let mut nav = state.nav_state.write().await;

    if let Some(temp) = req.temperature {
        nav.config.set_temperature(temp);
    }
    if let Some(tokens) = req.max_tokens {
        nav.config.set_max_tokens(tokens);
    }
    if let Some(prompt) = req.system_prompt {
        nav.config.set_system_prompt(prompt);
    }

    if let Err(e) = nav.config.save() {
        return Json(CommandResponse {
            success: false,
            message: format!("Failed to save: {}", e),
        });
    }

    nav.add_log(
        "WebUI".to_string(),
        LogLevel::Success,
        "Settings updated".to_string(),
    );

    Json(CommandResponse {
        success: true,
        message: "Settings updated successfully".to_string(),
    })
}

async fn select_model(
    State(state): State<AppState>,
    Json(req): Json<SelectModelRequest>,
) -> Json<CommandResponse> {
    let mut nav = state.nav_state.write().await;

    nav.config.set_selected_model(req.model_name.clone());

    if let Err(e) = nav.config.save() {
        return Json(CommandResponse {
            success: false,
            message: format!("Failed to save: {}", e),
        });
    }

    nav.add_log(
        "Models".to_string(),
        LogLevel::Success,
        format!("Switched to model: {}", req.model_name),
    );

    Json(CommandResponse {
        success: true,
        message: format!("Model switched to {}", req.model_name),
    })
}

async fn get_logs(State(state): State<AppState>) -> Json<Vec<LogEntry>> {
    let nav = state.nav_state.read().await;
    Json(nav.logs.clone())
}

async fn get_gemini_catalog(State(state): State<AppState>) -> Json<GeminiCatalogResponse> {
    let api_key = {
        let nav = state.nav_state.read().await;
        nav.config.gemini_api_key.clone()
    };

    let Some(key) = api_key else {
        return Json(GeminiCatalogResponse {
            success: false,
            message: "Set GEMINI_API_KEY in config.env to load Google models.".to_string(),
            models: Vec::new(),
        });
    };

    match fetch_gemini_models(&key).await {
        Ok(models) => Json(GeminiCatalogResponse {
            success: true,
            message: format!("Loaded {} Google Gemini models.", models.len()),
            models,
        }),
        Err(e) => Json(GeminiCatalogResponse {
            success: false,
            message: format!("Failed to load Google models: {}", e),
            models: Vec::new(),
        }),
    }
}

async fn select_gemini_model(
    State(state): State<AppState>,
    Json(req): Json<GeminiSelectionRequest>,
) -> Json<CommandResponse> {
    if req.model_id.trim().is_empty() {
        return Json(CommandResponse {
            success: false,
            message: "Model ID is required.".to_string(),
        });
    }

    let mut nav = state.nav_state.write().await;
    nav.config
        .set_gemini_selection(req.model_id.trim().to_string(), req.display_name.trim().to_string());

    if let Err(e) = nav.config.save() {
        return Json(CommandResponse {
            success: false,
            message: format!("Failed to save selection: {}", e),
        });
    }

    nav.add_log(
        "Models".to_string(),
        LogLevel::Success,
        format!(
            "Selected Google Gemini model: {}",
            req.display_name.trim()
        ),
    );

    Json(CommandResponse {
        success: true,
        message: format!("Gemini model set to {}", req.display_name.trim()),
    })
}

#[derive(Debug, Deserialize)]
struct ChatRequest {
    message: String,
    session_id: Option<String>,
}

#[derive(Debug, Serialize)]
struct ChatResponse {
    success: bool,
    response: String,
    session_id: String,
}

async fn chat_endpoint(
    State(state): State<AppState>,
    Json(req): Json<ChatRequest>,
) -> Json<ChatResponse> {
    if req.message.trim().is_empty() {
        // Get or create session for error response
        let session = state.sessions.get_or_create_session(req.session_id.clone()).await;
        return Json(ChatResponse {
            success: false,
            response: "Message cannot be empty".to_string(),
            session_id: session.id,
        });
    }

    // Get or create session
    let session = state.sessions.get_or_create_session(req.session_id.clone()).await;
    let session_id = session.id.clone();

    // Store user message
    state.sessions.add_message(&session_id, "user".to_string(), req.message.clone()).await;

    {
        let mut nav = state.nav_state.write().await;
        nav.add_log(
            "WebUI".to_string(),
            LogLevel::Info,
            format!("Chat message [session:{}]: {}", &session_id[..8], req.message),
        );
    }

    // Snapshot configuration so we can drop locks before heavy work
    let (
        selected_model,
        temperature,
        max_tokens,
        system_prompt,
        gemini_key,
        gemini_override,
        gemini_label,
    ) = {
        let nav = state.nav_state.read().await;
        (
            nav.config.get_selected_model().cloned(),
            nav.config.temperature,
            nav.config.max_tokens,
            nav.config.system_prompt.clone(),
            nav.config.gemini_api_key.clone(),
            nav.config.gemini_active_model.clone(),
            nav.config.gemini_active_label.clone(),
        )
    };

    let Some(model) = selected_model else {
        return Json(ChatResponse {
            success: false,
            response: "No model selected. Please go to Models tab and select one.".to_string(),
            session_id,
        });
    };

    {
        let mut nav = state.nav_state.write().await;
        let display_model = match (&model.model_type, gemini_label.as_ref()) {
            (ModelType::CloudGemini { .. }, Some(label)) => {
                format!("{} ({})", model.name, label)
            }
            _ => model.name.clone(),
        };

        nav.add_log(
            "AIHub".to_string(),
            LogLevel::Info,
            format!("Generating response with {}", display_model),
        );
    }

    let result = match &model.model_type {
        ModelType::LocalHuggingFace { .. } => {
            let mut coordinator = match state.coordinator.lock() {
                Ok(guard) => guard,
                Err(_) => {
                    return Json(ChatResponse {
                        success: false,
                        response: "Coordinator unavailable. Restart the server and try again.".to_string(),
                        session_id,
                    })
                }
            };
            coordinator
                .handle_query_clean(&req.message, true)
                .map_err(|e| format!("Generation error: {}", e))
        }
        ModelType::CloudGemini { api_key, model_name } => {
            let key = api_key
                .clone()
                .or_else(|| gemini_key.clone())
                .unwrap_or_default();
            if key.is_empty() {
                Err("Gemini API key missing. Update config.env or Models tab.".to_string())
            } else {
                let target_model = gemini_override
                    .clone()
                    .unwrap_or_else(|| model_name.clone());
                let mut coordinator = match state.coordinator.lock() {
                    Ok(guard) => guard,
                    Err(_) => {
                        return Json(ChatResponse {
                            success: false,
                            response: "Coordinator unavailable. Restart the server and try again.".to_string(),
                            session_id,
                        })
                    }
                };
                coordinator
                    .handle_query_with_model(
                        &req.message,
                        "gemini",
                        &target_model,
                        &key,
                        temperature,
                        max_tokens,
                        &system_prompt,
                        true, // clean_output for web UI
                    )
                    .map_err(|e| format!("Gemini error: {}", e))
            }
        }
        ModelType::CloudOpenAI { .. } => Err("OpenAI support not implemented yet.".to_string()),
        _ => Err("Unsupported model type.".to_string()),
    };

    match result {
        Ok(response) => {
            // Store assistant response in session
            state.sessions.add_message(&session_id, "assistant".to_string(), response.clone()).await;

            {
                let mut nav = state.nav_state.write().await;
                nav.add_log(
                    "AIHub".to_string(),
                    LogLevel::Success,
                    format!("Response generated [session:{}]", &session_id[..8]),
                );
            }

            Json(ChatResponse {
                success: true,
                response,
                session_id,
            })
        }
        Err(error) => {
            {
                let mut nav = state.nav_state.write().await;
                nav.add_log(
                    "AIHub".to_string(),
                    LogLevel::Error,
                    error.clone(),
                );
            }

            Json(ChatResponse {
                success: false,
                response: error,
                session_id,
            })
        }
    }
}

async fn websocket_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> Response {
    ws.on_upgrade(|socket| websocket_connection(socket, state))
}

async fn websocket_connection(socket: WebSocket, _state: AppState) {
    // TODO: Implement WebSocket chat functionality
    let (mut sender, mut receiver) = socket.split();

    while let Some(msg) = receiver.next().await {
        if let Ok(msg) = msg {
            if let Message::Text(text) = msg {
                // Echo back for now
                let response = Message::Text(format!("Echo: {}", text));
                if sender.send(response).await.is_err() {
                    break;
                }
            }
        }
    }
}

async fn fetch_gemini_models(api_key: &str) -> AnyResult<Vec<GeminiModelInfo>> {
    let client = Client::new();
    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models?key={}&pageSize=200",
        api_key
    );

    let response = client.get(url).send().await?.error_for_status()?;
    let payload: GeminiApiList = response.json().await?;

    let mut models = Vec::new();
    if let Some(items) = payload.models {
        for model in items {
            let methods = model.supported_generation_methods.clone().unwrap_or_default();
            if !methods
                .iter()
                .any(|m| m.eq_ignore_ascii_case("generateContent"))
            {
                continue;
            }

            let id = normalize_model_name(&model.name);
            models.push(GeminiModelInfo {
                id,
                display_name: model
                    .display_name
                    .clone()
                    .unwrap_or_else(|| model.name.clone()),
                description: model.description.clone(),
                input_tokens: model.input_token_limit,
                output_tokens: model.output_token_limit,
                generation_methods: methods,
            });
        }
    }

    models.sort_by(|a, b| a.display_name.cmp(&b.display_name));
    Ok(models)
}

fn normalize_model_name(source: &str) -> String {
    source
        .strip_prefix("models/")
        .unwrap_or(source)
        .to_string()
}
