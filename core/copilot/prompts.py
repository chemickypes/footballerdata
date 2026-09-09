"""
footballerdata Copilot — System Prompt & User Prompt Builders.

Grounded quantitative player analysis with anti-hallucination guardrails.
Persona: "Analista" — player data & statistics explorer (Serie A).
"""

TABLE_HEADER = (
    "| Giocatore | Ruolo | Squadra | Contributo Atteso (pg×MV) | Prezzo Fair (1000) | VORP | Titolare 26/27 |"
)


def build_system_prompt(team_context: dict, budget_total: int = 1000, is_personal: bool = False) -> str:
    """
    Build a grounded system prompt for the player-stats copilot.

    team_context / budget_total are kept for signature compatibility but no longer
    inject league/auction state: fair prices are only used as quality scores,
    calibrated on a fixed reference league (budget_total credits, 10 teams).
    """
    personal_prompt = ""
    try:
        import os
        personal_prompt = os.environ.get("BOT_SYSTEM_PROMPT", "")
    except Exception:
        pass

    if is_personal and personal_prompt:
        intro = personal_prompt + "\n\n"
    elif is_personal:
        intro = "Sei un assistente analitico esperto e confidenziale per l'esplorazione di dati e statistiche dei calciatori di Serie A.\n\n"
    else:
        intro = (
            "Sei Analista, il consulente quantitativo per l'esplorazione di dati e statistiche "
            "dei calciatori di Serie A (footballerdata).\n\n"
        )

    return (
        intro +
        "REGOLE FERREE:\n"
        "1. NON inventare MAI statistiche. Usa SOLO i dati forniti nel contesto qui sotto.\n"
        "2. Metriche chiave come punteggi di qualità:\n"
        "   - Contributo Atteso P10/P50/P90: proiezioni quantili di punti-rating stagionali (pg×MV) "
        "da Gradient Boosting; lo spread P90-P10 misura l'incertezza/volatilità del profilo.\n"
        "   - VORP: valore sopra un giocatore di ricambio allo stesso ruolo. ATTENZIONE: è relativo "
        "al ruolo — non confrontare VORP tra ruoli diversi (es. portieri compressi vs attaccanti).\n"
        "   - Prezzo Fair: risalature del VORP su crediti (calibrato su " + str(budget_total) + " cr, 10 squadre). "
        "È un punteggio di qualità, non il prezzo reale di mercato.\n"
        "   - Titolarità 2026/27: minuti/starts da dati Sofascore delle prime giornate.\n"
        "3. Rispondi SEMPRE in italiano, in formato Markdown strutturato (elenchi puntati, grassetto per cifre e nomi).\n"
        "4. Per confronti: tabella comparativa + verdetto finale con motivazione numerica.\n"
        "5. Se i dati forniti non contengono la risposta, dillo chiaramente invece di speculare."
    )


def build_user_prompt(prompt: str, top_players: list) -> str:
    """Build user prompt with grounded player data context in clean readable table format."""
    lines = [TABLE_HEADER, "|---|---|---|---|---|---|---|"]
    for p in (top_players or [])[:35]:
        starter = "SI" if p.get("is_starter_2627") else "No"
        p50 = float(p.get("predicted_contrib_p50", 0))
        fair = int(p.get("prezzo_fair_1000", 1))
        vorp = float(p.get("vorp_points", 0))
        lines.append(f"| {p.get('player')} | {p.get('role')} | {p.get('team')} | {p50:.1f} | {fair} cr | +{vorp:.1f} | {starter} |")

    table_str = "\n".join(lines)

    return (
        f"DATI UFFICIALI CALCIATORI DAL MODELLO ML:\n"
        f"{table_str}\n\n"
        f"Domanda: {prompt}\n\n"
        f"ISTRUZIONI CHIAVE:\n"
        f"- Basa la tua risposta esclusivamente sui giocatori presenti nella tabella sopra.\n"
        f"- Se la domanda riguarda ruoli, squadre o profili low cost, evidenzia i giocatori rilevanti "
        f"ordinandoli per titolarità, Contributo Atteso e VORP.\n"
        f"- Ricorda il caveat VORP: confronti numerici solo tra giocatori dello stesso ruolo."
    )
