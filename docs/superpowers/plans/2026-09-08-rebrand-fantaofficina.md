# Rebrand "La FantaOfficina" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the application brand from "Spectre - FantaMoneyball" to "La FantaOfficina" (bot AI: "FantaMoneyball AI" → "Il Maestro") across the app code and README, then rename the GitHub repository and local project folder to match.

**Architecture:** Pure text/branding rename — no new modules, no behavior changes. Direct grep-driven edits to `web/app.py` and `README.md`, followed by a GitHub repo rename (`gh repo rename`) and a local directory rename (`mv` + git remote URL update). No database, no API contract changes.

**Tech Stack:** Python 3 / Flask (`web/app.py`), Markdown (`README.md`), GitHub CLI (`gh`), git.

## Global Constraints

- New app brand name: **"La FantaOfficina"** (exact capitalization, used wherever "Spectre - FantaMoneyball" currently appears as a full brand string).
- New bot AI name: **"Il Maestro"** (exact capitalization, replaces "FantaMoneyball AI" default value of `BOT_NAME`).
- New GitHub repo slug: **`fantaofficina`** (lowercase, no hyphen) under the existing `spectrelabo` account — final repo path `spectrelabo/fantaofficina`.
- New local folder name: **`fantaofficina`** (replaces the current `fanta-lab` directory name on disk).
- **Do NOT modify:** `LICENSE` copyright line (`Copyright (c) 2026 SpectreLabo` stays exactly as-is).
- **Do NOT modify:** the Vercel project/domain (`fanta-lab.vercel.app` stays exactly as-is — no Vercel commands in this plan).
- **Do NOT modify:** anything under `live_bridge/` (`live_bridge/__init__.py`, `live_bridge/adapter.py`, `live_bridge/rtdb.py`, `live_bridge/drain.py`) or the `fantalab_room_id` / `fantalab_shard` localStorage keys in `web/app.py` — these refer to the external third-party auction app "FantaLab" (unrelated to our brand) and must remain byte-identical.
- **Do NOT modify:** the `ui-glowup` branch/worktree — this plan targets `main` only.
- Baseline test suite: `pytest -q` currently reports **89 passed, 1 pre-existing unrelated error** (`tests/test_dual_track_and_features.py::test`, a fixture-misuse issue unrelated to branding). This exact baseline must be unchanged after every task.

---

### Task 1: Rebrand `web/app.py` — module docstring, bot identity, and page title

**Files:**
- Modify: `web/app.py:3-4` (module docstring)
- Modify: `web/app.py:135` (`BOT_NAME` default)
- Modify: `web/app.py:140-141` (`BOT_GREETING` default)
- Modify: `web/app.py:1354` (comment in `api_ai_query`)
- Modify: `web/app.py:1790` (`<title>` tag)
- Modify: `web/app.py:8377` (startup banner `print`)
- Test: manual grep verification (no existing automated test covers these exact strings; see Step 6)

**Interfaces:**
- Consumes: nothing (pure string literal edits, no new functions/variables)
- Produces: nothing new — `BOT_NAME`, `BOT_GREETING`, `BOT_SUBTITLE`, `BOT_AVATAR_TEXT`, `BOT_BADGE` module-level variables keep their existing names, types (`str`), and override mechanism (env var → personal config → default) exactly as before. Only their **default literal values** change for `BOT_NAME`/`BOT_GREETING`. Later tasks do not depend on any new names from this task.

- [ ] **Step 1: Confirm current exact strings before editing**

Run: `grep -n "FantaMoneyball\|Spectre - " web/app.py`

