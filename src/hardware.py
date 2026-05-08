import shutil
import subprocess

def get_free_vram_mb() -> int | None:
    """Uses nvidia-smi to query the free VRAM in MB. Returns None if nvidia-smi is unavailable."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        # Query free memory directly
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True
        )
        # Assuming single GPU or we just take the first one
        free_vram = int(result.stdout.strip().split('\n')[0])
        return free_vram
    except Exception:
        return None
