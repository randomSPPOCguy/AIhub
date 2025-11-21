use project_frank::ffi::{CppBridge, GoBridge};

#[test]
fn go_music_stub_responds() {
    let bridge = GoBridge;
    let resp = bridge.music_query("sample").expect("music query");
    assert!(resp.contains("music"));
}

#[test]
fn cpp_discord_status_stub_responds() {
    let bridge = CppBridge;
    let resp = bridge.discord_status().expect("discord status");
    assert!(resp.contains("discord"));
}
