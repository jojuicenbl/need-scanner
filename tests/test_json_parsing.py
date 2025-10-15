"""Test JSON parsing from LLM responses."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from need_scanner.analysis.summarize import parse_llm_response


def test_parse_valid_json():
    """Test parsing valid JSON response."""
    response = '''
    {
        "title": "Automatisation facturation",
        "description": "Freelancers cherchent solutions pour automatiser facturation.",
        "monetizable": true,
        "justification": "Problème récurrent avec volonté de payer.",
        "mvp": "Template facture avec auto-remplissage.",
        "pain_score_llm": 8
    }
    '''

    result = parse_llm_response(response)
    assert result is not None
    assert result["title"] == "Automatisation facturation"
    assert result["monetizable"] is True
    assert result["pain_score_llm"] == 8
    print("✓ Valid JSON parsing works")


def test_parse_json_with_markdown():
    """Test parsing JSON wrapped in markdown code blocks."""
    response = '''
    Here's the analysis:

    ```json
    {
        "title": "Time tracking issue",
        "description": "Freelancers need simple time tracking.",
        "monetizable": true,
        "justification": "High pain point.",
        "mvp": "Simple timer app.",
        "pain_score_llm": 7
    }
    ```
    '''

    result = parse_llm_response(response)
    assert result is not None
    assert result["title"] == "Time tracking issue"
    assert result["pain_score_llm"] == 7
    print("✓ Markdown code block parsing works")


def test_parse_json_without_json_tag():
    """Test parsing JSON in markdown without 'json' tag."""
    response = '''
    ```
    {
        "title": "Contract templates",
        "description": "Need contract templates.",
        "monetizable": false,
        "justification": "Low willingness to pay.",
        "mvp": "Free template library.",
        "pain_score_llm": 4
    }
    ```
    '''

    result = parse_llm_response(response)
    assert result is not None
    assert result["monetizable"] is False
    print("✓ Generic code block parsing works")


def test_parse_invalid_json():
    """Test handling of invalid JSON."""
    response = '''
    This is not valid JSON at all.
    Just some random text.
    '''

    result = parse_llm_response(response)
    assert result is None
    print("✓ Invalid JSON handling works")


def test_all_required_fields():
    """Test that all required fields are present."""
    response = '''
    {
        "title": "Test",
        "description": "Test description",
        "monetizable": true,
        "justification": "Test justification",
        "mvp": "Test MVP",
        "pain_score_llm": 5
    }
    '''

    result = parse_llm_response(response)
    assert result is not None

    required_fields = ["title", "description", "monetizable", "justification", "mvp", "pain_score_llm"]
    for field in required_fields:
        assert field in result, f"Missing field: {field}"

    print("✓ All required fields present")


if __name__ == "__main__":
    print("Running JSON parsing tests...\n")

    try:
        test_parse_valid_json()
        test_parse_json_with_markdown()
        test_parse_json_without_json_tag()
        test_parse_invalid_json()
        test_all_required_fields()

        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)
