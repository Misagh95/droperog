import axios from 'axios';
import { FearGreedData } from './types';

export class MarketData {
  private fngCache: FearGreedData | null = null;
  private fngCacheTime = 0;
  private cacheTtl: number;

  constructor(cacheTtlMs: number = 3600000) {
    this.cacheTtl = cacheTtlMs;
  }

  async getFearGreedIndex(): Promise<FearGreedData | null> {
    if (this.fngCache && (Date.now() - this.fngCacheTime) < this.cacheTtl) {
      return this.fngCache;
    }

    try {
      const res = await axios.get('https://api.alternative.me/fng/', {
        params: { limit: 1 },
        timeout: 10000,
      });

      if (res.data?.data?.[0]) {
        const item = res.data.data[0];
        this.fngCache = {
          value: parseInt(item.value),
          classification: item.value_classification,
          timestamp: new Date().toISOString(),
        };
        this.fngCacheTime = Date.now();
        return this.fngCache;
      }
    } catch { /* ignore */ }
    return null;
  }

  classificationEmoji(classification: string): string {
    const map: Record<string, string> = {
      'Extreme Fear': '😱',
      'Fear': '😰',
      'Neutral': '😐',
      'Greed': '😊',
      'Extreme Greed': '🤑',
    };
    return map[classification] || '❓';
  }

  async printFearGreed(): Promise<void> {
    const data = await this.getFearGreedIndex();
    if (!data) {
      console.log('  ❌ Failed to fetch Fear & Greed Index');
      return;
    }
    const emoji = this.classificationEmoji(data.classification);
    const barLen = Math.round(data.value / 10);
    const bar = '█'.repeat(barLen) + '░'.repeat(10 - barLen);
    console.log(`  ${emoji} Fear & Greed: ${bar} ${data.value}/100 — ${data.classification}`);
  }
}
