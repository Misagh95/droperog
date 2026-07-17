const KNOWN_CHAINS = [
  'ethereum', 'eth',
  'arbitrum', 'arb',
  'optimism', 'op',
  'base',
  'polygon', 'matic',
  'zksync', 'era', 'zksync era',
  'solana', 'sol',
  'avalanche', 'avax',
  'bsc', 'bnb', 'binance',
  'scroll',
  'linea',
  'starknet',
  'celestia', 'tia',
  'sui',
  'aptos',
  'ton',
  'near',
  'cosmos',
  'osmosis',
  'injective',
  'sei',
  'berachain',
];

const CHAIN_ALIASES: Record<string, string> = {
  eth: 'ethereum',
  arb: 'arbitrum',
  op: 'optimism',
  matic: 'polygon',
  era: 'zksync',
  sol: 'solana',
  avax: 'avalanche',
  bnb: 'bsc',
  tia: 'celestia',
};

export function extractChains(text: string): string[] {
  const chains = new Set<string>();
  const lower = text.toLowerCase();

  for (const keyword of KNOWN_CHAINS) {
    if (lower.includes(keyword)) {
      const normalized = CHAIN_ALIASES[keyword] || keyword;
      chains.add(normalized);
    }
  }

  return Array.from(chains);
}

export function cleanText(text: string): string {
  return text
    .replace(/<[^>]*>/g, ' ')
    .replace(/&[a-z]+;/g, ' ')
    .replace(/[\n\r\t]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .trim();
}

export function generateId(prefix: string = 'proj'): string {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).substr(2, 6);
  return `${prefix}_${ts}_${rand}`;
}

export function formatDate(ts: number): string {
  return new Date(ts).toLocaleDateString('fa-IR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function getTimeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

export function truncate(str: string, len: number = 80): string {
  if (!str || str.length <= len) return str || '';
  return str.slice(0, len) + '...';
}

export function chainToEmoji(chain: string): string {
  const map: Record<string, string> = {
    ethereum: '⟠',
    arbitrum: '🔷',
    optimism: '🔴',
    base: '🔵',
    polygon: '🟣',
    zksync: '⚡',
    solana: '◎',
    avalanche: '🔺',
    bsc: '🟡',
    unknown: '❓',
  };
  return map[chain.toLowerCase()] || '⛓';
}

export function emojiForStatus(status: string): string {
  const map: Record<string, string> = {
    upcoming: '🆕',
    active: '🟢',
    ended: '🔴',
    claimed: '✅',
    unknown: '❓',
  };
  return map[status] || '❓';
}

export function bar(percent: number, size: number = 10): string {
  const filled = Math.round((percent / 100) * size);
  const empty = size - filled;
  return '█'.repeat(Math.max(0, filled)) + '░'.repeat(Math.max(0, empty));
}