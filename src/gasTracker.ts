import axios from 'axios';
import { GasData } from './types';

const GAS_APIS: Record<string, { url: string; parser: (data: any) => GasData | null }> = {
  ethereum: {
    url: 'https://api.etherscan.io/api?module=gastracker&action=gasoracle',
    parser: (data: any) => {
      if (data?.status === '1' && data?.result) {
        return {
          safe: parseInt(data.result.SafeGasPrice),
          standard: parseInt(data.result.ProposeGasPrice),
          fast: parseInt(data.result.FastGasPrice),
          chain: 'ethereum',
        };
      }
      return null;
    },
  },
  polygon: {
    url: 'https://api.polygonscan.com/api?module=gastracker&action=gasoracle',
    parser: (data: any) => {
      if (data?.status === '1' && data?.result) {
        return {
          safe: parseInt(data.result.SafeGasPrice),
          standard: parseInt(data.result.ProposeGasPrice),
          fast: parseInt(data.result.FastGasPrice),
          chain: 'polygon',
        };
      }
      return null;
    },
  },
  bsc: {
    url: 'https://api.bscscan.com/api?module=gastracker&action=gasoracle',
    parser: (data: any) => {
      if (data?.status === '1' && data?.result) {
        return {
          safe: parseInt(data.result.SafeGasPrice),
          standard: parseInt(data.result.ProposeGasPrice),
          fast: parseInt(data.result.FastGasPrice),
          chain: 'bsc',
        };
      }
      return null;
    },
  },
};

export class GasTracker {
  private cache: Map<string, { data: GasData; time: number }> = new Map();
  private cacheTtl: number;

  constructor(cacheTtlMs: number = 120000) {
    this.cacheTtl = cacheTtlMs;
  }

  async getGas(chain: string = 'ethereum'): Promise<GasData | null> {
    const cached = this.cache.get(chain);
    if (cached && (Date.now() - cached.time) < this.cacheTtl) {
      return cached.data;
    }

    const api = GAS_APIS[chain];
    if (!api) return null;

    try {
      const res = await axios.get(api.url, { timeout: 10000 });
      const data = api.parser(res.data);
      if (data) {
        this.cache.set(chain, { data, time: Date.now() });
      }
      return data;
    } catch { return null; }
  }

  async getAllGas(): Promise<GasData[]> {
    const results: GasData[] = [];
    const chains = Object.keys(GAS_APIS);

    const responses = await Promise.allSettled(
      chains.map(c => this.getGas(c))
    );

    for (const r of responses) {
      if (r.status === 'fulfilled' && r.value) {
        results.push(r.value);
      }
    }

    return results;
  }

  gasEmoji(gwei: number): string {
    if (gwei <= 20) return '🟢';
    if (gwei <= 50) return '🟡';
    if (gwei <= 100) return '🟠';
    return '🔴';
  }

  async printGas(): Promise<void> {
    const allGas = await this.getAllGas();
    if (allGas.length === 0) {
      console.log('  ❌ Failed to fetch gas data (API key may be needed)');
      return;
    }

    for (const g of allGas) {
      const emoji = this.gasEmoji(g.standard);
      console.log(`  ${emoji} ${g.chain}: ${g.standard} gwei (safe: ${g.safe}, fast: ${g.fast})`);
    }
  }
}
