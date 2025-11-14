"""
ONNX Runtime Engine
===================
Lightweight runtime adapter for ONNX Runtime with CUDA/CPU/TensorRT support.
No model downloads - only loads models if a local path is configured.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import onnxruntime as ort  # ORT base; EPs come from onnxruntime-gpu
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ort = None

# GenAI is installed, but we won't load any model here:
# import onnxruntime_genai as og


def available_providers() -> List[str]:
    """Return providers compiled into this ORT build (e.g., CUDA/TensorRT/CPU)."""
    if not ONNX_AVAILABLE:
        return []
    return ort.get_available_providers()


def _providers_from_env(provider_config: str, enable_trt: bool = False) -> List[str]:
    """
    Map ONNX_EXECUTION_PROVIDER into an ordered providers list for ORT.
    
    Examples:
    - 'cuda' -> ['CUDAExecutionProvider', 'CPUExecutionProvider']
    - 'cpu' -> ['CPUExecutionProvider']
    - 'tensorrt,cuda' -> ['TensorrtExecutionProvider','CUDAExecutionProvider','CPUExecutionProvider']
    
    Args:
        provider_config: Comma-separated provider list (e.g., "cuda", "tensorrt,cuda", "cpu")
        enable_trt: If True and "tensorrt" not in config, prepend TensorRT EP
    
    Returns:
        Ordered list of execution provider names
    """
    raw = (provider_config or "cuda").lower().strip()
    
    def map_one(tok: str) -> List[str]:
        if tok == "cuda":
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if tok == "tensorrt":
            return ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
        if tok == "cpu":
            return ["CPUExecutionProvider"]
        return []
    
    # Allow comma-separated ordering, then de-dupe
    order: List[str] = []
    for part in (p.strip() for p in raw.split(",")):
        for ep in map_one(part):
            if ep not in order:
                order.append(ep)
    
    # If TensorRT is explicitly enabled but not in config, prepend it
    if enable_trt and "TensorrtExecutionProvider" not in order:
        # Insert TensorRT at the beginning, but keep CPU at the end
        if "CPUExecutionProvider" in order:
            order.remove("CPUExecutionProvider")
        order.insert(0, "TensorrtExecutionProvider")
        order.append("CPUExecutionProvider")
    
    return order or ["CPUExecutionProvider"]


def build_session_if_configured(
    model_path: Optional[str],
    provider_config: str = "cuda",
    enable_trt: bool = False
) -> Optional[ort.InferenceSession]:
    """
    Build an ORT InferenceSession if `model_path` exists; else return None.
    Does not download models. Keeps provider order from config.
    
    Args:
        model_path: Path to ONNX model file (or directory containing model.onnx)
        provider_config: Execution provider configuration string
        enable_trt: Enable TensorRT execution provider
    
    Returns:
        InferenceSession if model exists, None otherwise
    """
    if not ONNX_AVAILABLE:
        return None
    
    if not model_path:
        return None
    
    p = Path(model_path)
    
    # If path is a directory, look for any .onnx file inside
    if p.is_dir():
        onnx_files = list(p.glob("*.onnx"))
        if not onnx_files:
            return None
        # Use the first .onnx file found
        p = onnx_files[0]
    
    if not p.exists():
        return None
    
    providers = _providers_from_env(provider_config, enable_trt)
    
    # Optional: tune CUDA EP via session options (examples only; safe defaults)
    so = ort.SessionOptions()
    # so.add_session_config_entry("session.set_denormal_as_zero", "1")
    # so.add_session_config_entry("session.use_deterministic_compute", "0")
    
    try:
        sess = ort.InferenceSession(str(p), sess_options=so, providers=providers)
        return sess
    except Exception as e:
        # Log error but don't crash
        print(f"⚠️ Failed to create ONNX session: {e}")
        return None


def status(
    model_dir_env: Optional[str],
    provider_config: str = "cuda",
    enable_trt: bool = False
) -> Dict[str, Any]:
    """
    Get ONNX Runtime status information.
    
    Args:
        model_dir_env: Path to model directory from environment
        provider_config: Execution provider configuration
        enable_trt: TensorRT enabled flag
    
    Returns:
        Dictionary with status information
    """
    if not ONNX_AVAILABLE:
        return {
            "onnx_available": False,
            "error": "ONNX Runtime not installed",
            "available_providers": [],
            "requested_providers": [],
            "model_dir_configured": False,
            "model_dir": "",
        }
    
    avail = available_providers()
    prov = _providers_from_env(provider_config, enable_trt)
    model_dir = (model_dir_env or "").strip()
    has_model_dir = bool(model_dir) and Path(model_dir).exists()
    
    # Check if requested providers are available
    missing_providers = [p for p in prov if p not in avail]
    
    return {
        "onnx_available": True,
        "available_providers": avail,
        "requested_providers": prov,
        "missing_providers": missing_providers,
        "model_dir_configured": has_model_dir,
        "model_dir": model_dir if has_model_dir else "",
        "warnings": _get_warnings(avail, prov, missing_providers),
    }


def _get_warnings(
    available: List[str],
    requested: List[str],
    missing: List[str]
) -> List[str]:
    """Generate warning messages for ONNX configuration."""
    warnings = []
    
    if missing:
        warnings.append(
            f"Requested providers not available: {', '.join(missing)}. "
            f"Will fall back to available providers."
        )
    
    if "CUDAExecutionProvider" in requested and "CUDAExecutionProvider" not in available:
        warnings.append(
            "CUDA provider requested but not available. "
            "Ensure CUDA toolkit and cuDNN are installed and on PATH."
        )
    
    if "TensorrtExecutionProvider" in requested and "TensorrtExecutionProvider" not in available:
        warnings.append(
            "TensorRT provider requested but not available. "
            "Ensure TensorRT is installed for enhanced performance."
        )
    
    return warnings

