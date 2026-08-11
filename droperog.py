#!/usr/bin/env python3
"""
DroperOG v2 — Multi-source airdrop hunter with auto-categorization & monitoring
"""

import json, os, random, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
STATE_FILE = DATA_DIR / "state.json"
REPORT_FILE = DATA_DIR / "last_report.txt"
LOG_FILE = DATA_DIR / "run_log.txt"
DATA_DIR.mkdir(exist_ok=True)

# URLs whose fetch failed completely after retries — used to avoid
# treating a network outage as "projects removed".
FETCH_ERRORS: list[str] = []


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def fetch_json(url: str, timeout: int = 20, params: dict | None = None, retries: int = 3) -> Any:
    """GET with retry + exponential backoff. Returns parsed JSON or None.
    On total failure the URL is recorded in FETCH_ERRORS."""
    last_err = ""
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                headers={"User-Agent": "DroperOG/2.0", "Accept": "application/json"})
            if r.status_code == 200:
                return r.json()
            last_err = f"HTTP {r.status_code}"
            if r.status_code < 500:
                break  # client error — retrying won't help
        except Exception as e:
            last_err = str(e)
        if attempt < retries - 1:
            time.sleep(0.5 * (2 ** attempt) + random.uniform(0, 0.3))
    FETCH_ERRORS.append(url)
    log(f"  Error: {url} ({last_err})")
    return None


