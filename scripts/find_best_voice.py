"""Find the best British male voice for XTTS v2 by testing multiple references."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tts.engine import CoquiTTSEngine
from src.utils.config import get_settings

# Sample text for testing
SAMPLE_TEXT = """
The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.
He had been waiting for this moment for weeks, and now it was finally here.
The football match would begin in an hour, and he could already hear the crowd gathering.
"""


def main():
    """Test multiple British male voices with XTTS v2."""
    print("🎙️  Finding Best British Male Voice for XTTS v2")
    print("=" * 60)
    
    # Get available VCTK samples
    vctk_dir = Path("data/voice_samples/british_male")
    vctk_samples = sorted(vctk_dir.glob("british_male_*.wav"))
    
    if not vctk_samples:
        print("❌ No VCTK samples found!")
        print("   Run: python scripts/test_british_male.py")
        return 1
    
    # Test first 5-10 voices (or all if fewer)
    test_samples = vctk_samples[:10] if len(vctk_samples) >= 10 else vctk_samples
    
    print(f"Testing {len(test_samples)} British male voices with XTTS v2\n")
    
    # Setup
    settings = get_settings()
    original_model = settings.tts_model
    settings.tts_model = "tts_models/multilingual/multi-dataset/xtts_v2"
    
    output_dir = Path("data/voice_samples/xtts_v2/voice_comparison")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        print("Loading XTTS v2 model...")
        engine = CoquiTTSEngine()
        engine.load_model()
        print("✅ Model loaded\n")
        
        results = []
        
        for ref_audio in test_samples:
            speaker_id = ref_audio.stem.replace("british_male_", "")
            print(f"Testing {speaker_id}...", end=" ", flush=True)
            
            output_path = output_dir / f"xtts_v2_{speaker_id}.wav"
            
            try:
                start_time = time.time()
                engine.synthesize(
                    text=SAMPLE_TEXT.strip(),
                    output_path=output_path,
                    language="en",
                    speaker=str(ref_audio),
                )
                elapsed = time.time() - start_time
                file_size_kb = output_path.stat().st_size / 1024
                
                results.append({
                    "speaker": speaker_id,
                    "path": output_path,
                    "time": elapsed,
                    "size": file_size_kb,
                })
                
                print(f"✅ ({elapsed:.1f}s, {file_size_kb:.1f} KB)")
                
            except Exception as e:
                print(f"❌ Failed: {e}")
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Generated {len(results)} voice samples")
        print(f"\nSamples saved to: {output_dir}/")
        print("\nAll samples:")
        for r in results:
            print(f"  - {r['path'].name} (speaker: {r['speaker']}, {r['time']:.1f}s)")
        
        if results:
            fastest = min(results, key=lambda x: x["time"])
            print(f"\n⚡ Fastest: {fastest['speaker']} ({fastest['time']:.1f}s)")
            print(f"📊 Average time: {sum(r['time'] for r in results) / len(results):.1f}s")
        
        print("\n🎵 Listen to samples:")
        print(f"   open {output_dir}")
        print("\n💡 Choose your favorite voice, then use it as reference:")
        print("   python scripts/generate_audio.py chapter.txt \\")
        print(f"     --speaker {output_dir}/xtts_v2_<speaker_id>.wav")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        settings.tts_model = original_model


if __name__ == "__main__":
    sys.exit(main())

