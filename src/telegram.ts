import axios from 'axios';
import { AirdropProject } from './types';
import { emojiForStatus, chainToEmoji, bar, truncate } from './utils';

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const CHAT_ID = process.env.TELEGRAM_CHAT_ID || '';

export class TelegramNotifier {
  private enabled: boolean;

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

  async notifyNewProjects(projects: AirdropProject[]): Promise<void> {
    if (!this.enabled || projects.length === 0) return;

    const header = `🪂 <b>DroperOG — ${projects.length} New Airdrops!</b>\n`;

    const chunks = this.chunkProjects(projects.slice(0, 10));
    await this.sendMessage(header + chunks[0]);

    for (let i = 1; i < chunks.length; i++) {
      await this.sendMessage(chunks[i]);
    }
  }

  async notifySummary(total: number, trusted: number, newCount: number): Promise<void> {
    if (!this.enabled) return;
    const msg = `📊 <b>DroperOG Summary</b>\n` +
      `Total tracked: ${total}\n` +
      `Trusted (≥70%): ${trusted} ✅\n` +
      `New this run: ${newCount} 🆕`;
    await this.sendMessage(msg);
  }

  private chunkProjects(projects: AirdropProject[]): string[] {
    const chunks: string[] = [];
    let current = '';

    for (const p of projects) {
      const statusEmoji = emojiForStatus(p.status);
      const chains = p.chains.map(c => chainToEmoji(c)).join(' ');
      const trustBar = bar(p.trustScore);
      const tokenLine = p.tokenInfo?.symbol ? ` | Token: ${p.tokenInfo.symbol}` : '';

      const line = `\n${statusEmoji} <b>${p.name}</b>\n` +
        `   Trust: ${trustBar} ${p.trustScore}% | ${chains || '?'}${tokenLine}\n` +
        `   Status: ${p.status} | ${p.sourceUrl}`;

      if ((current + line).length > 3800) {
        chunks.push(current);
        current = line;
      } else {
        current += line;
      }
    }

    if (current) chunks.push(current);
    return chunks;
  }
}