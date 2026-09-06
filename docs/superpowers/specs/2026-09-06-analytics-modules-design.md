# Pilastro 4 — Moduli Analitici (Lineup Solver, Audit Engine, Trade Machine)

## Contesto

Pilastro 3 (feed dinamico infrasettimanale) è già in produzione su `main`: `pipeline/dynamic/client.py`
espone un client singleton thread-safe con cache TTL 15m su `data/current_matchday.json`
(titolarità, quote, EWMA forma), con fallback su `data/fallback_matchday.json`. Questo client
**non è ancora consumato da nessuna route Flask** — Pilastro 4 è il primo consumatore reale.

Questo pilastro introduce 3 moduli analitici nuovi, isolati in un package `modules/` (primo
tassello della riorganizzazione prevista dal Pilastro 7, ma senza spostare file esistenti):

1. **Weekly Lineup Solver** — formazione ottimale settimanale via MILP.
2. **Post-Draft Audit Engine** — power ranking di lega e badge post-asta, con re-weighting
   dinamico in-season.
3. **Trade Machine** — valutazione scambi N-per-N e Win-Win Detector.

## Scope e vincoli concordati

- Nessuna modifica ai 5 tab/route esistenti (`draft`, `targets`, `strategy`, `rosters`, `listone`, `ai`).
- 3 nuovi tab in navbar: **"Formazione"**, **"Classifica Lega"**, **"Scambi"** (nomi semplificati
  rispetto al capitolato originale, su richiesta utente).
- Il Lineup Solver calcola per **tutte** le squadre di `state["teams"]`, ma la UI mostra sempre e
  solo la formazione della squadra con `is_me: true` (non esiste ancora un vero sistema di login
  multi-utente — quello sarà un progetto futuro separato).
- Nessun nuovo scraping per la fragilità infortuni: si riusano le colonne già presenti in
  `dataset_finale.csv` (`giorni_infortunio_3y`, `n_infortuni_3y`, `malus_infortuni`).
- Il retraining del modello quantile GBR (Stage 8) resta fuori scope: si usa un **re-weighting
  leggero** (non retraining) via EWMA/titolarità già raccolti da Pilastro 3.
- Il backtest/analisi errore del modello è esplicitamente **fuori scope**, rimandato a un progetto
  futuro opzionale.

## Architettura generale

```
modules/
├── common/
│   └── data_provider.py      # Data layer condiviso (dataset statico + feed dinamico + xPts uniforme)
├── lineup/
│   └── lineup_solver.py      # MILP formazione settimanale
├── valuation/
│   ├── audit_engine.py       # Power ranking, fragilità, badge
│   └── season_tracking.py    # Append/lettura data/season_tracking.jsonl
└── trades/
    └── trade_analyzer.py     # Scambi N-per-N, Win-Win Detector
```

Ogni modulo espone funzioni pure (nessuno stato interno nascosto), riceve i dati già caricati
(dataframe/dict) come parametri e ritorna dict/dataclass serializzabili in JSON. Le route Flask in
`app.py` restano sottili: caricano stato/dataset, chiamano il modulo, serializzano la risposta.

## Sezione 1 — Data provider condiviso (`modules/common/data_provider.py`)

Responsabilità:

- `get_player_pool() -> pd.DataFrame`: wrapper su `load_dataset()` di `app.py` (dataset statico
  P10/P50/P90, VORP, prezzi, fragilità).
- `get_dynamic_overlay() -> dict | None`: chiama `pipeline.dynamic.client` (singleton esistente).
  Cattura qualunque eccezione/timeout e ritorna `None` se il feed non è disponibile o scaduto —
  **non solleva mai eccezioni verso il chiamante**.
