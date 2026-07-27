#!/usr/bin/env python3
"""
DroperOG v2 — Multi-source airdrop hunter with auto-categorization & monitoring
"""

import json, os, sys, time
from datetime import datetime, timezone
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


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def fetch_json(url: str, timeout: int = 20, params: dict | None = None) -> Any:
    try:
        r = requests.get(url, params=params, timeout=timeout,
            headers={"User-Agent": "DroperOG/2.0", "Accept": "application/json"})
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        log(f"  Error: {e}")
        return None


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
        if a.get("fundingAmount") and a["fundingAmount"] not in ("Undisclosed", "Hidden", ""): trust += 15
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
        if coin.get("totalRaise"): trust += 10
        if coin.get("funds"): trust += 10
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
            "source": "CryptoRank",
            "trust": trust,
            "cost": cost,
            "time": time_min,
            "reward_type": reward_type,
        })
    return result


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


CAT_LABEL = {"testnet": "Testnet", "task_farmer": "Task Farmer", "mainnet": "Mainnet"}
CAT_EMOJI = {"testnet": "🟣", "task_farmer": "🟡", "mainnet": "🟢"}
CAT_COLOR = {"testnet": "\033[35m", "task_farmer": "\033[33m", "mainnet": "\033[32m"}


# ─── STATE ─────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {"projects": {}, "last_run": None, "seen_ids": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), "utf-8")


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
    lines.append(f"  Total: {total} | Testnet: {tn} | Task Farmer: {tf} | Mainnet: {mn}")
    if state.get("last_run"):
        try:
            last = datetime.fromisoformat(state["last_run"])
            diff = (datetime.now(timezone.utc).replace(tzinfo=None) - last.replace(tzinfo=None)).total_seconds() / 60
            lines.append(f"  Last run: {diff:.0f} min ago")
        except:
            pass
    lines.append(sep)
    return "\n".join(lines)


# ─── MAIN ──────────────────────────────────────────────────

def main():
    log("DroperOG v2 starting...\n")

    state = load_state()
    seen_ids = set(state.get("seen_ids", []))

    log("AlphaDrops...")
    ad = fetch_alphadrops()
    log(f"  {len(ad)} projects")

    log("CryptoRank...")
    cr = fetch_cryptorank()
    log(f"  {len(cr)} projects")

    all_p = ad + cr

    # Dedup by name
    seen_names = set()
    deduped = []
    for p in all_p:
        k = p["name"].lower().strip()
        if k in seen_names or len(k) < 2 or len(k) > 60:
            continue
        seen_names.add(k)
        deduped.append(p)

    # Detect new / updated / removed
    new_p = []
    updated = []
    cur_ids = set()
    for p in deduped:
        pid = p["id"]
        cur_ids.add(pid)
        if pid not in seen_ids:
            new_p.append(p)
        else:
            old = state["projects"].get(pid, {})
            ot = old.get("trust", 0)
            if abs(p["trust"] - ot) >= 10:
                updated.append({"name": p["name"], "change": f"Trust: {ot}% -> {p['trust']}%"})

    removed_p = []
    for pid in seen_ids:
        if pid not in cur_ids:
            removed_p.append(state["projects"].get(pid, {}).get("name", pid))

    # Update state
    for p in deduped:
        state["projects"][p["id"]] = {
            "name": p["name"], "trust": p["trust"], "category": categorize(p),
            "categories": p.get("categories", []), "chains": p.get("chains", []),
            "last_seen": datetime.now().isoformat(),
        }
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["seen_ids"] = list(cur_ids)
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


if __name__ == "__main__":
    main()
