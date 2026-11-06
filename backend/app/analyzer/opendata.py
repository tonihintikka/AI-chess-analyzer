"""Optional online open data from Lichess. Only FEN positions are sent.

- Syzygy tablebase (tablebase.lichess.ovh): no auth, positions with <= 7 pieces.
- Opening explorer (explorer.lichess.ovh): requires a Lichess token in
  LICHESS_TOKEN (personal token, no scopes needed). Skipped without it.

Responses are cached in backend/.cache/opendata.json so repeated runs do not
hit the rate limits. Every failure is reported, never raised.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

import chess

CACHE_PATH = Path(__file__).resolve().parents[2] / ".cache" / "opendata.json"
USER_AGENT = "ai-chess-analyzer (local study tool)"
TB_MAX_PIECES = 7
TB_MAX_QUERIES = 40
RATING_BUCKETS = [0, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500]


class OpenData:
    def __init__(self, token: Optional[str] = None, cache_path: Path = CACHE_PATH):
        self.token = token if token is not None else os.getenv("LICHESS_TOKEN")
        self.cache_path = cache_path
        try:
            self.cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        except (OSError, ValueError):
            self.cache = {}
        self.notes: list[str] = []
        self.requests = 0
        if self.token and self.token.startswith("op://"):
            # Secret reference was not resolved: run via `op run` (see analyze.sh).
            self.notes.append("LICHESS_TOKEN on 1Password-viittaus, jota ei ratkaistu. "
                              "Aja analysaattori komennolla ./analyze.sh tai op run.")
            self.token = None

    def save(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache))
        except OSError as e:
            self.notes.append(f"Välimuistin tallennus epäonnistui: {e}")

    def _get(self, url: str, auth: bool = False) -> Optional[dict]:
        if url in self.cache:
            return self.cache[url]
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers)
        for attempt in range(2):
            try:
                if self.requests:
                    time.sleep(0.25)  # be polite
                self.requests += 1
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode())
                self.cache[url] = data
                return data
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt == 0:
                    time.sleep(60)
                    continue
                self.notes.append(f"{urllib.parse.urlparse(url).netloc}: HTTP {e.code}")
                return None
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                self.notes.append(f"{urllib.parse.urlparse(url).netloc}: {e}")
                return None
        return None

    # ------------------------------------------------------------------ tablebase

    def tablebase(self, fen: str) -> Optional[dict]:
        url = "https://tablebase.lichess.ovh/standard?fen=" + urllib.parse.quote(fen)
        return self._get(url)

    # ------------------------------------------------------------------ explorer

    def explorer(self, fen: str, db: str = "lichess", speed: Optional[str] = None,
                 rating: Optional[int] = None) -> Optional[dict]:
        if not self.token:
            return None
        params = {"fen": fen, "moves": 5, "topGames": 0, "recentGames": 0}
        if db == "lichess":
            if speed in ("bullet", "blitz", "rapid", "classical", "ultraBullet"):
                params["speeds"] = speed
            if rating is not None:
                params["ratings"] = str(max(b for b in RATING_BUCKETS if b <= max(rating, 0)))
        url = f"https://explorer.lichess.ovh/{db}?" + urllib.parse.urlencode(params)
        return self._get(url, auth=True)


TB_FLIP = {"win": "loss", "loss": "win", "cursed-win": "blessed-loss", "blessed-loss": "cursed-win",
           "maybe-win": "maybe-loss", "maybe-loss": "maybe-win", "draw": "draw", "unknown": "unknown"}
TB_FI = {"win": "voitto", "loss": "tappio", "draw": "tasapeli", "cursed-win": "voitto (50 siirron sääntö estää)",
         "blessed-loss": "tappio (50 siirron sääntö pelastaa)", "maybe-win": "todennäköinen voitto",
         "maybe-loss": "todennäköinen tappio", "unknown": "tuntematon"}
_RANK = {"loss": 0, "maybe-loss": 1, "blessed-loss": 2, "draw": 3, "cursed-win": 4, "maybe-win": 5, "win": 6}


def annotate_tablebase(plies: list, od: OpenData) -> int:
    """Add exact tablebase verdicts for <= 7-piece positions. Returns queries used."""
    used = 0
    for p in plies:
        before = chess.Board(p.fen_before)
        if len(before.piece_map()) > TB_MAX_PIECES:
            continue
        if used >= TB_MAX_QUERIES:
            od.notes.append(f"Tablebase-kyselyt rajattiin {TB_MAX_QUERIES} asemaan.")
            break
        tb_b = od.tablebase(p.fen_before)
        tb_a = od.tablebase(p.fen_after)
        used += 1
        if not tb_b or not tb_a:
            continue
        cat_before = tb_b.get("category", "unknown")
        cat_after = TB_FLIP.get(tb_a.get("category", "unknown"), "unknown")  # mover POV
        best = (tb_b.get("moves") or [{}])[0].get("san")
        p.tablebase = {"before": cat_before, "after": cat_after, "best_san": best,
                       "dtm_before": tb_b.get("dtm"), "before_fi": TB_FI.get(cat_before),
                       "after_fi": TB_FI.get(cat_after)}
        if cat_before in _RANK and cat_after in _RANK and _RANK[cat_after] < _RANK[cat_before]:
            if cat_before in ("win", "maybe-win", "cursed-win"):
                p.tags.append("tb_threw_win")
            elif cat_before == "draw":
                p.tags.append("tb_threw_draw")
            p.tag_details["tablebase"] = p.tablebase
    return used


def explorer_summary(data: Optional[dict], played_san: Optional[str] = None) -> Optional[dict]:
    if not data:
        return None
    total = data.get("white", 0) + data.get("draws", 0) + data.get("black", 0)
    moves = []
    for m in data.get("moves", [])[:5]:
        n = m.get("white", 0) + m.get("draws", 0) + m.get("black", 0)
        moves.append({
            "san": m.get("san"), "games": n,
            "share": round(100 * n / total, 1) if total else None,
            "white_pct": round(100 * m.get("white", 0) / n, 1) if n else None,
            "draw_pct": round(100 * m.get("draws", 0) / n, 1) if n else None,
            "black_pct": round(100 * m.get("black", 0) / n, 1) if n else None,
            "average_rating": m.get("averageRating"),
        })
    played = next((m for m in moves if m["san"] == played_san), None)
    return {"games": total, "top_moves": moves, "played": played,
            "opening": (data.get("opening") or {}).get("name")}
