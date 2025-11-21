use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct NlgRequest<'a> {
    pub query: &'a str,
    pub enrichment: &'a [String],
    pub sources: &'a [String],
}

pub fn fallback_response(request: &NlgRequest<'_>) -> String {
    let mut lines = vec![format!("Here's what I can share about '{}':", request.query)];
    if request.enrichment.is_empty() {
        lines.push("No enrichment data yet, but I'm on it.".into());
    } else {
        lines.push("Context:".into());
        lines.extend(request.enrichment.iter().map(|chunk| format!("- {chunk}")));
    }
    if !request.sources.is_empty() {
        lines.push(String::from("Sources:"));
        lines.extend(request.sources.iter().map(|src| format!("• {src}")));
    }
    lines.join("\n")
}
