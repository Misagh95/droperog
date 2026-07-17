import axios from 'axios';
import { AirdropProject } from '../types';
import { generateId, extractChains } from '../utils';

interface RSSFeed {
  title: string;
  description: string;
  link: string;
  pubDate: string;
  content?: string;
  contentSnippet?: string;
}

export class RSSSource {
  private feeds: string[];

  constructor(feeds: string[]) {
    this.feeds = feeds;
  }

  async fetchAll(): Promise<AirdropProject[]> {
    const all: AirdropProject[] = [];

    for (const url of this.feeds) {
      try {
        console.log(`  [RSS] Fetching ${url}...`);
        const items = await this.parseRSS(url);
        const projects = items
          .map(item => this.rssToProject(item, url))
          .filter(p => p !== null) as AirdropProject[];
        all.push(...projects);
        console.log(`  [RSS] Found ${projects.length} items`);
      } catch (err: any) {
        console.error(`  [RSS] ${url}: ${err.message}`);
      }
    }

    return all;
  }

  private async parseRSS(url: string): Promise<RSSFeed[]> {
    // Fetch RSS as XML and parse manually (supports RSS 2.0 and Atom)
    const res = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml',
      },
      timeout: 15000,
    });

    const xml = res.data;
    const items: RSSFeed[] = [];

    // Simple regex-based RSS/Atom parser
    // Match <item> (RSS 2.0) or <entry> (Atom)
    const itemRegex = /<(?:item|entry)>[\s\S]*?<\/(?:item|entry)>/gi;
    const matches = xml.matchAll(itemRegex);

    for (const match of matches) {
      const block = match[0];
      items.push({
        title: this.extractTag(block, 'title'),
        description: this.extractTag(block, 'description') || this.extractTag(block, 'summary'),
        link: this.extractTag(block, 'link') || this.extractHref(block),
        pubDate: this.extractTag(block, 'pubDate') || this.extractTag(block, 'published'),
        content: this.extractTag(block, 'content:encoded') || this.extractTag(block, 'content'),
        contentSnippet: this.extractTag(block, 'content:encoded')?.replace(/<[^>]*>/g, '').slice(0, 300),
      });
    }

    return items;
  }

  private extractTag(xml: string, tag: string): string {
    // Try CDATA first
    const cdataRegex = new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`, 'i');
    const cdataMatch = xml.match(cdataRegex);
    if (cdataMatch) return cdataMatch[1].trim();

    // Try regular content
    const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
    const match = xml.match(regex);
    if (!match) return '';

    // Decode HTML entities
    return match[1]
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#039;/g, "'")
      .replace(/&#8217;/g, "'")
      .replace(/&#8211;/g, "-")
      .replace(/&#038;/g, "&")
      .trim();
  }

  private extractHref(xml: string): string {
    // Try <link> with href attribute (Atom)
    const atomMatch = xml.match(/<link[^>]*href="([^"]+)"[^>]*\/?>/i);
    if (atomMatch) return atomMatch[1];

    // Try <link> with just text content (RSS)
    const rssMatch = xml.match(/<link[^>]*>([^<]+)<\/link>/i);
    if (rssMatch) return rssMatch[1].trim();

    return '';
  }

  private rssToProject(item: RSSFeed, feedUrl: string): AirdropProject | null {
    const text = `${item.title} ${item.description} ${item.contentSnippet || ''}`.toLowerCase();

    // Skip items that aren't about airdrops
    if (!this.isAirdropRelated(text)) return null;

    const name = this.extractProjectName(item.title || '');
    if (!name) return null;

    const allText = `${item.title} ${item.description} ${item.contentSnippet || ''}`;
    const chains = extractChains(allText);

    return {
      id: generateId('rss'),
      name,
      description: item.contentSnippet || item.description || 'No description',
      source: 'web_scrape',
      sourceUrl: item.link || feedUrl,
      chains: chains.length > 0 ? chains : ['unknown'],
      status: this.guessStatus(allText),
      trustScore: 55,
      scamFlags: [],
      links: {},
      discoveredAt: item.pubDate ? new Date(item.pubDate).getTime() : Date.now(),
      lastChecked: Date.now(),
    };
  }

  private isAirdropRelated(text: string): boolean {
    const keywords = [
      'airdrop', 'retrodrop', 'token claim', 'claim token',
      'free token', 'community distribution', 'protocol launch',
      'defi launch', 'governance token', 'new listing',
      'native token', 'ecosystem fund', 'reward distribution',
      'farming reward', 'liquidity', 'staking reward',
      'double dip', 'potential airdrop',
    ];
    return keywords.some(k => text.includes(k));
  }

  private extractProjectName(title: string): string | null {
    // Try to extract project name from title like "ProjectName Airdrop: Claim Your Tokens"
    const clean = title
      .replace(/<[^>]*>/g, '')
      .replace(/&[a-z]+;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    if (!clean || clean.length < 3) return null;

    // Remove common prefixes/suffixes
    let name = clean;
    const prefixes = ['Airdrop:', 'Claim:', 'New:', 'Latest:', 'Upcoming:'];
    for (const p of prefixes) {
      if (name.startsWith(p)) {
        name = name.slice(p.length).trim();
        break;
      }
    }

    return name;
  }

  private guessStatus(text: string): AirdropProject['status'] {
    const t = text.toLowerCase();
    if (t.includes('ended') || t.includes('finished') || t.includes('closed')) return 'ended';
    if (t.includes('active') || t.includes('live') || t.includes('claim now')) return 'active';
    if (t.includes('upcoming') || t.includes('soon') || t.includes('announced') || t.includes('new')) return 'upcoming';
    return 'unknown';
  }
}