use anyhow::Result;
use crossterm::event::{self, Event, KeyCode, KeyEventKind, KeyModifiers};
use crossterm::terminal::{disable_raw_mode, enable_raw_mode, Clear, ClearType};
use crossterm::ExecutableCommand;
use ratatui::backend::CrosstermBackend;
use ratatui::layout::{Constraint, Direction, Layout};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::Line;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Terminal;
use std::io::{self, Stderr};
use std::time::Duration;

use crate::navigation::{Hub, LogLevel, NavigationState};

pub trait QueryEngine {
    fn handle_query(&mut self, query: &str) -> Result<String>;
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
    ) -> Result<String>;
}

struct TextEditor {
    content: String,
    cursor_pos: usize,
    selection_start: Option<usize>,
}

impl TextEditor {
    fn new() -> Self {
        Self {
            content: String::new(),
            cursor_pos: 0,
            selection_start: None,
        }
    }

    fn insert_char(&mut self, ch: char) {
        // Delete selection if exists
        if self.selection_start.is_some() {
            self.delete_selection();
        }

        // Ensure cursor is at a valid char boundary
        let safe_pos = self.safe_char_boundary(self.cursor_pos);
        self.content.insert(safe_pos, ch);
        self.cursor_pos = safe_pos + ch.len_utf8();
    }

    fn backspace(&mut self) {
        // If there's a selection, delete it
        if self.selection_start.is_some() {
            self.delete_selection();
        } else if self.cursor_pos > 0 {
            // Move to previous char boundary
            let mut new_pos = self.cursor_pos.saturating_sub(1);
            while new_pos > 0 && !self.content.is_char_boundary(new_pos) {
                new_pos -= 1;
            }
            self.content.drain(new_pos..self.cursor_pos);
            self.cursor_pos = new_pos;
        }
    }

    fn delete_selection(&mut self) {
        if let Some(start) = self.selection_start {
            let (begin, end) = if start < self.cursor_pos {
                (start, self.cursor_pos)
            } else {
                (self.cursor_pos, start)
            };

            // Ensure boundaries are valid
            let safe_begin = self.safe_char_boundary(begin);
            let safe_end = self.safe_char_boundary(end);

            self.content.drain(safe_begin..safe_end);
            self.cursor_pos = safe_begin;
            self.selection_start = None;
        }
    }

    fn safe_char_boundary(&self, pos: usize) -> usize {
        let clamped = pos.min(self.content.len());
        if self.content.is_char_boundary(clamped) {
            clamped
        } else {
            // Find the nearest char boundary to the left
            (0..=clamped).rev().find(|&i| self.content.is_char_boundary(i)).unwrap_or(0)
        }
    }

    fn move_cursor_left(&mut self, select: bool) {
        if select {
            if self.selection_start.is_none() {
                self.selection_start = Some(self.cursor_pos);
            }
        } else {
            self.selection_start = None;
        }

        if self.cursor_pos > 0 {
            // Move to previous char boundary
            let mut new_pos = self.cursor_pos - 1;
            while new_pos > 0 && !self.content.is_char_boundary(new_pos) {
                new_pos -= 1;
            }
            self.cursor_pos = new_pos;
        }
    }

    fn move_cursor_right(&mut self, select: bool) {
        if select {
            if self.selection_start.is_none() {
                self.selection_start = Some(self.cursor_pos);
            }
        } else {
            self.selection_start = None;
        }

        if self.cursor_pos < self.content.len() {
            // Move to next char boundary
            let mut new_pos = self.cursor_pos + 1;
            while new_pos < self.content.len() && !self.content.is_char_boundary(new_pos) {
                new_pos += 1;
            }
            self.cursor_pos = new_pos.min(self.content.len());
        }
    }

    fn move_to_start(&mut self, select: bool) {
        if select {
            if self.selection_start.is_none() {
                self.selection_start = Some(self.cursor_pos);
            }
        } else {
            self.selection_start = None;
        }
        self.cursor_pos = 0;
    }

    fn move_to_end(&mut self, select: bool) {
        if select {
            if self.selection_start.is_none() {
                self.selection_start = Some(self.cursor_pos);
            }
        } else {
            self.selection_start = None;
        }
        self.cursor_pos = self.content.len();
    }

    fn set_content(&mut self, content: String) {
        self.content = content;
        self.cursor_pos = self.content.len();
        self.selection_start = None;
    }

    fn clear(&mut self) {
        self.content.clear();
        self.cursor_pos = 0;
        self.selection_start = None;
    }

    fn select_all(&mut self) {
        self.selection_start = Some(0);
        self.cursor_pos = self.content.len();
    }
}

