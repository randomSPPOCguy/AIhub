#!/usr/bin/env python3
"""
Model Downloader - Download ONNX models from HuggingFace
Specifically for Mistral and other popular models
"""
import os
import sys
from pathlib import Path

# Colors
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
END = '\033[0m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*70}{END}")
    print(f"{BOLD}{BLUE}{text.center(70)}{END}")
    print(f"{BOLD}{BLUE}{'='*70}{END}\n")

def print_success(text):
    print(f"{GREEN}✓{END} {text}")

def print_error(text):
    print(f"{RED}✗{END} {text}")

def print_info(text):
    print(f"{BLUE}→{END} {text}")

def print_warning(text):
    print(f"{YELLOW}⚠{END} {text}")

# Popular ONNX models optimized for RTX 4060 (8GB VRAM)
MODELS = {
    "1": {
        "name": "Phi-3 Mini 4K (ONNX)",
        "repo": "microsoft/Phi-3-mini-4k-instruct-onnx",
        "size": "~8GB",
        "vram": "4-6GB",
        "speed": "~40 tok/s (CUDA)",
        "recommended": True,
        "description": "Microsoft's efficient 3.8B model, perfect for RTX 4060"
    },
    "2": {
        "name": "Phi-3 Mini 128K (ONNX)",
        "repo": "microsoft/Phi-3-mini-128k-instruct-onnx",
        "size": "~8GB",
        "vram": "4-6GB",
        "speed": "~40 tok/s (CUDA)",
        "recommended": True,
        "description": "Same as above but with huge 128K context window"
    },
    "3": {
        "name": "Phi-3 Small 8K (ONNX)",
        "repo": "microsoft/Phi-3-small-8k-instruct-onnx",
        "size": "~15GB",
        "vram": "7-8GB",
        "speed": "~20 tok/s (CUDA)",
        "recommended": False,
        "description": "7B model, higher quality but needs full 8GB VRAM"
    },
    "4": {
        "name": "Mistral 7B (PyTorch - need to convert)",
        "repo": "mistralai/Mistral-7B-Instruct-v0.3",
        "size": "~14GB",
        "vram": "7-8GB",
        "speed": "~15-20 tok/s (CUDA)",
        "recommended": False,
        "description": "Popular 7B model, requires ONNX conversion or quantization",
        "note": "⚠️  Not ONNX format, requires conversion or use with PyTorch"
    },
    "5": {
        "name": "Qwen 2.5 3B (PyTorch)",
        "repo": "Qwen/Qwen2.5-3B-Instruct",
        "size": "~7GB",
        "vram": "3-5GB",
        "speed": "~50 tok/s (CUDA)",
        "recommended": True,
        "description": "Excellent coding model, very fast",
        "note": "PyTorch format, works with transformers"
    }
}

def show_models():
    """Display available models"""
    print_header("Available Models for RTX 4060 (8GB VRAM)")
    
    print(f"{BOLD}Recommended for your GPU:{END}")
    print()
    
    for key, model in MODELS.items():
        if model.get("recommended"):
            print(f"{GREEN}[{key}]{END} {BOLD}{model['name']}{END}")
            print(f"    Repo: {model['repo']}")
            print(f"    Size: {model['size']} | VRAM: {model['vram']} | Speed: {model['speed']}")
            print(f"    {model['description']}")
            if model.get("note"):
                print(f"    {YELLOW}{model['note']}{END}")
            print()
    
    print(f"{BOLD}Other options:{END}")
    print()
    
    for key, model in MODELS.items():
        if not model.get("recommended"):
            print(f"{YELLOW}[{key}]{END} {model['name']}")
            print(f"    Repo: {model['repo']}")
            print(f"    Size: {model['size']} | VRAM: {model['vram']} | Speed: {model['speed']}")
            print(f"    {model['description']}")
            if model.get("note"):
                print(f"    {YELLOW}{model['note']}{END}")
            print()

def download_model(repo_id, model_name, use_onnx=True):
    """Download a model from HuggingFace"""
    print_header(f"Downloading {model_name}")
    
    # Check for huggingface_hub
    try:
        from huggingface_hub import snapshot_download
        print_success("huggingface_hub is installed")
    except ImportError:
        print_error("huggingface_hub not installed")
        print()
        print_info("Installing huggingface_hub...")
        import subprocess
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "huggingface_hub", "--break-system-packages"
            ])
            from huggingface_hub import snapshot_download
            print_success("Installed successfully")
        except:
            print_error("Failed to install. Run manually:")
            print("  pip install huggingface_hub --break-system-packages")
            return None
    
    # Set download directory
    models_dir = Path("backend/models")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Create model-specific directory
    model_dir = models_dir / repo_id.replace("/", "_")
    
    print()
    print_info(f"Repository: {repo_id}")
    print_info(f"Download to: {model_dir}")
    print()
    print_warning("This may take a while (models are large)...")
    print_warning("Download speed depends on your internet connection")
    print()
    
    try:
        local_dir = snapshot_download(
            repo_id=repo_id,
            local_dir=str(model_dir),
            local_dir_use_symlinks=False,
        )
        
        print()
        print_success(f"Downloaded successfully to: {local_dir}")
        
        # Check for ONNX files
        model_files = list(Path(local_dir).rglob("*.onnx"))
        if model_files:
            print_success(f"Found {len(model_files)} ONNX file(s)")
            for f in model_files[:3]:  # Show first 3
                print(f"  → {f.name}")
        else:
            print_warning("No ONNX files found - this might be a PyTorch model")
            print_info("You'll need to use it with transformers or convert to ONNX")
        
        return local_dir
    
    except Exception as e:
        print_error(f"Download failed: {e}")
        print()
        print_info("Possible solutions:")
        print("  1. Check your internet connection")
        print("  2. Make sure you have enough disk space")
        print("  3. Try again later")
        return None

