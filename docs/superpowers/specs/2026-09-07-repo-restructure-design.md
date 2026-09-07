# Pilastro 7 — Riorganizzazione Repository, Documentazione e Licenza

Data: 2026-09-07
Stato: Approvato

## Contesto

Il repository `fanta-lab` ha attraversato 6 pilastri di evoluzione (config dual-track,
bugfix pipeline/ML, feed dinamico infrasettimanale, moduli analitici, AI copilot locale,
tutorial interattivo) mantenendo una struttura piatta al root (`pipeline/`, `copilot/`,
`modules/`, `app.py`, `static/`). Il capitolato originale richiede una struttura modulare
a 3 macro-aree (`core/`, `modules/`, `web/`), documentazione bilingue divulgativa +
tecnica per ogni modulo, una timeline di progetto, e un cambio di licenza da MIT
(permissiva, commerciale) a una licenza non-commerciale che protegga il codice da usi
commerciali di terzi mantenendo per l'autore la facoltà di commercializzarlo in futuro.

Questo è l'ultimo pilastro rimasto (esplicitamente "da fare per ultimo" nel capitolato
originale) e non introduce nuove funzionalità: è un refactor strutturale + documentale.

## Obiettivi

1. Riorganizzare l'intero albero dei file secondo la struttura target del capitolato,
   aggiornando ogni riferimento (`import`, path assoluti/relativi, `sys.path`, workflow
   YAML, `vercel.json`, test) così che nulla si rompa.
2. Sostituire la licenza MIT con **PolyForm Noncommercial 1.0.0**.
3. Scrivere un README dedicato per ciascun modulo/cartella principale, con due sezioni:
   una divulgativa (linguaggio semplice, italiano) e una tecnica (algoritmi, formule,
   colonne di output, dipendenze).
4. Scrivere una timeline di progetto (`docs/it/TIMELINE_PROGETTO.md` +
   `docs/en/PROJECT_TIMELINE.md`) con focus sull'approccio statistico/quantitativo,
   dal punto di partenza (script pre-asta) al presente (piattaforma stagionale) fino a
   una visione futura ad alto livello.
5. Aggiungere placeholder per screenshot nei README dei moduli che non hanno ancora
   immagini reali (da sostituire dopo il futuro redesign UI ("glow up")); riutilizzare
   gli screenshot già esistenti in `docs/assets/` dove pertinenti (Command Center,
   Listone, Blueprint, AI Copilot sono già disponibili).

## Struttura Target

```
fanta-lab/
├── core/
│   ├── __init__.py
│   ├── config.py                      # ex config.py (root)
│   ├── config_defaults.py             # ex config_defaults.py (root)
│   ├── config.personal.py             # ex config.personal.py (root, gitignored)
│   ├── config.personal.example.py     # ex config.personal.example.py (root)
│   ├── README.md                      # nuovo
│   ├── ingestion/
│   │   ├── __init__.py                # nuovo (pacchetto)
│   │   ├── README.md                  # nuovo
│   │   ├── static/                    # ex pipeline/*.py (step numerati 01-10 + utility)
│   │   │   ├── __init__.py
│   │   │   ├── 01_scrape_historical.py
│   │   │   ├── 03_update_listone.py
│   │   │   ├── 04_scrape_understat.py
│   │   │   ├── 04b_scrape_lineups.py
│   │   │   ├── 05_scrape_injuries.py
│   │   │   ├── 06_build_dataset.py
│   │   │   ├── 07_generate_excel.py
│   │   │   ├── 08_quantile_points_model.py
│   │   │   ├── 09_vorp_auction_pricing.py
│   │   │   ├── 10_roster_optimizer.py
│   │   │   ├── generate_excel_italiano.py
│   │   │   └── target_pricing.py
│   │   └── dynamic/                   # ex pipeline/dynamic/* (invariato al suo interno)
│   │       ├── __init__.py, api_football_client.py, build_feed.py, client.py,
│   │       │   scrape_lineups.py, scrape_odds.py, scrape_results.py,
│   │       │   scrape_status.py, utils.py
│   ├── models/                        # nuovo pacchetto (documentazione, no move di codice:
│   │   │                               # il codice modello resta in core/ingestion/static/08_*
│   │   │                               # e 09_*; qui va solo un README che spiega gli
│   │   │                               # algoritmi, referenziando quei file)
│   │   └── README.md
│   └── copilot/                       # ex copilot/* (invariato al suo interno)
│       ├── __init__.py, providers.py, prompts.py, Modelfile
│       └── README.md                  # nuovo
│
├── modules/                            # invariato nei contenuti interni, solo nuovi README
│   ├── common/          (invariato)   + README.md (nuovo)
│   ├── lineup/           (invariato)  + README.md (nuovo)
│   ├── valuation/        (invariato)  + README.md (nuovo)
│   ├── trades/           (invariato)  + README.md (nuovo)
│   └── auction/          (nuovo, solo README.md — vedi nota sotto)
│
├── web/
│   ├── __init__.py                    # nuovo (per import puliti se serve)
│   ├── app.py                         # ex app.py (root)
│   ├── static/
│   │   ├── css/                       # ex static/css/*
│   │   └── js/                        # ex static/js/*
│   └── README.md                      # nuovo
│
├── docs/
│   ├── it/
│   │   ├── TIMELINE_PROGETTO.md       # nuovo
│   │   └── METRICHE_E_COLONNE.md      # nuovo (glossario semplice, se non già coperto)
│   ├── en/
│   │   ├── PROJECT_TIMELINE.md        # nuovo
│   │   └── METRICS_AND_COLUMNS.md     # nuovo
│   ├── assets/                        # invariato (screenshot esistenti)
│   ├── superpowers/                   # invariato (specs/plans di questo assistente)
│   ├── MODEL_INTERPRETABILITY.md      # invariato (già valido, linkato dai nuovi README)
│   ├── LIVE_COMMAND_CENTER.md         # invariato
│   ├── data_sources.md                # invariato
│   ├── pipeline_architecture.md       # aggiornato con i nuovi path
│   └── scoring_methodology.md         # invariato
│
├── tests/                             # invariato nei nomi file, import aggiornati
├── examples/                          # invariato
├── data/                              # invariato
├── scripts/                           # invariato
├── .github/workflows/dynamic_feed.yml # aggiornato: `python -m core.ingestion.dynamic.build_feed`
├── run_pipeline.py                    # aggiornato: importlib.import_module(f"core.ingestion.static.{module_name}")
├── requirements.txt                   # invariato
├── vercel.json                        # aggiornato: "src": "web/app.py"
├── LICENSE                            # sostituito con PolyForm Noncommercial 1.0.0
└── README.md                          # riscritto: overview, quickstart, indice moduli, timeline, badge
```

