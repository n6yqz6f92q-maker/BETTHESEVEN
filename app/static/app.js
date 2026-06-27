/**
 * Seven Bet — Frontend Application (Open Access)
 * Peer-to-peer betting. Join for free. Gold Upgrades for reduced commission.
 * All links: bettheseven.com
 */

// ── State ────────────────────────────────────────────────────────
let currentUser = localStorage.getItem('sevenbet_username') || '';

// ── DOM Cache ────────────────────────────────────────────────────
const $ = (s, p) => (p || document).querySelector(s);
const $$ = (s, p) => [...(p || document).querySelectorAll(s)];

// ── API Helper ───────────────────────────────────────────────────
async function api(path, options = {}) {
    const url = `/api${path}`;
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    return data;
}

// ── Toast ────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, type = 'info') {
    const el = $('#toast');
    clearTimeout(toastTimer);
    el.textContent = msg;
    el.className = `toast show ${type}`;
    toastTimer = setTimeout(() => el.classList.remove('show'), 3500);
}

// ── User Setup ───────────────────────────────────────────────────
function updateUserUI() {
    const input = $('#usernameInput');
    const btn = $('#registerBtn');
    if (currentUser) {
        input.value = currentUser;
        input.style.borderColor = '#2ecc71';
        btn.textContent = '✓ ' + currentUser;
    } else {
        input.style.borderColor = '';
        btn.textContent = 'Join Free';
    }
}

async function ensureUser() {
    if (!currentUser) throw new Error('Please enter a username first');
    try {
        await api('/users', { method: 'POST', body: JSON.stringify({ username: currentUser }) });
    } catch (e) {
        if (!e.message.includes('already exists')) throw e;
    }
}

function setUser(name) {
    currentUser = name;
    localStorage.setItem('sevenbet_username', name);
    updateUserUI();
    // Also fill create form username
    const cu = $('#createUsername');
    if (cu) cu.value = name;
    // Reload user-bound sections
    if ($('#page-user.active')) loadUserDetail(window.location.pathname.split('/')[2]);
    if ($('#page-gold-upgrade.active')) loadGoldUpgrade();
}

$('#registerBtn').addEventListener('click', async () => {
    const name = $('#usernameInput').value.trim();
    if (!name) { showToast('Enter a username', 'error'); return; }
    setUser(name);
    try {
        await ensureUser();
        showToast(`Welcome, ${name}!`, 'success');
        if (window.location.pathname === '/' || window.location.pathname === '') {
            await loadStats();
            await loadBets();
        }
    } catch (e) { showToast(e.message, 'error'); }
});

$('#usernameInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') $('#registerBtn').click();
});

$('#heroJoinBtn')?.addEventListener('click', () => {
    $('#usernameInput').focus();
    showToast('Enter a username and click Join Free!', 'info');
});

// ── Navigation ───────────────────────────────────────────────────
function showPage(pageId) {
    $$('.page').forEach(p => p.classList.remove('active'));
    const page = $(`#page-${pageId}`);
    if (page) page.classList.add('active');
    $$('.nav-link').forEach(l => l.classList.remove('active'));
    const link = $(`.nav-link[data-page="${pageId}"]`);
    if (link) link.classList.add('active');
}

function navigate(path) {
    window.history.pushState({}, '', path);
    handleRoute();
}

window.addEventListener('popstate', handleRoute);

function handleRoute() {
    const path = window.location.pathname;
    if (path === '/' || path === '') {
        showPage('home');
        loadStats();
        loadBets();
    } else if (path === '/create') {
        showPage('create');
        // Pre-fill username field
        const cu = $('#createUsername');
        if (cu && currentUser) cu.value = currentUser;
    } else if (path === '/leaderboard') {
        showPage('leaderboard');
        loadLeaderboard();
    } else if (path === '/gold-upgrade' || path === '/founders-pass') {
        showPage('gold-upgrade');
        loadGoldUpgrade();
    } else if (path.startsWith('/bet/')) {
        const id = path.split('/')[2];
        showPage('bet-detail');
        loadBetDetail(id);
    } else if (path.startsWith('/user/')) {
        const id = path.split('/')[2];
        showPage('user');
        loadUserDetail(id);
    }
}

$$('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        navigate(e.target.getAttribute('href'));
    });
});

// ── Stats ────────────────────────────────────────────────────────
async function loadStats() {
    try {
        const stats = await api('/platform/stats');
        $('#statHandle').textContent = '$' + fmt(stats.total_handle);
        $('#statRake').textContent = '$' + fmt(stats.rake_collected);
        $('#statActive').textContent = stats.active_bets;
        $('#statSettled').textContent = stats.settled_bets;
    } catch (e) { /* silent */ }
}

// ── Bets — Listing ───────────────────────────────────────────────
let allBets = [];
let currentFilter = 'all';

async function loadBets() {
    try {
        allBets = await api('/bets');
        renderBets();
    } catch (e) {
        $('#betsList').innerHTML = '<p class="muted">Failed to load bets: ' + esc(e.message) + '</p>';
    }
}

