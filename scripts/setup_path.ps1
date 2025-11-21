# Helper script to add MinGW GCC to PATH for current session
# Run this before building: . .\scripts\setup_path.ps1

$mingwPath = "C:\msys64\mingw64\bin"

if (Test-Path $mingwPath) {
    if ($env:Path -notlike "*$mingwPath*") {
        $env:Path += ";$mingwPath"
        Write-Host "Added $mingwPath to PATH for this session" -ForegroundColor Green
        Write-Host "Verifying GCC is available..." -ForegroundColor Yellow
        gcc --version
    } else {
        Write-Host "MinGW is already in PATH" -ForegroundColor Green
        gcc --version
    }
} else {
    Write-Host "MinGW not found at $mingwPath" -ForegroundColor Red
    Write-Host "Please install MSYS2 from https://www.msys2.org/" -ForegroundColor Yellow
    Write-Host "Then install MinGW: pacman -S mingw-w64-x86_64-toolchain" -ForegroundColor Yellow
}