**Nota su `modules/auction/`**: il capitolato lo prevede come cartella, ma nella pratica
la logica dell'asta live (VORP pricing display, blueprint, battitore, stop-loss) vive
oggi interamente dentro `web/app.py` (non è mai stata estratta in un modulo separato
durante i Pilastri precedenti). Estrarla ora sarebbe un refactor di codice rischioso e
fuori scopo per un pilastro "solo struttura + doc". Decisione: creo `modules/auction/`
con solo un `README.md` che spiega la logica dell'asta (blueprint, stop-loss, VORP
pricing) e rimanda esplicitamente a `web/app.py` come posizione attuale del codice,
segnalando l'estrazione come miglioria futura. Nessun codice viene spostato in questa
cartella.

## Aggiornamento Riferimenti (dipendenze)

File da modificare per correggere path/import dopo lo spostamento:

- `web/app.py`: `import config` → `from core import config`; import dei moduli
  (`from modules...`) restano invariati (già assoluti dalla root); `from copilot import ...`
  → `from core.copilot import ...`; `BASE_DIR` ricalcolato correttamente (deve continuare
  a puntare alla root del repo per trovare `data/`, non a `web/`); route statica Flask
  deve puntare a `web/static/` invece di `static/`.
- `run_pipeline.py`: `importlib.import_module(f"pipeline.{module_name}")` →
  `f"core.ingestion.static.{module_name}"`.
- `.github/workflows/dynamic_feed.yml`: `python -m pipeline.dynamic.build_feed` →
  `python -m core.ingestion.dynamic.build_feed`.
- `vercel.json`: `"src": "app.py"` → `"src": "web/app.py"`; route dest aggiornato di
  conseguenza.
- `tests/*.py`: tutti gli import `from pipeline.dynamic...` → `from core.ingestion.dynamic...`;
  `sys.path.insert` continua a puntare alla root del repo (invariato, dato che gli import
  restano assoluti dal root).
- Ogni file spostato in `core/ingestion/static/` che importa moduli fratelli (es. `01_*`
  importato da `06_build_dataset.py`, se presente) va verificato e corretto.
- `docs/pipeline_architecture.md`: aggiornare i path citati.

## Licenza