Expected output (line numbers and content must match exactly before you proceed — if they differ, the file has changed since this plan was written and you should re-read the surrounding context before editing):
```
3:fanta-lab — Spectre - FantaMoneyball: Modern Quantitative Auction & Live Draft Platform for Fantacalcio Serie A
4:Clean, professional interface with local profile isolation, custom targets, FantaMoneyball AI query assistant, and Admin-gated Live Draft.
135:BOT_NAME = "FantaMoneyball AI"
140:    "Ciao! Sono l'assistente quantitativo di **Spectre - FantaMoneyball**. Chiedimi confronti (es. *Malen vs Lautaro*), "
1354:    FantaMoneyball AI Tactical Engine
1790:    <title>Spectre - FantaMoneyball — Centro Decisionale Asta & Strategia</title>
8377:    print("  Spectre - FantaMoneyball — Centro Decisionale Asta & Strategia (PRO)")
```

- [ ] **Step 2: Edit the module docstring (lines 3-4)**

Find:
```python
"""
fanta-lab — Spectre - FantaMoneyball: Modern Quantitative Auction & Live Draft Platform for Fantacalcio Serie A
Clean, professional interface with local profile isolation, custom targets, FantaMoneyball AI query assistant, and Admin-gated Live Draft.
"""
```

Replace with:
```python
"""
fanta-lab — La FantaOfficina: Modern Quantitative Auction & Live Draft Platform for Fantacalcio Serie A
Clean, professional interface with local profile isolation, custom targets, Il Maestro AI query assistant, and Admin-gated Live Draft.
"""
```

- [ ] **Step 3: Edit `BOT_NAME` default and `BOT_GREETING` default (lines 135, 140-141)**

Find:
```python
BOT_NAME = "FantaMoneyball AI"
BOT_SUBTITLE = "Assistente Tattico Quantitativo"
BOT_AVATAR_TEXT = "AI"
BOT_BADGE = "PRO DECISION"
BOT_GREETING = (
    "Ciao! Sono l'assistente quantitativo di **Spectre - FantaMoneyball**. Chiedimi confronti (es. *Malen vs Lautaro*), "
    "analisi di reparto o raccomandazioni basate su VORP e proiezioni ML."
)
```

Replace with:
```python
BOT_NAME = "Il Maestro"
BOT_SUBTITLE = "Assistente Tattico Quantitativo"
BOT_AVATAR_TEXT = "AI"
BOT_BADGE = "PRO DECISION"
BOT_GREETING = (
    "Ciao! Sono l'assistente quantitativo de **La FantaOfficina**. Chiedimi confronti (es. *Malen vs Lautaro*), "
    "analisi di reparto o raccomandazioni basate su VORP e proiezioni ML."
)
```

- [ ] **Step 4: Edit the comment in `api_ai_query` (line 1354)**

Find:
```python
    """
    FantaMoneyball AI Tactical Engine
    Priorità: Ollama locale -> OpenAI-compatible -> Google Gemini -> Local Quantitative Reasoner.
    """
```

Replace with:
```python
    """
    Il Maestro AI Tactical Engine
    Priorità: Ollama locale -> OpenAI-compatible -> Google Gemini -> Local Quantitative Reasoner.
    """
```

- [ ] **Step 5: Edit the `<title>` tag (line 1790) and startup banner (line 8377)**

Find:
```python
    <title>Spectre - FantaMoneyball — Centro Decisionale Asta & Strategia</title>
```

Replace with:
```python
    <title>La FantaOfficina — Centro Decisionale Asta & Strategia</title>
```

Find:
```python
    print("  Spectre - FantaMoneyball — Centro Decisionale Asta & Strategia (PRO)")
```

Replace with:
```python
    print("  La FantaOfficina — Centro Decisionale Asta & Strategia (PRO)")
```

- [ ] **Step 6: Verify no unintended occurrences remain, and no unrelated strings were touched**

Run: `grep -n "FantaMoneyball\|Spectre - " web/app.py`
Expected: no output (empty — all six occurrences replaced).

Run: `grep -n "fantalab_room_id\|fantalab_shard" web/app.py`
Expected: unchanged from before this task (these are unrelated to the brand rename and must still be present, untouched):
```
            const savedRoomId = localStorage.getItem('fantalab_room_id') || '';
            const savedShard = localStorage.getItem('fantalab_shard') || 'auto';
            if (inputRoom) localStorage.setItem('fantalab_room_id', inputRoom.value.trim());
            if (selectShard) localStorage.setItem('fantalab_shard', selectShard.value);
                        localStorage.setItem('fantalab_room_id', qAsta);
                                localStorage.setItem('fantalab_shard', detectedShardStr);
```
(exact line numbers may vary slightly, but all six calls must still exist.)

