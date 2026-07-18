<p align="center">
  <img src="https://img.shields.io/badge/DroperOG-v1.0.0-blueviolet?style=for-the-badge&logo=typescript" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/status-beta-orange?style=for-the-badge" alt="Status">
</p>

<h1 align="center">🪂 DroperOG</h1>
<p align="center"><b>Multi-Source Airdrop Hunter & Trust Scanner</b></p>
<p align="center">Scans AlphaDrops 🅰️ · CryptoRank 📊 · RSS 📰 · Twitter 🐦<br>in real-time to surface <b>new legitimate airdrop opportunities</b>.</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **4 Sources** | AlphaDrops (REST API), CryptoRank (official API, 729+ projects), RSS (airdrops.io), Twitter (Nitter) |
| 🤖 **Trust Scoring** | Auto-calculates trust (0-100%) — flags scams, fake giveaways, suspicious patterns |
| 🔗 **Chain Detection** | Extracts chains (Ethereum, Solana, Arbitrum, Base, etc.) from project data |
| 🆕 **New-Project Alerts** | Tracks what's already seen, highlights brand-new finds |
| 🧹 **Noise Filtering** | Filters out old projects (>6mo), spam, and irrelevant results |
| ⏱️ **Auto-Refresh** | Runs on GitHub Actions every 2 hours |
| 📱 **PWA Dashboard** | Installable mobile dashboard with filters & sorting |

## 🚀 Quick Start

```bash
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
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 📸 Output Preview

```
========================================================
   DroperOG - Airdrop Hunter
========================================================

  🔍 Scanning sources...
  ✓ CryptoRank: 729 projects
  ✓ RSS: 10 projects
  ✓ AlphaDrops: 6 projects

  🆕 3 New Projects Found!

  💎 TxFlow 🌐
     ├─ Trust: ███████░░░ 72%
     ├─ Chain: ❓
     ├─ Status: potential
     ├─ Link: https://cryptorank.io/price/txflow
     ├─ Found: 1d ago
     ╰─ ✅ No red flags
     📝 Rating: 8/1000 | Tasks: Trading | Effort: 30pts / 20min

  📊 Total tracked: 159 projects
```

## 🧠 Architecture

```
src/
├── index.ts           # Orchestrator — runs all sources, dedup, display
├── config.ts          # Toggles, intervals, Twitter accounts, RPCs
├── types.ts           # All TypeScript interfaces
├── utils.ts           # Formatting helpers (chain emojis, time ago, etc.)
├── trustChecker.ts    # Scam detection & trust scoring engine
├── telegram.ts        # Telegram notification sender
├── scan.ts            # GitHub Actions entry point
└── sources/
    ├── alphadrops.ts  # AlphaDrops API (156+ airdrops)
    ├── cryptorank.ts  # CryptoRank API (729+ projects, paginated)
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
| ❌ Scam pattern match | ❌ Drops to 0-30 |

## 🔧 Commands

```bash
npm run build     # Compile TypeScript → dist/
npm start         # Run compiled version
npm run dev       # Run via ts-node (dev mode)
npm run scan      # Run scanner once (used by GitHub Actions)
```

## 📦 Dependencies

- `axios` — HTTP requests
- `rss-parser` — RSS/Atom feeds
- `ethers` — Blockchain RPC (planned)
- `dotenv` — Environment variables

## 🗺️ Roadmap

- [x] 📬 Telegram bot notifications
- [x] 🤖 GitHub Actions auto-scanner (every 2h)
- [x] 🧠 First-run state build (no spam)
- [x] 📱 PWA dashboard for mobile
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
