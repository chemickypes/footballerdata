# Design: Feed Dinamico Infrasettimanale (38 Giornate) — Pilastro 3

**Data**: 2026-09-06
**Stato**: Approvato, in attesa di piano di implementazione

## Contesto e scope decisionale

Questo spec nasce da un capitolato tecnico molto ampio (7 pilastri architetturali per
`fanta-lab`). Per evitare un piano ingestibile, il lavoro è stato scomposto in
sotto-progetti indipendenti. Questo documento copre **esclusivamente il Pilastro 3**
(scraping dinamico infrasettimanale). Gli altri pilastri sono stati processati così:

- **Pilastro 1 (Dual-track config community/Vercel)**: verificato come **già
  implementato correttamente** in `app.py` (cascata `APP_ENV`/`IS_PERSONAL`,
  `_get_writable_path()` con redirect su `/tmp` in Vercel, `config.personal.py`/`.env`
  mai committati). Nessuna modifica necessaria.
- **Pilastro 2 (bugfix critici pipeline/ML)**: verificato come **già risolto** dai
  commit recenti (`player_uid` fallback in Stage 8, retry/backoff in
  `05_scrape_injuries.py`, check colonne in `07_generate_excel.py`, fasce per
  quantili disgiunti per ruolo, blueprint/battitore scalati sul budget reale). Nessuna
  modifica necessaria.
- **Pilastri 4-7**: non ancora affrontati, da riprendere in sessioni successive con lo
  stesso processo di scomposizione.

## Obiettivo

Rendere `fanta-lab` operativo durante tutta la stagione (38 giornate), fornendo un feed
aggiornato di probabili formazioni, quote bookmaker e forma recente, senza appesantire
Vercel (serverless, no scraping a runtime) né rischiare blocchi IP dell'utente in locale.

## Architettura

Si mantiene la convenzione di cartelle esistente (`pipeline/`) invece di introdurre
`core/ingestion/` (che anticiperebbe la riorganizzazione prevista dal Pilastro 7).

```
pipeline/
  dynamic/
    __init__.py
    scrape_odds.py       # api-football.com: fixtures, quote 1X2/O-U 2.5, de-vig
    scrape_lineups.py    # fantacalcio.it/SOS Fanta: probabili formazioni, xMin
    scrape_results.py    # api-football.com: risultati turno concluso, EWMA forma
    build_feed.py         # Orchestratore: merge, fuzzy-match, validazione, output
    client.py             # Singleton HTTP client con cache TTL 15 min (usato da app.py)

.github/workflows/
  dynamic_feed.yml        # Cron: Gio 18:00, Ven 12:00/19:00, Sab 11:00 UTC

data/
  current_matchday.json   # Output pubblicato su branch orfana `data-feed`
  fallback_matchday.json  # Fallback statico committato su main
```

### 1. `scrape_odds.py` — Quote Bookmaker (api-football.com)

- Fonte: **api-football.com**, chiave in `API_FOOTBALL_KEY` (env var / GitHub Secret,
  mai committata).
- Endpoint: `/fixtures` (turno corrente Serie A), `/odds` (1X2, Over/Under 2.5).
- De-vig: rimuove l'aggio del banco per ricavare probabilità pure:
  `P(evento) = (1/Q) / (1 + A)` dove `A = Σ(1/Qk) - 1`.
- Output per fixture: `home_win_prob`, `draw_prob`, `away_win_prob`,
  `clean_sheet_prob_home/away` (derivata da Under 0.5 conceded se disponibile,
  altrimenti da modello di Poisson approssimato sulle expected goals implicite),
  `expected_goals_home/away`.
- Resilienza: retry con backoff esponenziale (max 3 tentativi); se l'endpoint odds non
  ha dati per una fixture, i campi restano `null` e il fixture è marcato
  `"odds_available": false` — non blocca il resto del feed.

### 2. `scrape_lineups.py` — Probabili Formazioni

- Fonte: fantacalcio.it / SOS Fanta (probabili formazioni testuali, non API ufficiale).
- Estrae per giocatore: `titular_prob` ∈ [0,1], `status`
  (`OK`/`BALLOTTAGGIO`/`INFORTUNATO`/`SQUALIFICATO`/`DIFFERENZIATO`), `ballottaggio_vs`
  (nome competitor se in ballottaggio).
- Calcolo minuti attesi:
  `xMin = titular_prob * 70 + (1 - titular_prob) * 20 * is_bench_candidate`.
- Matching sul dataset esistente: riuso del pattern già presente in
  `pipeline/04b_scrape_lineups.py` — normalizzazione nome (rimozione accenti,
  lowercase) + `difflib.get_close_matches` con narrowing per squadra, poi fallback
  globale a cutoff più permissivo.
- Resilienza: stesso pattern di `05_scrape_injuries.py` — User-Agent rotante, retry con
  backoff, se >15% delle richieste fallisce interrompe e marca il feed
  `"lineups_degraded": true` mantenendo l'ultimo stato noto da
  `fallback_matchday.json`.

### 3. `scrape_results.py` — Forma Recente (EWMA)

- Fonte: api-football.com, endpoint `/fixtures/players` per il turno concluso.
- Usa il campo `rating` (0-10) restituito da api-football come **proxy** del voto
  fantacalcio ufficiale (non è la pagella reale di fantacalcio.it). Questo viene
  dichiarato esplicitamente nel JSON con `"rating_source": "api_football_proxy"` per
  trasparenza — non è un dato "inventato", ma un proxy quantitativo dichiarato.
