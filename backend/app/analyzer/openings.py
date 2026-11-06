"""Opening book from the Lichess chess-openings dataset (CC0, vendored in data/openings).

A move is a *book move* when the resulting position appears on any named
opening line (including intermediate positions of those lines) and every
earlier move of the game was also book. This is a naming database, not a full
theory tree, so "out of book" means "left the named lines", not "theoretical
novelty".
"""
from __future__ import annotations

import csv
import io
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

import chess
import chess.pgn

DATA_DIR = Path(__file__).parent / "data" / "openings"
SOURCE = "lichess-org/chess-openings (CC0)"


def _epd(board: chess.Board) -> str:
    return board.epd()


@lru_cache(maxsize=1)
def load_book() -> tuple[dict, dict]:
    """Return (named, children).

    named:    epd -> {"eco", "name"} for positions that end a named line
    children: epd -> {san: child_epd} for every position on any named line
    """
    named: dict[str, dict] = {}
    children: dict[str, dict[str, str]] = {}
    for path in sorted(DATA_DIR.glob("*.tsv")):
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                game = chess.pgn.read_game(io.StringIO(row["pgn"]))
                if game is None:
                    continue
                board = game.board()
                for mv in game.mainline_moves():
                    parent = _epd(board)
                    san = board.san(mv)
                    board.push(mv)
                    children.setdefault(parent, {})[san] = _epd(board)
                children.setdefault(_epd(board), {})
                # Shortest name wins on duplicates is not guaranteed; keep the first
                # (files are ordered by ECO and generality).
                named.setdefault(_epd(board), {"eco": row["eco"], "name": row["name"]})
    return named, children


def lichess_opening_url(name: str) -> str:
    key = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    for ch in (":", ",", "'"):
        key = key.replace(ch, "")
    return "https://lichess.org/opening/" + key.replace(" ", "_")


def annotate_book(plies: list) -> dict:
    """Mark book plies in place and return an opening summary.

    Sets on each ply: `book` (bool) and `opening_name` (named position after
    the move, if any).
    """
    named, children = load_book()
    if not plies or plies[0].fen_before != chess.STARTING_FEN:
        for p in plies:
            p.book, p.opening_name = False, None
        return {"source": SOURCE, "eco": None, "name": None, "named_at_ply": None,
                "lichess_url": None, "book_plies": 0, "deviation": None,
                "note": "Peli alkaa erikoisasemasta, joten avauskirjaa ei käytetty."}
    in_book = True
    last_named: Optional[dict] = None
    last_named_ply = 0
    book_plies = 0
    deviation = None

    for p in plies:
        before = chess.Board(p.fen_before)
        after = chess.Board(p.fen_after)
        epd_after = _epd(after)
        info = named.get(epd_after)
        p.opening_name = info["name"] if info else None
        if info:
            last_named, last_named_ply = info, p.ply
        if in_book and epd_after in children and p.san in children.get(_epd(before), {}):
            p.book = True
            book_plies = p.ply
            continue
        p.book = False
        if in_book:
            in_book = False
            alts = sorted(children.get(_epd(before), {}).keys())
            deviation = {
                "ply": p.ply, "color": p.color, "move_number": p.move_number, "san": p.san,
                "book_alternatives": alts,
                "engine_best": p.best_move_san,
                "classification": p.classification,
            }

    summary = {
        "source": SOURCE,
        "eco": last_named["eco"] if last_named else None,
        "name": last_named["name"] if last_named else None,
        "named_at_ply": last_named_ply or None,
        "lichess_url": lichess_opening_url(last_named["name"]) if last_named else None,
        "book_plies": book_plies,
        "deviation": deviation,
    }
    return summary
