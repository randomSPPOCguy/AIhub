# 🤖 Using Local Models with AI Hub Backend

Your backend supports **ANY HuggingFace model** running locally - no API keys needed!

## 🚀 Quick Start

### 1. Install Local Model Dependencies

```bash
cd backend
pip install transformers torch accelerate --break-system-packages
```

**With GPU (CUDA):**
```bash
pip install transformers torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --break-system-packages
pip install accelerate --break-system-packages
```

### 2. Test Local Models

```bash
# Start the backend
python -m uvicorn main:app --reload

# In another terminal, test it
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "local",
    "model": "microsoft/Phi-3-mini-4k-instruct",
    "message": "Hello! Can you explain quantum computing in simple terms?",
    "conversation_id": "test-local"
  }'
```

## 📦 Supported Models

Your backend can run **ANY** HuggingFace model! Here are some popular ones:

### Small & Fast (Good for CPU)
- `microsoft/Phi-3-mini-4k-instruct` - 3.8B params ⭐ Default
- `Qwen/Qwen2.5-3B-Instruct` - 3B params, very capable
- `stabilityai/stablelm-2-1_6b-chat` - 1.6B params, ultra-fast

### Medium (Better with GPU)
- `microsoft/Phi-3-mini-128k-instruct` - 3.8B params, huge context
- `mistralai/Mistral-7B-Instruct-v0.3` - 7B params, excellent
- `meta-llama/Llama-3.2-8B-Instruct` - 8B params (requires approval)

### Large (Requires GPU + lots of RAM)
- `meta-llama/Llama-3.1-70B-Instruct` - 70B params
- `mistralai/Mixtral-8x7B-Instruct-v0.1` - 47B params
- `Qwen/Qwen2.5-72B-Instruct` - 72B params

## 🎯 How It Works

### API Endpoint
```bash
POST /chat
```

### Request Body
```json
{
  "provider": "local",
  "model": "microsoft/Phi-3-mini-4k-instruct",
  "message": "Your question here",
  "conversation_id": "your-conv-id",
  "stream": false
}
```

### Example: Chat with Local Phi-3
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "local",
    "message": "Write a Python function to calculate fibonacci numbers",
    "conversation_id": "coding-help"
  }'
```

## 🔧 Configuration

### Change Default Model

Edit `backend/providers/local/local_model_provider.py`:

```python
def __init__(self, model_name: Optional[str] = None):
    # Change this line:
    self.model_name = model_name or "microsoft/Phi-3-mini-4k-instruct"
    # To your preferred model:
    self.model_name = model_name or "Qwen/Qwen2.5-3B-Instruct"
```

### Or specify in API call:
```json
{
  "provider": "local",
  "model": "Qwen/Qwen2.5-3B-Instruct",
  "message": "Hello!"
}
```

## 💻 System Requirements

### CPU Only
- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 5-10GB per model
- **Speed**: Slow but works!
- **Best models**: Phi-3-mini, Qwen2.5-3B, StableLM-2

### With GPU (Recommended)
- **VRAM**: 8GB+ for 7B models, 16GB+ for 13B models
- **RAM**: 16GB system RAM
- **CUDA**: NVIDIA GPU with CUDA support
- **Speed**: Much faster! 🚀

### Check Your Setup
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
```

## 🧪 Testing Script

Create `test_local_model.py`:

```python
#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"

def test_local_model(model_name=None, message="Hello! Tell me a fun fact about space."):
    """Test a local model"""
    
    payload = {
        "provider": "local",
        "message": message,
        "conversation_id": "test-local",
        "stream": False
    }
    
    if model_name:
        payload["model"] = model_name
    
    print(f"\n{'='*60}")
    print(f"Testing Local Model: {model_name or 'default (Phi-3)'}")
    print(f"{'='*60}\n")
    print(f"Message: {message}\n")
    print("Waiting for response...\n")
    
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data.get('response', 'N/A')}\n")
        print(f"Model: {data.get('model', 'N/A')}")
        print(f"Provider: {data.get('provider', 'N/A')}")
    else:
        print(f"Error {response.status_code}: {response.text}")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    # Test default model
    test_local_model()
    
    # Test specific model (uncomment to try)
    # test_local_model("Qwen/Qwen2.5-3B-Instruct", "Explain AI in simple terms")
```

