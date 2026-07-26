import { AirdropProject, LinkWarning, ScamCheckResult, ScamDetail, ScoringWeights } from './types';

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

const CHAIN_ECOSYSTEM_SCORE: Record<string, number> = {
  ethereum: 90, arbitrum: 85, optimism: 80, base: 80,
  zksync: 85, solana: 80, polygon: 70, avalanche: 65,
  bsc: 60, scroll: 70, linea: 70, starknet: 75,
  celestia: 60, sui: 65, aptos: 60, ton: 55,
  near: 50, cosmos: 65, osmosis: 55, sei: 50,
  berachain: 60, injective: 55,
};

const MAJOR_FUNDING_THRESHOLD = 5_000_000;

const SUSPICIOUS_TLDS = new Set(['.xyz', '.top', '.gq', '.ml', '.cf', '.tk', './ga', '.zip', '.mov', '.click', '.date', '.review', '.trade', '.win', '.bid']);

const PHISHING_DOMAIN_KEYWORDS = ['claim', 'airdrop', 'free', 'giveaway', 'bonus', 'reward', 'promo', 'earn', 'get-', 'official'];

const URL_SHORTENERS = new Set(['bit.ly', 'tinyurl.com', 'tiny.cc', 'shorturl.at', 'shorte.st', 'tr.im', 'is.gd', 'rb.gy', 'cutt.ly', 'ow.ly', 'buff.ly', 'short.link', 'lnk.to', 't.co']);

const BRAND_KEYWORDS = ['uniswap', 'arbitrum', 'optimism', 'zksync', 'base', 'polygon', 'solana', 'pancake', 'aave', 'compound', 'curve', 'balancer', 'lido', 'maker', 'frax', 'pendle', 'eigenlayer', 'layerzero', 'starknet', 'scroll', 'linea', 'blast', 'mode', 'manta', 'celestia', 'dymension', 'saga', 'avalanche', 'sui', 'aptos', 'injective', 'sei', 'cosmos', 'osmo', 'berachain', 'story', 'monad']; 

function scamRiskToString(severity: ScamDetail['severity'] | null): AirdropProject['scamRisk'] {
  if (!severity) return 'low';
  switch (severity) {
    case 'critical': return 'critical';
    case 'high': return 'high';
    case 'medium': return 'medium';
    default: return 'low';
  }
}

export class TrustChecker {
  private defaultWeights: ScoringWeights = {
    legitimacy: 0.25,
    reward: 0.30,
    effort: 0.15,
    urgency: 0.10,
    safety: 0.20,
  };

  checkProject(project: AirdropProject): ScamCheckResult {
    const flags: string[] = [];
    const details: ScamDetail[] = [];

    const text = `${project.name} ${project.description}`;
    for (const { pattern, severity, desc } of KNOWN_SCAM_PATTERNS) {
      if (pattern.test(text)) {
        flags.push('suspicious_keywords');
        details.push({ type: 'fake_site', severity, description: desc });
      }
    }

    if (project.links.website) {
      try {
        const domain = new URL(project.links.website).hostname.replace('www.', '');
        if (!TRUSTED_DOMAINS.some(d => domain.includes(d))) {
          details.push({ type: 'fake_site', severity: 'low', description: `Unknown domain: ${domain}` });
        }
      } catch { /* invalid URL */ }
    }

    if (!project.description || project.description === 'No description' || project.description.length < 15) {
      flags.push('poor_description');
      details.push({ type: 'suspicious_timing', severity: 'low', description: 'Poor or missing description' });
    }

    const missingCommunity: string[] = [];
    if (!project.links.twitter && !project.links.discord && !project.links.telegram) {
      missingCommunity.push('social');
    }

    if (project.chains.includes('unknown')) {
      flags.push('unknown_chain');
      details.push({ type: 'suspicious_timing', severity: 'low', description: 'No blockchain specified' });
    }

    const score = this.calculateScore(flags, details, missingCommunity);

    return { score, flags, details };
  }

