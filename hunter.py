#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DroperOG Hunter — ماژول شکار زودهنگام (Early Detection)
=========================================================
ایده: droperog.py لیست‌های عمومی (AlphaDrops, CryptoRank) رو می‌خونه که همیشه دیرن.
این ماژول منابعی رو مانیتور می‌کنه که پروژه‌ها قبل از دیده‌شدن در لیست‌های عمومی
توشون ظاهر می‌شن:

  1) تست‌نت‌های تازه        (dropjet.co/categories/testnet)
  2) خبرهای فاندینگ         (Google News RSS + CoinDesk/TheBlock: تازه پول جذب کرده = ایردراپ آینده)
  3) ریپوهای جدید گیت‌هاب   (پروژه‌های پری‌توکن تازه‌ساخته)

استفاده:
  python hunter.py                 # فقط گزارش محلی (خروجی terminal + فایل)
  python hunter.py --telegram      # + ارسال خلاصه تمیز به تلگرام (BOT_TOKEN/CHAT_ID)
  python hunter.py --always        # حتی وقتی مورد جدیدی نیست هم پیام بفرست
  python hunter.py --dry-run       # پیام تلگرام را چاپ کن ولی نفرست (برای تست)

خروجی‌ها:
  data/hunter_report.txt   گزارش متنی آخرین اجرا
  data/triage.csv          بارانداز شما (برای بارگذاری دستی)
  docs/hunter_report.md    گزارش تمیز به شکل Markdown (برای گیت‌هاب/کامیت)
"""

import csv
import hashlib
import json
import os
import re
import sys
import time
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

HEADERS = {"User-Agent": "DroperOG-Hunter/1.0", "Accept": "application/json"}
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def fetch_text(url: str, timeout: int = 20, headers: dict | None = None,
               params: dict | None = None) -> str | None:
    try:
        r = requests.get(url, timeout=timeout, headers=headers or BROWSER_HEADERS, params=params)
        return r.text if r.status_code == 200 else None
    except Exception as e:
        log(f"  Error {url}: {e}")
        return None


def fetch_json(url: str, timeout: int = 20, params: dict | None = None) -> object:
    try:
        r = requests.get(url, params=params, timeout=timeout, headers=HEADERS)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        log(f"  Error {url}: {e}")
        return None


# ─── 1) تست‌نت‌های تازه (dropjet) ─────────────────────────────────────

def slug_to_name(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split() if w)


def fetch_fresh_testnets() -> list[dict]:
    """لیست تست‌نت‌های فعال dropjet — هر کارت یک پروژه."""
    html = fetch_text("https://dropjet.co/categories/testnet/")
    if not html:
        log("  dropjet: no response")
        return []

    out = []
    # هر کارت: <article class="airdrop-post-item ..."> ... </article>
    for m in re.finditer(r'<article[^>]*class="[^"]*airdrop-post-item[^"]*"[^>]*>(.*?)</article>', html, re.S):
        block = m.group(1)
        pj = re.search(r'href="(https://dropjet\.co/airdrops/([^"/]+)/)"', block)
        if not pj:
            continue
        url, slug = pj.group(1), pj.group(2)
        title = ""
        tm = re.search(r"<h2[^>]*>\s*<a[^>]+href=\"[^\"]+\"[^>]*>(.*?)</a>", block, re.S)
        if tm:
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        out.append({
            "id": f"h_testnet_{slug}",
            "name": slug_to_name(slug),
            "category": "testnet",
            "source": "dropjet/testnet",
            "url": url,
            "desc": title,
            "date": None,  # زمان دیده‌شدن به‌عنوان معیار تازگی (در گزارش ست می‌شود)
        })
    log(f"  dropjet: {len(out)} testnet items")
    return out


# ─── 2) خبرهای فاندینگ ────────────────────────────────────────────────

GSEARCH = "https://news.google.com/rss/search"
FUNDING_QUERIES = [
    "crypto raises funding",
    "crypto startup secures funding",
]
SECONDARY_FEEDS = [
    ("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("theblock", "https://www.theblock.co/rss.xml"),
]
FUNDING_KEYWORDS = [
    "raises", "raised", "raise", "funding", "seed round", "series a", "series b",
    "series c", "led by", "valuation", "secures", "backers", "round led",
]
# عنوان‌هایی که «raise» دارند ولی خبر فاندینگ نیستند
FUNDING_BLOCKLIST = [
    "sues", "lawsuit", "tax", "saylor", "raises stakes", "freeze", "hack",
    "price", "etf", "inflow", "outflow", "chart", "market",
]


def is_funding_news(title: str) -> bool:
    low = title.lower()
    if any(b in low for b in FUNDING_BLOCKLIST):
        return False
    if not any(k in low for k in FUNDING_KEYWORDS):
        return False
    # حداقل یک نشانه پولی واقعی لازم است
    if extract_funding_amount(title):
        return True
    return any(k in low for k in ("funding round", "valuation", "seed round", "series a", "series b", "series c"))


def stable_id(*parts: str) -> str:
    """شناسه پایدار و بیناجرایی (برخلاف hash() که در هر اجرا تغییر میکند)."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


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
            items.append({
                "title": t,
                "url": (link.group(1).strip() if link else ""),
                "pub": (pub.group(1).strip() if pub else ""),
            })
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