def parse_dt(s: Any) -> datetime | None:
    """Tolerant date parser: ISO 8601, YYYY-MM-DD, or RFC 1123."""
    if not s:
        return None
    text = str(s).strip()
    try:
        d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            d = datetime.strptime(text, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# پروژه‌هایی که لیست‌شدنشان قدیمی‌تر از این باشد، بی‌صدا به state اضافه می‌شوند
# و در تلگرام به‌عنوان NEW اعلام نمی‌شوند — جلوی اسپم بک‌فیل منابع قدیمی (مثل DropJet) را می‌گیرد
FRESH_DAYS = 30


def is_old_listing(p: dict) -> bool:
    """True if the project's listing date is confidently older than FRESH_DAYS."""
    d = parse_dt(p.get("date"))
    if d is None:
        return False  # بدون تاریخ → اعلام کن (رفتار قبلی)
    return (datetime.now(timezone.utc) - d).days > FRESH_DAYS


# ─── SOURCES ───────────────────────────────────────────────

def fetch_alphadrops() -> list[dict]:
    """AlphaDrops API — rich project data with categories, chains, tasks."""
    data = fetch_json("https://alphadrops.net/api/airdrops")
    if not isinstance(data, list):
        return []
    cutoff = (time.time() - 365 * 24 * 3600)
    result = []
    for a in data:
        if a.get("premiumOnly") or a.get("status") == "ended":
            continue
        added = a.get("addedDate")
        if added:
            try:
                if "T" in str(added):
                    ts_dt = datetime.fromisoformat(str(added).replace("Z", "+00:00")).timestamp()
                else:
                    ts_dt = datetime.strptime(str(added), "%Y-%m-%d").timestamp()
                if ts_dt < cutoff:
                    continue
            except (ValueError, TypeError):
                pass
        chains = [c.lower().replace(" ", "") for c in (a.get("blockchains") or [])]
        cats = [c.lower() for c in (a.get("categories") or [])]
        tasks_raw = (a.get("tasks") or []) + (a.get("suggestedTasks") or [])
        tasks = [t.get("title") or t.get("description", "") for t in tasks_raw if t.get("title") or t.get("description")]
        trust = 50
        if a.get("featured"): trust += 15
        f_usd = funding_usd(a.get("fundingAmount"))
        if f_usd is not None:
            if f_usd >= 50_000_000: trust += 15
            elif f_usd >= 10_000_000: trust += 12
            elif f_usd >= 1_000_000: trust += 10
            else: trust += 5
        if a.get("isClaimable"): trust += 10
        if a.get("claimLink"): trust += 5
        if a.get("website"): trust += 5
        if a.get("socialTwitter"): trust += 3
        if a.get("socialDiscord"): trust += 2
        trust = min(trust, 95)

        result.append({
            "id": f"ad_{a.get('id', '')}",
            "name": a.get("name", "Unknown"),
            "desc": a.get("shortDescription", "") or "",
            "chains": chains if chains else [],
            "categories": cats,
            "tasks": tasks,
            "status_raw": a.get("status", ""),
            "funding": a.get("fundingAmount") or "",
            "url": f"https://alphadrops.net/airdrops/{a.get('slug', '')}",
            "date": added or "",
            "source": "AlphaDrops",
            "trust": trust,
        })
    return result


def fetch_cryptorank() -> list[dict]:
    """CryptoRank API — large dataset with activity types, costs, ratings."""
    base = "https://api.cryptorank.io/v0/drop-hunting/activities/table/public"
    all_items = []
    offset = 0
    limit = 100
    while True:
        data = fetch_json(base, params={"limit": limit, "offset": offset})
        if not data:
            break
        items = data.get("data") or []
        all_items.extend(items)
        count = data.get("count", 0)
        offset += len(items)
        if len(items) < limit or offset >= count:
            break
        time.sleep(0.3)

    result = []
    chk = {"ethereum":["eth","ethereum"],"arbitrum":["arbitrum","arb"],"optimism":["optimism","op"],
           "base":["base"],"polygon":["polygon","matic"],"zksync":["zksync","era"],
           "solana":["solana","sol"],"avalanche":["avalanche","avax"],"bsc":["bsc","bnb","binance"],
           "scroll":["scroll"],"linea":["linea"],"starknet":["starknet"],"sui":["sui"],
           "aptos":["aptos"],"ton":["ton"],"berachain":["berachain"],"monad":["monad"],"ink":["ink"],
           "pharos":["pharos"],"hyperliquid":["hyperliquid"],"robinhood":["robinhood"]}

    for item in all_items:
        coin = item.get("coin") or {}
        name = coin.get("name", "Unknown")
        types = item.get("activityTypes") or []
        types_text = " ".join(types).lower()
        # chain inference from name + types
        text_data = f"{name.lower()} {types_text}"
        chains = [c for c, kw in chk.items() if any(k in text_data for k in kw)]
        reward_type = item.get("rewardType", "")
        cost = item.get("cost") or 0
        time_min = item.get("time") or 0
        trust = 50
        rating = item.get("rating", 0)
        if rating > 100: trust += 15
        elif rating > 50: trust += 10
        elif rating > 10: trust += 5
        f_usd = funding_usd(coin.get("totalRaise"))
        if f_usd is not None:
            if f_usd >= 50_000_000: trust += 12
            elif f_usd >= 10_000_000: trust += 10
            elif f_usd >= 1_000_000: trust += 8
            else: trust += 4
        elif coin.get("funds"): trust += 5
        if item.get("status") == "CONFIRMED": trust += 10
        if item.get("linkToClaim"): trust += 5
        trust = min(trust, 95)

        result.append({
            "id": f"cr_{item.get('key', '')}",
            "name": name,
            "desc": f"Rating: {rating} | {reward_type} | ${cost}/{time_min}min",
            "chains": chains,
            "categories": [t.lower() for t in types],
            "tasks": types,
            "status_raw": item.get("status", ""),
            "funding": f"${coin.get('totalRaise', 0):,}" if coin.get("totalRaise") else "",
            "url": f"https://cryptorank.io/price/{coin.get('key', '')}",
            "date": item.get("createdAt") or "",
            "source": "CryptoRank",
            "trust": trust,
            "cost": cost,
            "time": time_min,
            "reward_type": reward_type,
        })
    return result


# ─── SOURCE: DROPJET ──────────────────────────────────────
# Public WordPress REST API of dropjet.co — human-curated airdrops with
# category, blockchain and investor taxonomy terms.

DROPJET_API = "https://dropjet.co/wp-json/wp/v2"


def _wp_get(path: str, params: dict | None = None) -> Any:
    return fetch_json(f"{DROPJET_API}/{path}", params=params)


def _wp_terms(taxonomy: str) -> dict[int, str]:
    """Fetch all terms of a DropJet taxonomy: {term_id: name}."""
    out: dict[int, str] = {}
    page = 1
    while True:
        data = _wp_get(taxonomy, params={"per_page": 100, "page": page})
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


def fetch_dropjet() -> list[dict]:
    """DropJet — curated airdrop list via its public WP REST API."""
    cats = _wp_terms("airdrop_categories")
    chains = _wp_terms("blockchains")
    investors = _wp_terms("investors")

    all_items = []
    page = 1
    while True:
        data = _wp_get("airdrops", params={"per_page": 100, "page": page})
        if not isinstance(data, list) or not data:
            break
        all_items.extend(data)
        if len(data) < 100:
            break
        page += 1

    result = []
    for a in all_items:
        name = (a.get("title") or {}).get("rendered") or "Unknown"
        cat_names = [cats.get(t) for t in (a.get("airdrop_categories") or [])]
        cat_names = [c for c in cat_names if c]
        chain_names = [chains.get(t) for t in (a.get("blockchains") or [])]
        chain_names = [c for c in chain_names if c]
        inv_names = [investors.get(t) for t in (a.get("investors") or [])]
        inv_names = [i for i in inv_names if i]

        desc = _strip_html((a.get("content") or {}).get("rendered", ""))
        cats_low = " ".join(cat_names).lower()

        trust = 50
        n_inv = len(inv_names)
        if n_inv >= 5: trust += 12
        elif n_inv >= 2: trust += 8
        elif n_inv == 1: trust += 5
        if any(k in cats_low for k in ("layer 1", "layer 2", "rollup", "infrastructure")):
            trust += 5
        if "social" in cats_low or "gamefi" in cats_low:
            trust += 3
        trust = min(trust, 95)

        result.append({
            "id": f"dj_{a.get('id', '')}",
            "name": name,
            "desc": desc[:300],
            "chains": [c.lower() for c in chain_names],
            "categories": [c.lower() for c in cat_names],
            "tasks": cat_names,
            "status_raw": "active",
            "funding": "",
            "url": a.get("link") or "",
            "date": a.get("date") or a.get("date_gmt") or "",
            "source": "DropJet",
            "trust": trust,
            "investors": inv_names,
        })
    return result


# ─── DATA QUALITY ─────────────────────────────────────────

def funding_usd(funding: Any) -> float | None:
    """Parse a funding string ('$5.2M', '$10 million', '$94,000,000') to USD."""
    if not funding:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(b|m|k|billion|million|thousand)?", str(funding).lower())
    if not m:
        return None
    amt = float(m.group(1).replace(",", ""))
    unit = m.group(2) or ""
    if unit.startswith("b"):
        return amt * 1e9
    if unit.startswith("m"):
        return amt * 1e6
    if unit.startswith("k"):
        return amt * 1e3
    return amt


def funding_rank(funding: Any) -> int:
    """Order funding display values: concrete > undisclosed > empty."""
    if not funding:
        return 0
    if str(funding).strip().lower() in ("undisclosed", "hidden"):
        return 1
    return 2


def normalize_name(name: str) -> str:
    """Normalize a project name for dedup: strip token symbols in parens,
    common suffixes and punctuation."""
    n = name.lower().strip()
    n = re.sub(r"\s*\([^)]*\)", "", n)  # "Polymarket (POLY)" -> "polymarket"
    for suf in (" protocol", " network", " finance", " foundation", " labs",
                " lab", " token", " coin", " project", " official"):
        if n.endswith(suf):
            n = n[: -len(suf)]
            break
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def project_key(p: dict) -> str:
    """Stable dedup key for a project record."""
    k = normalize_name(p.get("name") or "")
    if len(k) < 2 or len(k) > 60:
        return ""
    if k == "unknown":
        # keep anonymous projects separate instead of merging them
        return f"unknown_{p.get('id', '')}"
    return k


def merge_projects(projects: list[dict]) -> list[dict]:
    """Dedup by normalized name; merge records from multiple sources:
    union of chains/categories/tasks, max trust, best funding.
    Each merged record keeps `ids` = list of all source ids."""
    merged: dict[str, dict] = {}
    for p in projects:
        k = project_key(p)
        if not k:
            continue
        if k not in merged:
            m = dict(p)
            m["ids"] = [p["id"]]
            merged[k] = m
            continue
        m = merged[k]
        for field in ("chains", "categories", "tasks"):
            m[field] = list(dict.fromkeys((m.get(field) or []) + (p.get(field) or [])))
        m["trust"] = max(m["trust"], p["trust"])
        if funding_rank(p.get("funding")) > funding_rank(m.get("funding")):
            m["funding"] = p.get("funding", "")
        # قدیمی‌ترین تاریخ لیست‌شدن را نگه دار
        pd = parse_dt(p.get("date"))
        md = parse_dt(m.get("date"))
        if pd and (md is None or pd < md):
            m["date"] = p.get("date")
        if len(p["name"]) < len(m["name"]):
            m["name"] = p["name"]
        if p["id"] not in m["ids"]:
            m["ids"].append(p["id"])
    return list(merged.values())


# ─── CATEGORIZATION ────────────────────────────────────────

def categorize(project: dict) -> str:
    name = (project.get("name") or "").lower()
    cats = " ".join(project.get("categories") or []).lower()
    tasks = " ".join(project.get("tasks") or []).lower()
    desc = (project.get("desc") or "").lower()
    text = f"{name} {cats} {tasks} {desc}"
    cost = project.get("cost") or 0
    time_min = project.get("time") or 0
    reward = (project.get("reward_type") or "").lower()

    if any(kw in text for kw in ("testnet", "sepolia", "faucet", "devnet")):
        return "testnet"
    if "mint nft" in text:
        return "mainnet"
    if any(kw in text for kw in ("trading", "swap", "bridge", "stake", "perps", "perpetual",
                                 "deposit", "liquidity", "lend", "borrow", "mainnet")):
        return "mainnet"
    if cost > 0:
        return "mainnet"
    if time_min > 60:
        return "mainnet"
    if any(kw in text for kw in ("social", "quest", "galxe", "task", "bounty", "ambassador",
                                 "discord", "telegram", "twitter", "follow", "retweet", "quiz",
                                 "survey", "form", "referral", "check-in", "getting a role")):
        return "task_farmer"
    if cost == 0 and time_min <= 30:
        return "task_farmer"
    if "whitelist" in reward or "waitlist" in reward:
        return "task_farmer"
    return "task_farmer"


CAT_LABEL = {"testnet": "Testnet", "task_farmer": "Social Tasks", "mainnet": "Mainnet"}
CAT_EMOJI = {"testnet": "🟣", "task_farmer": "🟡", "mainnet": "🟢"}
CAT_COLOR = {"testnet": "\033[35m", "task_farmer": "\033[33m", "mainnet": "\033[32m"}


# ─── STATE ─────────────────────────────────────────────────

STATE_SCHEMA = 2


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {"projects": {}, "last_run": None}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), "utf-8")


