import axios from 'axios';
import { AirdropProject } from '../types';
import { generateId, extractChains } from '../utils';

const API_BASE = 'https://api.coingecko.com/api/v3';

interface CoinGeckoCoin {
  id: string;
  symbol: string;
  name: string;
  market_cap_rank?: number;
  large?: string;
  thumb?: string;
}

interface CoinGeckoSearchResult {
  coins: CoinGeckoCoin[];
  exchanges: any[];
  categories: any[];
  nfts: any[];
}

interface CoinDetails {
  id: string;
  name: string;
  symbol: string;
  description: { en: string };
  links: {
    twitter_screen_name?: string;
    telegram_channel_identifier?: string;
    subreddit_url?: string;
    homepage: string[];
  };
  categories: string[];
  genesis_date?: string;
}

export class CoinGeckoSource {
  private cache: Set<string> = new Set();

  async fetchAirdropCandidates(): Promise<AirdropProject[]> {
    const projects: AirdropProject[] = [];

    // Search for airdrop-related keywords
    const keywords = ['airdrop', 'retrodrop', 'claim', 'governance token'];
    
    for (const keyword of keywords) {
      try {
        const results = await this.searchKeyword(keyword);
        for (const coin of results) {
          if (this.cache.has(coin.id)) continue;
          this.cache.add(coin.id);

          const detail = await this.getCoinDetails(coin.id);
          if (!detail) continue;

          const allText = `${detail.name} ${detail.symbol} ${detail.description?.en || ''} ${detail.categories?.join(' ') || ''}`.toLowerCase();
          const chains = extractChains(allText);
          const links = this.extractLinks(detail);

          projects.push({
            id: generateId('cg'),
            name: detail.name,
            description: this.cleanDesc(detail.description?.en || ''),
            source: 'web_scrape',
            sourceUrl: links.website || `https://www.coingecko.com/en/coins/${detail.id}`,
            chains: chains.length > 0 ? chains : ['unknown'],
            status: 'upcoming',
            trustScore: 55,
            scamFlags: [],
            links,
            tokenInfo: { symbol: detail.symbol.toUpperCase(), name: detail.name, chain: chains[0] || 'unknown' },
            discoveredAt: Date.now(),
            lastChecked: Date.now(),
          });
        }
      } catch (err: any) {
        console.error(`  [CoinGecko] Search '${keyword}': ${err.message}`);
        if (err.response?.status === 429) {
          console.error('  [CoinGecko] Rate limited. Will retry later.');
          break;
        }
      }
    }

    // Also get trending coins (often have recent airdrops)
    try {
      const trending = await this.getTrending();
      for (const coin of trending) {
        if (this.cache.has(coin.id)) continue;
        this.cache.add(coin.id);

        const allText = `${coin.name} ${coin.symbol}`.toLowerCase();
        
        projects.push({
          id: generateId('cg_tr'),
          name: coin.name,
          description: `${coin.name} (${coin.symbol.toUpperCase()}) - Trending on CoinGecko`,
          source: 'web_scrape',
          sourceUrl: `https://www.coingecko.com/en/coins/${coin.id}`,
          chains: extractChains(allText),
          status: 'upcoming',
          trustScore: 50,
          scamFlags: [],
          links: {},
          tokenInfo: { symbol: coin.symbol.toUpperCase(), name: coin.name, chain: 'unknown' },
          discoveredAt: Date.now(),
          lastChecked: Date.now(),
        });
      }
    } catch (err: any) {
      if (err.response?.status !== 429) {
        console.error(`  [CoinGecko] Trending: ${err.message}`);
      }
    }

    return projects;
  }

  private async searchKeyword(keyword: string): Promise<CoinGeckoCoin[]> {
    const res = await axios.get<CoinGeckoSearchResult>(`${API_BASE}/search`, {
      params: { query: keyword },
      headers: { 'Accept': 'application/json' },
      timeout: 10000,
    });
    return res.data.coins || [];
  }

  private async getCoinDetails(coinId: string): Promise<CoinDetails | null> {
    try {
      const res = await axios.get<CoinDetails>(`${API_BASE}/coins/${coinId}`, {
        params: {
          localization: 'false',
          tickers: 'false',
          market_data: 'false',
          community_data: 'false',
          developer_data: 'false',
          sparkline: 'false',
        },
        headers: { 'Accept': 'application/json' },
        timeout: 10000,
      });
      return res.data;
    } catch {
      return null;
    }
  }

  private async getTrending(): Promise<CoinGeckoCoin[]> {
    const res = await axios.get<{ coins: { item: CoinGeckoCoin }[] }>(`${API_BASE}/search/trending`, {
      headers: { 'Accept': 'application/json' },
      timeout: 10000,
    });

    const SKIP_COINS = new Set([
      'bitcoin', 'ethereum', 'solana', 'litecoin', 'ripple',
      'cardano', 'polkadot', 'dogecoin', 'avalanche', 'chainlink',
      'polygon', 'tron', 'toncoin', 'stellar', 'vechain',
      'internet-computer', 'near', 'aptos', 'cronos', 'algorand',
    ]);

    return (res.data?.coins || [])
      .map(c => c.item)
      .filter(c => !SKIP_COINS.has(c.id));
  }

  private extractLinks(coin: CoinDetails): AirdropProject['links'] {
    const links: AirdropProject['links'] = {};
    if (coin.links?.homepage?.[0]) links.website = coin.links.homepage[0];
    if (coin.links?.twitter_screen_name) links.twitter = `https://twitter.com/${coin.links.twitter_screen_name}`;
    if (coin.links?.telegram_channel_identifier) links.telegram = `https://t.me/${coin.links.telegram_channel_identifier}`;
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