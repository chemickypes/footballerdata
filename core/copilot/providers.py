"""
footballerdata Copilot — LLM Provider Implementations.

Provider priority (first available wins):
1. Local endpoint   — LLM_BASE_URL set: OllamaProvider (no key, native /api/chat)
                      or OpenAIProvider (key, /v1 chat completions)
2. GroqProvider     — GROQ_API_KEY set
3. GeminiProvider   — GEMINI_API_KEY set
4. OpenAIProvider   — LLM_API_KEY set without LLM_BASE_URL (cloud endpoint)
5. None             — Falls back to HeuristicProvider in app.py

Local models default to gemma4:e4b via LLM_MODEL. Env knobs:
- LLM_TIMEOUT (seconds): per-request read timeout — generous on CPU-only inference
- LLM_REASONING_EFFORT: off (default) disables thinking, low/medium/high caps it
- LLM_NUM_CTX: optional context-window override
"""

import os
import json
import requests

# Try loading .env if present locally
if os.path.exists(".env"):
    try:
        with open(".env", "r") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip()
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass


class CopilotProvider:
    """Base interface for LLM providers."""
    engine_name: str = "unknown"

    def query(self, system_prompt: str, user_prompt: str, temperature: float = 0.35, max_tokens: int = 800) -> str | None:
        raise NotImplementedError


class OllamaProvider(CopilotProvider):
    """Local Ollama via native /api/chat endpoint (full control over `think`)."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, timeout: float | None = None):
        base = base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self.base_url = base
        self.model = model
        self.api_key = api_key
        # Non-streaming replies arrive only at the end of generation: on CPU
        # inference a full answer can take minutes of socket silence.
        self.timeout = timeout or float(os.environ.get("LLM_TIMEOUT", "300"))
        self.engine_name = f"ollama/{model}"

    def query(self, system_prompt: str, user_prompt: str, temperature: float = 0.35, max_tokens: int = 650) -> str | None:
        endpoint = f"{self.base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }
        num_ctx = os.environ.get("LLM_NUM_CTX")
        if num_ctx and num_ctx.isdigit():
            payload["options"]["num_ctx"] = int(num_ctx)

        # Reasoning models (e.g. gemma4:e4b) emit a hidden thinking trace that eats
        # into the token budget and truncates the visible answer. The copilot's RAG
        # prompt already supplies every number, so thinking is pure CPU waste.
        # NOTE: the OpenAI-compatible /v1 endpoint IGNORES think:false on current
        # Ollama builds — only the native /api/chat honors it. LLM_REASONING_EFFORT:
        #   off (default) -> think:false | low/minimal/medium/high -> cap effort
        #   default -> model default behavior
        effort = (os.environ.get("LLM_REASONING_EFFORT") or "off").strip().lower()
        if effort == "off":
            payload["think"] = False
        elif effort in ("minimal", "low", "medium", "high"):
            payload["think"] = True
            payload["reasoning_effort"] = effort

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        msg = resp.json().get("message", {})
        content = (msg.get("content") or "").strip()
        if not content:
            return None
        return content


class OpenAIProvider(CopilotProvider):
    """Any OpenAI-compatible cloud API (OpenAI, DeepSeek, Groq, vLLM, etc.)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.engine_name = model

    def query(self, system_prompt: str, user_prompt: str, temperature: float = 0.35, max_tokens: int = 650) -> str | None:
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return None


class GeminiProvider(CopilotProvider):
    """Google Gemini native REST API with verified active models."""
    CANDIDATE_MODELS = [
        "gemini-3.6-flash",
        "gemini-flash-latest",
        "gemini-2.5-pro"
    ]

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or os.environ.get("GEMINI_MODEL") or "gemini-3.6-flash"
        self.engine_name = f"Gemini ({self.model})"

    def query(self, system_prompt: str, user_prompt: str, temperature: float = 0.35, max_tokens: int = 2048) -> str | None:
        models_to_try = [self.model] + [m for m in self.CANDIDATE_MODELS if m != self.model]

        for candidate in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [{"text": f"System Context:\n{system_prompt}\n\n{user_prompt}"}]
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }
            try:
                resp = requests.post(url, json=payload, timeout=4)
                if resp.status_code == 200:
                    self.engine_name = f"Gemini ({candidate})"
                    return (resp.json()
                            .get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "").strip())
            except Exception:
                continue
        return None


