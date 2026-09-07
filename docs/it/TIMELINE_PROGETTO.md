# Timeline del progetto

Questa pagina racconta la storia di `fanta-lab`: da dove è partito, cosa è diventato attraverso sette pilastri di lavoro, e verso quale idea di prodotto si sta muovendo. Non è un changelog tecnico — per quello ci sono i README dei singoli moduli — ma una narrazione pensata per chiunque voglia capire *perché* il progetto è fatto così.

## 1. Da dove veniamo

`fanta-lab` è nato come uno script pensato per un solo momento della stagione: l'asta pre-campionato. L'obiettivo era semplice e circoscritto — dato un listone di calciatori, produrre un prezzo "giusto" a cui comprarli, da consultare la sera del draft e poi accantonare fino all'anno successivo.

Il cuore statistico di quella prima versione era una regressione quantile (Gradient Boosting Regressor) allenata sui dati storici dei giocatori, capace di stimare non un singolo numero ma tre percentili dei punti attesi a fine stagione: P10 (scenario pessimista), P50 (scenario mediano) e P90 (scenario ottimista). Da questa distribuzione di punti attesi si derivava il VORP (Value Over Replacement Player), che confrontava ogni giocatore con un ipotetico sostituto di livello base nel suo ruolo per arrivare a un fair price coerente con il budget d'asta.

Era, in sostanza, una fotografia: un unico calcolo, fatto una volta, per decidere come spendere il budget in un'unica serata. Tutto quello che è successo dopo — i sette pilastri descritti qui sotto — è la storia di come quella fotografia sia diventata un film: un sistema che continua a osservare, aggiornare e ricalibrare le proprie stime lungo l'intero arco delle 38 giornate di campionato.

## 2. Cosa abbiamo costruito (Pilastri 1-7)

**Pilastro 1 — Dual-track community/personal.** Il primo passo di maturazione architetturale: separare una configurazione "community", pensata per essere condivisa e riprodotta da chiunque cloni il repository, da una configurazione "personal", con dati e parametri specifici di chi usa il progetto per la propria lega. La cascata di configurazione guidata dalla variabile d'ambiente `APP_ENV` ha reso possibile questa distinzione senza duplicare codice.

**Pilastro 2 — Bugfix critici.** Una serie di correzioni che hanno reso il sistema affidabile in produzione: un fallback su `player_id` per garantire la riproducibilità del training anche quando l'identificativo primario non è disponibile; maggiore resilienza dello scraping da Transfermarkt, con meccanismi di fallback quando le pagine cambiano struttura o non rispondono; una ricalibrazione dei percentili della Scala Slot per tenere conto delle differenze tra ruoli; e un blueprint di percentuali dinamiche, riscalate sul budget effettivo della lega invece di un valore fisso.

**Pilastro 3 — Feed dinamico infrasettimanale.** Il cambio di paradigma più importante dal punto di vista statistico: l'introduzione di un feed dati che si aggiorna automaticamente tre volte a settimana, per tutte le 38 giornate di campionato, tramite GitHub Actions e una branch orfana (`data-feed`) dedicata a ospitare questi aggiornamenti senza inquinare la storia del codice sorgente. Da qui in poi, le stime non sono più fissate all'asta ma vive per l'intera stagione.

**Pilastro 4 — Moduli analitici.** La costruzione di strumenti pensati per l'uso settimanale, non più solo pre-asta: un Weekly Lineup Solver basato su programmazione lineare intera mista (MILP) per scegliere la formazione ottimale rispettando i vincoli di modulo e ruoli; un Post-Draft Audit con Power Rankings per valutare l'andamento della propria asta rispetto agli avversari; e una Trade Machine capace di valutare gli scambi in base all'utilità marginale che ciascun giocatore porta alla squadra, non solo al suo valore assoluto.

**Pilastro 5 — AI copilot locale.** L'introduzione di un assistente AI "provider-agnostic", capace di funzionare con diversi backend (incluso Ollama in locale, a costo zero), per affiancare l'utente nell'interpretazione dei dati e nelle decisioni tattiche senza dipendere da un singolo fornitore o da costi ricorrenti.

**Pilastro 6 — Finestra medica e onboarding.** Un'attenzione crescente all'esperienza utente: un sistema di badge di fragilità (🟢🟡🔴) per segnalare a colpo d'occhio il rischio infortuni di un giocatore, e un tutorial interattivo con spotlight per accompagnare i nuovi utenti nella scoperta delle funzionalità.

**Pilastro 7 — Questa ristrutturazione.** La riorganizzazione del repository in tre aree — `core/`, `modules/`, `web/` — con confini di dipendenza espliciti, il passaggio della licenza a PolyForm Noncommercial 1.0.0 e la scrittura di documentazione dedicata per ciascun modulo. È il pilastro che rende sostenibile tutto ciò che è venuto prima: senza una struttura chiara, l'accumulo di funzionalità dei Pilastri 1-6 sarebbe diventato via via più difficile da mantenere e da estendere.

Il filo conduttore di questi sette pilastri, dal punto di vista statistico, è il passaggio da una stima puntuale calcolata una sola volta a un sistema che aggiorna continuamente le proprie probabilità: le quote dei bookmaker vengono "devigged" (private del margine implicito) per estrarre probabilità pulite, la forma recente dei giocatori viene pesata con una media mobile esponenziale (EWMA) che dà più peso alle partite più recenti, e la probabilità di essere titolare viene stimata e aggiornata partita dopo partita. Il risultato è un sistema che non fotografa più un singolo momento, ma accompagna l'utente lungo l'intera stagione.

## 3. Dove vogliamo arrivare

La direzione verso cui il progetto si muove non è un elenco di funzionalità da spuntare, ma un'idea di fondo: rendere l'incertezza statistica sempre più centrale e sempre più accessibile.

Da un lato, vogliamo che il motore predittivo ragioni sempre di più in termini di distribuzioni intere piuttosto che di singoli punti attesi — non "quanti punti farà questo giocatore", ma "con quale probabilità farà più o meno punti di questa soglia", lasciando che sia l'utente, con il proprio contesto e la propria propensione al rischio, a decidere come usare quell'informazione.

Dall'altro, vogliamo che l'AI copilot guadagni progressivamente più autonomia nel suggerire decisioni in-season — non solo rispondere a domande, ma proporre attivamente formazioni, scambi o correzioni di rotta quando i dati indicano un cambiamento significativo.

Infine, e forse soprattutto, vogliamo che tutta questa sofisticazione statistica — quantili, VORP, indici di fragilità — resti o diventi accessibile a chi non ha competenze tecniche. Il valore di un sistema come questo non sta nella complessità dei suoi calcoli, ma nella capacità di tradurli in decisioni comprensibili per chi gioca a fantacalcio per divertirsi, non per fare data science.
