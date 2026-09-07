# Design: Tutorial Interattivo Spotlight (Pilastro 6)

## Contesto e scope

Il capitolato originale (Pilastro 6) richiedeva due elementi UI: (1) una Finestra Medica per la
scheda giocatore e (2) un Tutorial Interattivo in-game. Un audit del repository ha verificato che
la **Finestra Medica esiste già ed è completa**: il drawer `#playerDetailDrawer` (app.py,
funzione `openPlayerDetailDrawer`) mostra badge stato clinico (🟢/🟡/🔴 con soglie 15/60 giorni
esattamente come da capitolato), giorni di indisponibilità, elenco lesioni, metriche Understat
(xG/90, npxG/90, xA/90, tiri/90), delta gol reali vs xG, e la forchetta quantile P10/P50/P90 con
spread di volatilità e barra visiva. Nessuna modifica è quindi necessaria su questo fronte.

**Questo documento copre esclusivamente il secondo elemento: il Tutorial Interattivo Spotlight**,
che non esiste ancora nel repository (verificato: nessun file, nessuna funzione, nessuna chiave
`fanta_tour_done` in localStorage).

**Decisione linguistica** (chiarita con l'utente): l'app è rivolta a un pubblico italiano ed è
interamente in italiano, senza alcun sistema i18n. Il requisito di bilinguismo IT/EN del
capitolato originale riguardava la convenzione di documentazione dei repository open-source
(README, docs), non la UI applicativa. **Il tutorial sarà quindi esclusivamente in italiano**,
coerente con il resto dell'app. Non viene introdotto alcun framework di internazionalizzazione.

## Architettura

Due nuovi file statici, zero dipendenze esterne. Il repository serve già gli asset statici da una
cartella `static/` alla radice del progetto tramite la route Flask esistente
`@app.route("/static/<path:path>")` (`app.py:819-821`, `send_from_directory(BASE_DIR/"static", path)`).
I nuovi file seguono questo stesso pattern già in uso (non la struttura `web/static/` ipotizzata dal
capitolato originale, che non corrisponde all'attuale organizzazione del repository):

- `static/js/tutorial.js` — modulo IIFE che espone un singolo oggetto globale `FantaTour` con
  API pubblica `FantaTour.start()` e `FantaTour.maybeAutoStart()`.
- `static/css/tutorial.css` — stili per overlay, spotlight, tooltip, frecce direzionali,
  pulsanti, indicatore di progresso, transizioni.

Vengono referenziati nell'`HTML_TEMPLATE` con `<link rel="stylesheet" href="/static/css/tutorial.css">`
e `<script src="/static/js/tutorial.js"></script>`, coerenti con eventuali altri asset statici già
linkati nel template (se presenti, verificarne il pattern esatto in fase di implementazione).

### Meccanismo di spotlight (ritaglio dinamico)

Anziché un singolo overlay con `box-shadow: 0 0 0 9999px` (che richiede calcolare bordi ellittici
o rettangolari in un pseudo-elemento e non gestisce bene bordi arrotondati su elementi di forma
irregolare), si usa la tecnica **a 4 rettangoli**: 4 `<div>` assolutamente posizionati (sopra,
sotto, sinistra, destra dell'elemento target, calcolati da `getBoundingClientRect()`), ciascuno
con `background: rgba(0,0,0,0.75)`, che insieme coprono l'intero viewport tranne il rettangolo del
target. Questo produce lo stesso effetto visivo dello spotlight richiesto dal capitolato, è più
semplice da calcolare/mantenere per elementi di larghezza/altezza variabile, e si aggiorna
correttamente su `resize`/`scroll` ricalcolando i 4 rettangoli.

Il rettangolo del target riceve inoltre un contorno luminoso (`box-shadow` esterno più sottile,
es. `0 0 0 3px var(--gold)`) per rinforzare l'evidenziazione, applicato tramite una quinta `<div>`
posizionata esattamente sopra il target con `pointer-events: none` (per non intercettare i click
sull'elemento reale sottostante).

### Tooltip e controlli

Un tooltip (`<div class="tour-tooltip">`) ancorato al bordo dell'elemento target (sopra/sotto,
scelto automaticamente in base allo spazio disponibile nel viewport, con una piccola freccia CSS
triangolare che punta verso il target) contiene:
- Titolo dello step (es. "Pannello Impostazioni")
- Testo descrittivo (1-2 frasi)
- Indicatore "Passo X di N"
- Pulsanti: "Indietro" (disabilitato al primo step), "Avanti" (diventa "Fine" all'ultimo step),
  "Salta Tutorial (X)" sempre visibile in alto a destra del tooltip

### Gestione step cross-tab

Ogni step dichiara, oltre al selettore CSS del target, un campo opzionale `requiresTab` (es.
`"listone"`, `"strategy"`, `"lineup"`). Prima di renderizzare lo step, `FantaTour` verifica se
`requiresTab` è definito e diverso dal tab attualmente attivo; in tal caso invoca la funzione
globale `switchTab(requiresTab)` già esistente in `app.py`, attende un breve timeout (100ms, per
consentire al DOM del tab di renderizzarsi — i tab esistenti in questa app sono già tutti presenti
nel DOM e semplicemente nascosti/mostrati via `display:none`, quindi non serve attendere fetch di
rete) e solo dopo calcola la posizione dell'elemento target e mostra lo step.

Se un elemento target non viene trovato nel DOM (`querySelector` restituisce `null` — es. per un
cambiamento futuro di markup), lo step viene saltato automaticamente con un avviso in console,
senza bloccare il tour né lanciare eccezioni visibili all'utente.

### Percorso del tour (7 step)

| # | Selettore target | requiresTab | Titolo | Testo |
|---|---|---|---|---|
| 1 | `#btnLeagueSettings` | — (nessuno, è nella navbar sempre visibile) | Pannello Impostazioni | "Configura qui budget di lega, numero di squadre e slot per ruolo. Puoi modificarli in qualsiasi momento." |
| 2 | `#sideNav-strategy` | — | Blueprint Strategici | "Scegli tra 5 piani tattici pre-configurati (es. Trazione Anteriore, Moneyball) con soglie di spesa per ruolo calcolate sul tuo budget di lega." |
| 3 | `#tab-listone` (o prima riga renderizzata di `#listoneContainer`, se presente nel DOM al momento dello step) | `listone` | Colonne Listone | "Le colonne chiave: Prezzo Equo (il massimo razionale da offrire), P50 (punti attesi), e Surplus di Mercato (l'affare potenziale rispetto alla quotazione)." |
| 4 | Il primo badge/elemento medico cliccabile visibile nella riga giocatore (`.medical-badge`, se presente nel DOM in quel momento; altrimenti fallback al selettore dell'header colonna corrispondente) | `listone` | Scheda Clinica | "Clicca il badge medico di un giocatore per aprire la sua cartella clinica: stato di rischio, giorni di infortunio, e metriche avanzate xG/xA." |
| 5 | `#sideNav-draft` | — | Modulo Asta | "Qui gestisci l'asta live: assegnazione giocatori, tracciamento budget, live draft." |
| 6 | `#sideNav-lineup` | — | Formazione Settimanale | "Calcola la formazione ottimale della giornata in base a probabili formazioni, quote e xPts." |
| 7 | `#sideNav-audit` | — | Valutatore & Scambi | "Analizza la classifica di lega post-asta e valuta scambi vantaggiosi con gli altri manager nella sezione Scambi." |

Nota sullo step 7: il capitolato originale raggruppa "Valutatore e Scambi" come un'unica tappa di
"Navigazione Moduli". Si mantiene un singolo step ancorato a `#sideNav-audit` (Valutatore) il cui
testo menziona esplicitamente anche la sezione Scambi, evitando di introdurre un ottavo step
ridondante per due bottoni adiacenti nella stessa area di navbar.

Per gli step 3 e 4, se l'elemento a granularità fine (prima riga tabella / primo badge medico) non
è disponibile nel DOM (es. dataset vuoto, o timing di caricamento asincrono del listone), il target
degrada automaticamente al contenitore padre più stabile (`#listoneContainer` o l'header tabella),
così il tour non si blocca in ambienti con dati non ancora caricati.

### Persistenza e riavvio

- Al completamento del tour (click "Fine" sull'ultimo step) o al click su "Salta Tutorial":
  `localStorage.setItem('fanta_tour_done', 'true')`.
- Un nuovo bottone "❓ Guida" viene aggiunto alla navbar esistente (area già usata da altri bottoni
  profilo/admin, es. vicino a `#btnLeagueSettings`), sempre visibile, che chiama
  `FantaTour.start()` incondizionatamente (ignora il flag — permette di rivedere il tour a
  richiesta).
- All'avvio pagina (`window.onload`, dopo la funzione `init()` esistente), viene chiamato
  `FantaTour.maybeAutoStart()`, che controlla il flag in localStorage e avvia il tour solo se
  assente/diverso da `'true'`, con un breve ritardo (es. 600ms) per lasciare che il rendering
  iniziale della UI si stabilizzi.

### Stile visivo

Coerente con il tema dark esistente dell'app (variabili CSS già definite: `--surface`,
`--border`, `--primary`, `--gold`, `--text-muted`). L'overlay usa `rgba(0,0,0,0.75)` come da
capitolato. Font e border-radius del tooltip coerenti con `.modal-box` esistente.

### Responsive

Su viewport mobile (dove esiste già una bottom-nav separata dalla sidebar), gli step che puntano a
bottoni della sidebar (`#sideNav-*`) verificano anche l'esistenza dell'equivalente bottone
bottom-nav (`#botNav-*`, se lo step lo prevede) e usano quello come target quando la sidebar non è
visibile (media query / controllo `offsetParent !== null` per determinare visibilità reale
dell'elemento).

## Testing

Nessun test automatico Python (JS/CSS puramente visivo, coerente con l'approccio già usato per
Task 7 di Pilastro 4 — nessuna suite di test frontend esiste in questo repository). Verifica
manuale equivalente:
1. Avvio server, curl della pagina index, grep per conferma presenza dei nuovi tag `<link>`/
   `<script>`, del bottone "❓ Guida", e che i file statici `tutorial.js`/`tutorial.css`
   rispondano con 200.
2. Ispezione statica del JS per bilanciamento parentesi/backtick (stesso controllo already
   applicato nella review finale di Pilastro 4).
3. Esecuzione della suite pytest esistente per confermare zero regressioni.

## Criteri di accettazione

- I 2 nuovi file esistono con i percorsi indicati e sono serviti correttamente da Flask (200 OK).
- Il bottone "❓ Guida" è sempre visibile in navbar e riavvia il tour anche dopo il completamento.
- Il tour naviga automaticamente tra i tab necessari per ciascuno dei 7 step.
- Il completamento o lo skip del tour persiste `fanta_tour_done` in localStorage.
- Nessuna regressione nella suite pytest esistente (89 test attualmente passanti + 1 errore
  preesistente non correlato, invariato).
- Nessuna dipendenza esterna aggiunta (zero librerie JS/CSS di terze parti).
