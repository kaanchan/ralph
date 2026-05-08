import json
from pathlib import Path

# Registry mapping model tags to their hardware profiles and capabilities.
MODELS = {
    "qwen25-coder-14b": {
        "supports_aider_diff": False,
        "base_vram_mb": 9500,          # Approx memory for Q4 quantized 14B weights
        "system_prompt": "local_system.txt",
        "optimal_temperature": 0.0
    },
    "default_local": {
        "supports_aider_diff": False,
        "base_vram_mb": 4000,
        "system_prompt": "local_system.txt",
        "optimal_temperature": 0.0
    }
}

def get_model_profile(model_name: str) -> dict:
    name = model_name.removeprefix("ollama/")
    return MODELS.get(name, MODELS["default_local"])

def calculate_safe_ctx(model_name: str, free_vram_mb: int | None) -> int:
    """Calculate the maximum safe context window (num_ctx) to prevent VRAM exhaustion.
    
    If we can't determine VRAM, we default to 4096 to be safe.
    """
    if free_vram_mb is None:
        return 4096 # Conservative default
        
    profile = get_model_profile(model_name)
    base_vram = profile["base_vram_mb"]
    
    if free_vram_mb < base_vram:
        return 2048 
        
    available_for_ctx = free_vram_mb - base_vram
    
    # Rough heuristic: ~125MB per 1024 tokens for 14B models.
    safe_tokens = int((available_for_ctx / 125.0) * 1024)
    
    # Cap between 2048 and 32768
    safe_tokens = max(2048, min(32768, safe_tokens))
    return safe_tokens