pub fn run(engine: &mut impl QueryEngine) -> Result<()> {
    let mut nav_state = NavigationState::new()?;
    let mut editor = TextEditor::new();
    let mut command_history: Vec<String> = Vec::new();
    let mut history_index: Option<usize> = None;

    // Clear screen before starting TUI
    io::stderr().execute(Clear(ClearType::All))?;

    enable_raw_mode()?;
    let mut terminal = init_terminal()?;
    terminal.clear()?;

    // Add welcome log
    nav_state.add_log(
        "System".to_string(),
        LogLevel::Success,
        "Project Frank initialized successfully".to_string(),
    );

    let result = loop {
        terminal.draw(|frame| draw(frame, &nav_state, &editor.content))?;

        if event::poll(Duration::from_millis(250))? {
            match event::read()? {
                Event::Key(key_event) => {
                    if key_event.kind != KeyEventKind::Press {
                        continue;
                    }

                    let shift = key_event.modifiers.contains(KeyModifiers::SHIFT);
                    let ctrl = key_event.modifiers.contains(KeyModifiers::CONTROL);

                    // Check for Ctrl+C
                    if key_event.code == KeyCode::Char('c') && ctrl {
                        break Ok(());
                    }

                    // Check for Ctrl+A (select all)
                    if key_event.code == KeyCode::Char('a') && ctrl {
                        editor.select_all();
                        continue;
                    }

                    // Process key input
                    match key_event.code {
                        KeyCode::Char(ch) => {
                            editor.insert_char(ch);
                            history_index = None;
                        }
                        KeyCode::Backspace => {
                            editor.backspace();
                            history_index = None;
                        }
                        KeyCode::Delete => {
                            if editor.selection_start.is_some() {
                                editor.delete_selection();
                            } else if editor.cursor_pos < editor.content.len() {
                                // Find next char boundary
                                let start = editor.cursor_pos;
                                let mut end = start + 1;
                                while end < editor.content.len() && !editor.content.is_char_boundary(end) {
                                    end += 1;
                                }
                                editor.content.drain(start..end);
                            }
                            history_index = None;
                        }
                        KeyCode::Left => {
                            if ctrl {
                                // Move to start
                                editor.move_to_start(shift);
                            } else {
                                editor.move_cursor_left(shift);
                            }
                            history_index = None;
                        }
                        KeyCode::Right => {
                            if ctrl {
                                // Move to end
                                editor.move_to_end(shift);
                            } else {
                                editor.move_cursor_right(shift);
                            }
                            history_index = None;
                        }
                        KeyCode::Home => {
                            editor.move_to_start(shift);
                            history_index = None;
                        }
                        KeyCode::End => {
                            editor.move_to_end(shift);
                            history_index = None;
                        }
                        KeyCode::Up => {
                            // Navigate command history backwards
                            if !command_history.is_empty() {
                                if let Some(idx) = history_index {
                                    if idx > 0 {
                                        history_index = Some(idx - 1);
                                        editor.set_content(command_history[idx - 1].clone());
                                    }
                                } else {
                                    history_index = Some(command_history.len() - 1);
                                    editor.set_content(command_history[command_history.len() - 1].clone());
                                }
                            }
                        }
                        KeyCode::Down => {
                            // Navigate command history forwards
                            if let Some(idx) = history_index {
                                if idx < command_history.len() - 1 {
                                    history_index = Some(idx + 1);
                                    editor.set_content(command_history[idx + 1].clone());
                                } else {
                                    history_index = None;
                                    editor.clear();
                                }
                            }
                        }
                        KeyCode::Enter => {
                            let command = editor.content.trim().to_owned();
                            if !command.is_empty() {
                                // Add to history
                                command_history.push(command.clone());
                                history_index = None;

                                handle_command(&mut nav_state, engine, &command)?;
                            }
                            editor.clear();
                        }
                        KeyCode::Esc => break Ok(()),
                        _ => {}
                    }
                }
                Event::Resize(_, _) => {}
                _ => {}
            }
        }
    };

    shutdown_terminal(terminal)?;
    result
}

