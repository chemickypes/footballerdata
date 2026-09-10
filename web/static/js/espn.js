/* ============================================================================
   ESPNX — client ESPN per il tab Partite (dati live: scoreboard, eventi di
   gara, classifica, marcatori).

   Le richieste partono SEMPRE dal browser di chi visita: ESPN blocca gli IP
   da datacenter/server (403) ma lascia passare il canale browser (CORS
   pubblico). Nessuna chiave, nessun backend. Tutti i metodi degradano a
   null/[] senza rompere la pagina se ESPN non risponde.

   Join con i nostri dati: le fixture dello stage 11 hanno date_utc + codici
   squadra (TEAM_ABBR_MAP); ESPN ha date + abbreviations quasi identiche
   (solo ROMA->ROM e COMO->COM richiedono rimappa). La chiave e'
   'giorno-utc|casa|fuori' (±1 giorno per rinvii).
============================================================================ */
const ESPNX = (function () {
    'use strict';

    const BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1';
    const V2 = 'https://site.api.espn.com/apis/v2/sports/soccer/ita.1';

    // abbreviazioni ESPN -> codici squadra del dataset (solo le differenze)
    const CODE_FIX = { ROMA: 'ROM', COMO: 'COM' };
    // fallback per nome (se l'abbreviazione non mappa: promozioni/renaming)
    const NAME_CODE = {
        'internazionale': 'INT', 'inter': 'INT', 'inter milan': 'INT', 'as roma': 'ROM', 'roma': 'ROM',
        'ac milan': 'MIL', 'milan': 'MIL',
        'napoli': 'NAP', 'ssc napoli': 'NAP', 'atalanta': 'ATA', 'lazio': 'LAZ',
        'fiorentina': 'FIO', 'bologna': 'BOL', 'torino': 'TOR', 'udinese': 'UDI',
        'genoa': 'GEN', 'cagliari': 'CAG', 'empoli': 'EMP', 'hellas verona': 'VER',
        'verona': 'VER', 'parma': 'PAR', 'como': 'COM', 'como 1907': 'COM',
        'monza': 'MON', 'lecce': 'LEC', 'venezia': 'VEN', 'sassuolo': 'SAS',
        'frosinone': 'FRO', 'cremonese': 'CRE', 'pisa': 'PIS',
    };

    let _events = [];              // eventi stagione (scoreboard ESPN, raw)
    let _byKey = new Map();        // 'giorno|casa|fuori' -> evento
    let _seasonPromise = null;     // fetch stagione memoizzato (null = retry ok)
    let _summaries = new Map();    // eventId -> Promise<summary|null>
    let _standings = null;         // classifica memoizzata 10 min
    let _standingsAt = 0;
    let _scorersPromise = null;    // marcatori memoizzati per sessione
    let _ready = false;
    const _readyCbs = [];

    /* ---------- utilities ---------- */
    function _esc(s) {
        return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    function _norm(s) {
        return String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-z0-9]+/g, ' ').trim();
    }
    function _utcDay(iso) {
        const d = new Date(iso);
        return isNaN(d) ? '' : d.toISOString().slice(0, 10);
    }
    function _dayOffset(day, n) {
        const d = new Date(day + 'T12:00:00Z');
        d.setUTCDate(d.getUTCDate() + n);
        return d.toISOString().slice(0, 10);
    }
    function _teamCode(comp) {
        const abbr = String((comp.team && comp.team.abbreviation) || '').toUpperCase().replace(/[^A-Z]/g, '');
        if (CODE_FIX[abbr]) return CODE_FIX[abbr];
        if (abbr && abbr.length <= 4) return abbr;
        const nm = _norm((comp.team && (comp.team.displayName || comp.team.shortDisplayName)) || '');
        return NAME_CODE[nm] || abbr;
    }
    // etichetta testuale (short/display name) -> codice squadra dataset
    function codeFromLabel(label) {
        const nm = _norm(label);
        if (NAME_CODE[nm]) return NAME_CODE[nm];
        const up = nm.toUpperCase().replace(/[^A-Z]/g, '');
        return CODE_FIX[up] || up;
    }
    function _key(day, a, b) {
        return day + '|' + [a, b].sort().join('|');
    }
    function _pairsOf(ev) {
        const comp = (ev.competitions || [])[0];
        if (!comp) return null;
        const cs = comp.competitors || [];
        if (cs.length < 2) return null;
        const home = cs.find(c => c.homeAway === 'home') || cs[0];
        const away = cs.find(c => c.homeAway === 'away') || cs[1];
        return { home, away };
    }

    /* ---------- fetch ---------- */
    async function _getJSON(url) {
        try {
            const r = await fetch(url, { cache: 'no-store' });
            if (!r.ok) return null;
            return await r.json();
        } catch (_) {
            return null;
        }
    }

    function _mergeEvents(lists) {
        const byId = new Map();
        for (const list of lists) {
            for (const ev of (list && list.events) || []) {
                if (ev && ev.id && !byId.has(ev.id)) byId.set(ev.id, ev);
            }
        }
        return [...byId.values()].sort((a, b) => ((a.date || '') < (b.date || '') ? -1 : 1));
    }

    function _indexEvents() {
        _byKey = new Map();
        for (const ev of _events) {
            const p = _pairsOf(ev);
            const day = _utcDay(ev.date);
            if (!p || !day) continue;
            _byKey.set(_key(day, _teamCode(p.home), _teamCode(p.away)), ev);
        }
    }

    // blocchi di 14 giorni coperti da scoreboard?dates=YYYYMMDD-YYYYMMDD
    function _ranges(startIso, endIso) {
        const parse = s => {
            if (!s || s.length < 10) return null;
            return new Date(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)));
        };
        const start = parse(startIso), end = parse(endIso);
        if (!start || !end || end < start) return [];
        const out = [];
        let cur = new Date(start);
        while (cur <= end) {
            const blkEnd = new Date(Math.min(cur.getTime() + 13 * 864e5, end.getTime()));
            const fmt = d => '' + d.getUTCFullYear() + String(d.getUTCMonth() + 1).padStart(2, '0') + String(d.getUTCDate()).padStart(2, '0');
            out.push(fmt(cur) + '-' + fmt(blkEnd));
            cur = new Date(blkEnd.getTime() + 864e5);
        }
        return out;
    }

    /* ---------- stagione ---------- */
    function ensureSeason() {
        if (_seasonPromise) return _seasonPromise;
        _seasonPromise = (async () => {
            const board = await _getJSON(BASE + '/scoreboard');
            if (!board || !board.leagues || !board.leagues.length) {
                _seasonPromise = null;
                return false;
            }
            const season = board.leagues[0].season || {};
            const ranges = _ranges(season.startDate, season.endDate);
            const blocks = await Promise.all(ranges.map(rng => _getJSON(BASE + '/scoreboard?dates=' + rng)));
            _events = _mergeEvents([board].concat(blocks));
            _indexEvents();
            if (!_ready) {
                _ready = true;
                const cbs = _readyCbs.splice(0);
                cbs.forEach(cb => { try { cb(); } catch (_) { /* noop */ } });
            }
            return true;
        })();
        return _seasonPromise;
    }

    /* ---------- lookup partita per (data, codici squadra) ---------- */
    function lookup(dateIso, codeA, codeB) {
        if (!_ready || !dateIso || !codeA || !codeB) return null;
        const base = _utcDay(dateIso);
        if (!base) return null;
        for (const off of [0, -1, 1]) {
            const hit = _byKey.get(_key(_dayOffset(base, off), codeA, codeB));
            if (hit) return hit;
        }
        return null;
    }

    /* ---------- stato / punteggi ---------- */
    function stateOf(ev) {
        return (ev && ev.status && ev.status.type && ev.status.type.state) || 'pre';
    }
    function statusOf(ev) {
        const t = (ev && ev.status && ev.status.type) || {};
        const state = t.state || 'pre';
        let clock = '';
        if (state === 'in') {
            clock = ((t.name || '') === 'STATUS_HALFTIME' || /halftime/i.test(t.description || ''))
                ? 'Intervallo'
                : String((ev.status && ev.status.displayClock) || t.shortDetail || '').trim();
        }
        return { state, clock, live: state === 'in', finished: state === 'post' };
    }
    function espnLink(ev) {
        if (!ev) return '';
        // URL canonico dall'evento ("summary", es. .../gameId/<id>/casa-ospite):
        // il solo .../gameId/<id> non risolve più sul sito ESPN.
        const links = ev.links || [];
        const sum = links.find(l => (l.rel || []).includes('summary') && l.href)
            || (links.find(l => l.href) || null);
        if (sum && sum.href) return sum.href;
        return ev.id ? 'https://www.espn.com/soccer/match/_/gameId/' + ev.id : '';
    }
    function scoresOf(ev) {
        const p = _pairsOf(ev || {});
        if (!p) return null;
        const num = v => { const n = parseInt(v, 10); return Number.isFinite(n) ? n : null; };
        const logoOf = c => (c.team && (c.team.logo || (c.team.logos && c.team.logos[0] && c.team.logos[0].href))) || '';
        const st = statusOf(ev);
        return {
            state: st.state, clock: st.clock, live: st.live, finished: st.finished,
            home: { code: _teamCode(p.home), name: (p.home.team && (p.home.team.shortDisplayName || p.home.team.displayName)) || '?', logo: logoOf(p.home), score: num(p.home.score) },
            away: { code: _teamCode(p.away), name: (p.away.team && (p.away.team.shortDisplayName || p.away.team.displayName)) || '?', logo: logoOf(p.away), score: num(p.away.score) },
            link: espnLink(ev),
        };
    }

    /* ---------- summary partita: gol, cartellini, cambi, moduli ---------- */
    function summary(eventId, force) {
        const id = String(eventId);
        if (force && _summaries.has(id)) _summaries.delete(id);
        if (!_summaries.has(id)) {
            _summaries.set(id, _getJSON(BASE + '/summary?event=' + id));
        }
        return _summaries.get(id);
    }

    function _minuteOf(o) {
        const m = String((o && o.clock && o.clock.displayValue) || '').match(/\d+/);
        return m ? parseInt(m[0], 10) : null;
    }
    function _athletes(d) {
        return ((d && (d.athletesInvolved || d.participants)) || [])
            .map(x => (x && x.athlete) || x).filter(Boolean);
    }
    function _nameOf(a) {
        return a ? (a.displayName || a.fullName || a.shortName || '') : '';
    }
    // chi ha servito l'assist: prima dal testo ("Assisted by X"), poi dal secondo
    // atlete dell'azione. Niente assist su rigori/autogol (gestito dal chiamante).
    function _assistOf(d, scorer) {
        const m = String((d && d.text) || '').match(/assist(?:ed by|:)\s+([^.,;(]+)/i);
        let a = m ? m[1].replace(/\s+(with|after|following|from)\b.*$/i, '') : '';
        if (!a) {
            const ath = _athletes(d);
            a = (ath[1] && _nameOf(ath[1])) || '';
        }
        a = String(a).replace(/\s+/g, ' ').trim();
        if (!a || a.toLowerCase() === String(scorer || '').toLowerCase()) return '';
        return a;
    }

    function extractEvents(sm) {
        const out = { events: [], form: { home: '', away: '' } };
        if (!sm) return out;
        const comp = ((sm.header || {}).competitions || [])[0] || {};
        const cs = comp.competitors || [];
        const homeId = ((cs.find(c => c.homeAway === 'home') || cs[0]) || {}).id;
        const sideOf = id => (String(id) === String(homeId) ? 'home' : 'away');

        for (const d of (comp.details || [])) {
            if (!d || !d.scoringPlay || d.shootout) continue;
            const player = _nameOf(_athletes(d)[0]) || '\u2014';
            const kind = d.ownGoal ? 'own' : (d.penaltyKick ? 'penalty' : 'goal');
            out.events.push({
                minute: _minuteOf(d), side: sideOf(d.team && d.team.id), kind, player,
                assist: kind === 'goal' ? _assistOf(d, player) : '',
            });
        }
        for (const k of (sm.keyEvents || [])) {
            const t = String((k.type && k.type.text) || '');
            const type = t.includes('Red Card') ? 'red' : (t.includes('Yellow Card') ? 'yellow' : null);
            if (type) {
                out.events.push({ minute: _minuteOf(k), side: sideOf(k.team && k.team.id), kind: type, player: _nameOf(_athletes(k)[0]) || '\u2014', assist: '' });
                continue;
            }
            if (/substitution/i.test(t)) {
                const names = (k.participants || []).map(p => p.athlete && p.athlete.displayName).filter(Boolean);
                out.events.push({ minute: _minuteOf(k), side: sideOf(k.team && k.team.id), kind: 'sub', player: names[0] || '', assist: names[1] || '' });
            }
        }
        out.events.sort((a, b) => (a.minute || 0) - (b.minute || 0));

        for (const r of (sm.rosters || [])) {
            const s = r.homeAway === 'home' ? 'home' : 'away';
            out.form[s] = r.formation || '';
        }
        return out;
    }

    /* ---------- classifica (endpoint v2) ---------- */
    async function standings() {
        const now = Date.now();
        if (_standings && now - _standingsAt < 10 * 60 * 1000) return _standings;
        const d = await _getJSON(V2 + '/standings');
        if (!d) return _standings || null;
        let entries = [];
        const ch = d.children || [];
        if (ch.length && ch[0].standings && ch[0].standings.entries) entries = ch[0].standings.entries;
        else if (d.standings && d.standings.entries) entries = d.standings.entries;
        if (!entries.length) return _standings || null;
        const statOf = (e, ...names) => {
            for (const n of names) {
                const s = (e.stats || []).find(x => x.name === n || x.abbreviation === n);
                if (s) return (s.displayValue != null ? s.displayValue : s.value);
            }
            return '';
        };
        const num = v => { const n = parseInt(v, 10); return Number.isFinite(n) ? n : 0; };
        const rows = entries.map((e, i) => {
            const t = e.team || {};
            return {
                pos: num(statOf(e, 'rank')) || i + 1,
                name: t.shortDisplayName || t.displayName || '?',
                logo: t.logo || (t.logos && t.logos[0] && t.logos[0].href) || '',
                pts: num(statOf(e, 'points')), gp: num(statOf(e, 'gamesPlayed')),
                w: num(statOf(e, 'wins')), d: num(statOf(e, 'ties')), l: num(statOf(e, 'losses')),
                gf: num(statOf(e, 'pointsFor', 'goalsFor')), ga: num(statOf(e, 'pointsAgainst', 'goalsAgainst')),
                gd: statOf(e, 'pointDifferential', 'goalDifference'),
            };
        }).sort((a, b) => a.pos - b.pos);
        _standings = rows;
        _standingsAt = now;
        return rows;
    }

    /* ---------- marcatori: gol contati dalle partite della stagione ---------- */
    function _teamLabel(comp, teamId) {
        const c = (comp.competitors || []).find(x => String(x.team && x.team.id) === String(teamId));
        return c && c.team ? (c.team.shortDisplayName || c.team.displayName || '') : '';
    }
    function _ranking(map) {
        return [...map.entries()]
            .map(kv => { const p = kv[0].split('|'); return { player: p[0], team: p[1] || '', goals: kv[1] }; })
            .sort((a, b) => b.goals - a.goals || a.player.localeCompare(b.player))
            .slice(0, 30);
    }
    // gratis: i gol sono gia' nelle partite scaricate all'avvio. Vale solo se
    // il tabellone porta i dettagli per quasi tutte le partite con gol.
    function _countFromScoreboard() {
        const map = new Map();
        let withGoals = 0, withDetails = 0;
        for (const ev of _events) {
            const comp = (ev.competitions || [])[0];
            if (!comp) continue;
            const goals = (comp.competitors || []).reduce((s, c) => s + (parseInt(c.score, 10) || 0), 0);
            const det = comp.details || [];
            if (stateOf(ev) === 'post' && goals > 0) { withGoals++; if (det.length) withDetails++; }
            for (const d of det) {
                if (!d || !d.scoringPlay || d.ownGoal || d.shootout) continue;
                const name = _nameOf(_athletes(d)[0]);
                if (!name) continue;
                const k = name + '|' + _teamLabel(comp, d.team && d.team.id);
                map.set(k, (map.get(k) || 0) + 1);
            }
        }
        if (withGoals < 5 || withDetails / withGoals < 0.8) return null;
        return _ranking(map);
    }
    // a mano: un summary per partita finita, 5 richieste alla volta
    async function _countFromSummaries(onProgress) {
        const done = _events.filter(ev => stateOf(ev) === 'post');
        if (!done.length) return [];
        const map = new Map();
        let made = 0;
        const queue = done.slice();
        const worker = async () => {
            while (queue.length) {
                const ev = queue.shift();
                const parsed = extractEvents(await summary(ev.id));
                const comp = (ev.competitions || [])[0] || {};
                for (const e of parsed.events) {
                    if (e.kind !== 'goal' && e.kind !== 'penalty') continue; // autogol e cartellini fuori
                    const c = (comp.competitors || []).find(x => (e.side === 'home' ? x.homeAway === 'home' : x.homeAway === 'away')) || {};
                    const label = c.team ? (c.team.shortDisplayName || c.team.displayName || '') : '';
                    const k = e.player + '|' + label;
                    map.set(k, (map.get(k) || 0) + 1);
                }
                made++;
                if (onProgress) { try { onProgress(made, done.length); } catch (_) { /* noop */ } }
            }
        };
        await Promise.all([0, 1, 2, 3, 4].map(worker));
        return _ranking(map);
    }
    function scorers(onProgress) {
        if (!_scorersPromise) {
            _scorersPromise = (async () => {
                await ensureSeason();
                const fast = _countFromScoreboard();
                if (fast) return fast;
                const rows = await _countFromSummaries(onProgress);
                if (!rows.length) _scorersPromise = null; // ritentabile al prossimo accesso
                return rows;
            })();
        }
        return _scorersPromise;
    }

    /* ---------- ready ---------- */
    function ready() { return _ready; }
    function whenReady(cb) {
        if (_ready) cb();
        else _readyCbs.push(cb);
    }

    /* ---------- refresh mirato (bottone sulla pagina partita) ---------- */
    function _upsertEvents(fresh) {
        const byId = new Map(_events.map(ev => [ev.id, ev]));
        for (const ev of fresh || []) if (ev && ev.id) byId.set(ev.id, ev);
        _events = [...byId.values()].sort((a, b) => ((a.date || '') < (b.date || '') ? -1 : 1));
        _indexEvents();
    }

    // Ricarica lo scoreboard del giorno della partita (stato live/punteggi
    // aggiornati), invalida il summary cachato e ritorna l'evento fresco.
    async function refreshEvent(dateIso, codeA, codeB) {
        const day = _utcDay(dateIso);
        if (!day) return null;
        const d = await _getJSON(BASE + '/scoreboard?dates=' + day.replace(/-/g, '') + '&_=' + Date.now());
        if (d && d.events && d.events.length) _upsertEvents(d.events);
        const ev = lookup(dateIso, codeA, codeB);
        if (ev) summary(ev.id, true);
        return ev;
    }

    return {
        ensureSeason, lookup, summary, extractEvents,
        statusOf, scoresOf, stateOf, espnLink, codeFromLabel,
        standings, scorers, refreshEvent,
        ready, whenReady,
    };
})();
window.ESPNX = ESPNX;
