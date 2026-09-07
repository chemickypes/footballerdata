# Fanta-Lab UI Glow-Up: Design Spec

**Data:** 2026-09-07
**Stato:** Approvato dall'utente in sede di brainstorming (skill `superpowers:brainstorming`), pronto per pianificazione implementativa (skill `superpowers:writing-plans`).

## 1. Obiettivo e Contesto

Restyle visivo completo della web app `fanta-lab` (`web/app.py`, Flask monolitico, nessun framework/build step frontend). Il restyle copre: (a) un nuovo splash screen di ingresso in stile "selezione personaggio"; (b) un tema visivo "Officina Vittoriana" (steampunk caldo: ottone, cuoio, legno scuro) per l'intera UI, con le 8 tab principali ridisegnate come card quadrate in stile "taccuino da viaggio"; (c) una mascotte pixel-art ("Il Maestro", un vecchio saggio ibrido Leonardo da Vinci/steampunk) che guida il tutorial e ha una presenza ambientale discreta nell'app; (d) due diagrammi di campo da calcio in stile "appunti di Leonardo da Vinci" (inchiostro seppia su carta invecchiata) per la tab Asta e la tab Formazione.

Questo lavoro NON tocca backend/pipeline/ML — è puro restyle di `web/app.py` e `web/static/`.

## 2. Processo di Design Seguito

Il primo tentativo di mockup rapido (fatto nel visual companion del brainstorming, mockup HTML piatti) è stato esplicitamente giudicato dall'utente insufficiente ("sembra un designer appena laureato"). Di conseguenza sono stati creati:

