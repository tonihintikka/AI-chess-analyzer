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

# Avoin online-data: tablebase (<= 7 nappulaa) ja explorer (vaatii LICHESS_TOKEN)
.venv/bin/python -m app.analyzer peli.pgn --player tonhin --online --md

# PGN stdinistä
pbpaste | .venv/bin/python -m app.analyzer - --player tonhin --md
```

HTTP: `POST /api/engine-report?player=tonhin&depth=14&online=false` ja body `{"pgn": "..."}`. Palauttaa saman JSONin.
Vanha `/api/analyze` (GPT-pohjainen) on ennallaan.

## Avoin data

| Lähde | Mitä antaa | Käyttö | Lisenssi tai ehto |
|---|---|---|---|
| [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings) | Avauksen nimi, ECO, kirjasiirrot ja kirjasta poikkeamisen kohta | Aina, offline (`backend/app/analyzer/data/openings/`) | CC0 |
| [Lichess Syzygy tablebase](https://tablebase.lichess.ovh) | Tarkka tulos (voitto, tasapeli tai tappio) asemille, joissa on enintään 7 nappulaa; tunnistaa siirrot, jotka heittävät voiton tai tasapelin | `--online` | Avoin API ilman tunnistautumista |
| [Lichess opening explorer](https://lichess.org/api#tag/Opening-Explorer) | Suosio ja tulokset kirjasta poikkeamisen asemassa: samantasoiset Lichess-pelaajat samalla aikakontrollilla sekä mestaripelit | `--online` ja `LICHESS_TOKEN` | Vaatii Lichess-tunnisteen (marraskuu 2026: ilman tunnistetta HTTP 401) |
| Lichessin tehtäväteemat ja avaussivut | Linkit harjoituksiin jokaiselle oppimisprioriteetille sekä avaussivu | Aina (vain linkkejä) | – |

### Lichess-tunniste 1Passwordista

1. Luo tunniste osoitteessa https://lichess.org/account/oauth/token. Oikeuksia (scopes) ei tarvita.
2. Tallenna se 1Passwordiin API Credential -kohteeksi, esim. `Lichess API token` holviin `Private`.
3. `cp backend/.env.op.example backend/.env.op` ja korjaa viittaus (`op://<holvi>/<kohde>/<kenttä>`).
   Tiedosto sisältää vain viittauksen, ja se on gitignoressa.
4. Aja `backend/analyze.sh peli.pgn --player tonhin --online --md`. `op run` injektoi tunnisteen
   vain tälle prosessille ja peittää sen tulosteesta. Jos tunniste on ratkaisematon `op://`-viittaus,
   explorer ohitetaan ja asiasta tulee huomautus.

Lichessiin lähetetään vain FEN-asemia, ei pelaajanimiä. Vastaukset välimuistitetaan tiedostoon
`backend/.cache/opendata.json`. Jos Lichess palauttaa 429, odotetaan minuutti ja yritetään kerran uudelleen.
Kaikki epäonnistumiset kirjataan kenttään `open_data.notes`, eikä analyysi kaadu niihin.

## Ohje esittävälle tekoälylle

1. Käytä vain raportin kenttiä. Jokaisella havainnolla on `evidence` (ply-numerot), joten näytä asema
   `moves[ply-1].fen_after` ja tarvittaessa `best_move_san` / `best_line_san`.
2. Jos `perspective` on asetettu, puhu sille pelaajalle (`players[perspective]`). Vastustajan
   raportti on kontekstia.
3. Kerro rajoitteet (`limitations`), etenkin avauskirjan puuttuminen ja saavuttamattomat vaiheet.
4. Älä muuta luokitteluja. Jos olet eri mieltä, sano se erikseen omana tulkintanasi.

## JSON-skeema (v1.0, tiivistetty)

