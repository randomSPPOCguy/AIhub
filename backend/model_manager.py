"""
Model Manager - Handles downloading, installing, and managing AI models
"""
import os
import json
import shutil
import time
from typing import Callable, Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from huggingface_hub import snapshot_download, login
from tqdm import tqdm

# Import from utils to avoid circular import
from utils import get_aihub_dirs

# Constants - Recommended Open-Source Models
DEFAULT_MODELS = [
    {
        "id": "phi-3-mini-4k",
        "name": "Phi-3 Mini 4K",
        "huggingface_id": "microsoft/Phi-3-mini-4k-instruct",
        "size_gb": 2.4,
        "parameters": "3.8B",
        "license": "MIT",
        "capabilities": ["general", "coding", "math"],
        "speed_rating": 5,
        "description": "Microsoft's compact yet capable model, ideal for everyday use."
    },
    {
        "id": "gemma-2-2b",
        "name": "Gemma 2 2B",
        "huggingface_id": "google/gemma-2-2b-it",
        "size_gb": 1.6,
        "parameters": "2B",
        "license": "Gemma Terms",
        "capabilities": ["general", "coding", "fast"],
        "speed_rating": 6,
        "description": "Google's lightweight model optimized for speed and efficiency."
    },
    {
        "id": "qwen2-3b",
        "name": "Qwen2.5 3B",
        "huggingface_id": "Qwen/Qwen2.5-3B-Instruct",
        "size_gb": 1.9,
        "parameters": "3B",
        "license": "Apache 2.0",
        "capabilities": ["general", "coding", "multilingual"],
        "speed_rating": 5,
        "description": "Alibaba's multilingual model with strong coding capabilities."
    },
    {
        "id": "llama-3-8b",
        "name": "Llama 3.2 8B",
        "huggingface_id": "meta-llama/Llama-3.2-8B-Instruct",
        "size_gb": 4.7,
        "parameters": "8B",
        "license": "Llama 3 Community",
        "capabilities": ["general", "creative", "reasoning"],
        "speed_rating": 4,
        "description": "Meta's versatile model balancing quality and performance."
    },
    {
        "id": "mistral-7b-v0.3",
        "name": "Mistral 7B v0.3",
        "huggingface_id": "mistralai/Mistral-7B-Instruct-v0.3",
        "size_gb": 4.1,
        "parameters": "7B",
        "license": "Apache 2.0",
        "capabilities": ["general", "instruction", "reasoning"],
        "speed_rating": 4,
        "description": "Mistral AI's instruction-following specialist with strong reasoning."
    },
    {
        "id": "phi-3-medium-128k",
        "name": "Phi-3 Medium 128K",
        "huggingface_id": "microsoft/Phi-3-medium-128k-instruct",
        "size_gb": 8.2,
        "parameters": "14B",
        "license": "MIT",
        "capabilities": ["general", "coding", "long-context"],
        "speed_rating": 3,
        "description": "Microsoft's medium-sized model with extremely long context (128K tokens)."
    },
    {
        "id": "mixtral-8x7b",
        "name": "Mixtral 8x7B",
        "huggingface_id": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "size_gb": 26.0,
        "parameters": "47B",
        "license": "Apache 2.0",
        "capabilities": ["general", "expert", "multilingual"],
        "speed_rating": 2,
        "description": "Mistral's MoE architecture combining 8 expert models, requires 32GB+ RAM."
    },
    {
        "id": "llama-3-70b",
        "name": "Llama 3.1 70B",
        "huggingface_id": "meta-llama/Llama-3.1-70B-Instruct",
        "size_gb": 40.0,
        "parameters": "70B",
        "license": "Llama 3 Community",
        "capabilities": ["general", "creative", "reasoning", "expert"],
        "speed_rating": 1,
        "description": "Meta's flagship model with state-of-the-art performance, requires 48GB+ RAM."
    }
]

# Progress callback type
ProgressCallback = Callable[[int, int], None]

