"""The metrics code of scripts/benchmark_models.py (no Ollama needed)."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "benchmark_models.py"
spec = importlib.util.spec_from_file_location("benchmark_models", SCRIPT)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

CANDIDATES = ["Bob", "Cy", "Dee"]


def rows(*texts):
    return [{"text": t, "candidates": CANDIDATES} for t in texts]


def test_target_stats_separates_exact_parsed_and_invalid():
    stats = bench.target_stats(rows("Bob", "  Cy. ", "I vote for Dee because", "nobody"))
    assert stats == {"exact": 0.5, "parsed": 0.75, "invalid": 0.25}


def test_witch_stats_counts_understood_decisions():
    stats = bench.witch_stats(rows("SAVE", "POISON Bob", "PASS", "I like tea"))
    assert stats == {"understood": 0.75}


def test_discussion_stats():
    stats = bench.discussion_stats([
        {"text": "I think Bob looks suspicious today.", "role": "villager"},
        {"text": "I think Bob looks suspicious today.", "role": "villager"},
        {"text": "As the seer I saw something. Really. Truly.", "role": "seer"},
        {"text": "no comment", "role": "witch"},
    ])
    assert stats["no_comment"] == pytest.approx(0.25)
    assert stats["role_leak"] == pytest.approx(1 / 3)           # "As the seer" from the seer
    assert stats["role_word"] == pytest.approx(1 / 3)
    assert stats["names_a_player"] == pytest.approx(2 / 3)
    assert stats["too_long"] == pytest.approx(1 / 3)
    assert stats["identical_answers"] == pytest.approx(1 / 3)
    assert 0 < stats["distinct_bigrams"] < 1


def test_markdown_table_has_one_column_per_model():
    report = {
        "model": "m", "size_gb": 1.0, "vram_gb": 1.5, "cold_start_s": 2, "tokens_per_s": 50.0,
        "avg_answer_s": 0.5, "avg_prompt_tokens": 300, "errors": 0,
        "vote": {"exact": 1.0, "parsed": 1.0}, "night": {"exact": 0.5, "parsed": 1.0},
        "witch": {"understood": 0.75},
        "discussion": {"no_comment": 0.1, "role_leak": 0.0, "role_word": 0.1, "names_a_player": 0.5,
                       "too_long": 0.0, "avg_words": 12,
                       "distinct_bigrams": 0.9, "identical_answers": 0.0},
        "samples": {"discussion": ["hello"], "vote": ["Bob"], "night": ["Cy"]},
    }
    table = bench.to_markdown([report, {**report, "model": "n"}])
    assert "| Metric | m | n |" in table
    assert "| Vote: valid after parsing | 100% | 100% |" in table
    assert "- *discussion*: hello" in table
