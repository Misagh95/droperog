import axios from 'axios';
import * as cheerio from 'cheerio';
import { AirdropProject, ScrapeResult, SourceConfig } from '../types';
import { generateId } from '../utils';

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

export class Scraper {
  private sources: SourceConfig[];

  constructor(sources: SourceConfig[]) {
    this.sources = sources.filter(s => s.enabled);
  }

  async scrapeAll(): Promise<ScrapeResult[]> {
    const results: ScrapeResult[] = [];

    for (const source of this.sources) {
      try {
        console.log(`  [${source.name}] Scraping...`);
        const projects = await this.scrapeSource(source);
        results.push({ source: source.name, projects, timestamp: Date.now() });
        console.log(`  [${source.name}] Found ${projects.length} projects`);
      } catch (err: any) {
        console.error(`  [${source.name}] Error: ${err.message}`);
        results.push({ source: source.name, projects: [], error: err.message, timestamp: Date.now() });
      }
    }

    return results;
  }

  private async scrapeSource(source: SourceConfig): Promise<AirdropProject[]> {
    switch (source.name) {
      case 'airdropsio':
        return this.scrapeAirdropsIo(source);
      case 'airdropsmob':
        return this.scrapeAirdropsMob(source);
      case 'airdrops_king':
        return this.scrapeAirdropsIo(source);
      default:
        return [];
    }
  }