- **Skill dedicata:** `.agents/skills/web-app-visual-design/SKILL.md` — cattura i motivi del fallimento (emoji al posto di icone vere, componenti sovradimensionati rispetto al contenuto reale, decorazioni scollegate da un riferimento concreto, animazioni generiche) e il workflow corretto (ancorare ogni scelta a un riferimento concreto, prototipare dentro il layout reale non in isolamento, riusare icone/motion language già presenti nell'app).
- **Agent dedicato:** `.github/agents/fantalab-ui-designer.agent.md`, modello `claude-opus-4.8`, `reasoning_effort: high` — usato per produrre mockup e (in seguito) l'implementazione reale.

I mockup prodotti con questo agent (`.superpowers/brainstorm/mockups-davinci-mascot/*.png`) sono stati approvati dall'utente e sono la base di questo spec. **Ogni implementer futuro deve rileggere la SKILL.md prima di modificare `web/app.py`.**

## 3. Splash Screen (Entry Point)

### 3.1 Modello di identità: Profilo Locale Persistente

Confermato modello "A" tra 3 opzioni discusse (Profilo Locale vs Room Code condiviso vs Account veri con backend): nessun account, nessun nuovo backend stateful (coerente col vincolo Vercel serverless read-only già stabilito in Pilastro 1). L'identità utente resta `activeProfileId` in `localStorage`, esattamente come oggi — questo restyle non cambia la logica di persistenza esistente, solo la sua veste grafica e la sua collocazione come primo touchpoint.

### 3.2 Flusso

1. **Prima visita (nessun `activeProfileId` salvato):** schermata a pagina intera "Seleziona la tua Squadra" — card per ogni team di lega (stile selezione personaggio), grafica Officina Vittoriana. Al click si salva `activeProfileId` in `localStorage` come oggi.
2. **Subito dopo la prima selezione:** breve intro de **Il Maestro** (la mascotte, vedi sez. 5) che dà il benvenuto e presenta rapidamente l'app, prima di entrare nella dashboard. Questa intro appare **una sola volta** (stessa logica di gate già usata per `fanta_tour_done` in `localStorage` — un nuovo flag es. `fanta_maestro_intro_done`).
3. **Visite successive:** lo splash si salta automaticamente, si entra direttamente in dashboard.
4. **Separazione dal PIN Asta Live:** il gate PIN esistente (`sessionLoginModal`, team+PIN per la sessione d'asta condivisa) resta un secondo gate **separato e invariato nella logica**, richiesto solo quando l'utente entra nella tab "Asta Live". Solo il suo restyle grafico rientra in questo lavoro, non la sua logica di autenticazione.

### 3.3 Vincoli di implementazione
- Nessuna scrittura sincrona su disco (vincolo Vercel già stabilito) — tutto lo stato dello splash vive in `localStorage`.
- Riusa `activeProfileId` e le strutture dati team già presenti in `/api/state`, non introdurre un nuovo formato dati per i team.

## 4. Tema Visivo: "Officina Vittoriana" — Tab come Taccuini da Viaggio

### 4.1 Direzione visiva approvata

Calda, non fredda: ottone (`#e8b96a`/`#8b6339`), cuoio/legno scuro (`#3a2815`/`#241708`/`#1a1108`), non il verde-rame "Sala Macchine" scartato. Le 8 tab principali (Asta, Obiettivi/Target, Rose, Listone, AI Copilot, Formazione, Audit, Scambi) diventano card quadrate ispirate visivamente ai taccuini da viaggio in pelle mostrati dall'utente (foto di riferimento: quaderni "Traveler's Notebook" con copertina in pelle marmorizzata invecchiata, cornice-illustrazione centrale, laccio/ciondolo).

**Importante — lezione dal secondo tentativo bocciato:** le card-taccuino letterali (grandi, con laccio/ciondolo penzolante, cornice pergamena enorme) sono state giudicate troppo grandi rispetto al contenuto reale e visivamente "basic". La versione approvata (vedi mockup `mascot-hero.html`, header/nav reali) usa una bottom-nav **compatta da 68px di altezza**, non tab-card grandi: icone Font Awesome semanticamente scelte (martello=Asta, bersaglio=Obiettivi, ecc., già presenti in `web/app.py`), bordo ottone sottile, dettaglio rivetto agli angoli **solo se la scala lo permette senza affollare**, glow/pulse sullo stato attivo. Il riferimento "taccuino" informa la **palette e texture** (pelle, ottone, carta invecchiata), non le proporzioni letterali della foto.

### 4.2 Icone
Font Awesome (già caricato in `web/app.py` — verificare con `grep -n "font-awesome\|fa-solid" web/app.py` prima di aggiungere qualsiasi altra libreria). Nessuna emoji nei componenti UI.

### 4.3 Animazioni
Devono essere purposeful, non decorative fini a sé stesse: segnalare stato (attivo/inattivo, hover, successo/errore) o rinforzare la logica del materiale (es. un ingranaggio che ruota ha senso, un rimbalzo casuale no). Riusare le curve di easing (`cubic-bezier`) già presenti in `web/app.py` per mantenere coerenza motion-language, non inventarne di nuove senza motivo.

## 5. Mascotte: "Il Maestro"

### 5.1 Concept
Vecchio saggio ibrido steampunk/Leonardo da Vinci ("inventore, cartografo del calcio e tua guida d'asta" — copy già scritto e approvato nel mockup), reso in **pixel-art 8-bit** via SVG inline costruito su griglia (tecnica scelta dall'agent designer: nessun asset PNG esterno necessario, scalabile, coerente col vincolo "zero build step").

### 5.2 Ruoli e placement (confermati dall'utente)
1. **Narratore del tutorial:** ancorato al tooltip del tour esistente (`web/static/js/tutorial.js` + `tutorial.css`, il sistema di spotlight walkthrough già implementato in Pilastro 6) — il Maestro appare accanto al tooltip con dialoghi contestuali ("Il Prezzo Equo è il massimo razionale da offrire..."). **Non introdurre un nuovo sistema di tutorial**: il Maestro si aggiunge come layer sopra lo spotlight/tooltip esistente, riusando le classi reali (`tour-overlay-rect`, `tour-overlay-highlight`, `tour-tooltip`).
2. **Presenza ambientale fissa:** un piccolo avatar (**64px**, confermato dall'utente come taglia più discreta tra le 3 proposte) ancorato in un angolo fisso dello schermo (bottom-corner, sempre visibile ma non invasivo), NON sopra righe di dati/tabelle — deve restare nel "gutter" visivo.
3. **Intro allo splash screen:** breve apparizione una tantum dopo la prima selezione squadra (vedi sez. 3.2).

### 5.3 Espressività: sprite multi-posa (decisione aggiornata rispetto al mockup iniziale)
Il mockup iniziale usava una singola posa statica. **L'utente ha richiesto più pose** per differenziare i momenti del tutorial/ambient: almeno **saluto** (benvenuto/intro), **indica** (quando il tutorial punta a un elemento specifico), **pensieroso** (quando dà un suggerimento/tip contestuale), oltre alla posa base neutra già prodotta. Ogni posa resta un SVG a griglia pixel-art nello stesso stile (stessa palette, stessa risoluzione griglia ~22×33) per coerenza visiva — è un lavoro di variazione sulla tecnica già validata, non una tecnica nuova.

### 5.4 Vincoli
- Nessun asset immagine binario esterno da gestire/versionare — tutto SVG inline o in un file `.js`/`.css` di supporto sotto `web/static/`.
- Il peek ambientale non deve mai coprire dati reali (celle tabella, badge prezzo) — verificare in fase di implementazione con la vera densità delle tab (Listone in particolare, la più densa).

## 6. Campi "Da Vinci" (Asta + Formazione)

### 6.1 Stile condiviso
Inchiostro seppia su pergamena/carta invecchiata: texture fibra-carta (SVG `feTurbulence`), bordi strappati/irregolari (path SVG non rettangolare), linee campo "disegnate a mano" (leggero `feDisplacementMap` sul wobble delle linee), cross-hatching per le aree ombreggiate, annotazioni in corsivo stile appunti anatomici, marginalia in basso ("Cod. FantaLab, f.34r" nel mockup — dettaglio da mantenere, rinforza il tema "manoscritto"). Tecnica: SVG inline puro, nessun asset raster.

### 6.2 Tab Asta — decorativo, predisposto per interattività futura
Nel mockup approvato appare come "tavola tattica" statica dietro il lotto in asta corrente (nessun token giocatore, nessuna interattività). **Decisione utente:** per ora resta puramente decorativo, ma va **strutturato nel codice in modo da poter diventare in futuro un mini-preview interattivo della formazione live** (es. non hardcodare valori come se il campo fosse un'immagine statica; mantenere il campo come funzione/componente riutilizzabile che accetta già in firma — anche se non ancora popolato — un elenco di posizioni giocatore, così l'evoluzione futura non richieda un riscrittura strutturale). Questa è un'indicazione di **design per l'estensibilità**, non un requisito funzionale di questa iterazione: nessuna logica di preview live va implementata ora.

### 6.3 Tab Formazione — funzionale, sostituisce il campo esistente
Deve rispettare esattamente la struttura del tool reale già esistente in `web/app.py` (selettore modulo, HUD statistiche — Titolari/FantaMedia/xPts/Costo —, righe organizzate per ruolo dall'attacco al portiere, pulsante Auto-Fill, badge di validità modulo). Cambia solo la resa visiva del campo e dei token giocatore:
- **Token giocatore:** "sigilli di ceralacca" a inchiostro (cerchio con iniziale ruolo) + targhetta nome su pergamena, click-to-swap invariato rispetto al comportamento esistente.
- **Colori ruolo:** attenuati/seppia (`#c0533f` A, `#5c9457` D, `#4f89a3` C, `#d99b34` P — valori indicativi dal mockup, non ancora produzione-finale) — **confermato dall'utente**, coerenti col registro "carta antica" invece dei colori pieni attuali. Deve restare una legenda visibile (Portiere/Difesa/Centrocampo/Attacco) per non perdere leggibilità immediata del ruolo.
- **Formazioni multiple:** il campo deve gestire tutti i moduli già supportati dal Lineup Solver di Pilastro 4 (3-4-3, 4-3-3, 4-4-2, ecc.), non solo il 3-4-3 mostrato nel mockup.

## 7. Cosa NON è in scope

- Nessuna modifica a backend, pipeline dati, modelli ML, o logica di autenticazione PIN.
- Nessun nuovo sistema di tutorial (si riusa/estende quello esistente).
- Nessuna funzionalità di preview live interattivo sul campo Asta (solo predisposizione strutturale, sez. 6.2).
- Nessun account utente/backend stateful aggiuntivo (modello di identità resta locale/`localStorage`).
- Nessuna nuova libreria/framework frontend o build step.

## 8. Riferimenti

- Mockup approvati: `.superpowers/brainstorm/mockups-davinci-mascot/{mascot-hero,mascot-tutorial-context,pitch-davinci-auction,pitch-davinci-lineup}.html` (+ screenshot `.png` corrispondenti).
- Skill di design: `.agents/skills/web-app-visual-design/SKILL.md`.
- Agent dedicato: `.github/agents/fantalab-ui-designer.agent.md`.
- Tutorial esistente da riusare: `web/static/js/tutorial.js`, `web/static/css/tutorial.css` (Pilastro 6, già implementato).
- Sistema PIN Asta Live esistente da NON toccare logicamente: `web/app.py` — `sessionLoginModal`, `/api/auth/login`, `/api/auth_admin`.
- Lineup Solver esistente (dati reali per il campo Formazione): `modules/lineup/lineup_solver.py`, formazioni supportate documentate in `modules/lineup/README.md`.