- Aggiornamento EWMA: `EWMA_t = 0.35 * rating_t + 0.65 * EWMA_{t-1}`, persistito in
  `data/ewma_state.json` (letto/scritto solo dalla pipeline offline, mai da `app.py` a
  runtime — coerente col vincolo Vercel read-only).

### 4. `build_feed.py` — Orchestratore

- Esegue i tre scraper in sequenza, tollerando fallimenti parziali di ciascuno.
- Fuzzy-match dei giocatori sul dataset (`dataset_finale.csv`) per produrre chiavi
  `team_playername_role` (es. `inter_lautaro_martinez_a`), riusando le stesse funzioni
  di normalizzazione di `04b_scrape_lineups.py` (estratte in un piccolo modulo comune
  per evitare duplicazione, es. `pipeline/dynamic/_matching.py`).
- Calcola `xpts` per giocatore con la formula del capitolato:
  `xPts = (xMin/90) * [Voto Base + 3*P(Gol) + 1*P(Assist) - 1*E[Gol Subiti] - 0.25*P(Ammonizione)]`
  usando `ewma_form` come Voto Base e le probabilità disponibili da odds/lineup (con
  default neutri se mancanti).
- Validazione: assert `len(players) >= 450`, altrimenti lo step CI fallisce con
  messaggio diagnostico esplicito (fail-fast, coerente col pattern già usato in Stage
  8).
- Scrive `data/current_matchday.json` con lo schema esatto specificato nel capitolato
  (`matchday`, `season`, `updated_at`, `fixtures[]`, `players{}`).

### 5. `client.py` — Client Web App

- Classe singleton thread-safe (lock su get/set cache).
- Fetch via HTTP GET del JSON raw dalla branch `data-feed` su GitHub (URL raw
  configurabile via env, default punta al repo pubblico).
- Cache in-memory con TTL 15 minuti.
- Fallback automatico su `data/fallback_matchday.json` (committato su `main`, quindi
  sempre disponibile anche offline) se il fetch fallisce o va in timeout/rate-limit.
- Nessuna scrittura su disco a runtime (coerente col Pilastro 1: legge solo file
  statici già presenti nel deploy).

### 6. `.github/workflows/dynamic_feed.yml`

- Runner `ubuntu-latest`, `actions/checkout`, setup Python, `pip install -r
  requirements.txt`.
- Cron: `'0 18 * * 4'` (Gio 18:00 UTC), `'0 12,19 * * 5'` (Ven 12:00 e 19:00 UTC),
  `'0 11 * * 6'` (Sab 11:00 UTC). Aggiunto anche `workflow_dispatch` per run manuali.
- Step: `python -m pipeline.dynamic.build_feed`.
- Verifica: fallisce il job se `current_matchday.json` ha meno di 450 giocatori validi
  (già garantito dall'assert in `build_feed.py`, il workflow controlla anche l'exit
  code).
- Commit del file generato su branch orfana `data-feed` (creata/aggiornata via
  `git checkout --orphan` se non esiste, altrimenti fast-forward), push con
  `GITHUB_TOKEN` di default (nessun secret aggiuntivo necessario per il push).
- Secret richiesto: `API_FOOTBALL_KEY` (da configurare da chi fa il fork/deploy — la
  chiave dell'utente NON viene mai committata né condivisa nel repo pubblico).

## Gestione segreti e privacy

- La chiave `API_FOOTBALL_KEY` fornita dall'utente in questa sessione **non è stata
  salvata in memoria né scritta in alcun file tracciato da git**. Va configurata
  manualmente come GitHub Actions Secret e in `.env` locale (già in `.gitignore`).
- Si raccomanda all'utente di rigenerare la chiave, dato che è stata condivisa in
  chiaro in chat.

## Error handling e degradazione

Ogni componente segue il pattern già consolidato nel resto della pipeline (vedi
`05_scrape_injuries.py`): retry con backoff esponenziale, soglia di fallimento (15%)
oltre la quale si attiva un fallback esplicito con log `[WARNING]`, mai un crash non
gestito. Il feed finale include sempre flag di degradazione (`odds_available`,
`lineups_degraded`) così il frontend/i moduli a valle possono adattarsi (es. usare
default neutri) invece di fallire.

## Testing

Nuovo file `tests/test_dynamic_feed.py` (stesso stile di
`tests/test_dual_track_and_features.py`, funzioni `test()` con assert manuali e
stampa PASS/FAIL), copre:
- Validazione schema di `current_matchday.json` (chiavi richieste presenti).
- Calcolo de-vig su quote sintetiche note.
- Calcolo EWMA su una sequenza di rating sintetici.
- Fuzzy-match di un set di nomi noti con variazioni di accenti/abbreviazioni.
- Comportamento di `client.py` in caso di fetch fallito (fallback attivato).

## Fuori scope (rimandato a pilastri successivi)

- Moduli analitici che consumano il feed (Weekly Lineup Solver, Audit Engine, Trade
  Analyzer) → Pilastro 4.
- Estrazione della cascata di configurazione in un modulo `core/config.py` dedicato →
  Pilastro 7 (riorganizzazione repo).
