"""Script to set up Ollama models."""

import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import get_settings


def check_ollama_installed() -> bool:
    """Check if Ollama is installed."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def pull_model(model_name: str) -> bool:
    """Pull an Ollama model."""
    try:
        print(f"📥 Pulling model: {model_name}")
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=False,
            timeout=600,  # 10 minute timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout pulling model: {model_name}")
        return False
    except Exception as e:
        print(f"❌ Error pulling model: {e}")
        return False


def main():
    """Main setup function."""
    if not check_ollama_installed():
        print("❌ Ollama is not installed. Please install it first:")
        print("   curl -fsSL https://ollama.ai/install.sh | sh")
        sys.exit(1)

    settings = get_settings()
    model_name = settings.ollama_model

    print(f"🔍 Checking for model: {model_name}")
    
    # Check if model exists
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if model_name in result.stdout:
            print(f"✅ Model {model_name} already installed")
            return
    except Exception as e:
        print(f"⚠️  Could not check existing models: {e}")

    # Pull the model
    if not pull_model(model_name):
        print(f"❌ Failed to pull model: {model_name}")
        print(f"   You can try manually: ollama pull {model_name}")
        sys.exit(1)

    print(f"✅ Successfully set up model: {model_name}")


if __name__ == "__main__":
    main()

