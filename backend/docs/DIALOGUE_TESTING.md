# Dialogue Module Testing Guide

This guide explains how to test the dialogue extraction module, including unit tests that don't require a running LLM.

## Overview

The dialogue module uses a two-pass LLM approach, which presents testing challenges:
- LLM calls are slow and expensive
- Tests should run in CI/CD without requiring Ollama
- Tests should be fast and deterministic

## Testing Strategy

### Unit Tests (No LLM Required)

All unit tests use **mocked LLM clients** and don't require Ollama to be running.

**Key Components:**
- `MockOllamaClient`: Mock implementation that returns predefined responses
- Pytest fixtures: Reusable test data and mocks
- Test utilities: Helper functions for creating mock responses

### Integration Tests (Optional LLM)

Integration tests can optionally use a real LLM if available, but are marked to skip in CI.

## Running Tests

### Run All Unit Tests (Recommended for CI)

```bash
# Run all dialogue tests (uses mocks, no LLM required)
pytest tests/text_processing/test_dialogue*.py -v

# Run only unit tests (excludes integration/E2E)
pytest tests/text_processing/test_dialogue*.py -m unit -v
```

### Run Tests with Coverage

```bash
pytest tests/text_processing/test_dialogue*.py --cov=src.text_processing.dialogue --cov-report=term-missing
```

### Run Specific Test Files

```bash
# Test models only
pytest tests/text_processing/test_dialogue_models.py -v

# Test validator only
pytest tests/text_processing/test_dialogue_validator.py -v

# Test service only
pytest tests/text_processing/test_dialogue_service.py -v

# Test LLM services only
pytest tests/text_processing/test_dialogue_llm_service.py -v
```

## Using MockOllamaClient

The `MockOllamaClient` class allows you to test without a real LLM:

```python
from src.text_processing.dialogue.service import DialogueService
from src.text_processing.dialogue.test_utils import (
    MockOllamaClient,
    create_mock_character_response,
    create_mock_dialogue_response,
)

# Create mock responses
char_response = create_mock_character_response([
    {
        "name": "John Smith",
        "aliases": ["John"],
        "traits": [{"name": "old", "category": "innate", "confidence": 1.0}],
        "first_mentioned": True,
    }
])

dialogue_response = create_mock_dialogue_response([
    {
        "text": "Hello",
        "speaker": "John Smith",
        "start_pos": 0,
        "end_pos": 5,
        "confidence": 0.9,
    }
])

# Create service with mock client
mock_client = MockOllamaClient(responses=[char_response, dialogue_response])
service = DialogueService(llm_client=mock_client)

# Use service normally
char_analysis, dialogue_analysis, warnings = service.process_chapter(
    chapter_text='John said "Hello"',
    chapter_id="test_ch1",
    validate=False,
)
```

## Using Pytest Fixtures

Pytest fixtures provide reusable test data:

```python
import pytest

def test_with_fixtures(dialogue_service_mocked, sample_chapter_text):
    """Test using fixtures."""
    service = dialogue_service_mocked
    
    char_analysis, dialogue_analysis, warnings = service.process_chapter(
        chapter_text=sample_chapter_text,
        chapter_id="test_ch1",
        validate=False,
    )
    
    assert len(char_analysis.characters) > 0
```

**Available Fixtures:**
- `mock_ollama_client`: Mock Ollama client
- `sample_character_response`: Sample character JSON response
- `sample_dialogue_response`: Sample dialogue JSON response
- `mock_llm_responses`: Pre-configured mock with responses
- `sample_chapter_text`: Sample chapter text with dialogue
- `sample_characters`: Sample Character objects
- `sample_dialogue_segments`: Sample DialogueSegment objects
- `dialogue_service_mocked`: DialogueService with mocked LLM

## Test Markers

Tests are marked with pytest markers:

- `@pytest.mark.unit`: Unit tests (no LLM, fast)
- `@pytest.mark.integration`: Integration tests (may require LLM)
- `@pytest.mark.e2e`: End-to-end tests (requires full setup)
- `@pytest.mark.slow`: Slow tests (skip in CI)

**Run only unit tests:**
```bash
pytest -m unit
```

**Skip slow tests:**
```bash
pytest -m "not slow"
```

## CI/CD Configuration

For CI/CD pipelines, configure pytest to:
1. Run only unit tests (fast, no dependencies)
2. Skip slow/integration tests
3. Generate coverage reports

**Example GitHub Actions:**

```yaml
- name: Run tests
  run: |
    pytest tests/text_processing/test_dialogue*.py \
      -m "unit and not slow" \
      --cov=src.text_processing.dialogue \
      --cov-report=xml \
      --cov-report=term
```

## Testing Validation

Validation tests don't require LLM mocks:

```python
def test_validate_dialogue_segment():
    """Test dialogue validation."""
    from src.text_processing.dialogue.validator import DialogueValidator
    from src.text_processing.dialogue.models import DialogueSegment
    
    text = 'John said "Hello"'
    segment = DialogueSegment(
        text="Hello",
        speaker="John",
        start_pos=text.find("Hello"),
        end_pos=text.find("Hello") + 5,
    )
    
    is_valid, error = DialogueValidator.validate_dialogue_segment(segment, text)
    assert is_valid
```

## Error Handling Tests

Test error handling without triggering real errors:

```python
def test_llm_error_handling():
    """Test handling of LLM errors."""
    # Mock client that raises exception
    mock_client = MockOllamaClient()
    mock_client.generate.side_effect = Exception("Connection failed")
    
    service = DialogueService(llm_client=mock_client)
    
    # Should handle gracefully
    result = service.process_chapter("text", "ch1", validate=False)
    # Returns empty analysis on error
    assert len(result[0].characters) == 0
```

## Best Practices

1. **Always use mocks for unit tests**: Don't require Ollama to be running
2. **Use fixtures for common test data**: Reduces duplication
3. **Test validation separately**: Validation logic doesn't need LLM
4. **Mark tests appropriately**: Use markers for test organization
5. **Keep tests fast**: Unit tests should complete in seconds
6. **Test error cases**: Ensure graceful error handling

## Troubleshooting

### Tests fail with "Connection refused"

**Problem:** Tests are trying to connect to real Ollama.

**Solution:** Ensure you're using `MockOllamaClient` or mocking `OllamaClient`:

```python
# Correct
service = DialogueService(llm_client=MockOllamaClient())

# Incorrect (will try real connection)
service = DialogueService()  # Creates real OllamaClient
```

### Tests are slow

**Problem:** Tests are making real LLM calls.

**Solution:** Check that mocks are properly configured. Use `-v` flag to see which tests are slow:

```bash
pytest tests/text_processing/test_dialogue*.py -v --durations=10
```

### Coverage is low

**Problem:** Some code paths aren't tested.

**Solution:** Add tests for error cases and edge cases. Check coverage report:

```bash
pytest --cov=src.text_processing.dialogue --cov-report=html
# Open htmlcov/index.html
```

## Example Test Structure

```python
import pytest
from src.text_processing.dialogue.service import DialogueService
from src.text_processing.dialogue.test_utils import MockOllamaClient

class TestMyFeature:
    """Tests for my feature."""
    
    @pytest.mark.unit
    def test_feature_success(self):
        """Test successful case."""
        mock_client = MockOllamaClient(responses=[...])
        service = DialogueService(llm_client=mock_client)
        # Test...
    
    @pytest.mark.unit
    def test_feature_error(self):
        """Test error handling."""
        # Test error cases...
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_feature_with_real_llm(self):
        """Test with real LLM (skip in CI)."""
        # Only runs if explicitly requested
        pass
```
