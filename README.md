<p align="center">
  <img src="https://img.shields.io/badge/DroperOG-v2.0.0-8b5cf6?style=for-the-badge&logo=typescript" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/coverage-6%20phases-06b6d4?style=for-the-badge" alt="Phases">
  <img src="https://img.shields.io/badge/build-passing-22c55e?style=for-the-badge" alt="Build">
  <img src="https://img.shields.io/badge/PWA-ready-7c3aed?style=for-the-badge&logo=pwa" alt="PWA">
</p>

<h1 align="center">🪂 DroperOG <sup><sub>v2</sub></sup></h1>
<p align="center"><b>🦈 Multi-Source Airdrop Hunter · 🎯 Smart Scoring Engine · 🛡️ Link Security · 🤖 Telegram Bot · 📋 Checklist Tracker · 🔍 Wallet Analyzer</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white">
  <img src="https://img.shields.io/badge/Node.js-339933?style=flat-square&logo=nodedotjs&logoColor=white">
  <img src="https://img.shields.io/badge/Ethers.js-2535A0?style=flat-square&logo=ethereum&logoColor=white">
  <img src="https://img.shields.io/badge/PWA-5A0FC8?style=flat-square&logo=pwa&logoColor=white">
  <img src="https://img.shields.io/badge/Telegram-26A5E4?style=flat-square&logo=telegram&logoColor=white">
  <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white">
</p>

<p align="center">
  Scans <b>4+ sources</b> · Scores <b>8 dimensions</b> · Detects <b>7 link threats</b> · Checks <b>6 EVM chains</b>
</p>

---

## 🚀 Features at a Glance

| Area | What it does |
|------|-------------|
| 🎯 **Smart Scoring** | 8-dimensional scoring engine — legitimacy, reward, effort, urgency, scam risk, opportunity, expected value, $/hr |
| 🛡️ **Link Security** | 7 phishing/threat detectors — homograph attacks, suspicious TLDs, brand impersonation, URL shorteners, no HTTPS, phishing keywords, raw IP |
| 📱 **PWA Dashboard** | Installable mobile dashboard with filters by status, chain, risk level — sort by opportunity, value, urgency, trust |
| 🤖 **Telegram Bot** | Rich project cards, deadline alerts, risk warnings, top-opportunity digest, smart summary |
| 📋 **Checklist Tracker** | Auto-generated task lists per project, deadline countdowns with color-coded urgency, persistent storage |
| 🔍 **Wallet Analyzer** | Non-custodial on-chain analysis across 6 EVM chains, protocol detection, airdrop eligibility estimation |
| 🔄 **Auto-Refresh** | Runs on GitHub Actions every 2 hours, sends smart notifications via Telegram |

---

## 🧠 Scoring Engine — 8 Dimensions

```
🎯 OPPORTUNITY  ─── ████████░░  88%
├─ ✅ Trust       █████████░  90%
├─ 🎯 Legitimacy  ████████░░  83%
├─ 💰 Reward      ██████████ 100%
├─ 💪 Effort      ██████░░░░  60%
├─ ⏰ Urgency     ████████░░  80%
├─ 🟢 Risk        low
└─ 💵 $500  ·  $16.7/hr
```

| Score | Range | Weight |
|-------|-------|--------|
| 🎯 **legitimacyScore** | 0-100 | 25% — social presence, GitHub, description quality, domain trust |
| 💰 **rewardPotential** | 0-100 | 30% — token info, project stage, chain ecosystem, funding |
| 💪 **effortScore** | 0-100 | 15% — inverse of effort (criteria complexity, tasks, volume) |
| ⏰ **urgencyScore** | 0-100 | 10% — deadline proximity (claimEndDate, snapshotDate) |
| 🟢 **scamRisk** | low→critical | 20% — derived from scam flags & link warnings |
| 🎯 **opportunityScore** | 0-100 | **Composite weighted score** |

---

## 🛡️ Link Security — 7 Threat Detectors

| Threat | Severity | Example |
|--------|----------|---------|
| 🌐 **Homograph Attack** | 🔴 Critical | `xn--uniswаp-mwb.com` (Cyrillic chars) |
| 🔗 **Suspicious TLD** | 🟠 High | `.xyz`, `.top`, `.gq`, `.zip`, `.click` |
| 🎭 **Brand Impersonation** | 🟠 High | `claim-uniswap.xyz`, `airdrop-arbitrum.com` |
| 📍 **Raw IP Address** | 🟠 High | `http://192.168.1.1/claim` |
| 🔗 **URL Shortener** | 🟡 Medium | `bit.ly`, `tinyurl.com`, `t.co`, `cutt.ly` |
| 🔓 **No HTTPS** | 🟡 Medium | `http://example.com` |
| 🎣 **Phishing Keywords** | 🟡 Medium | `free`, `giveaway`, `claim` in URL path |

