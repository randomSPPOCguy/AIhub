/// Navigation system for Project Frank
/// MS-DOS style menu navigation with hubs and commands

use anyhow::Result;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use serde::{Serialize, Deserialize};
use crate::config::{AppConfig, ModelType};

#[derive(Debug, Clone, PartialEq)]
pub enum Hub {
    Main,
    Chat,
    Models,
    Download,
    Settings,
    Logs,
}

pub struct NavigationState {
    pub current_hub: Hub,
    pub config: AppConfig,
    pub logs: Vec<LogEntry>,
    pub chat_history: Vec<Line<'static>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub timestamp: String,
    pub source: String,
    pub level: LogLevel,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum LogLevel {
    Success,
    Warning,
    Error,
    Info,
}

impl LogLevel {
    pub fn color(&self) -> Color {
        match self {
            LogLevel::Success => Color::Green,
            LogLevel::Warning => Color::Yellow,
            LogLevel::Error => Color::Red,
            LogLevel::Info => Color::Cyan,
        }
    }

    pub fn emoji(&self) -> &str {
        match self {
            LogLevel::Success => "✅",
            LogLevel::Warning => "⚠️",
            LogLevel::Error => "❌",
            LogLevel::Info => "ℹ️",
        }
    }
}

impl NavigationState {
    pub fn new() -> Result<Self> {
        let config = AppConfig::load().unwrap_or_default();
        Ok(Self {
            current_hub: Hub::Main,
            config,
            logs: Vec::new(),
            chat_history: Vec::new(),
        })
    }

    pub fn add_log(&mut self, source: String, level: LogLevel, message: String) {
        let timestamp = chrono::Local::now().format("%H:%M:%S").to_string();
        self.logs.push(LogEntry {
            timestamp,
            source,
            level,
            message,
        });
    }

    pub fn navigate_to(&mut self, hub: Hub) {
        self.current_hub = hub;
    }

