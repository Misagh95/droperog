const DATA_URL = 'https://raw.githubusercontent.com/Misagh95/droperog/main/docs/data/projects.json';

const state = { projects: [], filtered: [], chainFilter: 'all', statusFilter: 'all' };

const chainEmoji = c => ({ ethereum: '⟠', solana: '◎', base: '🔵', arbitrum: '🔴', optimism: '🟠', polygon: '🟣', bsc: '🟡', avalanche: '🔺', ton: '💎' } [c] || '❓');

const statusBadge = s => {
  const m = { active: ['🟢', 'Active'], upcoming: ['🆕', 'Upcoming'], ended: ['🔴', 'Ended'], unknown: ['❓', 'Unknown'] };
  const [e, t] = m[s] || ['❓', s];
  return `<span class="badge badge-${s}">${e} ${t}</span>`;
};

const trustColor = s => s >= 80 ? '#22c55e' : s >= 60 ? '#eab308' : s >= 40 ? '#f97316' : '#ef4444';

function trustBar(score) {
  const color = trustColor(score);
  return `<div class="trust-bar"><div class="trust-fill" style="width:${score}%;background:${color}"></div></div><span class="trust-text" style="color:${color}">${score}%</span>`;
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

function render() {
  const list = document.getElementById('project-list');
  const count = document.getElementById('count');
  let items = state.filtered;

  if (state.chainFilter !== 'all') items = items.filter(p => p.chains.includes(state.chainFilter) || p.chains.includes('unknown'));
  if (state.statusFilter !== 'all') items = items.filter(p => p.status === state.statusFilter);

  items.sort((a, b) => b.discoveredAt - a.discoveredAt);
  count.textContent = `${items.length} airdrops`;

  if (!items.length) {
    list.innerHTML = '<div class="empty">✨ No airdrops found</div>';
    return;
  }

  list.innerHTML = items.map(p => `
    <div class="card" onclick="window.open('${p.sourceUrl}','_blank')">
      <div class="card-header">
        <span class="card-name">${statusBadge(p.status)} ${p.name}</span>
        <span class="card-source">${p.source === 'twitter' ? '🐦' : '🌐'}</span>
      </div>
      <div class="card-body">
        <div class="card-row">
          <span class="label">Trust</span>
          ${trustBar(p.trustScore)}
        </div>
        <div class="card-row">
          <span class="label">Chain</span>
          <span>${p.chains.map(c => chainEmoji(c)).join(' ') || '?'}</span>
        </div>
        ${p.tokenInfo?.symbol ? `<div class="card-row"><span class="label">Token</span><span>${p.tokenInfo.symbol}</span></div>` : ''}
        <div class="card-row">
          <span class="label">Found</span>
          <span>${timeAgo(p.discoveredAt)}</span>
        </div>
      </div>
      ${p.description && p.description.length > 10 ? `<div class="card-desc">${p.description.substring(0, 100)}${p.description.length > 100 ? '...' : ''}</div>` : ''}
      ${p.scamFlags.length ? `<div class="card-flags">⚠️ ${p.scamFlags.join(', ')}</div>` : '<div class="card-flags safe">✅ No red flags</div>'}
    </div>
  `).join('');
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

function filterByChain(chain) {
  state.chainFilter = state.chainFilter === chain ? 'all' : chain;
  document.querySelectorAll('.chain-btn').forEach(b => b.classList.toggle('active', b.dataset.chain === state.chainFilter));
  render();
}

function filterByStatus(status) {
  state.statusFilter = state.statusFilter === status ? 'all' : status;
  document.querySelectorAll('.status-btn').forEach(b => b.classList.toggle('active', b.dataset.status === state.statusFilter));
  render();
}

function search(q) {
  if (!q) { state.filtered = [...state.projects]; render(); return; }
  const lq = q.toLowerCase();
  state.filtered = state.projects.filter(p => p.name.toLowerCase().includes(lq) || (p.description || '').toLowerCase().includes(lq) || (p.chains || []).some(c => c.includes(lq)));
  render();
}

document.addEventListener('DOMContentLoaded', () => {
  load();
  document.getElementById('search').addEventListener('input', e => search(e.target.value));
  setInterval(load, 300000); // auto-refresh every 5min
});

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/droperog/sw.js');
}
