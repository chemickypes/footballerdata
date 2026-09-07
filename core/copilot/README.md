# core.copilot

## 1. Divulgativo
Questo è il cervello conversazionale del progetto: l’assistente tattico che prova a rispondere alle domande sull’asta senza obbligarti a usare API a pagamento. L’idea chiave è semplice: se c’è un provider AI disponibile lo usa, se non c’è cade in modo elegante su logiche quantitative locali. Così il copilot resta utile sia su laptop personale sia in ambienti più limitati.

## 2. Tecnico
`core/copilot/providers.py` implementa un’architettura provider-agnostic basata su un’interfaccia comune `CopilotProvider` con metodo:

```python
query(self, system_prompt: str, user_prompt: str, temperature: float = 0.35, max_tokens: int = 800) -> str | None
```

Provider presenti nel file:
- `OllamaProvider` — backend locale via endpoint OpenAI-compatible `/chat/completions`; usa `base_url.rstrip("/")` e in locale punta tipicamente a `http://localhost:11434` / `http://localhost:11434/v1`.
- `OpenAIProvider` — wrapper generico per API OpenAI-compatible cloud.
- `GeminiProvider` — backend REST nativo Google, attivato solo se `GEMINI_API_KEY` è presente.
- `GroqProvider` — specializzazione di `OpenAIProvider` per Groq Free Tier.
- `CascadeProvider` — failover chain che prova più provider in ordine fino al primo reply valido.

La factory `get_copilot_provider()` costruisce la cascata runtime. Nel codice corrente l’ordine effettivo è: Groq se configurato, poi Gemini, poi OpenAI-compatible remoto, poi Ollama locale; se nessuno è disponibile ritorna `None` e `web/app.py` usa il fallback quantitativo offline. In termini architetturali il comportamento richiesto dal modulo resta: provider interface comune, backend locale come default naturale su macchina personale, Gemini opzionale via env var, e fallback euristico/matematico quando non c’è alcun LLM operativo.

`get_copilot_diagnostics()` espone stato dei provider e motore attivo, utile per la UI del Command Center.

## 3. Screenshot
![AI Tactical Copilot](../../docs/assets/ai_tactical_copilot.png)

## 4. Dipendenze
- Dipende da `requests`, variabili ambiente (`GROQ_API_KEY`, `GEMINI_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`) e opzionalmente `.env` locale.
- Viene consumato da `web/app.py` tramite `get_copilot_diagnostics()`, `test_all_providers()` e la logica di risposta del copilot.
- Non dipende da `modules/`; usa solo prompt e contesto testuale forniti dal layer web.
