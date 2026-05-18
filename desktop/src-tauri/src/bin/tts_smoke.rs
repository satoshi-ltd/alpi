fn main() {
    let rt = tokio::runtime::Runtime::new().unwrap();
    let voice = std::env::args().nth(1).unwrap_or_else(|| "en-US-AriaNeural".into());
    let text = std::env::args().nth(2)
        .unwrap_or_else(|| "Hello from edge TTS.".into());
    rt.block_on(async {
        match desktop_lib::tts::synthesize(&voice, &text).await {
            Ok(audio) => {
                eprintln!("ok: {} bytes (voice={voice})", audio.len());
                std::fs::write("/tmp/tts-smoke.mp3", &audio).unwrap();
            }
            Err(e) => {
                eprintln!("FAIL: {e}");
                std::process::exit(1);
            }
        }
    });
}
