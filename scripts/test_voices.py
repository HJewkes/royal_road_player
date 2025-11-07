"""Script to generate sample audio clips from different TTS models and speakers."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tts.engine import CoquiTTSEngine
from src.utils.config import get_settings

# Sample text for testing (short enough for quick generation)
SAMPLE_TEXT = """
Hello, this is a test of the text-to-speech system. 
We're evaluating different voices and models to find the best one for audiobook narration.
The voice should be clear, natural, and pleasant to listen to for extended periods.
"""


def generate_sample(model_name: str, speaker: str = None, output_dir: Path = None):
    """Generate a sample audio clip."""
    if output_dir is None:
        output_dir = Path("data/voice_samples")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    if speaker:
        print(f"Speaker: {speaker}")
    print(f"{'='*60}")

    # Temporarily change model
    settings = get_settings()
    original_model = settings.tts_model
    settings.tts_model = model_name

    try:
        engine = CoquiTTSEngine()
        engine.load_model()

        # Determine output filename
        if speaker:
            filename = f"{model_name.replace('/', '_')}_{speaker}.wav"
        else:
            filename = f"{model_name.replace('/', '_')}.wav"
        output_path = output_dir / filename

        # Generate with timing
        start_time = time.time()
        engine.synthesize(
            text=SAMPLE_TEXT,
            output_path=output_path,
            speaker=speaker,
        )
        elapsed = time.time() - start_time

        # Get file size
        file_size_kb = output_path.stat().st_size / 1024

        print(f"✅ Generated: {output_path.name}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Size: {file_size_kb:.2f} KB")
        print(f"   Speed: {len(SAMPLE_TEXT) / elapsed:.1f} chars/sec")

        return {
            "model": model_name,
            "speaker": speaker,
            "path": output_path,
            "time": elapsed,
            "size": file_size_kb,
        }

    except Exception as e:
        print(f"❌ Failed: {e}")
        return None
    finally:
        # Restore original model
        settings.tts_model = original_model


def main():
    """Test different models and speakers."""
    print("🎙️  Generating voice samples for comparison...")
    print(f"Sample text length: {len(SAMPLE_TEXT)} characters\n")

    results = []

    # Test different models
    models_to_test = [
        # High quality single-speaker models
        ("tts_models/en/ljspeech/tacotron2-DDC", None),
        ("tts_models/en/ljspeech/glow-tts", None),
        ("tts_models/en/ljspeech/speedy-speech", None),
        
        # Multi-speaker models (test a few speakers)
        ("tts_models/en/vctk/vits", "p225"),  # Female voice
        ("tts_models/en/vctk/vits", "p226"),  # Male voice
        ("tts_models/en/vctk/vits", "p227"),  # Another voice
    ]

    for model_name, speaker in models_to_test:
        try:
            result = generate_sample(model_name, speaker)
            if result:
                results.append(result)
        except Exception as e:
            print(f"⚠️  Skipped {model_name}: {e}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Generated {len(results)} samples")
    print(f"\nSamples saved to: data/voice_samples/")
    print("\nTo listen to samples:")
    print("  open data/voice_samples/")
    print("\nFastest generation:")
    if results:
        fastest = min(results, key=lambda x: x["time"])
        print(f"  {fastest['model']} ({fastest.get('speaker', 'default')}): {fastest['time']:.2f}s")


if __name__ == "__main__":
    main()

