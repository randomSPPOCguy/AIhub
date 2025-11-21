"""Python bridge for Project Frank.

This module is embedded into the Rust binary via PyO3. It provides the public
functions invoked from Rust and orchestrates enrichment + LLM calls using
a local Phi-3 model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    print("⚠️  transformers not installed. Using placeholder responses.")

from enrichment_pipeline import EnrichmentPipeline

_pipeline = EnrichmentPipeline()

# Global model and tokenizer (loaded once)
_model = None
_tokenizer = None


def _initialize_model():
    """Initialize the Phi-3 model and tokenizer (lazy loading)."""
    global _model, _tokenizer

    if _model is not None:
        return  # Already initialized

    if not HAS_TRANSFORMERS:
        print("❌ Transformers not available, using fallback")
        return

    try:
        print("🔄 Loading Phi-3 Mini model (this may take a minute on first run)...")

        # Load tokenizer and model
        _tokenizer = AutoTokenizer.from_pretrained(
            "microsoft/Phi-3-mini-4k-instruct",
            trust_remote_code=True
        )

        _model = AutoModelForCausalLM.from_pretrained(
            "microsoft/Phi-3-mini-4k-instruct",
            trust_remote_code=True,
            torch_dtype=torch.float16,  # Use FP16 for faster inference
            device_map="auto"  # Automatically use GPU if available
        )

        print("✅ Phi-3 model loaded successfully!")

    except Exception as e:
        print(f"❌ Error loading Phi-3 model: {e}")
        print("Using fallback placeholder responses")
        _model = None


def _generate_with_phi3(prompt: str, max_tokens: int = 512) -> str:
    """Generate text using the local Phi-3 model."""
    _initialize_model()

    if _model is None or _tokenizer is None:
        return "[Phi-3 model not available, using placeholder response]"

    try:
        # Format using Phi-3's chat template
        messages = [
            {"role": "user", "content": prompt}
        ]

        # Apply chat template
        inputs = _tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt"
        )

        # Move to same device as model
        device = next(_model.parameters()).device
        inputs = inputs.to(device)

        # Generate response
        with torch.no_grad():
            outputs = _model.generate(
                inputs,
                max_new_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                pad_token_id=_tokenizer.eos_token_id
            )

        # Decode and clean response
        response = _tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Remove the input prompt from response
        if prompt in response:
            response = response.split(prompt)[1].strip()

        # Remove any remaining template markers
        response = response.replace("<|assistant|>", "").strip()

        return response

    except Exception as e:
        return f"[Generation error: {str(e)}]"


@dataclass
class ResponseBundle:
    query: str
    enrichment: List[str]
    llm_response: str = ""

    def format(self) -> str:
        chunks = "\n".join(f"- {item}" for item in self.enrichment) or "No enrichment data."

        sections = [
            "=" * 60,
            "PROJECT FRANK - Phi-3 Response",
            "=" * 60,
            f"\nYour Query: {self.query}\n",
        ]

        if chunks != "No enrichment data.":
            sections.append(f"Enrichment Data:\n{chunks}\n")

        if self.llm_response:
            sections.append(f"AI Response:\n{self.llm_response}\n")

        sections.append("=" * 60)

        return "\n".join(sections)


def generate_response(query: str, enrichment_data: List[str]) -> str:
    """Generate a response using the local Phi-3 model with enrichment context."""

    # Build context from enrichment data
    context = ""
    if enrichment_data and enrichment_data != ["No enrichment data."]:
        context = "\n\nContext information:\n" + "\n".join(enrichment_data)

    # Create a prompt for Phi-3
    prompt = f"""You are a helpful AI assistant. Answer the following question based on the provided context.

Question: {query}{context}

Please provide a clear, concise, and helpful answer."""

    try:
        # Generate response using Phi-3
        llm_response = _generate_with_phi3(prompt, max_tokens=512)

        # Create response bundle
        bundle = ResponseBundle(
            query=query,
            enrichment=enrichment_data,
            llm_response=llm_response
        )

        return bundle.format()

    except Exception as e:
        # Fallback to placeholder if model fails
        print(f"Error generating LLM response: {e}")
        bundle = ResponseBundle(
            query=query,
            enrichment=enrichment_data,
            llm_response=f"[Model error: {str(e)}]"
        )
        return bundle.format()


def enrich_entity(entity_name: str, entity_type: str = "artist") -> str:
    """Return enrichment payload as a JSON string."""
    enriched = _pipeline.enrich(entity_name, entity_type)
    return json.dumps(enriched, ensure_ascii=False)
