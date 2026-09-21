# DroperOG v2

<p align="center">
  <img src="docs/logo.png" width="150" height="150" alt="DroperOG v2 Logo" style="border-radius:50%; box-shadow: 0 4px 20px rgba(88,166,255,.2);">
</p>

Multi-source airdrop monitor with auto-categorization (Testnet / Task Farmer / Mainnet) and change detection.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # set BOT_TOKEN and CHAT_ID
python droperog.py
```

## Features

- **3 data sources:** AlphaDrops + CryptoRank + DropJet (~800+ unique projects)
- **Auto-categorization:** 🟣 Testnet / 🟡 Social Tasks / 🟢 Mainnet
- **Change detection:** NEW 🆕 / UPDATED 🔄 / REMOVED 🗑️ shown on each run
- **Trust Score:** 0-95% based on funding, rating, status, and metadata
- **State persistence:** only deltas shown after the first run
- **Scheduling:** Windows Task Scheduler every 4h
- **Honest health reporting:** a single broken source never kills the scan.
  Exit codes: `0` ok · `1` degraded (source down / Telegram failed) · `2` aborted
  (no source returned data). Every run also writes `data/scan_status.json` for CI.
- **Watchdog:** if the last fully-healthy scan is older than 12h, the bot warns
  on Telegram (with a 6h cooldown so it doesn't spam).
- **No lost alerts:** Telegram messages are split under the 4096-unit limit and
  state is only persisted *after* a successful delivery — a failed send means
  the news is re-announced on the next run instead of silently vanishing.

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

## Telegram (optional)

Set `BOT_TOKEN` and `CHAT_ID` in `.env`:

```
🪂 Airdrop Scan — 17:42

🆕 New (3)
  PIN AI  ·  Social Tasks  ·  https://...  ·  Social, Fill The Form
  Fomo  ·  Mainnet  ·  https://...  ·  Trade Perps
  Soul Labs  ·  Testnet  ·  https://...  ·  Testnet, Faucet

📊 Summary
  🟣 Testnet: 8
  🟢 Mainnet: 89
  🟡 Social Tasks: 667
  ────────────
  Total: 764
```
