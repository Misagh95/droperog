import { ethers } from 'ethers';
import { AirdropProject, ChainActivity, EligibilityResult, WalletProfile } from './types';

const CHAIN_RPCS: Record<string, string> = {
  ethereum: 'https://cloudflare-eth.com',
  arbitrum: 'https://arb1.arbitrum.io/rpc',
  optimism: 'https://mainnet.optimism.io',
  base: 'https://mainnet.base.org',
  polygon: 'https://polygon-rpc.com',
  bsc: 'https://bsc-dataseed.binance.org',
};

const CHAIN_IDs: Record<string, number> = {
  ethereum: 1, arbitrum: 42161, optimism: 10, base: 8453, polygon: 137, bsc: 56,
};

const NATIVE_SYMBOLS: Record<string, string> = {
  ethereum: 'ETH', arbitrum: 'ETH', optimism: 'ETH', base: 'ETH', polygon: 'MATIC', bsc: 'BNB',
};

const KNOWN_PROTOCOLS: { name: string; chain: string; address: string }[] = [
  { name: 'Uniswap', chain: 'ethereum', address: '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984' },
  { name: 'Uniswap V3', chain: 'ethereum', address: '0x1f98431c8ad98523631ae4a59f267346ea31f984' },
  { name: 'Arbitrum', chain: 'arbitrum', address: '0x912CE59144191C1204E64559FE8253a0e49E6548' },
  { name: 'Optimism', chain: 'optimism', address: '0x4200000000000000000000000000000000000042' },
  { name: 'Aave V3', chain: 'ethereum', address: '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9' },
  { name: 'MATIC', chain: 'polygon', address: '0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0' },
];

const PROTOCOL_NAMES_BY_CHAIN: Record<string, string[]> = {
  ethereum: ['Uniswap', 'Aave', 'Compound', 'Curve', 'Lido', 'MakerDAO', 'EigenLayer', 'Pendle'],
  arbitrum: ['Uniswap', 'Aave', 'GMX', 'Camelot', 'Radiant', 'Pendle'],
  optimism: ['Uniswap', 'Aave', 'Velodrome', 'Synthetix'],
  base: ['Uniswap', 'Aerodrome', 'Compound'],
  polygon: ['Uniswap', 'Aave', 'Quickswap', 'Balancer'],
  bsc: ['PancakeSwap', 'Venus', 'Alpaca'],
};

export class WalletAnalyzer {
  private providers: Map<string, ethers.JsonRpcProvider> = new Map();
  private timeoutMs: number;

  constructor(timeoutMs: number = 8000) {
    this.timeoutMs = timeoutMs;
  }

  private getProvider(chain: string): ethers.JsonRpcProvider | null {
    const url = CHAIN_RPCS[chain];
    if (!url) return null;

    if (!this.providers.has(chain)) {
      this.providers.set(chain, new ethers.JsonRpcProvider(url, CHAIN_IDs[chain] || undefined));
    }
    return this.providers.get(chain)!;
  }

  async analyzeWallet(address: string): Promise<WalletProfile> {
    if (!ethers.isAddress(address)) {
      throw new Error(`Invalid Ethereum address: ${address}`);
    }

    const chains: ChainActivity[] = [];
    let totalTxCount = 0;
    const protocols: Set<string> = new Set();

    const chainEntries = Object.entries(CHAIN_RPCS);

    const results = await Promise.allSettled(
      chainEntries.map(async ([chain]) => {
        try {
          const provider = this.getProvider(chain);
          if (!provider) return;

          const txCount = await this.queryTxCount(provider, address);
          if (txCount === 0) return;

          const balance = await provider.getBalance(address);
          const nativeBalance = ethers.formatEther(balance);

          totalTxCount += txCount;

          chains.push({
            chain,
            txCount,
            lastActive: Date.now(),
            hasTransactions: txCount > 0,
          });

          const chainProtocols = PROTOCOL_NAMES_BY_CHAIN[chain] || [];
          for (const p of chainProtocols) {
            protocols.add(p);
          }

          const nativeSymbol = NATIVE_SYMBOLS[chain] || 'Unknown';
          if (parseFloat(nativeBalance) > 0.01) {
            console.log(`  [${chain}] ${txCount} txs, ${parseFloat(nativeBalance).toFixed(4)} ${nativeSymbol}`);
          } else {
            console.log(`  [${chain}] ${txCount} txs`);
          }
        } catch (err: any) {
          console.error(`  [${chain}] Query error: ${err.message}`);
        }
      })
    );

    return {
      address,
      chains,
      totalTxCount,
      protocols: Array.from(protocols),
      analyzedAt: Date.now(),
    };
  }