- [ ] **Step 7: Verify Python syntax and run baseline test suite**

Run: `python3 -c "import ast; ast.parse(open('web/app.py').read())" && echo "SYNTAX OK"`
Expected: `SYNTAX OK`

Run: `/usr/bin/python3 -m pytest -q`
Expected: `89 passed, 1 warning, 1 error in <N>s` (same baseline as before — the 1 error is the pre-existing unrelated `tests/test_dual_track_and_features.py::test` fixture issue).

- [ ] **Step 8: Manually verify the running app shows the new brand**

Run: `cd web && python3 app.py &` (background), wait 2 seconds, then:
`curl -s http://127.0.0.1:5050/ | grep -o "La FantaOfficina\|Il Maestro"`
Expected output includes both `La FantaOfficina` and `Il Maestro` (at least one occurrence each).

Then stop the server: find its PID with `lsof -ti:5050` and `kill <PID>`.

- [ ] **Step 9: Commit**

```bash
git add web/app.py
git commit -m "rebrand: rename app brand to La FantaOfficina, bot to Il Maestro

Renames all in-app branding strings from 'Spectre - FantaMoneyball' to
'La FantaOfficina', and the default bot AI name from 'FantaMoneyball AI'
to 'Il Maestro' (reusing the existing Da Vinci-styled mascot brand from
the UI glow-up). Pure text rename — no behavior changes. The
fantalab_room_id/fantalab_shard localStorage keys and live_bridge/
module (which integrate with the unrelated external auction app
'FantaLab') are explicitly untouched.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Rebrand `README.md`

**Files:**
- Modify: `README.md:1` (title)
- Modify: `README.md:52` (framework description)
- Modify: `README.md:267` (repository structure tree root)
- Modify: `README.md:297-298` (clone instructions)
- Modify: `README.md:364` (support/donation blurb)

**Interfaces:**
- Consumes: nothing (documentation-only edits)
- Produces: nothing (no code interfaces affected)

- [ ] **Step 1: Confirm current exact strings before editing**

Run: `grep -n "FantaMoneyball\|Spectre - \|fanta-lab" README.md`

Expected output (must match before proceeding):
```
1:# Spectre - FantaMoneyball — Quantitative Fantasy Football & League Analytics Framework
52:`FantaMoneyball` was built to replace emotional hallucinations with cold, reproducible, data-driven analytics. The framework does not care about names, transfer market hype, or media narratives. Its singular purpose is to quantify the **risk-adjusted expected value** of every active player and solve the **optimal roster knapsack problem**.
267:fanta-lab/
297:git clone https://github.com/spectrelabo/fanta-lab.git
298:cd fanta-lab
364:If `Spectre - FantaMoneyball` prevented an emotional 2:00 AM panic buy, saved your budget, or gave you an algorithmic edge in your fantasy auction, consider buying a coffee to support ongoing open-source maintenance:
```

- [ ] **Step 2: Edit the title (line 1)**

Find:
```markdown
# Spectre - FantaMoneyball — Quantitative Fantasy Football & League Analytics Framework
```

Replace with:
```markdown
# La FantaOfficina — Quantitative Fantasy Football & League Analytics Framework
```

- [ ] **Step 3: Edit the framework description (line 52)**

Find:
```markdown
`FantaMoneyball` was built to replace emotional hallucinations with cold, reproducible, data-driven analytics. The framework does not care about names, transfer market hype, or media narratives. Its singular purpose is to quantify the **risk-adjusted expected value** of every active player and solve the **optimal roster knapsack problem**.
```

Replace with:
```markdown
`La FantaOfficina` was built to replace emotional hallucinations with cold, reproducible, data-driven analytics. The framework does not care about names, transfer market hype, or media narratives. Its singular purpose is to quantify the **risk-adjusted expected value** of every active player and solve the **optimal roster knapsack problem**.
```

- [ ] **Step 4: Edit the repository structure tree root (line 267)**

Find:
```
fanta-lab/
├── config.py                          # Global configuration, scoring weights, team mappings
```

Replace with:
```
fantaofficina/
├── config.py                          # Global configuration, scoring weights, team mappings
```

- [ ] **Step 5: Edit the clone instructions (lines 297-298)**

Find:
```bash
git clone https://github.com/spectrelabo/fanta-lab.git
cd fanta-lab
```

Replace with:
```bash
git clone https://github.com/spectrelabo/fantaofficina.git
cd fantaofficina
```

- [ ] **Step 6: Edit the support/donation blurb (line 364)**

Find:
```markdown
If `Spectre - FantaMoneyball` prevented an emotional 2:00 AM panic buy, saved your budget, or gave you an algorithmic edge in your fantasy auction, consider buying a coffee to support ongoing open-source maintenance:
```

Replace with:
```markdown
If `La FantaOfficina` prevented an emotional 2:00 AM panic buy, saved your budget, or gave you an algorithmic edge in your fantasy auction, consider buying a coffee to support ongoing open-source maintenance:
```

- [ ] **Step 7: Verify no unintended occurrences remain**

Run: `grep -n "FantaMoneyball\|Spectre - " README.md`
Expected: no output (empty).

Run: `grep -n "fanta-lab" README.md`
Expected: no output (empty — all three occurrences, including the tree root and clone/cd commands, replaced with `fantaofficina`).

- [ ] **Step 8: Commit**

```bash
git add README.md
git commit -m "rebrand: rename README references to La FantaOfficina / fantaofficina

