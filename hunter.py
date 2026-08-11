#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DroperOG Hunter v3 — شکار زودهنگام با فیلتر تازگی واقعی
========================================================
v3 چی عوض شد؟
  - منبع گیت‌هاب کاملاً حذف شد (نویز بود).
  - منبع جدید: AlphaDrops (فیلد addedDate = تاریخ واقعی ثبت هر ایردراپ + داده غنی:
    فاندینگ، چین، سیستم پوینت، وضعیت). این بهترین منبع «تازه» است.
  - CryptoRank هم با همان فیلتر createdAt (فقط موارد ۷ روز اخیر) + نماد توکن.
  - خبرهای ایردراپ/تستنت تازه از Google News.

فقط مواردی گزارش می‌شوند که تاریخ واقعی‌شان در بازه تازگی باشد — «اولین باری که
دیدم» دیگر به‌معنای «جدید» نیست.

استفاده:
  python hunter.py                      # فقط گزارش محلی
  python hunter.py --telegram           # + ارسال به تلگرام (فقط وقتی مورد تازه هست)
  python hunter.py --telegram --always  # + حتی وقتی تازه نیست هم پیام بفرست
  python hunter.py --dry-run            # پیش‌نمایش پیام بدون ارسال

تنظیم از طریق environment (اختیاری):
  HUNTER_FRESH_DAYS=7    # بازه تازگی کمپین/ایردراپ (روز)
  HUNTER_NEWS_DAYS=3     # بازه تازگی خبرهای ایردراپ (روز)
