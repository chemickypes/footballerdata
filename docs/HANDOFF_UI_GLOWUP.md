# Handoff — UI Glow-Up "Officina Vittoriana" (fanta-lab)

Documento di passaggio consegne, pensato per essere letto da un'altra sessione/AI
con **zero memoria della conversazione precedente**. Contiene tutto il contesto
necessario per continuare il lavoro, capire le decisioni prese e sapere cosa manca.

Ultimo aggiornamento: al completamento del branch `ui-glowup` (commit `1d6742d`),
subito dopo un deploy di verifica in produzione su Vercel.

---

## 1. Contesto generale del progetto (storia pregressa, prima di questo branch)

`fanta-lab` è un'app Flask (`web/app.py`, template monolitico HTML+CSS+JS embedded
in Python) per la gestione di un fantacalcio: analisi statistica/ML dei giocatori,
asta, gestione rose, tab tattico con campo 2D, ecc.

In sessioni precedenti a questa (non ricostruite in dettaglio qui, ma rilevanti se
si toccano quelle aree) sono stati affrontati grandi pilastri architetturali:

- **Pilastro 1 — Dual-track architecture**: il repo pubblico GitHub (community,
  MIT license, nessun dato sensibile) e l'istanza privata deployata su Vercel
  devono condividere lo stesso codice ma differire per configurazione. Meccanismo:
  `core/config.py` legge `APP_ENV` (`community`|`personal`) e, se `personal`,
  carica `LEAGUE_PRIVATE_CONFIG` (JSON) da variabile d'ambiente. File
  `core/config.personal.py` e `.env.local` sono in `.gitignore`; esiste solo
  `core/config.personal.example.py` come template tracciato. **Vincolo importante**:
  su Vercel il filesystem è read-only a runtime — l'app non deve mai fare
  `open(..., 'w')` per salvare stato; tutto passa da `localStorage` lato client.
- **Pilastro 2 — Bugfix pipeline ML critici**: fix su `player_id` vuoti nello
  scraping storico (`01_scrape_historical.py`) con fallback deterministico su
  `nome+ruolo` in `08_quantile_points_model.py`; resilienza scraping infortuni
  Transfermarkt (`05_scrape_injuries.py`, rotazione User-Agent, backoff, dataset
  di riserva); controllo colonne richieste in `07_generate_excel.py`.
- **Ristrutturazione repo (Pilastro 7)**: riorganizzazione cartelle, licenza MIT,
  README per modulo.
- **Naming**: le repo GitHub sono sotto l'account/organizzazione `spectrelabo`
  (nome usato solo come "brand" delle repo, **non è una società/entità legale**
  dell'utente — da tenere presente per qualunque testo, licenza o doc che parli
  dell'autore/organizzazione).

Se una sessione futura deve lavorare su questi pilastri, non ci sono modifiche
pendenti note: erano stati completati prima dell'inizio di questo segmento.

---

## 2. Questo segmento: UI Glow-Up "Officina Vittoriana"

### 2.1 Richiesta originale dell'utente

L'utente ha chiesto un restyling profondo del frontend con queste caratteristiche:
- Look "da videogioco": login/accesso come schermata identitaria, tab come
  "modalità di gioco", animazioni.
- Dopo un primo giro di mockup (opzione "A" scelta dall'utente, senza emoji
  standard, con libreria icone più curata e più animazioni), l'utente ha
  richiesto un **redesign delle tab** (troppo grandi rispetto al contenuto,
  stile interno "da designer junior").
- L'utente ha esplicitamente chiesto di **preparare una skill/agent con un
  modello più performante per il design** prima di procedere con l'implementazione
  vera e propria — è stata quindi condotta una fase di brainstorming/design con
  un modello ad alta capacità, producendo mockup HTML statici approvati in
  `.superpowers/brainstorm/mockups-davinci-mascot/` (4 file: mascot-hero,
  mascot-tutorial-context, pitch-davinci-auction, pitch-davinci-lineup).
- Tema finale approvato: **"Officina Vittoriana"** — estetica steampunk/da-vinci-esca
  (ottone, cuoio, pergamena, inchiostro seppia) con una mascotte "Maestro" in stile
  Leonardo da Vinci che accompagna l'utente (splash iniziale, tutorial, presenza
  ambientale fluttuante), e un componente "campo tattico" disegnato come schizzo
  di Leonardo (SVG generato, non più `<div>` statici).

### 2.2 Documenti di riferimento (letture consigliate se si riprende il lavoro)

- `docs/superpowers/specs/2026-09-07-ui-glowup-design.md` — spec di design approvata
  (a monte del piano). Descrive l'intera visione: splash gate, mascotte Maestro,
  nav Officina Vittoriana, componente Da Vinci pitch condiviso.
- `docs/superpowers/plans/2026-09-07-ui-glowup-implementation.md` — piano di
  implementazione a 8 task (1624 righe), con vincoli globali e target di codice
  precisi per ogni task. **Questo è il documento con la massima autorità tecnica**
  su cosa doveva essere fatto e perché.
