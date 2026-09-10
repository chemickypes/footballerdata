let allPlayers = [];
let currentRoleFilter = 'ALL';
let currentFasciaFilter = 'ALL';
let matchesData = null;
let currentMatchdayView = null;

function runBootSplash(onComplete) {
    const splash = document.getElementById('appBootSplash');
    if (!splash) {
        onComplete();
        return;
    }
    setTimeout(() => {
        splash.classList.add('fade-out');
        setTimeout(() => {
            splash.style.display = 'none';
            onComplete();
        }, 250); // matches the 0.25s CSS transition above
    }, 400);
}

/* ─────────────────────────────────────────────────────────────
   TOAST NOTIFICATIONS
───────────────────────────────────────────────────────────── */
/* ─────────────────────────────────────────────────────────────
   PLAYER DETAIL DRAWER (Finestra Medica & Metriche Avanzate)
───────────────────────────────────────────────────────────── */
function openPlayerDetailDrawer(playerName, opts) {
    opts = opts || {};
    const p = (typeof allPlayers !== 'undefined' ? allPlayers : []).find(x => x.player === playerName) ||
              (typeof allPlayers !== 'undefined' ? allPlayers : []).find(x => (x.player || '').trim().toLowerCase() === (playerName || '').trim().toLowerCase());
    if (!p) {
        console.warn('Player not found for detail page:', playerName);
        return;
    }
    _currentDetailPlayer = p;

    // Header
    document.getElementById('pdName').textContent = p.player;
    const roleEl = document.getElementById('pdRole');
    roleEl.textContent = p.role;
    roleEl.className = 'role-badge role-' + p.role.toLowerCase();
    document.getElementById('pdTeam').textContent = p.team || '';

    // Summary bar
    document.getElementById('pdFairPrice').textContent = `${getPlayerFairPrice(p)} cr`;
    document.getElementById('pdVorp').textContent = (p.vorp || 0).toFixed(1);
    document.getElementById('pdScore').textContent = (p.score || 0).toFixed(1);
    document.getElementById('pdFascia').textContent = p.fascia;

    // Econometric Target & Clearing
    const activeB = leagueBudget || 1000;
    const targetPr = activeB === 500 ? (p.target_price_500 || p.price_fair_500 || 1) : (p.target_price_1000 || p.price_fair_1000 || 1);
    const clearPr = activeB === 500 ? (p.clearing_price_500 || targetPr) : (p.clearing_price_1000 || targetPr);
    document.getElementById('pdTargetPrice').textContent = `${targetPr} cr`;
    document.getElementById('pdClearingPrice').textContent = `${clearPr} cr`;
    const surplus = targetPr - clearPr;
    const surpEl = document.getElementById('pdSurplusVal');
    surpEl.textContent = (surplus >= 0 ? '+' : '') + `${surplus} cr`;
    surpEl.style.color = surplus >= 0 ? 'var(--success)' : 'var(--danger)';

    const flags = p.target_flags || '';
    document.getElementById('pdTargetFlags').textContent = flags ? `Fattori: ${flags.replace(/;/g, ' • ')}` : 'Nessun fattore correttivo applicato';
    const badgeEl = document.getElementById('pdClearingSourceBadge');
    if (flags.includes('asta_xlsx')) {
        badgeEl.textContent = 'Asta Reale (1000cr)';
        badgeEl.style.background = 'rgba(63,185,117,0.15)';
        badgeEl.style.color = '#3fb975';
    } else if (flags.includes('fantabot_golden')) {
        badgeEl.textContent = 'Aste Storiche (500cr)';
        badgeEl.style.background = 'rgba(94,139,255,0.15)';
        badgeEl.style.color = '#5e8bff';
    } else {
        badgeEl.textContent = 'Stima Target';
        badgeEl.style.background = 'rgba(255,255,255,0.05)';
        badgeEl.style.color = 'var(--text-muted)';
    }

    // Medical
    const med = p.medical || {};
    document.getElementById('pdDaysLost').textContent = med.days_lost_3y || 0;
    document.getElementById('pdInjCount').textContent = med.injuries_count_3y || 0;

    const severeEl = document.getElementById('pdSevere');
    severeEl.innerHTML = med.infortunio_grave 
        ? '<span style="color:var(--danger);"><i class="fa-solid fa-triangle-exclamation icon-pulse" style="margin-right:3px;"></i> Sì</span>' 
        : '<span style="color:var(--success);"><i class="fa-solid fa-circle-check" style="margin-right:3px;"></i> No</span>';

    const medBadge = document.getElementById('pdMedBadge');
    medBadge.innerHTML = (med.status_badge || '') + ' ' + (med.status_label || 'N/D');
    if (med.status === 'safe') { medBadge.style.background = 'rgba(63,185,117,0.15)'; medBadge.style.color = '#3fb975'; }
    else if (med.status === 'warning') { medBadge.style.background = 'rgba(194,147,67,0.15)'; medBadge.style.color = '#c29343'; }
    else { medBadge.style.background = 'rgba(229,83,75,0.15)'; medBadge.style.color = '#e5534b'; }

    const injList = document.getElementById('pdInjuryList');
    const details = med.dettaglio_infortuni || [];
    if (details.length > 0) {
        injList.innerHTML = details.map(d => `<div style="padding:2px 0; border-bottom:1px solid var(--border);">• ${d}</div>`).join('');
    } else {
        injList.innerHTML = '<div style="color:var(--text-muted); font-style:italic;">Nessun dettaglio disponibile</div>';
    }

    // Understat
    const us = p.understat || {};
    document.getElementById('pdXg90').textContent = (us.xg_per90 || 0).toFixed(3);
    document.getElementById('pdNpxg90').textContent = (us.npxg_per90 || 0).toFixed(3);
    document.getElementById('pdXa90').textContent = (us.xa_per90 || 0).toFixed(3);
    document.getElementById('pdShots90').textContent = (us.shots_per90 || 0).toFixed(2);

    const deltaEl = document.getElementById('pdDeltaXg');
    const deltaVal = us.delta_goals_xg || 0;
    deltaEl.textContent = (deltaVal >= 0 ? '+' : '') + deltaVal.toFixed(2);
    deltaEl.style.color = deltaVal >= 0 ? 'var(--success)' : 'var(--danger)';

    // Quantiles
    const q = p.quantiles || {};
    const p10 = q.floor_p10 || 0, p50 = q.expected_p50 || 0, p90 = q.ceiling_p90 || 0;
    document.getElementById('pdP10').textContent = p10.toFixed(0);
    document.getElementById('pdP50').textContent = p50.toFixed(0);
    document.getElementById('pdP90').textContent = p90.toFixed(0);
    document.getElementById('pdSpread').textContent = (q.spread || 0).toFixed(0);

    const profBadge = document.getElementById('pdProfileBadge');
    profBadge.innerHTML = q.profile_badge || '';
    if ((q.spread || 0) < 150) { profBadge.style.background = 'rgba(94,139,255,0.15)'; profBadge.style.color = '#5e8bff'; }
    else { profBadge.style.background = 'rgba(194,147,67,0.15)'; profBadge.style.color = '#c29343'; }

    // Quantile visual bar
    const maxContrib = Math.max(p90, 250);
    const barLeft = (p10 / maxContrib) * 100;
    const barWidth = ((p90 - p10) / maxContrib) * 100;
    const p50Pos = (p50 / maxContrib) * 100;
    const qBar = document.getElementById('pdQuantileBar');
    qBar.style.left = barLeft + '%';
    qBar.style.width = barWidth + '%';
    qBar.style.background = 'rgba(94,139,255,0.25)';
    document.getElementById('pdQuantileP50Mark').style.left = p50Pos + '%';

    // Career trajectory (lazy fetch)
    loadPlayerTrajectory(p.player);

    // Starter info
    const starterEl = document.getElementById('pdStarter');
    if (starterEl) {
        starterEl.innerHTML = p.is_starter_2627 
            ? '<span style="color:var(--success);"><i class="fa-solid fa-circle-check" style="margin-right:3px;"></i> Sì</span>' 
            : '<span style="color:var(--danger);"><i class="fa-solid fa-circle-xmark" style="margin-right:3px;"></i> No</span>';
    }
    document.getElementById('pdStarts').textContent = p.starts_2627 || 0;
    document.getElementById('pdMinutes').textContent = (p.minutes_2627 || 0).toLocaleString();

    // Team form (Serie A results, stage 11)
    renderTeamForm(p.team);

    // Per-match stats (Serie A match log, stage 12) — lazy fetch
    loadPlayerMatches(p.player);

    // Season heatmap (stage 13) — lazy fetch
    window.__pdPlayerName = p.player;
    loadPlayerHeatmap(p.player);

    // Advanced season stats (stage 14) — lazy fetch
    loadPlayerAdvanced(p.player);

    // Attributes / contract (Transfermarkt)
    const fmtMV = v => v == null ? 'N/D' : (v >= 1e6 ? `€${(v / 1e6).toFixed(v % 1e6 === 0 ? 0 : 1)}M` : `€${Math.round(v / 1e3)}K`);
    document.getElementById('pdAge').textContent = p.age != null ? p.age : 'N/D';
    document.getElementById('pdHeight').textContent = p.height_cm != null ? `${p.height_cm} cm` : 'N/D';
    document.getElementById('pdFoot').textContent = p.foot || 'N/D';
    document.getElementById('pdMarketValue').textContent = fmtMV(p.market_value_eur);
    document.getElementById('pdContract').textContent = p.contract_until || 'N/D';

    // Show full-page player view
    const page = document.getElementById('playerPage');
    if (page) {
        page.style.display = 'block';
        page.scrollTop = 0;
    }
    if (!opts.noPush) {
        const target = '/player/' + encodeURIComponent(p.player);
        if (window.location.pathname !== target) {
            try { history.pushState({ playerPage: p.player }, '', target); } catch (e) { /* noop */ }
        }
    }
}