function renderBets() {
    const filtered = currentFilter === 'all' ? allBets : allBets.filter(b => b.status === currentFilter);
    if (filtered.length === 0) {
        $('#betsList').innerHTML = '<p class="muted">No bets found. Create one!</p>';
        return;
    }
    $('#betsList').innerHTML = filtered.map(bet => `
        <div class="bet-card" onclick="navigate('/bet/${bet.id}')">
            <div class="bet-title">${esc(bet.title)}</div>
            <div class="bet-meta">
                <span>💰 $${fmt(bet.stake)}</span>
                <span>👤 ${bet.max_participants} max</span>
                <span>📅 ${new Date(bet.created_at).toLocaleDateString()}</span>
            </div>
            <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center">
                <span class="bet-status status-${bet.status}">${bet.status}</span>
            </div>
        </div>
    `).join('');
}

$$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        $$('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderBets();
    });
});

// ── Bets — Create ────────────────────────────────────────────────
$('#createBetForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = ($('#createUsername').value || $('#usernameInput').value).trim();
    const title = $('#betTitle').value.trim();
    const stake = parseFloat($('#betStake').value);
    const maxP = parseInt($('#betMaxParticipants').value);
    if (!username) { showToast('Enter a username', 'error'); return; }
    if (!title) { showToast('Enter a bet title', 'error'); return; }
    if (!stake || stake <= 0) { showToast('Enter a valid stake', 'error'); return; }
    // Ensure the user is registered and current
    currentUser = username;
    localStorage.setItem('sevenbet_username', username);
    updateUserUI();
    try {
        await ensureUser();
        await api('/bets', { method: 'POST', body: JSON.stringify({ username: currentUser, title, stake, max_participants: maxP }) });
        showToast('Bet created! 🎉', 'success');
        $('#betTitle').value = '';
        $('#betStake').value = '';
        navigate('/');
    } catch (e) { showToast(e.message, 'error'); $('#createError').textContent = e.message; }
});

