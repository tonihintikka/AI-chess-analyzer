"""Deterministic engine analysis: per-move evaluation, classification and phases.

No LLM calls here. Everything is derived from Stockfish evaluations and
board state so that any AI tool can present the results without guessing.
"""
from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass, field, asdict
from typing import Optional

import chess
import chess.engine
import chess.pgn

MATE_CP = 10000
PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
PIECE_NAMES_FI = {
    chess.PAWN: "sotilas", chess.KNIGHT: "ratsu", chess.BISHOP: "lähetti",
    chess.ROOK: "torni", chess.QUEEN: "kuningatar", chess.KING: "kuningas",
}

# Win-probability loss thresholds (percentage points, mover's point of view).
# Close to chess.com expected-points thresholds (0.05 / 0.10 / 0.20).
THRESHOLDS = [(2.0, "excellent"), (5.0, "good"), (10.0, "inaccuracy"), (20.0, "mistake")]
NAG_BY_CLASS = {"inaccuracy": "?!", "mistake": "?", "blunder": "??"}


def win_pct(cp: int) -> float:
    """Lichess win-percentage model for a centipawn score (mover POV)."""
    cp = max(-MATE_CP, min(MATE_CP, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def move_accuracy(win_loss: float) -> float:
    """Lichess per-move accuracy formula, clipped to 0..100."""
    acc = 103.1668 * math.exp(-0.04354 * max(0.0, win_loss)) - 3.1669
    return round(max(0.0, min(100.0, acc)), 1)


def non_pawn_material(board: chess.Board) -> int:
    total = 0
    for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += PIECE_VALUES[pt] * (len(board.pieces(pt, chess.WHITE)) + len(board.pieces(pt, chess.BLACK)))
    return total


def _backrank_pieces(board: chess.Board, color: chess.Color) -> int:
    rank = 0 if color == chess.WHITE else 7
    count = 0
    for f in range(8):
        p = board.piece_at(chess.square(f, rank))
        if p and p.color == color and p.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            count += 1
    return count


def raw_phase(board: chess.Board) -> str:
    """Heuristic phase of a position (simplified version of Lichess' Divider).

    - endgame: non-pawn material <= 20, or queens off and <= 26
    - opening: still mostly undeveloped (>= 5 pieces on each back rank) and
      no more than move 12, with nearly all pieces on the board
    - otherwise middlegame
    """
    npm = non_pawn_material(board)
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    if npm <= 20 or (queens == 0 and npm <= 26):
        return "endgame"
    undeveloped = _backrank_pieces(board, chess.WHITE) >= 5 or _backrank_pieces(board, chess.BLACK) >= 5
    if board.fullmove_number <= 12 and npm >= 50 and undeveloped:
        return "opening"
    if board.fullmove_number <= 8 and npm >= 50:
        return "opening"
    return "middlegame"


@dataclass
class PlyAnalysis:
    ply: int
    move_number: int
    color: str  # "white" | "black"
    san: str
    uci: str
    fen_before: str
    fen_after: str
    phase: str
    eval_before: str  # human readable, white POV ("+0.35", "#-2")
    eval_after: str
    cp_before_white: int
    cp_after_white: int
    best_move_san: Optional[str]
    best_move_uci: Optional[str]
    best_line_san: list[str]
    opponent_best_reply_san: Optional[str]
    win_before: float  # mover POV, 0..100
    win_after: float
    win_loss: float
    accuracy: float
    classification: str
    nag: Optional[str]
    legal_moves: int
    clock_seconds: Optional[float] = None
    time_spent_seconds: Optional[float] = None
    book: bool = False
    opening_name: Optional[str] = None
    tablebase: Optional[dict] = None
    tags: list[str] = field(default_factory=list)
    tag_details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def find_stockfish(path: Optional[str] = None) -> str:
    candidate = path or os.getenv("STOCKFISH_PATH") or shutil.which("stockfish")
    if not candidate:
        raise RuntimeError(
            "Stockfishia ei löytynyt. Asenna se (brew install stockfish) tai aseta STOCKFISH_PATH."
        )
    return candidate


def _fmt_score(score: chess.engine.PovScore) -> str:
    w = score.white()
    if w.is_mate():
        m = w.mate()
        return f"#{m}" if m is not None else "#"
    cp = w.score() or 0
    return f"{cp / 100:+.2f}"


def _line_san(board: chess.Board, pv: list[chess.Move], n: int = 5) -> list[str]:
    b = board.copy()
    out = []
    for mv in pv[:n]:
        if mv not in b.legal_moves:
            break
        out.append(b.san(mv))
        b.push(mv)
    return out


@dataclass
class _PosEval:
    score: chess.engine.PovScore
    pv: list[chess.Move]


def _evaluate(engine: chess.engine.SimpleEngine, board: chess.Board, limit: chess.engine.Limit) -> _PosEval:
    if board.is_checkmate():
        # Side to move is mated.
        return _PosEval(chess.engine.PovScore(chess.engine.Mate(-0), board.turn), [])
    if board.is_game_over(claim_draw=False):
        return _PosEval(chess.engine.PovScore(chess.engine.Cp(0), board.turn), [])
    info = engine.analyse(board, limit)
    return _PosEval(info["score"], list(info.get("pv", [])))


def _classify(win_loss: float, played_is_best: bool, legal_moves: int) -> str:
    if legal_moves == 1:
        return "forced"
    if played_is_best:
        return "best"
    for limit, name in THRESHOLDS:
        if win_loss < limit:
            return name
    return "blunder"


def analyze_game(
    game: chess.pgn.Game,
    depth: int = 14,
    engine_path: Optional[str] = None,
    time_per_move: Optional[float] = None,
) -> list[PlyAnalysis]:
    """Run Stockfish over every position of the mainline and return per-ply facts."""
    limit = chess.engine.Limit(depth=depth, time=time_per_move) if time_per_move else chess.engine.Limit(depth=depth)
    board = game.board()
    nodes = list(game.mainline())
    boards = [board.copy()]
    for node in nodes:
        board.push(node.move)
        boards.append(board.copy())

    increment = _increment(game.headers.get("TimeControl"))

    results: list[PlyAnalysis] = []
    with chess.engine.SimpleEngine.popen_uci(find_stockfish(engine_path)) as engine:
        evals = [_evaluate(engine, b, limit) for b in boards]

    phase_state = "opening"
    order = {"opening": 0, "middlegame": 1, "endgame": 2}
    last_clock: dict[bool, Optional[float]] = {chess.WHITE: None, chess.BLACK: None}

    for i, node in enumerate(nodes):
        before, after = boards[i], boards[i + 1]
        mover = before.turn
        move = node.move
        ev_b, ev_a = evals[i], evals[i + 1]

        cp_b = ev_b.score.pov(mover).score(mate_score=MATE_CP)
        cp_a = ev_a.score.pov(mover).score(mate_score=MATE_CP)
        w_b, w_a = win_pct(cp_b), win_pct(cp_a)
        loss = round(max(0.0, w_b - w_a), 2)

        best = ev_b.pv[0] if ev_b.pv else None
        legal = before.legal_moves.count()
        played_is_best = best is not None and best == move
        if played_is_best:
            loss = 0.0
        cls = _classify(loss, played_is_best, legal)

        # Phase is monotonic: never go back from middlegame to opening.
        p = raw_phase(before)
        if order[p] > order[phase_state]:
            phase_state = p
        clock = node.clock()
        spent = None
        if clock is not None and last_clock[mover] is not None:
            spent = round(max(0.0, last_clock[mover] - clock + (increment or 0)), 1)
        if clock is not None:
            last_clock[mover] = clock

        pa = PlyAnalysis(
            ply=i + 1,
            move_number=before.fullmove_number,
            color="white" if mover == chess.WHITE else "black",
            san=before.san(move),
            uci=move.uci(),
            fen_before=before.fen(),
            fen_after=after.fen(),
            phase=phase_state,
            eval_before=_fmt_score(ev_b.score),
            eval_after=_fmt_score(ev_a.score),
            cp_before_white=ev_b.score.white().score(mate_score=MATE_CP),
            cp_after_white=ev_a.score.white().score(mate_score=MATE_CP),
            best_move_san=before.san(best) if best else None,
            best_move_uci=best.uci() if best else None,
            best_line_san=_line_san(before, ev_b.pv),
            opponent_best_reply_san=after.san(ev_a.pv[0]) if ev_a.pv else None,
            win_before=round(w_b, 1),
            win_after=round(w_a, 1),
            win_loss=loss,
            accuracy=100.0 if played_is_best or cls == "forced" else move_accuracy(loss),
            classification=cls,
            nag=NAG_BY_CLASS.get(cls),
            legal_moves=legal,
            clock_seconds=clock,
            time_spent_seconds=spent,
        )
        _tag(pa, before, after, ev_b, ev_a, mover, results)
        results.append(pa)
    return results


def _tag(pa: PlyAnalysis, before: chess.Board, after: chess.Board, ev_b: _PosEval, ev_a: _PosEval,
         mover: chess.Color, previous: list[PlyAnalysis]) -> None:
    """Attach factual tactical tags derived from engine lines."""
    opp = not mover
    move = chess.Move.from_uci(pa.uci)
    bad = pa.classification in ("mistake", "blunder")

    if after.is_checkmate():
        pa.tags.append("delivered_mate")

    # Mover had a forced mate and lost it.
    mb = ev_b.score.pov(mover)
    ma = ev_a.score.pov(mover)
    if (not after.is_checkmate() and mb.is_mate() and (mb.mate() or 0) > 0
            and not (ma.is_mate() and (ma.mate() or 0) > 0)):
        pa.tags.append("missed_mate")
        pa.tag_details["missed_mate"] = {"mate_in": mb.mate(), "line": pa.best_line_san}

    # Move allowed the opponent a forced mate.
    ob, oa = ev_b.score.pov(opp), ev_a.score.pov(opp)
    if oa.is_mate() and (oa.mate() or 0) > 0 and not (ob.is_mate() and (ob.mate() or 0) > 0):
        pa.tags.append("allowed_mate")
        pa.tag_details["allowed_mate"] = {"mate_in": oa.mate(), "line": _line_san(after, ev_a.pv)}

    # Opponent's best reply wins material.
    if bad and "allowed_mate" not in pa.tags and ev_a.pv:
        reply = ev_a.pv[0]
        if after.is_capture(reply):
            victim = after.piece_at(reply.to_square)
            if victim is None and after.is_en_passant(reply):
                victim = chess.Piece(chess.PAWN, mover)
            if victim:
                pa.tags.append("lost_material")
                pa.tag_details["lost_material"] = {
                    "piece": PIECE_NAMES_FI[victim.piece_type],
                    "square": chess.square_name(reply.to_square),
                    "reply": after.san(reply),
                }
        elif after.gives_check(reply):
            pa.tags.append("allowed_tactic")
            pa.tag_details["allowed_tactic"] = {"reply": after.san(reply), "line": _line_san(after, ev_a.pv)}

    # Best move was a capture that wins material, and we didn't play it.
    best = ev_b.pv[0] if ev_b.pv else None
    if best and best != move and pa.classification in ("inaccuracy", "mistake", "blunder") and before.is_capture(best):
        victim = before.piece_at(best.to_square)
        if victim:
            pa.tags.append("missed_capture")
            pa.tag_details["missed_capture"] = {
                "piece": PIECE_NAMES_FI[victim.piece_type],
                "best": pa.best_move_san,
            }

    # Opponent just erred and we didn't punish it.
    if previous:
        prev = previous[-1]
        if prev.classification in ("mistake", "blunder") and pa.win_loss >= 10:
            pa.tags.append("missed_punishment")
            pa.tag_details["missed_punishment"] = {"opponent_move": prev.san, "best": pa.best_move_san}

    # Opening habits (facts, judged later in coaching layer).
    piece = before.piece_at(move.from_square)
    if pa.phase == "opening" and piece:
        if piece.piece_type == chess.QUEEN:
            pa.tags.append("queen_move_opening")
        if piece.piece_type == chess.PAWN and chess.square_file(move.from_square) in (0, 7):
            pa.tags.append("flank_pawn_opening")
    if before.is_castling(move):
        pa.tags.append("castled")


def _increment(tc: Optional[str]) -> Optional[int]:
    if not tc or "+" not in tc:
        return None
    try:
        return int(tc.split("+")[1])
    except ValueError:
        return None
