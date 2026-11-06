"""Rule-based coaching layer on top of engine facts.

Produces a JSON-serialisable report. Every observation points to the plies
(evidence) it is based on, so a presenting AI tool can show the position and
must not invent new claims.
"""
from __future__ import annotations

import io
from collections import Counter
from typing import Optional

import chess
import chess.pgn

from .engine import PlyAnalysis, analyze_game
from .openings import annotate_book
from .opendata import OpenData, annotate_tablebase, explorer_summary

SCHEMA_VERSION = "1.1"
PHASES = ["opening", "middlegame", "endgame"]
PHASE_FI = {"opening": "Avaus", "middlegame": "Keskipeli", "endgame": "Loppupeli"}
CLASS_FI = {
    "book": "kirjasiirto", "best": "paras", "excellent": "erinomainen", "good": "hyvä", "forced": "pakkosiirto",
    "inaccuracy": "epätarkkuus", "mistake": "virhe", "blunder": "vakava virhe",
}
ERROR_CLASSES = ("inaccuracy", "mistake", "blunder")

TOPICS = {
    "blunder_check": {
        "resources": [{"title": "Lichess: suojaamaton nappula", "url": "https://lichess.org/training/hangingPiece"}, {"title": "Lichess: puolustussiirto", "url": "https://lichess.org/training/defensiveMove"}],
        "title": "Tarkistus ennen siirtoa: shakit, lyönnit ja uhat",
        "practice": "Kysy ennen jokaista siirtoa: mitä vastustaja voi lyödä tai millä shakata, "
                    "jos teen tämän? Tee taktiikkatehtäviä 10 min/päivä teemalla 'hanging piece'.",
    },
    "mate_patterns": {
        "resources": [{"title": "Lichess: matti 1 siirrossa", "url": "https://lichess.org/training/mateIn1"}, {"title": "Lichess: matti 2 siirrossa", "url": "https://lichess.org/training/mateIn2"}, {"title": "Lichess: kuningassivun hyökkäys", "url": "https://lichess.org/training/kingsideAttack"}],
        "title": "Mattikuviot ja kuninkaan turvallisuus",
        "practice": "Ratkaise 'matti 1–2 siirrossa' -tehtäviä (esim. Lichessin mateIn1/mateIn2-teemat). "
                    "Seuraa erityisesti avautuvia linjoja kuninkaan edessä (h- ja g-linja).",
    },
    "tactics_material": {
        "resources": [{"title": "Lichess: haarukka", "url": "https://lichess.org/training/fork"}, {"title": "Lichess: kiinnitys", "url": "https://lichess.org/training/pin"}, {"title": "Lichess: suojaamaton nappula", "url": "https://lichess.org/training/hangingPiece"}],
        "title": "Taktiikka: vapaa materiaali, haarukka ja kiinnitys",
        "practice": "Etsi joka siirrolla suojaamattomat nappulat molemmilta puolilta. "
                    "Tehtäväteemat: hangingPiece, fork, pin.",
    },
    "punish_mistakes": {
        "resources": [{"title": "Lichess: etu (advantage)", "url": "https://lichess.org/training/advantage"}, {"title": "Lichess: hiljainen siirto", "url": "https://lichess.org/training/quietMove"}],
        "title": "Vastustajan virheiden rankaiseminen",
        "practice": "Kun vastustaja tekee yllättävän siirron, pysähdy ja kysy: mitä se jätti "
                    "suojaamatta, ja mikä muuttui edellisestä siirrosta?",
    },
    "opening_principles": {
        "resources": [{"title": "Lichess: avaustehtävät", "url": "https://lichess.org/training/opening"}, {"title": "Lichess Learn: perusteet", "url": "https://lichess.org/learn"}],
        "title": "Avausperiaatteet",
        "practice": "Kehitä ratsut ja lähetit, linnoita ajoissa ja vältä saman nappulan "
                    "toistuvia siirtoja. Opettele 1–2 avausta periaatteiden kautta, älä ulkoa.",
    },
    "middlegame_plans": {
        "resources": [{"title": "Lichess: keskipelitehtävät", "url": "https://lichess.org/training/middlegame"}],
        "title": "Keskipelin suunnitelmat ja nappuloiden aktiivisuus",
        "practice": "Etsi asemasta heikoin nappulasi ja paranna sitä. Kun et keksi siirtoa, "
                    "kysy, mihin vastustaja on menossa.",
    },
    "endgame_technique": {
        "resources": [{"title": "Lichess Practice: perusloppupelit", "url": "https://lichess.org/practice"}, {"title": "Lichess: loppupelitehtävät", "url": "https://lichess.org/training/endgame"}],
        "title": "Loppupelitekniikka",
        "practice": "Kuninkaan aktivointi, vapaasotilaat ja perusloppupelit "
                    "(K+T vs K, sotilasloppupelien oppositio).",
    },
    "time_management": {
        "resources": [{"title": "Lichess Puzzle Storm (nopeusharjoitus)", "url": "https://lichess.org/storm"}],
        "title": "Ajankäyttö",
        "practice": "Käytä aikaa kriittisiin hetkiin (vaihdot, avautuva kuningas) ja pelaa "
                    "rutiinisiirrot nopeasti. Pidä aina varalla aikaa loppua varten.",
    },
}