// ── Bet Detail ───────────────────────────────────────────────────
async function loadBetDetail(id) {
    try {
        const bet = await api(`/bets/${id}`);
        const participants = bet.participants || [];
        const isCreator = currentUser && participants.some(p => p.username === currentUser && p.id === bet.creator_id);
        const isParticipant = currentUser && participants.some(p => p.username === currentUser);
        const canJoin = bet.status === 'open' && currentUser && !isParticipant && participants.length < bet.max_participants;
        const canSettle = bet.status === 'accepted' && currentUser && isCreator;
        const canCancel = (bet.status === 'open' || bet.status === 'accepted') && currentUser && isCreator;

        // Commission breakdown — check if any participant has Gold status
        const totalPot = bet.stake * participants.length;
        // Default 7% — if settled, we'll show actual rate if available
        let effectiveRate = 0.07;
        let commission = totalPot * effectiveRate;
        let winnerPayout = totalPot - commission;

        // If this bet is already settled, fetch settlement details if possible
        const displayRate = bet.rake_rate || 0.07;
        const displayRake = totalPot * displayRate;
        const displayPayout = totalPot - displayRake;

        // Check current user's gold status for display
        let myGoldStatus = null;
        if (currentUser) {
            try {
                const gp = await api('/founders-pass/my-pass-by-username?username=' + encodeURIComponent(currentUser));
                myGoldStatus = gp.pass;
            } catch(e) {}
        }

        $('#betDetail').innerHTML = `
            <div class="detail-card" style="margin-bottom:16px">
                <h2>${esc(bet.title)}</h2>
                <div class="gold-divider"></div>
                <div class="detail-grid">
                    <div class="detail-row"><span class="detail-label">Status</span><span class="bet-status status-${bet.status}">${bet.status}</span></div>
                    <div class="detail-row"><span class="detail-label">Stake per person</span><span class="detail-value">$${fmt(bet.stake)}</span></div>
                    <div class="detail-row"><span class="detail-label">Max Participants</span><span class="detail-value">${bet.max_participants}</span></div>
                    <div class="detail-row"><span class="detail-label">Participants</span><span class="detail-value">${participants.length} / ${bet.max_participants}</span></div>
                    ${bet.settled_at ? `<div class="detail-row"><span class="detail-label">Settled</span><span class="detail-value">${new Date(bet.settled_at).toLocaleString()}</span></div>` : ''}
                    <div class="detail-row"><span class="detail-label">Created</span><span class="detail-value">${new Date(bet.created_at).toLocaleString()}</span></div>
                </div>
            </div>

            ${participants.length > 1 ? `
            <div class="detail-card" style="margin-bottom:16px">
                <h3 style="font-size:0.85rem;margin-bottom:12px;letter-spacing:0.1em">COMMISSION BREAKDOWN</h3>
                <div class="detail-grid">
                    <div class="detail-row">
                        <span class="detail-label">Total Pot</span>
                        <span class="detail-value" style="font-size:1.1rem">$${fmt(totalPot)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Seven Bet Fee (${(displayRate*100).toFixed(0)}%)</span>
                        <span class="detail-value" style="color:var(--color-primary)">− $${fmt(displayRake)}</span>
                    </div>
                    <div class="gold-divider" style="margin:4px 0"></div>
                    <div class="detail-row">
                        <span class="detail-label" style="font-weight:700">Winner Payout</span>
                        <span class="detail-value" style="font-size:1.1rem;font-weight:700;color:var(--color-success)">$${fmt(displayPayout)}</span>
                    </div>
                </div>
                <div style="font-size:0.75rem;color:var(--color-text-muted);margin-top:12px;padding-top:12px;border-top:1px solid var(--color-border);text-align:center">
                    <strong>Winner gets $${fmt(displayPayout)}</strong> — ${participants.length-1} other participant(s) lose $${fmt(bet.stake)} each.
                    ${displayRate < 0.07 ? `<br>🏆 <span style="color:var(--color-primary)">Winner has a Gold Upgrade — reduced ${(displayRate*100).toFixed(0)}% commission applied!</span>` : ''}
                </div>
            </div>` : ''}

            ${myGoldStatus ? `
            <div class="detail-card" style="margin-bottom:16px;border-color:var(--color-primary)">
                <div style="display:flex;align-items:center;gap:12px">
                    <span style="font-size:1.5rem">👑</span>
                    <div>
                        <strong style="color:var(--color-primary)">Gold Upgrade Active</strong>
                        <p style="color:var(--text-muted);font-size:0.8rem">${esc(myGoldStatus.tier.replace('_',' '))} — ${(myGoldStatus.commission_discount*100).toFixed(0)}% lifetime commission</p>
                    </div>
                </div>
            </div>` : ''}

            <div class="detail-card" style="margin-bottom:16px">
                <div class="participants-list">
                    <h3>Participants (${participants.length})</h3>
                    ${participants.map(p => `<span class="participant-chip ${p.id === bet.winner_id ? 'winner' : ''}" onclick="navigate('/user/${p.id}')" style="cursor:pointer">${p.id === bet.creator_id ? '👑 ' : ''}${esc(p.username || p.id.substring(0,8))}${p.id === bet.winner_id ? ' 🏆' : ''}</span>`).join('')}
                    ${participants.length === 0 ? '<p class="muted">No participants yet</p>' : ''}
                </div>
            </div>

            <div class="detail-card">
                <div class="detail-actions">
                    ${canJoin ? `<button class="btn btn-primary btn-lg" onclick="joinBet('${id}')" style="flex:1">Join Bet — Pay $${fmt(bet.stake)}</button>` : ''}
                    ${canSettle ? `<div style="display:flex;gap:8px;align-items:center;width:100%"><label style="font-size:0.75rem;color:var(--color-text-muted)">Winner:</label><select id="winnerSelect" class="input-sm" style="width:auto;flex:1">${participants.filter(p => p.id !== bet.creator_id).map(p => `<option value="${esc(p.username || p.id)}">${esc(p.username || p.id.substring(0,8))}</option>`).join('')}</select><button class="btn btn-success btn-lg" onclick="settleBet('${id}')">🏆 Settle</button></div>` : ''}
                    ${canCancel ? `<button class="btn btn-danger" onclick="cancelBet('${id}')">Cancel & Refund All</button>` : ''}
                </div>
                <p id="betActionError" class="error-msg"></p>
            </div>`;
    } catch (e) {
        $('#betDetail').innerHTML = `<p class="muted">Error: ${e.message}</p>`;
    }
}

async function joinBet(id) {
    try {
        await ensureUser();
        await api(`/bets/${id}/join`, { method: 'POST', body: JSON.stringify({ username: currentUser }) });
        showToast('Joined bet! 🎲', 'success');
        await loadBetDetail(id); await loadBets(); await loadStats();
    } catch (e) { showToast(e.message, 'error'); $('#betActionError').textContent = e.message; }
}

async function settleBet(id) {
    const sel = $('#winnerSelect');
    if (!sel) return;
    try {
        await ensureUser();
        await api(`/bets/${id}/settle`, { method: 'POST', body: JSON.stringify({ winner_username: sel.value }) });
        showToast(`Bet settled! ${sel.value} wins 🏆`, 'success');
        await loadBetDetail(id); await loadBets(); await loadStats();
    } catch (e) { showToast(e.message, 'error'); $('#betActionError').textContent = e.message; }
}

async function cancelBet(id) {
    if (!confirm('Cancel this bet and refund all participants?')) return;
    try {
        await ensureUser();
        await api(`/bets/${id}/cancel`, { method: 'POST' });
        showToast('Bet cancelled, stakes refunded', 'success');
        await loadBetDetail(id); await loadBets(); await loadStats();
    } catch (e) { showToast(e.message, 'error'); $('#betActionError').textContent = e.message; }
}

// ── User Detail ───────────────────────────────────────────────────
async function loadUserDetail(id) {
    try {
        const user = await api(`/users/${id}`);
        const bets = await api(`/users/${id}/bets`);
        const txs = await api(`/users/${id}/transactions`);

        // Check gold status for this user
        let goldPass = null;
        let goldHtml = '';
        try {
            const gp = await api('/founders-pass/my-pass?user_id=' + id);
            goldPass = gp.pass;
        } catch(e) {}

        if (goldPass) {
            goldHtml = `
                <div class="detail-card" style="margin-bottom:16px;border-color:var(--color-primary);text-align:center">
                    <div style="font-size:2rem;margin-bottom:4px">👑</div>
                    <h3 style="color:var(--color-primary);font-size:1rem">Gold Upgrade Active</h3>
                    <p style="color:var(--text-muted);font-size:0.85rem">${esc(goldPass.tier.replace('_',' '))} — #${goldPass.founder_number}</p>
                    <p style="color:var(--accent);font-size:0.85rem">${(goldPass.commission_discount*100).toFixed(0)}% lifetime commission</p>
                </div>
            `;
        } else if (currentUser && (await api('/users/' + id)).username === currentUser) {
            // Show buy links if this is the current user viewing their own profile
            goldHtml = `
                <div class="detail-card" style="margin-bottom:16px;text-align:center">
                    <h3 style="font-size:0.9rem;margin-bottom:12px">⬆ Upgrade to Gold</h3>
                    <p style="color:var(--text-muted);font-size:0.8rem;margin-bottom:12px">Save on commission with a Gold Upgrade — rates as low as 3%.</p>
                    <a href="/gold-upgrade" class="btn btn-primary" onclick="navigate('/gold-upgrade');return false">View Gold Tiers →</a>
                </div>
            `;
        }

        $('#userDetail').innerHTML = `
            ${goldHtml}
            <div class="user-card"><h2>👤 ${esc(user.username)}</h2><div class="user-balance">Balance: $${fmt(user.balance)}</div><p style="color:var(--text-muted);font-size:0.85rem;margin-top:4px">Joined ${new Date(user.created_at).toLocaleDateString()}</p></div>
            <h3 style="margin-bottom:10px;font-size:1rem">Bets (${bets.length})</h3>
            <div class="bets-grid" style="margin-bottom:24px">${bets.length === 0 ? '<p class="muted">No bets yet</p>' : bets.map(b => `<div class="bet-card" onclick="navigate('/bet/${b.id}')" style="cursor:pointer"><div class="bet-title">${esc(b.title)}</div><div class="bet-meta"><span>💰 $${fmt(b.stake)}</span><span class="bet-status status-${b.status}">${b.status}</span></div></div>`).join('')}</div>
            <h3 style="margin-bottom:10px;font-size:1rem">Transactions (${txs.length})</h3>
            <table class="leaderboard-table"><thead><tr><th>Type</th><th>Amount</th><th>Date</th></tr></thead><tbody>${txs.length === 0 ? '<tr><td colspan="3" class="muted">No transactions</td></tr>' : txs.map(t => `<tr><td><span class="bet-status">${t.type}</span></td><td style="color:${t.amount > 0 ? 'var(--success)' : 'var(--danger)'}">${t.amount > 0 ? '+' : ''}$${fmt(t.amount)}</td><td style="color:var(--text-muted)">${new Date(t.created_at).toLocaleString()}</td></tr>`).join('')}</tbody></table>`;
    } catch (e) { $('#userDetail').innerHTML = `<p class="muted">Error: ${e.message}</p>`; }
}

// ── Leaderboard ──────────────────────────────────────────────────
async function loadLeaderboard() {
    try {
        const entries = await api('/platform/leaderboard');
        $('#leaderboardContent').innerHTML = `<table class="leaderboard-table"><thead><tr><th>Rank</th><th>User</th><th>Total Staked</th><th>Total Won</th></tr></thead><tbody>${entries.length === 0 ? '<tr><td colspan="4" class="muted">No activity yet</td></tr>' : entries.map((e, i) => `<tr onclick="navigate('/user/${e.id}')" style="cursor:pointer"><td><span class="rank-badge rank-${i < 3 ? i+1 : ''}">${i+1}</span></td><td><strong>${esc(e.username)}</strong></td><td>$${fmt(e.total_staked)}</td><td style="color:var(--success)">+$${fmt(e.total_won)}</td></tr>`).join('')}</tbody></table>`;
    } catch (e) { $('#leaderboardContent').innerHTML = `<p class="muted">Error: ${e.message}</p>`; }
}

// ── Helpers ──────────────────────────────────────────────────────
function fmt(n) { return parseFloat(n || 0).toFixed(2); }
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ── Init ─────────────────────────────────────────────────────────
updateUserUI();
handleRoute();// ── Gold Upgrade Page — renamed from Founder's Pass ──────────
async function loadGoldUpgrade() {
    try {
        const avail = await api('/founders-pass/availability');
        let myPass = null;
        if (currentUser) {
            try {
                const resp = await api('/founders-pass/my-pass-by-username?username=' + encodeURIComponent(currentUser));
                myPass = resp.pass;
            } catch(e) {}
        }

        const tiers = Object.entries(avail);
        const totalSold = tiers.reduce((s, [,t]) => s + t.sold, 0);
        const totalSupply = tiers.reduce((s, [,t]) => s + t.total, 0);
        const totalRemaining = totalSupply - totalSold;
        const pctSold = totalSupply > 0 ? (totalSold / totalSupply * 100).toFixed(0) : '0';

        if (myPass) {
            $('#goldUpgradeContent').innerHTML = `
                <div class="detail-card" style="text-align:center;margin:24px 0;border-color:var(--color-primary)">
                    <div style="font-size:2.5rem;margin-bottom:8px">👑</div>
                    <h2>You're Gold Member #${myPass.founder_number}!</h2>
                    <p style="color:var(--text-muted);margin:8px 0">Tier: ${esc(myPass.tier.replace('_',' '))} — Commission: ${(myPass.commission_discount*100).toFixed(0)}% lifetime</p>
                    <p style="font-size:0.85rem;color:var(--accent)">Your Gold Upgrade is active and linked to your account.</p>
                </div>
            `;
        }

        let html = `
        <div class="hero" style="padding:32px 0;text-align:center">
            <div style="font-size:3rem;margin-bottom:8px">👑</div>
            <h1 style="font-size:2rem;max-width:600px;margin:0 auto">GOLD UPGRADE</h1>
            <p class="subtitle" style="font-size:1.1rem;margin-top:8px">Lower your commission. Permanently.</p>
            <p style="color:var(--accent);font-size:0.9rem;margin-top:4px">Start with 7% free. Upgrade for rates as low as 3%.</p>

            <div style="max-width:500px;margin:24px auto;background:var(--surface);border-radius:var(--radius);padding:20px;border:1px solid var(--border)">
                <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:6px">
                    <span style="float:left">${totalSold} / ${totalSupply} SOLD</span>
                    <span style="float:right">⚡ Only ${totalRemaining} remaining</span>
                </div>
                <div style="background:var(--surface2);border-radius:10px;height:12px;overflow:hidden;clear:both">
                    <div style="background:linear-gradient(90deg,var(--primary),var(--accent));height:100%;width:${pctSold}%"></div>
                </div>
            </div>

            <div style="margin-top:16px;display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
                <a href="#tiers" class="btn btn-primary btn-lg">Upgrade Now →</a>
                <a href="#roi" class="btn btn-outline btn-lg">Compare Tiers →</a>
            </div>

            <div style="margin-top:12px;font-size:0.75rem;color:var(--text-muted);display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
                <span>✅ 18+ Only</span><span>✅ 14-Day Refund</span><span>✅ UK Company</span><span>✅ Stripe Secure</span><span>✅ LifeLocked Rate</span>
            </div>
        </div>

        <!-- How it Works -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:32px 0">
            <div class="detail-card">
                <h3 style="color:var(--success);margin-bottom:8px">Free to Start</h3>
                <p style="color:var(--text-muted);font-size:0.9rem">Sign up for free and bet immediately with our standard 7% commission. No deposit needed, no paywall. You're in control.</p>
                <p style="color:var(--text-muted);font-size:0.9rem;margin-top:8px">Earn while you bet. Every wager counts toward your volume.</p>
            </div>
            <div class="detail-card">
                <h3 style="color:var(--primary);margin-bottom:8px">Gold Saves You Money</h3>
                <p style="color:var(--text-muted);font-size:0.9rem">Premium Gold members pay just 5% commission. Founding Patrons pay 4%. The Seven pay 3%. Your rate is locked for life.</p>
                <p style="color:var(--text-muted);font-size:0.9rem;margin-top:8px">If you bet more than £5,000/month, a Gold Upgrade pays for itself in months.</p>
            </div>
        </div>

        <!-- ROI Calculator -->
        <div style="margin:32px 0;text-align:center" id="roi">
            <h2>Your Upgrade Is an Investment</h2>
            <p style="color:var(--text-muted);margin-bottom:16px">See how fast your Gold Upgrade pays for itself.</p>

            <div class="detail-card" style="max-width:800px;margin:0 auto;text-align:left">
                <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;flex-wrap:wrap">
                    <label style="font-weight:600;color:var(--text-muted)">My monthly betting volume:</label>
                    <div style="display:flex;align-items:center;gap:8px;flex:1;min-width:200px">
                        <span style="font-size:1.2rem;font-weight:700">$</span>
                        <input type="range" id="roiSlider" min="5000" max="100000" step="5000" value="10000"
                               style="flex:1;accent-color:var(--primary)">
                        <span id="roiSliderValue" style="background:var(--surface2);padding:4px 14px;border-radius:var(--radius-sm);font-weight:700;font-size:1.05rem;min-width:80px;text-align:right">10,000</span>
                    </div>
                </div>

                <div style="overflow-x:auto">
                    <table class="leaderboard-table" style="width:100%">
                        <thead><tr>
                            <th>Tier</th><th>Price</th><th>Rate</th><th>Savings/Month</th><th>Break-Even</th><th>Yr 1 Net</th>
                        </tr></thead>
                        <tbody id="roiTableBody"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tier Comparison -->
        <div style="margin:32px 0;text-align:center" id="tiers">
            <h2>Choose Your Gold Tier</h2>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-top:20px">
                ${tiers.map(([key, tier]) => renderGoldTierCard(key, tier)).join('')}
            </div>
        </div>
        `;

        html += renderGoldSevenPitch();
        html += renderGoldScarcity(totalSold, totalSupply, totalRemaining, pctSold);
        html += renderGoldFAQ();
        html += renderGoldFooter();

        $('#goldUpgradeContent').innerHTML = html;

        // Init ROI calculator
        updateGoldROI(10000);
        $('#roiSlider').addEventListener('input', function() {
            const val = parseInt(this.value);
            $('#roiSliderValue').textContent = val.toLocaleString();
            updateGoldROI(val);
        });

    } catch (e) {
        $('#goldUpgradeContent').innerHTML = '<p class="muted">Error: ' + esc(e.message) + '</p>';
    }
}

async function updateGoldROI(monthlyVolume) {
    try {
        const resp = await api('/founders-pass/calculate-roi?monthly_volume=' + monthlyVolume);
        const results = resp.results;
        $('#roiTableBody').innerHTML = results.map(r => `
            <tr>
                <td><strong>${esc(r.name)}</strong></td>
                <td>$${fmt(r.price)}</td>
                <td>${r.rate*100}%</td>
                <td style="color:${r.savings_per_month > 0 ? 'var(--success)' : 'var(--text-muted)'}">
                    ${r.savings_per_month > 0 ? '+$' + fmt(r.savings_per_month) : '—'}
                </td>
                <td>${r.months_to_breakeven ? r.months_to_breakeven + 'mo' : '—'}</td>
                <td style="color:${r.year_1_net > 0 ? 'var(--success)' : r.year_1_net < 0 ? 'var(--danger)' : 'var(--text-muted)'}">
                    ${r.year_1_net > 0 ? '+' : ''}$${fmt(r.year_1_net)}
                </td>
            </tr>
        `).join('');
    } catch(e) {}
}

function renderGoldTierCard(key, tier) {
    const isSoldOut = tier.remaining <= 0;
    const isPremium = key === 'premium';
    const isSeven = key === 'the_seven';
    const stars = key === 'entry' ? '' : key === 'standard' ? '★' : key === 'premium' ? '★★' : key === 'founding_patron' ? '★★★' : '★★★★';
    const hasDiscount = !['entry','standard'].includes(key);

    return `
        <div class="detail-card" style="text-align:center;position:relative;${isSoldOut ? 'opacity:0.5' : ''}${isPremium ? 'border-color:var(--primary);transform:translateY(-4px)' : ''}${isSeven ? 'border-color:gold' : ''}">
            ${isPremium ? '<div style="position:absolute;top:-10px;left:50%;transform:translateX(-50%);background:var(--primary);color:white;padding:2px 14px;border-radius:12px;font-size:0.7rem;font-weight:700">BEST VALUE</div>' : ''}
            ${isSeven ? '<div style="position:absolute;top:-10px;left:50%;transform:translateX(-50%);background:gold;color:#000;padding:2px 14px;border-radius:12px;font-size:0.7rem;font-weight:700">✦ 7 ONLY ✦</div>' : ''}
            <h3 style="font-size:1rem;margin-top:${isPremium || isSeven ? '16px' : '0'}">${stars} ${tier.name}</h3>
            <div style="font-size:1.8rem;font-weight:800;color:var(--primary);margin:8px 0">
                $${fmt(tier.price_gbp)}
                <span style="font-size:0.75rem;color:var(--text-muted);font-weight:400;display:block">One-time payment</span>
            </div>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:8px">
                <span style="background:var(--surface2);padding:2px 10px;border-radius:12px">${tier.remaining} / ${tier.total} remaining</span>
            </div>

            <div style="text-align:left;font-size:0.8rem;color:var(--text-muted);margin:12px 0">
                <div style="padding:3px 0">✅ Gold Badge</div>
                <div style="padding:3px 0">✅ Member Number</div>
                <div style="padding:3px 0">✅ Hall of Fame</div>
                ${hasDiscount ? `<div style="padding:3px 0;color:var(--accent)">✅ ${tier.commission_discount*100}% Lifetime Commission</div>` : `<div style="padding:3px 0">✅ 7% Standard Commission</div>`}
                ${hasDiscount ? `<div style="padding:3px 0;color:var(--accent)">✅ ${tier.staking_multiplier}x Staking Limits</div>` : ''}
                ${key === 'founding_patron' ? '<div style="padding:3px 0;color:gold">✅ Lifetime Pro Status</div>' : ''}
                ${isSeven ? `<div style="padding:3px 0;color:gold">✅ 10x Staking Limits</div>
                             <div style="padding:3px 0;color:gold">✅ Private CEO Hotline</div>
                             <div style="padding:3px 0;color:gold">✅ Annual VIP Hospitality</div>` : ''}
            </div>

            <div style="font-size:1.2rem;font-weight:700;padding:8px;background:var(--surface2);border-radius:var(--radius-sm);margin:12px 0">
                ${tier.commission_discount*100}% Commission
                ${hasDiscount ? `<span style="font-size:0.7rem;display:block;color:var(--accent)">Saves ${Math.round((0.07 - tier.commission_discount)*100)}% on every pot</span>` : ''}
            </div>

            ${isSeven ? `
                <button class="btn btn-primary btn-lg" style="width:100%;background:gold;color:#000" onclick="inquireGoldSeven()">
                    ✦ Inquire ✦
                </button>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:4px">7 slots — by application only</p>
            ` : (tier.remaining > 0 ? `
                <a href="${tier.stripe_payment_link}" target="_blank" class="btn btn-primary btn-lg" style="width:100%;display:inline-block;text-align:center;text-decoration:none">
                    Buy Now (${tier.remaining} left)
                </a>
            ` : `
                <button class="btn btn-outline" disabled style="width:100%">Sold Out</button>
            `)}
        </div>
    `;
}

function renderGoldSevenPitch() {
    return `
        <section style="margin:32px 0;text-align:center" class="seven-pitch">
            <div class="detail-card" style="border-color:gold;background:linear-gradient(135deg,var(--surface),var(--surface2))">
                <h2 style="font-size:1.5rem;color:gold">✦ THE SEVEN ✦</h2>
                <p class="subtitle" style="font-size:1.1rem">Seven people. Seven passes. One of a kind.</p>
                <p style="color:var(--text-muted);max-width:600px;margin:16px auto;font-size:0.9rem">
                    The Seven isn't a product tier — it's a partnership. Only seven people in the world will ever hold this pass. You'll be part of Seven Bet's inner circle from day one.
                </p>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:20px 0;text-align:left">
                    <div class="detail-card" style="font-size:0.85rem">
                        <strong style="color:gold">🔑 Choose Your Number</strong>
                        <p style="color:var(--text-muted);font-size:0.8rem;margin-top:4px">Select #1-#7. Lower numbers first come, first served.</p>
                    </div>
                    <div class="detail-card" style="font-size:0.85rem">
                        <strong style="color:gold">📞 Private CEO Hotline</strong>
                        <p style="color:var(--text-muted);font-size:0.8rem;margin-top:4px">Direct line to the CEO — no tickets, no queues.</p>
                    </div>
                    <div class="detail-card" style="font-size:0.85rem">
                        <strong style="color:gold">🎪 Annual VIP Hospitality</strong>
                        <p style="color:var(--text-muted);font-size:0.8rem;margin-top:4px">Premier League, Wimbledon, The Open, or Ascot — your guest.</p>
                    </div>
                    <div class="detail-card" style="font-size:0.85rem">
                        <strong style="color:gold">📊 Board-Level Influence</strong>
                        <p style="color:var(--text-muted);font-size:0.8rem;margin-top:4px">Quarterly strategy calls. Your features go straight to the board.</p>
                    </div>
                </div>
                <div style="margin-top:20px;padding:16px;border-top:1px solid var(--border)">
                    <p style="font-weight:700;color:gold">Only 7 passes will ever be minted.</p>
                    <a href="mailto:concierge@sevenbet.com" class="btn btn-primary btn-lg" style="background:gold;color:#000;border:none;text-decoration:none;display:inline-flex;align-items:center;gap:8px">
                        ✦ Apply for The Seven ✦
                    </a>
                    <p style="font-size:0.8rem;color:var(--text-muted);margin-top:4px">concierge@sevenbet.com</p>
                </div>
            </div>
        </section>
    `;
}

function renderGoldScarcity(totalSold, totalSupply, totalRemaining, pctSold) {
    return `
        <section style="margin:32px 0;text-align:center">
            <h2>Limited Supply — Once They're Gone, They're Gone</h2>
            <div class="detail-card" style="max-width:500px;margin:16px auto">
                <h3 style="font-size:1rem;margin-bottom:10px">Only 1,500 Gold Upgrades Will Ever Be Sold</h3>
                <div style="background:var(--surface2);border-radius:10px;height:16px;overflow:hidden">
                    <div style="background:linear-gradient(90deg,var(--primary),var(--accent));height:100%;width:${pctSold}%;display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;color:white;min-width:40px">${pctSold}%</div>
                </div>
                <p style="margin-top:8px;font-size:0.9rem"><strong>${totalSold} of ${totalSupply} upgrades claimed.</strong> ${totalRemaining} remaining.</p>
            </div>
        </section>
    `;
}

function renderGoldFAQ() {
    const faqs = [
        {q: 'Who can buy a Gold Upgrade?', a: 'Anyone aged 18 or over. This is a digital upgrade — not a gambling product.'},
        {q: 'What happens after I buy?', a: 'Your Gold Upgrade is activated immediately. Your reduced commission rate applies to every bet from that moment forward.'},
        {q: 'Can I get a refund?', a: 'Yes — 14-day cooling-off period under UK Consumer Contracts Regulations.'},
        {q: 'Is the commission rate really locked for life?', a: 'Yes — your reduced rate is permanent. It applies to every bet on the platform forever.'},
        {q: 'Can I upgrade my tier later?', a: 'Yes — you can upgrade by paying the difference. Downgrades are not available.'},
        {q: 'Do I need a Gold Upgrade to bet?', a: 'No! You can sign up and bet for free with a 7% commission. Gold is optional — it saves you money if you bet regularly.'},
        {q: 'What payment methods do you accept?', a: 'Debit/credit cards and Apple Pay via Stripe.'},
        {q: 'How do I apply for The Seven?', a: 'Email concierge@sevenbet.com with your name and betting background.'},
    ];
    return `
        <section style="margin:32px 0;max-width:700px;margin-left:auto;margin-right:auto">
            <h2 style="text-align:center">Frequently Asked Questions</h2>
            <div style="margin-top:16px">
                ${faqs.map((f, i) => `
                    <details style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);margin-bottom:8px;padding:12px 16px;cursor:pointer">
                        <summary style="font-weight:600;font-size:0.9rem;outline:none">${esc(f.q)}</summary>
                        <p style="color:var(--text-muted);font-size:0.85rem;margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">${esc(f.a)}</p>
                    </details>
                `).join('')}
            </div>
        </section>
    `;
}

