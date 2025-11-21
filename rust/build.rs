use std::env;
use std::error::Error;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    if let Err(err) = try_main() {
        panic!("build script failed: {err:?}");
    }
}

fn try_main() -> Result<(), Box<dyn Error>> {
    println!("cargo:rerun-if-changed=../go/frankgo.go");
    println!("cargo:rerun-if-changed=../cpp/frankcpp.cpp");

    let out_dir = PathBuf::from(env::var("OUT_DIR")?);
    build_go_module(&out_dir)?;
    build_cpp_module(&out_dir)?;
    Ok(())
}

fn build_go_module(out_dir: &Path) -> Result<(), Box<dyn Error>> {
    let target_dir = out_dir.join("libfrankgo");
    std::fs::create_dir_all(&target_dir)?;

    let go_src_dir = Path::new("..").join("go");
    if !go_src_dir.exists() {
        println!("cargo:warning=Go sources not found. Skipping go build step.");
        return Ok(());
    }

    let output_name = format!(
        "{}{}",
        shared_prefix(),
        format!("frankgo{}", shared_extension())
    );
    let output_path = target_dir.join(output_name);

    let status = Command::new("go")
        .args([
            "build",
            "-buildmode=c-shared",
            "-o",
            output_path.to_str().unwrap(),
        ])
        .arg(go_src_dir.to_str().unwrap())
        .status()?;

    if !status.success() {
        return Err("failed to build Go shared library".into());
    }

    println!(
        "cargo:rustc-link-search=native={}",
        target_dir.to_string_lossy()
    );
    println!("cargo:rustc-link-lib=dylib=frankgo");
    Ok(())
}

fn build_cpp_module(out_dir: &Path) -> Result<(), Box<dyn Error>> {
    let src_file = Path::new("..").join("cpp").join("frankcpp.cpp");
    if !src_file.exists() {
        println!("cargo:warning=C++ sources not found. Skipping cpp build step.");
        return Ok(());
    }

    cc::Build::new()
        .cpp(true)
        .flag_if_supported("-std=c++17")
        .shared_flag(true)
        .file(&src_file)
        .compile("frankcpp");

    println!("cargo:rustc-link-lib=dylib=frankcpp");
    println!(
        "cargo:rerun-if-changed={}",
        src_file.as_path().display()
    );
    Ok(())
}

fn shared_extension() -> &'static str {
    if cfg!(target_os = "windows") {
        ".dll"
    } else if cfg!(target_os = "macos") {
        ".dylib"
    } else {
        ".so"
    }
}

fn shared_prefix() -> &'static str {
    if cfg!(target_os = "windows") {
        ""
    } else {
        "lib"
    }
}