```text
schema_version        "1.1"
game
  white, black, white_elo, black_elo, result, termination, date, eco, opening, link
  time_control        {raw, base_seconds, increment_seconds, estimated_seconds,
                       category: ultrabullet|bullet|blitz|rapid|classical|daily|unknown, category_fi}
  length              {plies, full_moves, category: short(<=25)|medium(<=60)|long, category_fi}
  phases_reached      ["opening","middlegame","endgame"]
  has_clock_data      bool   (PGN:n [%clk]-kommentit)
  final_fen
engine                {name, depth}
opening               {source, eco, name, named_at_ply, lichess_url, book_plies,
                       deviation{ply, color, move_number, san, book_alternatives[], engine_best, classification},
                       explorer?{position_ply, filters{speed, rating_from},
                                 lichess|masters{games, opening, played, top_moves[{san, games, share,
                                 white_pct, draw_pct, black_pct, average_rating}]}},
                       note?}
open_data             {online, sources[], notes[]}
perspective           "white"|"black"|null
players.{white,black}
  name, elo, accuracy, counts{best,excellent,good,forced,inaccuracy,mistake,blunder}
  phases.{opening,middlegame,endgame}
    reached, moves, accuracy, counts, worst_moves[{ply,text}], good_moments[{ply,text}]
  observations[]      {id, phase, severity: info|warning, text, evidence[ply]}
                      id: queen_moves_early | flank_pawn | slow_development | no_castle |
                          time_trouble | long_thinks | avg_time_per_phase
  time_control_advice[]   aikakontrolli- ja pituuskohtaiset vinkit
  learning_priorities[]   {rank, topic, title, practice, score, evidence[ply], resources[{title, url}]}  (max 3)
  skip_for_now[]          mitä ei kannata vielä opetella (tasoon sidottu)
key_moments[]         {ply, reason: error|mate|punished, color, text, lichess_analysis_url}
moves[]               (yksi per ply)
  ply, move_number, color, san, uci, fen_before, fen_after, phase
  eval_before, eval_after          valkean näkökulmasta, esim. "+0.35" tai "#-1"
  cp_before_white, cp_after_white
  best_move_san, best_move_uci, best_line_san[], opponent_best_reply_san
  win_before, win_after, win_loss  siirtäjän voitto-odotus 0..100 (Lichessin malli)
  accuracy                         0..100 (Lichessin siirtokohtainen kaava)
  classification                   book|best|excellent|good|forced|inaccuracy|mistake|blunder
  book, opening_name               kirjasiirto ja nimetty avausasema siirron jälkeen
  tablebase                        {before, after, best_san, dtm_before, before_fi, after_fi} tai null
  nag                              "?!", "?", "??" tai null
  clock_seconds, time_spent_seconds
  tags[]               delivered_mate, missed_mate, allowed_mate, lost_material, allowed_tactic,
                       missed_capture, missed_punishment, queen_move_opening,
                       flank_pawn_opening, castled, tb_threw_win, tb_threw_draw
  tag_details{}        taktisten tagien yksityiskohdat (linjat, nappula, ruutu)
limitations[]
```

## Luokittelu

Siirtäjän voitto-odotuksen pudotus (%-yksikköä): alle 2 erinomainen, alle 5 hyvä, alle 10
epätarkkuus, alle 20 virhe, vähintään 20 vakava virhe. Moottorin paras siirto on aina `best`,
ja ainoa laillinen siirto on `forced`. Kirjasiirrot ovat `book`, eikä niitä lasketa
tarkkuuteen eikä virheisiin. Moottorin luvut säilyvät silti kentissä.

## Tunnetut rajoitteet

- Avauskirja on nimettyjen avausten tietokanta, ei täysi teoriapuu. Kirjasta poistuminen ei tarkoita,
  että siirto olisi huono, eikä tunnettu mutta nimeämätön teoriasiirto saa `book`-merkintää.
- Erikoisasemasta (FEN) alkavissa peleissä avauskirjaa ei käytetä.
- Pelivaiheet päätellään heuristisesti (materiaali ja takarivin kehitys).
- Tarkkuus on keskiarvo, eikä se ole suoraan verrattavissa chess.comin tarkkuuslukuun.
- Kelloanalyysi vaatii `[%clk]`-kommentit PGN:ssä.