function _hidePlayerPage() {
    const page = document.getElementById('playerPage');
    if (page) page.style.display = 'none';
    _currentDetailPlayer = null;
}

window.addEventListener('popstate', function(e) {
    const st = e.state || {};
    if (st.playerPage) {
        _hideMatchPage();
        if (!_currentDetailPlayer || _currentDetailPlayer.player !== st.playerPage) {
            openPlayerDetailDrawer(st.playerPage, { noPush: true });
        }
    } else if (st.matchPage) {
        if (_currentDetailPlayer) _hidePlayerPage();
        if (!_currentMatchDetailId || _currentMatchDetailId !== st.matchPage) {
            openMatchPage(st.matchPage, { noPush: true });
        }
    } else {
        if (_currentDetailPlayer) _hidePlayerPage();
        if (_currentMatchDetailId) _hideMatchPage();
    }
});

function _normalizePlayerName(s) {
    return String(s || '').toLowerCase().trim().replace(/[.'\-\s]/g, '');
}

function loadPlayerTrajectory(playerName) {
    const el = document.getElementById('pdTrajectory');
    if (!el) return;
    el.innerHTML = '<div style="font-style:italic;">Caricamento…</div>';
    fetch(`/api/player_history?player=${encodeURIComponent(playerName)}`)
        .then(r => r.ok ? r.json() : Promise.reject(new Error('not found')))
        .then(data => {
            const hist = (data.history || []).filter(h => h.mv != null && h.mv > 0);
            if (!hist.length) {
                el.innerHTML = '<div style="font-style:italic;">Nessuno storico Serie A disponibile (giovane o nuova acquisizione)</div>';
                return;
            }
            el.innerHTML = renderTrajectorySVG(hist);
        })
        .catch(() => {
            el.innerHTML = '<div style="font-style:italic;">Nessuno storico Serie A disponibile</div>';
        });
}

function renderTrajectorySVG(hist) {
    const W = 400, H = 170, padL = 30, padR = 8, padT = 12, padB = 34;
    const n = hist.length;
    const mvs = hist.map(h => h.mv);
    let yMin = Math.min(5.0, Math.floor(Math.min(...mvs) * 2) / 2) - 0.1;
    const yMax = Math.max(7.5, Math.ceil(Math.max(...mvs) * 2) / 2) + 0.1;
    const x = i => n === 1 ? (padL + (W - padL - padR) / 2) : padL + (i / (n - 1)) * (W - padL - padR);
    const y = v => padT + (1 - (v - yMin) / (yMax - yMin)) * (H - padT - padB);

    let gridLines = '';
    for (let gv = Math.ceil(yMin); gv <= Math.floor(yMax); gv++) {
        gridLines += `<line x1="${padL}" y1="${y(gv)}" x2="${W - padR}" y2="${y(gv)}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>` +
            `<text x="${padL - 5}" y="${y(gv) + 3}" text-anchor="end" font-size="9" fill="rgba(255,255,255,0.35)">${gv}</text>`;
    }

    const points = hist.map((h, i) => ({ cx: x(i), cy: y(h.mv), h }));
    const path = points.map((pt, i) => `${i === 0 ? 'M' : 'L'}${pt.cx.toFixed(1)},${pt.cy.toFixed(1)}`).join(' ');
    const dots = points.map(pt => {
        const h = pt.h;
        const tip = `${h.season} · ${h.team || '?'} · ${h.pg} presenze · MV ${h.mv.toFixed(2)}` +
            ((h.gol || h.assist) ? ` · ${h.gol || 0}G ${h.assist || 0}A` : '');
        return `<circle cx="${pt.cx.toFixed(1)}" cy="${pt.cy.toFixed(1)}" r="4" fill="var(--primary)" stroke="var(--surface-elevated)" stroke-width="1.5"><title>${tip}</title></circle>`;
    }).join('');
    const seasonLabels = points.map(pt => {
        const s = pt.h.season || '';
        const short = s.length >= 7 ? s.slice(2, 5) + '/' + s.slice(7) : s;
        return `<text x="${pt.cx.toFixed(1)}" y="${H - padB + 14}" text-anchor="middle" font-size="8.5" fill="rgba(255,255,255,0.45)">${short}</text>`;
    }).join('');
    const pgLabels = points.map(pt =>
        `<text x="${pt.cx.toFixed(1)}" y="${H - padB + 25}" text-anchor="middle" font-size="8" fill="rgba(255,255,255,0.30)">${pt.h.pg}p</text>`
    ).join('');

    const last = hist[n - 1];
    const trend = n >= 2 ? (mvs[n - 1] - mvs[n - 2]) : 0;
    const trendTxt = n >= 2
        ? `<span style="color:${trend >= 0 ? 'var(--success)' : 'var(--danger)'}; font-weight:600;">${trend >= 0 ? '▲' : '▼'} ${Math.abs(trend).toFixed(2)}</span> vs stagione precedente`
        : '';

    return `
        <svg viewBox="0 0 ${W} ${H}" style="width:100%; height:auto; display:block;" role="img" aria-label="Traiettoria MV per stagione">
            ${gridLines}
            <path d="${path}" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linejoin="round" opacity="0.9"/>
            ${dots}
            ${seasonLabels}
            ${pgLabels}
        </svg>
        <div style="margin-top:4px; font-size:0.72rem; color:var(--text-muted);">
            MV per stagione (presenze sotto) — ultima: <b style="color:var(--text-main);">${last.mv.toFixed(2)}</b> in ${n} stagioni Serie A ${trendTxt}
        </div>
    `;
}

function closePlayerDetailDrawer() {
    if (history.state && history.state.playerPage) {
        history.back();  // il popstate chiama _hidePlayerPage()
        return;
    }
    _hidePlayerPage();
}

/* ─────────────────────────────────────────────────────────────
   MATCH PAGE (dettaglio partita: formazioni, marcatori, MOTM)
   ───────────────────────────────────────────────────────────── */
let _currentMatchDetailId = null;

function openMatchPage(eventId, opts) {
    opts = opts || {};
    eventId = parseInt(eventId, 10);
    if (!eventId) return;
    if (_currentDetailPlayer) _hidePlayerPage();
    _currentMatchDetailId = eventId;

    const page = document.getElementById('matchPage');
    if (page) {
        page.style.display = 'block';
        page.scrollTop = 0;
    }
    if (!opts.noPush) {
        const target = '/match/' + eventId;
        if (window.location.pathname !== target) {
            try { history.pushState({ matchPage: eventId }, '', target); } catch (err) { /* noop */ }
        }
    }
    loadMatchDetail(eventId);
}

function _hideMatchPage() {
    const page = document.getElementById('matchPage');
    if (page) page.style.display = 'none';
    _currentMatchDetailId = null;
}

function closeMatchPage() {
    if (history.state && history.state.matchPage) {
        history.back();
        return;
    }
    _hideMatchPage();
}

function loadMatchDetail(eventId) {
    const el = document.getElementById('mdScoreline');
    if (el) el.textContent = 'Caricamento…';
    fetch(`/api/match_detail?event=${parseInt(eventId, 10)}`)
        .then(r => r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? 'no-data' : 'error')))
        .then(data => renderMatchDetail(data))
        .catch(() => {
            if (el) el.textContent = 'Partita';
            ['mdHomeLineup', 'mdAwayLineup'].forEach(id => {
                const c = document.getElementById(id);
                if (c) c.innerHTML = '<div style="font-style:italic;">Dati non disponibili (esegui gli stage 11 e 12)</div>';
            });
        });
}

function _mdRatingBadge(rating) {
    if (rating == null) return '<span class="md-rating" style="color:var(--text-muted);">—</span>';
    let bg = 'rgba(255,255,255,0.08)', color = 'var(--text-muted)';
    if (rating >= 7.5) { bg = 'rgba(63,185,117,0.16)'; color = '#3fb975'; }
    else if (rating >= 6.8) { bg = 'rgba(94,139,255,0.16)'; color = 'var(--primary)'; }
    return `<span class="md-rating" style="background:${bg}; color:${color};">${rating.toFixed(1)}</span>`;
}

