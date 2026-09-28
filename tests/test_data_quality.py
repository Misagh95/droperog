"""Tests for the DeFiLlama source (CryptoRank replacement).

api.cryptorank.io went behind Cloudflare (HTTP 403 on every endpoint), so
DeFiLlama is what keeps the scan from returning near-zero projects.
"""

import pytest

import droperog
import hunter


PROTOCOLS = [
    {"id": "1", "slug": "aave", "name": "Aave", "category": "Lending",
     "chains": ["Ethereum", "Arbitrum", "Solana"], "tvl": 1.5e10, "mcap": 1.8e10,
     "audits": "2", "twitter": "aave", "symbol": "AAVE",
     "description": "A lending protocol", "url": "https://aave.com",
     "listedAt": 1669000000},
    {"id": "2", "slug": "okx", "name": "OKX", "category": "CEX",
     "chains": ["Ethereum"], "tvl": 3e10, "mcap": 2e9, "audits": "0",
     "twitter": "okx", "symbol": "OKB", "description": "Exchange",
     "url": "https://okx.com", "listedAt": 1669000000},
    {"id": "3", "slug": "dust", "name": "Dusty", "category": "Dexs",
     "chains": ["Ethereum"], "tvl": 12.0, "mcap": None, "audits": None,
     "twitter": None, "symbol": None, "description": "", "url": "",
     "listedAt": 1669000000},
]


@pytest.fixture
def stub_api(monkeypatch):
    monkeypatch.setattr(droperog, "fetch_json", lambda *a, **k: PROTOCOLS)
    monkeypatch.setattr(droperog, "FETCH_ERRORS", [])
    monkeypatch.setattr(hunter, "fetch_json", lambda *a, **k: PROTOCOLS)
    monkeypatch.setattr(hunter, "FETCH_ERRORS", [])


def test_defillama_drops_noise_keeps_real_protocols(stub_api):
    out = droperog.fetch_defillama()
    names = {p["name"] for p in out}
    assert "Aave" in names
    assert "OKX" not in names        # CEX ارزش پیگیری ایردراپ ندارد
    assert "Dusty" not in names      # TVL ناچیز = پروژه مرده


def test_defillama_normalizes_chains_and_builds_url(stub_api):
    aave = next(p for p in droperog.fetch_defillama() if p["name"] == "Aave")
    assert aave["chains"] == ["ethereum", "arbitrum", "solana"]
    assert aave["url"] == "https://aave.com"
    assert aave["id"].startswith("dl_")
    assert aave["source"] == "DeFiLlama"
    assert aave["trust"] >= 65
    assert aave["date"]                     # listedAt به تاریخ ISO تبدیل شده


def test_defillama_falls_back_to_defillama_url(monkeypatch):
    rows = [dict(PROTOCOLS[0], url="")]
    monkeypatch.setattr(droperog, "fetch_json", lambda *a, **k: rows)
    aave = droperog.fetch_defillama()[0]
    assert aave["url"] == "https://defillama.com/protocol/aave"


def test_defillama_survives_bad_payload(monkeypatch):
    monkeypatch.setattr(droperog, "fetch_json", lambda *a, **k: {"not": "a list"})
    assert droperog.fetch_defillama() == []


def test_defillama_source_is_tracked_for_removal_guard(stub_api):
    assert droperog._record_sources({"ids": ["dl_aave"]}) == {"defillama"}


def test_defillama_hunter_only_reports_recent_listings(monkeypatch):
    # لیست ۲۰۲۲ → خارج از بازه «تازه» و نباید گزارش شود
    monkeypatch.setattr(hunter, "fetch_json", lambda *a, **k: [PROTOCOLS[0]])
    assert hunter.fetch_defillama_fresh(days=30) == []

    # یک روز پیش → باید دیده شود
    import time
    fresh = dict(PROTOCOLS[0], listedAt=int(time.time()) - 86400)
    monkeypatch.setattr(hunter, "fetch_json", lambda *a, **k: [fresh])
    out = hunter.fetch_defillama_fresh(days=30)
    assert len(out) == 1
    assert out[0]["source"] == "defillama"
    assert out[0]["id"].startswith("dl_")
    assert out[0]["category"] == "mainnet"      # Lending → مین‌نت
    assert out[0]["date"] is not None


import json
from datetime import datetime, timedelta, timezone

import droperog
import hunter
from health_helpers import item


def test_prune_state_handles_legacy_local_naive_timestamp():
    fresh_local = datetime.now().isoformat()                # legacy: naive local time
    old_local = (datetime.now() - timedelta(days=90)).isoformat()
    state = {"projects": {"a": {"last_seen": fresh_local},
                          "b": {"last_seen": old_local}}}
    droperog.prune_state(state)
    assert "a" in state["projects"]
    assert "b" not in state["projects"]


