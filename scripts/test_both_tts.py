"""Test both XTTS v2 and Bark with British male voices - interactive version."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SAMPLE_TEXT = """
The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.
He had been waiting for this moment for weeks, and now it was finally here.
The football match would begin in an hour, and he could already hear the crowd gathering.
"""

def main():
    """Test both systems."""
    print("🎙️  Testing XTTS v2 and Bark - British Male Voices")
    print("=" * 60)
    print("\nThis script will test both systems.")
    print("You'll need to accept the XTTS v2 license when prompted.\n")
    
    # Test XTTS v2
    print("=" * 60)
    print("TEST 1: XTTS v2")
    print("=" * 60)
    try:
        from scripts.test_xtts_v2_british import main as test_xtts
        test_xtts()
    except Exception as e:
        print(f"XTTS v2 test failed: {e}")
        print("You may need to run this interactively to accept the license.")
    
    # Test Bark (with note about PyTorch issue)
    print("\n" + "=" * 60)
    print("TEST 2: Bark")
    print("=" * 60)
    print("\n⚠️  Note: Bark has a PyTorch 2.6 compatibility issue.")
    print("   We're working on a fix. For now, you can:")
    print("   1. Use XTTS v2 (which works)")
    print("   2. Try Bark with PyTorch < 2.6")
    print("   3. Wait for Bark update\n")
    
    try:
        # Try the patched version
        from scripts.test_bark_british import test_bark_british
        test_bark_british()
    except Exception as e:
        print(f"Bark test failed: {e}")
        print("\nBark requires PyTorch < 2.6 or a fix.")
        print("XTTS v2 is ready to use!")

if __name__ == "__main__":
    main()