function _mdLineupRow(p) {
    const name = p.player || p.player_sofascore || '?';
    const enc = encodeURIComponent(name);
    const hasDataset = !!p.player;
    const nameHtml = hasDataset
        ? `<a href="/player/${enc}" style="color:var(--text-main); text-decoration:none; font-weight:600;"
              onclick="event.preventDefault(); openPlayerDetailDrawer(decodeURIComponent('${enc}'))">${name}</a>`
        : `<span style="color:var(--text-muted);">${name}</span>`;
    const evBits = [];
    if (p.goals > 0) evBits.push(`<span title="Gol">⚽${p.goals > 1 ? p.goals : ''}</span>`);
    if (p.assists > 0) evBits.push(`<span title="Assist" style="color:var(--primary);">🅰${p.assists > 1 ? p.assists : ''}</span>`);
    if (!p.is_starter) evBits.push(`<span title="Subentrato" style="color:var(--text-muted);">↺</span>`);
    return `
        <div class="md-row">
            <span class="md-shirt">${p.shirt_number != null ? p.shirt_number : ''}</span>
            ${nameHtml}
            <span class="md-events">${evBits.join(' ')}</span>
            <span class="md-min">${p.minutes_played != null ? p.minutes_played + "'" : ''}</span>
            ${_mdRatingBadge(p.rating)}
        </div>`;
}

function renderMatchDetail(data) {
    const m = data.match || {};
    const subEl = document.getElementById('mdSub');
    const scoreEl = document.getElementById('mdScoreline');
    if (subEl) subEl.textContent = `Serie A · Giornata ${m.round || '—'} · ${formatMatchDate(m.date)}`;

    const finished = m.finished && m.home_score != null && m.away_score != null;
    if (scoreEl) {
        scoreEl.innerHTML = finished
            ? `<span>${m.home_team}</span>
               <span class="md-score">${m.home_score} – ${m.away_score}</span>
               <span>${m.away_team}</span>`
            : `<span>${m.home_team}</span>
               <span class="md-score md-score-tbd">vs</span>
               <span>${m.away_team}</span>`;
    }

    const strip = document.getElementById('mdScorersStrip');
    if (strip) {
        const bits = [];
        if (data.scorers && data.scorers.length) {
            bits.push('⚽ ' + data.scorers.map(s => `${s.player}${s.goals > 1 ? ` (${s.goals})` : ''}`).join(', '));
        }
        if (data.motm) {
            bits.push(`<span style="margin-left:auto;"><i class="fa-solid fa-star" style="color:var(--gold);"></i> MOTM: <b style="color:var(--text-main);">${data.motm.player}</b> (${data.motm.rating.toFixed(1)})</span>`);
        }
        if (bits.length) {
            strip.innerHTML = bits.join('');
            strip.style.display = 'flex';
            strip.style.flexWrap = 'wrap';
            strip.style.gap = '8px';
        } else {
            strip.style.display = 'none';
        }
    }

    const homeEl = document.getElementById('mdHomeName');
    const awayEl = document.getElementById('mdAwayName');
    if (homeEl) homeEl.textContent = data.home ? data.home.name : '—';
    if (awayEl) awayEl.textContent = data.away ? data.away.name : '—';

    const noLineups = '<div style="font-style:italic;">Formazioni disponibili dopo la partita (stage 12)</div>';
    ['mdHomeLineup', 'mdAwayLineup'].forEach((id, i) => {
        const c = document.getElementById(id);
        if (!c) return;
        const side = i === 0 ? data.home : data.away;
        if (!data.lineups_available || !side || !side.players.length) {
            c.innerHTML = noLineups;
        } else {
            c.innerHTML = side.players.map(_mdLineupRow).join('');
        }
    });
}


function toggleMobileSidebar() {
    const sb = document.getElementById('appSidebar');
    const bd = document.getElementById('sidebarBackdrop');
    sb.classList.toggle('open');
    bd.classList.toggle('show');
}

async function init() {
    await fetchPlayers();
    fetchAIStatus();
    await fetchMatches();
    renderListone();

    runBootSplash(() => {});

    // Apertura diretta pagina giocatore (route /player/<name>)
    if (window.__initialPlayer) {
        openPlayerDetailDrawer(window.__initialPlayer, { noPush: true });
    }
    // Apertura diretta pagina partita (route /match/<id>)
    if (window.__initialMatch) {
        openMatchPage(window.__initialMatch, { noPush: true });
    }

    if (window.location.hash) {
        const tabName = window.location.hash.replace('#', '');
        if (['ai', 'listone', 'partite'].includes(tabName)) {
            switchTab(tabName);
        }
    }
}

let leagueBudget = 1000;

function getPlayerFairPrice(p, budget) {
    if (!p) return 1;
    const b = budget || leagueBudget || 1000;

    // If player object has _budget_scale from API matching this budget
    if (p._budget_scale !== undefined && Math.round(p._budget_scale * 1000) === b) {
        return p.price_fair_scaled || (b === 500 ? (p.price_fair_500 || Math.round(p.price_fair_1000 * 0.5)) : p.price_fair_1000);
    }

    // Accurate benchmark for 500 cr
    if (b === 500) {
        if (p.price_fair_500) return p.price_fair_500;
        if (p.price_fair_1000) return Math.max(1, Math.round(p.price_fair_1000 * 0.5));
    }

    // Accurate benchmark for 1000 cr
    if (b === 1000) {
        if (p.price_fair_1000) return p.price_fair_1000;
    }

    // Proportional scaling for any custom budget
    let base1000 = p.price_fair_1000;
    if (!base1000) {
        if (p._budget_scale && p._budget_scale !== 1.0) {
            base1000 = Math.round((p.price_fair_scaled || 1) / p._budget_scale);
        } else {
            base1000 = p.price_fair_scaled || 1;
        }
    }
    return Math.max(1, Math.round(base1000 * (b / 1000.0)));
}

async function fetchPlayers() {
    const res = await fetch(`/api/players?budget=${leagueBudget}`);
    const data = await res.json();
    allPlayers = data.players || [];
    if (data.league_budget) leagueBudget = data.league_budget;
    renderListone();
}

/* ─────────────────────────────────────────────────────────────
   PARTITE & RISULTATI TAB (Serie A match results & team form)
   ───────────────────────────────────────────────────────────── */
async function fetchMatches() {
    try {
        const res = await fetch('/api/matches');
        matchesData = await res.json();
        if (matchesData && matchesData.available && !currentMatchdayView) {
            const rounds = (matchesData.rounds || []).map(r => r.round);
            currentMatchdayView = matchesData.current_round || rounds[0] || 1;
        }
        if (document.getElementById('tab-partite') && document.getElementById('tab-partite').classList.contains('active')) {
            renderMatches();
        }
    } catch (e) {
        matchesData = null;
    }
}

function changeMatchdayRound(delta) {
    if (!matchesData || !matchesData.available || !matchesData.rounds || !matchesData.rounds.length) return;
    const rounds = matchesData.rounds.map(r => r.round);
    let idx = rounds.indexOf(currentMatchdayView);
    if (idx === -1) idx = 0;
    idx = Math.min(rounds.length - 1, Math.max(0, idx + delta));
    currentMatchdayView = rounds[idx];
    renderMatches();
}

function formatMatchDate(dateStr) {
    const d = new Date(dateStr);
    if (isNaN(d)) return '';
    const date = d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short' });
    const time = d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    return `${date} · ${time}`;
}

function renderMatchCard(m) {
    const finished = m.finished && m.home_score != null && m.away_score != null;
    const homeWin = finished && m.home_score > m.away_score;
    const awayWin = finished && m.away_score > m.home_score;

    const scoreHtml = finished
        ? `<span class="match-score">${m.home_score}<span class="match-score-sep">–</span>${m.away_score}</span>`
        : `<span class="match-score match-score-tbd">vs</span>`;

    const htHtml = (finished && m.ht_home_score != null && m.ht_away_score != null)
        ? `<div class="match-ht">HT ${m.ht_home_score}–${m.ht_away_score}</div>` : '';

    const meta = finished
        ? `<div class="match-meta">Finale${(m.status && m.status !== 'FT') ? ` (${m.status})` : ''}</div>`
        : `<div class="match-meta">${formatMatchDate(m.date)}</div>`;

    return `
        <div class="match-card" data-finished="${finished ? 1 : 0}" onclick="openMatchPage(${m.fixture_id})" title="Dettaglio partita">
            <div class="match-team match-team-home ${homeWin ? 'win' : ''}">
                <span class="match-team-name">${m.home_display || m.home_team || '?'}</span>
                <span class="match-team-code">${m.home_code || ''}</span>
            </div>
            <div class="match-center">
                ${scoreHtml}
                ${htHtml}
                ${meta}
            </div>
            <div class="match-team match-team-away ${awayWin ? 'win' : ''}">
                <span class="match-team-code">${m.away_code || ''}</span>
                <span class="match-team-name">${m.away_display || m.away_team || '?'}</span>
            </div>
        </div>
    `;
}

