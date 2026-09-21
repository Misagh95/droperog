"""M1–M6: timestamps, categorize negations, safer name-merging, honest report."""

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
