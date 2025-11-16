import os
import sys
import glob
import logging
from pathlib import Path
from typing import List, Optional, Dict

import fastapi
from fastapi import HTTPException
from pydantic import BaseModel
import uvicorn

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import onnxruntime_genai as ort_genai
except ImportError as exc:
    raise RuntimeError(
        "onnxruntime-genai is required. Install with 'pip install onnxruntime-genai'."
    ) from exc

try:
    import onnxruntime as ort
except ImportError:
    ort = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if load_dotenv:
    env_path = PROJECT_ROOT / "config.env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

logger = logging.getLogger("python_ai")
logging.basicConfig(level=logging.INFO)

MODEL_ROOT = os.getenv("PYTHON_MODEL_ROOT", os.path.join(os.getcwd(), "models", "downloads"))
DEFAULT_PORT = int(os.getenv("PYTHON_AI_PORT", "8000"))
HOST = os.getenv("PYTHON_AI_HOST", "0.0.0.0")

app = fastapi.FastAPI(title="AI Hub ONNX Runtime GenAI service")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    modelId: Optional[str] = None
    modelPath: Optional[str] = None
    messages: List[Message]
    temperature: Optional[float] = 0.7
    maxTokens: Optional[int] = 1024


class RegisterRequest(BaseModel):
    id: str
    name: Optional[str] = None
    path: Optional[str] = None
    size: Optional[int] = None


class ModelBundle:
    def __init__(self, model_path: str, model_id: Optional[str]):
        self.path = model_path
        self.model_id = model_id or os.path.basename(model_path.rstrip(os.sep))
        logger.info("Loading ONNX GenAI model %s from %s", self.model_id, model_path)
        self.model = ort_genai.Model(model_path)
        self.tokenizer = ort_genai.Tokenizer(self.model)


MODEL_CACHE: Dict[str, ModelBundle] = {}


def resolve_model_path(model_path: Optional[str], model_id: Optional[str]) -> str:
    if model_path:
        expanded = os.path.abspath(model_path)
        if not os.path.exists(expanded):
            raise HTTPException(status_code=400, detail=f"modelPath {expanded} not found")
        return expanded
    if not model_id:
        raise HTTPException(status_code=400, detail="modelId or modelPath is required")
    root = os.path.abspath(os.getenv("PYTHON_MODEL_ROOT", MODEL_ROOT))
    candidate_dir = os.path.join(root, model_id)
    if os.path.isdir(candidate_dir):
        # Look for ONNX assets under this directory.
        onnx_files = glob.glob(os.path.join(candidate_dir, "**", "*.onnx"), recursive=True)
        if onnx_files:
            return os.path.dirname(onnx_files[0])
        return candidate_dir
    # Maybe the ID is already a file-like path
    if os.path.exists(model_id):
        return os.path.abspath(model_id)
    raise HTTPException(status_code=404, detail=f"Unable to resolve model path for {model_id}")


def get_or_load_model(model_path: str, model_id: Optional[str]) -> ModelBundle:
    key = model_path
    bundle = MODEL_CACHE.get(key)
    if bundle:
        return bundle
    try:
        bundle = ModelBundle(model_path, model_id)
    except Exception as exc:
        logger.exception("Failed to load model from %s", model_path)
        raise HTTPException(status_code=500, detail=f"Failed to load model: {exc}") from exc
    MODEL_CACHE[key] = bundle
    return bundle


def build_prompt(messages: List[Message]) -> str:
    if not messages:
        return ""
    prompt_segments = []
    for msg in messages:
        role = msg.role.lower()
        content = msg.content or ""
        if role == "system":
            prompt_segments.append(f"<|system|>\n{content}\n<|end|>")
        elif role == "assistant":
            prompt_segments.append(f"<|assistant|>\n{content}\n<|end|>")
        else:
            # treat as user
            prompt_segments.append(f"<|user|>\n{content}\n<|end|>")
    if messages[-1].role.lower() != "assistant":
        prompt_segments.append("<|assistant|>")
    return "\n".join(prompt_segments)


def run_generation(bundle: ModelBundle, prompt: str, temperature: float, max_tokens: int):
    tokenizer = bundle.tokenizer
    model = bundle.model
    input_tokens = tokenizer.encode(prompt)
    params = ort_genai.GeneratorParams(model)
    # Check input token length
    input_token_count = len(input_tokens)
    if input_token_count > 3500:
        logger.warning("Input tokens (%d) approaching model context limit", input_token_count)
        # Truncate input tokens if too long
        input_tokens = input_tokens[-3500:]

    # Set generation parameters
    params.set_search_options(max_length=input_token_count + max_tokens, temperature=temperature)
    generator = ort_genai.Generator(model, params)
    generator.append_tokens(input_tokens)
    generated_tokens = []
    while not generator.is_done():
        generator.generate_next_token()
        next_tokens = generator.get_next_tokens()
        if next_tokens:
            generated_tokens.append(next_tokens[0])
    text = tokenizer.decode(generated_tokens)
    return {
        "text": text,
        "usage": {
            "prompt_tokens": len(input_tokens),
            "completion_tokens": len(generated_tokens),
            "total_tokens": len(input_tokens) + len(generated_tokens)
        }
    }


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages array is required")
    model_path = resolve_model_path(req.modelPath, req.modelId)
    bundle = get_or_load_model(model_path, req.modelId)
    prompt = build_prompt(req.messages)
    try:
        result = run_generation(
            bundle,
            prompt,
            temperature=req.temperature or 0.7,
            max_tokens=req.maxTokens or 1024
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Generation failed for model %s", bundle.model_id)
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc
    result["raw"] = {"model_path": bundle.path, "model_id": bundle.model_id}
    return result


@app.get("/api/health")
async def health():
    providers = []
    has_cuda = False
    if ort:
        providers = ort.get_available_providers()
        has_cuda = any("CUDA" in provider.upper() for provider in providers)
    return {
        "status": "ok",
        "has_cuda": has_cuda,
        "available_providers": providers,
        "loaded_models": [
            {"id": bundle.model_id, "path": path, "device": getattr(bundle.model, "device_type", "unknown")}
            for path, bundle in MODEL_CACHE.items()
        ]
    }


@app.get("/api/models")
async def list_models():
  return {
    "models": [
      {"id": bundle.model_id, "path": path, "device": getattr(bundle.model, "device_type", "unknown")}
      for path, bundle in MODEL_CACHE.items()
    ]
  }


@app.get("/api/local_models")
async def list_models_alias():
  return await list_models()


@app.post("/api/local_chat")
async def local_chat_alias(req: ChatRequest):
  return await chat_endpoint(req)


@app.post("/api/models/register")
async def register_model(req: RegisterRequest):
  # For now we just acknowledge the registration so the Node side can track downloads.
  logger.info("Registering model %s (path=%s size=%s)", req.id, req.path, req.size)
  return {"status": "ok", "id": req.id}


def main():
  uvicorn.run(app, host=HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    main()
