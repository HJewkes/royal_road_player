"""Generate sample audio clips from different speakers for comparison."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tts.engine import CoquiTTSEngine

# Sample text for audiobook narration
SAMPLE_TEXT = """
The morning sun cast long shadows across the empty street. 
Sarah walked slowly, her footsteps echoing in the quiet neighborhood.
She had been waiting for this moment for weeks, and now it was finally here.
"""

# Speakers to test (mix of male and female voices)
SPEAKERS_TO_TEST = [
    "p225",  # Female
    "p226",  # Male
    "p227",  # Female
    "p228",  # Male
    "p229",  # Female
]


def main():
    """Generate samples from different speakers."""
    print("🎙️  Generating Voice Samples")
    print("=" * 60)
    print(f"Sample text: {len(SAMPLE_TEXT)} characters\n")

    output_dir = Path("data/voice_samples")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load engine once
    print("Loading TTS model...")
    engine = CoquiTTSEngine()
    engine.load_model()
    print("✅ Model loaded\n")

    results = []

    for speaker in SPEAKERS_TO_TEST:
        print(f"Generating sample with speaker: {speaker}")
        output_path = output_dir / f"sample_{speaker}.wav"

        try:
            start_time = time.time()
            engine.synthesize(
                text=SAMPLE_TEXT,
                output_path=output_path,
                speaker=speaker,
            )
            elapsed = time.time() - start_time
            file_size_kb = output_path.stat().st_size / 1024

            results.append({
                "speaker": speaker,
                "path": output_path,
                "time": elapsed,
                "size": file_size_kb,
            })

            print(f"  ✅ Generated in {elapsed:.2f}s ({file_size_kb:.1f} KB)\n")

        except Exception as e:
            print(f"  ❌ Failed: {e}\n")

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Generated {len(results)} voice samples")
    print(f"\nSamples saved to: {output_dir}/")
    print("\nTo listen to samples:")
    print(f"  open {output_dir}")
    print("\nSample files:")
    for r in results:
        print(f"  - {r['path'].name} (speaker: {r['speaker']})")


if __name__ == "__main__":
    main()

