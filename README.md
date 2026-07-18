<p align="center">
  <img src="https://img.shields.io/badge/DroperOG-v1.0.0-blueviolet?style=for-the-badge&logo=typescript" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/status-beta-orange?style=for-the-badge" alt="Status">
</p>

<h1 align="center">🪂 DroperOG</h1>
<p align="center"><b>Multi-Source Airdrop Hunter & Trust Scanner</b></p>
<p align="center">Scans CoinGecko 🦎 · CryptoRank 📊 · RSS 📰 · Twitter 🐦 · CoinRanking 🔗<br>in real-time to surface <b>new legitimate airdrop opportunities</b>.</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **5 Sources** | CoinGecko (trending + search), CryptoRank (NEXT_DATA), RSS feeds (airdrops.io), Twitter (Nitter), CoinRanking API |
| 🤖 **Trust Scoring** | Auto-calculates trust (0-100%) — flags scams, fake giveaways, suspicious patterns |
| 🔗 **Chain Detection** | Extracts chains (Ethereum, Solana, Arbitrum, Base, etc.) from project data |
| 🆕 **New-Project Alerts** | Tracks what's already seen, highlights brand-new finds |
| 🧹 **Noise Filtering** | Filters out established coins, spam, and irrelevant results |
| ⏱️ **Auto-Refresh** | Runs on a configurable interval (default: 20 min) |

## 🚀 Quick Start

```bash
# Clone & install
git clone https://github.com/Misagh95/droperog.git
cd droperog
npm install

# Run once
npm run dev -- --once

# Or run in auto-refresh mode
npm run dev
```

### ⚙️ Environment Variables

Copy `.env.example` → `.env` and optionally set:

```env
# CoinRanking API key (optional — without it, falls back to rate-limited access)
COINRANKING_API_KEY=your_key_here
```

## 📸 Output Preview

```
========================================================
   DroperOG - Airdrop Hunter
========================================================

  🔍 Scanning sources...
  ✓ CoinRanking: 3 projects
  ✓ CoinGecko: 17 projects
  ✓ RSS: 10 projects
  ✓ Twitter: 13 projects
  ✓ CryptoRank: 20 projects

  🆕 20 New Projects Found!

  🆕 TxFlow 🌐
     ├─ Trust: ███████░░░ 72%
     ├─ Chain: ❓
     ├─ Status: upcoming
     ├─ Link: https://cryptorank.io/drophunting/txflow
     ├─ Found: 15d ago
     ╰─ ✅ No red flags
     📝 Rating: 8/1000 | Tasks: Trading | Effort: 30pts / 20min

  📊 Total tracked: 41 projects
  🔄 Auto-check every 20 minutes.
```

## 🧠 Architecture

```
src/
├── index.ts           # Orchestrator — runs all sources, dedup, display
├── config.ts          # Toggles, intervals, Twitter accounts, RPCs
├── types.ts           # All TypeScript interfaces
├── utils.ts           # Formatting helpers (chain emojis, time ago, etc.)
├── trustChecker.ts    # Scam detection & trust scoring engine
├── scrapers/
│   └── scraper.ts     # Generic web scraper utilities
└── sources/
    ├── coingecko.ts   # CoinGecko trending & search API
    ├── coinranking.ts # CoinRanking API (new coins)
    ├── cryptorank.ts  # CryptoRank drophunting (NEXT_DATA)
    ├── rss.ts         # RSS/Atom feed parser
    └── twitter.ts     # Nitter-based Twitter scraper
```

## 🛡️ Trust Score Breakdown

| Factor | Bonus |
|--------|-------|
| 🔢 Rating > 100 | +15 pts |
| 🔢 Rating > 50 | +10 pts |
| 💰 Has fundraising | +10 pts |
| 🏦 Has VC backing | +10 pts |
| 🔗 Has claim link | +5 pts |
| 🐦 Twitter score > 1K | +5 pts |
| ✅ CONFIRMED status | +10 pts |
| ❌ Scam pattern match | ❌ Drops to 0–30 |

## 🔧 Commands

```bash
npm run build     # Compile TypeScript → dist/
npm start         # Run compiled version
npm run dev       # Run via ts-node (dev mode)
```

## 📦 Dependencies

- `axios` — HTTP requests
- `cheerio` — HTML parsing (fallback)
- `rss-parser` — RSS/Atom feeds
- `ethers` — Blockchain RPC (planned)
- `dotenv` — Environment variables

## 🗺️ Roadmap

- [x] 📬 Telegram bot notifications
- [x] 🤖 GitHub Actions auto-scanner (every 2h)
- [x] 🧠 First-run state build (no spam)
- [ ] 💰 On-chain balance verification for claim eligibility
- [ ] 🔍 DeFiLlama & more source integrations
- [ ] 📊 Historical trust-score tracking

---

<p align="center">
  🪂 <b>Happy Hunting!</b> 🪂
</p>
<p align="center">
  <sub>Built by <a href="https://github.com/Misagh95">@Misagh95</a> · Contributions welcome!</sub>
</p>
