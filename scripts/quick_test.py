"""Quick TTS test with a single word."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tts.engine import CoquiTTSEngine

def main():
    """Quick test with single word."""
    print("🎙️  Quick TTS Test")
    print("=" * 50)
    
    # Very short text for quick test
    test_text = "Hello world"
    
    print(f"Text: '{test_text}'")
    print(f"Model: tts_models/en/vctk/vits")
    print(f"Loading model...")
    
    # Create engine
    engine = CoquiTTSEngine()
    engine.load_model()
    
    # Generate audio
    output_path = Path("data/test_audio.wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGenerating audio...")
    start_time = time.time()
    
    engine.synthesize(
        text=test_text,
        output_path=output_path,
        speaker="p225",  # Use a specific speaker
    )
    
    elapsed = time.time() - start_time
    
    # Get file info
    file_size_kb = output_path.stat().st_size / 1024
    
    print(f"\n✅ Success!")
    print(f"   Output: {output_path}")
    print(f"   Time: {elapsed:.2f}s")
    print(f"   Size: {file_size_kb:.2f} KB")
    print(f"\n🎵 Play audio with:")
    print(f"   open {output_path}")
    print(f"   or")
    print(f"   afplay {output_path}")

if __name__ == "__main__":
    main()