---

## 🤖 Smart Telegram Notifications

| Notification | Trigger | Badge |
|-------------|---------|-------|
| 🆕 **New Projects** | Every scan cycle | 🔥 for high-opportunity, 🚨 for critical risk, ⏰ for urgent |
| ⏰ **Deadline Alerts** | urgencyScore ≥ 70 | `⏰ X Urgent Deadlines` |
| 🚨 **Risk Alerts** | scamRisk = high/critical | `🚨 X Security Alerts` |
| 🏆 **Top Opportunities** | opportunityScore ≥ 60 | `🏆 Top 5 Opportunities` |
| 📊 **Smart Summary** | End of each scan | Avg opp, high value, urgent, security issues |

### Sample Telegram Card
```
🪂 DroperOG — 3 New Airdrops

🔥 ✅ EigenLayer
   🎯 Opp: ████████░░ 88% | ✅ Trust: █████████░ 85%
   🟢 Risk: low | ⟠
   🎯 90% · 💰 95% · 💪 40% · ⏰ 75%
   💰 Est. Value: $1200 · $24.5/hr
   Token: EIGEN
   https://eigenlayer.xyz

🔥 🟢 Scroll
   🎯 Opp: ██████░░░░ 55% | ✅ Trust: ██████░░░░ 60%
   🟢 Risk: low | 📜
   🎯 50% · 💰 70% · 💪 30% · ⏰ 10%
   💰 Est. Value: $200 · $3.5/hr
   https://scroll.io

🏆 Top Opportunities: EigenLayer, Scroll
```

---

## 📋 Checklist & Deadline Tracker

- ✅ **Auto-generated tasks** — follow socials, bridge assets, stake tokens, claim deadlines
- ⏰ **Deadline countdown** — 🔴 ≤1 day · 🟠 ≤3 days · 🟡 ≤7 days
- 💾 **Persistent storage** — `data/checklist.json`
- 📊 **Progress tracking** — `2/4 tasks` per project

```
📋 EigenLayer
  ✅ Follow on Twitter
  ✅ Follow on Discord
  ⬜ Complete on-chain transactions (by Dec 30, 2025)
  ⬜ Claim tokens (by Jan 15, 2026)

⏰ DEADLINE ALERTS:
  🟠 EigenLayer: "Claim tokens" — 3d left
  🟡 Scroll: "Complete tasks before deadline" — 5d left
```

---

## 🔍 Wallet Analyzer (Non-Custodial)

> 🔒 **No seed phrases · No private keys · No transaction signing**  
> Just a public wallet address for eligibility estimation

- ✅ Queries **6 EVM chains** — Ethereum, Arbitrum, Optimism, Base, Polygon, BSC
- 📊 Detects **transaction count & native balance** per chain
- 🏛️ Identifies **protocol usage** (Uniswap, Aave, GMX, PancakeSwap, etc.)
- 🎯 Estimates **airdrop eligibility** by matching wallet activity against project criteria
- 📈 Returns **compatibility score** with reasons & missing requirements

```
🔍 Analyzing wallet: 0xAb58...e9C9
  [arbitrum] 12 txs
  [bsc] 8 txs
  [ethereum] 45 txs

🟢 Top Matches:
  Uniswap Airdrop — 85%
    ✅ Active on ethereum (45 txs, min 10)
    ✅ Holds related protocol tokens
  Arbitrum Airdrop — 72%
    ✅ Active on arbitrum (12 txs)
    ⬜ Required contract interactions not detected
```

---

## 📱 PWA Dashboard

Installable on your phone's home screen:

| Filter Options | Sort Options | Display Features |
|----------------|-------------|------------------|
| 🌐 Chain (ETH, SOL, Base, Arb, OP, MATIC, BSC) | 🎯 Opportunity Score | Score bars with color coding |
| 📋 Status (Active, Upcoming, Confirmed, Potential) | ✅ Trust Score | Risk level indicators |
| 🛡️ Risk Level (Low → Critical) | 💰 Est. Value | Link warnings count |
| 🔍 Search by name/chain/description | ⚡ $/hr | 4-dimension detail row |
| 🆕 New (last 3 days) | ⏰ Urgency | Average opportunity in header |