function renderMatches() {
    const container = document.getElementById('matchesContainer');
    if (!container) return;
    const label = document.getElementById('matchdayLabel');

    if (!matchesData || !matchesData.available || !matchesData.rounds || !matchesData.rounds.length) {
        if (label) label.textContent = 'Giornata —';
        container.innerHTML = `
            <div style="text-align:center; color:var(--text-muted); padding:28px 16px; font-size:0.85rem; line-height:1.6;">
                <i class="fa-solid fa-database" style="font-size:1.3rem; display:block; margin-bottom:8px; opacity:0.6;"></i>
                Risultati non ancora importati.<br>
                Esegui lo stage 11 della pipeline:<br>
                <code style="color:var(--primary); background:rgba(94,139,255,0.08); padding:2px 8px; border-radius:6px; font-size:0.78rem;">python run_pipeline.py --step 11</code>
            </div>`;
        return;
    }

    const seasonLabel = document.getElementById('matchesSeasonLabel');
    if (seasonLabel && matchesData.season) seasonLabel.textContent = 'Serie A ' + matchesData.season;

    const lastRound = matchesData.rounds[matchesData.rounds.length - 1].round;
    if (label) label.textContent = `Giornata ${currentMatchdayView} / ${lastRound}`;

    const rnd = matchesData.rounds.find(r => r.round === currentMatchdayView);
    if (!rnd || !rnd.matches.length) {
        container.innerHTML = '<div style="text-align:center; color:var(--text-muted); padding:24px; font-size:0.85rem;">Nessuna partita trovata per questa giornata.</div>';
        return;
    }

    container.innerHTML = rnd.matches.map(m => renderMatchCard(m)).join('');
}

function renderTeamForm(teamCode) {
    const el = document.getElementById('pdTeamForm');
    if (!el) return;
    const form = (matchesData && matchesData.team_form) || {};
    const entry = form[teamCode];
    if (!entry) {
        el.innerHTML = '<div style="font-style:italic; font-size:0.78rem;">Nessun dato disponibile (esegui lo stage 11: risultati Serie A)</div>';
        return;
    }
    const chipClass = { W: 'form-w', D: 'form-d', L: 'form-l' };
    const chips = (entry.last5 || []).map(x => {
        const tip = `Giornata ${x.round || '?'} vs ${x.opponent || '?'} (${x.venue === 'home' ? 'Casa' : 'Fuori'}) — ${x.gf}-${x.ga}`;
        return `<span class="form-chip ${chipClass[x.result] || ''}" title="${tip}">${x.result}</span>`;
    }).join('');
    el.innerHTML = `
        <div style="display:flex; gap:4px; margin-bottom:6px; flex-wrap:wrap;">
            ${chips || '<span style="font-style:italic; font-size:0.76rem;">Nessuna partita disputata</span>'}
        </div>
        <div style="font-size:0.72rem; color:var(--text-muted);">
            Stagione: <b style="color:var(--text-main);">${entry.wins}V ${entry.draws}N ${entry.losses}P</b> · ${entry.points} punti · GF ${entry.gf} / GA ${entry.ga}
        </div>
    `;
}

/* ─────────────────────────────────────────────────────────────
   ULTIME PARTITE (per-match player stats, stage 12)
   ───────────────────────────────────────────────────────────── */
function loadPlayerMatches(playerName) {
    const el = document.getElementById('pdRecentMatches');
    if (!el) return;
    el.innerHTML = '<div style="font-style:italic;">Caricamento…</div>';
    fetch(`/api/player_matches?player=${encodeURIComponent(playerName)}`)
        .then(r => r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? 'no-data' : 'error')))
        .then(data => { el.innerHTML = renderRecentMatches(data); })
        .catch(() => {
            el.innerHTML = '<div style="font-style:italic; font-size:0.76rem;">Nessuna partita registrata (giocatore fuori quota o stage 12 non eseguito)</div>';
        });
}

function _pmRatingColor(rating) {
    if (rating == null) return 'var(--text-muted)';
    if (rating >= 7.3) return '#3fb975';
    if (rating >= 6.8) return 'var(--primary)';
    if (rating >= 6.2) return 'var(--text-main)';
    return '#e5534b';
}

function _pmRatingSparkline(matches) {
    const rated = matches.filter(m => m.rating != null).slice(0, 5).reverse();
    if (rated.length < 2) return '';
    const W = 380, H = 46, padB = 12;
    const lo = Math.min(5.8, Math.min(...rated.map(m => m.rating)) - 0.2);
    const hi = Math.max(7.6, Math.max(...rated.map(m => m.rating)) + 0.2);
    const x = i => (i + 0.5) * (W / rated.length);
    const y = v => padB + (1 - (v - lo) / (hi - lo)) * (H - padB - 4);
    const bars = rated.map((m, i) => {
        const bw = Math.min(26, (W / rated.length) - 6);
        return `<rect x="${(x(i) - bw / 2).toFixed(1)}" y="${y(m.rating).toFixed(1)}" width="${bw}" height="${(H - padB - y(m.rating)).toFixed(1)}" rx="2" fill="rgba(94,139,255,0.35)"><title>G${m.round} · ${m.rating.toFixed(1)} vs ${m.opponent_display}</title></rect>` +
            `<text x="${x(i).toFixed(1)}" y="${(y(m.rating) - 3).toFixed(1)}" text-anchor="middle" font-size="8.5" font-weight="600" fill="${_pmRatingColor(m.rating)}">${m.rating.toFixed(1)}</text>`;
    }).join('');
    const labels = rated.map((m, i) =>
        `<text x="${x(i).toFixed(1)}" y="${H - 1}" text-anchor="middle" font-size="7.5" fill="rgba(255,255,255,0.35)">G${m.round}</text>`
    ).join('');
    return `
        <svg viewBox="0 0 ${W} ${H}" style="width:100%; height:auto; display:block; margin-bottom:8px;" role="img" aria-label="Rating ultime partite">
            ${bars}${labels}
        </svg>
    `;
}

function renderRecentMatches(data) {
    const ms = (data.matches || []).slice(0, 8);
    if (!ms.length) {
        return '<div style="font-style:italic; font-size:0.76rem;">Nessuna partita registrata in questa stagione</div>';
    }
    const s = data.summary || {};

    const sparkline = _pmRatingSparkline(ms);
    const summaryTxt = [
        s.played != null ? `${s.played} presenze` : null,
        s.starts != null ? `${s.starts} da titolare` : null,
        s.avg_rating != null ? `rating medio <b style="color:${_pmRatingColor(s.avg_rating)};">${s.avg_rating.toFixed(2)}</b>` : null,
        s.goals ? `${s.goals}G` : null,
        s.assists ? `${s.assists}A` : null,
        s.xg ? `xG ${s.xg.toFixed(1)}` : null,
        s.minutes != null ? `${Math.round(s.minutes / Math.max(1, s.played))}' media` : null,
    ].filter(Boolean).join(' · ');

    const rows = ms.map(m => {
        const venueTag = m.venue === 'home' ? 'Casa' : 'Fuori';
        const ratingTxt = m.rating != null ? m.rating.toFixed(1) : '–';
        const chips = [];
        if (m.goals) chips.push(`<span class="pm-chip pm-chip-g">${m.goals}G</span>`);
        if (m.assists) chips.push(`<span class="pm-chip pm-chip-a">${m.assists}A</span>`);
        if (m.xg && m.xg >= 0.3) chips.push(`<span class="pm-chip pm-chip-x">xG ${m.xg.toFixed(1)}</span>`);
        return `
            <div class="pm-row">
                <span class="pm-round">G${m.round || '?'}</span>
                <span class="pm-opp">${m.opponent_display || m.opponent || '?'} <span style="color:var(--text-muted); font-weight:400;">· ${venueTag}</span></span>
                <span class="pm-min">${m.minutes != null ? m.minutes + "'" : '–'}</span>
                <span class="pm-rating" style="color:${_pmRatingColor(m.rating)};">${ratingTxt}</span>
                <span class="pm-chips">${chips.join('')}</span>
            </div>
        `;
    }).join('');

    return `
        ${sparkline}
        <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:8px;">${summaryTxt}</div>
        <div class="pm-list">${rows}</div>
    `;
}

/* ─────────────────────────────────────────────────────────────
   MAPPA DI GIOCO (season heatmap, stage 13)
   ───────────────────────────────────────────────────────────── */
let heatmapRoundState = { player: null, until: '' };

function loadPlayerHeatmap(playerName, untilRound) {
    const el = document.getElementById('pdHeatmap');
    if (!el) return;
    if (heatmapRoundState.player !== playerName) {
        heatmapRoundState = { player: playerName, until: untilRound || '' };
    } else if (untilRound !== undefined) {
        heatmapRoundState.until = untilRound || '';
    }
    el.innerHTML = '<div style="font-style:italic;">Caricamento…</div>';
    const q = heatmapRoundState.until ? `&until_round=${encodeURIComponent(heatmapRoundState.until)}` : '';
    fetch(`/api/player_heatmap?player=${encodeURIComponent(playerName)}${q}`)
        .then(r => r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? 'no-data' : 'error')))
        .then(data => { el.innerHTML = renderPlayerHeatmap(data); })
        .catch(() => {
            el.innerHTML = '<div style="font-style:italic; font-size:0.76rem;">Nessun dato mappa (stage 13 non eseguito o giocatore senza posizioni registrate)</div>';
        });
}

