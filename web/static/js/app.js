let allPlayers = [];
let currentRoleFilter = 'ALL';
let currentFasciaFilter = 'ALL';

function maybeShowMaestroIntro(forceClose = false) {
    const overlay = document.getElementById('maestroIntroOverlay');
    if (!overlay) return;
    if (forceClose) {
        localStorage.setItem('fanta_maestro_intro_done', 'true');
        overlay.style.display = 'none';
        document.body.classList.remove('app-locked');
        return;
    }
    if (localStorage.getItem('fanta_maestro_intro_done') === 'true') return;
    overlay.style.display = 'flex';
    document.body.classList.add('app-locked');
}

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
        }, 400); // matches the 0.4s CSS transition above
    }, 1200);
}

window.MAESTRO_SPRITES = {
    neutral: [
        '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo.....','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
    ],
    greeting: [
        '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo..B..','.......oWWWWWWWWo..BB..','...RR..oWWWWWWWWo...B..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
    ],
    pointing: [
        '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWoBBB','...oWWWWWWWWWWWWWWWWo.B','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo.....','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
    ],
    thoughtful: [
        '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWooo....','......oWWWWWWWWWo......','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
    ]
};

const MAESTRO_PALETTE = {
    '.': null, o: '#241a12', H: '#4a3320', h: '#33230f', B: '#c69a4c', b: '#8a6329',
    L: '#f2c14e', G: '#8fd0c8', g: '#4f9a91', S: '#e6b184', s: '#c68b5c',
    W: '#efe9dc', w: '#c3bcaa', R: '#5c4326', r: '#3f2c15', C: '#b5703a'
};

function renderMaestroSprite(containerId, pose = 'neutral', scale = 3.2) {
    const host = document.getElementById(containerId);
    const map = window.MAESTRO_SPRITES[pose] || window.MAESTRO_SPRITES.neutral;
    if (!host || !map) return;
    const rows = map.length;
    const cols = map[0].length;
    let rects = '';
    map.forEach((row, y) => {
        row.split('').forEach((token, x) => {
            const fill = MAESTRO_PALETTE[token];
            if (!fill) return;
            rects += `<rect x="${x}" y="${y}" width="1.03" height="1.03" fill="${fill}" />`;
        });
    });
    host.innerHTML = `<svg viewBox="0 0 ${cols} ${rows}" width="${cols * scale}" height="${rows * scale}" shape-rendering="crispEdges" style="display:block">${rects}</svg>`;
}

let maestroCurrentPose = 'neutral';

function setMaestroPose(pose) {
    maestroCurrentPose = pose;
    renderMaestroSprite('maestroAmbientSprite', pose, 2.9);
    const introVisible = document.getElementById('maestroIntroOverlay');
    if (introVisible) renderMaestroSprite('maestroIntroSprite', pose === 'neutral' ? 'greeting' : pose, 4.6);
}

function ensureMaestroAmbient() {
    const el = document.getElementById('maestroAmbient');
    if (!el) return;
    el.style.display = 'flex';
    if (!document.getElementById('maestroAmbientSprite')?.innerHTML) {
        renderMaestroSprite('maestroAmbientSprite', maestroCurrentPose, 2.9);
    }
}

function updateMaestroAmbientState(tabId) {
    ensureMaestroAmbient();
    const bubble = document.getElementById('maestroAmbientBubble');
    const state = {
        draft: { pose: 'pointing', text: 'Segui il lotto: fair price e surplus sono la bussola.' },
        rosters: { pose: 'thoughtful', text: 'Ogni sigillo titolare resta modificabile con un tocco.' },
        listone: { pose: 'pointing', text: 'Occhio al surplus, giovane.' },
        ai: { pose: 'neutral', text: 'Qui gli esperimenti vanno letti con giudizio.' },
        lineup: { pose: 'thoughtful', text: 'Il solver resta separato: la vera lavagna è nelle Rose.' },
        audit: { pose: 'neutral', text: 'Una buona officina misura prima di giudicare.' },
        trades: { pose: 'greeting', text: 'Ogni scambio va pesato come un ingranaggio.' },
        targets: { pose: 'greeting', text: 'Fissa i tuoi obiettivi prima che il mercato corra.' }
    }[tabId] || { pose: 'neutral', text: "Bentornato nell'officina." };
    setMaestroPose(state.pose);
    if (bubble) bubble.textContent = state.text;
}