TC_FI = {"ultrabullet": "ultrabullet", "bullet": "bullet", "blitz": "blitz",
         "rapid": "pikapeli (rapid)", "classical": "pitkä peli (klassinen)",
         "daily": "kirjeshakki", "unknown": "tuntematon"}


# --------------------------------------------------------------------------- game meta

def parse_time_control(raw: Optional[str]) -> dict:
    out = {"raw": raw, "base_seconds": None, "increment_seconds": None,
           "estimated_seconds": None, "category": "unknown"}
    if not raw or raw in ("-", "?"):
        return out
    if "/" in raw:
        out["category"] = "daily"
        return out
    try:
        base, _, inc = raw.partition("+")
        base_s, inc_s = int(base), int(inc or 0)
    except ValueError:
        return out
    est = base_s + 40 * inc_s  # Lichess definition
    out.update(base_seconds=base_s, increment_seconds=inc_s, estimated_seconds=est)
    if est < 30:
        out["category"] = "ultrabullet"
    elif est < 180:
        out["category"] = "bullet"
    elif est < 480:
        out["category"] = "blitz"
    elif est < 1500:
        out["category"] = "rapid"
    else:
        out["category"] = "classical"
    return out


def game_length(plies: int) -> dict:
    full = (plies + 1) // 2
    if full <= 25:
        cat, fi = "short", "lyhyt"
    elif full <= 60:
        cat, fi = "medium", "keskipitkä"
    else:
        cat, fi = "long", "pitkä"
    return {"plies": plies, "full_moves": full, "category": cat, "category_fi": fi}


def _int(v: Optional[str]) -> Optional[int]:
    try:
        return int(v) if v else None
    except ValueError:
        return None


# --------------------------------------------------------------------------- helpers

def move_label(p: PlyAnalysis) -> str:
    return f"{p.move_number}.{'' if p.color == 'white' else '..'} {p.san}"


def tag_text(p: PlyAnalysis, tag: str) -> Optional[str]:
    d = p.tag_details.get(tag, {})
    if tag == "lost_material":
        return f"Siirron jälkeen vastustaja voi lyödä: {d['reply']} ({d['piece']} ruudussa {d['square']})."
    if tag == "allowed_mate":
        return f"Siirto salli matin {d['mate_in']} siirrossa: {' '.join(d['line'])}."
    if tag == "missed_mate":
        return f"Matti {d['mate_in']} siirrossa oli tarjolla: {' '.join(d['line'])}."
    if tag == "missed_capture":
        return f"Vapaa {d['piece']} jäi lyömättä: {d['best']}."
    if tag == "missed_punishment":
        return f"Vastustajan virhe {d['opponent_move']} jäi rankaisematta, paras oli {d['best']}."
    if tag in ("tb_threw_win", "tb_threw_draw"):
        d = p.tag_details.get("tablebase", {})
        return (f"Tablebase: asema oli {d['before_fi']}, siirron jälkeen {d['after_fi']}. "
                f"Tarkka siirto oli {d['best_san']}.")
    if tag == "allowed_tactic":
        return f"Siirto salli vastustajalle shakkiin perustuvan iskun: {' '.join(d['line'])}."
    return None


