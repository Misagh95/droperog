export interface AirdropProject {
  id: string;
  name: string;
  description: string;
  source: 'web_scrape' | 'twitter' | 'blockchain' | 'manual';
  sourceUrl: string;
  chains: string[];
  status: 'upcoming' | 'active' | 'ended' | 'claimed' | 'unknown';
  trustScore: number;
  scamFlags: string[];
  links: ProjectLinks;
  criteria?: EligibilityCriteria;
  tokenInfo?: TokenInfo;
  timeline?: ProjectTimeline;
  discoveredAt: number;
  lastChecked: number;
}

export interface ProjectLinks {
  website?: string;
  twitter?: string;
  discord?: string;
  telegram?: string;
  medium?: string;
  whitepaper?: string;
  github?: string;
}

export interface EligibilityCriteria {
  minTransactions?: number;
  minVolume?: string;
  requiredChains?: string[];
  requiredTokens?: string[];
  minHoldDuration?: number;
  contractInteractions?: string[];
  socialTasks?: string[];
  referralRequired?: boolean;
}

export interface TokenInfo {
  symbol: string;
  name: string;
  totalSupply?: string;
  chain: string;
  contractAddress?: string;
  expectedPrice?: string;
  listingExchanges?: string[];
}

export interface ProjectTimeline {
  announcementDate?: number;
  snapshotDate?: number;
  claimStartDate?: number;
  claimEndDate?: number;
  tgeDate?: number;
  listingDate?: number;
}

export interface ScamCheckResult {
  score: number;
  flags: string[];
  details: ScamDetail[];
}

export interface ScamDetail {
  type: 'fake_site' | 'no_team' | 'copycat' | 'no_code' | 'honeypot' | 'rug_pull_risk' | 'no_liquidity' | 'suspicious_timing';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
}

export interface SourceConfig {
  name: string;
  url: string;
  enabled: boolean;
  interval: number;
  type: 'rss' | 'api' | 'webpage' | 'twitter';
}

export interface Config {
  checkInterval: number;
  sources: SourceConfig[];
  twitter: TwitterConfig;
  blockchain: BlockchainConfig;
  notifications: NotificationConfig;
}

export interface TwitterConfig {
  accounts: string[];
  keywords: string[];
  enabled: boolean;
}

export interface BlockchainConfig {
  chains: string[];
  rpcUrls: Record<string, string>;
  enabled: boolean;
}

export interface NotificationConfig {
  console: boolean;
  desktop: boolean;
}

export interface ScrapeResult {
  source: string;
  projects: AirdropProject[];
  error?: string;
  timestamp: number;
}

export interface SearchFilter {
  chains?: string[];
  minTrustScore?: number;
  status?: string[];
  sortBy?: 'trustScore' | 'discoveredAt' | 'name';
  sortDir?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}