Run it:
```bash
python test_local_model.py
```

## ⚡ Performance Tips

### 1. Use GPU if available
Models run **10-100x faster** on GPU!

### 2. Start with small models
- Try Phi-3-mini or Qwen2.5-3B first
- They're fast and surprisingly capable

### 3. Quantization (advanced)
Use quantized models for faster inference:
```python
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(load_in_8bit=True)
model = AutoModelForCausalLM.from_pretrained(
    "microsoft/Phi-3-mini-4k-instruct",
    quantization_config=quantization_config,
    device_map="auto"
)
```

### 4. Batch processing
Process multiple requests together when possible

### 5. Model caching
Models are cached after first load - subsequent uses are instant!

## 🐛 Troubleshooting

### "transformers library not installed"
```bash
pip install transformers torch accelerate --break-system-packages
```

### "CUDA out of memory"
- Use a smaller model
- Reduce `max_tokens` in your request
- Enable 8-bit quantization
- Close other GPU applications

### "Model not found"
- Check the model name on HuggingFace
- Some models require approval (like Llama)
- Make sure you have internet for first download

### Slow CPU inference
- This is normal for CPU-only
- Use smaller models (Phi-3-mini, Qwen2.5-3B)
- Consider cloud providers for larger models
- Or get a GPU! 🎮

## 📊 Model Comparison

| Model | Size | Speed (CPU) | Quality | Context | Best For |
|-------|------|-------------|---------|---------|----------|
| Phi-3-mini-4k | 3.8B | Fast | Good | 4K | General chat, CPU |
| Phi-3-mini-128k | 3.8B | Fast | Good | 128K | Long docs, CPU |
| Qwen2.5-3B | 3B | Fastest | Great | 32K | Coding, fast replies |
| Mistral-7B | 7B | Medium | Excellent | 32K | General purpose |
| Llama-3.2-8B | 8B | Medium | Excellent | 128K | High quality |

## 🎓 Advanced: Custom Models

### Use ANY HuggingFace Model

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "local",
    "model": "your-username/your-model-name",
    "message": "Hello!",
    "conversation_id": "test"
  }'
```

### Fine-tuned Models
Upload your fine-tuned model to HuggingFace, then use it:
```json
{
  "provider": "local",
  "model": "your-username/your-finetuned-model",
  "message": "Query for your specialized model"
}
```

## 🔐 Privacy Benefits

Local models mean:
- ✅ **100% Private** - Nothing leaves your machine
- ✅ **No API costs** - Free forever
- ✅ **Offline capable** - Works without internet (after download)
- ✅ **Full control** - Your hardware, your rules
- ✅ **No rate limits** - Use as much as you want

## 💡 Example Use Cases

### Code Assistant
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "local",
    "model": "Qwen/Qwen2.5-3B-Instruct",
    "message": "Write a Python function to sort a dictionary by values"
  }'
```

### Creative Writing
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "local",
    "model": "microsoft/Phi-3-mini-4k-instruct",
    "message": "Write a short sci-fi story about AI"
  }'
```

### Data Analysis
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "local",
    "message": "Explain this SQL query: SELECT * FROM users WHERE age > 18"
  }'
```

## 🎉 Summary

Your AI Hub backend supports:
- ✅ **ANY HuggingFace model**
- ✅ **CPU and GPU support**
- ✅ **Automatic model loading**
- ✅ **Progress tracking**
- ✅ **No API keys needed**
- ✅ **100% private**

**Just install transformers and start using local AI!** 🚀

---

## 🔗 Resources

- **HuggingFace Models**: https://huggingface.co/models
- **Transformers Docs**: https://huggingface.co/docs/transformers
- **PyTorch**: https://pytorch.org/
- **CUDA Setup**: https://pytorch.org/get-started/locally/
