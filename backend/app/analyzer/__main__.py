"""CLI: python -m app.analyzer GAME.pgn [--player NAME] [--json out.json] [--html out.html] [--md]

Without output flags the JSON report is printed to stdout, so any AI tool can
pipe it: `python -m app.analyzer game.pgn --player tonhin | <ai tool>`.
Use `-` as the PGN path to read from stdin.
"""
import argparse
import json
import sys
from pathlib import Path

from .coach import build_report
from .render import to_html, to_markdown


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.analyzer", description="Shakkipelin moottorianalyysi")
    ap.add_argument("pgn", help="PGN-tiedosto tai '-' (stdin)")
    ap.add_argument("--player", help="Käyttäjänimi, jonka näkökulmasta raportoidaan")
    ap.add_argument("--depth", type=int, default=14, help="Stockfish-syvyys (oletus 14)")
    ap.add_argument("--engine", help="Stockfishin polku (oletus: PATH tai STOCKFISH_PATH)")
    ap.add_argument("--online", action="store_true",
                    help="Hae Lichessin avointa dataa: tablebase (<=7 nappulaa) ja explorer (vaatii LICHESS_TOKEN)")
    ap.add_argument("--json", dest="json_out", help="Kirjoita JSON-raportti tiedostoon")
    ap.add_argument("--html", dest="html_out", help="Kirjoita HTML-raportti laudoilla tiedostoon")
    ap.add_argument("--md", action="store_true", help="Tulosta Markdown-yhteenveto stdoutiin")
    a = ap.parse_args(argv)

    text = sys.stdin.read() if a.pgn == "-" else Path(a.pgn).read_text(encoding="utf-8")
    try:
        report = build_report(text, player=a.player, depth=a.depth, engine_path=a.engine, online=a.online)
    except (ValueError, RuntimeError) as e:
        print(f"Virhe: {e}", file=sys.stderr)
        return 1

    if a.json_out:
        Path(a.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.html_out:
        Path(a.html_out).write_text(to_html(report), encoding="utf-8")
    if a.md:
        print(to_markdown(report))
    elif not (a.json_out or a.html_out):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
