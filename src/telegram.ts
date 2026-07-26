import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import { AirdropProject, FearGreedData, GasData, NewListing, TelegramSubscriber, SubscriberStore } from './types';
import { emojiForStatus, chainToEmoji, bar } from './utils';

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const ADMIN_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '';
const SUBS_FILE = path.join(__dirname, '..', 'data', 'subscribers.json');

export class TelegramNotifier {
  private enabled: boolean;
  private notifiedUrgent = new Set<string>();
  private notifiedRisky = new Set<string>();
  private subscribers: TelegramSubscriber[] = [];
  private polling = false;

  constructor() {
    this.enabled = !!(BOT_TOKEN);
    if (!this.enabled) {
      console.log('  [Telegram] Disabled — set TELEGRAM_BOT_TOKEN');
    } else {
      this.loadSubscribers();
    }
  }

  // ── Subscriber Management ──

  private subsPath(): string { return SUBS_FILE; }

  private loadSubscribers(): void {
    try {
      if (fs.existsSync(this.subsPath())) {
        const store: SubscriberStore = JSON.parse(fs.readFileSync(this.subsPath(), 'utf-8'));
        this.subscribers = store.subscribers || [];
      }
    } catch { this.subscribers = []; }
  }

  private saveSubscribers(): void {
    const dir = path.dirname(this.subsPath());
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const store: SubscriberStore = { subscribers: this.subscribers };
    fs.writeFileSync(this.subsPath(), JSON.stringify(store, null, 2));
  }

  getSubscriberCount(): number { return this.subscribers.length; }

  addSubscriber(chatId: string): boolean {
    if (this.subscribers.some(s => s.chatId === chatId)) return false;
    this.subscribers.push({ chatId, subscribedAt: Date.now() });
    this.saveSubscribers();
    return true;
  }

  removeSubscriber(chatId: string): boolean {
    const before = this.subscribers.length;
    this.subscribers = this.subscribers.filter(s => s.chatId !== chatId);
    if (this.subscribers.length !== before) {
      this.saveSubscribers();
      return true;
    }
    return false;
  }

  isAdmin(chatId: string): boolean {
    if (!ADMIN_CHAT_ID) return true;
    return ADMIN_CHAT_ID.split(',').includes(chatId);
  }

  // ── Interactive Command Polling ──

  private lastUpdateId = 0;
  private cmdHandlers: Record<string, (chatId: string, args: string[]) => Promise<string>> = {};

  onCommand(cmd: string, handler: (chatId: string, args: string[]) => Promise<string>): void {
    this.cmdHandlers[cmd.toLowerCase()] = handler;
  }

  async startPolling(latestProjects: () => AirdropProject[]): Promise<void> {
    if (!this.enabled || this.polling) return;
    this.polling = true;

    // Register built-in commands
    this.onCommand('start', async (chatId) => {
      return `🪂 <b>DroperOG Bot</b>

/subscribe — Get airdrop alerts
/unsubscribe — Stop alerts
/latest — Latest airdrops
/status — Bot status
/help — This message`;
    });

    this.onCommand('help', async (chatId) => {
      return `🪂 <b>DroperOG Commands</b>

/subscribe — Subscribe to airdrop alerts
/unsubscribe — Unsubscribe from alerts
/latest — Show latest ${Math.min(5, latestProjects().length)} airdrops
/status — Show bot status & stats`;
    });

    this.onCommand('subscribe', async (chatId) => {
      if (!this.isAdmin(chatId)) return '⛔ Access denied.';
      if (this.addSubscriber(chatId)) return '✅ Subscribed to airdrop alerts!';
      return 'ℹ️ Already subscribed.';
    });

    this.onCommand('unsubscribe', async (chatId) => {
      if (this.removeSubscriber(chatId)) return '✅ Unsubscribed.';
      return 'ℹ️ You are not subscribed.';
    });

    this.onCommand('latest', async (chatId) => {
      const projects = latestProjects();
      if (!projects.length) return 'No airdrops found yet.';
      const top = projects
        .sort((a, b) => (b.opportunityScore ?? 0) - (a.opportunityScore ?? 0))
        .slice(0, 5);
      let msg = `🪂 <b>Latest Airdrops</b>\n`;
      for (const p of top) {
        const ev = p.expectedValue ?? 0;
        const chains = p.chains.map(c => chainToEmoji(c)).join(' ');
        msg += `\n<b>${p.name}</b>\n`;
        msg += `   🎯 ${p.opportunityScore ?? '?'}% · ✅ ${p.trustScore}% · ${chains}\n`;
        if (ev > 0) msg += `   💰 $${ev}\n`;
        msg += `   ${p.sourceUrl}\n`;
      }
      return msg;
    });

    this.onCommand('status', async (chatId) => {
      const projects = latestProjects();
      const total = projects.length;
      const trusted = projects.filter(p => p.trustScore >= 70).length;
      const highVal = projects.filter(p => (p.expectedValue ?? 0) >= 500).length;
      return `📊 <b>DroperOG Status</b>

👥 Subscribers: ${this.subscribers.length}
🪂 Tracked: ${total}
✅ Trusted (≥70%): ${trusted}
💰 High Value: ${highVal}
🆕 Subscribers: ${this.subscribers.length}`;
    });

    console.log('  [Telegram] Starting command polling...');
    await this.pollCommands();
  }

