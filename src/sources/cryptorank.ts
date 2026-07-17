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
    twitterScore: { twitterScore: number; followersCount: number | null };
  };
  activityTypes: string[];
  status: string | null;
  statusUpdatedAt: string;
  createdAt: string;
  rewardType: string;
  cost: number;
  time: number;
}

interface NextData {
  props?: {
    pageProps?: {
      fallbackTableData?: {
        data: CryptoRankItem[];
        count: number;
      };
    };
  };
}

export class CryptoRankSource {
  async fetchAirdrops(): Promise<AirdropProject[]> {
    try {
      const html = await this.fetchPage('https://cryptorank.io/drophunting');
      const items = this.extractItems(html);
      return items.map(item => this.toProject(item));
    } catch (err: any) {
      console.error(`  [CryptoRank] Error: ${err.message}`);
      return [];
    }
  }

  private async fetchPage(url: string): Promise<string> {
    const res = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
      },
      timeout: 15000,
    });
    return res.data;
  }

  private extractItems(html: string): CryptoRankItem[] {
    const match = html.match(/__NEXT_DATA__[^>]*>(.*?)<\/script>/s);
    if (!match) return [];

    try {
      const json: NextData = JSON.parse(match[1]);
      return json.props?.pageProps?.fallbackTableData?.data ?? [];
    } catch {
      return [];
    }
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
      sourceUrl: `https://cryptorank.io/drophunting/${item.coin?.key || item.key}`,
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
      case 'CONFIRMED': return 'active';
      case 'POTENTIAL': return 'upcoming';
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