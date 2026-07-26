const DATA_URL = 'https://raw.githubusercontent.com/Misagh95/droperog/main/docs/data/projects.json';

const state = {
  projects: [], filtered: [],
  chainFilter: 'all', statusFilter: 'all', viewFilter: 'all', riskFilter: 'all',
  sortOrder: 'opportunity', searchQuery: '',
};

const NEW_MS = 3 * 24 * 60 * 60 * 1000;

const chainEmoji = c =>
  ({ ethereum: '⟠', solana: '◎', base: '🔵', arbitrum: '🔴', optimism: '🟠',
     polygon: '🟣', zksync: '⚡', bsc: '🟡', avalanche: '🔺', ton: '💎',
     scroll: '📜', linea: '〰️', starknet: '⚔️', sui: '🌊' } [c] || '⛓');

const statusBadge = s => {
  const m = {
    potential: ['💎', 'Potential'], confirmed: ['✅', 'Confirmed'], active: ['🟢', 'Active'],
    upcoming: ['🆕', 'Upcoming'], ended: ['🔴', 'Ended'], unknown: ['❓', 'Unknown'],
  };
  const [e, t] = m[s] || ['❓', s];
  return `<span class="badge badge-${s}">${e} ${t}</span>`;
};

const scoreColor = s => s >= 80 ? '#22c55e' : s >= 60 ? '#eab308' : s >= 40 ? '#f97316' : '#ef4444';
const riskColor = r => ({ low: '#22c55e', medium: '#eab308', high: '#f97316', critical: '#ef4444' } [r] || '#64748b');

function scoreBar(score) {
  const c = scoreColor(score);
  return `<div class="score-bar"><div class="score-fill" style="width:${score}%;background:${c}"></div></div><span class="score-text" style="color:${c}">${score}%</span>`;
}

