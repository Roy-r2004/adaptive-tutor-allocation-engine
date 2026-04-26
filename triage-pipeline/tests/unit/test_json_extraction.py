"""Tests for the JSON extraction helper inside the LLM gateway."""

from __future__ import annotations

import pytest

from app.llm.gateway import LLMValidationError, _extract_json


def test_strict_json_parses() -> None:
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_markdown_fenced_json_parses() -> None:
    text = '```json\n{"a": 1, "b": "x"}\n```'
    assert _extract_json(text) == {"a": 1, "b": "x"}


def test_plain_fenced_json_parses() -> None:
    text = '```\n{"a": 1}\n```'
    assert _extract_json(text) == {"a": 1}


def test_prose_wrapper_parses() -> None:
    text = 'Here is your JSON:\n{"a": 1, "b": "x"}\nLet me know!'
    assert _extract_json(text) == {"a": 1, "b": "x"}


def test_empty_response_raises() -> None:
    with pytest.raises(LLMValidationError):
        _extract_json("")


def test_no_json_anywhere_raises() -> None:
    with pytest.raises(LLMValidationError):
        _extract_json("just some prose here")
