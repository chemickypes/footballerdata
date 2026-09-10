"""
footballerdata — structured retrieval layer (RAG senza embeddings).

Dominio chiuso (533 giocatori, ~380 fixture): la risoluzione di entità è
deterministica (alias + token matching accent-insensitive per i giocatori,
keyword → sigla squadra per le partite), quindi niente vettori/embedding.

Fornisce al copilot i blocchi di contesto recuperati dai data artifact:
  - profilo giocatore (dataset + stage 12 per-partita + stage 14 advanced)
  - partita (stage 11 fixture + eventi ESPN cache + forma squadre + MOTM)
  - aggregati (marcatori da stage 12, cartellini da colonne ESPN del dataset)

Tutte le funzioni accettano i dati come parametro opzionale (per test ermetici);
se assenti vengono caricati pigramente dagli artifact condivisi con le API web
(web.matches_api), così copilot e UI leggono sempre gli stessi numeri.
"""

import os
import re
import unicodedata

from web.config import PROJECT_ROOT
from web.data import load_dataset

try:
    from core import config as _core_config
except Exception:  # pragma: no cover
    _core_config = None

TEAM_KEYWORD_MAP = getattr(_core_config, "TEAM_KEYWORD_MAP", {})
PLAYER_NAME_ALIASES = getattr(_core_config, "PLAYER_NAME_ALIASES", {})

MATCH_RESULTS_CSV = os.path.join(PROJECT_ROOT, "data", "match_results.csv")
PLAYER_MATCH_STATS_CSV = os.path.join(PROJECT_ROOT, "data", "player_match_stats.csv")
PLAYER_ADVANCED_JSON = os.path.join(PROJECT_ROOT, "data", "player_advanced.json")
ESPN_EVENTS_JSON = os.environ.get(
    "ESPN_EVENTS_JSON", os.path.join(PROJECT_ROOT, "data", "espn_match_events.json")
)

MAX_PLAYER_BLOCKS = 3
MAX_MATCH_BLOCKS = 2
MATCH_TABLE_LIMIT = 5

RESULT_IT = {"W": "V", "D": "N", "L": "S"}

# Parole chiave aggregati (lowercase, accent-stripped)
_SCORER_KW = re.compile(r"\b(marcatori\w*|capocannoniere\w*|classifica marcatori)\b")
_RED_KW = re.compile(r"\b(espuls\w*|cartellini rossi|rossi)\b")
_YELLOW_KW = re.compile(r"\b(ammonit\w*|cartellini gialli|gialli)\b")

