"""Test XTTS v2 with a British male voice reference from VCTK samples."""

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
    """Test XTTS v2 with British male voice reference."""
    print("🎙️  Testing XTTS v2 - British Male Voice (Voice Cloning)")
    print("=" * 60)
    print(f"Sample text: {len(SAMPLE_TEXT)} characters\n")

    # Check if we have a VCTK sample to use as reference
    vctk_samples = list(Path("data/voice_samples/british_male").glob("british_male_*.wav"))
    
    if not vctk_samples:
        print("❌ No VCTK voice samples found!")
        print("   Please run: python scripts/test_british_male.py")
        print("   This will generate British male voice samples from VCTK")
        print("   that we can use as reference for XTTS v2 voice cloning.")
        return False

    # Use the first VCTK sample as reference
    reference_audio = vctk_samples[0]
    print(f"Using reference audio: {reference_audio.name}")
    print(f"Reference: {reference_audio}\n")

    # Temporarily change model
    settings = get_settings()
    original_model = settings.tts_model
    settings.tts_model = "tts_models/multilingual/multi-dataset/xtts_v2"
    settings.tts_language = "en"

    output_dir = Path("data/voice_samples/xtts_v2")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("Loading XTTS v2 model...")
        engine = CoquiTTSEngine()
        engine.load_model()
        print("✅ Model loaded\n")

        print("Generating sample with voice cloning...")
        print("(XTTS v2 will clone the voice from the reference audio)\n")
        
        output_path = output_dir / f"xtts_v2_cloned_{reference_audio.stem}.wav"
        
        start_time = time.time()
        engine.synthesize(
            text=SAMPLE_TEXT,
            output_path=output_path,
            language="en",
            speaker=str(reference_audio),  # Use VCTK sample as reference
        )
        elapsed = time.time() - start_time
        file_size_kb = output_path.stat().st_size / 1024

        print(f"\n✅ Success!")
        print(f"   Output: {output_path}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Size: {file_size_kb:.2f} KB")
        print(f"   Speed: {len(SAMPLE_TEXT) / elapsed:.1f} chars/sec")
        print(f"\n🎵 Play audio with:")
        print(f"   open {output_path}")
        print(f"\n💡 XTTS v2 voice cloning:")
        print("   - Cloned the British male voice from the reference")
        print("   - Natural prosody and pacing")
        print("   - Consistent voice across the text")
        print("   - Excellent for audiobook narration")

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

