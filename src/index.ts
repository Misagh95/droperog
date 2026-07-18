import { RSSSource } from './sources/rss';
import { TwitterSource } from './sources/twitter';
import { AlphaDropsSource } from './sources/alphadrops';
import { CryptoRankSource } from './sources/cryptorank';
import { TrustChecker } from './trustChecker';
import { loadConfig } from './config';
import { AirdropProject, SearchFilter } from './types';
import { emojiForStatus, chainToEmoji, bar, truncate, getTimeAgo } from './utils';

export class DroperOG {
  private rss: RSSSource;
  private twitter: TwitterSource;
  private cryptorank: CryptoRankSource;
  private alphadrops: AlphaDropsSource;
  private trustChecker: TrustChecker;
  private config = loadConfig();
  projects: AirdropProject[] = [];
  knownIds = new Set<string>();

  constructor(apiKey?: string) {
    this.rss = new RSSSource([
      'https://airdrops.io/feed/',
    ]);
    this.twitter = new TwitterSource([
      'AirdropAlert',
      'airdrops_io',
      'airdrops_king',
    ]);
    this.cryptorank = new CryptoRankSource();
    this.alphadrops = new AlphaDropsSource();
    this.trustChecker = new TrustChecker();
  }

  async runOnce(): Promise<AirdropProject[]> {
    console.log(`\n${'='.repeat(56)}`);
    console.log('   DroperOG - Airdrop Hunter');
    console.log(`${'='.repeat(56)}\n`);

    console.log('  🔍 Scanning sources...\n');

    const [rss, twitter, cryptoRank, alphaDrops] = await Promise.all([
      this.scrapeWithLog('RSS', () => this.rss.fetchAll()),
      this.scrapeWithLog('Twitter', () => this.twitter.fetchLatest()),
      this.scrapeWithLog('CryptoRank', () => this.cryptorank.fetchAirdrops()),
      this.scrapeWithLog('AlphaDrops', () => this.alphadrops.fetchAirdrops()),
    ]);

    let allProjects = [...rss, ...twitter, ...cryptoRank, ...alphaDrops];

    // Deduplicate
    const seen = new Set<string>();
    allProjects = allProjects.filter(p => {
      const key = p.name.toLowerCase().trim();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    // Filter noise
    allProjects = allProjects.filter(p => {
      const noise = [/^top\s+\d+/i, /^\d{4}/, /upcoming airdrops/i];
      for (const pat of noise) { if (pat.test(p.name)) return false; }
      if (p.name.length > 60 || p.name.length < 2) return false;
      if (!/[a-zA-Z]/.test(p.name)) return false;
      return true;
    });

    // Trust check & sort by newest
    allProjects = this.trustChecker.checkMultiple(allProjects);
    allProjects.sort((a, b) => b.discoveredAt - a.discoveredAt);

    // Track new
    const newProjects: AirdropProject[] = [];
    for (const p of allProjects) {
      if (!this.knownIds.has(p.id)) {
        newProjects.push(p);
        this.knownIds.add(p.id);
      }
    }

    // Merge
    for (const p of allProjects) {
      const existing = this.projects.find(e => e.name.toLowerCase() === p.name.toLowerCase());
      if (existing) Object.assign(existing, p, { discoveredAt: existing.discoveredAt });
      else this.projects.push(p);
    }

    if (newProjects.length > 0) {
      console.log(`\n  🆕 ${newProjects.length} New Projects Found!\n`);
      this.printProjects(newProjects);
    }

    console.log(`  📊 Total tracked: ${this.projects.length} projects`);
    console.log(`  ⏰ Last check: ${new Date().toLocaleTimeString()}\n`);

    return newProjects;
  }

  private async scrapeWithLog(name: string, fn: () => Promise<AirdropProject[]>): Promise<AirdropProject[]> {
    try {
      const result = await fn();
      console.log(`  ✓ ${name}: ${result.length} projects`);
      return result;
    } catch (err: any) {
      console.error(`  ✗ ${name}: ${err.message}`);
      return [];
    }
  }

  async start(intervalMs?: number): Promise<void> {
    const interval = intervalMs || this.config.checkInterval;
    await this.runOnce();
    console.log(`  🔄 Auto-check every ${Math.round(interval / 60000)} minutes.\n`);
    setInterval(() => {
      this.runOnce().catch(err => console.error('Error:', err.message));
    }, interval);
  }

  find(filter: SearchFilter = {}): AirdropProject[] {
    let result = [...this.projects];

    if (filter.chains && filter.chains.length > 0) {
      result = result.filter(p => p.chains.some(c => filter.chains!.includes(c.toLowerCase())));
    }
    if (filter.minTrustScore !== undefined) {
      result = result.filter(p => p.trustScore >= filter.minTrustScore!);
    }
    if (filter.status && filter.status.length > 0) {
      result = result.filter(p => filter.status!.includes(p.status));
    }
    if (filter.sortBy) {
      result.sort((a, b) => {
        const dir = filter.sortDir === 'asc' ? 1 : -1;
        if (filter.sortBy === 'trustScore') return (a.trustScore - b.trustScore) * dir;
        if (filter.sortBy === 'discoveredAt') return (a.discoveredAt - b.discoveredAt) * dir;
        return a.name.localeCompare(b.name) * dir;
      });
    }
    if (filter.limit) result = result.slice(0, filter.limit);
    return result;
  }

  printProjects(projects: AirdropProject[]): void {
    if (projects.length === 0) { console.log('  No projects found.'); return; }

    for (const p of projects) {
      const statusEmoji = emojiForStatus(p.status);
      const chains = p.chains.map(c => chainToEmoji(c)).join(' ');
      const trust = bar(p.trustScore);
      const source = p.source === 'twitter' ? '🐦' : '🌐';

      console.log(`  ${statusEmoji} ${p.name} ${source}`);
      console.log(`     ├─ Trust: ${trust} ${p.trustScore}%`);
      console.log(`     ├─ Chain: ${chains || '?'}`);
      console.log(`     ├─ Status: ${p.status}`);
      if (p.tokenInfo?.symbol) console.log(`     ├─ Token: ${p.tokenInfo.symbol}`);
      console.log(`     ├─ Link: ${p.sourceUrl}`);
      if (p.links?.twitter) console.log(`     ├─ 🐦: ${p.links.twitter}`);
      console.log(`     ├─ Found: ${getTimeAgo(p.discoveredAt)}`);
      if (p.scamFlags.length > 0) {
        console.log(`     ╰─ ⚠️  ${p.scamFlags.join(', ')}`);
      } else {
        console.log(`     ╰─ ✅ No red flags`);
      }
      if (p.description && p.description.length > 10) {
        console.log(`     📝 ${truncate(p.description, 80)}`);
      }
      console.log('');
    }
  }

  printSummary(): void {
    const total = this.projects.length;
    const trusted = this.projects.filter(p => p.trustScore >= 70).length;
    const potential = this.projects.filter(p => p.status === 'potential').length;
    const confirmed = this.projects.filter(p => p.status === 'confirmed').length;
    const active = this.projects.filter(p => p.status === 'active').length;

    console.log(`\n${'='.repeat(36)}`);
    console.log('  DroperOG Summary');
    console.log(`${'='.repeat(36)}`);
    console.log(`  Total:     ${total}`);
    console.log(`  Trusted:   ${trusted} ✅`);
    console.log(`  Potential: ${potential} 💎`);
    console.log(`  Confirmed: ${confirmed} ✅`);
    console.log(`  Active:    ${active} 🟢`);
    console.log(`${'='.repeat(36)}\n`);
  }
}

async function main() {
  const app = new DroperOG();
  const args = process.argv.slice(2);

  if (args.includes('--once')) {
    await app.runOnce();
    app.printSummary();
  } else {
    await app.start();
  }
}

if (require.main === module) {
  main().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

export default DroperOG;