def migrate_state(state: dict):
    """Migrate v1 state (keyed by source id) to v2 (keyed by project key)."""
    if state.get("schema") == STATE_SCHEMA:
        return
    migrated = {}
    for pid, rec in state.get("projects", {}).items():
        if isinstance(rec, dict) and rec.get("name"):
            k = project_key(rec)
            if k and k not in migrated:
                r = dict(rec)
                r["ids"] = [pid]
                migrated[k] = r
    state["projects"] = migrated
    state["schema"] = STATE_SCHEMA
    if migrated:
        log(f"  Migrated state to schema {STATE_SCHEMA}: {len(migrated)} project(s)")


def prune_state(state: dict, days: int = 60):
    """Drop projects not seen for `days` so state.json doesn't grow forever."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    stale = [k for k, p in state["projects"].items()
             if p.get("last_seen") and p["last_seen"] < cutoff]
    if stale:
        for k in stale:
            state["projects"].pop(k, None)
        log(f"  Pruned {len(stale)} project(s) not seen in {days}d")


# ─── REPORT ────────────────────────────────────────────────

def build_report(new_projects, updated, removed, categorized, state):
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "=" * 58
    lines.append(sep)
    lines.append(f"  DroperOG v2 — {now}")
    lines.append(sep)

    if new_projects:
        lines.append(f"\n  \033[32mNEW ({len(new_projects)}):\033[0m")
        for p in new_projects[:15]:
            cat = categorize(p)
            e = CAT_EMOJI.get(cat, "❓")
            l = CAT_LABEL.get(cat, cat)
            lines.append(f"  {e} {p['name']} [{l}]  Trust: {p['trust']}%")
            ch = ", ".join(p["chains"]) if p.get("chains") else "?"
            if ch: lines.append(f"     Chains: {ch}")
            if p.get("funding"): lines.append(f"     Funding: {p['funding']}")
            if p.get("cost"): lines.append(f"     Cost: ${p['cost']}")
            lines.append(f"     {p.get('url', '')}")
        if len(new_projects) > 15:
            lines.append(f"     ... and {len(new_projects) - 15} more")
    else:
        lines.append(f"\n  \033[32mNo new projects\033[0m")

    if updated:
        lines.append(f"\n  \033[36mUPDATED ({len(updated)}):\033[0m")
        for u in updated[:10]:
            lines.append(f"  {u['name']}: {u['change']}")

    if removed:
        lines.append(f"\n  \033[31mREMOVED ({len(removed)}):\033[0m {', '.join(removed[:10])}")

    lines.append(f"\n{'-' * 50}")
    lines.append("  CATEGORIZED SUMMARY (Trust >= 65)")
    lines.append(f"{'-' * 50}")

    for cat in ("testnet", "mainnet", "task_farmer"):
        items = categorized.get(cat, [])
        if not items:
            continue
        e = CAT_EMOJI.get(cat, "❓")
        l = CAT_LABEL.get(cat, cat)
        high = sorted([p for p in items if p["trust"] >= 65], key=lambda x: x["trust"], reverse=True)
        if not high:
            high = sorted(items, key=lambda x: x["trust"], reverse=True)[:5]
        lines.append(f"\n{e} {l} ({len(items)} — showing {len(high)} high-trust):")
        for p in high[:20]:
            ch = ", ".join(p["chains"]) if p.get("chains") else "?"
            fund = p.get("funding", "")
            t = ", ".join(p.get("tasks", [])[:2]) if p.get("tasks") else ""
            t_str = f" | {t}" if t else ""
            f_str = f" | {fund}" if fund else ""
            lines.append(f"  {p['name']} — {p['trust']}% | {ch}{f_str}{t_str}")

    total = sum(len(v) for v in categorized.values())
    tn = len(categorized.get("testnet", []))
    tf = len(categorized.get("task_farmer", []))
    mn = len(categorized.get("mainnet", []))
    lines.append(f"\n{'-' * 50}")
    lines.append(f"  Total: {total} | Testnet: {tn} | Social Tasks: {tf} | Mainnet: {mn}")
    if state.get("last_run"):
        try:
            last = datetime.fromisoformat(state["last_run"])
            diff = (datetime.now(timezone.utc).replace(tzinfo=None) - last.replace(tzinfo=None)).total_seconds() / 60
            lines.append(f"  Last run: {diff:.0f} min ago")
        except:
            pass
    lines.append(sep)
    return "\n".join(lines)


# ─── TELEGRAM ─────────────────────────────────────────────

BOT_TOKEN = (os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "")
CHAT_ID = (os.environ.get("CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID") or "")
# Also try loading from .env file
try:
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text("utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if k in ("BOT_TOKEN", "TELEGRAM_BOT_TOKEN") and not BOT_TOKEN: BOT_TOKEN = v
                if k in ("CHAT_ID", "TELEGRAM_CHAT_ID") and not CHAT_ID: CHAT_ID = v
except Exception:
    pass

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


def send_telegram(new_projects: list, categorized: dict):
    if not BOT_TOKEN or not CHAT_ID:
        return
    if not new_projects:
        return

    # belt-and-suspenders dedup — merge_projects already guarantees unique names
    seen = set()
    uniq = []
    for p in sorted(new_projects, key=lambda x: x["trust"], reverse=True):
        k = (p.get("name") or "").strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(p)

    lines = [f"🪂 <b>Airdrop Scan</b> — {datetime.now().strftime('%H:%M')}", ""]
    lines.append(f"🆕 <b>New ({len(uniq)})</b>")
    for p in uniq[:10]:
        cat = categorize(p)
        label = CAT_LABEL.get(cat, "?")
        emoji = CAT_EMOJI.get(cat, "❓")
        parts = []
        if p.get("tasks"):
            parts.append(", ".join(p["tasks"][:3]))
        fund = p.get("funding") or ""
        if fund and fund.strip().lower() not in ("undisclosed", "hidden"):
            parts.append(f"💰 {fund}")
        lines.append(f"<b>{esc(p['name'])}</b> {emoji} {label}")
        lines.append(f"🔗 {p['url']}")
        if parts:
            lines.append(f"<blockquote>{esc(', '.join(parts))}</blockquote>")
        lines.append("")
    lines.append("📊 <b>Summary</b>")
    for k, label in [("testnet", "Testnet"), ("mainnet", "Mainnet"), ("task_farmer", "Social Tasks")]:
        lines.append(f"  {CAT_EMOJI[k]} {label}: {len(categorized.get(k, []))}")
    lines.append(f"  ────────────────────")
    lines.append(f"  <b>Total: {sum(len(v) for v in categorized.values())}</b>")

    text = _truncate_html("\n".join(lines))
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=10,
        )
        ok = False
        if r.status_code == 200:
            try:
                ok = bool(r.json().get("ok"))
            except Exception:
                ok = False
        if ok:
            log("Telegram sent")
        else:
            log(f"Telegram error: HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"Telegram error: {e}")


# ─── MAIN ──────────────────────────────────────────────────

def main():
    log("DroperOG v2 starting...\n")

    state = load_state()
    migrate_state(state)
    prune_state(state)

    # Fetch all sources in parallel
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_ad = ex.submit(fetch_alphadrops)
        f_cr = ex.submit(fetch_cryptorank)
        f_dj = ex.submit(fetch_dropjet)
        log("Fetching AlphaDrops + CryptoRank + DropJet in parallel...")
        ad = f_ad.result()
        cr = f_cr.result()
        dj = f_dj.result()
    log(f"  AlphaDrops: {len(ad)} | CryptoRank: {len(cr)} | DropJet: {len(dj)}")

    if FETCH_ERRORS:
        log(f"  {len(FETCH_ERRORS)} fetch(es) failed — aborting scan.")
        log("  Keeping previous state to avoid false REMOVED reports.")
        return

    all_p = ad + cr + dj

    # Dedup by normalized name + merge records from all sources
    deduped = merge_projects(all_p)
    log(f"  After dedup/merge: {len(deduped)} unique projects")

    cur_names = {project_key(p) for p in deduped}

    # Detect new / updated / removed (state is keyed by project_key)
    new_p = []
    updated = []
    for p in deduped:
        k = project_key(p)
        if k not in state["projects"]:
            # بک‌فیل بی‌صدا: پروژه‌های با تاریخ لیست‌شدن قدیمی
            # (مثل کل لیست فعلی DropJet از ۲۰۲۵) به state اضافه می‌شوند
            # ولی به‌عنوان NEW اعلام نمی‌شوند
            if not is_old_listing(p):
                new_p.append(p)
        else:
            old = state["projects"].get(k, {})
            ot = old.get("trust", 0)
            if abs(p["trust"] - ot) >= 10:
                updated.append({"name": p["name"], "change": f"Trust: {ot}% -> {p['trust']}%"})

    removed_p = []
    for k in list(state["projects"].keys()):
        if k not in cur_names:
            nm = state["projects"][k].get("name", "")
            if nm and nm not in removed_p:
                removed_p.append(nm)

    # Update state
    for p in deduped:
        k = project_key(p)
        state["projects"][k] = {
            "name": p["name"], "trust": p["trust"], "category": categorize(p),
            "categories": p.get("categories", []), "chains": p.get("chains", []),
            "ids": p.get("ids") or [p["id"]],
            "last_seen": datetime.now().isoformat(),
        }
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    # Categorize
    categorized = {"testnet": [], "task_farmer": [], "mainnet": []}
    for p in deduped:
        cat = categorize(p)
        categorized.setdefault(cat, []).append(p)

    report = build_report(new_p, updated, removed_p, categorized, state)
    print("\n" + report)
    REPORT_FILE.write_text(report, "utf-8")
    log(f"Report -> {REPORT_FILE}")

    send_telegram(new_p, categorized)

    # Write summary JSON for GitHub Pages
    try:
        summary = {
            "summary": {k: len(v) for k, v in categorized.items()},
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        }
        pages_file = BASE / "docs" / "projects.json"
        pages_file.parent.mkdir(exist_ok=True)
        pages_file.write_text(json.dumps(summary, indent=2), "utf-8")
        log(f"Pages JSON -> {pages_file}")
    except Exception as e:
        log(f"Pages JSON error: {e}")


if __name__ == "__main__":
    main()