  private async fetchPage(url: string): Promise<string> {
    const res = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
      },
      timeout: 15000,
    });
    return res.data;
  }

  private extractChains(text: string): string[] {
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

  private extractLinks(el: cheerio.Cheerio, $: any): AirdropProject['links'] {
    const links: AirdropProject['links'] = {};
    const html = $(el).html()?.toLowerCase() || '';

    $(el).find('a').each((_: any, a: any) => {
      const href = $(a).attr('href') || '';
      const text = $(a).text().toLowerCase();

      if (href.includes('twitter.com') || href.includes('x.com') || text.includes('twitter') || text.includes('x.com')) {
        links.twitter = href;
      } else if (href.includes('discord') || text.includes('discord')) {
        links.discord = href;
      } else if (href.includes('t.me') || href.includes('telegram') || text.includes('telegram') || text.includes('t.me')) {
        links.telegram = href;
      } else if (href.includes('medium') || text.includes('medium')) {
        links.medium = href;
      } else if (!links.website && (href.startsWith('http') || href.startsWith('https'))) {
        links.website = href;
      }
    });

    return links;
  }

  private cleanText(text: string): string {
    return text
      .replace(/&[a-z]+;/g, ' ')        // HTML entities
      .replace(/[\n\r\t]+/g, ' ')        // Newlines/tabs
      .replace(/\s+/g, ' ')              // Multiple spaces
      .replace(/\s+([,.;:!?])/g, '$1')   // Space before punctuation
      .trim();
  }

  private async scrapeAirdropsIo(source: SourceConfig): Promise<AirdropProject[]> {
    const html = await this.fetchPage(source.url);
    const $ = cheerio.load(html);
    const projects: AirdropProject[] = [];

    // Try multiple common selectors
    const selectors = [
      '.airdrop-item', 'article', '.post', '.post-item',
      '.card', '[class*="airdrop"]', '[class*="post"]',
      'main > div > div', 'section > div',
      'table tr', '.entry', '.item',
    ];

    for (const sel of selectors) {
      $(sel).each((_, el) => {
        try {
          const $el = $(el);
          const name = this.cleanText($el.find('h2, h3, h4, .title, .entry-title, [class*="title"], [class*="name"]')
            .first().text());
          if (!name || name.length < 3) return;

          // Skip obviously non-crypto content
          if (this.looksLikeNoise(name, $el.text())) return;

          const desc = this.cleanText($el.find('p, .description, .excerpt, [class*="desc"], [class*="excerpt"]')
            .first().text());
          const link = $el.find('a').first().attr('href') || source.url;
          const allText = `${name} ${desc} ${$el.text()}`;
          const chains = this.extractChains(allText);
          const links = this.extractLinks($el, $);

          projects.push({
            id: generateId('adrops'),
            name,
            description: desc || 'No description',
            source: 'web_scrape',
            sourceUrl: link.startsWith('http') ? link : `${source.url}${link}`,
            chains: chains.length > 0 ? chains : ['unknown'],
            status: this.guessStatus(allText),
            trustScore: 50,
            scamFlags: [],
            links,
            discoveredAt: Date.now(),
            lastChecked: Date.now(),
          });
        } catch { /* skip */ }
      });
      if (projects.length > 0) break; // Stop if we found items
    }

    return projects;
  }

  private async scrapeAlphaDrops(source: SourceConfig): Promise<AirdropProject[]> {
    try {
      const html = await this.fetchPage(source.url);
      const $ = cheerio.load(html);
      const projects: AirdropProject[] = [];

      // Try to find airdrop-like content
      const selectors = [
        '[class*="airdrop"]', '[class*="project"]', '[class*="card"]',
        '[class*="item"]', 'article', '.post', 'table tr',
      ];

      for (const sel of selectors) {
        $(sel).each((_, el) => {
          try {
            const $el = $(el);
            const name = $el.find('h2, h3, h4, [class*="title"], [class*="name"]')
              .first().text().trim();
            if (!name || name.length < 3) return;
            if (this.looksLikeNoise(name, $el.text())) return;

            const desc = $el.find('p, [class*="desc"], [class*="text"]')
              .first().text().trim();
            const link = $el.find('a').first().attr('href') || source.url;
            const allText = `${name} ${desc} ${$el.text()}`;

            // Only include if it mentions crypto/airdrop related terms
            if (!this.isCryptoRelated(allText)) return;

            const chains = this.extractChains(allText);
            const links = this.extractLinks($el, $);

            projects.push({
              id: generateId('alpha'),
              name,
              description: desc || 'No description',
              source: 'web_scrape',
              sourceUrl: link.startsWith('http') ? link : `${source.url}${link}`,
              chains: chains.length > 0 ? chains : ['unknown'],
              status: this.guessStatus(allText),
              trustScore: 50,
              scamFlags: [],
              links,
              discoveredAt: Date.now(),
              lastChecked: Date.now(),
            });
          } catch { /* skip */ }
        });
        if (projects.length > 0) break;
      }

      return projects;
    } catch {
      return [];
    }
  }

  private async scrapeEarndefi(source: SourceConfig): Promise<AirdropProject[]> {
    try {
      const html = await this.fetchPage(source.url);
      const $ = cheerio.load(html);
      const projects: AirdropProject[] = [];

      const selectors = [
        'article', '[class*="airdrop"]', '[class*="post"]',
        '[class*="card"]', 'table tr', '[class*="item"]',
      ];

      for (const sel of selectors) {
        $(sel).each((_, el) => {
          try {
            const $el = $(el);
            const name = $el.find('h2, h3, h4, .title, [class*="title"]')
              .first().text().trim();
            if (!name || name.length < 3) return;
            if (this.looksLikeNoise(name, $el.text())) return;

            const allText = `${name} ${$el.text()}`;
            if (!this.isCryptoRelated(allText)) return;

            const desc = $el.find('p, [class*="desc"], [class*="excerpt"]')
              .first().text().trim();
            const link = $el.find('a').first().attr('href') || source.url;
            const chains = this.extractChains(allText);
            const links = this.extractLinks($el, $);

            projects.push({
              id: generateId('earn'),
              name,
              description: desc || 'No description',
              source: 'web_scrape',
              sourceUrl: link.startsWith('http') ? link : `${source.url}${link}`,
              chains: chains.length > 0 ? chains : ['unknown'],
              status: this.guessStatus(allText),
              trustScore: 50,
              scamFlags: [],
              links,
              discoveredAt: Date.now(),
              lastChecked: Date.now(),
            });
          } catch { /* skip */ }
        });
        if (projects.length > 0) break;
      }

      return projects;
    } catch {
      return [];
    }
  }

  private async scrapeAirdropAlert(source: SourceConfig): Promise<AirdropProject[]> {
    try {
      const html = await this.fetchPage(source.url);
      const $ = cheerio.load(html);
      const projects: AirdropProject[] = [];

      const selectors = ['[class*="card"]', '[class*="item"]', 'article', 'table tr', '[class*="event"]'];
      for (const sel of selectors) {
        $(sel).each((_, el) => {
          try {
            const $el = $(el);
            const name = $el.find('h2, h3, h4, .title, [class*="title"], [class*="name"]').first().text().trim();
            if (!name || name.length < 3) return;
            if (this.looksLikeNoise(name, $el.text())) return;

            const allText = `${name} ${$el.text()}`;
            if (!this.isCryptoRelated(allText)) return;

            projects.push({
              id: generateId('alert'),
              name,
              description: $el.find('p, [class*="desc"]').first().text().trim() || 'No description',
              source: 'web_scrape',
              sourceUrl: $el.find('a').first().attr('href') || source.url,
              chains: this.extractChains(allText),
              status: this.guessStatus(allText),
              trustScore: 50,
              scamFlags: [],
              links: this.extractLinks($el, $),
              discoveredAt: Date.now(),
              lastChecked: Date.now(),
            });
          } catch { /* skip */ }
        });
        if (projects.length > 0) break;
      }
      return projects;
    } catch { return []; }
  }

  private async scrapeAirdropsMob(source: SourceConfig): Promise<AirdropProject[]> {
    try {
      const html = await this.fetchPage(source.url);
      const $ = cheerio.load(html);
      const projects: AirdropProject[] = [];

      const selectors = ['article', '[class*="post"]', '[class*="card"]', '[class*="item"]', '[class*="airdrop"]'];
      for (const sel of selectors) {
        $(sel).each((_, el) => {
          try {
            const $el = $(el);
            const name = $el.find('h2, h3, h4, .title, [class*="title"]').first().text().trim();
            if (!name || name.length < 3) return;
            if (this.looksLikeNoise(name, $el.text())) return;

            const allText = `${name} ${$el.text()}`;
            if (!this.isCryptoRelated(allText)) return;

            projects.push({
              id: generateId('mob'),
              name,
              description: $el.find('p, [class*="desc"], [class*="excerpt"]').first().text().trim() || 'No description',
              source: 'web_scrape',
              sourceUrl: $el.find('a').first().attr('href') || source.url,
              chains: this.extractChains(allText),
              status: this.guessStatus(allText),
              trustScore: 50,
              scamFlags: [],
              links: this.extractLinks($el, $),
              discoveredAt: Date.now(),
              lastChecked: Date.now(),
            });
          } catch { /* skip */ }
        });
        if (projects.length > 0) break;
      }
      return projects;
    } catch { return []; }
  }

  private isCryptoRelated(text: string): boolean {
    const lower = text.toLowerCase();
    const keywords = [
      'airdrop', 'token', 'crypto', 'blockchain', 'defi', 'yield', 'stake',
      'swap', 'bridge', 'protocol', 'dao', 'nft', 'web3', 'wallet',
      'launch', 'retrodrop', 'claim', 'vesting', 'tge', 'presale',
      'liquid', 'stake', 'farm', 'pool', 'lend', 'borrow',
    ];
    // Must contain at least one crypto keyword
    return keywords.some(k => lower.includes(k));
  }

  private looksLikeNoise(name: string, allText: string): boolean {
    const lower = `${name} ${allText}`.toLowerCase();
    // Remove HTML-like entities from text for checking
    const clean = lower.replace(/&[a-z]+;/g, ' ').replace(/\s+/g, ' ');
    const noiseKeywords = [
      'shipping', 'packaging', 'toy', 'kids', 'baby', 'toddler',
      'book', 'kitchen', 'bathroom', 'garden', 'fitness', 'health',
      'product review', 'amazon', 'buy now', 'shop', 'cart',
      'delhi', 'bangalore', 'mumbai', 'pune', 'reviewer',
      'essentials', 'premium', 'coupon', 'discount 202', 'best crypto',
    ];
    let noiseCount = 0;
    for (const kw of noiseKeywords) {
      if (clean.includes(kw)) noiseCount++;
      if (noiseCount >= 2) return true;
    }
    return false;
  }

  private guessStatus(text: string): AirdropProject['status'] {
    const t = text.toLowerCase();
    if (t.includes('ended') || t.includes('finished') || t.includes('closed')) return 'ended';
    if (t.includes('active') || t.includes('live') || t.includes('claim now')) return 'active';
    if (t.includes('upcoming') || t.includes('soon') || t.includes('coming') || t.includes('new')) return 'upcoming';
    if (t.includes('claimed')) return 'claimed';
    return 'unknown';
  }
}