"""
Hardware Detection System
Auto-detects GPU/CPU and selects optimal inference backend
"""

import platform
import subprocess
import logging
from typing import Dict, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

class GPUVendor(Enum):
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    APPLE = "apple"
    NONE = "none"

class InferenceBackend(Enum):
    PYTORCH_CUDA = "pytorch_cuda"      # NVIDIA GPU (best)
    ONNX_CUDA = "onnx_cuda"            # NVIDIA GPU (faster)
    ONNX_DIRECTML = "onnx_directml"    # AMD/Intel GPU (Windows)
    ONNX_ROCM = "onnx_rocm"            # AMD GPU (Linux)
    PYTORCH_MPS = "pytorch_mps"        # Apple Silicon
    PYTORCH_CPU = "pytorch_cpu"        # CPU fallback
    ONNX_CPU = "onnx_cpu"              # CPU fallback (faster)

class HardwareInfo:
    """System hardware information"""
    
    def __init__(self):
        self.gpu_vendor: GPUVendor = GPUVendor.NONE
        self.gpu_name: Optional[str] = None
        self.gpu_memory_mb: int = 0
        self.cpu_name: str = platform.processor()
        self.ram_gb: int = 0
        self.os: str = platform.system()
        self.has_cuda: bool = False
        self.has_rocm: bool = False
        self.has_mps: bool = False
        self.recommended_backend: InferenceBackend = InferenceBackend.PYTORCH_CPU
        
    def to_dict(self) -> Dict:
        return {
            "gpu_vendor": self.gpu_vendor.value,
            "gpu_name": self.gpu_name,
            "gpu_memory_mb": self.gpu_memory_mb,
            "cpu_name": self.cpu_name,
            "ram_gb": self.ram_gb,
            "os": self.os,
            "has_cuda": self.has_cuda,
            "has_rocm": self.has_rocm,
            "has_mps": self.has_mps,
            "recommended_backend": self.recommended_backend.value,
        }