Updates the project title, framework description, repository tree
root, clone instructions, and support blurb to match the new
La FantaOfficina brand and fantaofficina repo slug.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Rename the GitHub repository and update the local remote

**Files:**
- No file content changes in this task — this task renames the GitHub repository itself and updates local git configuration (`.git/config`, not a plan-tracked file).

**Interfaces:**
- Consumes: nothing
- Produces: the git remote `origin` URL now points to `https://github.com/spectrelabo/fantaofficina.git` (or the SSH equivalent, matching whatever protocol the remote already used) — this is required context for Task 4, which renames the local folder and re-verifies the remote from the new working directory.

- [ ] **Step 1: Confirm current remote URL and repo visibility**

Run: `git remote -v`
Expected: shows `origin` pointing to `spectrelabo/fanta-lab` (either `https://github.com/spectrelabo/fanta-lab.git` or `git@github.com:spectrelabo/fanta-lab.git` depending on how it was cloned — note which protocol is in use, you will need it in Step 3).

- [ ] **Step 2: Push any pending local commits from Tasks 1-2 before renaming**

Run: `git push origin main`
Expected: push succeeds (no errors). This ensures the rename happens on a repo that already has the branding-commit history, avoiding any confusion about which commits exist under which name.

- [ ] **Step 3: Rename the repository via GitHub CLI**

Run: `gh repo rename fantaofficina --repo spectrelabo/fanta-lab --yes`
Expected: output confirms the rename, e.g. `✓ Renamed repository spectrelabo/fanta-lab to spectrelabo/fantaofficina`

If `gh` is not authenticated or not installed, stop here and report to the user — do not attempt to rename via the GitHub web UI as a workaround without asking first, since this plan assumes CLI-driven execution.

- [ ] **Step 4: Update the local remote URL to match**

If the remote in Step 1 used HTTPS:
```bash
git remote set-url origin https://github.com/spectrelabo/fantaofficina.git
```

If the remote in Step 1 used SSH:
```bash
git remote set-url origin git@github.com:spectrelabo/fantaofficina.git
```

- [ ] **Step 5: Verify the new remote works**

