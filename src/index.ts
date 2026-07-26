import { RSSSource } from './sources/rss';
import { TwitterSource } from './sources/twitter';
import { AlphaDropsSource } from './sources/alphadrops';
import { CryptoRankSource } from './sources/cryptorank';
import { TrustChecker } from './trustChecker';
import { ChecklistManager } from './checklist';
import { WalletAnalyzer } from './walletAnalyzer';
import { loadConfig } from './config';
import { AirdropProject, ProjectChecklist, SearchFilter } from './types';
import { emojiForStatus, chainToEmoji, bar, truncate, getTimeAgo } from './utils';

export class DroperOG {
  private rss: RSSSource;
  private twitter: TwitterSource;
  private cryptorank: CryptoRankSource;
  private alphadrops: AlphaDropsSource;
  private trustChecker: TrustChecker;
  private checklist: ChecklistManager;
  private walletAnalyzer: WalletAnalyzer;
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
    this.checklist = new ChecklistManager();
    this.walletAnalyzer = new WalletAnalyzer();
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

    // Filter projects older than 6 months
    const sixMonthsAgo = Date.now() - 180 * 24 * 60 * 60 * 1000;
    const before = allProjects.length;
    allProjects = allProjects.filter(p => p.discoveredAt >= sixMonthsAgo);
    if (allProjects.length < before) {
      console.log(`  🗑️ Removed ${before - allProjects.length} projects older than 6 months`);
    }

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

    // Generate checklists for all projects
    for (const p of this.projects) {
      this.checklist.getOrCreate(p);
    }

    // Show deadline alerts
    this.checklist.printDeadlineAlerts();

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

  async analyzeWallet(address: string): Promise<void> {
    console.log(`\n  🔍 Analyzing wallet: ${address}\n`);
    try {
      const profile = await this.walletAnalyzer.analyzeWallet(address);
      const eligible = this.walletAnalyzer.estimateEligibility(profile, this.projects);
      this.walletAnalyzer.printAnalysis(profile, eligible);
    } catch (err: any) {
      console.error(`  ✗ Wallet analysis failed: ${err.message}`);
    }
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
        if (filter.sortBy === 'opportunityScore') return ((a.opportunityScore ?? 0) - (b.opportunityScore ?? 0)) * dir;
        if (filter.sortBy === 'expectedValue') return ((a.expectedValue ?? 0) - (b.expectedValue ?? 0)) * dir;
        if (filter.sortBy === 'valuePerHour') return ((a.valuePerHour ?? 0) - (b.valuePerHour ?? 0)) * dir;
        if (filter.sortBy === 'urgencyScore') return ((a.urgencyScore ?? 0) - (b.urgencyScore ?? 0)) * dir;
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
      const opp = p.opportunityScore ?? 50;
      const oppBar = bar(opp);
      const source = p.source === 'twitter' ? '🐦' : '🌐';
      const risk = p.scamRisk ?? 'unknown';
      const scamEmoji = risk === 'critical' ? '🔴' : risk === 'high' ? '🟠' : risk === 'medium' ? '🟡' : '🟢';

      console.log(`  ${statusEmoji} ${p.name} ${source}`);
      console.log(`     ├─ Trust: ${trust} ${p.trustScore}%`);
      console.log(`     ├─ Opportunity: ${oppBar} ${opp}%`);
      console.log(`     ├─ Chain: ${chains || '?'}`);
      console.log(`     ├─ Status: ${p.status}  |  Risk: ${scamEmoji} ${risk}`);
      console.log(`     ├─ Legitimacy: ${p.legitimacyScore ?? '?'}%  |  Reward: ${p.rewardPotential ?? '?'}%`);
      console.log(`     ├─ Effort: ${p.effortScore ?? '?'}%  |  Urgency: ${p.urgencyScore ?? '?'}%`);
      const ev = p.expectedValue ?? 0;
      if (ev > 0) console.log(`     ├─ Est. Value: $${ev}  |  $${p.valuePerHour ?? 0}/hr`);
      if (p.tokenInfo?.symbol) console.log(`     ├─ Token: ${p.tokenInfo.symbol}`);
      console.log(`     ├─ Link: ${p.sourceUrl}`);
      if (p.links?.twitter) console.log(`     ├─ 🐦: ${p.links.twitter}`);
      console.log(`     ├─ Found: ${getTimeAgo(p.discoveredAt)}`);
      // Checklist progress
      const cl = this.checklist.getProjectChecklist(p.id);
      if (cl && cl.items.length > 0) {
        const done = cl.items.filter(i => i.completed).length;
        const total = cl.items.length;
        const checkEmoji = done === total ? '✅' : '📋';
        console.log(`     ├─ ${checkEmoji} ${done}/${total} tasks`);
      }

      if (p.linkWarnings && p.linkWarnings.length > 0) {
        const high = p.linkWarnings.filter(w => w.severity === 'high' || w.severity === 'critical');
        const countText = high.length > 0 ? `${p.linkWarnings.length} warning(s) — ${high.length} critical` : `${p.linkWarnings.length} warning(s)`;
        console.log(`     ├─ 🔗 ${countText}`);
        if (p.linkWarnings.length <= 3) {
          for (const w of p.linkWarnings) {
            const emoji = w.severity === 'critical' ? '🔴' : w.severity === 'high' ? '🟠' : '🟡';
            console.log(`     │  ${emoji} [${w.field}] ${w.reason}`);
          }
        }
      }
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

    const avgOpportunity = total > 0 ? Math.round(this.projects.reduce((s, p) => s + (p.opportunityScore ?? 0), 0) / total) : 0;
    const highValue = this.projects.filter(p => (p.expectedValue ?? 0) >= 500).length;
    const lowRisk = this.projects.filter(p => p.scamRisk === 'low' || p.scamRisk === 'medium').length;
    const urgent = this.projects.filter(p => (p.urgencyScore ?? 0) >= 70).length;
    const linkWarnings = this.projects.reduce((s, p) => s + (p.linkWarnings?.length ?? 0), 0);

    console.log(`\n${'='.repeat(42)}`);
    console.log('  DroperOG Scoring Summary');
    console.log(`${'='.repeat(42)}`);
    console.log(`  Total:         ${total}`);
    console.log(`  Trusted:       ${trusted} ✅`);
    console.log(`  Potential:     ${potential} 💎`);
    console.log(`  Confirmed:     ${confirmed} ✅`);
    console.log(`  Active:        ${active} 🟢`);
    console.log(`  Avg Opp.:      ${avgOpportunity}%`);
    console.log(`  High Value:    ${highValue} 💰`);
    console.log(`  Low Risk:      ${lowRisk} 🟢`);
    console.log(`  Urgent:        ${urgent} ⏰`);
    console.log(`  Link Warnings: ${linkWarnings} 🔗`);
    const clStats = this.checklist.getStats();
    if (clStats.total > 0) {
      console.log(`  Tasks:         ${clStats.completed}/${clStats.total} ✅`);
      if (clStats.deadlinesNear > 0) console.log(`  Deadlines:     ${clStats.deadlinesNear} approaching ⏰`);
    }
    console.log(`${'='.repeat(42)}\n`);
  }
}

async function main() {
  const app = new DroperOG();
  const args = process.argv.slice(2);

  const walletIdx = args.indexOf('--wallet');
  if (walletIdx !== -1 && walletIdx + 1 < args.length) {
    await app.runOnce();
    await app.analyzeWallet(args[walletIdx + 1]);
    return;
  }

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