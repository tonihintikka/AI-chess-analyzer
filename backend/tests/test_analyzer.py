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


# ----------------------------------------------------------------- open data

from app.analyzer.openings import lichess_opening_url
from app.analyzer import coach as coach_mod

TRAP = (Path(__file__).parent / "games" / "stalemate_trap.pgn").read_text()


def test_lichess_opening_url_normalises_names():
    assert lichess_opening_url("Scandinavian Defense: Mieses-Kotrč Variation") == \
        "https://lichess.org/opening/Scandinavian_Defense_Mieses-Kotrc_Variation"
    assert lichess_opening_url("Anderssen's Opening") == "https://lichess.org/opening/Anderssens_Opening"


@needs_engine
def test_opening_book(report):
    moves = report["moves"]
    assert [m["classification"] for m in moves[:5]] == ["book"] * 5
    assert not moves[5]["book"] and moves[5]["san"] == "Qe6+"
    o = report["opening"]
    assert o["eco"] == "B01" and "Scandinavian" in o["name"]
    assert o["deviation"]["ply"] == 6 and "Qa5" in o["deviation"]["book_alternatives"]
    # Book moves are excluded from accuracy and from error counts.
    assert report["players"]["black"]["counts"]["book"] == 2


class FakeOpenData:
    token = None
    notes: list = []

    def __init__(self, token=None):
        pass

    def tablebase(self, fen):
        if fen.startswith("8/8/8/8/8/3Q4/8/k1K5 w"):
            return {"category": "win", "dtm": 1, "moves": [{"san": "Qb1#"}]}
        return {"category": "draw", "dtm": None, "moves": []}

    def save(self):
        pass


@needs_engine
def test_tablebase_flags_thrown_win(monkeypatch):
    monkeypatch.setattr(coach_mod, "OpenData", FakeOpenData)
    r = build_report(TRAP, depth=10, online=True)
    m = r["moves"][0]
    assert "tb_threw_win" in m["tags"]
    assert m["tablebase"]["after"] == "draw" and m["tablebase"]["best_san"] == "Qb1#"
    assert r["opening"]["name"] is None  # non-standard start: no book
    topics = [lp["topic"] for lp in r["players"]["white"]["learning_priorities"]]
    assert "endgame_technique" in topics and "opening_principles" not in topics