  private async pollCommands(): Promise<void> {
    while (this.polling) {
      try {
        const res = await axios.get(
          `https://api.telegram.org/bot${BOT_TOKEN}/getUpdates`,
          {
            params: {
              offset: this.lastUpdateId + 1,
              timeout: 30,
              allowed_updates: JSON.stringify(['message']),
            },
            timeout: 35000,
          }
        );

        const updates = res.data?.result || [];
        for (const update of updates) {
          this.lastUpdateId = update.update_id;
          const msg = update.message;
          if (!msg || !msg.text || !msg.chat) continue;

          const chatId = String(msg.chat.id);
          const text = msg.text.trim();
          const parts = text.split(/\s+/);
          const cmd = parts[0].toLowerCase().replace(/^@\w+/, ''); // strip bot username
          const args = parts.slice(1);
          const handler = this.cmdHandlers[cmd] || this.cmdHandlers[cmd.replace(/^\//, '')];
          if (!handler) continue;

          const reply = await handler(chatId, args);
          await this.sendReply(chatId, reply);
        }
      } catch (err: any) {
        if (err.code !== 'ECONNABORTED') {
          console.error(`  [Telegram] Poll error: ${err.message}`);
        }
        await new Promise(r => setTimeout(r, 3000));
      }
    }
  }

  stopPolling(): void {
    this.polling = false;
  }

  // ── Message Sending ──

  async sendMessage(text: string): Promise<void> {
    if (!this.enabled) return;
    try {
      await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        chat_id: ADMIN_CHAT_ID || (this.subscribers[0]?.chatId),
        text,
        parse_mode: 'HTML',
        disable_web_page_preview: true,
      }, { timeout: 10000 });
    } catch (err: any) {
      console.error(`  [Telegram] Send error: ${err.message}`);
    }
  }

  async broadcast(text: string): Promise<void> {
    if (!this.enabled) return;
    const targets = new Set<string>();
    if (ADMIN_CHAT_ID) targets.add(ADMIN_CHAT_ID);
    for (const s of this.subscribers) targets.add(s.chatId);

    for (const chatId of targets) {
      try {
        await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
          chat_id: parseInt(chatId),
          text,
          parse_mode: 'HTML',
          disable_web_page_preview: true,
        }, { timeout: 10000 });
        await new Promise(r => setTimeout(r, 300));
      } catch { /* skip failed sends */ }
    }
  }

  private async sendReply(chatId: string, text: string): Promise<void> {
    if (!this.enabled) return;
    try {
      await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        chat_id: parseInt(chatId),
        text,
        parse_mode: 'HTML',
        disable_web_page_preview: true,
      }, { timeout: 10000 });
    } catch { /* ignore */ }
  }

  // ── Notification Methods ──

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
      await this.broadcast(chunk);
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
    await this.broadcast(header + body + reminder);
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
    await this.broadcast(header + body);
  }

  async notifyTopOpportunities(projects: AirdropProject[]): Promise<void> {
    if (!this.enabled || projects.length === 0) return;

    const scored = projects.filter(p => (p.opportunityScore ?? 0) >= 60);
    if (scored.length === 0) return;

    const sorted = [...scored].sort((a, b) => (b.opportunityScore ?? 0) - (a.opportunityScore ?? 0));
    const top = sorted.slice(0, 5);

    const header = `🏆 <b>DroperOG — Top ${top.length} Opportunities</b>\n`;
    const body = top.map(p => this.formatProjectCard(p, true)).join('');
    await this.broadcast(header + body);
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
      `💵 Total Est. Value: $${totalValue.toLocaleString()}\n` +
      `👥 Subscribers: ${this.subscribers.length}`;

    await this.broadcast(msg);
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

    await this.broadcast(msg);
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