class ModelDownloadProgress:
    """Track download progress for a model"""
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.progress_percent = 0
        self.status = "initializing"
        self.error = None
        self.start_time = datetime.now()
        self.completion_time = None
        self.callbacks = []
        self.last_update_time = time.time()
    
    def add_callback(self, callback: ProgressCallback):
        """Add a callback function that will be called on progress updates"""
        self.callbacks.append(callback)
    
    def update(self, downloaded: int, total: int):
        """Update progress and notify all callbacks (throttled to 100ms)"""
        now = time.time()
        # Throttle updates to every 100ms
        if now - self.last_update_time < 0.1 and downloaded < total:
            return
            
        self.last_update_time = now
        self.downloaded_bytes = downloaded
        self.total_bytes = total
        self.progress_percent = int(100 * downloaded / total) if total > 0 else 0
        self.status = "downloading"
        
        # Notify all callbacks
        for callback in self.callbacks:
            try:
                callback(downloaded, total)
            except Exception:
                pass  # Don't let callback errors break downloads
    
    def complete(self):
        """Mark download as complete"""
        self.progress_percent = 100
        self.status = "completed"
        self.completion_time = datetime.now()
        
        # Notify all callbacks
        for callback in self.callbacks:
            try:
                callback(self.total_bytes, self.total_bytes)
            except Exception:
                pass
    
    def fail(self, error: Exception):
        """Mark download as failed"""
        self.status = "failed"
        self.error = str(error)
        self.completion_time = datetime.now()