TACTICAL_TAGS = ("allowed_mate", "missed_mate", "lost_material", "missed_capture",
                 "missed_punishment", "allowed_tactic", "tb_threw_win", "tb_threw_draw")


def describe_move(p: PlyAnalysis) -> str:
    parts = [f"{move_label(p)} – {CLASS_FI[p.classification]} "
             f"(voitto-odotus {p.win_before:.0f} % → {p.win_after:.0f} %)."]
    if p.best_move_san and p.best_move_san != p.san:
        parts.append(f"Moottorin paras: {p.best_move_san}.")
    for t in TACTICAL_TAGS:
        if t in p.tags:
            parts.append(tag_text(p, t))
    return " ".join(x for x in parts if x)


def _accuracy(moves: list[PlyAnalysis]) -> Optional[float]:
    moves = [m for m in moves if not m.book]
    if not moves:
        return None
    return round(sum(m.accuracy for m in moves) / len(moves), 1)


def _counts(moves: list[PlyAnalysis]) -> dict:
    c = Counter(m.classification for m in moves)
    return {k: c.get(k, 0) for k in CLASS_FI}


# --------------------------------------------------------------------------- per player

def _opening_habits(color: str, mine: list[PlyAnalysis], all_plies: list[PlyAnalysis]) -> list[dict]:
    obs = []
    queen = [m for m in mine if "queen_move_opening" in m.tags and not m.book]
    if len(queen) >= 3:
        costly = [m for m in queen if m.win_loss >= 5]
        obs.append({
            "id": "queen_moves_early", "phase": "opening",
            "severity": "warning" if costly else "info",
            "text": f"Kuningatar liikkui avausvaiheessa kirjan jälkeen {len(queen)} kertaa. Jokainen ylimääräinen "
                    f"kuningatarsiirto on pois kehityksestä, ja vastustaja voi voittaa tempoja "
                    f"hyökkäämällä sitä vastaan."
                    + (f" Näistä {len(costly)} maksoi moottorin mukaan selvästi." if costly else ""),
            "evidence": [m.ply for m in queen],
        })
    for m in mine:
        if "flank_pawn_opening" in m.tags and m.win_loss >= 5:
            obs.append({
                "id": "flank_pawn", "phase": "opening", "severity": "warning",
                "text": f"{move_label(m)}: reunasotilaan siirto avauksessa maksoi "
                        f"{m.win_loss:.0f} %-yksikköä. Kehitys tai keskusta olisi ollut tärkeämpää.",
                "evidence": [m.ply],
            })
    # Development and castling after the player's 10th / 12th move.
    tenth = next((m for m in mine if m.move_number == 10), None)
    if tenth:
        b = chess.Board(tenth.fen_after)
        c = chess.WHITE if color == "white" else chess.BLACK
        rank = 0 if c == chess.WHITE else 7
        home = [chess.square(f, rank) for f in (1, 2, 5, 6)]
        undeveloped = [sq for sq in home if (p := b.piece_at(sq)) and p.color == c
                       and p.piece_type in (chess.KNIGHT, chess.BISHOP)]
        if len(undeveloped) >= 2:
            obs.append({
                "id": "slow_development", "phase": "opening", "severity": "warning",
                "text": f"10. siirron jälkeen {len(undeveloped)} kevyttä upseeria oli vielä "
                        f"lähtöruuduissa ({', '.join(chess.square_name(s) for s in undeveloped)}).",
                "evidence": [tenth.ply],
            })
    if len(mine) >= 12 and not any("castled" in m.tags for m in mine):
        b = chess.Board(mine[11].fen_after)
        if b.queens:
            obs.append({
                "id": "no_castle", "phase": "opening", "severity": "warning",
                "text": "Kuningas ei linnoittautunut 12 siirron aikana, vaikka kuningattaret olivat laudalla.",
                "evidence": [mine[11].ply],
            })
    return obs