- `.superpowers/brainstorm/mockups-davinci-mascot/*.html` / `*.png` — i 4 mockup
  visivi approvati dall'utente, usati come riferimento per ogni verifica visiva
  (nessuno screenshot automatico è stato possibile: niente browser headless
  disponibile, verifica solo strutturale/via codice).

### 2.3 Metodologia di esecuzione

Eseguito con lo skill **subagent-driven-development**: lavoro isolato in un
git worktree (`.worktrees/ui-glowup`, branch `ui-glowup`, creato da `main` al
commit `e72bdc6`), 8 task eseguiti in sequenza ciascuno con:
1. generazione di un "brief" di task,
2. dispatch a un subagent implementatore,
3. dispatch a un subagent reviewer (rigoroso, con requisiti di verifica espliciti),
4. eventuale round di fix se il reviewer trovava problemi "Important",
5. commit con Co-authored-by Copilot.

Al termine, è stata fatta una **review finale dell'intero branch** (9 commit
contro il base `e72bdc6`), con esito **"Ready to merge: Yes"**.

---

## 3. Stato attuale del branch `ui-glowup`

**10 commit sopra `main` (`e72bdc6`)**, worktree in `.worktrees/ui-glowup`:

| Commit | Descrizione |
|---|---|
| `140a7ce` | feat: splash screen identity gate |
| `23d96cb` | fix: riconciliazione precedenza splash gate vs PIN login modal |
| `741a1bf` | feat: restyle bottom nav + session gate (Officina Vittoriana) |
| `aa52dec` | feat: mascotte Maestro ambientale persistente |
| `ffa528b` | fix: nascondere mascotte ambientale durante splash/intro |
| `245e4b3` | feat: aggancio Maestro nel tutorial a spotlight |
| `7c08553` | feat: componente condiviso "Da Vinci pitch" + token sepia |
| `0d9b407` | feat: campo Da Vinci decorativo nel tab Asta |
| `5dc19d8` | feat: restyle campo tattico Rose come tavola Da Vinci (funzionale) |
| `1d6742d` | chore: pulizie finali post-review (CSS morto, commento obsoleto, escaping label) |

**Tutti i commit sono stati rivisti e approvati.** La review finale ha segnalato
solo 3 punti "Minor" (non bloccanti), tutti risolti nel commit `1d6742d`:
CSS morto `.pitch-node*` rimosso, commento nav "5 Tabs" corretto, label SVG del
campo tattico ora passate per `escapeHTML()` (coerenza con la griglia squadre
dello splash).

**Test**: `pytest -q` → 89 passed, 1 errore pre-esistente e non collegato
(`tests/test_dual_track_and_features.py::test`, problema di fixture, esisteva
già prima di questo branch). Invariato per tutti i 10 commit.

**Il branch NON è ancora stato mergiato su `main` né pushato su GitHub.**
Esiste solo localmente nel worktree.

### 3.1 Cosa cambia concretamente (per chi deve orientarsi nel codice)

Tutto il lavoro è in un unico file: `web/app.py`.

- **Splash / Identity Gate** (`#splashIdentityGate`): prima schermata alla prima
  visita, permette di scegliere la propria squadra; si coordina con il modale PIN
  pre-esistente (`#sessionLoginModal`) tramite `maybeStartIdentityGate()` che
  verifica se il PIN modal è già visibile per evitare doppio overlay.
- **Mascotte Maestro**: sprite multi-posa stile Leonardo (`MAESTRO_SPRITES`,
  `renderMaestroSprite`, `setMaestroPose`), presenza ambientale fluttuante
  (`ensureMaestroAmbient`, `updateMaestroAmbientState`, nascosta durante onboarding
  via `body.app-locked .maestro-ambient { display: none !important; }`), e
  agganciata anche ai tooltip del tutorial esistente (`tutorial.js`/`tutorial.css`,
  nuovi campi `maestroText`/`maestroPose` su ciascuno dei 7 step del tour).
- **Nav Officina Vittoriana**: bottom nav ristilizzata (8 tab), nuovi token CSS
  `--officina-brass`, `--officina-gold`, `--officina-leather`, `--officina-wood`,
  `--officina-ink`, `--officina-parchment`, `--maestro-z: 1200`, ecc. (in `:root`,
  vicino a `--role-a`).