class ModelManager:
    """Manages AI model downloads, configurations and lifecycle"""
    
    def __init__(self):
        self.dirs = get_aihub_dirs()
        self.active_downloads = {}
        self.load_model_registry()
        self._load_hf_token()
    
    def load_model_registry(self):
        """Load the registry of available and installed models"""
        registry_path = self.dirs["config"] / "models_registry.json"
        
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    self.models_registry = json.load(f)
            except Exception:
                self.models_registry = {"models": DEFAULT_MODELS.copy()}
        else:
            self.models_registry = {"models": DEFAULT_MODELS.copy()}
            self.save_model_registry()
        
        # Update installed status by checking directories
        self._update_installed_status()
    
    def save_model_registry(self):
        """Save the models registry to disk"""
        registry_path = self.dirs["config"] / "models_registry.json"
        try:
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(self.models_registry, f, indent=2)
            return True
        except Exception:
            return False
    
    def _update_installed_status(self):
        """Update the installed status of all models by checking if they exist on disk"""
        for model in self.models_registry["models"]:
            model_dir = self.dirs["models"] / model["id"]
            model["installed"] = model_dir.exists() and any(model_dir.iterdir())
            
            # Check for config file
            config_file = self.dirs["config"] / f"{model['id']}_config.json"
            model["configured"] = config_file.exists()
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of all available models with installation status"""
        self._update_installed_status()
        return self.models_registry["models"]
    
    def get_installed_models(self) -> List[Dict[str, Any]]:
        """Get list of installed models only"""
        self._update_installed_status()
        return [m for m in self.models_registry["models"] if m.get("installed", False)]
    
    def get_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific model by ID"""
        for model in self.models_registry["models"]:
            if model["id"] == model_id:
                return model
        return None
    
    def _load_hf_token(self):
        """Load HuggingFace token from config"""
        token_path = self.dirs["config"] / "huggingface_token.json"
        if token_path.exists():
            try:
                with open(token_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    token = data.get("token")
                    if token:
                        # Log in to HuggingFace Hub
                        login(token=token, add_to_git_credential=False)
            except Exception:
                pass  # Token not configured or invalid
    
    def save_hf_token(self, token: str) -> Dict[str, Any]:
        """Save HuggingFace token to config"""
        from logging_manager import log_info, log_error
        
        if not token or not token.strip():
            return {"success": False, "error": "Token cannot be empty"}
        
        token = token.strip()
        token_path = self.dirs["config"] / "huggingface_token.json"
        
        try:
            # Test the token by logging in
            login(token=token, add_to_git_credential=False)
            
            # Save to file
            with open(token_path, "w", encoding="utf-8") as f:
                json.dump({"token": token, "saved_at": datetime.now().isoformat()}, f, indent=2)
            
            log_info("✅ HuggingFace token saved successfully", category="auth")
            return {"success": True, "message": "Token saved and authenticated"}
        except Exception as e:
            log_error(f"Failed to save HuggingFace token: {str(e)}", category="auth")
            return {"success": False, "error": f"Invalid token: {str(e)}"}
    
    def get_hf_token_status(self) -> Dict[str, Any]:
        """Check if HuggingFace token is configured"""
        token_path = self.dirs["config"] / "huggingface_token.json"
        
        if not token_path.exists():
            return {"configured": False, "saved_at": None}
        
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "configured": True,
                    "saved_at": data.get("saved_at"),
                    "token_preview": data.get("token", "")[:8] + "..." if data.get("token") else None
                }
        except Exception:
            return {"configured": False, "saved_at": None}
    
    def clear_hf_token(self) -> Dict[str, Any]:
        """Remove stored HuggingFace token"""
        from logging_manager import log_info
        
        token_path = self.dirs["config"] / "huggingface_token.json"
        
        try:
            if token_path.exists():
                token_path.unlink()
            log_info("HuggingFace token cleared", category="auth")
            return {"success": True, "message": "Token removed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def download_model(self, model_id: str, progress_callback: Optional[ProgressCallback] = None) -> Dict[str, Any]:
        """
        Download a model from HuggingFace Hub
        
        Args:
            model_id: The internal model ID (not the HF ID)
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dict with download results
        """
        from logging_manager import log_info, log_error
        
        model = self.get_model_by_id(model_id)
        if not model:
            log_error(f"Model {model_id} not found in registry", category="model")
            raise ValueError(f"Model {model_id} not found in registry")
            
        # Get HuggingFace model ID
        hf_model_id = model["huggingface_id"]
        
        # Create a progress tracker
        progress = ModelDownloadProgress(model_id)
        self.active_downloads[model_id] = progress
        
        # Add the callback if provided
        if progress_callback:
            progress.add_callback(progress_callback)
        
        # Target directory for the model
        model_dir = self.dirs["models"] / model_id
        
        # Log the start of the download
        log_info(f"Starting download of {model['name']} from HuggingFace ({model['size_gb']} GB)", category="model")
        
        # Check disk space before downloading
        free_space_gb = shutil.disk_usage(self.dirs["models"]).free / (1024**3)
        required_space_gb = float(model["size_gb"]) * 1.2  # Add 20% margin
        
        if free_space_gb < required_space_gb:
            error_msg = f"Not enough disk space. Need {required_space_gb:.1f} GB but only {free_space_gb:.1f} GB available."
            log_error(error_msg, category="model")
            progress.fail(Exception(error_msg))
            return {"success": False, "error": error_msg}
        
        try:
            # Create a custom tqdm class that reports progress
            # We need to create a factory function that returns a class, not use partial
            def create_progress_tqdm(progress_tracker):
                """Factory function to create a tqdm class with bound progress tracker"""
                class ProgressTqdm(tqdm):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self._progress_tracker = progress_tracker
                        
                    def update(self, n=1):
                        super().update(n)
                        if self._progress_tracker and self.total:
                            self._progress_tracker.update(self.n, self.total)
                
                return ProgressTqdm
            
            # Start the download
            progress.status = "downloading"
            
            # Use snapshot_download with our custom tqdm class
            local_dir = snapshot_download(
                repo_id=hf_model_id,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
                resume_download=True,
                max_workers=4,
                tqdm_class=create_progress_tqdm(progress)
            )
            
            # Verify the model files
            if not self._verify_model(model_id, local_dir):
                progress.fail(Exception("Model download incomplete or files corrupted"))
                return {"success": False, "error": "Model download incomplete or files corrupted"}
            
            # Download completed successfully
            progress.complete()
            
            # Update the model status in the registry
            model["installed"] = True
            model["install_date"] = datetime.now().isoformat()
            model["local_path"] = str(model_dir)
            self.save_model_registry()
            
            # Create default configuration
            self._create_default_config(model_id)
            
            log_info(f"✅ Model {model['name']} downloaded successfully to {local_dir}", category="model")
            
            return {
                "success": True,
                "model_id": model_id,
                "local_path": local_dir,
                "elapsed_time": (progress.completion_time - progress.start_time).total_seconds()
            }
            
        except Exception as e:
            error_msg = f"Error downloading model {model_id}: {str(e)}"
            log_error(error_msg, category="model")
            progress.fail(e)
            return {"success": False, "error": error_msg}
        
        finally:
            # Clean up
            if model_id in self.active_downloads:
                del self.active_downloads[model_id]
    
    def _verify_model(self, model_id: str, model_path: str) -> bool:
        """Verify downloaded model is complete"""
        try:
            # Check for essential files
            model_dir = Path(model_path)
            
            # Most HuggingFace models have at least a config.json file
            if not (model_dir / "config.json").exists():
                return False
                
            # Check for model weights
            has_weights = False
            for weights_file in ["pytorch_model.bin", "model.safetensors", "pytorch_model.bin.index.json"]:
                if list(model_dir.glob(f"**/{weights_file}")):
                    has_weights = True
                    break
                    
            if not has_weights:
                return False
                
            return True
        except Exception:
            return False
    
    def get_download_progress(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get the current download progress for a model"""
        if model_id not in self.active_downloads:
            return None
            
        progress = self.active_downloads[model_id]
        return {
            "model_id": model_id,
            "status": progress.status,
            "downloaded_bytes": progress.downloaded_bytes,
            "total_bytes": progress.total_bytes,
            "progress_percent": progress.progress_percent,
            "error": progress.error,
            "elapsed_seconds": (datetime.now() - progress.start_time).total_seconds()
        }
    
    def delete_model(self, model_id: str) -> Dict[str, Any]:
        """Delete a downloaded model to free up disk space"""
        from logging_manager import log_info, log_error
        
        model = self.get_model_by_id(model_id)
        if not model:
            return {"success": False, "error": f"Model {model_id} not found in registry"}
            
        model_dir = self.dirs["models"] / model_id
        if not model_dir.exists():
            return {"success": False, "error": f"Model directory not found: {model_dir}"}
        
        try:
            # Delete the model directory
            log_info(f"Deleting model {model['name']} from {model_dir}", category="model")
            shutil.rmtree(model_dir)
            
            # Update the model status in the registry
            model["installed"] = False
            model["install_date"] = None
            model["local_path"] = None
            self.save_model_registry()
            
            # Delete configuration
            config_path = self.dirs["config"] / f"{model_id}_config.json"
            if config_path.exists():
                config_path.unlink()
                model["configured"] = False
            
            log_info(f"✅ Model {model['name']} deleted successfully", category="model")
            return {"success": True, "model_id": model_id}
            
        except Exception as e:
            error_msg = f"Error deleting model {model_id}: {str(e)}"
            log_error(error_msg, category="model")
            return {"success": False, "error": error_msg}
    
    def _create_default_config(self, model_id: str) -> bool:
        """Create a default configuration for a model"""
        from logging_manager import log_info, log_error
        
        model = self.get_model_by_id(model_id)
        if not model:
            return False
            
        # Default configuration based on model size
        params_b = float(model["parameters"].replace("B", ""))
        
        # Adjust defaults based on model size
        if params_b <= 3:
            max_tokens = 4096
            context_window = 4096
        elif params_b <= 8:
            max_tokens = 6144
            context_window = 8192
        elif params_b <= 20:
            max_tokens = 8192
            context_window = 16384
        else:
            max_tokens = 8192
            context_window = 32768
        
        config = {
            "model_id": model_id,
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "response_style": 5,
            "creativity": 5,
            "context_window": context_window,
            "last_updated": datetime.now().isoformat()
        }
        
        # Save the configuration
        config_path = self.dirs["config"] / f"{model_id}_config.json"
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            
            # Update the model status
            model["configured"] = True
            self.save_model_registry()
            
            log_info(f"Created default configuration for {model['name']}", category="model")
            return True
        except Exception as e:
            log_error(f"Error creating default configuration for {model_id}: {e}", category="model")
            return False
    
    def get_model_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get the configuration for a model"""
        config_path = self.dirs["config"] / f"{model_id}_config.json"
        if not config_path.exists():
            return None
            
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    
    def save_model_config(self, model_id: str, config: Dict[str, Any]) -> bool:
        """Save configuration for a model"""
        from logging_manager import log_info, log_error
        
        model = self.get_model_by_id(model_id)
        if not model:
            return False
            
        # Update timestamp
        config["last_updated"] = datetime.now().isoformat()
        
        # Save the configuration
        config_path = self.dirs["config"] / f"{model_id}_config.json"
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            
            # Update the model status
            model["configured"] = True
            self.save_model_registry()
            
            log_info(f"✓ Configuration saved for {model['name']}", category="model")
            return True
        except Exception as e:
            log_error(f"Error saving configuration for {model_id}: {e}", category="model")
            return False

# Singleton instance
model_manager = ModelManager()

