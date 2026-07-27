# DroperOG v2

Multi-source airdrop monitor with auto-categorization (Testnet / Task Farmer / Mainnet) and change detection.

## Quick Start

```bash
pip install -r requirements.txt
python droperog.py
```

## Features

- **2 data sources:** AlphaDrops + CryptoRank (~400+ unique projects)
- **Auto-categorization:** 🟣 Testnet / 🟡 Social Tasks / 🟢 Mainnet
- **Change detection:** NEW 🆕 / UPDATED 🔄 / REMOVED 🗑️ shown on each run
- **Trust Score:** 0-95% based on funding, rating, status, and metadata
- **State persistence:** only deltas shown after the first run
- **Scheduling:** Windows Task Scheduler every 4h

## Schedule (Windows Task Scheduler)

```powershell
# Run as Administrator:
powershell -File setup_schedule.ps1       # every 4 hours
powershell -File setup_schedule.ps1 -Hours 6   # every 6 hours
```

## Output

```
==========================================================
  DroperOG v2 — 2026-07-27 17:11:55
==========================================================

  No new projects

--------------------------------------------------
  CATEGORIZED SUMMARY
--------------------------------------------------

🟣 Testnet (3):
  Fermah — 80% | $5.2M | Predictions, Testnet
  Tempo — 70% | $500M | Use Testnet, Complete Quests
  ...

🟢 Mainnet (75):
  Fomo — 85% | solana, base, ethereum | $94M
  Polymarket — 85% | polygon | $2.88B
  ...

🟡 Social Tasks (279):
  PIN AI — 95% | $10M | Social
  DogeOS — 85% | $6.9M
  ...

--------------------------------------------------
  Total: 357 | Testnet: 3 | Social Tasks: 279 | Mainnet: 75
==========================================================
```
