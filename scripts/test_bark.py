"""Test Bark TTS for natural prosody and inflection."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_bark():
    """Test Bark TTS if available."""
    print("🎙️  Testing Bark TTS")
    print("=" * 60)
    
    try:
        from bark import SAMPLE_RATE, generate_audio, preload_models
        from scipy.io.wavfile import write as write_wav
        import numpy as np
        
        print("✅ Bark imported successfully")
        print("\nPreloading models (this may take a while on first run)...")
        preload_models()
        
        # Test text with natural prosody challenges
        test_text = """
        The morning sun cast long shadows across the empty street in Manchester. 
        James walked slowly, his footsteps echoing in the quiet neighbourhood.
        He had been waiting for this moment for weeks, and now it was finally here.
        The football match would begin in an hour, and he could already hear the crowd gathering.
        """
        
        print(f"\nGenerating audio ({len(test_text)} characters)...")
        print("(Bark handles prosody and inflection very naturally)")
        
        audio_array = generate_audio(test_text.strip())
        
        # Save output
        output_path = Path("data/voice_samples/bark_sample.wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_wav(str(output_path), SAMPLE_RATE, audio_array)
        
        file_size_kb = output_path.stat().st_size / 1024
        duration = len(audio_array) / SAMPLE_RATE
        
        print(f"\n✅ Success!")
        print(f"   Output: {output_path}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Size: {file_size_kb:.2f} KB")
        print(f"\n🎵 Play audio with:")
        print(f"   open {output_path}")
        print(f"\n💡 Bark excels at:")
        print("   - Natural prosody and pacing")
        print("   - Expressive inflection")
        print("   - Handling complex text")
        print("   - Most similar to ElevenLabs/Hume")
        
        return True
        
    except ImportError:
        print("❌ Bark not installed")
        print("\nInstall with:")
        print("  pip install bark")
        print("\nOr check:")
        print("  https://github.com/suno-ai/bark")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_bark()