_aggregate_cache = {"mtime": None, "scorers": None}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize_text(value) -> str:
    """Lowercase, accent-stripped, spazi collassati."""
    s = unicodedata.normalize("NFD", str(value or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def _fnum(v, nd=2):
    try:
        if v is None or str(v).strip() in ("", "None", "nan"):
            return None
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, nd)


def _fmt_num(v, nd=2, suffix=""):
    f = _fnum(v, nd)
    return "—" if f is None else f"{f:.{nd}f}{suffix}"


def _int_or_none(v):
    try:
        if v is None or str(v).strip() in ("", "None", "nan"):
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _fmt_date(iso):
    if not iso:
        return "—"
    return str(iso)[:10]


# ─────────────────────────────────────────────────────────────────────────────
# Lazy loaders (condivisi con web.matches_api: stessa fonte, stessa cache)
# ─────────────────────────────────────────────────────────────────────────────

def _auto_matches_payload():
    try:
        from web import matches_api
        return matches_api._load_payload()
    except Exception:
        return None


def _auto_pm_df():
    try:
        from web import matches_api
        return matches_api._load_pm_stats()
    except Exception:
        return None


def _auto_advanced():
    try:
        from web import matches_api
        return matches_api._load_advanced()
    except Exception:
        return None


def _auto_espn_store():
    try:
        from web import matches_api
        return matches_api._espn_store_cached()
    except Exception:
        return {}


def _load_scorer_index():
    """Indice marcatori da player_match_stats.csv: [(player, team, goals)].
    Cache invalidata sul mtime del CSV. None se il file manca."""
    if not os.path.exists(PLAYER_MATCH_STATS_CSV):
        return None
    mtime = os.path.getmtime(PLAYER_MATCH_STATS_CSV)
    if _aggregate_cache["scorers"] is not None and _aggregate_cache["mtime"] == mtime:
        return _aggregate_cache["scorers"]
    try:
        import pandas as pd
        df = pd.read_csv(PLAYER_MATCH_STATS_CSV)
        df = df[df["player"].notna()]
        grp = df.groupby("player").agg(
            goals=("goals", "sum"),
            team=("team_code", "first"),
            minutes=("minutes_played", "sum"),
        )
        grp = grp[grp["goals"] > 0].sort_values("goals", ascending=False)
        idx = [(p, str(r.get("team")), int(r["goals"])) for p, r in grp.iterrows()]
    except Exception:
        return None
    _aggregate_cache["mtime"] = mtime
    _aggregate_cache["scorers"] = idx
    return idx


# ─────────────────────────────────────────────────────────────────────────────
# Entity resolution — giocatori
# ─────────────────────────────────────────────────────────────────────────────

def resolve_players(prompt, df=None):
    """Nomi dataset (formato 'Cognome X.') menzionati nel prompt, best-first.

    Matching: containment nome completo (sul prompt espanso con gli alias) →
    token matching word-boundary accent-insensitive (sul prompt ORIGINALE,
    così l'alias 'lautaro' → 'martinez l.' non trascina dentro anche
    'Martinez Jo.').
    """
    if df is None or getattr(df, "empty", True):
        df = load_dataset()
    q_orig = normalize_text(prompt)
    if not q_orig:
        return []

    q_expanded = q_orig
    for alias, target in PLAYER_NAME_ALIASES.items():
        a = normalize_text(alias)
        if a and re.search(rf"\b{re.escape(a)}\b", q_orig) and normalize_text(target) not in q_expanded:
            q_expanded += " " + normalize_text(target)

    hits = []  # (name, matched_token_count, df_order)
    for order, raw in enumerate(df["player"].astype(str)):
        norm = normalize_text(raw)
        if not norm:
            continue
        toks = [t for t in re.split(r"[\s\.\-']+", norm) if len(t) >= 3]
        if not toks:
            continue
        if norm in q_expanded:
            # containment del nome completo: più lungo = più specifico
            hits.append((raw, 100 + len(norm), order))
            continue
        matched = [t for t in toks if re.search(rf"\b{re.escape(t)}\b", q_orig)]
        if matched:
            hits.append((raw, len(matched), order))

    hits.sort(key=lambda h: (-h[1], h[2]))
    return [h[0] for h in hits]


# ─────────────────────────────────────────────────────────────────────────────
# Entity resolution — partite
# ─────────────────────────────────────────────────────────────────────────────

def resolve_matches(prompt, matches_payload=None):
    """Fixture metas (payload /api/matches) citate nel prompt, best-first.

    Codici squadra in ordine di apparizione:
      ≥ 2 → head-to-head (ultime 2); 1 → ultima finita (o giornata richiesta,
            o prossima con keyword 'prossim'); 0 → giornata N se richiesta.
    """
    payload = matches_payload if matches_payload is not None else _auto_matches_payload()
    if not payload or not payload.get("available"):
        return []
    metas = [m for rnd in payload.get("rounds", []) for m in rnd.get("matches", [])]
    if not metas:
        return []
    metas.sort(key=lambda m: (m.get("round") or 0, m.get("date") or ""))

    q = normalize_text(prompt)

    round_no = None
    m = re.search(r"\bgiornata\s*(\d{1,2})\b", q)
    if m:
        round_no = int(m.group(1))
    elif re.search(r"\b(ultima|scorsa)\s+giornata\b", q):
        round_no = payload.get("current_round")

    codes = []
    for kw in sorted(TEAM_KEYWORD_MAP, key=len, reverse=True):
        code = TEAM_KEYWORD_MAP[kw]
        if code in codes:
            continue
        if re.search(rf"\b{re.escape(normalize_text(kw))}\b", q):
            codes.append(code)

    if len(codes) >= 2:
        picked = [m for m in metas
                  if {m.get("home_code"), m.get("away_code")} >= set(codes[:2])]
        if round_no:
            picked = [m for m in picked if m.get("round") == round_no]
        elif not re.search(r"\bprossim", q):
            # h2h: preferisci le gare già disputate (gol/cartellini/voti)
            finished = [m for m in picked if m.get("finished")]
            if finished:
                picked = finished
        return list(reversed(picked[-2:]))

    if len(codes) == 1:
        code = codes[0]
        team_fix = [m for m in metas if code in (m.get("home_code"), m.get("away_code"))]
        if round_no:
            return [m for m in team_fix if m.get("round") == round_no]
        if re.search(r"\bprossim", q):
            upcoming = [m for m in team_fix if not m.get("finished")]
            return upcoming[:1]
        finished = [m for m in team_fix if m.get("finished")]
        return list(reversed(finished[-1:]))

    if round_no:
        return [m for m in metas if m.get("round") == round_no]
    return []


def detect_aggregate(prompt):
    """'scorers' | 'red' | 'yellow' | None in base alle keyword del prompt."""
    q = normalize_text(prompt)
    if _SCORER_KW.search(q):
        return "scorers"
    if _RED_KW.search(q):
        return "red"
    if _YELLOW_KW.search(q):
        return "yellow"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Context blocks
# ─────────────────────────────────────────────────────────────────────────────

def _known_names(name, pm_df):
    """Nomi alternativi con cui l'utente può chiamare il giocatore (nome
    completo Sofascore + alias config) — servono all'LLM per collegare
    'Lautaro' al dataset name 'Martinez L.'."""
    known = []
    rev = {}
    for alias, target in PLAYER_NAME_ALIASES.items():
        rev.setdefault(normalize_text(target), []).append(str(alias).title())
    for k in rev.get(normalize_text(name), []):
        if k not in known:
            known.append(k)
    if pm_df is not None and not pm_df.empty:
        rows = pm_df[(pm_df["player"] == name) & pm_df["player_sofascore"].notna()]
        if not rows.empty:
            full = str(rows["player_sofascore"].iloc[0]).strip()
            if full and full.lower() != name.lower() and full not in known:
                known.insert(0, full)
    return known


def build_player_block(name, df=None, pm_df=None, advanced=None):
    """Blocco markdown profilo giocatore, o None se assente dal dataset."""
    if df is None or getattr(df, "empty", True):
        df = load_dataset()
    rows = df[df["player"] == name]
    if rows.empty:
        return None
    r = rows.iloc[0]

    if pm_df is None:
        pm_df = _auto_pm_df()
    known = _known_names(name, pm_df)
    who = f"{name} — {' / '.join(known)}" if known else name
    lines = [f"### GIOCATORE: {who} ({r.get('team')} · {r.get('role')} · {_fmt_num(r.get('age'), 0)} anni)"]
    lines.append(
        f"- Proiezione contributo (pg×MV): P50 {_fmt_num(r.get('predicted_contrib_p50'), 0)} "
        f"[P10 {_fmt_num(r.get('predicted_contrib_p10'), 0)} / P90 {_fmt_num(r.get('predicted_contrib_p90'), 0)}], "
        f"spread {_fmt_num(r.get('contrib_volatility_spread'), 0)}"
    )
    fair = _int_or_none(r.get("prezzo_fair_1000"))
    vorp = _fnum(r.get("vorp_points"), 1)
    surplus = _int_or_none(r.get("surplus_value_cr"))
    lines.append(
        f"- Qualità: prezzo fair {fair if fair is not None else '—'} cr · "
        f"VORP {'+' if (vorp or 0) >= 0 else ''}{vorp if vorp is not None else '—'} · "
        f"surplus {'+' if (surplus or 0) >= 0 else ''}{surplus if surplus is not None else '—'} cr"
    )
    lines.append(
        f"- 2026/27: {_int_or_none(r.get('starts_2627')) or 0} titolarità, "
        f"{_int_or_none(r.get('minutes_2627')) or 0} minuti "
        f"({'titolare' if r.get('is_starter_2627') else 'rotazione'})"
    )
    xg90, xa90 = _fnum(r.get("xg_per90"), 3), _fnum(r.get("xa_per90"), 3)
    if xg90 is not None:
        lines.append(
            f"- Sottoporta (Understat 3y): xG/90 {xg90:.3f} · xA/90 "
            f"{(_fnum(r.get('xa_per90'), 3) or 0):.3f} · tiri/90 {_fmt_num(r.get('shots_per90'))}"
        )
    inj_days = _int_or_none(r.get("giorni_infortunio_3y"))
    if inj_days is not None:
        grave = ", trauma grave" if r.get("infortunio_grave") else ""
        lines.append(
            f"- Infortuni 3y: {inj_days} giorni persi in "
            f"{_int_or_none(r.get('n_infortuni_3y')) or 0} episodi{grave}"
        )
    yel, red = _int_or_none(r.get("yellow_cards_espn")) or 0, _int_or_none(r.get("red_cards_espn")) or 0
    lines.append(f"- Cartellini ESPN 2026/27: {yel} gialli, {red} rossi (0 = nessun dato raccolto)")
    mv = _fnum(r.get("market_value_eur"), 0)
    if mv:
        lines.append(f"- Valore mercato TM: {int(mv):,} €".replace(",", "."))
    foot = r.get("foot")
    if foot and str(foot).strip() not in ("", "nan", "None"):
        lines.append(f"- Piede: {foot}")

    # Stage 14: statistiche avanzate stagione corrente
    advanced = advanced if advanced is not None else _auto_advanced()
    adv = (advanced or {}).get("players", {}).get(name)
    if adv and not adv.get("no_data") and adv.get("minutes"):
        cards = adv.get("cards") or {}
        totals = adv.get("totals") or {}
        lines.append(
            f"- Stagione avanzate (Sofascore): rating {_fmt_num(adv.get('rating'))} · "
            f"gol {_fmt_num(totals.get('goals'), 0)} · assist {_fmt_num(totals.get('assists'), 0)} · "
            f"gialli {int(cards.get('yellow') or 0)} · rossi "
            f"{int(cards.get('red') or 0) + int(cards.get('yellow_red') or 0) + int(cards.get('direct_red') or 0)} · "
            f"tiri/90 {_fmt_num((adv.get('per90') or {}).get('shots_per90'))}"
        )

    # Stage 12: riepilogo + ultime gare per-partita
    if pm_df is not None and not pm_df.empty:
        all_rows = pm_df[pm_df["player"] == name]
        if not all_rows.empty:
            with_rating = all_rows[all_rows["rating"].notna()]
            summary = (
                f"- Stagione 2026/27 (totale per-partita): {len(all_rows)} presenze, "
                f"{int(all_rows['goals'].sum())} gol, {int(all_rows['assists'].sum())} assist, "
                f"xG totale {_fmt_num(all_rows['xg'].sum())} · xA totale {_fmt_num(all_rows['xa'].sum())}"
            )
            if len(with_rating):
                summary += f", media voto {_fmt_num(with_rating['rating'].mean())}"
            lines.append(summary)

            recent = all_rows.sort_values(["round", "date_utc"], ascending=False).head(MATCH_TABLE_LIMIT)
            lines.append("- Ultime gare (G | Avv | Min | Voto | G+A | xG+xA):")
            for _, mr in recent.iterrows():
                opp = mr.get("opponent_code")
                venue = "vs" if str(mr.get("venue")) == "home" else "@"
                ga = (int(mr.get("goals") or 0)) + (int(mr.get("assists") or 0))
                xga = (_fnum(mr.get("xg"), 2) or 0) + (_fnum(mr.get("xa"), 2) or 0)
                rating = _fnum(mr.get("rating"), 1)
                lines.append(
                    f"  - G{int(mr['round']) if mr.get('round') == mr.get('round') else '?'} {venue}{opp or '?'} | "
                    f"{_int_or_none(mr.get('minutes_played')) or 0}' | "
                    f"{rating if rating is not None else '—'} | {ga} | {xga:.2f}"
                )

    return "\n".join(lines)


def build_match_block(meta, team_form=None, pm_df=None, espn_store=None):
    """Blocco markdown partita: fixture stage 11 + eventi ESPN + forma + MOTM."""
    home = meta.get("home_display") or meta.get("home_team") or "?"
    away = meta.get("away_display") or meta.get("away_team") or "?"
    hs, as_ = meta.get("home_score"), meta.get("away_score")
    played = meta.get("finished")

    score = f"{int(hs)}-{int(as_)}" if hs is not None and as_ is not None else "—"
    state = "finale" if played else "in programma"
    lines = [
        f"### PARTITA: {home} {score} {away} — Giornata {meta.get('round') or '?'} "
        f"({_fmt_date(meta.get('date'))}, {state})"
    ]
    ht_h, ht_a = meta.get("ht_home_score"), meta.get("ht_away_score")
    if played and ht_h is not None and ht_a is not None:
        lines.append(f"- Primo tempo: {int(ht_h)}-{int(ht_a)}")

    fid = str(meta.get("fixture_id"))
    espn_store = espn_store if espn_store is not None else _auto_espn_store()
    entry = (espn_store or {}).get(fid)
    side_codes = {"home": (meta.get("home_code") or "home").upper(),
                  "away": (meta.get("away_code") or "away").upper()}

    if entry:
        goals, yellows, reds = [], [], []
        for ev in entry.get("events") or []:
            minute = ev.get("minute")
            tag = f"{minute}'" if minute is not None else ""
            side = side_codes.get(str(ev.get("side") or "").lower(), "?")
            who = ev.get("player") or "?"
            kind = ev.get("kind")
            if kind in ("goal", "penalty", "own"):
                extra = ""
                if kind == "penalty":
                    extra = ", rigore"
                elif kind == "own":
                    extra = ", autogol"
                assist = ev.get("assist")
                if assist:
                    extra += f", ass. {assist}"
                goals.append(f"{tag} {who} ({side}{extra})")
            elif kind == "yellow":
                yellows.append(f"{tag} {who} ({side})")
            elif kind == "red":
                reds.append(f"{tag} {who} ({side})")
        if goals:
            lines.append("- Gol (ESPN): " + " · ".join(goals))
        if yellows:
            lines.append("- Ammoniti: " + " · ".join(yellows))
        if reds:
            lines.append("- Espulsi: " + " · ".join(reds))
        form = entry.get("form") or {}
        if form.get("home") or form.get("away"):
            lines.append(f"- Moduli: {home} {form.get('home') or '?'} vs {away} {form.get('away') or '?'}")
    else:
        lines.append("- Eventi dettagliati (gol/cartellini) non disponibili in cache locale "
                     "(si popolano aprendo la pagina partita con il feed ESPN).")

    # Fallback marcatori + MOTM dal per-partita (stage 12)
    if pm_df is None:
        pm_df = _auto_pm_df()
    if pm_df is not None and not pm_df.empty:
        ev_rows = pm_df[pm_df["event_id"] == meta.get("fixture_id")]
        if not ev_rows.empty:
            if not entry:
                scorers = {}
                for _, mr in ev_rows.iterrows():
                    g = int(mr.get("goals") or 0)
                    if g > 0 and mr.get("player") is not None:
                        p = str(mr["player"])
                        scorers[p] = scorers.get(p, 0) + g
                if scorers:
                    lines.append("- Marcatori (stage 12): " +
                                 " · ".join(f"{p} x{g}" for p, g in sorted(scorers.items(), key=lambda kv: -kv[1])))
            rated = ev_rows[ev_rows["rating"].notna()]
            if not rated.empty:
                best = rated.loc[rated["rating"].idxmax()]
                lines.append(
                    f"- Miglior voto: {best['player']} "
                    f"({best.get('team_code')}) {_fmt_num(best['rating'])}"
                )

    team_form = team_form if team_form is not None else (_auto_matches_payload() or {}).get("team_form") or {}
    hc, ac = meta.get("home_code"), meta.get("away_code")
    for code in (hc, ac):
        tf = (team_form or {}).get(code)
        if tf:
            results = " ".join(RESULT_IT.get(mm.get("result"), "?")
                               for mm in (tf.get("matches") or [])[-5:])
            lines.append(f"- Forma {code} (ultime 5): {results}")

    return "\n".join(lines)


def build_aggregate_block(prompt, df=None, pm_df=None):
    """Blocco markdown per classifiche (marcatori, cartellini). None se niente."""
    kind = detect_aggregate(prompt)
    if kind is None:
        return None

    if kind == "scorers":
        idx = _load_scorer_index() if pm_df is None else None
        if idx is None:
            if pm_df is None or pm_df.empty:
                return "### MARCATORI\n- Dati per-partita non disponibili (esegui lo stage 12)."
            sub = pm_df[pm_df["player"].notna()]
            grp = sub.groupby("player").agg(g=("goals", "sum"), team=("team_code", "first"))
            grp = grp[grp["g"] > 0].sort_values("g", ascending=False)
            idx = [(p, str(r.get("team")), int(r["g"])) for p, r in grp.iterrows()]
        lines = ["### MARCATORI 2026/27 (stage 12)"]
        for p, team, g in idx[:10]:
            lines.append(f"- {p} ({team}): {g} gol")
        return "\n".join(lines)

    if df is None or getattr(df, "empty", True):
        df = load_dataset()
    col = "red_cards_espn" if kind == "red" else "yellow_cards_espn"
    label = "ESPULSI" if kind == "red" else "AMMONITI"
    sub = df[df[col].fillna(0) > 0].sort_values(col, ascending=False).head(10)
    if sub.empty:
        return (f"### {label}\n- Nessun dato ESPN raccolto (crowdsourced: si popola "
                "dalle pagine partita visitate).")
    lines = [f"### {label} 2026/27 (feed ESPN, crowdsourced)"]
    for _, r in sub.iterrows():
        lines.append(f"- {r['player']} ({r.get('team')}): {int(r[col])} "
                     f"{'rossi' if kind == 'red' else 'gialli'}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level: contesto LLM
# ─────────────────────────────────────────────────────────────────────────────

def build_llm_context(prompt, df=None):
    """Blocchi di contesto markdown per il prompt LLM, in ordine di rilevanza.

    Giocatori espliciti → partite citate → aggregati (solo se nessuna entità).
    """
    if df is None:
        df = load_dataset()
    blocks = []

    for name in resolve_players(prompt, df)[:MAX_PLAYER_BLOCKS]:
        b = build_player_block(name, df=df)
        if b:
            blocks.append(b)

    payload = _auto_matches_payload()
    metas = resolve_matches(prompt, payload)
    if metas:
        pm_df = _auto_pm_df()
        store = _auto_espn_store()
        tf = (payload or {}).get("team_form") or {}
        for meta in metas[:MAX_MATCH_BLOCKS]:
            blocks.append(build_match_block(meta, team_form=tf, pm_df=pm_df, espn_store=store))

    if not blocks:
        agg = build_aggregate_block(prompt, df=df, pm_df=_auto_pm_df())
        if agg:
            blocks.append(agg)

    return blocks