def extract_funding_amount(text: str) -> str:
    m = re.search(r"\$\s?(\d+(?:\.\d+)?)\s?(M|Million|million|B|Billion|billion|K|k)?", text)
    if not m:
        return ""
    amt, unit = m.group(1), (m.group(2) or "").lower()
    if unit.startswith("b"):
        return f"${amt}B"
    if unit.startswith("m"):
        return f"${amt}M"
    return f"${amt}"


def strip_source(title: str) -> str:
    """Google News عنوان را با « - منبع» تمام می‌کند؛ حذفش کن."""
    return re.sub(r"\s+-\s+[^-]{1,40}$", "", title).strip()


def fetch_funding_news(days: int = 3) -> list[dict]:
    out = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    for q in FUNDING_QUERIES:
        data = fetch_text(GSEARCH, params={"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        if not data:
            log(f"  gnews '{q}': no response")
            time.sleep(2)
            continue
        n = 0
        for it in parse_rss_items(data):
            title = strip_source(it["title"])
            if not is_funding_news(title):
                continue
            pub = parse_pubdate(it["pub"])
            if pub and pub < cutoff:
                continue
            amt = extract_funding_amount(title)
            out.append({
                "id": f"h_fund_gnews_{stable_id(title)}",
                "name": title,
                "category": "funding",
                "source": "gnews",
                "url": it["url"],
                "desc": amt,
                "date": pub,
            })
            n += 1
        log(f"  gnews '{q}': {n} funding items")
        time.sleep(2)

    for src, url in SECONDARY_FEEDS:
        xml = fetch_text(url)
        if not xml:
            log(f"  {src}: no response")
            continue
        n = 0
        for it in parse_rss_items(xml):
            if not is_funding_news(it["title"]):
                continue
            pub = parse_pubdate(it["pub"])
            if pub and pub < cutoff:
                continue
            out.append({
                "id": f"h_fund_{src}_{stable_id(it['url'])}",
                "name": it["title"],
                "category": "funding",
                "source": f"funding/{src}",
                "url": it["url"],
                "desc": extract_funding_amount(it["title"]),
                "date": pub,
            })
            n += 1
        log(f"  {src}: {n} funding items")
        time.sleep(1)
    return out


# ─── 3) ریپوهای جدید گیت‌هاب ──────────────────────────────────────────

def github_fresh_repos(days: int = 7) -> list[dict]:
    """پروژه‌های تازه‌ساخته مرتبط با ایردراپ — سیگنال خیلی زودرس."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    queries = [
        ("airdrop testnet created:>" + since, "testnet"),
        ("airdrop points program created:>" + since, "points"),
        ("testnet quest created:>" + since, "testnet"),
    ]
    out = []
    for q, hint in queries:
        data = fetch_json("https://api.github.com/search/repositories",
                          params={"q": q, "sort": "created", "order": "desc", "per_page": 12})
        if not data or "items" not in data:
            log(f"  github: no data for '{q}' (rate limit؟)")
            time.sleep(10)
            continue
        n = 0
        for r in data["items"]:
            created = r.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                dt = None
            name = r.get("full_name", "")
            desc = (r.get("description") or "").strip()
            out.append({
                "id": f"h_gh_{name}",
                "name": name,
                "category": hint,
                "source": "github",
                "url": r.get("html_url", ""),
                "desc": f"{desc} | ⭐{r.get('stargazers_count', 0)}",
                "date": dt,
            })
            n += 1
        log(f"  github '{q}': {n} repos")
        time.sleep(8)  # rate limit بدون API-key: 10 در دقیقه
    return out


# ─── دسته‌بندی نهایی ──────────────────────────────────────────────────

def refine_category(item: dict) -> str:
    text = f"{item.get('name', '')} {item.get('desc', '')}".lower()
    if item["category"] == "funding":
        return "funding"
    if "testnet" in text or "faucet" in text or "sepolia" in text or "devnet" in text:
        return "testnet"
    if "points" in text or "season" in text or "check-in" in text or "checkin" in text or " xp " in text:
        return "points"
    if "quest" in text or "galxe" in text or "zealy" in text or "task" in text:
        return "task"
    if any(k in text for k in ("swap", "trade", "stake", "deposit", "liquidity", "bridge", "dex")):
        return "mainnet"
    return "unknown"


def funding_dedup_key(name: str) -> str:
    """کلید یکتا برای خبرهای هم‌داستان: «نام پروژه|مبلغ» — مثلاً firmus|2b"""
    low = name.lower()
    mm = re.search(r"(raises|raised|secures|securing|closes)\s+\$?\s*(\d+(?:\.\d+)?)\s*(m|b|k)?", low)
    if mm:
        before = low[: mm.start()].rstrip()
        tokens = [t for t in re.split(r"[^a-z0-9.]+", before) if t]
        entity = tokens[-1] if tokens else ""
        return f"{entity}|{mm.group(2)}{mm.group(3) or ''}"
    return low[:45]


CAT_LABEL = {
    "testnet": "🟣 تست‌نت", "task": "🟡 تسک اجتماعی", "points": "🔵 سیستم پوینت",
    "funding": "💰 خبر فاندینگ", "mainnet": "🟢 مین‌نت", "unknown": "❓ نامشخص",
}
CAT_ORDER = ["testnet", "funding", "points", "task", "mainnet", "unknown"]


# ─── state / گزارش / بارانداز ─────────────────────────────────────────

def load_state() -> dict:
    if HUNTER_STATE.exists():
        try:
            return json.loads(HUNTER_STATE.read_text("utf-8"))
        except Exception:
            pass
    return {"seen": {}, "last_run": None}


def save_state(state: dict):
    HUNTER_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), "utf-8")


def append_triage(items: list[dict]):
    """بارانداز تو: هر آیتم جدید به CSV اضافه می‌شه، تو وضعیتش رو تعیین می‌کنی."""
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


def build_report(new_items: list[dict], fresh: dict) -> str:
    lines = []
    sep = "=" * 60
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(sep)
    lines.append(f"  DroperOG Hunter — {now}   (شکار زودهنگام)")
    lines.append(sep)

    if not new_items:
        lines.append("\n  🆕 هیچ مورد تازه‌ای نسبت به اجرای قبلی پیدا نشد.")
        lines.append("  (این یعنی تا اسکن بعدی چیزی جدید توی منابع ظاهر نشده؛ بارانداز CSV رو چک کن.)")
    else:
        lines.append(f"\n  🆕 جدید ({len(new_items)}) — مرتب بر اساس تازگی:")
        for p in sorted(new_items, key=lambda x: x.get("date") or x["first_seen"], reverse=True)[:30]:
            src_date = p.get("date") or p["first_seen"]
            delta = datetime.now(timezone.utc) - src_date
            hrs = int(delta.total_seconds() // 3600)
            age = f"({hrs}h پیش)" if hrs < 48 else f"({hrs // 24}d پیش)"
            label = CAT_LABEL.get(p["category"], p["category"])
            lines.append(f"  {label} {p['name']}  {age}")
            lines.append(f"      {p['url']}")
            if p.get("desc"):
                lines.append(f"      {p['desc']}")
        if len(new_items) > 30:
            lines.append(f"      ... و {len(new_items) - 30} مورد دیگر")

    lines.append(f"\n{'-' * 50}")
    lines.append("  📊 چشم‌انداز این اسکن بر اساس دسته:")
    for cat in CAT_ORDER:
        n = fresh.get(cat, 0)
        if n:
            lines.append(f"  {CAT_LABEL[cat]}: {n}")
    lines.append(f"  جمع: {sum(fresh.values())}")

    lines.append(sep)
    lines.append("  📌 triage.csv به‌روزرسانی شد — بارانداز با خودته.")
    lines.append(sep)
    return "\n".join(lines)


# ─── تلگرام ───────────────────────────────────────────────────────────

BOT_TOKEN = (os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "")
CHAT_ID = (os.environ.get("CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID") or "")
# بارگذاری از .env (برای اجرای محلی)
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


def build_telegram_message(new_items: list[dict], fresh: dict) -> str:
    """پیام تمیز برای تلگرام — کوتاه، مرتب، قابل اسکن سریع."""
    now = now_tehran()
    header = (f"🎯 DroperOG Hunter — {now.strftime('%Y-%m-%d %H:%M')} (تهران)\n"
              f"────────────────────")

    if not new_items:
        body = ("\n🔍 هیچ مورد جدیدی پیدا نشد.\n"
                "کاسه خالیه، ولی همین یه علامت خوبه: یعنی هنوز کسی جلو نیفتاده.\n"
                "📋 گزارش قبلی: docs/hunter_report.md")
        return f"{header}\n{body}"

    lines = [header, f"\n🆕 {len(new_items)} مورد جدید پیدا شد:"]

    # دسته‌ها به ترتیب اهمیت
    order = [("testnet", "🟣 تست‌نت"), ("funding", "💰 فاندینگ"),
             ("points", "🔵 پوینت"), ("task", "🟡 تسک"),
             ("mainnet", "🟢 مین‌نت"), ("unknown", "❓ نامشخص")]
    caps = {"testnet": 8, "funding": 5, "points": 4, "task": 4, "mainnet": 3, "unknown": 3}

    for cat, label in order:
        items = [x for x in new_items if x["category"] == cat]
        if not items:
            continue
        items.sort(key=lambda x: x.get("date") or x.get("first_seen"), reverse=True)
        lines.append(f"\n{label} ({len(items)}):")
        for p in items[: caps.get(cat, 5)]:
            age = age_str(p.get("date"))
            nm = p["name"]
            if len(nm) > 70:
                nm = nm[:67] + "..."
            lines.append(f"• {nm} {age}")
            lines.append(f"  {p['url']}")
        if len(items) > caps.get(cat, 5):
            lines.append(f"  … و {len(items) - caps[cat]} مورد دیگر")

    summary = "  |  ".join(f"{lbl}: {fresh.get(c, 0)}" for c, lbl in order if fresh.get(c, 0))
    lines.append(f"\n📊 چشم‌انداز: {summary}")
    lines.append("📋 جزئیات کامل: docs/hunter_report.md")

    # محدودیت طول تلگرام (4096)
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n…"
    return text


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
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=15,
        )
        log("  Telegram sent")
    except Exception as e:
        log(f"  Telegram error: {e}")


def build_markdown_report(new_items: list[dict], fresh: dict) -> str:
    """گزارش تمیز Markdown برای docs/hunter_report.md (قابل دیدن در گیت‌هاب)."""
    now = now_tehran()
    lines = [f"# 🎯 DroperOG Hunter — {now.strftime('%Y-%m-%d %H:%M')} (تهران)", ""]
    if not new_items:
        lines.append("🔍 هیچ مورد جدیدی پیدا نشد.")
    else:
        lines.append(f"🆕 **{len(new_items)} مورد جدید:**")
        lines.append("")
        order = [("testnet", "🟣 تست‌نت"), ("funding", "💰 فاندینگ"),
                 ("points", "🔵 پوینت"), ("task", "🟡 تسک"),
                 ("mainnet", "🟢 مین‌نت"), ("unknown", "❓ نامشخص")]
        for cat, label in order:
            items = [x for x in new_items if x["category"] == cat]
            if not items:
                continue
            items.sort(key=lambda x: x.get("date") or x.get("first_seen"), reverse=True)
            lines.append(f"## {label} ({len(items)})")
            lines.append("")
            for p in items:
                age = age_str(p.get("date"))
                lines.append(f"- **{p['name']}** {age}")
                lines.append(f"  - {p['url']}")
                if p.get("desc"):
                    lines.append(f"  - {p['desc']}")
            lines.append("")
    lines.append("---")
    lines.append("")
    summary = " | ".join(f"{lbl}: {fresh.get(c, 0)}" for c, lbl in order if fresh.get(c, 0))
    lines.append(f"**چشم‌انداز:** {summary}")
    return "\n".join(lines)


# ─── main ─────────────────────────────────────────────────────────────

def main():
    log("DroperOG Hunter starting...\n")

    send_telegram_flag = "--telegram" in sys.argv
    always_flag = "--always" in sys.argv
    dry_run = "--dry-run" in sys.argv

    state = load_state()
    seen = state.get("seen", {})

    log("1) تست‌نت‌های تازه (dropjet)...")
    testnets = fetch_fresh_testnets()

    log("2) خبرهای فاندینگ...")
    funding = fetch_funding_news(days=3)

    log("3) ریپوهای جدید گیت‌هاب...")
    repos = github_fresh_repos(days=7)

    all_items = testnets + funding + repos
    for it in all_items:
        it["category"] = refine_category(it)

    # dedup: فقط جدیدها (بر اساس id + کلید داستانی فاندینگ)
    new_items = []
    seen_names = set()
    seen_fund_keys = set(state.get("seen_fund_keys", []))
    for it in all_items:
        key = it["id"]
        if key in seen:
            continue
        if it["category"] == "funding":
            nm = funding_dedup_key(it["name"])
            if nm in seen_fund_keys:
                continue
            seen_fund_keys.add(nm)
        else:
            nm = it["name"].strip().lower()
            if nm in seen_names or not nm:
                continue
        seen_names.add(nm)
        first_seen = datetime.now(timezone.utc)
        it["first_seen"] = first_seen
        seen[key] = {"first_seen": first_seen.isoformat()}
        new_items.append(it)

    # چشم‌انداز: شمارش همه موارد این اسکن (قدیمی + جدید)
    fresh = {}
    for it in all_items:
        fresh[it["category"]] = fresh.get(it["category"], 0) + 1

    state["seen"] = seen
    state["seen_fund_keys"] = sorted(seen_fund_keys)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    if new_items:
        append_triage(new_items)
        log(f"   {len(new_items)} مورد جدید به triage.csv اضافه شد")

    report = build_report(new_items, fresh)
    print("\n" + report)
    HUNTER_REPORT.write_text(report, "utf-8")
    log(f"Report -> {HUNTER_REPORT}")

    # گزارش Markdown برای گیت‌هاب (docs/hunter_report.md)
    try:
        md = build_markdown_report(new_items, fresh)
        HUNTER_REPORT_MD.write_text(md, "utf-8")
        log(f"Markdown -> {HUNTER_REPORT_MD}")
    except Exception as e:
        log(f"Markdown error: {e}")

    # تلگرام
    if send_telegram_flag:
        if new_items or always_flag:
            msg = build_telegram_message(new_items, fresh)
            send_telegram(msg, dry_run=dry_run)
        else:
            log("  Telegram: مورد جدیدی نیست (از --always برای پیام در هر حالت استفاده کن)")


if __name__ == "__main__":
    main()