  private async queryTxCount(provider: ethers.JsonRpcProvider, address: string): Promise<number> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const count = await provider.getTransactionCount(address);
      return count;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  estimateEligibility(wallet: WalletProfile, projects: AirdropProject[]): EligibilityResult[] {
    const results: EligibilityResult[] = [];

    const walletChainSet = new Set(wallet.chains.map(c => c.chain));
    const walletTxCountByChain = new Map(wallet.chains.map(c => [c.chain, c.txCount]));

    for (const project of projects) {
      const reasons: string[] = [];
      const missing: string[] = [];
      let score = 0;

      const projectChains = project.chains.filter(c => c !== 'unknown');
      if (projectChains.length === 0) continue;

      const matchingChains = projectChains.filter(c => walletChainSet.has(c));
      const chainMatchRatio = matchingChains.length / projectChains.length;

      if (chainMatchRatio > 0) {
        score += chainMatchRatio * 40;
        reasons.push(`Active on ${matchingChains.join(', ')}`);
      } else {
        missing.push(`No activity on required chain(s): ${projectChains.join(', ')}`);
      }

      const minTx = project.criteria?.minTransactions;
      if (minTx !== undefined) {
        const walletTx = wallet.totalTxCount;
        if (walletTx >= minTx) {
          score += 20;
          reasons.push(`${walletTx} transactions (min ${minTx})`);
        } else {
          missing.push(`Only ${walletTx} txs, need ${minTx}`);
          score += Math.round((walletTx / minTx) * 15);
        }
      } else {
        score += 15;
      }

      if (project.criteria?.minVolume || project.criteria?.requiredTokens) {
        const hasToken = wallet.protocols.some(p =>
          project.name.toLowerCase().includes(p.toLowerCase()) ||
          p.toLowerCase().includes(project.name.toLowerCase())
        );
        if (hasToken) {
          score += 20;
          reasons.push('Holds related protocol tokens');
        } else {
          missing.push('Token holding not confirmed');
        }
      }

      if (project.criteria?.contractInteractions && project.criteria.contractInteractions.length > 0) {
        const matchedInteractions = project.criteria.contractInteractions.filter(ci =>
          wallet.protocols.some(p => ci.toLowerCase().includes(p.toLowerCase()))
        );
        if (matchedInteractions.length > 0) {
          score += 20;
          reasons.push(`Interacted with: ${matchedInteractions.join(', ')}`);
        } else {
          missing.push('Required contract interactions not detected');
        }
      }

      const oppScore = project.opportunityScore ?? 50;
      score = Math.round(score * (oppScore / 100));

      score = Math.max(0, Math.min(100, score));

      if (score > 0 || missing.length < projectChains.length) {
        results.push({
          projectId: project.id,
          projectName: project.name,
          score,
          reasons,
          missing,
        });
      }
    }

    results.sort((a, b) => b.score - a.score);
    return results.slice(0, 20);
  }

  printAnalysis(wallet: WalletProfile, eligible: EligibilityResult[]): void {
    console.log(`\n${'='.repeat(50)}`);
    console.log('  Wallet Analysis');
    console.log(`${'='.repeat(50)}`);
    console.log(`  Address: ${wallet.address}`);
    console.log(`  Total Tx: ${wallet.totalTxCount}`);
    console.log(`  Active Chains: ${wallet.chains.map(c => `${c.chain} (${c.txCount} txs)`).join(', ') || 'None'}`);
    console.log(`  Protocols: ${wallet.protocols.join(', ') || 'None detected'}`);

    const high = eligible.filter(e => e.score >= 70);
    const medium = eligible.filter(e => e.score >= 40 && e.score < 70);
    const low = eligible.filter(e => e.score < 40);

    console.log(`\n  Compatible Airdrops:`);
    console.log(`  🔥 High (≥70%): ${high.length}`);
    console.log(`  📊 Medium (40-70%): ${medium.length}`);
    console.log(`  📉 Low (<40%): ${low.length}`);

    if (high.length > 0) {
      console.log(`\n  🔥 TOP MATCHES:`);
      for (const e of high) {
        console.log(`    ${e.projectName} — ${e.score}%`);
        for (const r of e.reasons) console.log(`      ✅ ${r}`);
      }
    }

    if (medium.length > 0) {
      console.log(`\n  📊 MEDIUM MATCHES (top 5):`);
      for (const e of medium.slice(0, 5)) {
        console.log(`    ${e.projectName} — ${e.score}%`);
        for (const r of e.reasons) console.log(`      ✅ ${r}`);
        if (e.missing.length > 0) console.log(`      ⬜ ${e.missing[0]}`);
      }
    }

    console.log('');
  }
}
