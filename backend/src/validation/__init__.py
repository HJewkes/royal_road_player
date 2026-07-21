"""STT validation module (Whisper + text comparison)."""

from src.validation.stt import STTService, get_stt_service
from src.validation.comparison import compare_texts, ComparisonResult
from src.validation.validator import AudioValidator, get_audio_validator
from src.validation.defects import Defect, confirm_defects, detect_defects

__all__ = [
    'STTService', 'get_stt_service',
    'compare_texts', 'ComparisonResult',
    'AudioValidator', 'get_audio_validator',
    'Defect', 'detect_defects', 'confirm_defects',
]