---

## 🚀 Quick Start

```bash
# 1. Clone & install
git clone https://github.com/Misagh95/droperog.git
cd droperog
npm install

# 2. Run once
npm run dev -- --once

# 3. Analyze a wallet
npm run dev -- --wallet 0xYourWalletAddress
```

### ⚙️ Environment Variables

```env
# Telegram (optional — without it, runs in CLI-only mode)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 📦 Scripts

```bash
npm run build    # Compile TypeScript → dist/
npm start        # Run compiled version
npm run dev      # Run via ts-node (auto-refresh mode, every 20min)
npm run dev -- --once          # Single scan + exit
npm run dev -- --wallet 0x...  # Scan + analyze wallet
npm run scan                   # Scanner entry (used by GitHub Actions)
```

---

## 🧬 Architecture

```
src/
├── index.ts           🎯 Orchestrator — sources, dedup, scoring, display, CLI
├── trustChecker.ts    🛡️ Scam detection + 8-dimension scoring engine + link security
├── walletAnalyzer.ts  🔍 On-chain wallet analysis via public EVM RPCs
├── checklist.ts       📋 Task management per project + deadline tracker
├── telegram.ts        🤖 Smart Telegram notifications (rich cards, alerts, digest)
├── scan.ts            🔄 GitHub Actions entry point (scan + notify + PWA export)
├── types.ts           📐 All TypeScript interfaces & types
├── utils.ts           🔧 Formatting helpers (emojis, time ago, bars, chains)
├── config.ts          ⚙️ Default config (sources, intervals, RPCs)
├── scrapers/
│   └── scraper.ts     🕷️ Web scraper with multiple source adapters
└── sources/
    ├── alphadrops.ts  🅰️ AlphaDrops API (156+ airdrops)
    ├── cryptorank.ts  📊 CryptoRank API (729+ projects)
    ├── coingecko.ts   🦎 CoinGecko API
    ├── coinranking.ts 💰 CoinRanking API
    ├── rss.ts         📰 RSS/Atom feed parser
    └── twitter.ts     🐦 Twitter scraper (Nitter)

docs/                  📱 PWA dashboard
├── index.html         Dashboard HTML
├── app.js             Dashboard logic (filters, sorting, rendering)
├── style.css          Dark theme styles
├── manifest.json      PWA manifest
└── sw.js              Service worker for offline caching
```

---

## 🗺️ Roadmap

- [x] 🎯 **8-dimension scoring engine** — legitimacy, reward, effort, urgency, scam risk, opportunity, value, $/hr
- [x] 🛡️ **Link security** — 7 phishing/threat detectors
- [x] 📱 **PWA dashboard** — risk filters, smart sorting, live data
- [x] 🤖 **Smart Telegram bot** — rich cards, urgency alerts, top digest
- [x] 📋 **Checklist & deadlines** — auto-generated tasks, countdown alerts
- [x] 🔍 **Wallet analyzer** — non-custodial on-chain eligibility estimation
- [ ] 🌐 **DeFiLlama, Layer3, Galxe** — more source integrations
- [ ] 📊 **Historical scoring** — track opportunity changes over time
- [ ] 🔔 **Deadline reminders via Telegram** — 7d/3d/1d countdowns
- [ ] 🌎 **Multi-language support** — English, Persian, Chinese, Turkish

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

1. 🍴 Fork the repo
2. 🌿 Create your feature branch (`git checkout -b feature/amazing`)
3. 💾 Commit (`git commit -m 'Add amazing feature'`)
4. 📤 Push (`git push origin feature/amazing`)
5. 🎯 Open a Pull Request

---

<p align="center">
  <img src="https://img.shields.io/badge/built%20with-%F0%9F%92%9C-purple?style=for-the-badge">
  <img src="https://img.shields.io/badge/%F0%9F%AA%82%20happy%20hunting!-8b5cf6?style=for-the-badge">
</p>

<p align="center">
  <a href="https://github.com/Misagh95/droperog/stargazers">⭐ Star</a>
  ·
  <a href="https://github.com/Misagh95/droperog/issues">🐛 Report Bug</a>
  ·
  <a href="https://github.com/Misagh95/droperog/discussions">💬 Discuss</a>
</p>

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/Misagh95">@Misagh95</a> · Contributions welcome!</sub>
</p>