fn handle_command(
    nav_state: &mut NavigationState,
    engine: &mut impl QueryEngine,
    command: &str,
) -> Result<()> {
    // Global commands
    if command == "/exit" {
        std::process::exit(0);
    }

    if command == "/help" {
        nav_state.navigate_to(Hub::Main);
        nav_state.add_log(
            "Navigation".to_string(),
            LogLevel::Info,
            "Returned to main menu".to_string(),
        );
        return Ok(());
    }

    if command == "back" {
        nav_state.navigate_to(Hub::Main);
        nav_state.add_log(
            "Navigation".to_string(),
            LogLevel::Info,
            "Returned to main menu".to_string(),
        );
        return Ok(());
    }

    // Hub navigation
    match command {
        "/chat" => {
            nav_state.navigate_to(Hub::Chat);
            nav_state.add_log(
                "Navigation".to_string(),
                LogLevel::Info,
                "Entered chat hub".to_string(),
            );
        }
        "/models" => {
            nav_state.navigate_to(Hub::Models);
            nav_state.add_log(
                "Navigation".to_string(),
                LogLevel::Info,
                "Entered models hub".to_string(),
            );
        }
        "/download" => {
            nav_state.navigate_to(Hub::Download);
            nav_state.add_log(
                "Navigation".to_string(),
                LogLevel::Info,
                "Entered download hub".to_string(),
            );
        }
        "/settings" => {
            nav_state.navigate_to(Hub::Settings);
            nav_state.add_log(
                "Navigation".to_string(),
                LogLevel::Info,
                "Entered settings hub".to_string(),
            );
        }
        "/logs" => {
            nav_state.navigate_to(Hub::Logs);
            nav_state.add_log(
                "Navigation".to_string(),
                LogLevel::Info,
                "Viewing event logs".to_string(),
            );
        }
        _ => {
            // Hub-specific commands
            match nav_state.current_hub {
                Hub::Chat => handle_chat_command(nav_state, engine, command)?,
                Hub::Models => handle_models_command(nav_state, command)?,
                Hub::Settings => handle_settings_command(nav_state, command)?,
                Hub::Logs => handle_logs_command(nav_state, command)?,
                _ => {
                    nav_state.add_log(
                        "Command".to_string(),
                        LogLevel::Warning,
                        format!("Unknown command: {}", command),
                    );
                }
            }
        }
    }

    Ok(())
}

fn handle_chat_command(
    nav_state: &mut NavigationState,
    engine: &mut impl QueryEngine,
    command: &str,
) -> Result<()> {
    // Add user query to chat history
    nav_state.chat_history.push(Line::styled(
        format!("> {}", command),
        Style::default().fg(Color::Yellow),
    ));

    nav_state.add_log(
        "Chat".to_string(),
        LogLevel::Info,
        format!("User query: {}", command),
    );

    // Clone the necessary data from config to avoid borrow issues
    let model_config = nav_state.config.get_selected_model().cloned();
    let temperature = nav_state.config.temperature;
    let max_tokens = nav_state.config.max_tokens;
    let system_prompt = nav_state.config.system_prompt.clone();

    let response = if let Some(model) = model_config {
        nav_state.add_log(
            "AIHub".to_string(),
            LogLevel::Info,
            format!("Generating response with {}", model.name),
        );

        match &model.model_type {
            crate::config::ModelType::LocalHuggingFace { .. } => {
                // Use existing handle_query for local models
                engine.handle_query(command).unwrap_or_else(|e| {
                    nav_state.add_log(
                        "AIHub".to_string(),
                        LogLevel::Error,
                        format!("Error: {}", e),
                    );
                    format!("Error: {}", e)
                })
            }
            crate::config::ModelType::CloudGemini { api_key, model_name } => {
                let key = api_key.clone().unwrap_or_default();
                let model_id = model_name.clone();
                engine
                    .handle_query_with_model(
                        command,
                        "gemini",
                        &model_id,
                        &key,
                        temperature,
                        max_tokens,
                        &system_prompt,
                        false, // keep formatted output for TUI
                    )
                    .unwrap_or_else(|e| {
                        nav_state.add_log(
                            "Gemini".to_string(),
                            LogLevel::Error,
                            format!("Error: {}", e),
                        );
                        format!("Error: {}", e)
                    })
            }
            crate::config::ModelType::CloudOpenAI { .. } => {
                nav_state.add_log(
                    "OpenAI".to_string(),
                    LogLevel::Warning,
                    "OpenAI not yet implemented".to_string(),
                );
                "OpenAI support coming soon!".to_string()
            }
            _ => "Unknown model type".to_string(),
        }
    } else {
        nav_state.add_log(
            "Chat".to_string(),
            LogLevel::Warning,
            "No model selected".to_string(),
        );
        "Please select a model first using /models".to_string()
    };

    // Add response to chat history
    nav_state
        .chat_history
        .push(Line::styled(response, Style::default().fg(Color::Cyan)));

    nav_state.add_log(
        "AIHub".to_string(),
        LogLevel::Success,
        "Response generated successfully".to_string(),
    );

    Ok(())
}

