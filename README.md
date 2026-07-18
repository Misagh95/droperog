<p align="center">
  <img src="https://img.shields.io/badge/DroperOG-v1.0.0-blueviolet?style=for-the-badge&logo=typescript" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/status-beta-orange?style=for-the-badge" alt="Status">
</p>

<h1 align="center">🪂 DroperOG</h1>
<p align="center"><b>شکارچی چندمنبعی ایردراپ — با اسکنر اعتماد خودکار</b></p>
<p align="right">اسکن می‌کند AlphaDrops 🅰️ · CryptoRank 📊 · RSS 📰 · Twitter 🐦 را<br>در لحظه برای یافتن <b>ایردراپ‌های معتبر جدید</b>.</p>

---

## ✨ قابلیت‌ها

| قابلیت | توضیح |
|--------|-------|
| 🔍 **۴ منبع** | AlphaDrops (REST API)، CryptoRank (API رسمی، ۷۲۹+ پروژه)، RSS (airdrops.io)، Twitter (Nitter) |
| 🤖 **امتیاز اعتماد** | محاسبه خودکار اعتماد (۰-۱۰۰٪) — تشخیص کلاهبرداری، تبلیغات جعلی، الگوهای مشکوک |
| 🔗 **تشخیص زنجیر** | استخراج زنجیرها (Ethereum، Solana، Arbitrum، Base و...) از داده پروژه |
| 🆕 **هشدار پروژه جدید** | تشخیص پروژه‌های دیده‌نشده و نمایش فقط جدیدها |
| 🧹 **فیلتر نویز** | حذف کوین‌های معروف، اسپم و نتایج نامرتبط |
| ⏱️ **بروزرسانی خودکار** | هر ۲ ساعت یکبار توسط GitHub Actions |
| 📱 **PWA موبایل** | داشبورد قابل نصب روی هوم‌صفحه گوشی |

## 🚀 شروع سریع

```bash
git clone https://github.com/Misagh95/droperog.git
cd droperog
npm install

# اجرای یکبار
npm run dev -- --once

# یا اجرای پیوسته
npm run dev
```

### ⚙️ متغیرهای محیطی

فایل `.env.example` → `.env` کپی کن و تنظیم کن:

```env
TELEGRAM_BOT_TOKEN=توکن_ربات_تت
TELEGRAM_CHAT_ID=آیدی_چت_تلگرام
```

## 📸 خروجی نمونه

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
     ├─ Link: https://cryptorank.io/drophunting/txflow
     ├─ Found: 1d ago
     ╰─ ✅ No red flags
     📝 Rating: 8/1000 | Tasks: Trading | Effort: 30pts / 20min

  📊 Total tracked: 715 projects
```

## 🧠 معماری

```
src/
├── index.ts           # هماهنگ‌کننده — اجرای همه منابع، dedup، نمایش
├── config.ts          # تنظیمات، تایمرها، اکانت‌های توییتر، RPCها
├── types.ts           # تمام اینترفیس‌های TypeScript
├── utils.ts           # توابع کمکی (ایموجی زنجیر، time ago و...)
├── trustChecker.ts    # موتور تشخیص کلاهبرداری و امتیاز اعتماد
├── telegram.ts        # ارسال نوتیفیکیشن به تلگرام
├── scan.ts            # نقطه ورود GitHub Actions
└── sources/
    ├── alphadrops.ts  # AlphaDrops API (۱۵۶+ ایردراپ)
    ├── cryptorank.ts  # CryptoRank API (۷۲۹+ پروژه، با pagination)
    ├── rss.ts         # خوراک RSS/Atom
    └── twitter.ts     # Twitter Scraper از طریق Nitter
```

## 🛡️ محاسبه امتیاز اعتماد

| فاکتور | امتیاز |
|--------|--------|
| 🔢 ریتینگ > ۱۰۰ | +۱۵ |
| 🔢 ریتینگ > ۵۰ | +۱۰ |
| 💰 جذب سرمایه دارد | +۱۰ |
| 🏦 پشتوانه VC دارد | +۱۰ |
| 🔗 لینک کلیم دارد | +۵ |
| 🐦 امتیاز توییتر > ۱K | +۵ |
| ✅ وضعیت CONFIRMED | +۱۰ |
| ❌ الگوی کلاهبرداری | ❌ افت به ۰–۳۰ |

## 🔧 دستورات

```bash
npm run build     # کامپایل TypeScript → dist/
npm start         # اجرای نسخه کامپایل شده
npm run dev       # اجرا با ts-node (حالت توسعه)
```

## 📱 PWA (داشبورد موبایل)

بعد از فعال کردن GitHub Pages درSettings > Pages > main > /docs:

```
https://misagh95.github.io/droperog/
```

می‌تونی ذخیره کنی رو هوم‌صفحه گوشی (Add to Home Screen) — مثل یه اپ واقعی کار می‌کنه.

## 🗺️ نقشه راه

- [x] 📬 نوتیفیکیشن تلگرام
- [x] 🤖 اسکنر خودکار GitHub Actions (هر ۲ ساعت)
- [x] 🧠 اولین اجرا بیصدا (بدون اسپم)
- [x] 📱 داشبورد PWA برای موبایل
- [ ] 💰 بررسی آن‌چین برای احراز Eligibility
- [ ] 🔍 منابع بیشتر (DeFiLlama و...)
- [ ] 📊 ردیابی تاریخچه امتیاز اعتماد

---

<p align="center">
  🪂 <b>شکار خوبی داشته باشی!</b> 🪂
</p>
<p align="center">
  <sub>ساخته شده توسط <a href="https://github.com/Misagh95">@Misagh95</a> · مشارکت خوش‌آمد است!</sub>
</p>
