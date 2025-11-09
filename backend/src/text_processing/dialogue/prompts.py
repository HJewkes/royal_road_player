"""Prompts for dialogue extraction and character identification."""

from typing import List, Optional

from src.text_processing.dialogue.models import Character, ChapterCharacterAnalysis


class CharacterIdentificationPrompt:
    """Prompts for first-pass character identification and trait extraction."""
    
    SYSTEM_PROMPT = """You are a character analysis assistant for audiobook generation.
Your task is to identify all characters in a chapter/scene and extract their traits.

Character traits fall into two categories:
1. INNATE (permanent): Age, nationality, accent, gender, physical characteristics, etc.
   Examples: "old", "French", "deep voice", "female", "British accent"
   
2. TEMPORARY (context-dependent): Emotional states, physical conditions, situational traits
   Examples: "out of breath", "excited", "whispering", "angry", "tired"

You should:
- Identify all characters mentioned in the text
- Extract both innate and temporary traits
- Note character aliases/nicknames/titles
- Provide confidence scores for uncertain identifications
- Differentiate between traits that are permanent vs. situational

Return results as JSON."""

    @staticmethod
    def create_character_analysis_prompt(
        chapter_text: str,
        chapter_id: str,
        previous_characters: Optional[List[Character]] = None,
        context_hint: Optional[str] = None,
    ) -> str:
        """
        Create prompt for character identification and trait extraction.
        
        Args:
            chapter_text: Full text of the chapter/scene
            chapter_id: Identifier for this chapter
            previous_characters: Characters identified in previous chapters (for merging)
            context_hint: Optional context about the book/genre
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Analyze the following chapter text and identify all characters with their traits.",
            "",
            f"Chapter ID: {chapter_id}",
        ]
        
        if context_hint:
            prompt_parts.extend([
                "",
                f"Context: {context_hint}",
            ])
        
        if previous_characters:
            prompt_parts.extend([
                "",
                "Characters previously identified in earlier chapters:",
            ])
            for char in previous_characters:
                traits_str = ", ".join([t.name for t in char.get_innate_traits()])
                if traits_str:
                    prompt_parts.append(f"- {char.name} (innate traits: {traits_str})")
                else:
                    prompt_parts.append(f"- {char.name}")
        
        prompt_parts.extend([
            "",
            "Chapter text to analyze:",
            "---",
            chapter_text,
            "---",
            "",
            "Provide your analysis in the following JSON format:",
            "{",
            '  "characters": [',
            "    {",
            '      "name": "Character Name (normalized, primary name)",',
            '      "aliases": ["nickname", "title", "alternative name"],',
            '      "traits": [',
            "        {",
            '          "name": "trait name",',
            '          "category": "innate" or "temporary",',
            '          "context": "optional context about when/why this trait applies",',
            '          "confidence": 0.0-1.0',
            "        }",
            "      ],",
            '      "first_mentioned": true or false (if this is first appearance)',
            "    }",
            "  ]",
            "}",
            "",
            "Guidelines:",
            "- Normalize character names (use full name if available, e.g., 'John Smith' not 'John')",
            "- Include all aliases, nicknames, and titles",
            "- Mark traits as 'innate' if they are permanent characteristics",
            "- Mark traits as 'temporary' if they are situational (emotional state, physical condition)",
            "- If a character was in previous chapters, merge their traits (add new ones, keep existing innate traits)",
            "- Provide confidence scores (1.0 = certain, lower for ambiguous cases)",
            "- Only include characters who actually appear or are mentioned in this chapter",
        ])
        
        return "\n".join(prompt_parts)


class DialogueExtractionPrompt:
    """Prompts for second-pass dialogue extraction with speaker identification."""
    
    SYSTEM_PROMPT = """You are a dialogue extraction assistant for audiobook generation.
Your task is to identify all quoted dialogue segments, determine their speakers, and extract
emotion and speed cues for TTS generation.

You should:
- Extract all quoted dialogue (text within quotation marks)
- Identify the speaker for each dialogue segment using context
- Determine emotion/mood cues (excited, sad, angry, whispering, etc.)
- Determine speed/pacing cues (fast, slow, urgent, normal, etc.)
- Use character information from the first-pass analysis
- Provide confidence scores for uncertain identifications

Return results as JSON."""

    @staticmethod
    def create_dialogue_extraction_prompt(
        chapter_text: str,
        chapter_id: str,
        characters: List[Character],
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
    ) -> str:
        """
        Create prompt for dialogue extraction with speaker identification.
        
        Args:
            chapter_text: Full text of the chapter/scene
            chapter_id: Identifier for this chapter
            characters: Characters identified in first pass
            context_before: Optional text from previous chapter (for continuity)
            context_after: Optional text from next chapter (for continuity)
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Extract all dialogue segments from the following chapter text.",
            "",
            f"Chapter ID: {chapter_id}",
        ]
        
        if context_before:
            prompt_parts.extend([
                "",
                "Context from previous chapter (for continuity):",
                context_before[-500:],  # Last 500 chars
            ])
        
        prompt_parts.extend([
            "",
            "Characters identified in this chapter:",
        ])
        
        for char in characters:
            char_info = [char.name]
            if char.aliases:
                char_info.append(f"(aliases: {', '.join(char.aliases)})")
            innate = char.get_innate_traits()
            if innate:
                traits_str = ", ".join([t.name for t in innate[:3]])  # First 3 traits
                char_info.append(f"(traits: {traits_str})")
            prompt_parts.append(f"- {' '.join(char_info)}")
        
        prompt_parts.extend([
            "",
            "Chapter text to analyze:",
            "---",
            chapter_text,
            "---",
            "",
            "Provide your analysis in the following JSON format:",
            "{",
            '  "dialogue_segments": [',
            "    {",
            '      "text": "exact quoted dialogue text (without quotation marks)",',
            '      "speaker": "character name (normalized) or null if unknown",',
            '      "start_pos": character_position_in_text,',
            '      "end_pos": character_position_in_text,',
            '      "emotion": {',
            '        "emotion": "emotion name (e.g., excited, sad, angry, whispering, normal)",',
            '        "intensity": 0.0-1.0,',
            '        "confidence": 0.0-1.0',
            '      } or null,',
            '      "speed": {',
            '        "speed": "speed name (e.g., fast, slow, urgent, normal)",',
            '        "multiplier": 0.5-2.0 (1.0 = normal speed),',
            '        "confidence": 0.0-1.0',
            '      } or null,',
            '      "confidence": 0.0-1.0 (overall confidence for speaker identification)',
            '    }',
            "  ]",
            "}",
            "",
            "Guidelines:",
            "- Extract ONLY quoted dialogue (text within quotation marks)",
            "- Use context before and after quotes to identify speakers",
            "- Check for explicit attribution patterns ('said X', 'X said', etc.)",
            "- Use character names and aliases from the character list",
            "- If speaker is ambiguous, use null and lower confidence",
            "- Extract emotion cues from context (dialogue tags, narrative, situation)",
            "- Extract speed cues from punctuation, context, and narrative hints",
            "- Provide accurate character positions (start_pos and end_pos)",
            "- Normalize speaker names to match character names from first pass",
            "- Include confidence scores (1.0 = certain, lower for ambiguous cases)",
        ])
        
        if context_after:
            prompt_parts.extend([
                "",
                "Context from next chapter (for continuity):",
                context_after[:500],  # First 500 chars
            ])
        
        return "\n".join(prompt_parts)
