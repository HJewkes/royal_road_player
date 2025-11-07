"""Set default reference voice for XTTS v2."""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_settings


def main():
    """Set default voice reference."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Set default reference voice for XTTS v2")
    parser.add_argument(
        "voice_path",
        type=str,
        help="Path to reference audio file (e.g., data/voice_samples/british_male/british_male_p241.wav)",
    )
    
    args = parser.parse_args()
    
    voice_path = Path(args.voice_path)
    if not voice_path.exists():
        print(f"❌ Voice file not found: {voice_path}")
        return 1
    
    # Update .env file
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env file not found. Creating it...")
        env_file.touch()
    
    # Read existing .env
    env_lines = []
    if env_file.exists():
        env_lines = env_file.read_text().splitlines()
    
    # Update or add TTS_SPEAKER
    updated = False
    new_lines = []
    for line in env_lines:
        if line.startswith("TTS_SPEAKER="):
            new_lines.append(f"TTS_SPEAKER={voice_path.absolute()}")
            updated = True
        else:
            new_lines.append(line)
    
    if not updated:
        new_lines.append(f"TTS_SPEAKER={voice_path.absolute()}")
    
    env_file.write_text("\n".join(new_lines) + "\n")
    
    print(f"✅ Set default voice reference: {voice_path}")
    print(f"\nNow you can generate audio without specifying --speaker:")
    print("   python scripts/generate_audio.py chapter.txt")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

