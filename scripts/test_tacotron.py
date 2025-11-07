"""Test Tacotron2-DDC model for comparison."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tts.engine import CoquiTTSEngine
from src.utils.config import get_settings

# Same sample text as British male test for fair comparison
SAMPLE_TEXT = """
The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.
He had been waiting for this moment for weeks, and now it was finally here.
The football match would begin in an hour, and he could already hear the crowd gathering.
"""


def main():
    """Test Tacotron2-DDC model."""
    print("🎙️  Testing Tacotron2-DDC Model")
    print("=" * 60)
    print(f"Sample text: {len(SAMPLE_TEXT)} characters\n")

    # Temporarily change model
    settings = get_settings()
    original_model = settings.tts_model
    settings.tts_model = "tts_models/en/ljspeech/tacotron2-DDC"

    output_dir = Path("data/voice_samples")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "tacotron2_sample.wav"

    try:
        print("Loading Tacotron2-DDC model...")
        print("(This may take longer than VITS - it's a more complex model)\n")
        
        engine = CoquiTTSEngine()
        engine.load_model()

        print("Generating audio...")
        start_time = time.time()
        
        engine.synthesize(
            text=SAMPLE_TEXT,
            output_path=output_path,
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
        print(f"\n📊 Comparison:")
        print(f"   VITS (p240): ~2.6s for similar text")
        print(f"   Tacotron2: {elapsed:.2f}s")
        print(f"   Difference: {elapsed - 2.6:.2f}s slower")

    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore original model
        settings.tts_model = original_model


if __name__ == "__main__":
    main()

