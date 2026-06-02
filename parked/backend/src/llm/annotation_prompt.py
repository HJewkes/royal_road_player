"""Prompt engineering for LLM-based text annotation."""

from typing import Optional


class AnnotationPrompt:
    """Generate prompts for LLM-based annotation."""

    SYSTEM_PROMPT = """You are a text annotation assistant for audiobook generation.
Your task is to analyze text and identify where TTS annotations should be added for better
speech quality. You should identify:
1. Natural pause locations (sentence breaks, paragraph breaks, dramatic pauses)
2. Emphasis points (important words, dialogue emphasis)
3. Pitch shifts (questions, exclamations, character voices)
4. Speed changes (fast-paced action, slow contemplation)

Annotations should be provided as JSON metadata without modifying the original text.
Only add annotations that significantly improve speech quality."""

    @staticmethod
    def create_annotation_prompt(text: str, context: Optional[str] = None) -> str:
        """
        Create prompt for annotating text.

        Args:
            text: Text to annotate
            context: Optional context (e.g., chapter title, book genre)

        Returns:
            Formatted prompt string
        """
        prompt = f"""Analyze the following text and generate TTS annotations.

Text to annotate:
{text}

Provide annotations in the following JSON format:
{{
  "annotations": [
    {{
      "type": "pause|emphasis|pitch|speed",
      "position": <character_position>,
      "duration_ms": <duration_in_milliseconds> (for pauses),
      "strength": <multiplier> (for emphasis/speed),
      "shift": <pitch_shift> (for pitch, -0.5 to 0.5)
    }}
  ]
}}

Only include annotations that meaningfully improve speech quality.
Focus on natural pauses, dialogue emphasis, and emotional tone shifts."""

        if context:
            prompt = f"Context: {context}\n\n{prompt}"

        return prompt

    @staticmethod
    def get_annotation_format_example() -> dict:
        """
        Get example annotation format.

        Returns:
            Example annotation dictionary
        """
        return {
            "annotations": [
                {
                    "type": "pause",
                    "position": 50,
                    "duration_ms": 500,
                },
                {
                    "type": "emphasis",
                    "position": 100,
                    "strength": 1.3,
                },
                {
                    "type": "pitch",
                    "position": 200,
                    "shift": 0.1,
                },
            ]
        }