def _clock_observations(mine: list[PlyAnalysis], tc: dict) -> list[dict]:
    clocked = [m for m in mine if m.clock_seconds is not None]
    if not clocked or not tc.get("base_seconds"):
        return []
    base = tc["base_seconds"]
    obs = []
    low = [m for m in clocked if m.clock_seconds < 0.1 * base]
    if low:
        errs = [m for m in low if m.classification in ERROR_CLASSES]
        obs.append({
            "id": "time_trouble", "phase": low[0].phase, "severity": "warning" if errs else "info",
            "text": f"{len(low)} siirtoa pelattiin alle 10 %:n ajalla ({0.1 * base:.0f} s). "
                    f"Niistä {len(errs)} oli epätarkkuuksia tai virheitä.",
            "evidence": [m.ply for m in low],
        })
    long_thinks = [m for m in clocked if m.time_spent_seconds and m.time_spent_seconds > 0.15 * base]
    if long_thinks:
        obs.append({
            "id": "long_thinks", "phase": long_thinks[0].phase, "severity": "info",
            "text": f"{len(long_thinks)} siirrossa kului yli 15 % peruskellosta.",
            "evidence": [m.ply for m in long_thinks],
        })
    per_phase = {}
    for ph in PHASES:
        spent = [m.time_spent_seconds for m in clocked if m.phase == ph and m.time_spent_seconds is not None]
        if spent:
            per_phase[ph] = round(sum(spent) / len(spent), 1)
    if per_phase:
        txt = ", ".join(f"{PHASE_FI[k].lower()} {v} s" for k, v in per_phase.items())
        obs.append({"id": "avg_time_per_phase", "phase": None, "severity": "info",
                    "text": f"Keskimääräinen siirtoaika: {txt}.", "evidence": []})
    return obs


def _time_control_advice(tc: dict, length: dict, has_clock: bool) -> list[str]:
    cat = tc["category"]
    inc = tc.get("increment_seconds")
    adv = []
    if cat in ("bullet", "ultrabullet"):
        adv += ["Bulletissa ratkaisee yksinkertaisuus: pelaa tuttuja avausrakenteita ja vältä "
                "terävää teoriaa, jota et muista.",
                "Älä tee ennakkosiirtoja (premove) asemissa, joissa vastustajalla on lyöntejä tai shakkeja."]
    elif cat == "blitz":
        adv += ["Blitzissä tarkista nopeasti shakit, lyönnit ja uhat ainakin, kun vastustajan siirto muuttaa "
                "asemaa (lyönti, uusi hyökkäys tai linja aukeaa).",
                "Pelaa avaus rutiinilla, jotta keskipelin kriittisiin hetkiin jää aikaa."]
        if inc:
            adv.append(f"Inkrementti on {inc} s/siirto. 40 siirron pelissä se tuo noin {40 * inc} s lisäaikaa, "
                       f"joten lopussa ei tarvitse paniikkia, jos kellossa on yli 20 s.")
    elif cat == "rapid":
        adv += ["Pikapelissä ehdit laskea: valitse kriittisissä asemissa 2–3 ehdokassiirtoa ja vertaa niitä.",
                "Käytä enemmän aikaa, kun materiaali vaihtuu tai kuningas avautuu, ja vähemmän rutiinisiirtoihin."]
    elif cat == "classical":
        adv += ["Pitkässä pelissä laske pakottavat linjat loppuun ja tee suunnitelma ennen siirtoa.",
                "Varaa aikaa myös loppupeliin. Klassisen pelin tappiot syntyvät usein aikapulassa."]
    if length["category"] == "short":
        adv.append("Lyhyt peli: ratkaisu syntyi avauksessa tai varhaisessa keskipelissä, yleensä taktiikalla. "
                   "Pelistä ei saa dataa loppupelitaidoista.")
    elif length["category"] == "long":
        adv.append("Pitkä peli: kestävyys, ajankäyttö ja loppupelitekniikka korostuvat.")
        if cat in ("bullet", "blitz"):
            adv.append("Pitkä nopea peli lisää aikapulan riskiä. Seuraa, missä vaiheessa virheet alkavat kasaantua.")
    if not has_clock:
        adv.append("PGN:ssä ei ole kelloaikoja ([%clk]), joten ajankäyttöä ei voitu analysoida.")
    return adv


