import axios from 'axios';
import { AirdropProject, FearGreedData, GasData, NewListing } from './types';
import { emojiForStatus, chainToEmoji, bar } from './utils';

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const CHAT_ID = process.env.TELEGRAM_CHAT_ID || '';

export class TelegramNotifier {
  private enabled: boolean;
  private notifiedUrgent = new Set<string>();
  private notifiedRisky = new Set<string>();

  constructor() {
    this.enabled = !!(BOT_TOKEN && CHAT_ID);
    if (!this.enabled) {
      console.log('  [Telegram] Disabled — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID');
    }
  }

  async sendMessage(text: string): Promise<void> {
    if (!this.enabled) return;
    try {
      await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        chat_id: CHAT_ID,
        text,
        parse_mode: 'HTML',
        disable_web_page_preview: true,
      }, { timeout: 10000 });
    } catch (err: any) {
      console.error(`  [Telegram] Send error: ${err.message}`);
    }
  }

  private formatProjectCard(p: AirdropProject, showDetail: boolean = false): string {
    const statusEmoji = emojiForStatus(p.status);
    const chains = p.chains.map(c => chainToEmoji(c)).join(' ');
    const trustBar = bar(p.trustScore);
    const opp = p.opportunityScore ?? 50;
    const oppBar = bar(opp);
    const risk = p.scamRisk ?? 'low';
    const riskEmoji = risk === 'critical' ? '🔴' : risk === 'high' ? '🟠' : risk === 'medium' ? '🟡' : '🟢';
    const ev = p.expectedValue ?? 0;
    const vph = p.valuePerHour ?? 0;
    const lw = p.linkWarnings || [];
    const hasLinkIssue = lw.some(w => w.severity === 'high' || w.severity === 'critical');

    let card = `\n${statusEmoji} <b>${p.name}</b>\n` +
      `   🎯 Opp: ${oppBar} ${opp}% | ✅ Trust: ${trustBar} ${p.trustScore}%\n` +
      `   ${riskEmoji} Risk: ${risk} | ${chains || '?'}`;

    if (showDetail) {
      const leg = p.legitimacyScore ?? '?';
      const rw = p.rewardPotential ?? '?';
      const ef = p.effortScore ?? '?';
      const urg = p.urgencyScore ?? '?';
      card += `\n   🎯 ${leg}% · 💰 ${rw}% · 💪 ${ef}% · ⏰ ${urg}%`;
    }

    if (ev > 0) card += `\n   💰 Est. Value: $${ev}${vph > 0 ? ` · $${vph}/hr` : ''}`;
    if (p.tokenInfo?.symbol) card += `\n   Token: ${p.tokenInfo.symbol}`;
    card += `\n   ${p.sourceUrl}`;
    if (hasLinkIssue) card += `\n   🔗 ⚠️ Suspicious link detected`;
    if (p.scamFlags.length > 0) card += `\n   ⚠️ ${p.scamFlags.join(', ')}`;

    return card;
  }

  async notifyNewProjects(projects: AirdropProject[]): Promise<void> {
    if (!this.enabled || projects.length === 0) return;

    const highOpp = projects.filter(p => (p.opportunityScore ?? 0) >= 75);
    const criticalRisk = projects.filter(p => p.scamRisk === 'critical');
    const urgent = projects.filter(p => (p.urgencyScore ?? 0) >= 70);

    const header = `🪂 <b>DroperOG — ${projects.length} New Airdrops</b>`;
    let detailLines = '';

    const sorted = [...projects].sort((a, b) => (b.opportunityScore ?? 0) - (a.opportunityScore ?? 0));
    const top = sorted.slice(0, 8);

    for (const p of top) {
      const isTop = highOpp.includes(p);
      const isRisk = criticalRisk.includes(p);
      const isUrgent = urgent.includes(p);
      const badge = isTop ? '🔥 ' : isRisk ? '🚨 ' : isUrgent ? '⏰ ' : '';
      detailLines += `\n${badge}${this.formatProjectCard(p, true)}`;
    }

    if (sorted.length > 8) {
      detailLines += `\n\n... and ${sorted.length - 8} more`;
    }

    if (highOpp.length > 0) {
      detailLines += `\n\n🔥 <b>Top Opportunities:</b> ${highOpp.map(p => p.name).join(', ')}`;
    }

    if (criticalRisk.length > 0) {
      detailLines += `\n\n🚨 <b>⚠️ Critical Risk Projects:</b> ${criticalRisk.map(p => p.name).join(', ')}`;
    }

    if (urgent.length > 0) {
      detailLines += `\n\n⏰ <b>Urgent — Deadline Approaching:</b> ${urgent.map(p => p.name).join(', ')}`;
    }

    const chunks = this.chunkText(header + detailLines);
    for (const chunk of chunks) {
      await this.sendMessage(chunk);
    }
  }

  async notifyUrgentProjects(projects: AirdropProject[]): Promise<void> {
    if (!this.enabled || projects.length === 0) return;

    const newUrgent = projects.filter(p =>
      (p.urgencyScore ?? 0) >= 70 && !this.notifiedUrgent.has(p.id)
    );
    if (newUrgent.length === 0) return;

    for (const p of newUrgent) {
      this.notifiedUrgent.add(p.id);
    }

    const sorted = [...newUrgent].sort((a, b) => (b.urgencyScore ?? 0) - (a.urgencyScore ?? 0));
    const header = `⏰ <b>DroperOG — ${newUrgent.length} Urgent Deadline${newUrgent.length > 1 ? 's' : ''}</b>\n`;
    const body = sorted.slice(0, 6).map(p => this.formatProjectCard(p, true)).join('');
    const reminder = sorted.length > 6 ? `\n... and ${sorted.length - 6} more` : '';
    await this.sendMessage(header + body + reminder);
  }

  async notifyRiskAlerts(projects: AirdropProject[]): Promise<void> {
    if (!this.enabled) return;

    const risky = projects.filter(p =>
      (p.scamRisk === 'critical' || p.scamRisk === 'high') && !this.notifiedRisky.has(p.id)
    );
    if (risky.length === 0) return;

    for (const p of risky) {
      this.notifiedRisky.add(p.id);
    }

    const header = `🚨 <b>DroperOG — ${risky.length} Security Alert${risky.length > 1 ? 's' : ''}</b>\n` +
      `⚠️ The following projects have suspicious indicators:\n`;
    const body = risky.slice(0, 8).map(p => this.formatProjectCard(p, true)).join('');
    await this.sendMessage(header + body);
  }

  async notifyTopOpportunities(projects: AirdropProject[]): Promise<void> {
    if (!this.enabled || projects.length === 0) return;

    const scored = projects.filter(p => (p.opportunityScore ?? 0) >= 60);
    if (scored.length === 0) return;

    const sorted = [...scored].sort((a, b) => (b.opportunityScore ?? 0) - (a.opportunityScore ?? 0));
    const top = sorted.slice(0, 5);

    const header = `🏆 <b>DroperOG — Top ${top.length} Opportunities</b>\n`;
    const body = top.map(p => this.formatProjectCard(p, true)).join('');
    await this.sendMessage(header + body);
  }

  async notifySmartSummary(
    allProjects: AirdropProject[],
    newCount: number,
    totalValue: number,
  ): Promise<void> {
    if (!this.enabled) return;

    const total = allProjects.length;
    const trusted = allProjects.filter(p => p.trustScore >= 70).length;
    const scored = allProjects.filter(p => (p.opportunityScore ?? 0) > 0);
    const avgOpp = scored.length > 0
      ? Math.round(scored.reduce((s, p) => s + (p.opportunityScore ?? 0), 0) / scored.length)
      : 0;
    const highValue = allProjects.filter(p => (p.expectedValue ?? 0) >= 500).length;
    const urgent = allProjects.filter(p => (p.urgencyScore ?? 0) >= 70).length;
    const risky = allProjects.filter(p => p.scamRisk === 'critical' || p.scamRisk === 'high').length;
    const linkIssues = allProjects.reduce((s, p) => s + ((p.linkWarnings || []).filter(w => w.severity === 'high' || w.severity === 'critical').length), 0);

    let msg = `📊 <b>DroperOG Smart Summary</b>\n\n` +
      `📈 Tracked: ${total}\n` +
      `🆕 New: ${newCount}\n` +
      `✅ Trusted (≥70%): ${trusted}\n\n` +
      `🎯 Avg Opportunity: ${avgOpp}%\n` +
      `💰 High Value (≥$500): ${highValue}\n` +
      `⏰ Urgent: ${urgent}\n` +
      `🚨 Security Issues: ${risky} risky + ${linkIssues} link warnings\n\n` +
      `💵 Total Est. Value: $${totalValue.toLocaleString()}`;

    await this.sendMessage(msg);
  }

  async notifyMarketSnapshot(fng: FearGreedData | null, gasData: GasData[], newListings: NewListing[]): Promise<void> {
    if (!this.enabled) return;

    let msg = `🌍 <b>DroperOG — Market Snapshot</b>\n\n`;

    if (fng) {
      const emoji = fng.classification.includes('Fear') ? '😱' : fng.classification.includes('Greed') ? '🤑' : '😐';
      msg += `${emoji} <b>Fear & Greed:</b> ${fng.value}/100 — ${fng.classification}\n`;
    }

    if (gasData.length > 0) {
      msg += `\n⛽ <b>Gas Prices:</b>\n`;
      for (const g of gasData) {
        const ge = g.standard <= 20 ? '🟢' : g.standard <= 50 ? '🟡' : '🔴';
        msg += `  ${ge} ${g.chain}: ${g.standard} gwei (fast: ${g.fast})\n`;
      }
    }

    if (newListings.length > 0) {
      const top = newListings.slice(0, 5);
      msg += `\n🆕 <b>Recent New Listings:</b>\n`;
      for (const l of top) {
        msg += `  • ${l.name} (${l.symbol.toUpperCase()})\n`;
      }
      if (newListings.length > 5) msg += `  ... and ${newListings.length - 5} more\n`;
    }

    await this.sendMessage(msg);
  }

  private chunkText(text: string): string[] {
    const MAX = 4000;
    if (text.length <= MAX) return [text];

    const chunks: string[] = [];
    let current = '';

    const lines = text.split('\n');
    for (const line of lines) {
      if ((current + line).length > MAX) {
        chunks.push(current);
        current = line + '\n';
      } else {
        current += line + '\n';
      }
    }
    if (current.trim()) chunks.push(current);
    return chunks;
  }
}
