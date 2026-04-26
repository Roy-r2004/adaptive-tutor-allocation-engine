"""Unit tests for the Jinja prompt registry."""

from __future__ import annotations

import pytest
from jinja2 import UndefinedError

from app.prompts.registry import PromptRegistry, get_registry


def test_classification_template_renders_with_required_vars() -> None:
    reg = get_registry()
    out = reg.render(
        "classification/ticket_classify_v1.j2",
        body="Hi, I can't log in.",
        source="chat",
    )
    assert "<categories>" in out
    assert "<ticket source=\"chat\">" in out
    assert "Hi, I can't log in." in out


def test_strict_undefined_fails_on_missing_var() -> None:
    """StrictUndefined is the single most important Jinja setting in production."""
    reg = get_registry()
    with pytest.raises(UndefinedError):
        # Missing `body`
        reg.render("classification/ticket_classify_v1.j2", source="chat")


def test_template_hash_is_stable() -> None:
    reg = get_registry()
    h1 = reg.hash("classification/ticket_classify_v1.j2")
    h2 = reg.hash("classification/ticket_classify_v1.j2")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_few_shot_examples_loaded() -> None:
    reg = get_registry()
    out = reg.render(
        "classification/ticket_classify_v1.j2",
        body="payment problem",
        source="chat",
    )
    # Few-shot block should contain example rationales
    assert "<example>" in out
    assert "rationale" in out


def test_enrichment_template_renders() -> None:
    reg = get_registry()
    out = reg.render("enrichment/extract_v1.j2", body="invoice INV-123 charge $50")
    assert "INV-123" in out
    assert "<output_format>" in out


def test_summarization_template_renders() -> None:
    reg = get_registry()
    out = reg.render(
        "summarization/summary_v1.j2",
        body="my booking failed",
        category="bug_report",
        priority="medium",
        queue="engineering",
        issue_summary="user reports failed booking",
        affected_ids=["ORD-1"],
        invoice_amounts_usd=[],
    )
    assert "bug_report" in out
    assert "engineering" in out


def test_meta_yaml_loaded() -> None:
    reg = get_registry()
    meta = reg.read_meta("classification")
    assert meta["name"] == "classification"
    assert meta["version"] == "v1"
