import { AirdropProject, ScamCheckResult, ScamDetail } from './types';

const TRUSTED_DOMAINS = [
  'defillama.com', 'coingecko.com', 'coinmarketcap.com',
  'etherscan.io', 'arbiscan.io', 'basescan.org',
  'github.com', 'twitter.com', 'x.com',
];

const KNOWN_SCAM_PATTERNS = [
  { pattern: /free\s+(eth|btc|money|token)\s+(giveaway|gift)/i, severity: 'critical' as const, desc: 'Fake giveaway' },
  { pattern: /send\s+\d+\s+(eth|btc|bnb|matic|sol).*receive/i, severity: 'critical' as const, desc: 'Fake send-receive scheme' },
  { pattern: /(guaranteed|assured)\s+(profit|return|income)/i, severity: 'high' as const, desc: 'Guaranteed returns claim' },
  { pattern: /no\s*risk.*(high|huge|massive)\s*return/i, severity: 'high' as const, desc: 'No risk / high return' },
  { pattern: /presale.*(send|pay|deposit)\s+(eth|bnb|matic|sol)/i, severity: 'high' as const, desc: 'Suspicious presale' },
  { pattern: /(admin|support).*\/\/(?!http)/i, severity: 'medium' as const, desc: 'Admin impersonation' },
];

export class TrustChecker {
  checkProject(project: AirdropProject): ScamCheckResult {
    const flags: string[] = [];
    const details: ScamDetail[] = [];

    // Check for scam keywords
    const text = `${project.name} ${project.description}`;
    for (const { pattern, severity, desc } of KNOWN_SCAM_PATTERNS) {
      if (pattern.test(text)) {
        flags.push('suspicious_keywords');
        details.push({ type: 'fake_site', severity, description: desc });
      }
    }

    // Check website credibility
    if (project.links.website) {
      try {
        const domain = new URL(project.links.website).hostname.replace('www.', '');
        if (!TRUSTED_DOMAINS.some(d => domain.includes(d))) {
          // Unknown domain is not a red flag, but known-good is a plus
          details.push({ type: 'fake_site', severity: 'low', description: `Unknown domain: ${domain}` });
        }
      } catch { /* invalid URL */ }
    }

    // Check description quality
    if (!project.description || project.description === 'No description' || project.description.length < 15) {
      flags.push('poor_description');
      details.push({ type: 'suspicious_timing', severity: 'low', description: 'Poor or missing description' });
    }

    // Community presence assessment (not a flag, just lower score)
    const missingCommunity: string[] = [];
    if (!project.links.twitter && !project.links.discord && !project.links.telegram) {
      missingCommunity.push('social');
    }

    // Chain specificity
    if (project.chains.includes('unknown')) {
      flags.push('unknown_chain');
      details.push({ type: 'suspicious_timing', severity: 'low', description: 'No blockchain specified' });
    }

    const score = this.calculateScore(flags, details, missingCommunity);

    return { score, flags, details };
  }

  private calculateScore(flags: string[], details: ScamDetail[], missing: string[]): number {
    let score = 80; // Start higher since we're scraping from known airdrop sites

    for (const detail of details) {
      switch (detail.severity) {
        case 'critical': score -= 35; break;
        case 'high': score -= 20; break;
        case 'medium': score -= 10; break;
        case 'low': score -= 3; break;
      }
    }

    for (const flag of flags) {
      if (flag === 'unknown_chain') score -= 5;
      if (flag === 'poor_description') score -= 5;
    }

    if (missing.length === 0) score += 10;

    return Math.max(0, Math.min(100, score));
  }

  checkMultiple(projects: AirdropProject[]): AirdropProject[] {
    return projects.map(project => {
      const result = this.checkProject(project);
      return {
        ...project,
        trustScore: result.score,
        scamFlags: result.flags,
      };
    });
  }
}