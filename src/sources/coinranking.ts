import axios from 'axios';
import { AirdropProject } from '../types';
import { generateId, extractChains } from '../utils';

const API_BASE = 'https://api.coinranking.com/v2';

interface CoinRankingCoin {
  uuid: string;
  symbol: string;
  name: string;
  description: string;
  iconUrl: string;
  websiteUrl: string;
  links: { name: string; url: string; type: string }[];
  color: string;
  listedAt: number;
  tier: number;
  rank: number;
  price: string;
  tags: string[];
}

interface CoinRankingResponse {
  status: string;
  data: {
    coins: CoinRankingCoin[];
    stats: { total: number; totalCoins: number };
  };
}

export class CoinRankingSource {
  private apiKey: string;

  constructor(apiKey?: string) {
    this.apiKey = apiKey || process.env.COINRANKING_API_KEY || '';
  }

  async fetchNewCoins(limit: number = 100): Promise<AirdropProject[]> {
    try {
      const headers: Record<string, string> = {
        'Accept': 'application/json',
      };
      if (this.apiKey) {
        headers['x-access-token'] = this.apiKey;
      }

      const res = await axios.get<CoinRankingResponse>(`${API_BASE}/coins`, {
        headers,
        params: {
          limit,
          orderBy: 'listedAt',
          orderDirection: 'desc',
        },
        timeout: 15000,
      });

      const coins = res.data.data?.coins || [];
      if (coins.length === 0) {
        console.error('  [CoinRanking] No coins returned. Response:', JSON.stringify(res.data).slice(0, 300));
        return [];
      }

      const projects: AirdropProject[] = [];
      const threeMonthsAgo = Date.now() - 90 * 24 * 60 * 60 * 1000;

      for (const coin of coins) {
        const allText = `${coin.name} ${coin.symbol} ${coin.description || ''} ${(coin.tags || []).join(' ')}`.toLowerCase();

        // Skip if listed too long ago
        const listedAt = coin.listedAt > 0 ? coin.listedAt * 1000 : 0;
        if (listedAt > 0 && listedAt < threeMonthsAgo) continue;

        // Must be airdrop-related or recently listed
        if (!this.isAirdropCandidate(allText) && listedAt < (Date.now() - 7 * 24 * 60 * 60 * 1000)) continue;

        const chains = extractChains(allText);
        const links = this.extractLinks(coin);
        const desc = this.cleanDesc(coin.description || '');

        projects.push({
          id: generateId('cr'),
          name: coin.name,
          description: desc || `${coin.name} (${coin.symbol})`,
          source: 'web_scrape',
          sourceUrl: coin.websiteUrl || `https://coinranking.com/coin/${coin.uuid}`,
          chains: chains.length > 0 ? chains : ['unknown'],
          status: listedAt > (Date.now() - 30 * 24 * 60 * 60 * 1000) ? 'upcoming' : 'unknown',
          trustScore: 55,
          scamFlags: [],
          links,
          tokenInfo: {
            symbol: coin.symbol,
            name: coin.name,
            chain: chains[0] || 'unknown',
          },
          discoveredAt: listedAt || Date.now(),
          lastChecked: Date.now(),
        });
      }

      return projects;
    } catch (err: any) {
      console.error(`  [CoinRanking] Error: ${err.message}`);
      if (err.response) {
        console.error(`  [CoinRanking] Status: ${err.response.status}`);
        console.error(`  [CoinRanking] Data: ${JSON.stringify(err.response.data).slice(0, 200)}`);
      }
      if (err.response?.status === 429) {
        console.error('  [CoinRanking] Rate limited. Get free API key at https://coinranking.com');
      }
      return [];
    }
  }

  private isAirdropCandidate(text: string): boolean {
    const keywords = [
      'airdrop', 'retrodrop', 'claim', 'token distribution',
      'community distribution', 'protocol', 'defi', 'launch',
      'yield', 'stake', 'governance token',
      'native token', 'ecosystem token', 'reward',
      'farming', 'liquidity mining',
    ];
    return keywords.some(k => text.includes(k));
  }

  private extractLinks(coin: CoinRankingCoin): AirdropProject['links'] {
    const links: AirdropProject['links'] = {};

    if (coin.websiteUrl) links.website = coin.websiteUrl;

    for (const link of (coin.links || [])) {
      const url = link.url.toLowerCase();
      if (url.includes('twitter') || url.includes('x.com')) links.twitter = link.url;
      else if (url.includes('discord')) links.discord = link.url;
      else if (url.includes('t.me') || url.includes('telegram')) links.telegram = link.url;
      else if (url.includes('github')) links.github = link.url;
    }

    return links;
  }

  private cleanDesc(desc: string): string {
    return desc
      .replace(/<[^>]*>/g, '')
      .replace(/&[a-z]+;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 300);
  }
}