function renderGoldFooter() {
    return `
        <footer style="margin:32px 0;padding:20px;border-top:1px solid var(--border);font-size:0.75rem;color:var(--text-muted);text-align:center">
            <p><strong>Seven Bet Ltd</strong> — United Kingdom</p>
            <p style="margin-top:4px">Standard UK VAT (20%) is included in all prices shown.</p>
            <div style="margin-top:8px;display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
                <a href="/terms" style="color:var(--primary)">Terms & Conditions</a>
                <a href="/privacy" style="color:var(--primary)">Privacy Policy</a>
                <a href="mailto:support@sevenbet.com" style="color:var(--primary)">Contact Us</a>
                <a href="mailto:concierge@sevenbet.com" style="color:gold">The Seven Inquiries</a>
            </div>
            <div style="margin-top:8px;display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
                <span>✅ 18+ Only</span> | <span>✅ 14-Day Refund</span> | <span>✅ UK Company</span> | <span>✅ Stripe Secure</span> | <span>✅ LifeLocked Rate</span>
            </div>
            <p style="margin-top:8px">When the fun stops, stop. <a href="https://www.begambleaware.org" style="color:var(--primary)">begambleaware.org</a></p>
        </footer>
    `;
}

function inquireGoldSeven() {
    const name = prompt('Enter your full name:', '');
    if (name === null) return;
    const email = prompt('Enter your email address:', '');
    if (email === null || !email) { showToast('Email is required', 'error'); return; }
    const number = prompt('Preferred Founder Number (1-7, optional):', '');
    api('/admin/concierge/capture-inquiry', {
        method: 'POST',
        body: JSON.stringify({
            email: email,
            tier: 'the_seven',
            name: name || '',
            notes: 'Inquiry via Gold Upgrade page. Name: ' + (name || 'Not provided'),
            preferred_number: number ? parseInt(number) : null,
        }),
    }).then(resp => {
        if (resp.ok) {
            showToast('Inquiry received! Our concierge team will be in touch within 24 hours.', 'success');
        }
    }).catch(e => {
        showToast('Inquiry logged. Our concierge team will contact you.', 'info');
    });
    window.open('mailto:concierge@sevenbet.com?subject=The%20Seven%20-%20Application&body=Hello%20Seven%20Bet%20Concierge%20Team%2C%0A%0AI%20am%20interested%20in%20joining%20The%20Seven.%20Please%20find%20my%20details%20below%3A%0A%0AName%3A%20' + encodeURIComponent(name || '') + '%0AEmail%3A%20' + encodeURIComponent(email) + '%0APreferred%20Number%3A%20' + encodeURIComponent(number || 'Not specified') + '%0A%0AThank%20you.%0A');
}

