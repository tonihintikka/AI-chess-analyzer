"""Presentation helpers: Markdown and a self-contained HTML page with SVG boards.

These renderers only format facts from the report; they add no analysis.
"""
from __future__ import annotations

import html

import chess
import chess.svg

from .coach import CLASS_FI, PHASE_FI, PHASES

CLASS_COLOR = {"best": "#2e7d32", "excellent": "#43a047", "good": "#7cb342", "forced": "#757575",
               "inaccuracy": "#f9a825", "mistake": "#ef6c00", "blunder": "#c62828"}


def board_svg(move: dict, flip: bool = False, size: int = 300) -> str:
    """Board after `move`, played move as last-move highlight, engine best as green arrow."""
    board = chess.Board(move["fen_after"])
    played = chess.Move.from_uci(move["uci"])
    arrows = []
    if move.get("best_move_uci") and move["best_move_uci"] != move["uci"]:
        b = chess.Move.from_uci(move["best_move_uci"])
        arrows.append(chess.svg.Arrow(b.from_square, b.to_square, color="#2e7d32cc"))
    check = board.king(board.turn) if board.is_check() else None
    return chess.svg.board(board, lastmove=played, arrows=arrows, check=check,
                           orientation=chess.BLACK if flip else chess.WHITE, size=size)


def _pct(v):
    return "–" if v is None else f"{v:.0f} %"


def to_markdown(r: dict) -> str:
    g = r["game"]
    tc = g["time_control"]
    out = [f"# {g['white']} ({g['white_elo']}) – {g['black']} ({g['black_elo']}): {g['result']}",
           "",
           f"- Aikakontrolli: {tc['raw']} → **{tc['category_fi']}**",
           f"- Pituus: {g['length']['full_moves']} siirtoa → **{g['length']['category_fi']}**",
           f"- Avaus: {g.get('eco') or ''} {g.get('opening') or ''}".rstrip(),
           f"- Vaiheet: {', '.join(PHASE_FI[p] for p in g['phases_reached'])}",
           ""]
    colors = [r["perspective"]] if r["perspective"] else ["white", "black"]
    for c in colors:
        p = r["players"][c]
        out += [f"## {p['name']} ({'valkea' if c == 'white' else 'musta'}), tarkkuus {_pct(p['accuracy'])}", ""]
        for ph in PHASES:
            d = p["phases"][ph]
            if not d["reached"]:
                continue
            cnt = d["counts"]
            out.append(f"### {PHASE_FI[ph]}: {d['moves']} siirtoa, tarkkuus {_pct(d['accuracy'])} "
                       f"(?! {cnt['inaccuracy']}, ? {cnt['mistake']}, ?? {cnt['blunder']})")
            out += [f"- {w['text']}" for w in d["worst_moves"]]
            out += [f"- ✓ {m['text']}" for m in d["good_moments"]]
            out.append("")
        if p["observations"]:
            out += ["### Havainnot"] + [f"- {o['text']}" for o in p["observations"]] + [""]
        out += ["### Aikakontrolli ja pelin pituus"] + [f"- {a}" for a in p["time_control_advice"]] + [""]
        out.append("### Mitä kannattaa opetella")
        for lp in p["learning_priorities"]:
            ev = ", ".join(str(e) for e in lp["evidence"])
            out.append(f"{lp['rank']}. **{lp['title']}**: {lp['practice']} (näyttö: plyt {ev})")
        if p["skip_for_now"]:
            out += ["", "**Voit jättää toistaiseksi:**"] + [f"- {s}" for s in p["skip_for_now"]]
        out.append("")
    out += ["## Rajoitteet"] + [f"- {l}" for l in r["limitations"]]
    return "\n".join(out)


CSS = """
:root{--bg:#f6f5f2;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e3e1dc}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe7;--muted:#a3a29c;--card:#22221f;--line:#34332f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:19px;margin:32px 0 8px}h3{font-size:16px;margin:20px 0 6px}
.meta{color:var(--muted)}.pills span{display:inline-block;padding:2px 10px;border:1px solid var(--line);
border-radius:99px;margin:4px 6px 0 0;font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.km{display:grid;grid-template-columns:300px 1fr;gap:16px;align-items:start}
@media (max-width:640px){.km{grid-template-columns:1fr}.km svg{max-width:100%;height:auto}}
.cls{font-weight:600}.big{font-size:28px;font-weight:700}
.moves{display:flex;flex-wrap:wrap;gap:4px}.mv{padding:2px 7px;border-radius:5px;border:1px solid var(--line);font-size:13px}
ol li{margin-bottom:6px}.muted{color:var(--muted);font-size:13px}
"""


