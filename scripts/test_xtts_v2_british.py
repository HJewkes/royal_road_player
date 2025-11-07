"""Test XTTS v2 with British male voice samples."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tts.engine import CoquiTTSEngine
from src.utils.config import get_settings

# Sample text with British context
SAMPLE_TEXT = """
The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.
He had been waiting for this moment for weeks, and now it was finally here.
The football match would begin in an hour, and he could already hear the crowd gathering.
"""


def main():
    """Test XTTS v2 with British male voice."""
    print("🎙️  Testing XTTS v2 - British Male Voice")
    print("=" * 60)
    print(f"Sample text: {len(SAMPLE_TEXT)} characters\n")

    # Temporarily change model
    settings = get_settings()
    original_model = settings.tts_model
    settings.tts_model = "tts_models/multilingual/multi-dataset/xtts_v2"
    settings.tts_language = "en"

    output_dir = Path("data/voice_samples/xtts_v2")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("⚠️  XTTS v2 requires license acceptance.")
        print("   You'll need to accept the license when the model loads.")
        print("   This is a one-time acceptance.\n")
        
        print("Loading XTTS v2 model...")
        print("(This will prompt for license acceptance on first run)\n")
        
        engine = CoquiTTSEngine()
        
        # Try to load - will prompt for license
        try:
            engine.load_model()
        except EOFError:
            print("\n❌ License acceptance required.")
            print("   Please run interactively to accept license:")
            print("   python scripts/test_xtts_v2_british.py")
            return False

        print("✅ Model loaded\n")

        # XTTS v2 can use speaker reference or default voice
        # For British male, we can use a reference audio or let it use default
        # XTTS v2 requires either speaker_wav (voice cloning) or can use a reference
        # For British male, we'll use a simple approach - generate with language only
        # XTTS v2 will use a default voice for the language
        print("Generating sample with British English (default voice)...")
        output_path = output_dir / "xtts_v2_british_default.wav"
        
        start_time = time.time()
        # XTTS v2 needs speaker_wav for voice cloning, or we can use a reference audio
        # For now, let's try without speaker (may need a reference)
        try:
            engine.synthesize(
                text=SAMPLE_TEXT,
                output_path=output_path,
                language="en",
                speaker=None,  # Try without speaker first
            )
        except ValueError as e:
            if "speaker" in str(e).lower():
                print("\n⚠️  XTTS v2 requires a speaker reference for voice cloning.")
                print("   For British male voice, you can:")
                print("   1. Provide a reference audio file with --speaker")
                print("   2. Use a pre-recorded British male voice sample")
                print("\n   Generating with a simple workaround...")
                # Try with a minimal speaker reference (empty or default)
                # Actually, XTTS v2 needs speaker_wav - let's create a note
                raise ValueError("XTTS v2 requires speaker_wav parameter for voice cloning. Please provide a reference audio file.")
        elapsed = time.time() - start_time
        file_size_kb = output_path.stat().st_size / 1024

        print(f"\n✅ Success!")
        print(f"   Output: {output_path}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Size: {file_size_kb:.2f} KB")
        print(f"   Speed: {len(SAMPLE_TEXT) / elapsed:.1f} chars/sec")
        print(f"\n🎵 Play audio with:")
        print(f"   open {output_path}")

        # Note about voice cloning
        print(f"\n💡 XTTS v2 supports voice cloning:")
        print("   - Provide a reference audio file with --speaker")
        print("   - Can clone any British male voice from a sample")
        print("   - Excellent for consistent narrator voice")

        return True

    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original model
        settings.tts_model = original_model


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

