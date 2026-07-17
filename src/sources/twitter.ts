import axios from 'axios';
import { AirdropProject } from '../types';
import { generateId, extractChains, cleanText } from '../utils';

const NITTER_INSTANCES = [
  'https://nitter.net',
  'https://nitter.1d4.us',
  'https://nitter.kavin.rocks',
  'https://nitter.snopyta.org',
];

interface Tweet {
  title: string;
  description: string;
  link: string;
  pubDate: string;
  content: string;
}

export class TwitterSource {
  private accounts: string[];
  private workingInstance: string | null = null;

  constructor(accounts: string[]) {
    this.accounts = accounts;
  }

  async fetchLatest(): Promise<AirdropProject[]> {
    const instance = await this.findWorkingInstance();
    if (!instance) {
      console.error('  [Twitter] No working Nitter instance found.');
      return [];
    }

    console.log(`  [Twitter] Using ${instance}`);
    const projects: AirdropProject[] = [];

    for (const account of this.accounts) {
      try {
        const tweets = await this.fetchAccountTweets(instance, account);
        for (const tweet of tweets) {
          const project = this.tweetToProject(tweet, account);
          if (project) projects.push(project);
        }
        console.log(`  [Twitter] @${account}: ${tweets.length} tweets`);
      } catch (err: any) {
        console.error(`  [Twitter] @${account}: ${err.message}`);
      }
    }

    return projects;
  }

  private async findWorkingInstance(): Promise<string | null> {
    if (this.workingInstance) return this.workingInstance;

    for (const instance of NITTER_INSTANCES) {
      try {
        await axios.head(instance, { timeout: 5000 });
        this.workingInstance = instance;
        return instance;
      } catch { continue; }
    }
    return null;
  }

  private async fetchAccountTweets(instance: string, account: string): Promise<Tweet[]> {
    // Nitter provides RSS for each account
    const rssUrl = `${instance}/${account}/rss`;
    const res = await axios.get(rssUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml',
      },
      timeout: 15000,
    });

    const xml = res.data;
    const items: Tweet[] = [];
    const itemRegex = /<(?:item|entry)>[\s\S]*?<\/(?:item|entry)>/gi;
    const matches = xml.matchAll(itemRegex);

    for (const match of matches) {
      const block = match[0];
      const title = this.extractTag(block, 'title');
      const description = this.extractTag(block, 'description') || this.extractTag(block, 'summary');
      const link = this.extractLink(block);
      const pubDate = this.extractTag(block, 'pubDate') || this.extractTag(block, 'published');
      const content = this.extractTag(block, 'content:encoded') || this.extractTag(block, 'content');

      if (title) {
        items.push({ title, description, link, pubDate, content });
      }
    }

    return items;
  }

  private extractTag(xml: string, tag: string): string {
    const cdataRegex = new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`, 'i');
    const cdataMatch = xml.match(cdataRegex);
    if (cdataMatch) return cdataMatch[1].trim();

    const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
    const match = xml.match(regex);
    return match ? match[1].trim() : '';
  }

  private extractLink(xml: string): string {
    const atomMatch = xml.match(/<link[^>]*href="([^"]+)"[^>]*\/?>/i);
    if (atomMatch) return atomMatch[1];
    const rssMatch = xml.match(/<link[^>]*>([^<]+)<\/link>/i);
    return rssMatch ? rssMatch[1].trim() : '';
  }

  private tweetToProject(tweet: Tweet, account: string): AirdropProject | null {
    const text = `${tweet.title} ${tweet.description} ${tweet.content}`.toLowerCase();

    // Skip replies
    if (tweet.title.startsWith('R to') || tweet.title.startsWith('@')) return null;

    // Must be airdrop-related
    if (!this.isAirdropTweet(text)) return null;

    // Extract project name from tweet
    const title = cleanText(tweet.title);
    const name = this.extractProjectName(title, text);
    if (!name) return null;

    const chains = extractChains(text);

    return {
      id: generateId('tw'),
      name,
      description: title.slice(0, 200),
      source: 'twitter',
      sourceUrl: tweet.link || `https://twitter.com/${account}`,
      chains: chains.length > 0 ? chains : ['unknown'],
      status: this.guessStatus(text),
      trustScore: 55,
      scamFlags: [],
      links: { twitter: `https://twitter.com/${account}` },
      discoveredAt: tweet.pubDate ? new Date(tweet.pubDate).getTime() : Date.now(),
      lastChecked: Date.now(),
    };
  }

  private isAirdropTweet(text: string): boolean {
    const keywords = [
      'airdrop', 'retrodrop', 'claim', 'token claim',
      'free token', ' $', 'launch', 'new token',
      'governance', 'protocol', 'staking',
    ];
    const count = keywords.filter(k => text.includes(k)).length;
    return count >= 2; // Must have at least 2 matching keywords
  }

  private extractProjectName(title: string, allText: string): string | null {
    // Try to find project name in format: "$TOKEN" or "Project Name"
    const dollarMatch = allText.match(/\$([A-Z0-9]{2,10})/);
    if (dollarMatch) return dollarMatch[1];

    // Look for common patterns in tweet titles
    const clean = title.replace(/^RT\s*/, '').trim();
    if (clean.length < 3 || clean.length > 80) return null;

    // Remove common tweet prefixes
    let name = clean
      .replace(/^(just|new|big|huge|🚀|🔥|💎)\s+/i, '')
      .replace(/\s+(airdrop|claim|launch).*$/i, '')
      .trim();

    // Take first meaningful part
    name = name.replace(/[^a-zA-Z0-9\s\-\.]/g, '').trim();
    if (name.length < 2) return null;

    return name.split(/\s+/).slice(0, 3).join(' ');
  }

  private guessStatus(text: string): AirdropProject['status'] {
    const t = text.toLowerCase();
    if (t.includes('live') || t.includes('open') || t.includes('claim now')) return 'active';
    if (t.includes('soon') || t.includes('upcoming') || t.includes('announced') || t.includes('new')) return 'upcoming';
    if (t.includes('ended') || t.includes('finished')) return 'ended';
    return 'unknown';
  }
}