use anyhow::{anyhow, Result};
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int};

const DEFAULT_BUFFER: usize = 8 * 1024;

pub struct GoBridge;

impl GoBridge {
    pub fn music_query(&self, query: &str) -> Result<String> {
        call_with_buffer(query, DEFAULT_BUFFER, |q, buf, len| unsafe {
            go_music_query(q, buf, len)
        })
    }

    pub fn sports_query(&self, query: &str) -> Result<String> {
        call_with_buffer(query, DEFAULT_BUFFER, |q, buf, len| unsafe {
            go_sports_query(q, buf, len)
        })
    }
}

pub struct CppBridge;

impl CppBridge {
    pub fn game_query(&self, query: &str) -> Result<String> {
        call_with_buffer(query, DEFAULT_BUFFER, |q, buf, len| unsafe {
            cpp_game_query(q, buf, len)
        })
    }

    pub fn discord_status(&self) -> Result<String> {
        call_with_buffer("", DEFAULT_BUFFER, |_, buf, len| unsafe {
            cpp_discord_status(buf, len)
        })
    }
}

fn call_with_buffer<F>(input: &str, buf_size: usize, f: F) -> Result<String>
where
    F: Fn(*const c_char, *mut c_char, c_int) -> c_int,
{
    let query = CString::new(input)?;
    let mut buffer = vec![0u8; buf_size];
    let status = f(query.as_ptr(), buffer.as_mut_ptr() as *mut c_char, buf_size as c_int);
    if status < 0 {
        return Err(anyhow!("FFI call failed with status {}", status));
    }
    let c_str =
        unsafe { CStr::from_ptr(buffer.as_ptr() as *const c_char) }.to_str()?.to_owned();
    Ok(c_str)
}

extern "C" {
    fn go_music_query(query: *const c_char, result_buf: *mut c_char, buf_size: c_int) -> c_int;
    fn go_sports_query(query: *const c_char, result_buf: *mut c_char, buf_size: c_int) -> c_int;
    fn cpp_game_query(query: *const c_char, result_buf: *mut c_char, buf_size: c_int) -> c_int;
    fn cpp_discord_status(result_buf: *mut c_char, buf_size: c_int) -> c_int;
}
