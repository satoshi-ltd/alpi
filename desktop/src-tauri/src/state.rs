use serde::Serialize;

#[derive(Serialize)]
pub struct SessionEntry {
    pub id: String,
    pub profile: String,
    pub mtime: u64,
    pub started_at: f64,
    pub updated_at: f64,
    pub first_user: String,
    pub model: Option<String>,
    pub turn_count: usize,
    pub kind: String,
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub cost_usd: f64,
    pub last_ctx_tokens: u64,
}

#[derive(Serialize, Clone)]
pub struct DecryptedMessage {
    pub seq: u32,
    pub from: String,
    pub from_pubkey: String,
    pub body: String,
    pub at: String,
}
