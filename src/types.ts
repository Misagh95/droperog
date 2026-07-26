export interface AirdropProject {
  id: string;
  name: string;
  description: string;
  source: 'web_scrape' | 'twitter' | 'blockchain' | 'manual';
  sourceUrl: string;
  chains: string[];
  status: 'upcoming' | 'active' | 'ended' | 'claimed' | 'unknown' | 'potential' | 'confirmed';
  trustScore: number;
  scamFlags: string[];
  links: ProjectLinks;
  criteria?: EligibilityCriteria;
  tokenInfo?: TokenInfo;
  timeline?: ProjectTimeline;
  discoveredAt: number;
  lastChecked: number;

  /** (0-100) Credibility & reputation */
  legitimacyScore?: number;
  /** (0-100) Estimated reward potential */
  rewardPotential?: number;
  /** (0-100) Lower = more effort required */
  effortScore?: number;
  /** (0-100) Deadline urgency */
  urgencyScore?: number;
  /** Overall scam risk level */
  scamRisk?: 'low' | 'medium' | 'high' | 'critical';
  /** (0-100) Composite opportunity score */
  opportunityScore?: number;
  /** Estimated USD value */
  expectedValue?: number;
  /** Estimated USD per hour of effort */
  valuePerHour?: number;
  /** Security warnings for project links */
  linkWarnings?: LinkWarning[];
}

export interface LinkWarning {
  field: keyof ProjectLinks;
  url: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  reason: string;
}

export interface ScoringWeights {
  legitimacy: number;
  reward: number;
  effort: number;
  urgency: number;
  safety: number;
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
  type: 'fake_site' | 'no_team' | 'copycat' | 'no_code' | 'honeypot' | 'rug_pull_risk' | 'no_liquidity' | 'suspicious_timing' | 'phishing_link' | 'suspicious_shortener' | 'homograph_attack' | 'brand_impersonation' | 'suspicious_tld';
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
  alertKeywords?: string[];
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

export interface ChainActivity {
  chain: string;
  txCount: number;
  lastActive: number;
  hasTransactions: boolean;
}

export interface WalletProfile {
  address: string;
  chains: ChainActivity[];
  totalTxCount: number;
  protocols: string[];
  analyzedAt: number;
}

export interface FearGreedData {
  value: number;
  classification: string;
  timestamp: string;
}

export interface GasData {
  safe: number;
  standard: number;
  fast: number;
  chain: string;
}

export interface NewListing {
  id: string;
  name: string;
  symbol: string;
  price: number;
  change24h: number;
  marketCap: number;
  discoveredAt: number;
}

export interface EligibilityResult {
  projectId: string;
  projectName: string;
  score: number;
  reasons: string[];
  missing: string[];
}

export interface ChecklistItem {
  id: string;
  task: string;
  type: 'social' | 'transaction' | 'bridge' | 'stake' | 'swap' | 'claim' | 'other';
  deadline?: number;
  completed: boolean;
  completedAt?: number;
}

export interface ProjectChecklist {
  projectId: string;
  projectName: string;
  items: ChecklistItem[];
  createdAt: number;
  updatedAt: number;
}

export interface TelegramSubscriber {
  chatId: string;
  subscribedAt: number;
  lastNotified?: number;
}

export interface SubscriberStore {
  subscribers: TelegramSubscriber[];
}

export interface SearchFilter {
  chains?: string[];
  minTrustScore?: number;
  status?: string[];
  sortBy?: 'trustScore' | 'discoveredAt' | 'name' | 'opportunityScore' | 'expectedValue' | 'valuePerHour' | 'urgencyScore';
  sortDir?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}