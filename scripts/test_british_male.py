"""Test British male voices from VCTK dataset."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tts.engine import CoquiTTSEngine

# Sample text with British context
SAMPLE_TEXT = """
The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.
He had been waiting for this moment for weeks, and now it was finally here.
The football match would begin in an hour, and he could already hear the crowd gathering.
"""

# British male speakers from VCTK dataset
# VCTK speakers p226-p260 are typically male voices with British accents
BRITISH_MALE_SPEAKERS = [
    "p226",  # Male, clear British accent
    "p228",  # Male, British accent
    "p230",  # Male, British accent
    "p231",  # Male, British accent
    "p232",  # Male, British accent
    "p233",  # Male, British accent
    "p234",  # Male, British accent
    "p236",  # Male, British accent
    "p237",  # Male, British accent
    "p238",  # Male, British accent
    "p239",  # Male, British accent
    "p240",  # Male, British accent
    "p241",  # Male, British accent
    "p243",  # Male, British accent
    "p244",  # Male, British accent
    "p245",  # Male, British accent
    "p246",  # Male, British accent
    "p247",  # Male, British accent
    "p248",  # Male, British accent
    "p249",  # Male, British accent
]


def main():
    """Generate samples from British male speakers."""
    print("🎙️  Testing British Male Voices")
    print("=" * 60)
    print(f"Sample text: {len(SAMPLE_TEXT)} characters")
    print(f"Testing {len(BRITISH_MALE_SPEAKERS)} speakers\n")

    output_dir = Path("data/voice_samples/british_male")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load engine once
    print("Loading TTS model...")
    engine = CoquiTTSEngine()
    engine.load_model()
    print("✅ Model loaded\n")

    results = []
    successful = 0

    for speaker in BRITISH_MALE_SPEAKERS:
        print(f"Testing speaker: {speaker}", end=" ... ", flush=True)
        output_path = output_dir / f"british_male_{speaker}.wav"

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

            successful += 1
            print(f"✅ ({elapsed:.1f}s)")

        except Exception as e:
            print(f"❌ Failed: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Successfully generated {successful}/{len(BRITISH_MALE_SPEAKERS)} voice samples")
    print(f"\nSamples saved to: {output_dir}/")
    print("\nTo listen to samples:")
    print(f"  open {output_dir}")
    print("\nAll British male voice samples:")
    for r in results:
        print(f"  - {r['path'].name} (speaker: {r['speaker']}, {r['time']:.1f}s)")
    
    if results:
        fastest = min(results, key=lambda x: x["time"])
        print(f"\n⚡ Fastest: {fastest['speaker']} ({fastest['time']:.1f}s)")
        print(f"📊 Average time: {sum(r['time'] for r in results) / len(results):.1f}s")


if __name__ == "__main__":
    main()