def _learning_priorities(mine: list[PlyAnalysis], habits: list[dict], clock_obs: list[dict],
                         elo: Optional[int]) -> tuple[list[dict], list[str]]:
    score: Counter = Counter()
    evidence: dict[str, list[int]] = {k: [] for k in TOPICS}

    def add(topic, pts, ply=None):
        score[topic] += pts
        if ply is not None and ply not in evidence[topic]:
            evidence[topic].append(ply)

    for m in mine:
        heavy = 2 if m.classification in ("mistake", "blunder") else 1
        tagged = False
        if "lost_material" in m.tags or "allowed_tactic" in m.tags:
            add("blunder_check", 3, m.ply); tagged = True
        if "allowed_mate" in m.tags:
            add("mate_patterns", 4, m.ply); add("blunder_check", 1, m.ply); tagged = True
        if "missed_mate" in m.tags:
            add("mate_patterns", 4, m.ply); tagged = True
        if "missed_capture" in m.tags:
            add("tactics_material", 2, m.ply); tagged = True
        if "missed_punishment" in m.tags:
            add("punish_mistakes", 3, m.ply); tagged = True
        if "tb_threw_win" in m.tags or "tb_threw_draw" in m.tags:
            add("endgame_technique", 4, m.ply); tagged = True
        if m.classification in ERROR_CLASSES and not tagged:
            topic = {"opening": "opening_principles", "middlegame": "middlegame_plans",
                     "endgame": "endgame_technique"}[m.phase]
            add(topic, heavy * (2 if m.phase == "endgame" else 1), m.ply)
    for h in habits:
        if h["severity"] == "warning":
            add("opening_principles", 2)
            evidence["opening_principles"].extend(p for p in h["evidence"] if p not in evidence["opening_principles"])
    for c in clock_obs:
        if c["id"] == "time_trouble" and c["severity"] == "warning":
            add("time_management", 3)
            evidence["time_management"].extend(c["evidence"])

    low_rated = elo is not None and elo < 1200
    if low_rated:
        for t in ("blunder_check", "mate_patterns", "tactics_material", "punish_mistakes"):
            score[t] *= 1.5
        score["middlegame_plans"] *= 0.5

    ranked = [t for t, s in score.most_common() if s > 0][:3]
    priorities = [{
        "rank": i + 1, "topic": t, "title": TOPICS[t]["title"], "practice": TOPICS[t]["practice"],
        "resources": TOPICS[t]["resources"],
        "score": round(score[t], 1), "evidence": sorted(evidence[t]),
    } for i, t in enumerate(ranked)]

    skip = []
    if low_rated:
        skip += ["Syvä avausteoria ja ulkoa opetellut linjat: tällä tasolla pelit ratkeavat taktiikkaan.",
                 "Hienovarainen asemapelistrategia (heikot ruudut, sotilasrakenteet) ennen kuin "
                 "nappulat pysyvät suojattuina."]
    return priorities, skip