// ── Real-time Scarcity Counter & Live Purchase Feed ────────────
let scarcityPollInterval = null;
let lastSoldCounts = {};

async function pollAvailability() {
    try {
        const avail = await api('/founders-pass/availability');
        const heroCounters = document.querySelectorAll('.scarcity-progress, .stat-value');
        if (heroCounters.length > 0) {
            const totalSold = Object.values(avail).reduce((s, t) => s + t.sold, 0);
            const totalSupply = Object.values(avail).reduce((s, t) => s + t.total, 0);
            const remaining = totalSupply - totalSold;
            const pct = totalSupply > 0 ? (totalSold / totalSupply * 100).toFixed(0) : '0';
            document.querySelectorAll('[class*="progress"]').forEach(el => {
                if (el.style && el.tagName === 'DIV') {
                    el.style.width = pct + '%';
                    el.textContent = pct + '%';
                }
            });
        }
        for (const [tier, data] of Object.entries(avail)) {
            const prevSold = lastSoldCounts[tier] || 0;
            if (data.sold > prevSold) {
                const diff = data.sold - prevSold;
                showLivePurchase(tier, data.name, diff);
            }
            lastSoldCounts[tier] = data.sold;
        }
    } catch (e) {}
}

function showLivePurchase(tier, name, count) {
    const names = ['Alex', 'Jordan', 'Sam', 'Casey', 'Riley', 'Morgan', 'Taylor', 'Jamie', 'Quinn', 'Avery',
                   'Drew', 'Blake', 'Cameron', 'Dakota', 'Skyler', 'Reese', 'Finley', 'Rowan', 'Peyton', 'Logan'];
    const locations = ['London', 'Manchester', 'Edinburgh', 'Birmingham', 'Glasgow', 'Liverpool', 'Bristol',
                       'New York', 'Los Angeles', 'Chicago', 'Miami', 'Austin', 'Denver', 'Boston', 'Seattle',
                       'Toronto', 'Sydney', 'Dublin', 'Amsterdam', 'Berlin'];
    const randomName = names[Math.floor(Math.random() * names.length)];
    const randomLocation = locations[Math.floor(Math.random() * locations.length)];
    const tierEmoji = tier === 'the_seven' ? '👑' : tier === 'founding_patron' ? '💎' : tier === 'premium' ? '⭐' : '🔥';
    const msg = tierEmoji + ' ' + randomName + ' from ' + randomLocation + ' just purchased the ' + name + ' upgrade!';
    showToast(msg, 'success');
}

function startScarcityPolling() {
    api('/founders-pass/availability').then(avail => {
        for (const [tier, data] of Object.entries(avail)) {
            lastSoldCounts[tier] = data.sold;
        }
    }).catch(() => {});
    if (scarcityPollInterval) clearInterval(scarcityPollInterval);
    scarcityPollInterval = setInterval(pollAvailability, 10000);
}

function stopScarcityPolling() {
    if (scarcityPollInterval) {
        clearInterval(scarcityPollInterval);
        scarcityPollInterval = null;
    }
}

// Override handleRoute for scarcity polling
const originalHandleRoute = handleRoute;
handleRoute = function() {
    const path = window.location.pathname;
    if (path === '/gold-upgrade' || path === '/founders-pass') {
        startScarcityPolling();
    } else {
        stopScarcityPolling();
    }
    originalHandleRoute();
};
