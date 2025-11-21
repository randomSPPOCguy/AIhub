#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Intent {
    Music,
    Sports,
    Game,
    General,
}

pub struct IntentClassifier;

impl IntentClassifier {
    pub fn classify(&self, query: &str) -> Intent {
        let lower = query.to_lowercase();
        if contains_any(&lower, &["song", "album", "artist", "music"]) {
            Intent::Music
        } else if contains_any(&lower, &["score", "match", "league", "team", "sports"]) {
            Intent::Sports
        } else if contains_any(&lower, &["game", "quest", "discord"]) {
            Intent::Game
        } else {
            Intent::General
        }
    }
}

fn contains_any(haystack: &str, needles: &[&str]) -> bool {
    needles.iter().any(|needle| haystack.contains(needle))
}
