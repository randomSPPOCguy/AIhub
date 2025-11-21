use anyhow::Result;
use crossterm::event::{self, Event, KeyCode, KeyModifiers};
use crossterm::terminal::{disable_raw_mode, enable_raw_mode};
use ratatui::backend::CrosstermBackend;
use ratatui::layout::{Constraint, Direction, Layout};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Terminal;
use std::io::{self, Stdout};
use std::time::Duration;

pub trait QueryEngine {
    fn handle_query(&mut self, query: &str) -> Result<String>;
}

pub fn run(engine: &mut impl QueryEngine) -> Result<()> {
    let mut ui_state = UiState::default();
    enable_raw_mode()?;
    let mut terminal = init_terminal()?;

    let result = loop {
        terminal.draw(|frame| draw(frame, &ui_state))?;
        if event::poll(Duration::from_millis(250))? {
            match event::read()? {
                Event::Key(key_event) => {
                    if key_event.code == KeyCode::Char('c')
                        && key_event.modifiers.contains(KeyModifiers::CONTROL)
                    {
                        break Ok(());
                    }
                    match key_event.code {
                        KeyCode::Char(ch) => ui_state.input.push(ch),
                        KeyCode::Backspace => {
                            ui_state.input.pop();
                        }
                        KeyCode::Enter => {
                            let query = ui_state.input.trim().to_owned();
                            if !query.is_empty() {
                                ui_state
                                    .messages
                                    .push(Line::styled(format!("> {query}"), Style::default()));
                                match engine.handle_query(&query) {
                                    Ok(response) => ui_state.messages.push(Line::styled(
                                        response,
                                        Style::default().fg(Color::Cyan),
                                    )),
                                    Err(err) => ui_state.messages.push(Line::styled(
                                        format!("Error: {err}"),
                                        Style::default().fg(Color::Red),
                                    )),
                                }
                            }
                            ui_state.input.clear();
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

fn init_terminal() -> Result<Terminal<CrosstermBackend<Stdout>>> {
    let stdout = io::stdout();
    let backend = CrosstermBackend::new(stdout);
    Ok(Terminal::new(backend)?)
}

fn shutdown_terminal(mut terminal: Terminal<CrosstermBackend<Stdout>>) -> Result<()> {
    disable_raw_mode()?;
    terminal.show_cursor()?;
    Ok(())
}

fn draw(frame: &mut ratatui::Frame<CrosstermBackend<Stdout>>, ui_state: &UiState) {
    let layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(3), Constraint::Length(3)])
        .split(frame.size());

    let history = Paragraph::new(ui_state.messages.clone())
        .block(Block::default().title("Conversation").borders(Borders::ALL))
        .wrap(Wrap { trim: true });
    frame.render_widget(history, layout[0]);

    let input = Paragraph::new(ui_state.input.as_str())
        .style(
            Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        )
        .block(Block::default().title("Prompt").borders(Borders::ALL));
    frame.render_widget(input, layout[1]);
}

struct UiState {
    input: String,
    messages: Vec<Line<'static>>,
}

impl Default for UiState {
    fn default() -> Self {
        Self {
            input: String::new(),
            messages: vec![Line::from(vec![
                Span::styled(
                    "Project Frank ready. Type a query and press Enter (Esc or Ctrl+C to exit).",
                    Style::default().fg(Color::Green),
                ),
            ])],
        }
    }
}