/* ─────────────────────────────────────────────────────────────
   TOAST NOTIFICATIONS
───────────────────────────────────────────────────────────── */
/* ─────────────────────────────────────────────────────────────
   PLAYER DETAIL DRAWER (Finestra Medica & Metriche Avanzate)
───────────────────────────────────────────────────────────── */
function openPlayerDetailDrawer(playerName) {
    const p = (typeof allPlayers !== 'undefined' ? allPlayers : []).find(x => x.player === playerName) ||
              (typeof allPlayers !== 'undefined' ? allPlayers : []).find(x => (x.player || '').trim().toLowerCase() === (playerName || '').trim().toLowerCase());
    if (!p) {
        console.warn('Player not found for detail drawer:', playerName);
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
    surpEl.style.color = surplus >= 0 ? '#22c55e' : '#ef4444';

    const flags = p.target_flags || '';
    document.getElementById('pdTargetFlags').textContent = flags ? `Fattori: ${flags.replace(/;/g, ' • ')}` : 'Nessun fattore correttivo applicato';
    const badgeEl = document.getElementById('pdClearingSourceBadge');
    if (flags.includes('asta_xlsx')) {
        badgeEl.textContent = 'Asta Reale (1000cr)';
        badgeEl.style.background = 'rgba(34,197,94,0.15)';
        badgeEl.style.color = '#22c55e';
    } else if (flags.includes('fantabot_golden')) {
        badgeEl.textContent = 'Aste Storiche (500cr)';
        badgeEl.style.background = 'rgba(99,102,241,0.15)';
        badgeEl.style.color = '#818cf8';
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
        ? '<span style="color:#ef4444;"><i class="fa-solid fa-triangle-exclamation icon-pulse" style="margin-right:3px;"></i> Sì</span>' 
        : '<span style="color:#22c55e;"><i class="fa-solid fa-circle-check" style="margin-right:3px;"></i> No</span>';

    const medBadge = document.getElementById('pdMedBadge');
    medBadge.innerHTML = (med.status_badge || '') + ' ' + (med.status_label || 'N/D');
    if (med.status === 'safe') { medBadge.style.background = 'rgba(34,197,94,0.15)'; medBadge.style.color = '#22c55e'; }
    else if (med.status === 'warning') { medBadge.style.background = 'rgba(234,179,8,0.15)'; medBadge.style.color = '#eab308'; }
    else { medBadge.style.background = 'rgba(239,68,68,0.15)'; medBadge.style.color = '#ef4444'; }

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
    deltaEl.style.color = deltaVal >= 0 ? '#22c55e' : '#ef4444';

    // Quantiles
    const q = p.quantiles || {};
    const p10 = q.floor_p10 || 0, p50 = q.expected_p50 || 0, p90 = q.ceiling_p90 || 0;
    document.getElementById('pdP10').textContent = p10.toFixed(0);
    document.getElementById('pdP50').textContent = p50.toFixed(0);
    document.getElementById('pdP90').textContent = p90.toFixed(0);
    document.getElementById('pdSpread').textContent = (q.spread || 0).toFixed(0);

    const profBadge = document.getElementById('pdProfileBadge');
    profBadge.innerHTML = q.profile_badge || '';
    if ((q.spread || 0) < 135) { profBadge.style.background = 'rgba(99,102,241,0.15)'; profBadge.style.color = '#818cf8'; }
    else { profBadge.style.background = 'rgba(245,158,11,0.15)'; profBadge.style.color = '#f59e0b'; }

    // Quantile visual bar
    const maxPts = Math.max(p90, 350);
    const barLeft = (p10 / maxPts) * 100;
    const barWidth = ((p90 - p10) / maxPts) * 100;
    const p50Pos = (p50 / maxPts) * 100;
    const qBar = document.getElementById('pdQuantileBar');
    qBar.style.left = barLeft + '%';
    qBar.style.width = barWidth + '%';
    qBar.style.background = 'linear-gradient(90deg, #ef4444 0%, var(--gold) 50%, #22c55e 100%)';
    qBar.style.opacity = '0.3';
    document.getElementById('pdQuantileP50Mark').style.left = p50Pos + '%';

    // Starter info
    const starterEl = document.getElementById('pdStarter');
    if (starterEl) {
        starterEl.innerHTML = p.is_starter_2627 
            ? '<span style="color:#22c55e;"><i class="fa-solid fa-circle-check" style="margin-right:3px;"></i> Sì</span>' 
            : '<span style="color:#ef4444;"><i class="fa-solid fa-circle-xmark" style="margin-right:3px;"></i> No</span>';
    }
    document.getElementById('pdStarts').textContent = p.starts_2627 || 0;
    document.getElementById('pdMinutes').textContent = (p.minutes_2627 || 0).toLocaleString();

    // Show drawer with slide animation
    const drawer = document.getElementById('playerDetailDrawer');
    if (drawer) {
        drawer.style.display = 'flex';
        drawer.classList.add('active');
        requestAnimationFrame(() => {
            const panel = document.getElementById('playerDetailPanel');
            if (panel) panel.style.right = '0px';
        });
    }
}

function closePlayerDetailDrawer() {
    const panel = document.getElementById('playerDetailPanel');
    if (panel) panel.style.right = '-480px';
    setTimeout(() => {
        const drawer = document.getElementById('playerDetailDrawer');
        if (drawer) {
            drawer.style.display = 'none';
            drawer.classList.remove('active');
        }
    }, 350);
    _currentDetailPlayer = null;
}

// Close drawer on backdrop click
const _detailDrawerEl = document.getElementById('playerDetailDrawer');
if (_detailDrawerEl) {
    _detailDrawerEl.addEventListener('click', function(e) {
        if (e.target === this) closePlayerDetailDrawer();
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
    renderListone();

    ensureMaestroAmbient();
    updateMaestroAmbientState('listone');

    runBootSplash(() => maybeShowMaestroIntro());

    if (window.location.hash) {
        const tabName = window.location.hash.replace('#', '');
        if (['ai', 'listone'].includes(tabName)) {
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

    if (typeof updateMaestroAmbientState === 'function') updateMaestroAmbientState(tabId);

    // Close mobile drawer if open
    const sb = document.getElementById('appSidebar');
    const bd = document.getElementById('sidebarBackdrop');
    if (sb && sb.classList.contains('open')) {
        sb.classList.remove('open');
        bd.classList.remove('show');
    }

    if (tabId === 'listone') renderListone();
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
const AI_AVATAR_HTML = `<div class="chat-msg-avatar" style="width:32px; height:32px; border-radius:50%; background:linear-gradient(135deg, #0284c7, #4f46e5); display:flex; align-items:center; justify-content:center; flex-shrink:0; border:1.5px solid var(--primary);"><svg style="width:16px; height:16px; stroke:#ffffff; fill:none; stroke-width:2;" viewBox="0 0 24 24"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg></div>`;

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
                Come posso aiutarti? Chiedimi confronti tra giocatori, diagnosi sul tuo bilancio o scommesse per completare la rosa!
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
            Sto analizzando i dati del listone, VORP e formazioni reali...
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
                tableHtml += '<thead><tr style="border-bottom:1.5px solid var(--border); background:rgba(255,45,117,0.12); color:var(--text-main);">';
                cells.forEach(c => { tableHtml += `<th style="padding:6px 8px; font-weight:800;">${c}</th>`; });
                tableHtml += '</tr></thead><tbody>';
            } else {
                tableHtml += '<tr style="border-bottom:1px solid rgba(255,255,255,0.06);">';
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
    formatted = formatted.replace(/\\*\\*(.*?)\\*\\*/g, '<b style="color:var(--text-main);">$1</b>');
    formatted = formatted.replace(/\\*(.*?)\\*/g, '<i style="color:var(--text-muted);">$1</i>');
    // Bullet Points
    formatted = formatted.replace(/^\\s*-\\s+(.*$)/gim, '<div style="display:flex; gap:6px; margin-bottom:3px;"><span style="color:var(--primary);">&bull;</span><span>$1</span></div>');
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
                    <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:6px; background:#0b111e; padding:8px 10px; border-radius:8px; margin-bottom:10px; font-size:0.82rem;">
                        <div>Crediti Residui: <b style="color:var(--gold);">${s.remaining || 0} cr</b></div>
                        <div>Max Rilancio: <b style="color:var(--danger);">${s.max_bid || 0} cr</b></div>
                        <div>Slot Liberi: <b>${free.total || 0}</b> (P:${free.P || 0} D:${free.D || 0} C:${free.C || 0} A:${free.A || 0})</div>
                        <div>Media cr/slot: <b>${s.avg_per_slot || 0} cr</b></div>
                    </div>
                    <div style="margin-bottom:8px;">
                        ${(data.advice || []).map(a => `<div style="margin-bottom:4px; font-size:0.85rem;">&bull; ${a}</div>`).join('')}
                    </div>
                    <div style="background:rgba(56,189,248,0.08); border-left:3px solid var(--primary); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
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
                    <div style="font-weight:800; font-size:1rem; color:var(--primary); margin-bottom:10px;">${data.title || 'Confronto'}</div>
                    <div style="display:grid; grid-template-columns:${players.length > 2 ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)'}; gap:8px; margin-bottom:10px;">
                        ${players.map(p => `
                            <div style="background:#0b111e; padding:10px 8px; border-radius:8px; border:1px solid var(--border); font-size:0.82rem;">
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
                    <div style="background:rgba(56,189,248,0.08); border-left:3px solid var(--primary); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
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
                    <div style="font-weight:800; font-size:1.02rem; color:var(--gold); margin-bottom:8px;">${data.title}</div>
                    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; text-align:center; margin-bottom:10px;">
                        <div style="background:#0b111e; padding:8px; border-radius:6px; border:1px solid var(--border);">
                            <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">PROIEZIONE P50</div>
                            <div style="font-size:1.1rem; font-weight:800; color:var(--primary);">${p.contrib_exp || 0}</div>
                        </div>
                        <div style="background:#0b111e; padding:8px; border-radius:6px; border:1px solid var(--border);">
                            <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">FAIR PRICE 1000</div>
                            <div style="font-size:1.1rem; font-weight:800; color:var(--gold);">${p.fair_1000 || 1} cr</div>
                        </div>
                        <div style="background:#0b111e; padding:8px; border-radius:6px; border:1px solid var(--border);">
                            <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">TITOLARITÀ REALE</div>
                            <div style="font-size:1.1rem; font-weight:800; color:var(--success);">${p.starts || 0} start</div>
                        </div>
                    </div>
                    <div style="background:rgba(56,189,248,0.08); border-left:3px solid var(--gold); padding:8px 10px; border-radius:4px; font-size:0.85rem; margin-bottom:8px;">
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
                    <div style="font-weight:800; font-size:1rem; color:var(--success); margin-bottom:8px;">${data.title}</div>
                    <div style="margin-bottom:10px;">
                        ${players.map(p => `
                            <div class="candidate-mini-row" style="display:flex; justify-content:space-between; align-items:center; padding:6px 8px; margin-bottom:4px; background:#0b111e; border-radius:6px; border:1px solid var(--border);">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span class="badge badge-${p.role}">${p.role}</span>
                                    <b>${p.name}</b> <small style="color:var(--text-muted);">(${p.team})</small>
                                </div>
                                <div style="text-align:right;">
                                    <span style="color:var(--gold); font-weight:800; font-size:0.95rem;">${p.fair_1000} cr</span>
                                    <span style="color:var(--primary); font-size:0.78rem; margin-left:6px;">+${p.vorp} vorp</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    <div style="background:rgba(16,185,129,0.08); border-left:3px solid var(--success); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
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
            <div style="background:#0b111e; border:1px solid var(--border); border-radius:6px; padding:8px 10px; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-weight:700; font-size:0.82rem; color:var(--text-main);">${p.name}</div>
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
                <div style="background:#090d16; border:1px solid var(--border); border-radius:6px; padding:8px; text-align:left; font-size:0.75rem;">
                    <div style="font-weight:800; color:var(--text-main); margin-bottom:4px;">Esito Ping (${latency}ms):</div>
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
                        <span style="font-family:'Outfit',sans-serif; font-weight:700; font-size:1.05rem; cursor:pointer;" data-player="${encPlayer}" onclick="openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))"> ${p.player}</span>
                        <button data-player="${encPlayer}" onclick="openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))"
                            title="Dettaglio Giocatore" style="background:transparent; border:none; cursor:pointer; font-size:0.85rem; padding:0 3px; color:var(--primary); opacity:0.75; transition:opacity 0.2s;"
                            onmouseenter="this.style.opacity='1'" onmouseleave="this.style.opacity='0.75'"><i class="fa-solid fa-circle-info"></i></button>
                        <small style="color:var(--text-muted); font-weight:600;">(${p.team})</small>
                        ${medBadge}
                        ${isStarter ? `<span class="scout-tag-starter">✓ Titolare</span>` : ''}
                    </div>
                    <div class="player-meta" style="display:flex; align-items:center; flex-wrap:wrap; gap:6px 10px; margin-top:4px;">
                        <span style="background:rgba(56,189,248,0.12); color:#38bdf8; padding:2px 7px; border-radius:5px; font-size:0.78rem; font-weight:700;">MV: <b>${p.mv || '6.0'}</b></span>
                        <span style="background:rgba(16,185,129,0.12); color:#34d399; padding:2px 7px; border-radius:5px; font-size:0.78rem; font-weight:700;">FM: <b>${p.mfv || '6.0'}</b></span>
                        <span style="color:var(--text-main); font-size:0.78rem; font-weight:600;"><span style="color:var(--gold); font-weight:700;">Bonus:</span> ${p.bonus_range || 'N/D'}</span>
                        <span class="scout-vorp-badge" style="font-size:0.75rem;">VORP +${p.vorp}</span>
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
