/// Session management for AI Hub conversations
/// Automatically cleans up inactive sessions after 15 seconds

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,      // "user" or "assistant"
    pub content: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct Session {
    pub id: String,
    pub messages: Vec<Message>,
    pub last_activity: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
}

impl Session {
    fn new() -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4().to_string(),
            messages: Vec::new(),
            last_activity: now,
            created_at: now,
        }
    }

    fn add_message(&mut self, role: String, content: String) {
        self.messages.push(Message {
            role,
            content,
            timestamp: Utc::now(),
        });
        self.last_activity = Utc::now();
    }

    fn is_expired(&self, timeout_secs: i64) -> bool {
        let now = Utc::now();
        let duration = now.signed_duration_since(self.last_activity);
        duration.num_seconds() > timeout_secs
    }
}

pub struct SessionManager {
    sessions: Arc<RwLock<HashMap<String, Session>>>,
    timeout_seconds: i64,
}

impl SessionManager {
    pub fn new(timeout_seconds: i64) -> Self {
        Self {
            sessions: Arc::new(RwLock::new(HashMap::new())),
            timeout_seconds,
        }
    }

    /// Get or create a session
    pub async fn get_or_create_session(&self, session_id: Option<String>) -> Session {
        let mut sessions = self.sessions.write().await;

        // If session_id provided, try to get existing session
        if let Some(id) = session_id {
            if let Some(session) = sessions.get_mut(&id) {
                // Update last activity
                session.last_activity = Utc::now();
                return session.clone();
            }
        }

        // Create new session
        let session = Session::new();
        let id = session.id.clone();
        sessions.insert(id.clone(), session.clone());
        session
    }

    /// Add a message to a session
    pub async fn add_message(&self, session_id: &str, role: String, content: String) {
        let mut sessions = self.sessions.write().await;
        if let Some(session) = sessions.get_mut(session_id) {
            session.add_message(role, content);
        }
    }

    /// Get conversation history for a session
    pub async fn get_history(&self, session_id: &str) -> Vec<Message> {
        let sessions = self.sessions.read().await;
        sessions
            .get(session_id)
            .map(|s| s.messages.clone())
            .unwrap_or_default()
    }

    /// Clean up expired sessions
    pub async fn cleanup_expired(&self) {
        let mut sessions = self.sessions.write().await;
        let timeout = self.timeout_seconds;

        // Collect expired session IDs
        let expired: Vec<String> = sessions
            .iter()
            .filter(|(_, session)| session.is_expired(timeout))
            .map(|(id, _)| id.clone())
            .collect();

        // Remove expired sessions
        for id in expired {
            sessions.remove(&id);
        }
    }

    /// Get total active sessions count
    pub async fn active_count(&self) -> usize {
        self.sessions.read().await.len()
    }

    /// Start background cleanup task
    pub fn start_cleanup_task(self: Arc<Self>) {
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(5));
            loop {
                interval.tick().await;
                self.cleanup_expired().await;
            }
        });
    }
}