def to_html(r: dict) -> str:
    g = r["game"]
    e = html.escape
    flip = r["perspective"] == "black"
    moves = r["moves"]
    parts = [f"<!doctype html><html lang='fi'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Shakkianalyysi</title><style>{CSS}</style></head><body><main>",
             f"<h1>{e(str(g['white']))} – {e(str(g['black']))} &nbsp;{e(str(g['result']))}</h1>",
             f"<div class='meta'>{e(str(g.get('date') or ''))} · {e(str(g.get('termination') or ''))}</div>",
             "<div class='pills'>"
             f"<span>⏱ {e(str(g['time_control']['raw']))} = {e(g['time_control']['category_fi'])}</span>"
             f"<span>{g['length']['full_moves']} siirtoa = {e(g['length']['category_fi'])} peli</span>"
             f"<span>{e(str(g.get('eco') or ''))} {e(str(g.get('opening') or ''))}</span>"
             f"<span>Stockfish syvyys {r['engine']['depth']}</span></div>"]

    # Move strip
    parts.append("<h2>Siirrot</h2><div class='moves'>")
    for m in moves:
        col = CLASS_COLOR[m["classification"]]
        num = f"{m['move_number']}." if m["color"] == "white" else ""
        parts.append(f"<span class='mv' title='{e(CLASS_FI[m['classification']])}, {m['eval_after']}' "
                     f"style='border-color:{col}'>{num}{e(m['san'])}"
                     f"<b style='color:{col}'>{e(m['nag'] or '')}</b></span>")
    parts.append("</div>")

    # Key moments with boards
    parts.append("<h2>Avainhetket</h2>")
    for km in r["key_moments"]:
        m = moves[km["ply"] - 1]
        col = CLASS_COLOR[m["classification"]]
        parts.append(f"<div class='card km'>{board_svg(m, flip=flip)}<div>"
                     f"<div class='cls' style='color:{col}'>{e(CLASS_FI[m['classification']])}"
                     f" · {e(PHASE_FI[m['phase']])}</div><p>{e(km['text'])}</p>"
                     f"<p class='muted'>Arvio ennen {e(m['eval_before'])}, jälkeen {e(m['eval_after'])}. "
                     f"Vihreä nuoli = moottorin paras siirto.</p></div></div>")

    colors = [r["perspective"]] if r["perspective"] else ["white", "black"]
    for c in colors:
        p = r["players"][c]
        parts.append(f"<h2>{e(str(p['name']))} ({'valkea' if c == 'white' else 'musta'})</h2>")
        parts.append("<div class='grid'>")
        parts.append(f"<div class='card'><div class='muted'>Tarkkuus</div><div class='big'>{_pct(p['accuracy'])}</div>"
                     f"<div class='muted'>?! {p['counts']['inaccuracy']} · ? {p['counts']['mistake']} · "
                     f"?? {p['counts']['blunder']}</div></div>")
        for ph in PHASES:
            d = p["phases"][ph]
            if not d["reached"]:
                parts.append(f"<div class='card'><div class='muted'>{PHASE_FI[ph]}</div>"
                             f"<div class='big'>–</div><div class='muted'>ei saavutettu</div></div>")
                continue
            parts.append(f"<div class='card'><div class='muted'>{PHASE_FI[ph]} · {d['moves']} siirtoa</div>"
                         f"<div class='big'>{_pct(d['accuracy'])}</div><div class='muted'>?! {d['counts']['inaccuracy']}"
                         f" · ? {d['counts']['mistake']} · ?? {d['counts']['blunder']}</div></div>")
        parts.append("</div>")
        for ph in PHASES:
            d = p["phases"][ph]
            if d["reached"] and (d["worst_moves"] or d["good_moments"]):
                parts.append(f"<h3>{PHASE_FI[ph]}</h3><ul>")
                parts += [f"<li>{e(w['text'])}</li>" for w in d["worst_moves"]]
                parts += [f"<li>✓ {e(gm['text'])}</li>" for gm in d["good_moments"]]
                parts.append("</ul>")
        if p["observations"]:
            parts.append("<h3>Havainnot</h3><ul>" + "".join(f"<li>{e(o['text'])}</li>" for o in p["observations"]) + "</ul>")
        parts.append("<h3>Aikakontrolli ja pelin pituus</h3><ul>"
                     + "".join(f"<li>{e(a)}</li>" for a in p["time_control_advice"]) + "</ul>")
        parts.append("<h3>Mitä kannattaa opetella</h3><ol>")
        for lp in p["learning_priorities"]:
            parts.append(f"<li><b>{e(lp['title'])}</b>: {e(lp['practice'])} "
                         f"<span class='muted'>(näyttö: plyt {', '.join(map(str, lp['evidence']))})</span></li>")
        parts.append("</ol>")
        if p["skip_for_now"]:
            parts.append("<h3>Voit jättää toistaiseksi</h3><ul>"
                         + "".join(f"<li>{e(s)}</li>" for s in p["skip_for_now"]) + "</ul>")

    parts.append("<h2>Rajoitteet</h2><ul>" + "".join(f"<li class='muted'>{e(l)}</li>" for l in r["limitations"]) + "</ul>")
    parts.append("</main></body></html>")
    return "".join(parts)
