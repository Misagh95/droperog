import axios from 'axios';
import { AirdropProject } from '../types';
import { generateId } from '../utils';

interface CryptoRankItem {
  key: string;
  rating: number;
  linkToClaim: string | null;
  checkLink: string | null;
  coin: {
    key: string;
    symbol: string | null;
    name: string;
    icon: string;
    totalRaise: number | null;
    funds: Array<{ slug: string; name: string }>;
    twitterScore: { twitterScore: number; followersCount: number | null; twitterAccountId: number };
  };
  activityTypes: string[];
  activityPoints: number;
  status: string | null;
  statusUpdatedAt: string;
  createdAt: string;
  rewardType: string;
  noActiveTask: boolean;
  cost: number;
  time: number;
}

interface ApiResponse {
  data: CryptoRankItem[];
  count: number;
}

const MAX_PAGE_SIZE = 100;
const API_BASE = 'https://api.cryptorank.io/v0/drop-hunting/activities/table/public';

export class CryptoRankSource {
  async fetchAirdrops(): Promise<AirdropProject[]> {
    try {
      const allItems = await this.fetchAllPages();
      return allItems.map(item => this.toProject(item));
    } catch (err: any) {
      console.error(`  [CryptoRank] Error: ${err.message}`);
      return [];
    }
  }

  private async fetchAllPages(): Promise<CryptoRankItem[]> {
    let offset = 0;
    let total = 0;
    const all: CryptoRankItem[] = [];

    do {
      const res = await axios.get<ApiResponse>(API_BASE, {
        params: { limit: MAX_PAGE_SIZE, offset },
        timeout: 20000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Origin': 'https://cryptorank.io',
          'Referer': 'https://cryptorank.io/',
        },
      });

      const { data, count } = res.data;
      all.push(...data);
      total = count;
      offset += data.length;

      if (data.length < MAX_PAGE_SIZE) break;
      await this.delay(400);
    } while (offset < total);

    return all;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(r => setTimeout(r, ms));
  }

  private toProject(item: CryptoRankItem): AirdropProject {
    const name = item.coin?.name || 'Unknown';
    const status = this.mapStatus(item.status);
    const chains = this.inferChains(item.activityTypes);

    const fundsRaised = item.coin?.totalRaise
      ? `${this.toCurrency(item.coin.totalRaise)} raised`
      : '';
    const activities = Array.isArray(item.activityTypes) ? item.activityTypes.join(', ') : '';
    const rating = item.rating || 0;

    const description = [
      `Rating: ${rating}/1000`,
      item.coin?.key,
      fundsRaised,
      activities ? `Tasks: ${activities}` : '',
      `Effort: ${item.cost || 0}pts / ${item.time || 0}min`,
    ].filter(Boolean).join(' | ');

    const trustScore = this.calcTrustScore(item);

    const links: Record<string, string> = {};
    if (item.linkToClaim) links.claim = item.linkToClaim;
    if (item.checkLink) links.check = item.checkLink;

    return {
      id: generateId('crnk'),
      name,
      description,
      source: 'web_scrape',
      sourceUrl: `https://cryptorank.io/price/${item.coin?.key || item.key}`,
      chains,
      status,
      trustScore,
      scamFlags: [],
      links,
      discoveredAt: new Date(item.createdAt).getTime(),
      lastChecked: Date.now(),
    };
  }

  private mapStatus(s: string | null): AirdropProject['status'] {
    switch (s?.toUpperCase()) {
      case 'CONFIRMED': return 'confirmed';
      case 'POTENTIAL': return 'potential';
      case 'DISTRIBUTED': return 'ended';
      default: return 'unknown';
    }
  }

  private inferChains(types: string[] | undefined): string[] {
    if (!types || types.length === 0) return ['unknown'];
    const text = types.join(' ').toLowerCase();
    const chains: string[] = [];
    if (/\b(eth|ethereum)\b/.test(text)) chains.push('ethereum');
    if (/\b(sol|solana)\b/.test(text)) chains.push('solana');
    if (/\b(base)\b/.test(text)) chains.push('base');
    if (/\b(arbitrum|arb)\b/.test(text)) chains.push('arbitrum');
    if (/\b(optimism|op)\b/.test(text)) chains.push('optimism');
    if (/\b(polygon|matic)\b/.test(text)) chains.push('polygon');
    if (/\b(bsc|bnb|binance)\b/.test(text)) chains.push('bsc');
    if (/\b(avax|avalanche)\b/.test(text)) chains.push('avalanche');
    if (/\b(ton)\b/.test(text)) chains.push('ton');
    return chains.length > 0 ? chains : ['unknown'];
  }

  private calcTrustScore(item: CryptoRankItem): number {
    let score = 50;
    if (item.rating > 100) score += 15;
    else if (item.rating > 50) score += 10;
    else if (item.rating > 10) score += 5;
    if (item.coin?.totalRaise) score += 10;
    if (item.coin?.funds && item.coin.funds.length > 0) score += 10;
    if (item.linkToClaim) score += 5;
    if (item.coin?.twitterScore?.twitterScore > 1000) score += 5;
    if (item.status === 'CONFIRMED') score += 10;
    return Math.min(score, 95);
  }

  private toCurrency(num: number): string {
    if (num >= 1_000_000_000) return `$${(num / 1_000_000_000).toFixed(1)}B`;
    if (num >= 1_000_000) return `$${(num / 1_000_000).toFixed(1)}M`;
    if (num >= 1_000) return `$${(num / 1_000).toFixed(1)}K`;
    return `$${num}`;
  }
}