def test_categorize_negations_are_not_mainnet():
    quiz = {"name": "Deposit-free quiz", "categories": ["quiz"], "tasks": ["answer quiz"],
            "desc": "no deposit needed, no trading required", "cost": 0, "time": 5,
            "reward_type": ""}
    assert droperog.categorize(quiz) == "task_farmer"

    real = {"name": "Trader hub", "categories": ["trading"], "tasks": ["Trade perps"],
            "desc": "provide liquidity", "cost": 10, "time": 60, "reward_type": ""}
    assert droperog.categorize(real) == "mainnet"

    testnet = {"name": "Dev playground", "categories": [], "tasks": ["Get faucet tokens"],
               "desc": "testnet", "cost": 0, "time": 5, "reward_type": ""}
    assert droperog.categorize(testnet) == "testnet"


def test_normalize_name_merges_safe_but_not_different_projects():
    key = lambda name: droperog.project_key({"name": name, "id": "x"})
    assert key("Polymarket (POLY)") == key("Polymarket")    # نماد توکن حذف میشود
    assert key("Sui (SUI)") == key("SUI") == key("sui")
    assert key("Sui Network") != key("Sui Labs")            # پروژههای متفاوت جدا میمانند
    assert key("Sui Network") != key("SUI")                 # «network» دیگر حذف نمیشود


def test_report_file_has_no_ansi_codes_and_honest_header():
    categorized = {"testnet": [],
                   "task_farmer": [{"name": "P1", "trust": 40, "chains": [], "tasks": [],
                                    "funding": "", "url": ""}],
                   "mainnet": []}
    rep = droperog.build_report([], [], [], categorized, {})
    plain = droperog._strip_ansi(rep)
    assert "\x1b" not in plain
    assert "none >= 65" in plain                            # دیگر «high-trust» دروغ نیست


def test_report_shows_broken_source_warning():
    rep = droperog.build_report([], [], [], {}, {}, failed_sources=["cryptorank"])
    assert "cryptorank" in droperog._strip_ansi(rep)


def test_hunter_duplicates_are_marked_seen_and_never_reannounced():
    seen = {}
    items = [item("ad_1", "MoonPay"), item("cr_1", "MOONPAY", source="cryptorank")]
    first = hunter.select_new_items(items, seen)
    assert len(first) == 1                                  # یکی نمایش داده میشود
    assert set(seen) == {"ad_1", "cr_1"}                    # ولی هر دو ثبت شدند
    again = hunter.select_new_items([item("ad_1", "MoonPay"),
                                     item("cr_1", "MOONPAY", source="cryptorank")], seen)
    assert again == []                                      # باگ «دوباره تازه شدن» نیست


def test_hunter_prune_seen_drops_old_entries():
    now = datetime.now(timezone.utc)
    state = {"seen": {"old": {"first_seen": (now - timedelta(days=200)).isoformat()},
                      "new": {"first_seen": now.isoformat()}}}
    assert hunter.prune_seen(state) == 1
    assert set(state["seen"]) == {"new"}


def test_hunter_load_state_keeps_seen_across_version_change():
    seen = {"a": {"first_seen": "2026-01-01T00:00:00+00:00"}}
    hunter.HUNTER_STATE.write_text(json.dumps({"v": -1, "seen": seen}), "utf-8")
    state = hunter.load_state()
    assert state["seen"] == seen                            # حافظه با تغییر نسخه نمیپرد


def test_hunter_report_triage_footer_is_honest():
    rep = hunter.build_report([], {"testnet": 0})
    assert "تغییری نکرد" in rep
    assert "چشم‌انداز این اسکن:" not in rep                 # بخش خالی چاپ نمیشود
    rep2 = hunter.build_report([item("x", "X")], {"task": 1}, triage_added=True)
    assert "به‌روزرسانی شد" in rep2


def test_migrate_preserves_source_ids():
    state = {"projects": {"stork": {"name": "Stork", "trust": 70, "ids": ["ad_1", "cr_x"]}}}
    droperog.migrate_state(state)
    rec = state["projects"]["stork"]
    assert set(rec["ids"]) == {"ad_1", "cr_x"}
    assert state["schema"] == droperog.STATE_SCHEMA


def test_record_sources_maps_id_prefixes():
    assert droperog._record_sources({"ids": ["ad_1", "cr_x"]}) == {"alphadrops", "cryptorank"}
    assert droperog._record_sources({"ids": ["cr_x"]}) == {"cryptorank"}
    assert droperog._record_sources({"ids": ["normalized-name"]}) == set()
    assert droperog._record_sources({}) == set()