function _heatColor(t) {
    // Scala blu → rossa stile heatmap (t = 0 freddo, 1 caldo)
    const lerp = (a, b, k) => Math.round(a + (b - a) * k);
    return `rgb(${lerp(56, 255, t)},${lerp(108, 92, t)},${lerp(255, 61, t)})`;
}

function renderPlayerHeatmap(data) {
    const cols = data.grid.cols, rowsN = data.grid.rows;
    const cells = data.cells || [];
    if (!cells.length || !data.points) {
        return '<div style="font-style:italic; font-size:0.76rem;">Nessuna posizione registrata</div>';
    }
    const maxCount = Math.max(...cells);
    if (!maxCount) {
        return '<div style="font-style:italic; font-size:0.76rem;">Nessuna posizione registrata</div>';
    }

    const W = 300, H = 200, cw = W / cols, ch = H / rowsN;
    const lineStroke = 'rgba(255,255,255,0.14)';

    let rects = '';
    for (let i = 0; i < cells.length; i++) {
        const c = cells[i];
        if (!c) continue;
        const t = Math.pow(c / maxCount, 0.75);
        const x = (i % cols) * cw, y = Math.floor(i / cols) * ch;
        rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${cw.toFixed(1)}" height="${ch.toFixed(1)}" fill="${_heatColor(t)}" fill-opacity="0.62"/>`;
    }

    const pitch = `
        <g fill="none" stroke="${lineStroke}" stroke-width="1.2">
            <rect x="1.5" y="1.5" width="${W - 3}" height="${H - 3}" rx="1"/>
            <line x1="${W / 2}" y1="1.5" x2="${W / 2}" y2="${H - 1.5}"/>
            <circle cx="${W / 2}" cy="${H / 2}" r="20"/>
            <rect x="1.5" y="${H / 2 - 48}" width="36" height="96"/>
            <rect x="${W - 37.5}" y="${H / 2 - 48}" width="36" height="96"/>
            <rect x="1.5" y="${H / 2 - 24}" width="14" height="48"/>
            <rect x="${W - 15.5}" y="${H / 2 - 24}" width="14" height="48"/>
        </g>`;

    // Selettore "fino alla giornata N" (solo se il player ha >= 2 giornate)
    let roundSel = '';
    const rounds = data.available_rounds || [];
    if (rounds.length >= 2) {
        const opts = ['<option value="">Stagione completa</option>']
            .concat(rounds.map(r =>
                `<option value="${r}"${String(r) === String(heatmapRoundState.until) ? ' selected' : ''}>Fino alla G${r}</option>`));
        roundSel = `
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:6px; font-size:0.72rem; color:var(--text-muted);">
                <span>Periodo:</span>
                <select id="pdHeatmapRoundSel" onchange="loadPlayerHeatmap(window.__pdPlayerName, this.value)"
                        style="background:var(--surface-elevated); color:var(--text-main); border:1px solid var(--border); border-radius:6px; padding:2px 6px; font-size:0.72rem;">
                    ${opts.join('')}
                </select>
            </div>`;
    }

    return `
        ${roundSel}
        <svg viewBox="0 0 ${W} ${H + 4}" style="width:100%; height:auto; display:block; background:rgba(255,255,255,0.02); border-radius:6px;" role="img" aria-label="Mappa di gioco stagionale">
            <defs>
                <filter id="pmHeatBlur" x="-5%" y="-5%" width="110%" height="110%">
                    <feGaussianBlur stdDeviation="2.2"/>
                </filter>
            </defs>
            ${pitch}
            <g filter="url(#pmHeatBlur)">${rects}</g>
        </svg>
        <div style="display:flex; justify-content:space-between; margin-top:5px; font-size:0.68rem; color:var(--text-muted);">
            <span>◀ porta propria</span>
            <span>${data.matches} partite · ${data.points} tocchi</span>
            <span>porta avversaria ▶</span>
        </div>
    `;
}

/* ─────────────────────────────────────────────────────────────
   STATISTICHE AVANZATE (season aggregates per-90 + percentili, stage 14)
   ───────────────────────────────────────────────────────────── */
function loadPlayerAdvanced(playerName) {
    const el = document.getElementById('pdAdvanced');
    if (!el) return;
    el.innerHTML = '<div style="font-style:italic;">Caricamento…</div>';
    fetch(`/api/player_advanced?player=${encodeURIComponent(playerName)}`)
        .then(r => r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? 'no-data' : 'error')))
        .then(data => { el.innerHTML = renderPlayerAdvanced(data); })
        .catch(() => {
            el.innerHTML = '<div style="font-style:italic; font-size:0.76rem;">Nessun dato (stage 14 non eseguito o giocatore senza minuti giocati)</div>';
        });
}

const ADV_GROUPS = [
    ['Attacco', [
        ['goals_per90', 'Gol', 'per90'], ['assists_per90', 'Assist', 'per90'],
        ['xg_per90', 'xG', 'per90'], ['xa_per90', 'xA', 'per90'],
        ['shots_per90', 'Tiri', 'per90'], ['shots_on_target_per90', 'Tiri in porta', 'per90'],
        ['key_passes_per90', 'Passaggi chiave', 'per90'], ['big_chances_created_per90', 'Occasioni grosse create', 'per90'],
    ]],
    ['Passaggi', [
        ['passes_pct', 'Passaggi riusciti', 'pct'], ['passes_final_third_per90', 'In ultimo terzo', 'per90'],
        ['long_balls_pct', 'Lunghi riusciti', 'pct'], ['crosses_per90', 'Cross', 'per90'],
    ]],
    ['Possesso', [
        ['touches_per90', 'Tocchi', 'per90'], ['dribbles_per90', 'Dribbling riusciti', 'per90'],
        ['dribbles_pct', 'Dribbling riusciti', 'pct'], ['possession_won_att_third', 'Recuperi zona offensiva', 'total'],
        ['dispossessed', 'Palla persa (contrastata)', 'total'], ['possession_lost', 'Possessi persi', 'total'],
    ]],
    ['Difesa', [
        ['tackles_per90', 'Contrasti', 'per90'], ['interceptions_per90', 'Intercetti', 'per90'],
        ['clearances_per90', 'Respingimenti', 'per90'], ['blocks_per90', 'Tiri bloccati', 'per90'],
        ['aerials_won_per90', 'Duelli aerei vinti', 'per90'], ['aerials_pct', 'Duelli aerei vinti', 'pct'],
        ['duels_pct', 'Duelli totali vinti', 'pct'], ['ball_recoveries_per90', 'Palla recuperata', 'per90'],
        ['fouls', 'Falli', 'total'],
    ]],
    ['Portiere', [
        ['saves_per90', 'Parate', 'per90'], ['saves_caught', 'Parate trattenute', 'total'],
        ['high_claims_per90', 'Uscite alte', 'per90'], ['punches_per90', 'Respinti di pugno', 'per90'],
        ['clean_sheets', 'Porte inviolate', 'total'], ['goals_prevented', 'Gol prevenuti', 'total'],
        ['goals_conceded', 'Gol subiti', 'total'],
    ]],
];

function _advBar(pct) {
    if (pct == null) return '';
    const w = Math.max(2, Math.min(100, pct));
    const color = pct >= 70 ? '#4ade80' : (pct >= 40 ? 'var(--accent)' : 'var(--text-muted)');
    return `
        <div style="flex:1; height:5px; background:rgba(255,255,255,0.07); border-radius:3px; overflow:hidden; margin:0 8px;">
            <div style="width:${w}%; height:100%; background:${color}; border-radius:3px;"></div>
        </div>
        <span style="font-size:0.66rem; color:var(--text-muted); width:28px; text-align:right;">${Math.round(pct)}</span>`;
}

function _advRow(key, label, kind, data) {
    let value, pct = null;
    if (kind === 'per90') {
        value = (data.per90 || {})[key];
        pct = (data.percentiles || {})[key];
    } else if (kind === 'pct') {
        value = (data.pcts || {})[key];
        pct = (data.percentiles || {})[key];
        if (value != null) value = value.toFixed(1) + '%';
    } else {
        value = (data.totals || {})[key];
        if (key === 'goals_prevented' && value != null) {
            value = value.toFixed(2);
            pct = (data.percentiles || {})['goals_prevented'];
        }
    }
    if (value == null) return '';
    if (kind === 'total' && typeof value === 'number' && !Number.isInteger(value)) {
        value = Math.round(value);
    }
    return `
        <div style="display:flex; align-items:center; padding:3px 0; font-size:0.74rem;">
            <span style="width:150px; flex-shrink:0; color:var(--text-muted);">${label}</span>
            <span style="width:44px; flex-shrink:0; text-align:right; font-weight:600; color:var(--text-main);">${value}</span>
            ${_advBar(pct)}
        </div>`;
}