def _player_report(color: str, plies: list[PlyAnalysis], headers, tc: dict, length: dict,
                   opening: Optional[dict] = None) -> dict:
    mine = [p for p in plies if p.color == color]
    elo = _int(headers.get("WhiteElo" if color == "white" else "BlackElo"))
    phases = {}
    for ph in PHASES:
        pm = [m for m in mine if m.phase == ph]
        if not pm:
            phases[ph] = {"reached": False, "moves": 0}
            continue
        worst = sorted([m for m in pm if m.classification in ERROR_CLASSES],
                       key=lambda m: m.win_loss, reverse=True)[:3]
        phases[ph] = {
            "reached": True, "moves": len(pm), "accuracy": _accuracy(pm), "counts": _counts(pm),
            "worst_moves": [{"ply": m.ply, "text": describe_move(m)} for m in worst],
            "good_moments": [{"ply": m.ply, "text": f"{move_label(m)}: löysit moottorin parhaan siirron "
                                                    f"tilanteessa, jossa sillä oli väliä."}
                             for m in pm if m.classification == "best" and
                             (any(t in m.tags for t in ("delivered_mate",)) or
                              (m.ply > 1 and plies[m.ply - 2].classification in ("mistake", "blunder")))],
        }
    habits = _opening_habits(color, mine, plies)
    dev = (opening or {}).get("deviation")
    if dev and dev["color"] == color:
        alts = ", ".join(dev["book_alternatives"][:6]) or "–"
        cls = dev["classification"]
        ok = cls not in ERROR_CLASSES
        habits.insert(0, {
            "id": "left_book", "phase": "opening", "severity": "info" if ok else "warning",
            "text": f"Poistuit avauskirjasta siirrolla {dev['move_number']}.{'' if color == 'white' else '..'} "
                    f"{dev['san']} ({CLASS_FI[cls]}). Kirjan jatkot: {alts}. Moottorin paras: {dev['engine_best']}.",
            "evidence": [dev["ply"]],
        })
    clock_obs = _clock_observations(mine, tc)
    priorities, skip = _learning_priorities(mine, habits, clock_obs, elo)
    if opening and opening.get("lichess_url"):
        for lp in priorities:
            if lp["topic"] == "opening_principles":
                lp["resources"] = [{"title": f"Lichess: {opening['name']}", "url": opening["lichess_url"]}] + lp["resources"]
    has_clock = any(p.clock_seconds is not None for p in plies)
    return {
        "color": color,
        "name": headers.get("White" if color == "white" else "Black"),
        "elo": elo,
        "accuracy": _accuracy(mine),
        "counts": _counts(mine),
        "phases": phases,
        "observations": habits + clock_obs,
        "time_control_advice": _time_control_advice(tc, length, has_clock),
        "learning_priorities": priorities,
        "skip_for_now": skip,
    }


def _key_moments(plies: list[PlyAnalysis], limit: int = 6) -> list[dict]:
    picks = []
    for p in plies:
        reason = None
        if p.classification in ("mistake", "blunder") or any(t in p.tags for t in TACTICAL_TAGS):
            reason = "error"
        elif "delivered_mate" in p.tags:
            reason = "mate"
        elif p.classification == "best" and p.ply > 1 and plies[p.ply - 2].classification == "blunder":
            reason = "punished"
        if reason:
            picks.append((p, reason))
    picks.sort(key=lambda x: (x[1] != "mate", -x[0].win_loss))
    chosen = sorted(picks[:limit], key=lambda x: x[0].ply)
    return [{"ply": p.ply, "reason": r, "color": p.color,
             "lichess_analysis_url": "https://lichess.org/analysis/standard/" + p.fen_before.replace(" ", "_"),
             "text": describe_move(p) if r == "error"
             else (f"{move_label(p)} – matti." if r == "mate"
                   else f"{move_label(p)} – vastustajan vakava virhe rangaistiin.")}
            for p, r in chosen]


# --------------------------------------------------------------------------- entry point