fn handle_models_command(nav_state: &mut NavigationState, command: &str) -> Result<()> {
    let parts: Vec<&str> = command.split_whitespace().collect();

    match parts.get(0).copied() {
        Some("select") => {
            if let Some(index_str) = parts.get(1) {
                if let Ok(index) = index_str.parse::<usize>() {
                    if index > 0 && index <= nav_state.config.models.len() {
                        let model_name = nav_state.config.models[index - 1].name.clone();
                        nav_state.config.set_selected_model(model_name.clone());
                        nav_state.config.save()?;
                        nav_state.add_log(
                            "Models".to_string(),
                            LogLevel::Success,
                            format!("Switched to {}", model_name),
                        );
                    } else {
                        nav_state.add_log(
                            "Models".to_string(),
                            LogLevel::Error,
                            "Invalid model number".to_string(),
                        );
                    }
                }
            }
        }
        Some("setkey") => {
            if let (Some(provider), Some(key)) = (parts.get(1), parts.get(2)) {
                nav_state.config.set_api_key(provider, key.to_string());
                nav_state.config.save()?;
                nav_state.add_log(
                    "Models".to_string(),
                    LogLevel::Success,
                    format!("API key set for {}", provider),
                );
            } else {
                nav_state.add_log(
                    "Models".to_string(),
                    LogLevel::Error,
                    "Usage: setkey <provider> <key>".to_string(),
                );
            }
        }
        _ => {
            nav_state.add_log(
                "Models".to_string(),
                LogLevel::Warning,
                format!("Unknown command: {}", command),
            );
        }
    }

    Ok(())
}

fn handle_settings_command(nav_state: &mut NavigationState, command: &str) -> Result<()> {
    let parts: Vec<&str> = command.splitn(2, ' ').collect();

    match parts.get(0).copied() {
        Some("temp") => {
            if let Some(value_str) = parts.get(1) {
                if let Ok(value) = value_str.parse::<f32>() {
                    nav_state.config.set_temperature(value);
                    nav_state.add_log(
                        "Settings".to_string(),
                        LogLevel::Success,
                        format!("Temperature set to {:.2}", nav_state.config.temperature),
                    );
                }
            }
        }
        Some("tokens") => {
            if let Some(value_str) = parts.get(1) {
                if let Ok(value) = value_str.parse::<u32>() {
                    nav_state.config.set_max_tokens(value);
                    nav_state.add_log(
                        "Settings".to_string(),
                        LogLevel::Success,
                        format!("Max tokens set to {}", nav_state.config.max_tokens),
                    );
                }
            }
        }
        Some("prompt") => {
            if let Some(text) = parts.get(1) {
                nav_state.config.set_system_prompt(text.to_string());
                nav_state.add_log(
                    "Settings".to_string(),
                    LogLevel::Success,
                    "System prompt updated".to_string(),
                );
            }
        }
        Some("save") => {
            nav_state.config.save()?;
            nav_state.add_log(
                "Settings".to_string(),
                LogLevel::Success,
                "Configuration saved".to_string(),
            );
        }
        _ => {
            nav_state.add_log(
                "Settings".to_string(),
                LogLevel::Warning,
                format!("Unknown command: {}", command),
            );
        }
    }

    Ok(())
}

fn handle_logs_command(nav_state: &mut NavigationState, command: &str) -> Result<()> {
    match command {
        "clear" => {
            nav_state.logs.clear();
            nav_state.add_log(
                "Logs".to_string(),
                LogLevel::Info,
                "Logs cleared".to_string(),
            );
        }
        _ => {
            nav_state.add_log(
                "Logs".to_string(),
                LogLevel::Warning,
                format!("Unknown command: {}", command),
            );
        }
    }

    Ok(())
}

fn init_terminal() -> Result<Terminal<CrosstermBackend<Stderr>>> {
    let stderr = io::stderr();
    let backend = CrosstermBackend::new(stderr);
    Ok(Terminal::new(backend)?)
}

fn shutdown_terminal(mut terminal: Terminal<CrosstermBackend<Stderr>>) -> Result<()> {
    disable_raw_mode()?;
    terminal.show_cursor()?;
    Ok(())
}

fn draw(frame: &mut ratatui::Frame, nav_state: &NavigationState, input: &str) {
    let layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(3), Constraint::Length(5)])
        .split(frame.size());

    // Main content area
    let content = Paragraph::new(nav_state.get_current_view())
        .block(Block::default().borders(Borders::ALL))
        .wrap(Wrap { trim: true });
    frame.render_widget(content, layout[0]);

    // Input area with multiline support
    let input_widget = Paragraph::new(input)
        .style(
            Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        )
        .block(
            Block::default()
                .title(format!(
                    "Command Input [{:?}] - Shift+← → to select | Ctrl+A select all | ↑↓ history",
                    nav_state.current_hub
                ))
                .borders(Borders::ALL),
        )
        .wrap(Wrap { trim: false }); // Enable wrapping for long commands
    frame.render_widget(input_widget, layout[1]);
}
