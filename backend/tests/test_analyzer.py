"""Analyzer tests. Require Stockfish on PATH (or STOCKFISH_PATH); skipped otherwise.

Run: cd backend && .venv/bin/python -m pytest tests/test_analyzer.py -q
"""
import json
import shutil
import os
from pathlib import Path

import pytest

from app.analyzer.coach import build_report, parse_time_control, game_length
from app.analyzer.engine import win_pct, move_accuracy
from app.analyzer.render import to_html, to_markdown

GAME = (Path(__file__).parent / "games" / "scandinavian_miniature.pgn").read_text()
HAS_ENGINE = bool(os.getenv("STOCKFISH_PATH") or shutil.which("stockfish"))
needs_engine = pytest.mark.skipif(not HAS_ENGINE, reason="Stockfish not installed")


def test_time_control_categories():
    assert parse_time_control("180+2")["category"] == "blitz"
    assert parse_time_control("60")["category"] == "bullet"
    assert parse_time_control("600")["category"] == "rapid"
    assert parse_time_control("1800+30")["category"] == "classical"
    assert parse_time_control("1/86400")["category"] == "daily"
    assert parse_time_control("-")["category"] == "unknown"


def test_game_length():
    assert game_length(22)["category"] == "short"
    assert game_length(80)["category"] == "medium"
    assert game_length(140)["category"] == "long"


def test_win_model_is_symmetric_and_bounded():
    assert round(win_pct(0), 1) == 50.0
    assert round(win_pct(300) + win_pct(-300), 6) == 100.0
    assert move_accuracy(0) == 100.0
    assert 0 <= move_accuracy(80) < 5


@pytest.fixture(scope="module")
def report():
    return build_report(GAME, player="tonhin", depth=12)


@needs_engine
def test_report_facts(report):
    assert report["perspective"] == "black"
    assert report["game"]["time_control"]["category"] == "blitz"
    assert report["game"]["length"]["category"] == "short"
    moves = report["moves"]
    assert len(moves) == 22
    by_san = {(m["ply"], m["san"]): m for m in moves}
    d4 = by_san[(17, "d4")]
    assert d4["classification"] == "blunder"
    assert "lost_material" in d4["tags"]
    assert "allowed_mate" in by_san[(21, "dxc6")]["tags"]
    mate = by_san[(22, "Qxh2#")]
    assert "delivered_mate" in mate["tags"] and "missed_mate" not in mate["tags"]
    assert "endgame" not in report["game"]["phases_reached"]


@needs_engine
def test_learning_priorities_follow_evidence(report):
    white = report["players"]["white"]["learning_priorities"]
    assert white[0]["topic"] == "blunder_check"
    assert any(p["topic"] == "mate_patterns" for p in white)
    black = report["players"]["black"]["learning_priorities"]
    assert black and black[0]["topic"] == "opening_principles"


@needs_engine
def test_renderers_and_json(report):
    json.dumps(report, ensure_ascii=False)
    html = to_html(report)
    assert html.count("<svg") >= 2
    assert "Mitä kannattaa opetella" in to_markdown(report)


def test_invalid_pgn():
    with pytest.raises(ValueError):
        build_report("not a pgn")