def show_mistral_specific_guide():
    """Show specific guide for Mistral"""
    print_header("Mistral 7B - Special Instructions")
    
    print(f"{YELLOW}⚠️  Important:{END} Mistral 7B is NOT available in ONNX format on HuggingFace")
    print()
    print(f"{BOLD}You have 3 options:{END}")
    print()
    
    print(f"{GREEN}Option 1: Use PyTorch (Recommended for now){END}")
    print("  - Download: mistralai/Mistral-7B-Instruct-v0.3")
    print("  - Install: pip install transformers torch --break-system-packages")
    print("  - Your backend supports this!")
    print("  - Speed: ~15-20 tok/s on RTX 4060")
    print()
    
    print(f"{YELLOW}Option 2: Use Quantized Version (Smaller, faster){END}")
    print("  - Download: TheBloke/Mistral-7B-Instruct-v0.2-GGUF")
    print("  - Requires: llama.cpp or ctransformers")
    print("  - Speed: ~25-30 tok/s with 4-bit quantization")
    print()
    
    print(f"{BLUE}Option 3: Convert to ONNX Yourself (Advanced){END}")
    print("  - Download PyTorch model")
    print("  - Use Optimum library to convert")
    print("  - Command: optimum-cli export onnx --model mistralai/Mistral-7B-Instruct-v0.3 ./onnx-model")
    print()
    
    print(f"{BOLD}Recommended:{END} Start with Option 1 (PyTorch)")
    print("It's the easiest and works with your backend immediately!")

def configure_backend(model_path, model_type="onnx"):
    """Show how to configure backend"""
    print_header("Backend Configuration")
    
    print_info("To use your downloaded model:")
    print()
    
    print(f"{BOLD}1. Edit backend/.env:{END}")
    print()
    
    if model_type == "onnx":
        print(f"{GREEN}# For ONNX models{END}")
        print(f"ONNX_MODEL_PATH={model_path}/model.onnx")
        print(f"ONNX_EXECUTION_PROVIDER=cuda  # or directml")
    else:
        print(f"{GREEN}# For PyTorch models{END}")
        print(f"LOCAL_MODEL_PATH={model_path}")
        print(f"LOCAL_MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3")
    
    print()
    print(f"{BOLD}2. Start the backend:{END}")
    print("   cd backend")
    print("   python -m uvicorn main:app --reload")
    print()
    
    print(f"{BOLD}3. Test it:{END}")
    print("   curl -X POST http://localhost:8000/chat \\")
    print('     -H "Content-Type: application/json" \\')
    print("     -d '{")
    print('       "provider": "local",')
    print('       "message": "Hello! Tell me about yourself."')
    print("     }'")

def main():
    """Main entry point"""
    print_header("🤖 Model Downloader for RTX 4060")
    
    print_info("This tool helps you download AI models for local inference")
    print()
    
    while True:
        show_models()
        
        print(f"{BOLD}What would you like to do?{END}")
        print()
        print("[1-5] Download a model")
        print("[M]   Mistral-specific guide")
        print("[Q]   Quit")
        print()
        
        choice = input(f"{BOLD}Your choice:{END} ").strip().upper()
        
        if choice == "Q":
            print_info("Goodbye!")
            break
        
        elif choice == "M":
            show_mistral_specific_guide()
            input(f"\n{BOLD}Press Enter to continue...{END}")
        
        elif choice in MODELS:
            model = MODELS[choice]
            
            print()
            print_info(f"Selected: {model['name']}")
            
            if "mistral" in model['repo'].lower():
                print_warning("Mistral needs special handling!")
                print()
                show_mistral_specific_guide()
                print()
                
                proceed = input(f"{BOLD}Download anyway? (y/n):{END} ").strip().lower()
                if proceed != 'y':
                    continue
            
            confirm = input(f"{BOLD}Download now? This will use {model['size']} of disk space (y/n):{END} ").strip().lower()
            
            if confirm == 'y':
                local_path = download_model(model['repo'], model['name'])
                
                if local_path:
                    print()
                    is_onnx = "onnx" in model['name'].lower()
                    configure_backend(local_path, "onnx" if is_onnx else "pytorch")
            
            input(f"\n{BOLD}Press Enter to continue...{END}")
        
        else:
            print_error("Invalid choice")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_info("Exiting...")
        sys.exit(0)
