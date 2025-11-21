use chrono::Duration;
use project_frank::cache::CacheStore;
use serde_json::json;
use tempfile::tempdir;

#[test]
fn cache_round_trip() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("test.sqlite3");
    let store = CacheStore::new(&path).expect("cache init");

    let key = "artist::test";
    store
        .set(key, &json!({"value": 42}), Some(Duration::seconds(60)))
        .expect("insert");
    let fetched = store.get(key).expect("get").expect("exists");
    assert_eq!(fetched.payload["value"], 42);
}
