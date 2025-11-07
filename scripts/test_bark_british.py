"""Test Bark TTS with British male voice samples."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Sample text with British context
SAMPLE_TEXT = """
The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.
He had been waiting for this moment for weeks, and now it was finally here.
The football match would begin in an hour, and he could already hear the crowd gathering.
"""


def test_bark_british():
    """Test Bark with British male voice prompts."""
    print("🎙️  Testing Bark TTS - British Male Voice")
    print("=" * 60)
    print(f"Sample text: {len(SAMPLE_TEXT)} characters\n")
    
    try:
        # Fix for PyTorch 2.6 compatibility with Bark
        import torch
        import numpy as np
        
        # Add safe globals for numpy types
        torch.serialization.add_safe_globals([
            np.core.multiarray.scalar,
            np.dtype,
            type(np.dtype('float32')),
        ])
        
        # Monkey-patch torch.load to use weights_only=False for Bark compatibility
        original_load = torch.load
        def patched_load(*args, **kwargs):
            if 'weights_only' not in kwargs:
                kwargs['weights_only'] = False
            return original_load(*args, **kwargs)
        torch.load = patched_load
        
        from bark import SAMPLE_RATE, generate_audio, preload_models
        from bark.generation import SUPPORTED_LANGS
        from scipy.io.wavfile import write as write_wav
        
        print("✅ Bark imported successfully")
        print("\nPreloading models (this may take a while on first run)...")
        print("(Downloading ~1.5GB of models)")
        preload_models()
        
        output_dir = Path("data/voice_samples/bark")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Bark uses prompts to control voice characteristics
        # For British male, we can use voice prompts
        british_male_prompts = [
            "A British man with a clear, professional voice",
            "A British man with a deep, authoritative voice",
            "A British man with a warm, friendly voice",
        ]
        
        results = []
        
        for i, voice_prompt in enumerate(british_male_prompts, 1):
            print(f"\n{'='*60}")
            print(f"Generating sample {i}/{len(british_male_prompts)}")
            print(f"Voice prompt: {voice_prompt}")
            print(f"{'='*60}")
            
            # Bark can use voice prompts in the text
            # Format: [speaker: description] text
            text_with_voice = f"[speaker: {voice_prompt}] {SAMPLE_TEXT.strip()}"
            
            print("Generating audio...")
            print("(Bark handles prosody and inflection very naturally)")
            
            start_time = time.time()
            audio_array = generate_audio(text_with_voice)
            elapsed = time.time() - start_time
            
            # Save output
            output_path = output_dir / f"bark_british_male_{i}.wav"
            write_wav(str(output_path), SAMPLE_RATE, audio_array)
            
            file_size_kb = output_path.stat().st_size / 1024
            duration = len(audio_array) / SAMPLE_RATE
            
            results.append({
                "prompt": voice_prompt,
                "path": output_path,
                "time": elapsed,
                "size": file_size_kb,
                "duration": duration,
            })
            
            print(f"✅ Generated in {elapsed:.2f}s")
            print(f"   Output: {output_path.name}")
            print(f"   Duration: {duration:.2f}s")
            print(f"   Size: {file_size_kb:.2f} KB")
            print(f"   Speed: {len(SAMPLE_TEXT) / elapsed:.1f} chars/sec")
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Generated {len(results)} Bark samples")
        print(f"\nSamples saved to: {output_dir}/")
        print("\nAll samples:")
        for r in results:
            print(f"  - {r['path'].name}")
            print(f"    Prompt: {r['prompt']}")
            print(f"    Time: {r['time']:.2f}s, Size: {r['size']:.1f} KB\n")
        
        print("🎵 Play samples with:")
        print(f"   open {output_dir}")
        
        print(f"\n💡 Bark features:")
        print("   - Natural prosody and pacing (closest to ElevenLabs)")
        print("   - Expressive inflection")
        print("   - Can handle complex text naturally")
        print("   - Voice cloning possible with reference audio")
        
        return True
        
    except ImportError:
        print("❌ Bark not installed")
        print("\nInstall with:")
        print("  pip install bark")
        print("\nOr check:")
        print("  https://github.com/suno-ai/bark")
        print("\nNote: Bark requires significant disk space (~1.5GB)")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_bark_british()
    sys.exit(0 if success else 1)

