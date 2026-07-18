import axios from 'axios';
import { AirdropProject } from '../types';
import { generateId } from '../utils';

interface AlphaDrop {
  id: string;
  name: string;
  slug: string;
  categories: string[];
  blockchains: string[];
  shortDescription: string;
  description: string;
  logo: string;
  fundingAmount: string | null;
  isFreeAccess: boolean;
  isClaimable: boolean;
  claimLink: string | null;
  claimDeadline: string | null;
  estimatedValue: string | null;
  status: string;
  featured: boolean;
  addedDate: string;
  website: string | null;
  socialTwitter: string | null;
  socialDiscord: string | null;
  premiumOnly: boolean;
  tasks: any[];
  suggestedTasks: any[];
}

export class AlphaDropsSource {
  async fetchAirdrops(): Promise<AirdropProject[]> {
    try {
      const res = await axios.get<AlphaDrop[]>('https://alphadrops.net/api/airdrops', {
        headers: { 'Accept': 'application/json', 'User-Agent': 'DroperOG/1.0' },
        timeout: 15000,
      });

      const data = res.data;
      if (!Array.isArray(data)) return [];

      const threeMonthsAgo = Date.now() - 90 * 24 * 60 * 60 * 1000;

      return data
        .filter(a => !a.premiumOnly && a.status !== 'ended')
        .filter(a => new Date(a.addedDate).getTime() > threeMonthsAgo)
        .map(a => this.toProject(a));
    } catch (err: any) {
      console.error(`  [AlphaDrops] Error: ${err.message}`);
      return [];
    }
  }

  private toProject(a: AlphaDrop): AirdropProject {
    const chains = (a.blockchains || []).map(b => b.toLowerCase().replace(/\s+/g, ''));
    const status = this.mapStatus(a.status, a.isClaimable);

    const descParts = [
      a.shortDescription,
      a.categories?.length ? `Categories: ${a.categories.join(', ')}` : '',
      a.fundingAmount ? `Funding: ${a.fundingAmount}` : '',
      a.estimatedValue ? `Est. value: ${a.estimatedValue}` : '',
    ].filter(Boolean);

    const links: Record<string, string> = {};
    if (a.website) links.website = a.website;
    if (a.socialTwitter) links.twitter = `https://twitter.com/${a.socialTwitter}`;
    if (a.socialDiscord) links.discord = a.socialDiscord;
    if (a.claimLink) links.claim = a.claimLink;

    const tasks = [
      ...(a.tasks || []).map((t: any) => t.title || t.description || ''),
      ...(a.suggestedTasks || []).map((t: any) => t.title || t.description || ''),
    ].filter(Boolean).join(', ');

    return {
      id: generateId('ad'),
      name: a.name,
      description: descParts.join(' | ') + (tasks ? ` | Tasks: ${tasks}` : ''),
      source: 'web_scrape',
      sourceUrl: `https://alphadrops.net/airdrops/${a.slug}`,
      chains: chains.length > 0 ? chains : ['unknown'],
      status,
      trustScore: this.calcTrust(a),
      scamFlags: [],
      links,
      discoveredAt: new Date(a.addedDate).getTime(),
      lastChecked: Date.now(),
    };
  }

  private mapStatus(status: string, claimable: boolean): AirdropProject['status'] {
    if (claimable || status === 'claim') return 'active';
    if (status === 'active') return 'active';
    if (status === 'upcoming') return 'upcoming';
    return 'unknown';
  }

  private calcTrust(a: AlphaDrop): number {
    let score = 55;
    if (a.featured) score += 10;
    if (a.fundingAmount && a.fundingAmount !== 'Undisclosed' && a.fundingAmount !== 'Hidden') score += 10;
    if (a.isClaimable) score += 10;
    if (a.claimLink) score += 5;
    if (a.website) score += 5;
    if (a.categories?.length > 0) score += 5;
    if (a.blockchains?.length > 0) score += 5;
    return Math.min(score, 95);
  }
}