function timeAgo(ts) {
  const sec = Math.floor((Date.now() - ts) / 1000);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function isNew(p) { return (Date.now() - p.discoveredAt) < NEW_MS; }
function safe(p, field, def) { const v = p[field]; return v !== void 0 && v !== null ? v : def; }

function updateMarketBar(projects) {
  const fngEl = document.getElementById('fng-value');
  const gasEl = document.getElementById('gas-value');
  const listingsEl = document.getElementById('listings-value');

  if (!projects.length) return;

  const avgTrust = Math.round(projects.reduce((s, p) => s + p.trustScore, 0) / projects.length);
  const newCount = projects.filter(isNew).length;
  const totalValue = projects.reduce((s, p) => s + safe(p, 'expectedValue', 0), 0);

  fngEl.textContent = `${avgTrust}% avg trust`;
  gasEl.textContent = `${projects.length} tracked`;
  listingsEl.textContent = `$${(totalValue / 1000).toFixed(1)}K est.`;
}

function render() {
  const list = document.getElementById('project-list');
  const count = document.getElementById('count');
  const avgOpp = document.getElementById('avg-opp');
  let items = [...state.filtered];

  if (state.chainFilter !== 'all')
    items = items.filter(p => (p.chains || []).some(c => c === state.chainFilter));

  if (state.viewFilter === 'new') items = items.filter(isNew);
  else if (state.statusFilter !== 'all') items = items.filter(p => p.status === state.statusFilter);

  if (state.riskFilter !== 'all')
    items = items.filter(p => (p.scamRisk || 'low') === state.riskFilter);

  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    items = items.filter(p =>
      p.name.toLowerCase().includes(q) ||
      (p.description || '').toLowerCase().includes(q) ||
      (p.tokenInfo && p.tokenInfo.symbol && p.tokenInfo.symbol.toLowerCase().includes(q))
    );
  }

  const sortFns = {
    opportunity: (a, b) => (safe(b, 'opportunityScore', 0) - safe(a, 'opportunityScore', 0)),
    newest: (a, b) => b.discoveredAt - a.discoveredAt,
    trust: (a, b) => b.trustScore - a.trustScore,
    value: (a, b) => (safe(b, 'expectedValue', 0) - safe(a, 'expectedValue', 0)),
    vph: (a, b) => (safe(b, 'valuePerHour', 0) - safe(a, 'valuePerHour', 0)),
    urgency: (a, b) => (safe(b, 'urgencyScore', 0) - safe(a, 'urgencyScore', 0)),
  };
  items.sort(sortFns[state.sortOrder] || sortFns.opportunity);

  count.textContent = `${items.length}`;
  const avg = items.length
    ? Math.round(items.reduce((s, p) => s + safe(p, 'opportunityScore', 0), 0) / items.length)
    : 0;
  avgOpp.textContent = `🎯 ${avg}%`;

  if (!items.length) {
    list.innerHTML = '<div class="empty">✨ No airdrops found</div>';
    return;
  }

  list.innerHTML = items.map(p => {
    const opp = safe(p, 'opportunityScore', '?');
    const leg = safe(p, 'legitimacyScore', '?');
    const rw = safe(p, 'rewardPotential', '?');
    const ef = safe(p, 'effortScore', '?');
    const urg = safe(p, 'urgencyScore', '?');
    const ev = safe(p, 'expectedValue', 0);
    const vph = safe(p, 'valuePerHour', 0);
    const risk = p.scamRisk || 'low';
    const lw = p.linkWarnings || [];
    const hasLinkWarn = lw.some(w => w.severity === 'high' || w.severity === 'critical');
    const chains = (p.chains || ['?']).map(c => chainEmoji(c)).join(' ');

    return `<div class="card" onclick="window.open('${p.sourceUrl}','_blank')">
      <div class="card-header">
        <span class="card-name">${statusBadge(p.status)} ${p.name}</span>
        <span>${p.source === 'twitter' ? '🐦' : '🌐'}</span>
      </div>
      <div class="card-body">
        <div class="card-row">
          <span class="card-label">🎯 Opportunity</span>
          ${scoreBar(opp)}
        </div>
        <div class="card-row">
          <span class="card-label">✅ Trust</span>
          ${scoreBar(p.trustScore)}
        </div>
        <div class="card-row">
          <span class="card-label">⛓ Chain</span>
          <span>${chains}</span>
        </div>
        <div class="card-row">
          <span class="card-label">🛡 Risk</span>
          <span style="color:${riskColor(risk)};font-weight:600">${risk}</span>
        </div>
        <div class="card-row">
          <span class="card-label">🕐 Found</span>
          <span>${timeAgo(p.discoveredAt)}</span>
        </div>
        ${p.tokenInfo?.symbol ? `<div class="card-row"><span class="card-label">Token</span><span>${p.tokenInfo.symbol}</span></div>` : ''}
        ${ev > 0 ? `<div class="card-row"><span class="card-label">💰 Value</span><span>$${ev} ${vph > 0 ? `· $${vph}/hr` : ''}</span></div>` : ''}
        <div class="score-row">
          <span class="score-item">🎯 <span style="color:${scoreColor(leg)}">${leg}%</span></span>
          <span class="score-item">💰 <span style="color:${scoreColor(rw)}">${rw}%</span></span>
          <span class="score-item">💪 <span style="color:${scoreColor(ef)}">${ef}%</span></span>
          <span class="score-item">⏰ <span style="color:${scoreColor(urg)}">${urg}%</span></span>
        </div>
      </div>
      ${p.description && p.description.length > 10 ? `<div class="card-desc">${p.description.substring(0, 100)}${p.description.length > 100 ? '...' : ''}</div>` : ''}
      ${hasLinkWarn ? `<div class="card-link-warn">🔗 ⚠️ ${lw.length} link warning(s)</div>` : ''}
      ${p.scamFlags && p.scamFlags.length ? `<div class="card-flags">⚠️ ${p.scamFlags.join(', ')}</div>` : `<div class="card-flags safe">✅ No red flags</div>`}
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
  updateMarketBar(state.projects);
  render();
}

function filterByChain(chain) {
  state.chainFilter = state.chainFilter === chain ? 'all' : chain;
  document.querySelectorAll('.chain-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.chain === state.chainFilter));
  render();
}

function setView(view) {
  state.viewFilter = state.viewFilter === view ? 'all' : view;
  state.statusFilter = 'all';
  document.querySelectorAll('.view-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.view === state.viewFilter));
  document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
  render();
}

function filterByStatus(status) {
  state.statusFilter = state.statusFilter === status ? 'all' : status;
  state.viewFilter = 'all';
  document.querySelectorAll('.status-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.status === state.statusFilter));
  document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  render();
}

function filterByRisk(risk) {
  state.riskFilter = state.riskFilter === risk ? 'all' : risk;
  document.querySelectorAll('.risk-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.risk === state.riskFilter));
  render();
}

function setSort(order) {
  state.sortOrder = order;
  document.querySelectorAll('.sort-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.sort === state.sortOrder));
  render();
}

function search(q) {
  state.searchQuery = q || '';
  render();
}

document.addEventListener('DOMContentLoaded', () => {
  load();
  document.getElementById('search').addEventListener('input', e => search(e.target.value));
  setInterval(load, 300000);
});

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js');
}
