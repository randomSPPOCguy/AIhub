use anyhow::Result;
use clap::{Parser, ValueEnum};
use project_frank::coordinator::AppCoordinator;
use project_frank::{tui, web};

#[derive(Parser, Debug)]
#[command(name = "Project Frank")]
#[command(about = "AI Gateway Hub - Multi-language AI orchestration system", long_about = None)]
struct Args {
    /// Interface mode: tui (terminal) or web (browser)
    #[arg(short, long, value_enum, default_value_t = Mode::Tui)]
    mode: Mode,
}

#[derive(Debug, Clone, ValueEnum)]
enum Mode {
    /// Terminal User Interface
    Tui,
    /// Web Browser Interface
    Web,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();

    match args.mode {
        Mode::Tui => {
            let mut coordinator = AppCoordinator::new()?;
            tui::run(&mut coordinator)
        }
        Mode::Web => web::run_server().await,
    }
}