    pub fn get_header(&self) -> Vec<Line<'static>> {
        vec![
            Line::from(vec![
                Span::styled("╔", Style::default().fg(Color::Cyan)),
                Span::styled("═".repeat(58), Style::default().fg(Color::Cyan)),
                Span::styled("╗", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("║", Style::default().fg(Color::Cyan)),
                Span::styled("            PROJECT FRANK - AI GATEWAY HUB", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
                Span::styled("            ║", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("║", Style::default().fg(Color::Cyan)),
                Span::styled("                Navigation System v2.0", Style::default().fg(Color::Yellow)),
                Span::styled("                   ║", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("╚", Style::default().fg(Color::Cyan)),
                Span::styled("═".repeat(58), Style::default().fg(Color::Cyan)),
                Span::styled("╝", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(""),
        ]
    }

    pub fn get_main_menu(&self) -> Vec<Line<'static>> {
        let mut lines = self.get_header();

        lines.push(Line::from(vec![
            Span::styled("📚 Main Commands:", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        ]));
        lines.push(Line::from(""));

        lines.push(Line::from(vec![
            Span::styled("  /chat", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled("     - Enter the AI Chat interface", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  /models", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled("   - Switch AI models (Local/Cloud)", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  /download", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled(" - Download models from HuggingFace", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  /settings", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled(" - Configure prompts, temperature, and more", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  /logs", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled("     - View detailed event logs", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  /help", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled("     - Show this help menu", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  /exit", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled("     - Exit Project Frank", Style::default().fg(Color::White)),
        ]));

        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("─".repeat(60), Style::default().fg(Color::DarkGray)),
        ]));

        // Show current model
        let model_name = self.config.selected_model
            .as_ref()
            .unwrap_or(&"None".to_string())
            .clone();
        lines.push(Line::from(vec![
            Span::styled("Current Model: ", Style::default().fg(Color::White)),
            Span::styled("🤖 ", Style::default()),
            Span::styled(model_name, Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
        ]));

        lines.push(Line::from(vec![
            Span::styled("Status: ", Style::default().fg(Color::White)),
            Span::styled("✅ Ready", Style::default().fg(Color::Green)),
        ]));

        lines
    }

    pub fn get_models_hub(&self) -> Vec<Line<'static>> {
        let mut lines = vec![
            Line::from(vec![
                Span::styled("╔", Style::default().fg(Color::Cyan)),
                Span::styled("═".repeat(58), Style::default().fg(Color::Cyan)),
                Span::styled("╗", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("║", Style::default().fg(Color::Cyan)),
                Span::styled("                    🤖 MODEL SELECTOR", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
                Span::styled("                      ║", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("╚", Style::default().fg(Color::Cyan)),
                Span::styled("═".repeat(58), Style::default().fg(Color::Cyan)),
                Span::styled("╝", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(""),
        ];

        // Local models
        lines.push(Line::from(vec![
            Span::styled("LOCAL MODELS:", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
        ]));
        lines.push(Line::from(""));

        let mut index = 1;
        for model in &self.config.models {
            if let ModelType::LocalHuggingFace { downloaded, .. } = &model.model_type {
                let status = if *downloaded { "✅ Downloaded" } else { "⬇️  Not Downloaded" };
                let status_color = if *downloaded { Color::Green } else { Color::DarkGray };

                let active = if Some(&model.name) == self.config.selected_model.as_ref() {
                    " [⭐ Active]"
                } else {
                    ""
                };

                lines.push(Line::from(vec![
                    Span::styled(format!("  {}. ", index), Style::default().fg(Color::Cyan)),
                    Span::styled(model.name.clone(), Style::default().fg(Color::White).add_modifier(Modifier::BOLD)),
                    Span::styled(format!(" [{}]", status), Style::default().fg(status_color)),
                    Span::styled(active.to_string(), Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
                ]));
                index += 1;
            }
        }

        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("CLOUD MODELS:", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
        ]));
        lines.push(Line::from(""));

        for model in &self.config.models {
            match &model.model_type {
                ModelType::CloudGemini { api_key, .. } | ModelType::CloudOpenAI { api_key, .. } => {
                    let status = if api_key.is_some() { "🔑 API Key Set" } else { "⚠️  No API Key" };
                    let status_color = if api_key.is_some() { Color::Green } else { Color::Yellow };

                    let active = if Some(&model.name) == self.config.selected_model.as_ref() {
                        " [⭐ Active]"
                    } else {
                        ""
                    };

                    lines.push(Line::from(vec![
                        Span::styled(format!("  {}. ", index), Style::default().fg(Color::Cyan)),
                        Span::styled(model.name.clone(), Style::default().fg(Color::White).add_modifier(Modifier::BOLD)),
                        Span::styled(format!(" [{}]", status), Style::default().fg(status_color)),
                        Span::styled(active.to_string(), Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
                    ]));
                    index += 1;
                }
                _ => {}
            }
        }

        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("─".repeat(60), Style::default().fg(Color::DarkGray)),
        ]));
        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("Commands:", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  select <number>", Style::default().fg(Color::Yellow)),
            Span::styled(" - Switch to model", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  setkey <provider> <key>", Style::default().fg(Color::Yellow)),
            Span::styled(" - Set API key (gemini/openai)", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  back", Style::default().fg(Color::Yellow)),
            Span::styled("            - Return to main menu", Style::default().fg(Color::White)),
        ]));

        lines
    }

    pub fn get_settings_hub(&self) -> Vec<Line<'static>> {
        let mut lines = vec![
            Line::from(vec![
                Span::styled("╔", Style::default().fg(Color::Cyan)),
                Span::styled("═".repeat(58), Style::default().fg(Color::Cyan)),
                Span::styled("╗", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("║", Style::default().fg(Color::Cyan)),
                Span::styled("                    ⚙️  SETTINGS", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
                Span::styled("                            ║", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("╚", Style::default().fg(Color::Cyan)),
                Span::styled("═".repeat(58), Style::default().fg(Color::Cyan)),
                Span::styled("╝", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(""),
        ];

        lines.push(Line::from(vec![
            Span::styled("CURRENT CONFIGURATION:", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
        ]));
        lines.push(Line::from(""));

        lines.push(Line::from(vec![
            Span::styled("  Temperature: ", Style::default().fg(Color::White)),
            Span::styled(format!("{:.2}", self.config.temperature), Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
            Span::styled(" (0.0 = focused, 2.0 = creative)", Style::default().fg(Color::DarkGray)),
        ]));

        lines.push(Line::from(vec![
            Span::styled("  Max Tokens:  ", Style::default().fg(Color::White)),
            Span::styled(format!("{}", self.config.max_tokens), Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        ]));

        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("  System Prompt:", Style::default().fg(Color::White)),
        ]));

        // Wrap system prompt to fit
        let prompt_lines = textwrap::wrap(&self.config.system_prompt, 56);
        for line in prompt_lines {
            lines.push(Line::from(vec![
                Span::styled("    ", Style::default()),
                Span::styled(line.to_string(), Style::default().fg(Color::Cyan)),
            ]));
        }

        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("─".repeat(60), Style::default().fg(Color::DarkGray)),
        ]));
        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("Commands:", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  temp <value>", Style::default().fg(Color::Yellow)),
            Span::styled("      - Set temperature (0.0-2.0)", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  tokens <value>", Style::default().fg(Color::Yellow)),
            Span::styled("    - Set max tokens (1-4096)", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  prompt <text>", Style::default().fg(Color::Yellow)),
            Span::styled("     - Set system prompt", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  save", Style::default().fg(Color::Yellow)),
            Span::styled("              - Save configuration", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  back", Style::default().fg(Color::Yellow)),
            Span::styled("              - Return to main menu", Style::default().fg(Color::White)),
        ]));

        lines
    }

    pub fn get_logs_hub(&self) -> Vec<Line<'static>> {
        let mut lines = vec![
            Line::from(vec![
                Span::styled("╔", Style::default().fg(Color::Cyan)),
                Span::styled("═".repeat(58), Style::default().fg(Color::Cyan)),
                Span::styled("╗", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("║", Style::default().fg(Color::Cyan)),
                Span::styled("                    📜 EVENT LOGS", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
                Span::styled("                           ║", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("╚", Style::default().fg(Color::Cyan)),
                Span::styled("═".repeat(58), Style::default().fg(Color::Cyan)),
                Span::styled("╝", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(""),
        ];

        if self.logs.is_empty() {
            lines.push(Line::from(vec![
                Span::styled("  No logs yet. Start using the system to see events here.", Style::default().fg(Color::DarkGray)),
            ]));
        } else {
            // Show last 20 logs
            let recent_logs: Vec<_> = self.logs.iter().rev().take(20).collect();
            for log in recent_logs {
                lines.push(Line::from(vec![
                    Span::styled(format!("[{}] ", log.timestamp), Style::default().fg(Color::DarkGray)),
                    Span::styled(format!("{} ", log.level.emoji()), Style::default()),
                    Span::styled(format!("[{}] ", log.source), Style::default().fg(Color::Magenta).add_modifier(Modifier::BOLD)),
                    Span::styled(log.message.clone(), Style::default().fg(log.level.color())),
                ]));
            }
        }

        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("─".repeat(60), Style::default().fg(Color::DarkGray)),
        ]));
        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("Commands:", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  clear", Style::default().fg(Color::Yellow)),
            Span::styled(" - Clear all logs", Style::default().fg(Color::White)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  back", Style::default().fg(Color::Yellow)),
            Span::styled("  - Return to main menu", Style::default().fg(Color::White)),
        ]));

        lines
    }

    pub fn get_current_view(&self) -> Vec<Line<'static>> {
        match self.current_hub {
            Hub::Main => self.get_main_menu(),
            Hub::Models => self.get_models_hub(),
            Hub::Settings => self.get_settings_hub(),
            Hub::Logs => self.get_logs_hub(),
            Hub::Chat => {
                let mut lines = self.get_header();
                lines.push(Line::from(vec![
                    Span::styled("💬 Chat Mode", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
                    Span::styled(" - Type 'back' to return to main menu", Style::default().fg(Color::DarkGray)),
                ]));
                lines.push(Line::from(""));
                lines.extend(self.chat_history.clone());
                lines
            }
            Hub::Download => {
                let mut lines = self.get_header();
                lines.push(Line::from(vec![
                    Span::styled("⬇️  Download Hub - Coming Soon!", Style::default().fg(Color::Yellow)),
                ]));
                lines.push(Line::from(""));
                lines.push(Line::from(vec![
                    Span::styled("Type 'back' to return to main menu", Style::default().fg(Color::DarkGray)),
                ]));
                lines
            }
        }
    }
}