- `compute_weekly_xpts(df, dynamic_overlay) -> pd.DataFrame`: se l'overlay è disponibile, calcola
  `xpts_week` per giocatore con la formula del capitolato:

  ```
  xPts_i = (xMin_i / 90) * [VotoBase_i + 3*P(Gol_i) + 1*P(Assist_i)
                             - 1*E[GolSubiti_i] - 0.25*P(Ammonizione_i)]
  ```

  Se l'overlay è `None`, la funzione **non produce un fallback silenzioso**: ritorna un
  indicatore esplicito `overlay_available=False` che i moduli a valle interpretano secondo le
  proprie regole (vedi Sezione 2 per il Lineup Solver, che blocca l'esecuzione in questo caso).

Questo isola in un solo punto la logica "prova il feed dinamico, altrimenti segnala assenza",
testabile in isolamento con mock del client.

## Sezione 2 — Weekly Lineup Solver (`modules/lineup/lineup_solver.py`)

### Requisito dati: feed dinamico obbligatorio

**Il solver richiede sempre un feed dinamico valido** (titolarità, infortuni/squalifiche, quote).
Non esiste un fallback che generi una formazione basata solo su `dataset_finale.csv`: usare solo
dati storici per decidere chi schierare in una specifica giornata rischia di consigliare
giocatori infortunati o fuori rosa, che è un errore inaccettabile per questo caso d'uso specifico
(diversamente dal resto dell'app, dove il fallback statico è appropriato).

Se `data_provider.get_dynamic_overlay()` ritorna `None`, la funzione `solve_lineup(...)` ritorna
immediatamente:
```python
{"success": False, "error": "feed_unavailable",
 "message": "Dati in tempo reale non disponibili (titolarità/infortuni/quote). Riprova più tardi."}
```
Nessuna formazione viene calcolata in questo caso. La route Flask propaga questo stato con HTTP 503.

### Algoritmo (quando il feed è disponibile)

1. **Esclusione a priori**: i giocatori con `status` in `{"INFORTUNATO", "SQUALIFICATO"}` nel feed
   dinamico vengono rimossi dal pool titolari ammissibili (non solo penalizzati nel punteggio).
2. Per ciascuno dei 7 moduli regolamentari (3-4-3, 3-5-2, 4-3-3, 4-4-2, 4-5-1, 5-3-2, 5-4-1),
   risolve un MILP binario — stesso pattern di `pipeline/10_roster_optimizer.py`
   (`scipy.optimize.milp` con `LinearConstraint`/`Bounds`, integrality binaria):
   - Variabili: 1 binaria per giocatore ammissibile in rosa (titolare sì/no).
   - Vincoli: esattamente 1 P, esattamente N_D/N_C/N_A del modulo, esattamente 11 titolari totali.
   - Obiettivo: massimizzare `Σ xpts_week` dei titolari + bonus modificatore atteso (se
     difensori schierati ≥ 4: media dei 3 migliori voti puri difensivi attesi + portiere).
   - Se il modulo non è risolvibile (rosa insufficiente per quel modulo specifico), viene
     scartato silenziosamente e si passa al successivo — nessun crash.
3. Si sceglie il modulo con obiettivo massimo tra quelli risolvibili.
4. Se **nessun** modulo è risolvibile (rosa gravemente incompleta), ritorna errore strutturato
   (`{"success": False, "error": "no_feasible_formation", ...}`), mai un'eccezione grezza.
5. **Panchina**: i non-titolari (esclusi infortunati/squalificati, che non compaiono affatto)
   vengono ordinati per `xpts_week` decrescente, raggruppati per ruolo — semplice sort, nessun MILP.

### Output

```python
{
  "success": True,
  "team_id": 1,
  "formation": "4-3-3",
  "starters": [{"player": "...", "role": "D", "xpts": 5.2}, ...],   # 11 elementi
  "bench": [{"player": "...", "role": "D", "xpts": 3.1}, ...],
  "total_xpts": 63.4,
  "bonus_modificatore_expected": 1.0
}
```

Il solver viene eseguito per tutte le squadre (per popolare potenzialmente un confronto futuro),
ma la route `/api/lineup/solve` per la UI restituisce di default solo la squadra `is_me`.

## Sezione 3 — Post-Draft Audit Engine (`modules/valuation/audit_engine.py`)

Questo modulo **non richiede il feed dinamico** — è un report di valutazione strategica, non una
decisione di formazione giornaliera. Usa dati statici (`dataset_finale.csv`) più un re-weighting
leggero basato sullo storico di forma accumulato in stagione.

### Tracking storico (`modules/valuation/season_tracking.py`)

- File `data/season_tracking.jsonl` (append-only, un record per giocatore per giornata conclusa).
- Popolato da un hook invocato dopo ogni esecuzione riuscita di `scrape_results.py` (già schedulata
  da Pilastro 3): per ogni giocatore con dati di giornata conclusa, appende:
  ```json
  {"matchday": 5, "player": "...", "predicted_pts_p50_original": 6.8,
   "ewma_form_at_that_point": 6.1, "actual_score": 5.5}
  ```
- Se il file non esiste ancora (inizio stagione, nessuna giornata conclusa), l'Audit Engine
  funziona comunque usando solo `predicted_pts_p50` originale, senza errori.

### Re-weighting dinamico

Per ogni giocatore con almeno 3 record nello storico, calcola un **valore attuale** pesato:
```
valore_attuale = 0.5 * predicted_pts_p50_original + 0.5 * media_ewma_ultime_3_giornate
```
Questo permette al Power Ranking di riflettere un calo di rendimento/titolarità (es. giocatore
finito ai margini delle rotazioni) senza alcun retraining del modello — puro re-weighting basato
su dati già raccolti da Pilastro 3.

### Calcoli per squadra

1. **Expected Season Points**: somma di `valore_attuale` (o `predicted_pts_p50` se non ancora
   disponibile re-weighting) per titolari teorici + riserve della rosa.
2. **Indice di Capitale a Rischio**: somma prezzi pagati per giocatori con `giorni_infortunio_3y
   > 60` (soglia 🔴 già definita), espresso in crediti assoluti e % sul budget di squadra.
3. **Badge automatici** (confronto cross-squadra):
   - *Miglior Colpo VORP*: giocatore con `surplus_value_cr` massimo in rosa.
   - *Peggior Overpay*: giocatore con `surplus_value_cr` minimo (più negativo).
   - *Most Balanced Squad*: minor deviazione standard tra spesa nei 4 ruoli vs. media dei blueprint.
   - *Glass Cannon*: squadra top-3 per Expected Points E top-3 per capitale a rischio.

### Output

Lista di dict per squadra, ordinata per Power Ranking (Expected Season Points decrescente):
`team_id`, `team_name`, `expected_points`, `risk_capital_cr`, `risk_capital_pct`, `badges` (lista).

Nessuno stato persistito da questo modulo: ricalcolato on-demand a ogni chiamata di
`GET /api/audit/rankings`.

## Sezione 4 — Trade Machine (`modules/trades/trade_analyzer.py`)

### Due modalità di valutazione

1. **Valutazione di Valore** (sempre disponibile, dati statici): confronto aggregato di
   `predicted_pts_p50` + `vorp_points` tra i giocatori ceduti e ricevuti da ciascuna squadra
   coinvolta. Nessuna dipendenza dal feed dinamico.
2. **Δ Formazione Live** (richiede feed dinamico, eredita il vincolo del Lineup Solver): esegue
   `solve_lineup()` sulla rosa pre-trade e post-trade di ciascuna squadra coinvolta e calcola
   `Δ Utilità = total_xpts_post - total_xpts_pre`. Se il feed dinamico non è disponibile, questa
   sezione della risposta è marcata `"available": False` con messaggio esplicativo, ma la
   Valutazione di Valore resta comunque visibile — nessun blocco totale della funzionalità.

### Scambio manuale N-per-N

- Selettore UI multi-select: fino a un massimo di **6 giocatori totali coinvolti** nello scambio
  (across the trade, es. anche 4 contro 2).
- Nessun vincolo di simmetria tra le parti.

### Win-Win Detector

- Itera automaticamente possibili scambi tra la propria rosa e ciascun avversario.
- Limite di ricerca combinatoria: **massimo 3 giocatori per lato** (quindi fino a 3-vs-3, 6 totali)
  per contenere il costo computazionale (le combinazioni oltre questo limite sono raggiungibili
  solo tramite lo scambio manuale, non dal detector automatico).
- Usa la **Valutazione di Valore** (statica, sempre disponibile) per calcolare il Δ Utilità di
  entrambe le parti — il detector non richiede il feed dinamico.
- Filtra solo le combinazioni dove **entrambe** le squadre hanno Δ Utilità ≥ 0.
- Ordina per Δ Utilità combinato (somma dei due delta) decrescente, ritorna le prime 10.

### Output

```python
{
  "value_evaluation": {"team_a_delta": ..., "team_b_delta": ...},
  "live_lineup_evaluation": {"available": True/False, "team_a_delta_xpts": ..., "team_b_delta_xpts": ..., "message": "..."},
}
```
Win-Win Detector: lista di fino a 10 proposte, ciascuna con giocatori coinvolti e delta per parte.

## Sezione 5 — Error handling, testing, route, UI

### Error handling (riepilogo)

| Modulo | Comportamento se feed dinamico assente |
|---|---|
| Lineup Solver | **Blocca**: nessuna formazione, errore esplicito (503) |
| Audit Engine | Non applicabile — non usa il feed dinamico |
| Trade Machine | Valutazione di Valore resta disponibile; Δ Formazione Live marcato non disponibile |

| Modulo | Comportamento con dati mancanti/incompleti |
|---|---|
| Lineup Solver | Rosa insufficiente per un modulo → scarta quel modulo, prova gli altri; se nessuno risolvibile → errore strutturato |
| Audit Engine | `season_tracking.jsonl` assente → usa solo P50 originale senza re-weighting, nessun crash |
| Trade Machine | Giocatore selezionato non trovato in rosa → errore 400 con messaggio chiaro, nessuna eccezione grezza propagata |

### Testing

Nuovi file, stile coerente con `tests/test_dynamic_feed.py` (fixture + mock):
- `tests/test_lineup_solver.py`: MILP con rosa completa/incompleta, esclusione infortunati,
  assenza feed (deve bloccare), nessun modulo risolvibile.
- `tests/test_audit_engine.py`: calcolo con/senza tracking storico, badge su casi limite
  (pareggio VORP, squadra con rosa vuota).
- `tests/test_trade_analyzer.py`: scambio 1-per-1 e N-per-N fino a 6, Win-Win Detector con
  limite 3-vs-3, giocatore inesistente, feed dinamico assente (Δ Live non disponibile ma Valore sì).
- `tests/test_season_tracking.py`: append idempotente, lettura file assente, file corrotto (riga
  malformata ignorata senza crash).

### Route Flask (nuove, in `app.py`)

- `POST /api/lineup/solve` — body `{team_id}` (default: squadra `is_me`); 503 se feed assente.
- `GET /api/audit/rankings` — nessun parametro, ricalcola sempre on-demand.
- `POST /api/trades/evaluate` — body `{team_id_a, players_out[], team_id_b, players_in[]}`
  (max 6 giocatori totali).
- `GET /api/trades/winwin?team_id=...` — Win-Win Detector per la squadra indicata.

### UI

3 nuovi tab in navbar, stesso pattern CSS/JS dei tab esistenti (`switchTab()`), senza alcuna
modifica ai 5 tab attuali:
- **Formazione**: mostra risultato di `/api/lineup/solve` per la squadra `is_me`; banner di errore
  se il feed non è disponibile.
- **Classifica Lega**: tabella Power Ranking + badge da `/api/audit/rankings`.
- **Scambi**: selettore multi-team/multi-player per scambio manuale (fino a 6 giocatori) +
  sezione separata "Scambi Win-Win Suggeriti" alimentata da `/api/trades/winwin`.

## Non-goal espliciti (fuori scope per questo pilastro)

- Sistema di login/autenticazione multi-utente reale (rimandato a progetto futuro).
- Retraining del modello quantile GBR (Stage 8) — solo re-weighting leggero.
- Backtest/analisi sistematica dell'errore di previsione del modello.
- Riorganizzazione gamificata dei tab esistenti (rimandata, verrà affrontata insieme al Pilastro 6).