  private calculateScore(flags: string[], details: ScamDetail[], missing: string[]): number {
    let score = 80;

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

  private computeLegitimacy(project: AirdropProject, details: ScamDetail[]): number {
    let score = 50;

    const hasTwitter = !!project.links.twitter;
    const hasDiscord = !!project.links.discord;
    const hasTelegram = !!project.links.telegram;
    const hasGithub = !!project.links.github;
    const hasWebsite = !!project.links.website;

    const socialCount = [hasTwitter, hasDiscord, hasTelegram].filter(Boolean).length;
    score += socialCount * 8;

    if (hasGithub) score += 10;
    if (hasWebsite) {
      try {
        const domain = new URL(project.links.website!).hostname.replace('www.', '');
        if (TRUSTED_DOMAINS.some(d => domain.includes(d))) score += 10;
      } catch { /* ignore */ }
    }

    if (project.description && project.description.length > 30) score += 5;
    if (project.tokenInfo?.symbol) score += 5;

    const worstDetail = details.reduce((w, d) => {
      const rank = { critical: 4, high: 3, medium: 2, low: 1 };
      return rank[d.severity] > rank[w.severity] ? d : w;
    }, details[0] || { severity: 'low' as const });

    const penaltyMap = { critical: 35, high: 20, medium: 10, low: 3 };
    score -= penaltyMap[worstDetail.severity];

    return Math.max(0, Math.min(100, score));
  }

  private computeRewardPotential(project: AirdropProject): number {
    let score = 30;

    const statusBoost: Record<string, number> = { confirmed: 25, active: 20, upcoming: 15, potential: 10 };
    score += statusBoost[project.status] || 5;

    if (project.tokenInfo?.expectedPrice) {
      const price = parseFloat(project.tokenInfo.expectedPrice);
      if (price > 0) score += 15;
    }
    if (project.tokenInfo?.symbol) score += 10;
    if (project.tokenInfo?.listingExchanges?.length) score += 10;

    if (project.chains.length > 0 && project.chains[0] !== 'unknown') {
      const topChains = project.chains.slice(0, 3);
      for (const c of topChains) {
        score += (CHAIN_ECOSYSTEM_SCORE[c.toLowerCase()] || 30) * 0.15;
      }
    }

    const fundingMatch = project.description.match(/funding:\s*\$?([\d,.]+[kmb]?)/i);
    if (fundingMatch) {
      const val = parseFunding(fundingMatch[1]);
      if (val > MAJOR_FUNDING_THRESHOLD) score += 15;
      else if (val > 1_000_000) score += 10;
      else score += 5;
    }

    const hasCriteria = !!project.criteria;
    if (hasCriteria) score += 5;

    return Math.max(0, Math.min(100, Math.round(score)));
  }

  private computeEffortScore(project: AirdropProject): number {
    let score = 60;

    if (project.criteria) {
      const c = project.criteria;
      if (c.minTransactions) score -= Math.min(c.minTransactions * 2, 20);
      if (c.contractInteractions?.length) score -= Math.min(c.contractInteractions.length * 3, 15);
      if (c.socialTasks?.length) score -= Math.min(c.socialTasks.length * 5, 20);
      if (c.referralRequired) score -= 15;
      if (c.minVolume) {
        const vol = parseFloat(c.minVolume.replace(/[$,]/g, ''));
        if (vol > 10000) score -= 15;
        else if (vol > 1000) score -= 8;
      }
      if (c.minHoldDuration) score -= Math.min(c.minHoldDuration / 86400 * 2, 10);
    }

    if (project.chains.length > 3) score -= 5;
    if (project.status === 'claimed') score = 0;
    if (project.status === 'ended') score = 0;

    return Math.max(0, Math.min(100, Math.round(score)));
  }

  private computeUrgencyScore(project: AirdropProject): number {
    let score = 20;
    const now = Date.now();

    if (project.timeline) {
      const t = project.timeline;

      if (t.claimEndDate) {
        const timeLeft = t.claimEndDate - now;
        if (timeLeft < 0) score = 0;
        else if (timeLeft < 86400000) score = 100;
        else if (timeLeft < 604800000) score = 80;
        else if (timeLeft < 2592000000) score = 60;
        else score = 40;
        return score;
      }

      if (t.claimStartDate) {
        if (now > t.claimStartDate) score = 50;
        else {
          const daysUntil = (t.claimStartDate - now) / 86400000;
          if (daysUntil < 7) score = 70;
          else if (daysUntil < 30) score = 50;
          else score = 30;
        }
        return score;
      }

      if (t.snapshotDate) {
        const daysSince = (now - t.snapshotDate) / 86400000;
        if (daysSince < 0) score = 70;
        else if (daysSince < 30) score = 50;
        else score = 20;
        return score;
      }
    }

    const statusUrgency: Record<string, number> = { active: 60, upcoming: 30, potential: 20, confirmed: 40 };
    score = statusUrgency[project.status] || 10;

    const ageDays = (now - project.discoveredAt) / 86400000;
    if (ageDays < 7) score += 15;
    else if (ageDays > 90) score -= 15;

    return Math.max(0, Math.min(100, Math.round(score)));
  }

  private computeExpectedValue(project: AirdropProject): number {
    if (project.tokenInfo?.expectedPrice) {
      const price = parseFloat(project.tokenInfo.expectedPrice);
      const supply = project.tokenInfo.totalSupply ? parseFloat(project.tokenInfo.totalSupply) : 0;
      if (price > 0 && supply > 0) {
        return Math.round(price * Math.min(supply * 0.001, 5000));
      }
      return Math.round(price * 100);
    }

    const estValueMatch = project.description.match(/est\.?\s*value:?\s*\$?([\d,.]+)/i);
    if (estValueMatch) {
      return Math.round(parseFloat(estValueMatch[1].replace(/,/g, '')));
    }

    let base = 50;
    if (project.chains[0] && project.chains[0] !== 'unknown') {
      const eco = CHAIN_ECOSYSTEM_SCORE[project.chains[0].toLowerCase()] || 30;
      base += eco * 1.5;
    }
    const statusVal: Record<string, number> = { confirmed: 300, active: 150, upcoming: 80, potential: 40 };
    base += statusVal[project.status] || 10;

    return Math.round(base);
  }

  private computeValuePerHour(expectedValue: number, effortScore: number): number {
    if (effortScore <= 0) return 0;
    const effortHours = 10 + (100 - effortScore) * 0.5;
    return Math.round((expectedValue / Math.max(effortHours, 1)) * 10) / 10;
  }

  checkLinkSecurity(project: AirdropProject): LinkWarning[] {
    const warnings: LinkWarning[] = [];
    const urlFields: (keyof typeof project.links)[] = ['website', 'twitter', 'discord', 'telegram', 'medium', 'whitepaper', 'github'];

    for (const field of urlFields) {
      const url = project.links[field];
      if (!url) continue;

      try {
        const parsed = new URL(url);
        const hostname = parsed.hostname.toLowerCase();

        // 1. Homograph attack: non-ASCII characters in domain
        if (/[^\x00-\x7F]/.test(hostname)) {
          warnings.push({ field, url, severity: 'critical', reason: `Homograph attack risk: domain contains non-ASCII characters` });
          continue;
        }

        // 2. Suspicious TLD
        const tld = '.' + hostname.split('.').pop();
        if (SUSPICIOUS_TLDS.has(tld)) {
          warnings.push({ field, url, severity: 'high', reason: `Suspicious TLD: ${tld}` });
        }

        // 3. URL shortener
        const domainWithoutWww = hostname.replace(/^www\./, '');
        if (URL_SHORTENERS.has(domainWithoutWww)) {
          warnings.push({ field, url, severity: 'medium', reason: `URL shortener hides real destination` });
        }

        // 4. HTTPS check
        if (parsed.protocol !== 'https:' && field === 'website') {
          warnings.push({ field, url, severity: 'medium', reason: `Website does not use HTTPS` });
        }

        // 5. Brand impersonation: domain contains known project name
        const domainName = hostname.replace(/^www\./, '').replace(/\.[^.]+$/, '');
        for (const brand of BRAND_KEYWORDS) {
          if (domainName.includes(brand) && !domainName.endsWith(brand) && !domainName.startsWith(brand)) {
            warnings.push({ field, url, severity: 'high', reason: `Possible brand impersonation of "${brand}"` });
            break;
          }
        }

        // 6. Phishing keywords in domain
        for (const kw of PHISHING_DOMAIN_KEYWORDS) {
          if (domainName.includes(kw) && !domainName.includes(kw + 'drop')) {
            const slashPart = parsed.pathname.toLowerCase();
            if (slashPart.includes(kw) || slashPart.includes('claim')) {
              warnings.push({ field, url, severity: 'medium', reason: `URL contains phishing keyword "${kw}"` });
              break;
            }
          }
        }

        // 7. IP address instead of domain
        if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname)) {
          warnings.push({ field, url, severity: 'high', reason: `IP address used instead of domain name` });
        }
      } catch {
        warnings.push({ field, url, severity: 'medium', reason: `Invalid URL format` });
      }
    }