function renderPlayerAdvanced(data) {
    if (!data || !data.minutes) {
        return '<div style="font-style:italic; font-size:0.76rem;">Nessun dato disponibile</div>';
    }
    const isKeeper = data.role === 'P';
    const started = data.matches_started || 0;
    const cards = data.cards || {};
    const cardsTxt = [cards.yellow ? `${cards.yellow} 🟨` : '', (cards.red || cards.direct_red) ? `${(cards.red || 0) + (cards.direct_red || 0)} 🟥` : '']
        .filter(Boolean).join(' · ');

    const metaBits = [
        `${data.appearances} presenze (${started} titolare)`,
        `${data.minutes} min`,
        data.rating != null ? `voto ${Number(data.rating).toFixed(2)}` : null,
        cardsTxt || null,
    ].filter(Boolean).join(' · ');

    const groups = ADV_GROUPS
        .filter(([title]) => title !== 'Portiere' || isKeeper)
        .map(([title, rows]) => {
            const body = rows.map(([key, label, kind]) => _advRow(key, label, kind, data)).join('');
            if (!body) return '';
            return `
                <div style="font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; color:var(--text-muted); margin:10px 0 3px;">${title}</div>
                ${body}`;
        }).join('');

    return `
        <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:4px;">${metaBits}</div>
        <div style="font-size:0.68rem; color:var(--text-muted); margin-bottom:6px; font-style:italic;">Barre = percentile vs pari ruolo Serie A (min. 60')</div>
        ${groups}
    `;
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.sidebar-nav-btn').forEach(el => el.classList.remove('active'));

    const targetTab = document.getElementById('tab-' + tabId);
    if (targetTab) targetTab.classList.add('active');

    const botBtn = document.getElementById('botNav-' + tabId);
    if (botBtn) botBtn.classList.add('active');

    const sideBtn = document.getElementById('sideNav-' + tabId);
    if (sideBtn) sideBtn.classList.add('active');

    // Close mobile drawer if open
    const sb = document.getElementById('appSidebar');
    const bd = document.getElementById('sidebarBackdrop');
    if (sb && sb.classList.contains('open')) {
        sb.classList.remove('open');
        bd.classList.remove('show');
    }

    if (tabId === 'listone') renderListone();
    if (tabId === 'partite') renderMatches();
}

function setRoleFilter(role) {
    currentRoleFilter = role;
    document.querySelectorAll('#rolePills .pill').forEach(el => {
        el.classList.toggle('active', el.textContent.includes(role === 'ALL' ? 'Tutti' : role));
    });
    renderListone();
}

function setFasciaFilter(f) {
    currentFasciaFilter = f;
    document.querySelectorAll('#fasciaPills .pill').forEach(el => {
        el.classList.toggle('active', el.textContent.includes(f === 'ALL' ? 'Tutte' : f + 'ª'));
    });
    renderListone();
}

/* ─────────────────────────────────────────────────────────────
   TACTICAL AI CONVERSATIONAL CHATBOT ENGINE
───────────────────────────────────────────────────────────── */
const AI_AVATAR_HTML = `<div class="chat-msg-avatar" style="background:var(--primary); display:flex; align-items:center; justify-content:center;"><svg style="width:15px; height:15px; stroke:#0a0a0b; fill:none; stroke-width:2;" viewBox="0 0 24 24"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg></div>`;

function setAIQuery(queryText) {
    document.getElementById('aiInputPrompt').value = queryText;
    submitAIQuery();
}

function clearAIChat() {
    const stream = document.getElementById('chatMessagesStream');
    stream.innerHTML = `
        <div class="chat-msg ai">
            ${AI_AVATAR_HTML}
            <div class="chat-bubble">
                <b>Chat azzerata.</b><br>
                Come posso aiutarti? Chiedimi confronti tra giocatori, proiezioni o statistiche.
            </div>
        </div>
    `;
}

async function submitAIQuery() {
    const input = document.getElementById('aiInputPrompt');
    const prompt = input.value.trim();
    if (!prompt) return;

    const stream = document.getElementById('chatMessagesStream');
    const btn = document.getElementById('btnSubmitAI');

    // 1. Append User Message Bubble
    const userMsg = document.createElement('div');
    userMsg.className = 'chat-msg user';
    userMsg.innerHTML = `<div class="chat-bubble">${escapeHTML(prompt)}</div>`;
    stream.appendChild(userMsg);

    input.value = '';
    if (btn) btn.disabled = true;

    // 2. Append Temporary Loading Bubble
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'chat-msg ai';
    loadingMsg.id = 'aiChatLoadingBubble';
    loadingMsg.innerHTML = `
        ${AI_AVATAR_HTML}
        <div class="chat-bubble" style="color:var(--text-muted); font-style:italic;">
            Sto analizzando statistiche, proiezioni e valori di mercato...
        </div>
    `;
    stream.appendChild(loadingMsg);
    stream.scrollTop = stream.scrollHeight;

    try {
        const res = await fetch('/api/ai_query', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ prompt: prompt })
        });

        if (!res.ok) {
            const errTxt = await res.text();
            throw new Error(`Server ${res.status}: ${errTxt.slice(0, 100)}`);
        }

        const data = await res.json();

        // Remove loading bubble
        const loadElem = document.getElementById('aiChatLoadingBubble');
        if (loadElem) loadElem.remove();

        // 3. Append AI Response Bubble
        const aiMsg = document.createElement('div');
        aiMsg.className = 'chat-msg ai';
        aiMsg.innerHTML = `
            ${AI_AVATAR_HTML}
            <div class="chat-bubble">
                ${renderAIChatContent(data)}
            </div>
        `;
        stream.appendChild(aiMsg);
    } catch(e) {
        console.error("AI Chat Exception:", e);
        const loadElem = document.getElementById('aiChatLoadingBubble');
        if (loadElem) loadElem.remove();

        const errBubble = document.createElement('div');
        errBubble.className = 'chat-msg ai';
        errBubble.innerHTML = `
            ${AI_AVATAR_HTML}
            <div class="chat-bubble" style="color:var(--danger); font-size:0.85rem;">
                <b>Errore di elaborazione:</b> ${escapeHTML(e.message || "Riprova con un'altra domanda.")}
            </div>
        `;
        stream.appendChild(errBubble);
    }

    if (btn) btn.disabled = false;
    stream.scrollTop = stream.scrollHeight;
}

