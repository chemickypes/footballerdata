# Specifica di Design — FantaLab Live Room Advisory (Read-Only)

**Data**: 2026-09-04  
**Stato**: Proposta (In attesa di approvazione)  
**Ambito**: Integrazione a innesto del motore decisionale e client RTDB di `fantabot` in `fanta-lab` per l'asta in tempo reale.

---

## 1. Obiettivi & Requisiti

### 1.1 Obiettivo Primario
Fornire all'utente un **assistente live decisionale in tempo reale** durante l'asta su FantaLab:
- Legge in streaming/polling HTTP rapido la stanza d'asta di FantaLab tramite l'ID fornito dall'utente.
- Identifica il calciatore attualmente chiamato sul banco d'asta e l'offerta corrente.
- Esegue **in toto** l'algoritmo di **Safe Drain Push** (`drain.py`) e le valutazioni di valore di `fantabot`.
- Mostra a video un verdetto semaforico istantaneo (**🟢 RILANCIA FINO A X cr**, **🟡 ATTENZIONE**, **🔴 MOLLA**).
- Registra automaticamente l'acquisto in `auction_state.json` all'assegnazione finale del lotto, senza digitazione manuale.

### 1.2 Vincoli Architetturali
- **Sola Lettura (Read-Only)**: Nessuna offerta o azione automatica viene inviata a FantaLab; l'utente mantiene il controllo esclusivo dei propri rilanci.
- **Zero Regressioni sull'Architettura Esistente**: Tutto il codice esistente di Fanta-Lab (`app.py`, Target a slot, Rose 2D, Listone, Copilot AI) rimane funzionante al 100%. L'assegnazione manuale rimane sempre attiva come fallback.
- **Deployment & Versioning**:
  - Nessun `git push origin main` su GitHub per questo test.
  - Deploy diretto e test su **Vercel** (`vercel --prod`).
  - Compatibilità nativa con Vercel Serverless Functions: uso di chiamate HTTP REST stateless (`rtdb.read_snapshot`) a Firebase RTDB senza necessità di websocket permanenti.

---

## 2. Architettura del Sistema

```
                      FantaLab Firebase RTDB
            (https://fantalab-{shard}.europe-west1.../auction/{room_id}.json)
                                     │
                                     ▼ (GET REST unauthenticated)
                    ┌─────────────────────────────────┐
                    │ fantabot.adapters.http.fantalab │
                    │          (rtdb.py)              │
                    └────────────────┬────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │      live_bridge/adapter.py     │
                    │ (Traduce tra FantaLab & Fantabot)│
                    └───────┬─────────────────┬───────┘
                            │                 │
                            ▼                 ▼
          ┌────────────────────────┐   ┌───────────────────────────┐
          │ fantabot.domain.asta   │   │     Fanta-Lab Core        │
          │       (drain.py)       │   │  - dataset_calciatori     │
          │  - safe_push_cap()     │   │  - auction_state.json     │
          │  - suggest_push()      │   │  - loadUserTargets()      │
          └────────────────────────┘   └─────────────┬─────────────┘
                                                     │
                                                     ▼
                                      /api/live/snapshot Endpoint
                                                     │
                                                     ▼
                                      Tab "Asta Live" Frontend UI
                                      (Advisory Card & Semaforo)
```

### 2.1 Moduli Coinvolti
1. **`engine/fantabot/`**: Codice originale di `fantabot` incorporato senza modifiche:
   - `fantabot.domain.asta.drain`: Logica di push e safe cap.
   - `fantabot.adapters.http.fantalab.rtdb`: Risoluzione shard e `read_snapshot` unauthenticated su Firebase.
2. **`live_bridge/adapter.py`**: Connettore tra Fanta-Lab e `fantabot`:
   - Converte i dati del calciatore di Fanta-Lab (`price_fair`, `target_max_price`, `score`, `pts_exp`) nei parametri attesi da `suggest_push`.
   - Analizza la stanza e i contester attivi.