class GroqProvider(OpenAIProvider):
    """Zero-cost cloud LLM inference via Groq Free Tier with verified active models."""
    CANDIDATE_MODELS = [
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "qwen/qwen3.8-27b"
    ]

    def __init__(self, api_key: str, model: str | None = None):
        target_model = model or os.environ.get("GROQ_MODEL") or "openai/gpt-oss-120b"
        super().__init__(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
            model=target_model
        )
        self.engine_name = f"Groq ({target_model})"

    def query(self, system_prompt: str, user_prompt: str, temperature: float = 0.35, max_tokens: int = 650) -> str | None:
        models_to_try = [self.model] + [m for m in self.CANDIDATE_MODELS if m != self.model]
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        for candidate in models_to_try:
            payload = {
                "model": candidate,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            try:
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                if resp.status_code == 200:
                    self.engine_name = f"Groq ({candidate})"
                    return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            except Exception:
                continue
        return None


class CascadeProvider(CopilotProvider):
    """Chains multiple LLM providers. Falls through on 429 rate limit or connection errors."""
    def __init__(self, providers: list[CopilotProvider]):
        self.providers = providers
        self.engine_name = "Cascade (" + " → ".join(p.engine_name for p in providers) + ")"
        self.last_successful_engine = None

    def query(self, system_prompt: str, user_prompt: str, temperature: float = 0.35, max_tokens: int = 650) -> str | None:
        for p in self.providers:
            try:
                reply = p.query(system_prompt, user_prompt, temperature, max_tokens)
                if reply:
                    self.last_successful_engine = p.engine_name
                    return reply
            except Exception:
                continue
        return None


def get_copilot_provider() -> CopilotProvider | None:
    """
    Factory: returns a cascading failover chain based on available free tiers and env vars.
    Cascade Order (local machine first):
      1. Local endpoint (if LLM_BASE_URL present and not on Vercel):
         Ollama when no LLM_API_KEY, authenticated OpenAI-compatible otherwise
      2. Groq Free Tier (if GROQ_API_KEY present)
      3. Gemini Free Tier (if GEMINI_API_KEY present)
      4. Cloud OpenAI-compatible (if LLM_API_KEY set without LLM_BASE_URL)
      5. None -> Fallback to Local Quantitative Reasoner in app.py (0$ Cost)
    """
    is_vercel = bool(os.environ.get("VERCEL"))
    available_providers: list[CopilotProvider] = []

    llm_api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    llm_base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    llm_model = os.environ.get("LLM_MODEL", "gemma4:e4b")
    groq_key = os.environ.get("GROQ_API_KEY")

    if is_vercel and llm_base_url and ("localhost" in llm_base_url or "127.0.0.1" in llm_base_url):
        llm_base_url = None

    # 1. Local / custom endpoint — primary engine on personal machines
    if llm_base_url and not is_vercel:
        if llm_api_key and llm_api_key != groq_key:
            available_providers.append(OpenAIProvider(base_url=llm_base_url, api_key=llm_api_key, model=llm_model))
        else:
            available_providers.append(OllamaProvider(base_url=llm_base_url, model=llm_model))

    # 2. Groq Free Tier (Ultra-fast, 0 token cost, no credit card required)
    if groq_key:
        available_providers.append(GroqProvider(api_key=groq_key, model=os.environ.get("GROQ_MODEL") or "openai/gpt-oss-120b"))

    # 3. Google Gemini Free Tier
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        available_providers.append(GeminiProvider(api_key=gemini_key, model=os.environ.get("GEMINI_MODEL") or "gemini-3.6-flash"))

    # 4. Cloud OpenAI-compatible (explicit key, no endpoint configured)
    if llm_api_key and llm_api_key != groq_key and not llm_base_url:
        available_providers.append(OpenAIProvider(base_url="https://api.openai.com/v1", api_key=llm_api_key, model=llm_model))

    if not available_providers:
        # None -> app.py activates the zero-cost local quantitative engine
        return None

    if len(available_providers) == 1:
        return available_providers[0]

    return CascadeProvider(available_providers)


def get_copilot_diagnostics() -> dict:
    """Returns diagnostic status of all configured AI engines."""
    is_vercel = bool(os.environ.get("VERCEL"))
    groq_key = bool(os.environ.get("GROQ_API_KEY"))
    gemini_key = bool(os.environ.get("GEMINI_API_KEY"))
    openai_key = bool(os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    ollama_url = os.environ.get("LLM_BASE_URL")

    provider = get_copilot_provider()
    active_engine = provider.engine_name if provider else "Fallback Matematico Offline (Nessun LLM attivo)"

    return {
        "is_vercel": is_vercel,
        "active_engine": active_engine,
        "has_llm": provider is not None,
        "providers": {
            "groq": {
                "configured": groq_key,
                "name": "Groq Cloud (Llama 3.3 / Llama 3.1)",
                "env_var": "GROQ_API_KEY",
                "status": "Attivo" if groq_key else "Non configurato (aggiungi GROQ_API_KEY)"
            },
            "gemini": {
                "configured": gemini_key,
                "name": "Google Gemini Free Tier",
                "env_var": "GEMINI_API_KEY",
                "status": "Attivo" if gemini_key else "Non configurato (aggiungi GEMINI_API_KEY)"
            },
            "openai_compat": {
                "configured": openai_key,
                "name": "OpenAI / Custom API",
                "env_var": "LLM_API_KEY",
                "status": "Attivo" if openai_key else "Non configurato"
            },
            "ollama": {
                "configured": bool(ollama_url and not is_vercel),
                "name": "Ollama Locale (gemma4:e4b default)",
                "env_var": "LLM_BASE_URL",
                "status": "Non supportato su Vercel (solo localhost)" if is_vercel else ("Attivo" if ollama_url else "Disattivato")
            }
        }
    }


def test_all_providers() -> dict:
    """Test ping on each configured provider and return diagnostics with exact HTTP response."""
    results = {}
    
    # 1. Test Groq
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                timeout=5
            )
            results["groq"] = {"ok": resp.status_code == 200, "status_code": resp.status_code, "msg": f"{resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            results["groq"] = {"ok": False, "status_code": None, "msg": f"Eccezione: {str(e)}"}
    else:
        results["groq"] = {"ok": False, "status_code": None, "msg": "GROQ_API_KEY non presente"}

    # 2. Test Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={gemini_key}"
            resp = requests.post(
                url,
                json={"contents": [{"role": "user", "parts": [{"text": "ping"}]}]},
                timeout=5
            )
            results["gemini"] = {"ok": resp.status_code == 200, "status_code": resp.status_code, "msg": f"{resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            results["gemini"] = {"ok": False, "status_code": None, "msg": f"Eccezione: {str(e)}"}
    else:
        results["gemini"] = {"ok": False, "status_code": None, "msg": "GEMINI_API_KEY non presente"}

    # 3. Test Ollama locale (ping minimo; il cold-start del modello su CPU puo' richiedere tempo)
    ollama_url = os.environ.get("LLM_BASE_URL")
    ollama_model = os.environ.get("LLM_MODEL", "gemma4:e4b")
    if ollama_url:
        try:
            base = ollama_url.rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3]
            resp = requests.post(
                f"{base}/api/chat",
                json={"model": ollama_model, "messages": [{"role": "user", "content": "ping"}], "stream": False, "think": False, "options": {"num_predict": 5}},
                headers={"Content-Type": "application/json"},
                timeout=120
            )
            ok = resp.status_code == 200 and bool((resp.json().get("message", {}).get("content") or "").strip())
            results["ollama"] = {"ok": ok, "status_code": resp.status_code, "msg": f"{resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            results["ollama"] = {"ok": False, "status_code": None, "msg": f"Eccezione: {str(e)}"}
    else:
        results["ollama"] = {"ok": False, "status_code": None, "msg": "LLM_BASE_URL non presente"}

    return results
