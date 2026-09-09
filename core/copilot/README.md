# core.copilot

## 1. Divulgativo
Questo è il cervello conversazionale del progetto: l'assistente "Analista" che risponde alle domande su dati e statistiche dei calciatori senza obbligarti a usare API a pagamento. L'idea chiave è semplice: se c'è un provider AI disponibile lo usa, se non c'è cade in modo elegante su logiche quantitative locali. Così il copilot resta utile sia su laptop personale sia in ambienti più limitati. Il backend locale (Ollama) è il motore primario su macchina personale.

## 2. Tecnico
`core/copilot/providers.py` implementa un'architettura provider-agnostic basata su un'interfaccia comune `CopilotProvider` con metodo:

```python
query(self, system_prompt: str, user_prompt: str, temperature: float = 0.35, max_tokens: int = 800) -> str | None
```

Provider presenti nel file:
- `OllamaProvider` — backend locale via endpoint **nativo `/api/chat`** (non `/v1`: l'endpoint OpenAI-compatible ignora `think: false` sulle build Ollama attuali). Normalizza `LLM_BASE_URL` togliendo l'eventuale suffisso `/v1`. Il read-timeout è configurabile con `LLM_TIMEOUT` (default **300s**): le risposte non-streaming arrivano solo a fine generazione e su CPU-only il tempo di generazione è di decine di secondi — un timeout troppo corto ucciderebbe ogni richiesta reale. Supporta `LLM_REASONING_EFFORT` (`off` default disattiva il thinking di gemma4:e4b, `low/medium/high` lo limita) e `LLM_NUM_CTX` (override della finestra di contesto).
- `OpenAIProvider` — wrapper generico per API OpenAI-compatible (cloud o remote autenticate).
- `GeminiProvider` — backend REST nativo Google, attivato solo se `GEMINI_API_KEY` è presente.
- `GroqProvider` — specializzazione di `OpenAIProvider` per Groq Free Tier.
- `CascadeProvider` — failover chain che prova più provider in ordine fino al primo reply valido.

La factory `get_copilot_provider()` costruisce la cascata runtime. Ordine effettivo: **endpoint locale** (`LLM_BASE_URL`, senza `LLM_API_KEY` → Ollama), poi Groq, poi Gemini, poi OpenAI-compatible cloud; se nessuno è disponibile ritorna `None` e `web/ai_api.py` usa il fallback quantitativo offline. Su Vercel gli endpoint localhost vengono ignorati.

Modello locale di default: **`gemma4:e4b`** (override con `LLM_MODEL`).

### Setup Ollama locale
```bash
ollama pull gemma4:e4b
# .env
LLM_BASE_URL=http://localhost:11434        # indirizzo e porta del tuo Ollama
LLM_MODEL=gemma4:e4b
LLM_TIMEOUT=300                             # opzionale, secondi di read-timeout
LLM_REASONING_EFFORT=off                    # opzionale, evita il thinking che tronca le risposte
```
(Il suffisso `/v1` finale, se presente, viene tolto automaticamente.)

Variante opzionale con persona già incapsulata nel modello:
```bash
ollama create analista -f core/copilot/Modelfile
# poi nel .env: LLM_MODEL=analista
```
Nota: quando si usa il modello base (senza `ollama create`) la persona arriva comunque dal system prompt costruito a runtime da `core/copilot/prompts.py`.

`get_copilot_diagnostics()` espone stato dei provider e motore attivo; `test_all_providers()` fa un ping HTTP reale a ogni backend configurato (incluso Ollama), utile per verificare l'integrazione da `/api/ai_test`.

## 3. Screenshot
![AI Tactical Copilot](../../docs/assets/ai_tactical_copilot.png)

## 4. Dipendenze
- Dipende da `requests`, variabili ambiente (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT`, `GROQ_API_KEY`, `GEMINI_API_KEY`) e opzionalmente `.env` locale.
- Viene consumato da `web/ai_api.py` tramite `get_copilot_diagnostics()`, `test_all_providers()` e la logica di risposta del copilot.
- Non dipende da `modules/`; usa solo prompt e contesto testuale forniti dal layer web.