3. **Endpoint Flask (`app.py`)**:
   - `GET /api/live/snapshot?room_id=<ID>&db=<shard>`:
     - Esegue `read_snapshot` su Firebase.
     - Se c'è un lotto attivo, unisce i dati col nostro dataset.
     - Calcola il consiglio con `suggest_push` e il nostro target personale.
     - Restituisce un payload JSON strutturato con stato stanza, offerta, timer e verdetto.
   - `POST /api/live/sync_sold`:
     - Chiamato quando il lotto si conclude per invocare internamente `api_assign` e aggiornare rose e budget.
4. **Interfaccia Utente (`Asta Live` Tab)**:
   - Widget a comparsa rapida: Input `Room ID` con salvataggio automatico in `localStorage`.
   - Switch `Live Room ON/OFF`.
   - Polling a intervalli regolari (1.5s) attivo solo quando la stanza è aperta e l'utente si trova nel tab Asta.
   - Card del Consiglio Live con badge semaforico colorato e spiegazione sintetica.

---

## 3. Logica Decisionale dell'Advisory Engine

Per ogni lotto sul banco con offerta corrente `current_price` e calciatore `p`:

1. **Verifica Target Personale**:
   - Se il calciatore è in *I Miei Target*, leggiamo `target_max = target.max_price` e priorità `T1/T2/T3`.
   - Se NON è in target, `our_value = fair_live_price` (prezzo fair stimato da Fanta-Lab).

2. **Esecuzione Algoritmo Safe Drain (`drain.py`)**:
   - `cap = safe_push_cap(our_value)`: limite massimo oltre il quale non è mai sicuro spingere.
   - `push_suggestion = suggest_push(...)`:
     - Se il giocatore è nostro target primario: NON si effettua drain puro, si rilancia fino al nostro target personale.
     - Se il giocatore NON è nel nostro piano ma ci sono >= 2 avversari che si contendono l'asta: suggerisce se è possibile rilanciare per far salire il prezzo agli avversari in sicurezza fino al `safe_cap`.

3. **Verdetto Visualizzato a Schermo**:
   - 🟢 **RILANCIA (Target)**: Se `current_price < target_max`. Mostra: *"Rilancia fino a {target_max} cr (Target T{priority})"*
   - 🟢 **RILANCIA (Safe Drain)**: Se `in_our_plan == False`, ma `suggest_push` è valido. Mostra: *"Safe Push: Puoi alzare fino a {cap} cr per drenare crediti a {contesters} avversari"*
   - 🟡 **ATTENZIONE / AL LIMITE**: Se `current_price` è a 1-2 crediti dal valore fair o target.
   - 🔴 **MOLLA / PASSA**: Se `current_price >= target_max` o sopra il fair value, o se lo slot di reparto è già pieno.

---

## 4. Gestione Errori e Casi Limite

| Caso Limite | Gestione |
|---|---|
| Stanza FantaLab vuota o in pausa | Il widget mostra `"Stanza connessa: in attesa della prossima chiamata..."` |
| Nessun lotto attivo sul banco | L'app mantiene il controllo manuale libero |
| Calciatore chiamato non trovato per nome esatto | Normalizzazione stringa (case-insensitive, rimozione accenti/apostrofi) con fallback al nome lotto |
| Timeout di rete su Firebase | Fallback trasparente senza interruzione dell'interfaccia utente |
| Disconnessione manuale | Il polling si interrompe istantaneamente liberando risorse |

---

## 5. Piano di Verifica e Test

1. **Test Unitari su `live_bridge/adapter.py`**:
   - Test con snapshot Firebase fittizio (lotto attivo, offerta corrente, offerente).
   - Verifica dei verdetti per giocatore in Target vs giocatore non in Target.
   - Validazione delle risposte di `drain.suggest_push` (nessun crash, output coerente).
2. **Test Endpoint Flask**:
   - Chiamata di test su `/api/live/snapshot`.
   - Verifica della risposta 200 JSON con schema advisory.
3. **Simulazione Frontend**:
   - Verifica di render del widget nel tab Asta Live.
   - Test di attivazione/disattivazione polling.
4. **Verifica Deploy Vercel**:
   - Esecuzione `vercel --prod --yes` e test sul dominio [https://fanta-lab.vercel.app](https://fanta-lab.vercel.app).
   - Zero modifiche inviate a GitHub (`git status` locale).
