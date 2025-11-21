# Setting Up GCC for CGO on Windows

## Quick Fix (Current Session Only)

Run this in PowerShell before building:

```powershell
. .\scripts\setup_path.ps1
.\scripts\build_all.ps1
```

Or manually:
```powershell
$env:Path += ";C:\msys64\mingw64\bin"
.\scripts\build_all.ps1
```

## Permanent Fix

### Option 1: System Environment Variables (Recommended)

1. Press `Win + X` and select "System"
2. Click "Advanced system settings"
3. Click "Environment Variables"
4. Under "System variables", find and select "Path", then click "Edit"
5. Click "New" and add: `C:\msys64\mingw64\bin`
6. Click "OK" on all dialogs
7. **Restart PowerShell/terminal** for changes to take effect

### Option 2: User Environment Variables

1. Press `Win + R`, type `sysdm.cpl`, press Enter
2. Go to "Advanced" tab → "Environment Variables"
3. Under "User variables", find "Path" (or create it)
4. Add: `C:\msys64\mingw64\bin`
5. **Restart PowerShell/terminal**

### Verify It Works

After adding to PATH and restarting terminal:

```powershell
gcc --version
```

You should see GCC version information. Then try building:

```powershell
.\scripts\build_all.ps1
```

## Alternative: Use TDM-GCC

If you prefer TDM-GCC instead of MinGW:

1. Download: https://jmeubank.github.io/tdm-gcc/
2. Install it
3. Add `C:\TDM-GCC-64\bin` to PATH (same steps as above)

## Troubleshooting

- **"gcc: command not found"** → PATH not set correctly or terminal not restarted
- **"CGO_ENABLED=0"** → Check that CGO is enabled (build script handles this)
- **Build still fails** → Make sure you restarted the terminal after adding to PATH

