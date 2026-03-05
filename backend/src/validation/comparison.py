"""Text comparison utilities for validating transcribed text against expected text."""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional


@dataclass
class ComparisonResult:
    """Result of comparing expected and actual text."""
    similarity: float
    passed: bool
    issues: list[str] = field(default_factory=list)
    insertions: list[str] = field(default_factory=list)
    deletions: list[str] = field(default_factory=list)
    normalized_expected: str = ""
    normalized_actual: str = ""


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison.

    Removes formatting, normalizes punctuation, and handles
    common differences that don't affect meaning.
    """
    # Convert to lowercase
    text = text.lower()

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    # Remove quotes (formatting)
    text = text.replace('"', '').replace("'", '')
    text = text.replace('"', '').replace('"', '')
    text = text.replace("'", '').replace("'", '')

    # Remove formatting characters
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'_+', '', text)
    text = re.sub(r'[()]', '', text)

    # Normalize abbreviations
    text = re.sub(r'([a-z])\.\s*([a-z])\.', r'\1\2', text)

    # Remove punctuation
    text = re.sub(r'[.:;,!?]+', ' ', text)
    text = re.sub(r'\.{3,}', '', text)
    text = re.sub(r'…+', '', text)

    # Normalize hyphens in compound words
    text = re.sub(r'([a-z]+)-([a-z]+)', r'\1 \2', text)

    # Normalize possessives
    text = re.sub(r"([a-z]+)'s\b", r'\1s', text)

    # Final cleanup
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def compare_texts(
    expected: str,
    actual: str,
    threshold: float = 0.90,
) -> ComparisonResult:
    """
    Compare expected and actual text.

    Args:
        expected: Expected text (from source)
        actual: Actual transcribed text
        threshold: Similarity threshold for pass (default: 0.90)

    Returns:
        ComparisonResult with similarity and issues
    """
    norm_expected = normalize_text(expected)
    norm_actual = normalize_text(actual)

    # Calculate similarity using SequenceMatcher
    similarity = SequenceMatcher(None, norm_expected, norm_actual).ratio()

    passed = similarity >= threshold
    issues = []

    if not passed:
        issues.append(f"Similarity {similarity:.1%} below threshold {threshold:.1%}")

    # Find differences
    expected_words = set(norm_expected.split())
    actual_words = set(norm_actual.split())

    deletions = list(expected_words - actual_words)[:5]
    insertions = list(actual_words - expected_words)[:5]

    if deletions:
        issues.append(f"Missing words: {', '.join(deletions)}")
    if insertions:
        issues.append(f"Extra words: {', '.join(insertions)}")

    return ComparisonResult(
        similarity=similarity,
        passed=passed,
        issues=issues,
        insertions=insertions,
        deletions=deletions,
        normalized_expected=norm_expected,
        normalized_actual=norm_actual,
    )


