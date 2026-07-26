const DATA_URL = 'https://raw.githubusercontent.com/Misagh95/droperog/main/docs/data/projects.json';

const state = { projects: [], filtered: [], statusFilter: 'all', riskFilter: 'all', sortOrder: 'opportunity', searchQuery: '' };
const NEW_MS = 3 * 24 * 60 * 60 * 1000;

const chainEmoji = c =>
  ({ ethereum:'⟠', solana:'◎', base:'🔵', arbitrum:'🔴', optimism:'🟠', polygon:'🟣', zksync:'⚡', bsc:'🟡', avalanche:'🔺', ton:'💎', scroll:'📜', linea:'〰️', starknet:'⚔️', sui:'🌊' } [c] || '⛓');

const scoreColor = s => s >= 80 ? '#22c55e' : s >= 60 ? '#eab308' : s >= 40 ? '#f97316' : '#ef4444';

function bar(score) {
  return `<div class="bar"><div class="bar-fill" style="width:${score}%;background:${scoreColor(score)}"></div></div>`;
}

function timeAgo(ts) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return 'now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function safe(p, f, d) { const v = p[f]; return v !== void 0 && v !== null ? v : d; }

function render() {
  const list = document.getElementById('project-list');
  const count = document.getElementById('count');
  const avgOpp = document.getElementById('avg-opp');
  let items = [...state.filtered];

  if (state.statusFilter === 'new') items = items.filter(p => (Date.now() - p.discoveredAt) < NEW_MS);
  else if (state.statusFilter !== 'all') items = items.filter(p => p.status === state.statusFilter);

  if (state.riskFilter !== 'all') items = items.filter(p => (p.scamRisk || 'low') === state.riskFilter);

  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    items = items.filter(p =>
      p.name.toLowerCase().includes(q) ||
      (p.tokenInfo && p.tokenInfo.symbol && p.tokenInfo.symbol.toLowerCase().includes(q))
    );
  }

  const sortFns = {
    opportunity: (a,b) => (safe(b,'opportunityScore',0) - safe(a,'opportunityScore',0)),
    newest: (a,b) => b.discoveredAt - a.discoveredAt,
    trust: (a,b) => b.trustScore - a.trustScore,
    value: (a,b) => (safe(b,'expectedValue',0) - safe(a,'expectedValue',0)),
    urgency: (a,b) => (safe(b,'urgencyScore',0) - safe(a,'urgencyScore',0)),
  };
  items.sort(sortFns[state.sortOrder] || sortFns.opportunity);

  count.textContent = items.length;
  const avg = items.length ? Math.round(items.reduce((s,p) => s + safe(p,'opportunityScore',0), 0) / items.length) : 0;
  avgOpp.textContent = `🎯 ${avg}% avg`;

  if (!items.length) {
    list.innerHTML = '<div class="empty">✨ No airdrops found</div>';
    return;
  }

  list.innerHTML = items.map(p => {
    const opp = safe(p,'opportunityScore','?');
    const ev = safe(p,'expectedValue',0);
    const risk = p.scamRisk || 'low';
    const chains = (p.chains || ['?']).map(c => chainEmoji(c)).join(' ');
    const flags = p.scamFlags || [];
    const lw = p.linkWarnings || [];

    return `<div class="card" onclick="window.open('${p.sourceUrl}','_blank')">
      <div class="card-top">
        <div>
          <div class="card-name">${p.name}</div>
          <div class="card-tags">
            <span class="tag tag-${p.status}">${p.status}</span>
            <span class="tag tag-${risk}" style="background:#1a1a2e;color:${risk==='low'?'#22c55e':risk==='medium'?'#eab308':risk==='high'?'#f97316':'#ef4444'}">${risk}</span>
          </div>
        </div>
        <div style="text-align:right;font-size:12px;color:#64748b;white-space:nowrap">
          ${chains}<br>
          ${timeAgo(p.discoveredAt)}
        </div>
      </div>
      <div class="card-stats">
        <span class="stat"><span class="stat-label">🎯</span><span class="stat-val" style="color:${scoreColor(opp)}">${opp}%</span> ${bar(opp)}</span>
        <span class="stat"><span class="stat-label">✅</span><span class="stat-val" style="color:${scoreColor(p.trustScore)}">${p.trustScore}%</span> ${bar(p.trustScore)}</span>
        ${p.tokenInfo?.symbol ? `<span class="stat"><span class="stat-label">Token</span><span class="stat-val">${p.tokenInfo.symbol}</span></span>` : ''}
        ${ev > 0 ? `<span class="stat"><span class="stat-label">💰</span><span class="stat-val">$${ev}</span></span>` : ''}
      </div>
      ${p.description && p.description.length > 10 ? `<div class="card-detail">${p.description.substring(0, 80)}${p.description.length > 80 ? '...' : ''}</div>` : ''}
      ${flags.length ? `<div class="card-warn">⚠️ ${flags.join(', ')}</div>` : ''}
      ${lw.length ? `<div class="card-warn">🔗 ${lw.length} link warning(s)</div>` : ''}
    </div>`;
  }).join('');
}

async function load() {
  document.getElementById('loading').classList.remove('hidden');
  try {
    const r = await fetch(DATA_URL + '?t=' + Date.now());
    state.projects = await r.json();
  } catch { state.projects = []; }
  document.getElementById('loading').classList.add('hidden');
  state.filtered = [...state.projects];
  document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
  render();
}

document.addEventListener('DOMContentLoaded', () => {
  load();

  document.getElementById('search').addEventListener('input', e => {
    state.searchQuery = e.target.value;
    render();
  });

  document.getElementById('sort-select').addEventListener('change', e => {
    state.sortOrder = e.target.value;
    render();
  });

  document.getElementById('status-select').addEventListener('change', e => {
    state.statusFilter = e.target.value;
    render();
  });

  document.getElementById('risk-select').addEventListener('change', e => {
    state.riskFilter = e.target.value;
    render();
  });

  setInterval(load, 300000);
});

if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js');