- **Componente condiviso "Da Vinci Pitch"** (`getDavinciPitchSvg`, funzione unica
  che genera l'SVG del campo in stile schizzo), usato in due punti:
  - **Tab Asta** (`0d9b407`): versione decorativa (`interactive:false`) accanto
    al lotto attivo, nessun binding di stato live.
  - **Tab Rose** (`5dc19d8`, task a più alto rischio): sostituisce il vecchio
    rendering `.pitch-node` (div statici + `onclick` inline) con token SVG
    generati dinamicamente + `addEventListener` programmatico. La mappatura
    slot↔ruolo↔giocatore (`resolvePitchLineup`, chiave localStorage
    `${role}_${slotIndex}`) è stata verificata byte-per-byte invariata:
    l'ordine di emissione dei token nell'SVG corrisponde esattamente all'ordine
    di riempimento dell'array per ruolo, quindi l'indice del click handler è
    sempre corretto. Nessun leak di listener: `pitchHost.innerHTML = ...` scarta
    i nodi (e i listener) vecchi a ogni render.
  - Token CSS sepia dedicati: `--davinci-role-p/d/c/a` (attenuati rispetto ai
    vivid `--role-p/d/c/a` usati altrove per badge/tabelle, che restano intatti).

### 3.2 Cose "fragili" da tenere d'occhio (non bug, ma note per il futuro)

- `--maestro-z: 1200` funziona solo perché la mascotte ambientale viene
  nascosta con `display:none` durante l'onboarding via classe `app-locked`,
  non per vera separazione di z-order. Se in futuro si aggiungono altri overlay
  con z-index vicino, verificare questa interazione.
- I nomi delle tab nella nav usano etichette in italiano mentre la spec di design
  originale suggeriva descrittori in inglese — scelta cosmetica, nessun impatto
  funzionale.
- Nessuna suite di test automatici copre il frontend: tutta la verifica visiva
  è stata fatta a livello di codice/grep/curl, confrontando manualmente con i
  mockup PNG approvati (nessun tool di screenshot headless disponibile in questo
  ambiente per i subagent). Se in futuro si aggiunge un tool del genere, sarebbe
  utile per validare più rigorosamente i prossimi restyling.

---

## 4. Deploy di verifica su Vercel (eseguito in questo segmento)

Il progetto Vercel esiste già: `spectre-labo/fanta-lab`, con dominio
`https://fanta-lab.vercel.app`. Il worktree è stato collegato con
`vercel link --yes --project fanta-lab --scope spectre-labo` (crea
`.vercel/` locale + `.env.local`, entrambi gitignored).

**Le variabili d'ambiente private** (`APP_ENV`, `LEAGUE_PIN`, `ADMIN_PIN`,
`GROQ_API_KEY`, `GEMINI_API_KEY`) risultano configurate **solo per l'ambiente
Production**, non per Preview. Per questo motivo, e su scelta esplicita
dell'utente, il test del branch `ui-glowup` è stato fatto con
**`vercel --prod` direttamente dal branch `ui-glowup`** (non da un deploy
Preview), cosa che ha aggiornato la produzione live su `fanta-lab.vercel.app`
con questo codice **prima ancora del push su GitHub**.

Esito: deploy riuscito (build ~53s, dipendenze Python installate via `uv`),
alias `fanta-lab.vercel.app` aggiornato, verificato con curl: risposta HTTP 200
e markup contenente `Officina Vittoriana`, `maestroAmbient`, `davinci-token`.

**⚠️ Importante per la prossima sessione**: la produzione live su Vercel ora
serve il codice del branch `ui-glowup`, **non quello di `main`**. Se in futuro
si fa un altro deploy da `main` (es. per un hotfix separato) o si collega il
deploy automatico a GitHub (`vercel git connect`), la produzione tornerebbe al
codice vecchio finché `ui-glowup` non viene mergiato su `main`. Ricordarsi di
mergiare `ui-glowup` → `main` per rendere permanente questo stato, o di
ri-deployare esplicitamente se si lavora nel frattempo su `main`.

---

## 5. Cosa manca / prossimi passi consigliati

1. **Merge del branch `ui-glowup` su `main`** — non ancora fatto. Consigliato
   usare lo skill `finishing-a-development-branch` per scegliere tra
   merge diretto, PR, o altre opzioni di integrazione.
2. **Push su GitHub** — l'utente ha esplicitamente chiesto di testare su Vercel
   *prima* del push su GitHub; ora che il test è stato fatto con successo, il
   push è lo step naturale successivo (da confermare con l'utente).
3. **Collegare il deploy Vercel a Git** (`vercel git connect`), se si vuole
   automatizzare i deploy futuri sul push — attualmente il deploy è manuale via
   CLI, come da vincolo Pilastro 1 (dual-track).
4. Nessun'altra pulizia di codice nota è pendente: la review finale ha dato
   "Ready to merge: Yes" e tutti i punti minori sono stati risolti nel commit
   `1d6742d`.

---

## 6. File chiave per orientarsi rapidamente

- `web/app.py` — l'intera app (template Flask monolitico), unico file toccato
  da questo segmento.
- `web/static/js/tutorial.js` / `web/static/css/tutorial.css` — sistema tutorial
  a spotlight pre-esistente, esteso (non duplicato) per agganciare il Maestro.
- `docs/superpowers/specs/2026-09-07-ui-glowup-design.md` — spec di design.
- `docs/superpowers/plans/2026-09-07-ui-glowup-implementation.md` — piano a 8 task.
- `.superpowers/sdd/progress.md` — ledger di avanzamento dei task (scratch,
  gitignored, utile solo per contesto storico locale).
- `vercel.json` — config deploy (`@vercel/python` su `web/app.py`), invariato.
- `core/config.personal.example.py` — template config personale (dual-track);
  la config reale vive solo come env var Vercel (`LEAGUE_PRIVATE_CONFIG`) o in
  un file locale gitignored, mai committata.
