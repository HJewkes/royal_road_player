"""Setup script to check and download TTS models."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_settings


def check_tts_installation():
    """Check if TTS library is installed."""
    try:
        import TTS
        print(f"✅ TTS library installed: {TTS.__version__}")
        return True
    except ImportError:
        print("❌ TTS library not installed")
        print("   Run: make install-tts or pip install TTS>=0.22.0")
        return False


def check_model_availability():
    """Check if the configured TTS model is available."""
    settings = get_settings()

    if not check_tts_installation():
        return False

    try:
        from TTS.api import TTS

        print(f"📥 Checking model: {settings.tts_model}")
        print("   This will download the model if not already present...")

        # Try to initialize the model (will download if needed)
        # For XTTS v2, we need to handle license acceptance
        import sys
        if "xtts" in settings.tts_model.lower():
            print("⚠️  XTTS v2 requires license acceptance.")
            print("   You'll need to accept the license when first loading the model.")
            print("   For testing, consider using: tts_models/en/vctk/vits")
            response = input("   Continue with XTTS v2? (y/n): ").strip().lower()
            if response != 'y':
                print("   Skipping XTTS v2 setup. Update TTS_MODEL in .env to use a different model.")
                return False
        
        tts = TTS(model_name=settings.tts_model, progress_bar=True)
        print(f"✅ Model ready: {settings.tts_model}")
        return True
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        print(f"   Model: {settings.tts_model}")
        return False


def main():
    """Main setup function."""
    print("🔍 Checking TTS setup...")
    print()

    if check_tts_installation() and check_model_availability():
        print()
        print("✅ TTS system is ready!")
        return 0
    else:
        print()
        print("❌ TTS setup incomplete")
        return 1


if __name__ == "__main__":
    sys.exit(main())

