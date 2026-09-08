# Rebrand: "Spectre - FantaMoneyball" → "La FantaOfficina"

## Contesto

L'app è attualmente brandizzata come "Spectre - FantaMoneyball" nel codice
(`web/app.py`, `README.md`) e vive nel repo GitHub `spectrelabo/fanta-lab`.
L'utente ha richiesto un rebrand completo verso un nuovo nome, coerente con
il tema visivo "Officina Vittoriana" già implementato nel precedente segmento
di UI glow-up (mascotte "Maestro" in stile Leonardo da Vinci, estetica
ottone/cuoio/pergamena).

Nota di chiarimento importante (da appunti cartacei dell'utente, scansione
8 set 2026): il nome "FantaLab" visto negli schizzi si riferiva a
un'applicazione di aste **esterna e già esistente**, integrata via
`live_bridge/` per leggere dati live durante l'asta — non è né era il nome
del nostro progetto. Questo rebrand non tocca in alcun modo quell'integrazione.

## Obiettivo

Rinominare il brand dell'applicazione da "Spectre - FantaMoneyball" a
**"La FantaOfficina"**, e il bot AI da "FantaMoneyball AI" a **"Il Maestro"**
(riusando il nome della mascotte già esistente), sia nel codice applicativo
sia nella documentazione e nel repository GitHub.

## Scope

### In scope

1. **Branding nell'app** (`web/app.py`):
   - Titolo pagina (`<title>`), header/splash screen, testi di benvenuto.
   - Docstring del modulo (righe 3-4).
   - `BOT_NAME` default: `"FantaMoneyball AI"` → `"Il Maestro"`.
   - Messaggio di benvenuto del bot (riga ~140) e ogni testo che cita il nome
     del bot per esteso, riscritto in coerenza con "Il Maestro".
   - Commento "FantaMoneyball AI Tactical Engine" (riga ~1354).
   - Banner ASCII stampato all'avvio del server (riga ~8377).
   - Qualunque altra occorrenza letterale di "Spectre - FantaMoneyball" o
     "FantaMoneyball" trovata via grep in fase di implementazione.

2. **README.md**:
   - Titolo principale e testi descrittivi che citano il vecchio nome.
   - Comando `git clone` aggiornato al nuovo slug repo
     (`https://github.com/spectrelabo/fantaofficina.git`).
   - Albero directory di esempio (`fanta-lab/` → `fantaofficina/`, se presente
     come testo illustrativo).

3. **Repository GitHub**: rinominato da `spectrelabo/fanta-lab` a
   `spectrelabo/fantaofficina` (tramite l'impostazione "rename" di GitHub, che
   crea automaticamente un redirect dal vecchio nome/URL).

4. **Cartella locale del progetto**: rinominata da `fanta-lab/` a
   `fantaofficina/` sul filesystem locale dell'utente.

5. **Remote git locale**: dopo il rename su GitHub, aggiornare l'URL del
   remote `origin` nella cartella locale rinominata per puntare al nuovo
   percorso repo (GitHub redirige comunque, ma è buona norma allinearlo).

### Esplicitamente fuori scope

- **`LICENSE`**: il copyright `Copyright (c) 2026 SpectreLabo` resta
  invariato — è il nome dell'account/organizzazione GitHub, non l'oggetto
  del rebrand applicativo, e l'utente ha confermato di non volerlo toccare.
- **Progetto e dominio Vercel**: resta `fanta-lab` / `fanta-lab.vercel.app`.
  Nessuna modifica alla configurazione o al progetto Vercel in questo lavoro.
- **`live_bridge/` e chiavi localStorage `fantalab_room_id`/`fantalab_shard`**:
  queste si riferiscono all'applicazione esterna di aste "FantaLab" (integrazione
  RTDB già esistente e matura, vedi `live_bridge/adapter.py`) e vanno lasciate
  **identiche** — non sono parte del nostro brand.
- **Branch `ui-glowup`** (worktree separato, non ancora mergiato): il rebrand
  si applica al branch `main`. Se `ui-glowup` verrà mergiato successivamente,
  un eventuale conflitto testuale sulle stringhe di branding andrà risolto in
  quel momento (probabilmente banale, dato che il rebrand tocca prevalentemente
  testo statico non riscritto dal glow-up).

## Approccio

Rename testuale diretto via grep + edit mirato su `web/app.py` e `README.md`,
seguito da:
1. Rinomina del repository su GitHub (via GitHub UI o `gh repo rename`).
2. Rinomina della cartella locale (`mv`) e aggiornamento del remote `origin`.
3. Verifica: riavvio del server Flask locale, controllo visivo di title/splash/
   header/banner, grep finale per assicurarsi che non restino occorrenze
   testuali del vecchio nome (escludendo `live_bridge/` e le chiavi
   `fantalab_*` in localStorage, che sono correttamente invariate).
4. `pytest -q` per confermare che nessun test dipenda da stringhe di branding
   ora cambiate (grep preventivo su `tests/` per "FantaMoneyball"/"Spectre").

## Criteri di accettazione

- Nessuna occorrenza testuale di "FantaMoneyball" o "Spectre - FantaMoneyball"
  rimane in `web/app.py` o `README.md` (verificabile via grep), ad eccezione
  del changelog/handoff storici in `docs/` che documentano il nome precedente
  (questi restano come registro storico, non richiedono modifica).
- Il bot AI si presenta come "Il Maestro" in ogni punto dell'interfaccia dove
  prima appariva "FantaMoneyball AI".
- Il repo GitHub risulta rinominato in `spectrelabo/fantaofficina`, con il
  vecchio URL che reindirizza correttamente (comportamento nativo GitHub).
- La cartella locale del progetto è `fantaofficina/` e il remote `origin`
  punta al nuovo URL del repo.
- `pytest -q` resta verde (89 passed, stesso errore pre-esistente non
  collegato, invariato rispetto alla baseline).
- L'app avviata localmente (`python3 app.py`) mostra "La FantaOfficina" nel
  banner di avvio, nel titolo di pagina e nell'header/splash.
