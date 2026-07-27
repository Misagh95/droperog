# DroperOG v2

هانتینگ خودکار ایردراپ با دسته‌بندی سه‌گانه (تست‌نت / تسک فارمر / مین‌نت) و تشخیص تغییرات

## Quick Start

```bash
pip install -r requirements.txt
python droperog.py
```

```powershell
# یا اجرای مستقیم:
python droperog.py
```

## Features

- **۲ منبع داده:** AlphaDrops + CryptoRank (~700+ پروژه)
- **دسته‌بندی خودکار:** 🟣 Testnet / 🟡 Task Farmer / 🟢 Mainnet
- **تشخیص تغییرات:** پروژه‌های جدید 🆕 / آپدیت شده 🔄 / حذف شده 🗑️
- **Trust Score:** براساس فاندینگ، ریتینگ، وضعیت و ویژگی‌ها
- **ذخیره وضعیت:** فقط تغییرات بین ران‌ها نشون داده می‌شه
- **قابلیت زمان‌بندی:** اجرا خودکار هر ۴ ساعت

## Schedule (Windows Task Scheduler)

```powershell
# Administrator:
powershell -File setup_schedule.ps1    # هر ۴ ساعت
powershell -File setup_schedule.ps1 -Hours 6   # هر ۶ ساعت
```

## Output

```
==========================================================
  DroperOG v2 — 2026-07-27 17:11:55
==========================================================

  No new projects

--------------------------------------------------
  CATEGORIZED SUMMARY (Trust >= 65)
--------------------------------------------------

🟣 Testnet (7):
  Soul Labs — 80% | ethereum
  Ithaca — 70% | ethereum | Faucet
  ...

🟢 Mainnet (80):
  Fomo — 85% | solana, base, ethereum | $15M
  ...

🟡 Task Farmer (676):
  PIN AI — 75% | ethereum | Social
  ...

--------------------------------------------------
  Total: 763 | Testnet: 7 | Task Farmer: 676 | Mainnet: 80
==========================================================
```
