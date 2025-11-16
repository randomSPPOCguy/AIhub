export const providerSuggestions = {
  openai: {
    models: [
      { remoteModel: "gpt-4o", description: "Flagship multimodal reasoning (higher cost)." },
      { remoteModel: "gpt-4o-mini", description: "Fast default assistant (current selection)." },
      { remoteModel: "gpt-4.1", description: "Production GPT-4 family with JSON output." },
      { remoteModel: "o1-mini", description: "Reasoning-focused small-model experiments." },
      { remoteModel: "gpt-4o-audio-preview", description: "Audio + chat preview build." }
    ],
    localNote:
      "OpenAI does not distribute ONNX/GGUF weights. Use Microsoft Phi-3 or Qwen downloads for NVIDIA CUDA deployment."
  },
  anthropic: {
    models: [
      { remoteModel: "claude-3-opus-20240229", description: "Most capable Claude 3 (Opus)." },
      { remoteModel: "claude-3-sonnet-20240229", description: "Balanced Claude 3 (Sonnet)." },
      { remoteModel: "claude-3-haiku-20240307", description: "Fast Claude 3 (Haiku)." }
    ]
  },
  gemini: {
    models: [
      { remoteModel: "gemini-1.5-pro", description: "Latest Gemini 1.5 Pro." },
      { remoteModel: "gemini-1.5-flash", description: "Streaming-optimized Flash variant." },
      { remoteModel: "gemini-2.0-flash-exp", description: "Experimental 2.0 Flash (default)." }
    ]
  },
  huggingface: {
    models: [
      { remoteModel: "mistralai/Mixtral-8x7B-Instruct-v0.1", description: "Mixtral MoE instruct." },
      { remoteModel: "meta-llama/Llama-3.1-8B-Instruct", description: "Llama 3.1 instruct." },
      { remoteModel: "google/gemma-2-9b-it", description: "Gemma 2 instruction-tuned." }
    ]
  }
};
