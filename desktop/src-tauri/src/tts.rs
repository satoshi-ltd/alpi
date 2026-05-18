use futures_util::{SinkExt, StreamExt};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::Message;

const TRUSTED_TOKEN: &str = "6A5AA1D4EAFF4E9FB37E23D68491D6F4";
const WSS_URL: &str = "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1";
// Chromium version must match a current Edge release or Microsoft 403s. Bump in sync with edge-tts upstream.
const UA: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                  (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0";
const GEC_VERSION: &str = "1-143.0.3650.75";

fn random_muid() -> String {
    let bytes: [u8; 16] = *uuid::Uuid::new_v4().as_bytes();
    let mut s = String::with_capacity(32);
    for b in bytes.iter() {
        s.push_str(&format!("{b:02X}"));
    }
    s
}

// SHA-256(ticks + TrustedClientToken), ticks = Windows FILETIME rounded to 5-min window.
fn gec_token() -> String {
    use sha2::{Digest, Sha256};
    let unix_secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    // Windows epoch is 1601-01-01; offset to Unix epoch is 11644473600s.
    let ticks = ((unix_secs + 11_644_473_600) as i128) * 10_000_000;
    let ticks = ticks - (ticks % 3_000_000_000); // 5-min granularity
    let payload = format!("{ticks}{TRUSTED_TOKEN}");
    let digest = Sha256::digest(payload.as_bytes());
    let mut hex = String::with_capacity(64);
    for b in digest.iter() {
        hex.push_str(&format!("{b:02X}"));
    }
    hex
}

fn escape_xml(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 8);
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '\'' => out.push_str("&apos;"),
            '"' => out.push_str("&quot;"),
            _ => out.push(c),
        }
    }
    out
}

fn now_header() -> String {
    chrono::Utc::now()
        .format("%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)")
        .to_string()
}

pub async fn synthesize(voice: &str, text: &str) -> Result<Vec<u8>, String> {
    if voice.is_empty() {
        return Err("voice required".into());
    }
    if text.is_empty() {
        return Err("text required".into());
    }

    let conn_id = uuid::Uuid::new_v4().simple().to_string().to_uppercase();
    let token = gec_token();
    let url = format!(
        "{WSS_URL}?TrustedClientToken={TRUSTED_TOKEN}\
         &Sec-MS-GEC={token}\
         &Sec-MS-GEC-Version={GEC_VERSION}\
         &ConnectionId={conn_id}"
    );

    let mut req = url
        .into_client_request()
        .map_err(|e| format!("bad ws request: {e}"))?;
    let headers = req.headers_mut();
    headers.insert("User-Agent", UA.parse().unwrap());
    headers.insert(
        "Origin",
        "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold".parse().unwrap(),
    );
    headers.insert("Pragma", "no-cache".parse().unwrap());
    headers.insert("Cache-Control", "no-cache".parse().unwrap());
    headers.insert("Accept-Encoding", "gzip, deflate, br".parse().unwrap());
    headers.insert("Accept-Language", "en-US,en;q=0.9".parse().unwrap());
    headers.insert(
        "Cookie",
        format!("muid={};", random_muid()).parse().unwrap(),
    );

    let (mut ws, _resp) = tokio::time::timeout(
        Duration::from_secs(8),
        tokio_tungstenite::connect_async(req),
    )
    .await
    .map_err(|_| "ws connect timed out".to_string())?
    .map_err(|e| format!("ws connect failed: {e}"))?;

    let ts = now_header();

    let config = format!(
        "X-Timestamp:{ts}\r\n\
         Content-Type:application/json; charset=utf-8\r\n\
         Path:speech.config\r\n\r\n\
         {{\"context\":{{\"synthesis\":{{\"audio\":{{\
         \"metadataoptions\":{{\"sentenceBoundaryEnabled\":\"false\",\
         \"wordBoundaryEnabled\":\"false\"}},\
         \"outputFormat\":\"audio-24khz-48kbitrate-mono-mp3\"}}}}}}}}"
    );
    ws.send(Message::Text(config))
        .await
        .map_err(|e| format!("send config: {e}"))?;

    let req_id = uuid::Uuid::new_v4().simple().to_string();
    let ssml = format!(
        "X-RequestId:{req_id}\r\n\
         Content-Type:application/ssml+xml\r\n\
         X-Timestamp:{ts}\r\n\
         Path:ssml\r\n\r\n\
         <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>\
         <voice name='{voice}'>\
         <prosody pitch='+0Hz' rate='+0%' volume='+0%'>{text}</prosody>\
         </voice></speak>",
        voice = voice,
        text = escape_xml(text),
    );
    ws.send(Message::Text(ssml))
        .await
        .map_err(|e| format!("send ssml: {e}"))?;

    let mut audio: Vec<u8> = Vec::with_capacity(64 * 1024);
    let recv_timeout = Duration::from_secs(30);

    loop {
        let next = tokio::time::timeout(recv_timeout, ws.next())
            .await
            .map_err(|_| "ws receive timed out".to_string())?;
        let msg = match next {
            Some(Ok(m)) => m,
            Some(Err(e)) => return Err(format!("ws error: {e}")),
            None => break,
        };
        match msg {
            Message::Binary(data) => {
                if data.len() < 2 {
                    continue;
                }
                let header_len = u16::from_be_bytes([data[0], data[1]]) as usize;
                if data.len() < 2 + header_len {
                    continue;
                }
                let header = std::str::from_utf8(&data[2..2 + header_len]).unwrap_or("");
                if header.contains("Path:audio") {
                    audio.extend_from_slice(&data[2 + header_len..]);
                }
            }
            Message::Text(t) => {
                if t.contains("Path:turn.end") {
                    break;
                }
            }
            Message::Close(_) => break,
            _ => {}
        }
    }

    let _ = ws.send(Message::Close(None)).await;

    if audio.is_empty() {
        return Err(format!(
            "no audio received (voice={voice}, text_len={})",
            text.len(),
        ));
    }
    Ok(audio)
}

// Tray app never quits → cache must self-bound. FIFO, 16 entries (~200KB).
const CACHE_LIMIT: usize = 16;

#[derive(Default)]
pub struct Cache {
    entries: Vec<(String, Arc<Vec<u8>>)>,
}

impl Cache {
    fn get(&self, key: &str) -> Option<Arc<Vec<u8>>> {
        self.entries
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| Arc::clone(v))
    }

    fn put(&mut self, key: String, value: Arc<Vec<u8>>) {
        self.entries.retain(|(k, _)| k != &key);
        if self.entries.len() >= CACHE_LIMIT {
            self.entries.remove(0);
        }
        self.entries.push((key, value));
    }
}

static CACHE: std::sync::OnceLock<Mutex<Cache>> = std::sync::OnceLock::new();

fn cache() -> &'static Mutex<Cache> {
    CACHE.get_or_init(|| Mutex::new(Cache::default()))
}

pub async fn synthesize_cached(voice: &str, text: &str) -> Result<Arc<Vec<u8>>, String> {
    let key = format!("{voice}\x00{text}");
    if let Some(hit) = cache().lock().await.get(&key) {
        return Ok(hit);
    }
    let audio = Arc::new(synthesize(voice, text).await?);
    cache().lock().await.put(key, Arc::clone(&audio));
    Ok(audio)
}