class HardwareDetector:
    """Detects system hardware and recommends optimal inference backend"""
    
    @staticmethod
    def detect() -> HardwareInfo:
        """Detect hardware and return info with recommendation"""
        info = HardwareInfo()
        
        # Detect GPU
        info.gpu_vendor, info.gpu_name, info.gpu_memory_mb = HardwareDetector._detect_gpu()
        
        # Detect CUDA availability
        info.has_cuda = HardwareDetector._check_cuda()
        
        # Detect ROCm (AMD on Linux)
        info.has_rocm = HardwareDetector._check_rocm()
        
        # Detect MPS (Apple Silicon)
        info.has_mps = HardwareDetector._check_mps()
        
        # Detect RAM
        info.ram_gb = HardwareDetector._get_ram_gb()
        
        # Recommend backend based on hardware
        info.recommended_backend = HardwareDetector._recommend_backend(info)
        
        # Log detection results
        logger.info(f"Hardware Detection Results:")
        logger.info(f"  GPU: {info.gpu_vendor.value} - {info.gpu_name or 'None'}")
        logger.info(f"  GPU Memory: {info.gpu_memory_mb} MB")
        logger.info(f"  CPU: {info.cpu_name}")
        logger.info(f"  RAM: {info.ram_gb} GB")
        logger.info(f"  OS: {info.os}")
        logger.info(f"  CUDA: {info.has_cuda}")
        logger.info(f"  ROCm: {info.has_rocm}")
        logger.info(f"  MPS: {info.has_mps}")
        logger.info(f"  Recommended Backend: {info.recommended_backend.value}")
        
        return info
    
    @staticmethod
    def _detect_gpu() -> tuple[GPUVendor, Optional[str], int]:
        """Detect GPU vendor, name, and memory"""
        
        # Try NVIDIA first (most common for AI)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    parts = output.split(',')
                    gpu_name = parts[0].strip()
                    gpu_memory = int(float(parts[1].strip()))
                    return GPUVendor.NVIDIA, gpu_name, gpu_memory
        except Exception as e:
            logger.debug(f"NVIDIA detection failed: {e}")
        
        # Try AMD on Windows (uses DirectML)
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for line in lines:
                        line = line.strip()
                        if line and ('AMD' in line.upper() or 'Radeon' in line):
                            parts = line.rsplit(None, 1)
                            if len(parts) == 2:
                                gpu_name = parts[0].strip()
                                gpu_memory = int(parts[1]) // (1024 * 1024)  # bytes to MB
                                return GPUVendor.AMD, gpu_name, gpu_memory
                        elif line and 'Intel' in line and ('Arc' in line or 'Iris' in line):
                            parts = line.rsplit(None, 1)
                            if len(parts) == 2:
                                gpu_name = parts[0].strip()
                                gpu_memory = int(parts[1]) // (1024 * 1024)
                                return GPUVendor.INTEL, gpu_name, gpu_memory
            except Exception as e:
                logger.debug(f"Windows GPU detection failed: {e}")
        
        # Try AMD on Linux (ROCm)
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return GPUVendor.AMD, result.stdout.strip(), 0
        except Exception as e:
            logger.debug(f"ROCm detection failed: {e}")
        
        # Check for Apple Silicon
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            return GPUVendor.APPLE, "Apple Silicon", 0
        
        return GPUVendor.NONE, None, 0
    
    @staticmethod
    def _check_cuda() -> bool:
        """Check if CUDA is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except:
            return False
    
    @staticmethod
    def _check_rocm() -> bool:
        """Check if ROCm is available"""
        try:
            import torch
            return torch.version.hip is not None
        except:
            return False
    
    @staticmethod
    def _check_mps() -> bool:
        """Check if Apple MPS is available"""
        try:
            import torch
            return hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        except:
            return False
    
    @staticmethod
    def _get_ram_gb() -> int:
        """Get system RAM in GB"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["wmic", "computersystem", "get", "TotalPhysicalMemory"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        ram_bytes = int(lines[1].strip())
                        return ram_bytes // (1024 ** 3)
            else:
                # Linux/Mac
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            ram_kb = int(line.split()[1])
                            return ram_kb // (1024 ** 2)
        except Exception as e:
            logger.debug(f"RAM detection failed: {e}")
        
        return 8  # Default assumption
    
    @staticmethod
    def _recommend_backend(info: HardwareInfo) -> InferenceBackend:
        """Recommend optimal inference backend based on hardware"""
        
        # NVIDIA GPU - best support
        if info.gpu_vendor == GPUVendor.NVIDIA:
            if info.has_cuda:
                # ONNX CUDA is 1.5-2x faster than PyTorch CUDA
                # Recommend ONNX for best performance
                return InferenceBackend.ONNX_CUDA
            else:
                logger.warning("NVIDIA GPU detected but CUDA not available")
                return InferenceBackend.PYTORCH_CPU
        
        # AMD GPU
        elif info.gpu_vendor == GPUVendor.AMD:
            if info.os == "Windows":
                # DirectML works on Windows for AMD
                return InferenceBackend.ONNX_DIRECTML
            elif info.has_rocm:
                # ROCm on Linux
                return InferenceBackend.ONNX_ROCM
            else:
                logger.warning("AMD GPU detected but no ROCm/DirectML support")
                return InferenceBackend.PYTORCH_CPU
        
        # Intel GPU
        elif info.gpu_vendor == GPUVendor.INTEL:
            if info.os == "Windows":
                # DirectML works for Intel Arc/Iris on Windows
                return InferenceBackend.ONNX_DIRECTML
            else:
                return InferenceBackend.PYTORCH_CPU
        
        # Apple Silicon
        elif info.gpu_vendor == GPUVendor.APPLE:
            if info.has_mps:
                return InferenceBackend.PYTORCH_MPS
            else:
                return InferenceBackend.PYTORCH_CPU
        
        # CPU only
        else:
            # ONNX CPU is generally faster than PyTorch CPU
            if info.ram_gb >= 16:
                return InferenceBackend.ONNX_CPU
            else:
                return InferenceBackend.PYTORCH_CPU


# Global hardware info cache
_hardware_info: Optional[HardwareInfo] = None

def get_hardware_info(force_redetect: bool = False) -> HardwareInfo:
    """Get cached hardware info or detect if not cached"""
    global _hardware_info
    if _hardware_info is None or force_redetect:
        _hardware_info = HardwareDetector.detect()
    return _hardware_info

