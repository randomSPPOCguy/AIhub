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

    // Check if 'go' command is available
    if Command::new("go").arg("version").output().is_err() {
        println!("cargo:warning=Go is not installed or not in PATH. Skipping go build step.");
        println!("cargo:warning=Install Go from https://go.dev/dl/ to enable Go features.");
        return Ok(());
    }
    
    // Check if CGO can work (needs a C compiler on Windows)
    // CGO requires gcc or clang to be available
    let has_gcc = Command::new("gcc").arg("--version").output().is_ok();
    let has_clang = Command::new("clang").arg("--version").output().is_ok();
    
    if !has_gcc && !has_clang {
        // Check common Windows locations
        let common_paths = [
            r"C:\msys64\mingw64\bin\gcc.exe",
            r"C:\TDM-GCC-64\bin\gcc.exe",
            r"C:\mingw64\bin\gcc.exe",
        ];
        
        let found_gcc = common_paths.iter().any(|path| Path::new(path).exists());
        
        if !found_gcc {
            eprintln!("cargo:error=GCC or Clang is required for CGO but not found in PATH.");
            eprintln!("cargo:error=");
            eprintln!("cargo:error=To fix this:");
            eprintln!("cargo:error=  1. Install MinGW-w64 (via MSYS2: https://www.msys2.org/)");
            eprintln!("cargo:error=  2. Add C:\\msys64\\mingw64\\bin to your system PATH");
            eprintln!("cargo:error=  3. Restart your terminal");
            eprintln!("cargo:error=");
            eprintln!("cargo:error=Or install TDM-GCC: https://jmeubank.github.io/tdm-gcc/");
            return Err("CGO requires a C compiler (gcc or clang) but none was found".into());
        } else {
            eprintln!("cargo:warning=GCC found but not in PATH. Add the MinGW bin directory to PATH.");
            eprintln!("cargo:warning=Example: $env:Path += ';C:\\msys64\\mingw64\\bin'");
        }
    }

    // Use .a extension for GNU toolchain, .lib for MSVC
    let output_name = if cfg!(target_env = "gnu") {
        "libfrankgo.a"  // GNU toolchain (MinGW)
    } else if cfg!(target_env = "msvc") {
        "frankgo.lib"   // MSVC toolchain
    } else {
        "libfrankgo.a"  // Default to .a for other Unix-like
    };
    let output_path = target_dir.join(output_name);

    // Change to the go directory and build from there
    // CGO_ENABLED=1 is required for c-archive buildmode with C interop
    let mut cmd = Command::new("go");
    cmd.args([
        "build",
        "-buildmode=c-archive",
        "-o",
        output_path.to_str().unwrap(),
        ".",
    ])
    .current_dir(&go_src_dir);

    // Enable CGO (required for import "C")
    cmd.env("CGO_ENABLED", "1");

    // Ensure MinGW gcc is in PATH for CGO
    // Check common Windows locations and add to PATH if found
    let mingw_paths = [
        r"C:\msys64\mingw64\bin",
        r"C:\TDM-GCC-64\bin",
        r"C:\mingw64\bin",
    ];

    let mut path_additions = Vec::new();
    for mingw_path in &mingw_paths {
        if Path::new(mingw_path).join("gcc.exe").exists() {
            path_additions.push(*mingw_path);
        }
    }

    // Build enhanced PATH with MinGW directories
    let enhanced_path = if !path_additions.is_empty() {
        let current_path = env::var("PATH").unwrap_or_default();
        let mut new_path = current_path.clone();
        for path in path_additions {
            if !current_path.contains(path) {
                new_path.push(';');
                new_path.push_str(path);
            }
        }
        Some(new_path)
    } else {
        None
    };

    // Apply enhanced PATH to Go command
    if let Some(ref new_path) = enhanced_path {
        cmd.env("PATH", new_path);

        // Also set CC explicitly for CGO
        for path in mingw_paths {
            let gcc_path = Path::new(path).join("gcc.exe");
            if gcc_path.exists() {
                cmd.env("CC", gcc_path.to_string_lossy().to_string());
                break;
            }
        }
    }
    
    let output = cmd.output()?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);

        eprintln!("cargo:error=Go build failed!");
        if !stdout.is_empty() {
            eprintln!("cargo:error=stdout: {}", stdout);
        }
        if !stderr.is_empty() {
            eprintln!("cargo:error=stderr: {}", stderr);
        }

        // Provide helpful hints based on common errors
        if stderr.contains("gcc") || stderr.contains("C compiler") {
            eprintln!("cargo:error=");
            eprintln!("cargo:error=This error suggests CGO can't find a C compiler.");
            eprintln!("cargo:error=Make sure GCC is in your PATH: gcc --version");
        }

        return Err("failed to build Go shared library".into());
    }

    // Verify that the static library was created
    let lib_path = target_dir.join(output_name);

    if !lib_path.exists() {
        eprintln!("cargo:error=Go build succeeded but {} not found at {:?}", output_name, lib_path);
        return Err("Go static library not found after build".into());
    }

    // c-archive mode creates the .lib file directly - no need for dlltool
    println!("cargo:warning=Successfully built Go static library: {}", output_name);

    // Check if header file exists in source directory and copy if needed
    let source_h_path = go_src_dir.join("frankgo.h");
    if source_h_path.exists() {
        std::fs::copy(&source_h_path, target_dir.join("frankgo.h"))?;
        println!("cargo:warning=Copied frankgo.h from source directory");
    }

    // Link the static library
    println!(
        "cargo:rustc-link-search=native={}",
        target_dir.to_string_lossy()
    );
    println!("cargo:rustc-link-lib=static=frankgo");
    Ok(())
}

fn build_cpp_module(_out_dir: &Path) -> Result<(), Box<dyn Error>> {
    let src_file = Path::new("..").join("cpp").join("frankcpp.cpp");
    if !src_file.exists() {
        println!("cargo:warning=C++ sources not found. Skipping cpp build step.");
        return Ok(());
    }

    // On Windows, we need to create a DLL. The cc crate creates static libs by default.
    // We'll compile as a static library and link it, which works for our FFI needs.
    cc::Build::new()
        .cpp(true)
        .flag_if_supported("/std:c++17")
        .flag_if_supported("-std=c++17")
        .file(&src_file)
        .compile("frankcpp");

    println!("cargo:rustc-link-lib=static=frankcpp");
    println!(
        "cargo:rerun-if-changed={}",
        src_file.as_path().display()
    );
    Ok(())
}
