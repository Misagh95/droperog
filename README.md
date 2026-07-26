<div align="center">
  <img src="https://img.shields.io/badge/v2.0-8b5cf6?style=for-the-badge&logo=typescript&label=DroperOG" alt="Version">
  <img src="https://img.shields.io/badge/MIT-22c55e?style=for-the-badge&label=license" alt="License">
  <img src="https://img.shields.io/badge/-passing-22c55e?style=for-the-badge&logo=githubactions&label=build" alt="Build">
  <img src="https://img.shields.io/badge/-ready-7c3aed?style=for-the-badge&logo=pwa&label=PWA" alt="PWA">
  <br>
  <img src="https://img.shields.io/badge/Node.js-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="Node">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TS">
  <img src="https://img.shields.io/badge/Telegram-26A5E4?style=flat-square&logo=telegram&logoColor=white" alt="Telegram">
  <img src="https://img.shields.io/badge/Ethers.js-2535A0?style=flat-square&logo=ethereum&logoColor=white" alt="Ethers">
</div>

<br>

<h1 align="center">🪂 DroperOG</h1>
<h3 align="center">Multi-source airdrop hunter with smart scoring, Telegram bot, PWA dashboard & wallet analysis</h3>

<br>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#environment">Environment</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#dashboard">Dashboard</a> •
  <a href="#telegram">Telegram</a>
</p>

---

## Features

| | |
|---|---|
| 🎯 **Smart Scoring** | 8-dimensional engine — legitimacy, reward, effort, urgency, scam risk, opportunity, value, $/hr |
| 🛡️ **Link Security** | 7 threat detectors — homograph attacks, suspicious TLDs, brand impersonation, URL shorteners, no HTTPS, phishing keywords, raw IP |
| 📱 **PWA Dashboard** | Installable mobile app with search, filters & sorting |
| 🤖 **Telegram Bot** | 🆕 New airdrops, ⏰ deadline alerts, 🚨 risk warnings, 📊 smart summary |
| 📋 **Checklist Tracker** | Auto-generated tasks per project, deadline countdowns, persistent storage |
| 🔍 **Wallet Analyzer** | Non-custodial on-chain analysis across 6 EVM chains, eligibility estimation |
| 👥 **Subscriber System** | Multi-user subscribe/unsubscribe, broadcast to all subscribers |
| 🔄 **Auto-Refresh** | GitHub Actions every 2 hours |

---

## Quick Start

```bash
git clone https://github.com/Misagh95/droperog.git
cd droperog
npm install

# Single scan
npm run dev -- --once

# Analyze a wallet
npm run dev -- --wallet 0xYourWalletAddress

# Continuous mode
npm run dev
```

### Scripts

| Command | Description |
|---------|-------------|
| `npm run build` | Compile TypeScript to `dist/` |
| `npm start` | Run compiled version |
| `npm run dev` | Run via ts-node (auto-refresh every 20 min) |
| `npm run dev -- --once` | Single scan + exit |
| `npm run dev -- --wallet 0x...` | Scan + wallet analysis |
| `npm run scan` | Scanner entry (used by GitHub Actions) |

---

## Environment

```env
# Telegram (optional — without it, runs in CLI-only mode)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

---

## Architecture

```
src/
├── index.ts            Orchestrator — sources, dedup, scoring, CLI
├── trustChecker.ts     Scoring engine + link security + scam detection
├── walletAnalyzer.ts   On-chain wallet analysis (6 EVM chains)
├── checklist.ts        Task management + deadline tracker
├── telegram.ts         Telegram bot — notifications + interactive commands
├── scan.ts             GitHub Actions entry point
├── market.ts           Fear & Greed Index
├── gasTracker.ts       Gas prices (Ethereum, Polygon, BSC)
├── types.ts            All TypeScript interfaces
├── utils.ts            Formatting helpers
├── config.ts           Default config
│
└── sources/
    ├── alphadrops.ts   AlphaDrops API
    ├── cryptorank.ts   CryptoRank API
    ├── coingecko.ts    CoinGecko API (airdrops + new listings)
    ├── rss.ts          RSS/Atom feed parser
    └── twitter.ts      Twitter scraper