"""

import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR = BASE / "docs"
DOCS_DIR.mkdir(exist_ok=True)

HUNTER_STATE = DATA_DIR / "hunter_state.json"
HUNTER_REPORT = DATA_DIR / "hunter_report.txt"
HUNTER_REPORT_MD = DOCS_DIR / "hunter_report.md"
TRIAGE_CSV = DATA_DIR / "triage.csv"
HUNTER_LOG = DATA_DIR / "hunter_log.txt"

STATE_VERSION = 3

# URLs that failed completely after retries — a failed fetch must not be
# treated as "everything disappeared" (no false REMOVED / state reset).
FETCH_ERRORS: list[str] = []

HEADERS = {"User-Agent": "DroperOG-Hunter/3.0", "Accept": "application/json"}
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}

FRESH_DAYS = int(os.environ.get("HUNTER_FRESH_DAYS", "7"))
NEWS_DAYS = int(os.environ.get("HUNTER_NEWS_DAYS", "3"))


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(HUNTER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _request(url: str, timeout: int, params: dict | None, headers: dict, retries: int = 3):
    """GET with retry + exponential backoff. Returns response or None."""
    last_err = ""
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout, headers=headers)
            if r.status_code == 200:
                return r
            last_err = f"HTTP {r.status_code}"
            if r.status_code < 500:
                break  # client error — retrying won't help
        except Exception as e:
            last_err = str(e)
        if attempt < retries - 1:
            time.sleep(0.5 * (2 ** attempt) + random.uniform(0, 0.3))
    FETCH_ERRORS.append(url)
    log(f"  Error {url}: {last_err}")
    return None


def fetch_json(url: str, timeout: int = 20, params: dict | None = None) -> object:
    r = _request(url, timeout, params, HEADERS)
    if r is None:
        return None
    try:
        return r.json()
    except Exception as e:
        log(f"  Error {url}: {e}")
        return None


def fetch_text(url: str, timeout: int = 20, params: dict | None = None) -> str | None:
    r = _request(url, timeout, params, BROWSER_HEADERS)
    if r is None:
        return None
    return r.text


def stable_id(*parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def fresh_cutoff(days: int) -> datetime:
    """شروع روز «days» روز پیش — یعنی هر چیزی که از آن روز به بعد اضافه شده داخل بازه است."""
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)


# ─── 1) AlphaDrops — منبع اصلی «ایردراپ تازه» (addedDate واقعی + داده غنی) ──

AD_CAT_MAP = {
    "mainnet": {"Perps", "DEX", "DeFi", "Lending", "Staking", "RWA",
                "Stablecoin", "Predictions", "NFT", "Trading", "Farming"},
    "network": {"Network", "Infrastructure", "Privacy", "Bridge", "Oracle",
                "Wallet", "Tools", "Dashboard", "Verification"},
    "task": {"Social", "Gaming", "Earn", "Referral"},
}
HIDDEN_FUNDING = {"Undisclosed", "Hidden", "", None}


def categorize_alpha(item: dict) -> str:
    cats = set(item.get("categories") or [])
    for cat, kwset in AD_CAT_MAP.items():
        if cats & kwset:
            return cat
    text = f"{item.get('name', '')} {item.get('shortDescription', '')}".lower()
    if any(k in text for k in ("testnet", "faucet", "devnet", "sepolia")):
        return "testnet"
    if item.get("hasPoints"):
        return "points"
    return "newtracked"


def build_alpha_desc(item: dict) -> str:
    parts = []
    cats = item.get("categories") or []
    if cats:
        parts.append(", ".join(cats[:3]))
    funding = item.get("fundingAmount")
    if funding and funding not in HIDDEN_FUNDING:
        parts.append(funding)
    if item.get("hasPoints"):
        parts.append("🎯 پوینت فعال")
    if item.get("isFreeAccess"):
        parts.append("رایگان")
    chains = item.get("blockchains") or []
    if chains:
        parts.append("🔗 " + ", ".join(chains[:3]))
    sd = (item.get("shortDescription") or "").strip()
    if sd and len(parts) < 4:
        parts.append(sd[:80])
    return " | ".join(parts)


def fetch_alpha_drops_fresh(days: int = FRESH_DAYS) -> list[dict]:
    """ایردراپ‌هایی که در N روز اخیر اضافه شده‌اند (addedDate) و هنوز فعال‌اند."""
    data = fetch_json("https://alphadrops.net/api/airdrops")
    if not isinstance(data, list):
        log("  alphadrops: no data")
        return []
    cutoff = fresh_cutoff(days)
    out = []
    for a in data:
        if a.get("premiumOnly"):
            continue
        status = a.get("status") or ""
        if status not in ("active", "upcoming"):
            continue
        added = parse_dt(a.get("addedDate"))
        if not added or added < cutoff:
            continue
        name = a.get("name") or "Unknown"
        cat = categorize_alpha(a)
        website = a.get("website") or ""
        url = website or f"https://alphadrops.net/airdrops/{a.get('slug', '')}"
        out.append({
            "id": f"ad_{stable_id(a.get('id') or a.get('slug') or name)}",
            "name": name,
            "category": cat,
            "source": "alphadrops",
            "url": url,
            "desc": build_alpha_desc(a),
            "date": added,
            "cost": 0 if a.get("isFreeAccess") else None,
        })
    log(f"  alphadrops: {len(out)} fresh airdrops (last {days}d)")
    return out


# ─── 2) CryptoRank — کمپین‌های تازه ثبت‌شده ─────────────────────────────

CAT_KEYWORDS = {
    "testnet": ("testnet", "faucet", "devnet", "sepolia", "test network"),
    "task": ("social", "quest", "galxe", "zealy", "bounty", "ambassador",
             "referral", "discord", "telegram", "twitter", "check-in", "checkin",
             "task", "airdrop", "event", "quiz", "survey"),
    "points": ("points", "point", "xp", "season", "campaign"),
    "mainnet": ("swap", "trade", "trading", "liquidity", "staking", "stake",
                "deposit", "bridge", "perpetual", "perps", "spot", "lending",
                "borrow", "mint", "nft"),
}


def categorize_crypto_rank(item: dict) -> str:
    types = " ".join(item.get("activityTypes") or []).lower()
    reward = str(item.get("rewardType") or "").lower()
    name = str((item.get("coin") or {}).get("name") or "").lower()
    text = f"{types} {reward} {name}"
    for cat, kws in CAT_KEYWORDS.items():
        if any(k in text for k in kws):
            return cat
    return "newtracked"


def fetch_crypto_rank_fresh(days: int = FRESH_DAYS) -> list[dict]:
    """کمپین‌هایی که در N روز اخیر ثبت شده‌اند (createdAt) و هنوز فعال‌اند."""
    base = "https://api.cryptorank.io/v0/drop-hunting/activities/table/public"
    cutoff = fresh_cutoff(days)
    all_items = []
    offset = 0
    limit = 100
    while True:
        data = fetch_json(base, params={"limit": limit, "offset": offset})
        if not data or not isinstance(data, dict):
            break
        items = data.get("data") or []
        all_items.extend(items)
        count = data.get("count", 0)
        offset += len(items)
        if len(items) < limit or offset >= count:
            break
        time.sleep(0.3)

    out = []
    for it in all_items:
        created = parse_dt(it.get("createdAt"))
        if not created or created < cutoff:
            continue
        status = it.get("status") or ""
        if status in ("ENDED", "REWARD_AVAILABLE"):
            continue
        coin = it.get("coin") or {}
        name = coin.get("name") or it.get("name") or "Unknown"
        symbol = coin.get("symbol") or ""
        key = it.get("key") or coin.get("key") or ""
        desc_parts = []
        if symbol:
            desc_parts.append(symbol)
        if it.get("rewardType"):
            desc_parts.append(f"🎁 {it['rewardType']}")
        if coin.get("totalRaise"):
            desc_parts.append(f"💰 ${coin['totalRaise']:,}")
        cost = it.get("cost")
        if cost is not None:
            desc_parts.append("رایگان" if cost == 0 else f"${cost}")
        if it.get("time"):
            desc_parts.append(f"⏱ {it['time']}min")
        cat = categorize_crypto_rank(it)
        out.append({
            "id": f"cr_{stable_id(key or name)}",
            "name": f"{name}" + (f" ({symbol})" if symbol else ""),
            "category": cat,
            "source": "cryptorank",
            "url": it.get("checkLink") or it.get("linkToClaim") or f"https://cryptorank.io/price/{key}",
            "desc": " | ".join(desc_parts),
            "date": created,
            "cost": cost,
        })
    log(f"  cryptorank: {len(out)} fresh campaigns (last {days}d)")
    return out


# ─── 2b) DropJet — لیست رایگان/کیوریت‌شده ایردراپ‌ها (WP REST API) ─────

DROPJET_API = "https://dropjet.co/wp-json/wp/v2"


def _wp_get(path: str, params: dict | None = None) -> object:
    return fetch_json(f"{DROPJET_API}/{path}", params=params)


def _wp_terms(taxonomy: str) -> dict[int, str]:
    """Fetch all terms of a DropJet taxonomy: {term_id: name}."""
    out: dict[int, str] = {}
    page = 1
    while True:
        data = _wp_get(taxonomy, {"per_page": 100, "page": page})
        if not isinstance(data, list) or not data:
            break
        for t in data:
            out[t.get("id")] = t.get("name") or t.get("slug") or ""
        if len(data) < 100:
            break
        page += 1
    return out


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def categorize_dropjet(cats: list[str], desc: str = "") -> str:
    text = " ".join(cats).lower() + " " + desc.lower()
    if any(k in text for k in ("testnet", "faucet", "devnet", "sepolia")):
        return "testnet"
    if any(k in text for k in ("social", "telegram mini apps", "raffle", "gamefi", "quest")):
        return "task"
    if any(k in text for k in ("points", "season", "campaign", "xp")):
        return "points"
    if any(k in text for k in ("layer 1", "layer 2", "dex", "defi", "lending",
                               "rollup", "tge", "mainnet", "trading")):
        return "mainnet"
    return "newtracked"


def fetch_dropjet_fresh(days: int = FRESH_DAYS) -> list[dict]:
    """DropJet airdrops added within the last N days (real publish date)."""
    cats = _wp_terms("airdrop_categories")
    chains = _wp_terms("blockchains")
    cutoff = fresh_cutoff(days)
    out = []
    page = 1
    while True:
        data = _wp_get("airdrops", {"per_page": 100, "page": page})
        if not isinstance(data, list) or not data:
            break
        for a in data:
            added = parse_dt(a.get("date") or a.get("date_gmt"))
            if not added or added < cutoff:
                continue
            name = (a.get("title") or {}).get("rendered") or "Unknown"
            cat_names = [cats.get(t) for t in (a.get("airdrop_categories") or []) if cats.get(t)]
            chain_names = [chains.get(t) for t in (a.get("blockchains") or []) if chains.get(t)]
            desc = _strip_html((a.get("content") or {}).get("rendered", ""))[:160]
            out.append({
                "id": f"dj_{a.get('id', '')}",
                "name": name,
                "category": categorize_dropjet(cat_names, desc),
                "source": "dropjet",
                "url": a.get("link") or "",
                "desc": ", ".join(cat_names[:4]) + (f" | 🔗 {', '.join(chain_names[:4])}" if chain_names else ""),
                "date": added,
                "cost": None,
            })
        if len(data) < 100:
            break
        page += 1
    log(f"  dropjet: {len(out)} fresh airdrops (last {days}d)")
    return out


# ─── 3) خبرهای ایردراپ/تستنت تازه (Google News) ────────────────────────

GSEARCH = "https://news.google.com/rss/search"
AIRDROP_QUERIES = [
    "airdrop testnet launch",
    "airdrop points program announcement",
    "\"testnet\" airdrop campaign new",
]
AIRDROP_BLOCKLIST = [
    "top ", "best ", "upcoming airdrops", "in 202", "roundup", "vip", "exclusive",
    "share $", "rewards in", "checklist", "list of", "watch", "guide to claim",
]


def parse_rss_items(xml: str) -> list[dict]:
    items = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        block = m.group(1)
        title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.S)
        link = re.search(r"<link>(.*?)</link>", block, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
        if not title:
            continue
        t = re.sub(r"\s+", " ", title.group(1)).strip()
        if t:
            items.append({"title": t, "url": (link.group(1).strip() if link else ""),
                          "pub": (pub.group(1).strip() if pub else "")})
    return items


def parse_pubdate(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            d = datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def strip_source(title: str) -> str:
    return re.sub(r"\s+-\s+[^-]{1,40}$", "", title).strip()


def airdrop_news_category(title: str) -> str:
    low = title.lower()
    if "testnet" in low or "faucet" in low or "devnet" in low or "sepolia" in low:
        return "testnet"
    if "points" in low or "season" in low or "portal" in low or "campaign" in low:
        return "points"
    return "task"


def fetch_airdrop_news(days: int = NEWS_DAYS) -> list[dict]:
    """اعلامیه‌های تازه ایردراپ/تستنت از اخبار — با فیلتر لیستیکل و پرومو."""
    out = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = [ex.submit(_airdrop_query, q, cutoff) for q in AIRDROP_QUERIES]
        for f in as_completed(futures):
            try:
                out.extend(f.result())
            except Exception as e:
                log(f"  gnews query error: {e}")
    return out


def _airdrop_query(q: str, cutoff: datetime) -> list[dict]:
    """Run one Google News query for airdrop/testnet announcements."""
    data = fetch_text(GSEARCH, params={"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    out = []
    if data:
        for it in parse_rss_items(data):
            title = strip_source(it["title"])
            low = title.lower()
            if any(b in low for b in AIRDROP_BLOCKLIST):
                continue
            if "airdrop" not in low and "testnet" not in low:
                continue
            pub = parse_pubdate(it["pub"])
            if pub and pub < cutoff:
                continue
            out.append({
                "id": f"h_news_{stable_id(title)}",
                "name": title,
                "category": airdrop_news_category(title),
                "source": "news",
                "url": it["url"],
                "desc": "",
                "date": pub,
            })
    log(f"  gnews '{q}': {len(out)} airdrop news")
    return out


# ─── دسته‌بندی / برچسب ────────────────────────────────────────────────

CAT_LABEL = {
    "testnet": "🟣 تست‌نت", "task": "🟡 تسک/کمپین", "points": "🔵 پوینت",
    "mainnet": "🟢 مین‌نت",
    "network": "🌐 شبکه/زیرساخت", "newtracked": "🆕 تازه در ترکر", "unknown": "❓ نامشخص",
}
CAT_ORDER = ["testnet", "points", "task", "mainnet", "network", "newtracked", "unknown"]

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def now_tehran() -> datetime:
    return datetime.now(timezone.utc).astimezone(TEHRAN_TZ)


def age_str(dt: datetime | None) -> str:
    if not dt:
        return ""
    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    hrs = int(delta.total_seconds() // 3600)
    if hrs < 1:
        return "(همین الان)"
    if hrs < 48:
        return f"({hrs}h پیش)"
    return f"({hrs // 24}d پیش)"


# ─── state / خروجی ────────────────────────────────────────────────────

def load_state() -> dict:
    if HUNTER_STATE.exists():
        try:
            st = json.loads(HUNTER_STATE.read_text("utf-8"))
            if st.get("v") == STATE_VERSION:
                return st
        except Exception:
            pass
    return {"v": STATE_VERSION, "seen": {}}


def save_state(state: dict):
    HUNTER_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), "utf-8")


def append_triage(items: list[dict]):
    new_file = not TRIAGE_CSV.exists()
    with open(TRIAGE_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["وضعیت", "نام", "دسته", "منبع", "لینک", "تاریخ", "شناسه"])
        for it in items:
            d = it.get("date")
            dstr = d.strftime("%Y-%m-%d") if d else ""
            w.writerow(["جدید", it["name"], CAT_LABEL.get(it["category"], it["category"]),
                        it["source"], it["url"], dstr, it["id"]])


def esc(s: object) -> str:
    """Escape text for Telegram HTML parse mode."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _truncate_html(text: str, limit: int = 3800) -> str:
    """Cut at a newline boundary so Telegram HTML tags stay well-formed."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit)
    if cut < 0:
        cut = limit
    return text[:cut] + "\n…"


def build_telegram_message(new_items: list[dict], fresh: dict) -> str:
    now = now_tehran()
    header = (f"🎯 <b>DroperOG Hunter</b> — {now.strftime('%Y-%m-%d %H:%M')} (تهران)\n"
              f"────────────────────")

    if not new_items:
        body = ("\n🔍 این اسکن: هیچ کمپین تازه‌ای (چند روز اخیر) پیدا نشد.\n"
                "📊 چشم‌انداز: " + "  |  ".join(
                    f"{CAT_LABEL[c]}: {fresh.get(c, 0)}" for c in CAT_ORDER if fresh.get(c, 0)) +
                "\n📋 جزئیات: docs/hunter_report.md")
        return f"{header}\n{body}"

    # defensive dedup by name — main() already dedups, but never show a
    # project twice in one message
    seen_names = set()
    uniq_items = []
    for it in new_items:
        k = (it.get("name") or "").strip().lower()
        if not k or k in seen_names:
            continue
        seen_names.add(k)
        uniq_items.append(it)

    lines = [header, f"\n🆕 <b>{len(uniq_items)} مورد تازه:</b>"]
    caps = {"testnet": 8, "points": 4, "task": 5,
            "mainnet": 5, "network": 6, "newtracked": 6, "unknown": 3}

    for cat in CAT_ORDER:
        items = sorted([x for x in uniq_items if x["category"] == cat],
                       key=lambda x: x.get("date") or x.get("first_seen"), reverse=True)
        if not items:
            continue
        lines.append(f"\n{CAT_LABEL[cat]} ({len(items)}):")
        for p in items[: caps.get(cat, 5)]:
            age = age_str(p.get("date"))
            nm = p["name"]
            if len(nm) > 70:
                nm = nm[:67] + "..."
            lines.append(f"<b>{esc(nm)}</b> {CAT_LABEL.get(p['category'], '')} {age}")
            lines.append(f"🔗 {p['url']}")
            if p.get("desc"):
                lines.append(f"<blockquote>{esc(p['desc'])}</blockquote>")
        if len(items) > caps.get(cat, 5):
            lines.append(f"  … و {len(items) - caps[cat]} مورد دیگر")

    summary = "  |  ".join(f"{CAT_LABEL[c]}: {fresh.get(c, 0)}" for c in CAT_ORDER if fresh.get(c, 0))
    lines.append(f"\n📊 <b>چشم‌انداز:</b> {summary}")
    lines.append("📋 جزئیات کامل: docs/hunter_report.md")

    return _truncate_html("\n".join(lines))


def send_telegram(text: str, dry_run: bool = False):
    if dry_run:
        print("\n────────── [DRY-RUN: پیام تلگرام] ──────────")
        print(text)
        print("────────────────────────────────────────────")
        return
    if not BOT_TOKEN or not CHAT_ID:
        log("  Telegram: BOT_TOKEN یا CHAT_ID تنظیم نشده — رد شد")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15,
        )
        ok = False
        if r.status_code == 200:
            try:
                ok = bool(r.json().get("ok"))
            except Exception:
                ok = False
        if ok:
            log("  Telegram sent")
        else:
            log(f"  Telegram error: HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"  Telegram error: {e}")


def build_markdown_report(new_items: list[dict], fresh: dict) -> str:
    now = now_tehran()
    lines = [f"# 🎯 DroperOG Hunter — {now.strftime('%Y-%m-%d %H:%M')} (تهران)", ""]
    if not new_items:
        lines.append("🔍 این اسکن: هیچ کمپین تازه‌ای (چند روز اخیر) پیدا نشد.")
    else:
        lines.append(f"🆕 **{len(new_items)} مورد تازه:**")
        lines.append("")
        for cat in CAT_ORDER:
            items = sorted([x for x in new_items if x["category"] == cat],
                           key=lambda x: x.get("date") or x.get("first_seen"), reverse=True)
            if not items:
                continue
            lines.append(f"## {CAT_LABEL[cat]} ({len(items)})")
            lines.append("")
            for p in items:
                lines.append(f"- **{p['name']}** {age_str(p.get('date'))}")
                lines.append(f"  - {p['url']}")
                if p.get("desc"):
                    lines.append(f"  - {p['desc']}")
            lines.append("")
    lines.append("---")
    lines.append("")
    summary = " | ".join(f"{CAT_LABEL[c]}: {fresh.get(c, 0)}" for c in CAT_ORDER if fresh.get(c, 0))
    lines.append(f"**چشم‌انداز:** {summary}")
    return "\n".join(lines)


def build_report(new_items: list[dict], fresh: dict) -> str:
    lines = []
    sep = "=" * 60
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(sep)
    lines.append(f"  DroperOG Hunter v3 — {now}   (شکار زودهنگام)")
    lines.append(sep)

    if not new_items:
        lines.append("\n  🆕 هیچ کمپین تازه‌ای (چند روز اخیر) پیدا نشد.")
    else:
        lines.append(f"\n  🆕 تازه ({len(new_items)}):")
        for p in sorted(new_items, key=lambda x: x.get("date") or x.get("first_seen"), reverse=True)[:30]:
            label = CAT_LABEL.get(p["category"], p["category"])
            lines.append(f"  {label} {p['name']}  {age_str(p.get('date'))}")
            lines.append(f"      {p['url']}")
            if p.get("desc"):
                lines.append(f"      {p['desc']}")

    lines.append(f"\n{'-' * 50}")
    lines.append("  📊 چشم‌انداز این اسکن:")
    for cat in CAT_ORDER:
        if fresh.get(cat):
            lines.append(f"  {CAT_LABEL[cat]}: {fresh[cat]}")
    lines.append(sep)
    lines.append("  📌 triage.csv به‌روزرسانی شد — بارانداز با خودته.")
    lines.append(sep)
    return "\n".join(lines)


# ─── تلگرام تنظیمات ───────────────────────────────────────────────────

BOT_TOKEN = (os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "")
CHAT_ID = (os.environ.get("CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID") or "")
try:
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text("utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if k in ("BOT_TOKEN", "TELEGRAM_BOT_TOKEN") and not BOT_TOKEN:
                    BOT_TOKEN = v
                if k in ("CHAT_ID", "TELEGRAM_CHAT_ID") and not CHAT_ID:
                    CHAT_ID = v
except Exception:
    pass


def main():
    log("DroperOG Hunter v3 starting...\n")

    send_flag = "--telegram" in sys.argv
    always_flag = "--always" in sys.argv
    dry_run = "--dry-run" in sys.argv

    state = load_state()
    seen = state.get("seen", {})

    log(f"Fetching 4 sources in parallel (AlphaDrops fresh {FRESH_DAYS}d, "
        f"CryptoRank fresh {FRESH_DAYS}d, DropJet fresh {FRESH_DAYS}d, "
        f"news fresh {NEWS_DAYS}d)...")
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_alpha = ex.submit(fetch_alpha_drops_fresh, days=FRESH_DAYS)
        f_cr = ex.submit(fetch_crypto_rank_fresh, days=FRESH_DAYS)
        f_dj = ex.submit(fetch_dropjet_fresh, days=FRESH_DAYS)
        f_news = ex.submit(fetch_airdrop_news, days=NEWS_DAYS)
        alpha = f_alpha.result()
        campaigns = f_cr.result()
        dropjet = f_dj.result()
        airdrop_news = f_news.result()
    log(f"  AlphaDrops: {len(alpha)} | CryptoRank: {len(campaigns)} | "
        f"DropJet: {len(dropjet)} | News: {len(airdrop_news)}")

    critical_failures = [u for u in FETCH_ERRORS
                         if "alphadrops" in u or "cryptorank" in u]
    if critical_failures:
        log(f"  Critical source(s) failed: {critical_failures} — aborting scan.")
        log("  Keeping previous state to avoid false REMOVED reports.")
        return
    if FETCH_ERRORS:
        log(f"  {len(FETCH_ERRORS)} non-critical fetch(es) failed (news) — continuing.")



    all_items = alpha + campaigns + dropjet + airdrop_news

    # فقط موارد واقعاً جدید برای ما
    new_items = []
    seen_names = set()
    for it in all_items:
        if it["id"] in seen:
            continue
        nm = it["name"].strip().lower()
        nm_key = nm[:45] if it["source"] in ("gnews", "news") else nm
        if nm_key in seen_names or not nm:
            continue
        seen_names.add(nm_key)
        first_seen = datetime.now(timezone.utc)
        it["first_seen"] = first_seen
        seen[it["id"]] = {"first_seen": first_seen.isoformat()}
        new_items.append(it)

    fresh = {}
    for it in all_items:
        fresh[it["category"]] = fresh.get(it["category"], 0) + 1

    state["seen"] = seen
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    if new_items:
        append_triage(new_items)
        log(f"   {len(new_items)} مورد جدید به triage.csv اضافه شد")

    report = build_report(new_items, fresh)
    print("\n" + report)
    HUNTER_REPORT.write_text(report, "utf-8")
    log(f"Report -> {HUNTER_REPORT}")

    try:
        md = build_markdown_report(new_items, fresh)
        HUNTER_REPORT_MD.write_text(md, "utf-8")
        log(f"Markdown -> {HUNTER_REPORT_MD}")
    except Exception as e:
        log(f"Markdown error: {e}")

    if send_flag and (new_items or always_flag):
        msg = build_telegram_message(new_items, fresh)
        send_telegram(msg, dry_run=dry_run)
    elif send_flag:
        log("  Telegram: مورد تازه‌ای نیست (برای پیام در هر حالت: --always)")


if __name__ == "__main__":
    main()