    return warnings;
  }

  scoreProject(project: AirdropProject, scamResult: ScamCheckResult): AirdropProject {
    const linkWarnings = this.checkLinkSecurity(project);

    for (const w of linkWarnings) {
      const severity = w.severity as ScamDetail['severity'];
      const existing = scamResult.details.find(d => d.description.includes(w.url));
      if (!existing) {
        scamResult.details.push({ type: 'phishing_link', severity, description: `[${w.field}] ${w.reason}: ${w.url}` });
        if (severity === 'high' || severity === 'critical') {
          if (!scamResult.flags.includes('suspicious_link')) {
            scamResult.flags.push('suspicious_link');
          }
        }
      }
    }

    // Recalculate trust score with link warnings included
    const missingCheck: string[] = [];
    if (!project.links.twitter && !project.links.discord && !project.links.telegram) {
      missingCheck.push('social');
    }
    const recalculatedScore = this.calculateScore(scamResult.flags, scamResult.details, missingCheck);
    scamResult.score = recalculatedScore;

    const legitimacyScore = this.computeLegitimacy(project, scamResult.details);
    const rewardPotential = this.computeRewardPotential(project);
    const effortScore = this.computeEffortScore(project);
    const urgencyScore = this.computeUrgencyScore(project);

    const worstSeverity = scamResult.details.reduce((w, d) => {
      const rank = { critical: 4, high: 3, medium: 2, low: 1 };
      return rank[d.severity] > rank[w.severity] ? d : w;
    }, scamResult.details[0] || { severity: 'low' as const }).severity;
    const scamRisk = scamRiskToString(worstSeverity);

    const safetyScore = (
      scamRisk === 'low' ? 100 :
      scamRisk === 'medium' ? 60 :
      scamRisk === 'high' ? 25 : 0
    );

    const w = this.defaultWeights;
    const opportunityScore = Math.round(
      legitimacyScore * w.legitimacy +
      rewardPotential * w.reward +
      effortScore * w.effort +
      urgencyScore * w.urgency +
      safetyScore * w.safety
    );

    const expectedValue = this.computeExpectedValue(project);
    const valuePerHour = this.computeValuePerHour(expectedValue, effortScore);

    return {
      ...project,
      trustScore: scamResult.score,
      scamFlags: scamResult.flags,
      legitimacyScore,
      rewardPotential,
      effortScore,
      urgencyScore,
      scamRisk,
      opportunityScore,
      expectedValue,
      valuePerHour,
      linkWarnings,
    };
  }

  checkMultiple(projects: AirdropProject[]): AirdropProject[] {
    return projects.map(project => {
      const result = this.checkProject(project);
      return this.scoreProject(project, result);
    });
  }
}

function parseFunding(val: string): number {
  const clean = val.toLowerCase().replace(/[$,]/g, '');
  if (clean.endsWith('b')) return parseFloat(clean) * 1e9;
  if (clean.endsWith('m')) return parseFloat(clean) * 1e6;
  if (clean.endsWith('k')) return parseFloat(clean) * 1e3;
  return parseFloat(clean) || 0;
}
