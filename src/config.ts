import { Config } from './types';

export const DEFAULT_CONFIG: Config = {
  checkInterval: 20 * 60 * 1000,

  sources: [
    {
      name: 'coinranking',
      url: 'https://api.coinranking.com/v2/coins',
      enabled: true,
      interval: 20 * 60 * 1000,
      type: 'api',
    },
    {
      name: 'rss_airdrops',
      url: 'https://airdrops.io/feed/',
      enabled: true,
      interval: 20 * 60 * 1000,
      type: 'rss',
    },
  ],

  twitter: {
    accounts: ['AirdropAlert', 'airdrops_io', 'AlphaDrops_'],
    keywords: ['airdrop', 'claim', 'retrodrop'],
    enabled: false,
  },

  blockchain: {
    chains: ['ethereum', 'arbitrum', 'optimism'],
    rpcUrls: {},
    enabled: false,
  },

  notifications: {
    console: true,
    desktop: false,
  },
};

export function loadConfig(): Config {
  return DEFAULT_CONFIG;
}