def build_report(pgn_text: str, player: Optional[str] = None, depth: int = 14,
                 engine_path: Optional[str] = None, online: bool = False,
                 lichess_token: Optional[str] = None) -> dict:
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is not None and game.errors:
        raise ValueError(f"PGN-virhe: {game.errors[0]}")
    if game is None or game.next() is None:
        raise ValueError("PGN ei sisällä siirtoja.")
    h = game.headers
    plies = analyze_game(game, depth=depth, engine_path=engine_path)
    tc = parse_time_control(h.get("TimeControl"))
    tc["category_fi"] = TC_FI[tc["category"]]
    length = game_length(len(plies))

    opening = annotate_book(plies)
    for p in plies:
        if p.book:
            p.classification, p.nag, p.accuracy = "book", None, 100.0

    perspective = None
    if player:
        if h.get("White", "").lower() == player.lower():
            perspective = "white"
        elif h.get("Black", "").lower() == player.lower():
            perspective = "black"

    open_data = {"online": online, "sources": [opening["source"]], "notes": []}
    if online:
        od = OpenData(token=lichess_token)
        n = annotate_tablebase(plies, od)
        if n:
            open_data["sources"].append("Lichess Syzygy tablebase")
        dev = opening.get("deviation")
        if dev:
            fen = plies[dev["ply"] - 1].fen_before
            elo_color = perspective or dev["color"]
            elo = _int(h.get("WhiteElo" if elo_color == "white" else "BlackElo"))
            speed = tc["category"] if tc["category"] in ("bullet", "blitz", "rapid", "classical") else None
            if od.token:
                opening["explorer"] = {
                    "position_ply": dev["ply"],
                    "filters": {"speed": speed, "rating_from": elo},
                    "lichess": explorer_summary(od.explorer(fen, "lichess", speed, elo), dev["san"]),
                    "masters": explorer_summary(od.explorer(fen, "masters"), dev["san"]),
                }
                open_data["sources"].append("Lichess opening explorer")
            else:
                od.notes.append("Opening explorer ohitettiin, koska LICHESS_TOKEN puuttuu.")
        od.save()
        open_data["notes"] = od.notes

    phases_reached = [ph for ph in PHASES if any(p.phase == ph for p in plies)]
    limitations = [
        f"Stockfish syvyydellä {depth}. Avauskirjana on Lichessin nimettyjen avausten tietokanta: se ei ole "
        f"täysi teoriapuu, joten poistuminen kirjasta ei tarkoita, että siirto olisi huono.",
        "Pelivaiheet on päätelty heuristisesti materiaalin ja kehityksen perusteella.",
        "Tarkkuus on siirtokohtaisten tarkkuuksien keskiarvo (ei Lichessin painotettua kaavaa), "
        "joten se ei ole suoraan verrattavissa chess.comin lukuun.",
    ]
    missing = [PHASE_FI[ph] for ph in PHASES if ph not in phases_reached]
    if missing:
        limitations.append(f"Peli ei edennyt vaiheisiin: {', '.join(missing).lower()}. "
                           f"Niistä ei ole dataa tässä pelissä.")

    return {
        "schema_version": SCHEMA_VERSION,
        "game": {
            "white": h.get("White"), "black": h.get("Black"),
            "white_elo": _int(h.get("WhiteElo")), "black_elo": _int(h.get("BlackElo")),
            "result": h.get("Result"), "termination": h.get("Termination"),
            "date": h.get("Date"), "eco": h.get("ECO"),
            "opening": opening["name"] or h.get("Opening")
                       or (h.get("ECOUrl", "").rsplit("/", 1)[-1].replace("-", " ") or None),
            "eco_book": opening["eco"],
            "link": h.get("Link"),
            "time_control": tc, "length": length, "phases_reached": phases_reached,
            "has_clock_data": any(p.clock_seconds is not None for p in plies),
            "final_fen": plies[-1].fen_after,
        },
        "engine": {"name": "Stockfish", "depth": depth},
        "opening": opening,
        "open_data": open_data,
        "perspective": perspective,
        "players": {c: _player_report(c, plies, h, tc, length, opening) for c in ("white", "black")},
        "key_moments": _key_moments(plies),
        "moves": [p.to_dict() for p in plies],
        "limitations": limitations,
    }