Sostituzione integrale di `LICENSE` con il testo ufficiale **PolyForm Noncommercial
1.0.0** (https://polyformproject.org/licenses/noncommercial/1.0.0/), copyright
"Copyright (c) 2026 SpectreLabo". Aggiornamento badge nel `README.md` radice da
`License: MIT` a `License: PolyForm Noncommercial 1.0.0` con link alla licenza.
Nessun'altra menzione "MIT" deve restare nel repository (verifica via grep).

## README dei Moduli — Contenuto e Formato

Ogni README di modulo segue questo schema in italiano:

1. **Cos'è (spiegazione semplice)**: 2-4 frasi, senza gergo tecnico, per un utente
   fantacalcistico medio — cosa fa questo modulo per l'utente finale.
2. **Come funziona (spiegazione tecnica)**: algoritmi, formule (LaTeX/markdown),
   librerie usate (SciPy/HiGHS, scikit-learn, ecc.), input/output, e — dove applicabile
   — **quale colonna del dataset finale viene generata da quale passaggio algoritmico**
   (es. "`vorp` è calcolato in `core/ingestion/static/09_vorp_auction_pricing.py` come
   `max(0, p50 - baseline_ruolo)`").
3. **Screenshot**: se esiste già uno screenshot pertinente in `docs/assets/`, lo si
   embedda con path relativo corretto; altrimenti placeholder:
   `> 📸 *Screenshot da aggiungere dopo il redesign UI (glow up).*`
4. **Dipendenze**: file/moduli da cui dipende e che ne dipendono.

Mappatura contenuto tecnico esistente da riorganizzare (non riscrivere da zero, ma
estrarre/adattare da `docs/MODEL_INTERPRETABILITY.md` e `docs/scoring_methodology.md`
già presenti e validi):
- `core/models/README.md` ← sezioni quantile regression, VORP, Fair Price da
  `MODEL_INTERPRETABILITY.md`.
- `modules/lineup/README.md` ← formula xPts e MILP da `MODEL_INTERPRETABILITY.md` /
  capitolato Pilastro 4.
- `modules/valuation/README.md` ← Power Rankings, Fragilità, Draft Badges.
- `modules/trades/README.md` ← Utilità Marginale, Win-Win Detector.
- `core/ingestion/README.md` ← scraping resiliente, fallback, EWMA, odds devigging.
- `core/copilot/README.md` ← architettura provider-agnostic già documentata in
  precedenti pilastri (verificare se già esiste un doc simile, altrimenti scrivere ex novo).

Il `README.md` radice diventa un indice con link a tutti questi, oltre a quickstart e
badge.

## Timeline di Progetto

`docs/it/TIMELINE_PROGETTO.md` (e versione EN): narrazione in 3 parti —
1. **Da dove veniamo**: script pre-asta monolitico, calcolo statico di quotazioni,
   nessuna gestione della stagione.
2. **Dove siamo ora**: pipeline ML a quantili (P10/P50/P90), VORP, MILP per formazioni,
   feed dinamico infrasettimanale, audit post-asta, trade analyzer, AI copilot locale,
   tutorial interattivo — piattaforma end-to-end per le 38 giornate.
3. **Dove vogliamo arrivare**: visione alto-livello (piattaforma statistica di
   riferimento per il fantacalcio data-driven, possibile community open-source attorno
   al non-commercial core, eventuale commercializzazione futura di una versione
   premium/managed una volta maturo il prodotto — nessun impegno di roadmap concreta).

Focus esplicito sull'approccio statistico come filo conduttore di ogni fase (dal singolo
numero deterministico alla distribuzione probabilistica, dalla quotazione fissa al
prezzo equo dinamico via VORP).

## Criteri di Accettazione

1. `pytest tests/ -v` passa con lo stesso conteggio della baseline attuale (89 passed +
   1 errore preesistente non correlato) dopo il refactor.
2. Nessun import rotto: verifica `grep -rn "from pipeline\|import pipeline\b"` e
   `grep -rn "^import config$\|from copilot import"` su tutto il repo → zero risultati
   residui (tutti sostituiti con i nuovi path `core.*`).
3. `web/app.py` avviato localmente serve correttamente `web/static/css/*` e
   `web/static/js/*` (verifica curl, come nei pilastri precedenti).
4. Nessuna occorrenza di "MIT" rimasta in badge/doc/LICENSE.
5. Ogni cartella modulo elencata ha un `README.md` con le 4 sezioni previste.
6. `docs/it/TIMELINE_PROGETTO.md` e `docs/en/PROJECT_TIMELINE.md` esistono e coprono le
   3 parti richieste.
7. `run_pipeline.py`, `.github/workflows/dynamic_feed.yml`, `vercel.json` puntano tutti
   ai nuovi path e nessuno dei tre contiene più riferimenti a `pipeline.` o `app.py` (root).

## Fuori Ambito (esplicitamente escluso da questo pilastro)

- Estrazione della logica d'asta da `web/app.py` in `modules/auction/*.py` (solo README
  documentale, nessun codice spostato).
- Redesign visivo della UI ("glow up") e cattura di screenshot reali — rimandato a un
  pilastro futuro; qui solo placeholder testuali dove mancano immagini.
- Introduzione di un framework i18n per la UI runtime (già deciso nel Pilastro 6: la UI
  resta italiano-only; il bilinguismo riguarda solo la documentazione in `docs/`).