Run: `git remote -v`
Expected: both `origin` entries (fetch/push) now show `spectrelabo/fantaofficina`.

Run: `git fetch origin`
Expected: succeeds with no errors (confirms the renamed repo is reachable under its new name).

- [ ] **Step 6: Verify the old URL redirects (GitHub's native rename-redirect behavior)**

Run: `curl -s -o /dev/null -w "%{http_code}\n" https://github.com/spectrelabo/fanta-lab`
Expected: `200` (GitHub serves a redirect page/target under the old URL — this is automatic and requires no action, just confirms the redirect is live).

No commit needed for this task (no tracked files changed).

---

### Task 4: Rename the local project folder

**Files:**
- No source files modified — this task renames the working directory itself on disk.

**Interfaces:**
- Consumes: the renamed GitHub repo and updated remote from Task 3.
- Produces: the project now lives at `fantaofficina/` instead of `fanta-lab/` on the local filesystem. This is the final task — nothing downstream depends on it within this plan.

- [ ] **Step 1: Identify the current absolute path and confirm no other process is using it**

Run: `pwd`
Expected: shows the current absolute path ending in `/fanta-lab` (e.g. `/Users/a409835/Documents/myProjects/fanta-lab`). Record the parent directory (e.g. `/Users/a409835/Documents/myProjects`) — you will `cd` there in Step 2.

Run: `lsof -ti:5050`
Expected: no output (empty — confirms no Flask dev server is still running from this directory; if it prints a PID, run `kill <PID>` first before proceeding, since a running server holds a working-directory handle that would otherwise be safe to move but is cleaner to stop first).

- [ ] **Step 2: Move up one directory and rename the folder**

```bash
cd /Users/a409835/Documents/myProjects
mv fanta-lab fantaofficina
cd fantaofficina
```

- [ ] **Step 3: Verify the git repository still works correctly from the new path**

Run: `git status`
Expected: shows the normal working tree status (e.g. `On branch main, nothing to commit, working tree clean`) — confirms git metadata (`.git/`) moved correctly with the folder and is not path-dependent.

Run: `git remote -v`
Expected: still shows `origin` pointing to `spectrelabo/fantaofficina` (from Task 3) — confirms the remote URL is a config value, not a local-path dependency, and survived the folder rename untouched.

- [ ] **Step 4: Verify the worktree for the separate `ui-glowup` branch still resolves correctly**

Run: `git worktree list`
Expected: shows the `ui-glowup` worktree entry, now with its path prefixed by the new `fantaofficina/` location instead of `fanta-lab/` (git worktree metadata auto-updates relative paths when the parent repo moves, but this step confirms it explicitly — if the worktree shows as `prunable` or broken, run `git worktree repair` and re-check).

- [ ] **Step 5: Re-run the baseline test suite from the new location to confirm nothing is path-dependent**

Run: `/usr/bin/python3 -m pytest -q`
Expected: `89 passed, 1 warning, 1 error in <N>s` (identical baseline — confirms no test or fixture hardcodes the old `fanta-lab` absolute or relative path).

No commit needed for this task (no tracked files changed — this is a local filesystem operation only, invisible to git history). Report completion to the user with the new absolute path.

---

## Post-Plan Verification Checklist

After all 4 tasks are complete, do one final end-to-end check:

- [ ] Run `grep -rn "FantaMoneyball\|Spectre - FantaMoneyball" web/app.py README.md` from the new `fantaofficina/` directory — expect no output.
- [ ] Run `/usr/bin/python3 -m pytest -q` one more time — expect `89 passed, 1 warning, 1 error`.
- [ ] Confirm `git remote -v` shows `spectrelabo/fantaofficina`.
- [ ] Confirm the folder is `fantaofficina/` via `pwd`.
- [ ] Report to the user that the Vercel project intentionally still says `fanta-lab` / `fanta-lab.vercel.app` (out of scope per the design spec) and that `live_bridge/` and `fantalab_*` localStorage keys are untouched by design (they refer to the unrelated external auction app).