function escapeHTML(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function formatMarkdownText(text) {
    if (!text) return '';
    let raw = escapeHTML(text);

    const nl = String.fromCharCode(10);
    // 1. Process Markdown Tables (| col1 | col2 |)
    const lines = raw.split(nl);
    let inTable = false;
    let tableHtml = '';
    let processedLines = [];

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line.startsWith('|') && line.endsWith('|')) {
            const cells = line.slice(1, -1).split('|').map(c => c.trim());
            // Skip separator row (|---|---|)
            if (cells.every(c => /^:?-+:?$/.test(c))) {
                continue;
            }
            if (!inTable) {
                inTable = true;
                tableHtml = '<div style="overflow-x:auto; margin:8px 0;"><table class="ai-table" style="width:100%; border-collapse:collapse; font-size:0.80rem; text-align:left;">';
                tableHtml += '<thead><tr style="border-bottom:1px solid var(--border); background:rgba(255,255,255,0.04); color:var(--text-main);">';
                cells.forEach(c => { tableHtml += `<th style="padding:6px 8px; font-weight:600;">${c}</th>`; });
                tableHtml += '</tr></thead><tbody>';
            } else {
                tableHtml += '<tr style="border-bottom:1px solid rgba(255,255,255,0.08);">';
                cells.forEach(c => { tableHtml += `<td style="padding:5px 8px;">${c}</td>`; });
                tableHtml += '</tr>';
            }
        } else {
            if (inTable) {
                tableHtml += '</tbody></table></div>';
                processedLines.push(tableHtml);
                inTable = false;
                tableHtml = '';
            }
            processedLines.push(line);
        }
    }
    if (inTable) {
        tableHtml += '</tbody></table></div>';
        processedLines.push(tableHtml);
    }

    let formatted = processedLines.join(nl);
    // Headers
    formatted = formatted.replace(/^### (.*$)/gim, '<h4 style="color:var(--primary); font-size:0.95rem; margin:10px 0 4px 0;">$1</h4>');
    formatted = formatted.replace(/^## (.*$)/gim, '<h3 style="color:var(--text-main); font-size:1.02rem; margin:12px 0 6px 0;">$1</h3>');
    // Bold & Italic
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<b style="color:var(--text-main);">$1</b>');
    formatted = formatted.replace(/\*(.*?)\*/g, '<i style="color:var(--text-muted);">$1</i>');
    // Bullet Points
    formatted = formatted.replace(/^\s*-\s+(.*$)/gim, '<div style="display:flex; gap:6px; margin-bottom:3px;"><span style="color:var(--primary);">&bull;</span><span>$1</span></div>');
    // Spacing
    formatted = formatted.split(nl + nl).join('<div style="height:8px;"></div>');
    formatted = formatted.split(nl).join('<br>');
    return formatted;
}

function renderAIChatContent(data) {
    if (!data) return 'Nessuna risposta disponibile.';
    const engineTag = `<div style="margin-top:8px; padding-top:6px; border-top:1px dashed rgba(255,255,255,0.08); font-size:0.68rem; color:var(--text-muted); display:flex; justify-content:space-between; align-items:center;"><span>Fonte: <b style="color:var(--primary);">${data.engine || 'Regole Tattiche Offline'}</b></span><span>${new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span></div>`;

    try {
        if (data.type === 'llm_chat') {
            return `<div>${formatMarkdownText(data.text || '')}${engineTag}</div>`;
        }

        if (data.type === 'roster_diagnostic') {
            const s = data.stats || {};
            const free = s.free_slots || {};
            return `
                <div>
                    <div style="font-weight:800; font-size:1.02rem; color:var(--primary); margin-bottom:8px;">${data.title || 'Analisi'}</div>
                    <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:6px; background:var(--surface-elevated); padding:8px 10px; border-radius:8px; margin-bottom:10px; font-size:0.82rem;">
                        <div>Crediti Residui: <b style="color:var(--gold);">${s.remaining || 0} cr</b></div>
                        <div>Max Rilancio: <b style="color:var(--danger);">${s.max_bid || 0} cr</b></div>
                        <div>Slot Liberi: <b>${free.total || 0}</b> (P:${free.P || 0} D:${free.D || 0} C:${free.C || 0} A:${free.A || 0})</div>
                        <div>Media cr/slot: <b>${s.avg_per_slot || 0} cr</b></div>
                    </div>
                    <div style="margin-bottom:8px;">
                        ${(data.advice || []).map(a => `<div style="margin-bottom:4px; font-size:0.85rem;">&bull; ${a}</div>`).join('')}
                    </div>
                    <div style="background:rgba(94,139,255,0.08); border-left:3px solid var(--primary); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
                        ${data.verdict || ''}
                    </div>
                    ${engineTag}
                </div>
            `;
        }

        if (data.type === 'comparison') {
            const players = data.players || [];
            return `
                <div>
                    <div style="font-weight:600; font-size:1rem; color:var(--primary); margin-bottom:10px;">${data.title || 'Confronto'}</div>
                    <div style="display:grid; grid-template-columns:${players.length > 2 ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)'}; gap:8px; margin-bottom:10px;">
                        ${players.map(p => `
                            <div style="background:var(--surface-elevated); padding:10px 8px; border-radius:8px; border:1px solid var(--border); font-size:0.82rem;">
                                <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                                    <span class="badge badge-${p.role}">${p.role}</span>
                                    <b>${p.name}</b>
                                </div>
                                <div style="color:var(--text-muted); font-size:0.75rem; margin-bottom:4px;">${p.team} - ${p.starts || 0} start</div>
                                <div>Contributo Atteso: <b>${p.contrib_exp || 0}</b></div>
                                <div>Fair Price: <b style="color:var(--gold);">${p.fair_1000 || 1} cr</b></div>
                                <div>VORP: <b style="color:var(--success);">+${p.vorp || 0}</b></div>
                            </div>
                        `).join('')}
                    </div>
                    <div style="background:rgba(94,139,255,0.08); border-left:3px solid var(--primary); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
                        ${formatMarkdownText(data.verdict || '')}
                    </div>
                    ${engineTag}
                </div>
            `;
        }

        if (data.type === 'player_deepdive') {
            const p = data.player || {};
            return `
                <div>
                    <div style="font-weight:600; font-size:1rem; color:var(--primary); margin-bottom:8px;">${data.title}</div>
                    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; text-align:center; margin-bottom:10px;">
                        <div style="background:var(--surface-elevated); padding:8px; border-radius:6px; border:1px solid var(--border);">
                            <div style="font-size:0.7rem; color:var(--text-muted); font-weight:600;">PROIEZIONE P50</div>
                            <div style="font-size:1.05rem; font-weight:600; color:var(--primary);">${p.contrib_exp || 0}</div>
                        </div>
                        <div style="background:var(--surface-elevated); padding:8px; border-radius:6px; border:1px solid var(--border);">
                            <div style="font-size:0.7rem; color:var(--text-muted); font-weight:600;">FAIR PRICE 1000</div>
                            <div style="font-size:1.05rem; font-weight:600; color:var(--gold);">${p.fair_1000 || 1} cr</div>
                        </div>
                        <div style="background:var(--surface-elevated); padding:8px; border-radius:6px; border:1px solid var(--border);">
                            <div style="font-size:0.7rem; color:var(--text-muted); font-weight:600;">TITOLARITÀ REALE</div>
                            <div style="font-size:1.05rem; font-weight:600; color:var(--success);">${p.starts || 0} start</div>
                        </div>
                    </div>
                    <div style="background:rgba(94,139,255,0.08); border-left:3px solid var(--primary); padding:8px 10px; border-radius:4px; font-size:0.85rem; margin-bottom:8px;">
                        ${formatMarkdownText(data.verdict || '')}
                    </div>
                    ${engineTag}
                </div>
            `;
        }

        if (data.type === 'recommendations') {
            const players = data.players || [];
            return `
                <div>
                    <div style="font-weight:600; font-size:1rem; color:var(--success); margin-bottom:8px;">${data.title}</div>
                    <div style="margin-bottom:10px;">
                        ${players.map(p => `
                            <div class="candidate-mini-row" style="display:flex; justify-content:space-between; align-items:center; padding:6px 8px; margin-bottom:4px; background:var(--surface-elevated); border-radius:6px; border:1px solid var(--border);">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span class="badge badge-${p.role}">${p.role}</span>
                                    <b>${p.name}</b> <small style="color:var(--text-muted);">(${p.team})</small>
                                </div>
                                <div style="text-align:right;">
                                    <span style="color:var(--gold); font-weight:600; font-size:0.95rem;">${p.fair_1000} cr</span>
                                    <span style="color:var(--primary); font-size:0.78rem; margin-left:6px;">+${p.vorp} vorp</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    <div style="background:rgba(63,185,117,0.08); border-left:3px solid var(--success); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
                        ${formatMarkdownText(data.verdict || '')}
                    </div>
                    ${engineTag}
                </div>
            `;
        }

        // Generic fallback for any unexpected type or structure
        const fallbackText = data.text || data.verdict || JSON.stringify(data);
        return `<div>${formatMarkdownText(fallbackText)}${engineTag}</div>`;
    } catch(renderErr) {
        console.error("renderAIChatContent Error:", renderErr);
        return `<div>${formatMarkdownText(data.text || data.verdict || 'Risposta elaborata.')}${engineTag}</div>`;
    }
}

async function fetchAIStatus() {
    try {
        const res = await fetch('/api/ai_status');
        const diag = await res.json();
        const dot = document.getElementById('aiEngineStatusDot');
        const lbl = document.getElementById('aiActiveEngineLabel');
        if (diag.has_llm) {
            if (dot) dot.className = 'status-dot dot-green';
            if (lbl) {
                lbl.textContent = diag.active_engine;
                lbl.style.color = 'var(--success)';
            }
        } else {
            if (dot) dot.className = 'status-dot dot-yellow';
            if (lbl) {
                lbl.textContent = 'Fallback Matematico (Nessuna API Key)';
                lbl.style.color = 'var(--gold)';
            }
        }
        return diag;
    } catch(e) {
        return null;
    }
}

async function openAIDiagnosticsModal() {
    const diag = await fetchAIStatus();
    const modal = document.getElementById('aiDiagnosticsModal');
    if (!modal || !diag) return;

    document.getElementById('diagActiveEngine').textContent = diag.active_engine || 'Nessuno';
    document.getElementById('diagActiveEngineDesc').textContent = diag.has_llm 
        ? 'LLM Cloud attivo: le risposte sono generate con intelligenza artificiale conversazionale.' 
        : 'Attualmente attivo il motore a regole locali: riconosce confronti, schede giocatore, formazioni e diagnosi, ma non genera risposte libere complesse.';

    const badge = document.getElementById('modalAiBadge');
    if (badge) {
        badge.textContent = diag.has_llm ? 'ONLINE' : 'OFFLINE MODE';
        badge.style.color = diag.has_llm ? 'var(--success)' : 'var(--gold)';
    }

    const list = document.getElementById('aiProvidersList');
    if (list && diag.providers) {
        list.innerHTML = Object.entries(diag.providers).map(([k, p]) => `
            <div style="background:var(--surface-elevated); border:1px solid var(--border); border-radius:6px; padding:8px 10px; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-weight:600; font-size:0.82rem; color:var(--text-main);">${p.name}</div>
                    <div style="font-size:0.70rem; color:var(--text-muted);">Env Vercel: <code>${p.env_var}</code></div>
                </div>
                <span class="badge ${p.configured ? 'badge-D' : 'badge-P'}" style="font-size:0.72rem;">
                    ${p.configured ? '✓ Configurato' : 'Non configurato'}
                </span>
            </div>
        `).join('');
    }

    document.getElementById('testAIResult').style.display = 'none';
    modal.classList.add('active');
}

function closeAIDiagnosticsModal() {
    const modal = document.getElementById('aiDiagnosticsModal');
    if (modal) modal.classList.remove('active');
}

async function testAIConnection() {
    const btn = document.getElementById('btnTestAI');
    const resBox = document.getElementById('testAIResult');
    if (btn) btn.disabled = true;
    if (resBox) {
        resBox.style.display = 'block';
        resBox.innerHTML = '<span style="color:var(--text-muted);">Ping live ai provider in corso...</span>';
    }

    const t0 = performance.now();
    try {
        const res = await fetch('/api/ai_test');
        const testData = await res.json();
        const latency = Math.round(performance.now() - t0);

        let details = '';
        if (testData.groq) {
            details += `<div>Groq: <b style="color:${testData.groq.ok ? 'var(--success)' : 'var(--danger)'};">${testData.groq.msg}</b></div>`;
        }
        if (testData.gemini) {
            details += `<div>Gemini: <b style="color:${testData.gemini.ok ? 'var(--success)' : 'var(--danger)'};">${testData.gemini.msg}</b></div>`;
        }

        if (resBox) {
            resBox.innerHTML = `
                <div style="background:var(--surface-solid); border:1px solid var(--border); border-radius:6px; padding:8px; text-align:left; font-size:0.75rem;">
                    <div style="font-weight:600; color:var(--text-main); margin-bottom:4px;">Esito Ping (${latency}ms):</div>
                    ${details}
                </div>
            `;
        }
        fetchAIStatus();
    } catch(e) {
        if (resBox) {
            resBox.innerHTML = `<span style="color:var(--danger); font-weight:700;">✕ Errore di chiamata: ${e.message}</span>`;
        }
    }
    if (btn) btn.disabled = false;
}

/* ─────────────────────────────────────────────────────────────
   LISTONE & ANALYTICS TAB
───────────────────────────────────────────────────────────── */
function renderListone() {
    const q = (document.getElementById('listSearch')?.value || '').toLowerCase();
    const activeBudget = leagueBudget || 1000;
    const sortBy = document.getElementById('listSortBy')?.value || 'best';

    const filtered = allPlayers.filter(p => {
        if (currentRoleFilter !== 'ALL' && p.role !== currentRoleFilter) return false;
        if (currentFasciaFilter !== 'ALL' && String(p.fascia) !== String(currentFasciaFilter)) return false;
        if (q && !p.player.toLowerCase().includes(q) && !p.team.toLowerCase().includes(q)) return false;
        return true;
    });

    // Sorting logic (Default: Miglior Giocatore come in Scala Slot)
    filtered.sort((a, b) => {
        if (sortBy === 'best') {
            const aScore = (parseFloat(a.score) || 0) * 12 + (parseFloat(a.vorp) || 0) * 2 + (a.is_starter_2627 ? 15 : 0) + (parseFloat(a.contrib_exp) || 0) * 0.1;
            const bScore = (parseFloat(b.score) || 0) * 12 + (parseFloat(b.vorp) || 0) * 2 + (b.is_starter_2627 ? 15 : 0) + (parseFloat(b.contrib_exp) || 0) * 0.1;
            return bScore - aScore;
        } else if (sortBy === 'mv_desc') {
            return (parseFloat(b.mv) || 0) - (parseFloat(a.mv) || 0);
        } else if (sortBy === 'mfv_desc') {
            return (parseFloat(b.mfv) || 0) - (parseFloat(a.mfv) || 0);
        } else if (sortBy === 'fair_desc') {
            const aFair = getPlayerFairPrice(a, activeBudget);
            const bFair = getPlayerFairPrice(b, activeBudget);
            return bFair - aFair;
        } else if (sortBy === 'fair_asc') {
            const aFair = getPlayerFairPrice(a, activeBudget);
            const bFair = getPlayerFairPrice(b, activeBudget);
            return aFair - bFair;
        } else if (sortBy === 'contrib_desc') {
            return (parseFloat(b.contrib_exp) || 0) - (parseFloat(a.contrib_exp) || 0);
        } else if (sortBy === 'vorp_desc') {
            return (parseFloat(b.vorp) || 0) - (parseFloat(a.vorp) || 0);
        } else if (sortBy === 'alpha') {
            return a.player.localeCompare(b.player);
        }
        return 0;
    });

    const container = document.getElementById('listoneContainer');
    if (!container) return;

    if (!allPlayers || allPlayers.length === 0) {
        container.innerHTML = '<div class="card" style="text-align:center; color:var(--text-muted); padding:24px;">Caricamento calciatori in corso...</div>';
        return;
    }

    if (filtered.length === 0) {
        container.innerHTML = '<div class="card" style="text-align:center; color:var(--text-muted); padding:24px;">Nessun calciatore trovato con i filtri selezionati.</div>';
        return;
    }

    container.innerHTML = filtered.map(p => {
        const fairLive = getPlayerFairPrice(p, activeBudget);

        const isStarter = p.is_starter_2627 === 1 || p.is_starter_2627 === true || p.is_starter_2627 === "1";
        const medDays = (p.medical && p.medical.days_lost_3y) || 0;
        const encPlayer = encodeURIComponent(p.player);
        const medBadge = medDays >= 120 
            ? `<span class="medical-badge medical-badge-danger" data-player="${encPlayer}" onclick="event.stopPropagation(); openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))" title="Finestra Medica: ${medDays} gg infortunio (3 anni)"><i class="fa-solid fa-heart-pulse icon-pulse"></i> ${medDays}gg</span>`
            : (medDays >= 30 
                ? `<span class="medical-badge medical-badge-warning" data-player="${encPlayer}" onclick="event.stopPropagation(); openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))" title="Finestra Medica: ${medDays} gg infortunio (3 anni)"><i class="fa-solid fa-triangle-exclamation"></i> ${medDays}gg</span>`
                : `<span class="medical-badge medical-badge-success" data-player="${encPlayer}" onclick="event.stopPropagation(); openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))" title="Finestra Medica: Integro (${medDays} gg infortunio)"><i class="fa-solid fa-circle-check"></i> Integro</span>`);

        return `
            <div class="player-row role-${p.role}">
                <div class="player-info">
                    <div class="player-name">
                        <span class="badge badge-${p.role}">${p.role}</span>
                        <a href="/player/${encPlayer}" style="font-weight:600; font-size:0.98rem; cursor:pointer; color:var(--text-main); text-decoration:none;"
                           onclick="event.preventDefault(); openPlayerDetailDrawer(decodeURIComponent('${encPlayer}'))"> ${p.player}</a>
                        <button data-player="${encPlayer}" onclick="openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))"
                            title="Dettaglio Giocatore" style="background:transparent; border:none; cursor:pointer; font-size:0.85rem; padding:0 3px; color:var(--primary); opacity:0.75; transition:opacity 0.2s;"
                            onmouseenter="this.style.opacity='1'" onmouseleave="this.style.opacity='0.75'"><i class="fa-solid fa-circle-info"></i></button>
                        <small style="color:var(--text-muted); font-weight:500;">(${p.team})</small>
                        ${medBadge}
                        ${isStarter ? `<span class="scout-tag-starter">✓ Titolare</span>` : ''}
                    </div>
                    <div class="player-meta" style="display:flex; align-items:center; flex-wrap:wrap; gap:6px 10px; margin-top:4px;">
                        <span style="background:rgba(255,255,255,0.06); color:var(--text-muted); padding:2px 7px; border-radius:6px; font-size:0.76rem; font-weight:500;">MV: <b style="color:var(--text-main);">${p.mv || '6.0'}</b></span>
                        <span style="background:rgba(255,255,255,0.06); color:var(--text-muted); padding:2px 7px; border-radius:6px; font-size:0.76rem; font-weight:500;">FM: <b style="color:var(--text-main);">${p.mfv || '6.0'}</b></span>
                        <span style="color:var(--text-muted); font-size:0.76rem; font-weight:500;">Bonus: <b style="color:var(--text-main);">${p.bonus_range || 'N/D'}</b></span>
                        <span class="scout-vorp-badge" style="font-size:0.74rem;">VORP +${p.vorp}</span>
                        <small style="color:var(--text-muted); font-size:0.72rem; margin-left:auto;">P50: <b>${p.contrib_exp}</b> (~${p.expected_matches || 28}p)</small>
                    </div>
                </div>
                <div class="player-stats">
                    <div class="scout-price-box">
                        <div class="player-fair" title="Prezzo Fair calcolato sul tuo budget di lega (${activeBudget} cr)">${fairLive} <span style="font-size:0.7rem; font-weight:700;">cr</span></div>
                    </div>
                    <div style="font-size:0.68rem; color:var(--text-muted); margin-top:2px;">
                        su ${activeBudget} cr
                    </div>
                    <div class="player-vorp" style="color:${p.surplus_value > 0 ? 'var(--success)' : 'var(--danger)'}">
                        ${p.surplus_value > 0 ? '+' : ''}${p.surplus_value} cr
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

window.onload = function () {
    init();
    if (typeof FantaTour !== 'undefined') {
        FantaTour.maybeAutoStart();
    }
};
