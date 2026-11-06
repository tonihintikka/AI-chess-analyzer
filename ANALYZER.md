# Analysaattori: faktat ensin, esitys erikseen

Työnjako:

- **Analysaattori** (`backend/app/analyzer/`) laskee faktat deterministisesti:
  Stockfish-arviot, siirtojen luokittelun, pelivaiheet, aikakontrollin ja pelin pituuden
  sekä sääntöpohjaiset havainnot ja oppimisprioriteetit. Se ei tee LLM-kutsuja.
- **Tekoälytyökalu** (Claude Code, Codex, Cursor, oma frontend…) lukee JSON-raportin ja
  esittää sen. Sen tehtävä on selittää ja visualisoida, ei keksiä uusia arvioita.

## Käyttö

```bash
cd backend
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
brew install stockfish   # tai STOCKFISH_PATH=/polku/stockfishiin

# JSON stdoutiin (putkitettavissa tekoälytyökalulle)
.venv/bin/python -m app.analyzer peli.pgn --player tonhin

# Tiedostot: JSON + HTML-raportti, jossa on laudat avainhetkistä
.venv/bin/python -m app.analyzer peli.pgn --player tonhin --json reports/peli.json --html reports/peli.html

# Ihmisluettava tiivistelmä
.venv/bin/python -m app.analyzer peli.pgn --player tonhin --md

# PGN stdinistä
pbpaste | .venv/bin/python -m app.analyzer - --player tonhin --md
```

HTTP: `POST /api/engine-report?player=tonhin&depth=14` ja body `{"pgn": "..."}`. Palauttaa saman JSONin.
Vanha `/api/analyze` (GPT-pohjainen) on ennallaan.

## Ohje esittävälle tekoälylle

1. Käytä vain raportin kenttiä. Jokaisella havainnolla on `evidence` (ply-numerot), joten näytä asema
   `moves[ply-1].fen_after` ja tarvittaessa `best_move_san` / `best_line_san`.
2. Jos `perspective` on asetettu, puhu sille pelaajalle (`players[perspective]`). Vastustajan
   raportti on kontekstia.
3. Kerro rajoitteet (`limitations`), etenkin avauskirjan puuttuminen ja saavuttamattomat vaiheet.
4. Älä muuta luokitteluja. Jos olet eri mieltä, sano se erikseen omana tulkintanasi.

## JSON-skeema (v1.0, tiivistetty)

```text
schema_version        "1.0"
game
  white, black, white_elo, black_elo, result, termination, date, eco, opening, link
  time_control        {raw, base_seconds, increment_seconds, estimated_seconds,
                       category: ultrabullet|bullet|blitz|rapid|classical|daily|unknown, category_fi}
  length              {plies, full_moves, category: short(<=25)|medium(<=60)|long, category_fi}
  phases_reached      ["opening","middlegame","endgame"]
  has_clock_data      bool   (PGN:n [%clk]-kommentit)
  final_fen
engine                {name, depth}
perspective           "white"|"black"|null
players.{white,black}
  name, elo, accuracy, counts{best,excellent,good,forced,inaccuracy,mistake,blunder}
  phases.{opening,middlegame,endgame}
    reached, moves, accuracy, counts, worst_moves[{ply,text}], good_moments[{ply,text}]
  observations[]      {id, phase, severity: info|warning, text, evidence[ply]}
                      id: queen_moves_early | flank_pawn | slow_development | no_castle |
                          time_trouble | long_thinks | avg_time_per_phase
  time_control_advice[]   aikakontrolli- ja pituuskohtaiset vinkit
  learning_priorities[]   {rank, topic, title, practice, score, evidence[ply]}  (max 3)
  skip_for_now[]          mitä ei kannata vielä opetella (tasoon sidottu)
key_moments[]         {ply, reason: error|mate|punished, color, text}
moves[]               (yksi per ply)
  ply, move_number, color, san, uci, fen_before, fen_after, phase
  eval_before, eval_after          valkean näkökulmasta, esim. "+0.35" tai "#-1"
  cp_before_white, cp_after_white
  best_move_san, best_move_uci, best_line_san[], opponent_best_reply_san
  win_before, win_after, win_loss  siirtäjän voitto-odotus 0..100 (Lichessin malli)
  accuracy                         0..100 (Lichessin siirtokohtainen kaava)
  classification                   best|excellent|good|forced|inaccuracy|mistake|blunder
  nag                              "?!", "?", "??" tai null
  clock_seconds, time_spent_seconds
  tags[]               delivered_mate, missed_mate, allowed_mate, lost_material, allowed_tactic,
                       missed_capture, missed_punishment, queen_move_opening,
                       flank_pawn_opening, castled
  tag_details{}        taktisten tagien yksityiskohdat (linjat, nappula, ruutu)
limitations[]
```

## Luokittelu

Siirtäjän voitto-odotuksen pudotus (%-yksikköä): alle 2 erinomainen, alle 5 hyvä, alle 10
epätarkkuus, alle 20 virhe, vähintään 20 vakava virhe. Moottorin paras siirto on aina `best`,
ja ainoa laillinen siirto on `forced`.

## Tunnetut rajoitteet

- Avauskirjaa ei ole, joten teoriassa hyväksyttyjä avaussiirtoja voidaan merkitä epätarkkuuksiksi.
- Pelivaiheet päätellään heuristisesti (materiaali ja takarivin kehitys).
- Tarkkuus on keskiarvo, eikä se ole suoraan verrattavissa chess.comin tarkkuuslukuun.
- Kelloanalyysi vaatii `[%clk]`-kommentit PGN:ssä.