docs/                   PWA dashboard
├── index.html
├── app.js
├── style.css
├── manifest.json
└── sw.js
```

---

## Scoring Engine

Projects are scored across 8 dimensions:

| Score | Range | Weight | What it measures |
|-------|-------|--------|-----------------|
| 🎯 **legitimacyScore** | 0–100 | 25% | Social presence, GitHub, description quality, domain trust |
| 💰 **rewardPotential** | 0–100 | 30% | Token info, project stage, ecosystem, funding |
| 💪 **effortScore** | 0–100 | 15% | Task complexity (inverse — higher = easier) |
| ⏰ **urgencyScore** | 0–100 | 10% | Deadline proximity |
| 🟢 **scamRisk** | low→critical | 20% | Derived from scam flags & link warnings |
| 🎯 **opportunityScore** | 0–100 | — | Composite: best ratio of reward vs effort |
| 💵 **expectedValue** | USD | — | Estimated claim value |
| ⚡ **valuePerHour** | USD/hr | — | Time-adjusted value |

---

## Link Security

| Threat | Severity |
|--------|----------|
| 🌐 **Homograph Attack** (Cyrillic lookalikes) | 🔴 Critical |
| 🔗 **Suspicious TLD** (`.xyz`, `.top`, `.gq`, `.zip`, `.click`) | 🟠 High |
| 🎭 **Brand Impersonation** (`claim-uniswap.xyz`) | 🟠 High |
| 📍 **Raw IP Address** | 🟠 High |
| 🔗 **URL Shortener** (`bit.ly`, `tinyurl.com`, `t.co`) | 🟡 Medium |
| 🔓 **No HTTPS** | 🟡 Medium |
| 🎣 **Phishing Keywords** in URL path | 🟡 Medium |

---

## Telegram

### Bot Commands

| Command | Description |
|---------|-------------|
| `/subscribe` | Subscribe to airdrop alerts |
| `/unsubscribe` | Unsubscribe |
| `/latest` | Top 5 airdrops by opportunity score |
| `/status` | Bot stats |
| `/help` | Command list |

### Notifications

| Type | Trigger | Content |
|------|---------|---------|
| 🆕 **New Airdrops** | Each scan | Cards with scores, chain, value, link |
| ⏰ **Deadline Alerts** | urgency ≥ 70 | Projects with approaching deadlines |
| 🚨 **Risk Alerts** | scamRisk high/critical | Suspicious projects |
| 🏆 **Top Opportunities** | oppScore ≥ 60 | Best opportunities |
| 📊 **Smart Summary** | End of scan | Stats, totals, subscriber count |

---

## Dashboard

https://misagh95.github.io/droperog/

Filters: status, risk level, sort by opportunity/trust/value/urgency/newness.  
Search by project name or token symbol. Installable as PWA on mobile.

---

## Wallet Analyzer

> 🔒 **Non-custodial** — no seed phrases, private keys, or transaction signing.  
> Just enter a public wallet address.

- Queries 6 EVM chains: Ethereum, Arbitrum, Optimism, Base, Polygon, BSC
- Detects transaction count & native balance per chain
- Identifies protocol usage (Uniswap, Aave, GMX, PancakeSwap)
- Estimates airdrop eligibility with compatibility score

```bash
npm run dev -- --wallet 0xAb58...e9C9
```

---

## Roadmap

- [x] Scoring engine (8 dimensions)
- [x] Link security (7 detectors)
- [x] PWA dashboard
- [x] Telegram bot with interactive commands
- [x] Checklist & deadline tracker
- [x] Wallet analyzer
- [x] Multi-user subscriber system
- [ ] DeFiLlama, Layer3, Galxe integrations
- [ ] Historical score tracking
- [ ] Deadline reminders (7d/3d/1d countdowns)
- [ ] Multi-language support

---

<div align="center">
  <sub>Built with ❤️ by <a href="https://github.com/Misagh95">@Misagh95</a></sub>
  <br><br>
  <a href="https://github.com/Misagh95/droperog/stargazers">⭐ Star</a> •
  <a href="https://github.com/Misagh95/droperog/issues">🐛 Report Bug</a> •
  <a href="https://github.com/Misagh95/droperog/discussions">💬 Discuss</a>
</div>
