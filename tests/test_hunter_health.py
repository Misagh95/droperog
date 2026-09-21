"""hunter.py: scan-health, exit codes, state-after-delivery (C1/C2/H2)."""

import json

import hunter
from health_helpers import TelegramStub, item, run_hunter, stub_telegram


def test_continues_when_only_dropjet_fails(monkeypatch):
    def broken(days=7):
        hunter.FETCH_ERRORS.append("https://dropjet.co/wp-json/wp/v2/airdrops")
        return []

    code = run_hunter(monkeypatch, alpha=[item("a", "A")], dropjet=broken)
    assert code == hunter.EXIT_DEGRADED
    assert hunter.HUNTER_REPORT.exists()
    assert hunter.HUNTER_STATE.exists()
    status = json.loads(hunter.HUNTER_STATUS.read_text("utf-8"))
    assert status["status"] == "degraded"
    assert status["failed_sources"] == ["dropjet"]


def test_aborts_when_everything_fails(monkeypatch):
    def dead(host):
        def f(days=7):
            hunter.FETCH_ERRORS.append(f"https://{host}/x")
            return []
        return f

    monkeypatch.setattr(hunter, "fetch_alpha_drops_fresh", dead("alphadrops.net"))
    monkeypatch.setattr(hunter, "fetch_crypto_rank_fresh", dead("api.cryptorank.io"))
    monkeypatch.setattr(hunter, "fetch_dropjet_fresh", dead("dropjet.co"))
    monkeypatch.setattr(hunter, "fetch_airdrop_news", dead("news.google.com"))
    code = run_hunter(monkeypatch)

    assert code == hunter.EXIT_ABORTED
    assert not hunter.HUNTER_REPORT.exists()
    assert not hunter.HUNTER_STATE.exists()
    status = json.loads(hunter.HUNTER_STATUS.read_text("utf-8"))
    assert status["status"] == "aborted"


def test_state_not_saved_when_telegram_fails(monkeypatch):
    stub_telegram(monkeypatch, hunter, TelegramStub(fail=True))
    code = run_hunter(monkeypatch, alpha=[item("a", "A")], argv=["--telegram"])
    assert code == hunter.EXIT_DEGRADED
    assert not hunter.HUNTER_STATE.exists()
    assert hunter.HUNTER_REPORT.exists()


def test_ok_run_writes_healthy_status(monkeypatch):
    code = run_hunter(monkeypatch, alpha=[item("a", "A")])
    assert code == hunter.EXIT_OK
    status = json.loads(hunter.HUNTER_STATUS.read_text("utf-8"))
    assert status["status"] == "ok"
    assert status["last_success"]


def test_seen_grows_but_items_never_repeat(monkeypatch):
    stub_telegram(monkeypatch, hunter, TelegramStub())
    code = run_hunter(monkeypatch, alpha=[item("a", "A")], argv=["--telegram"])
    assert code == hunter.EXIT_OK
    state = json.loads(hunter.HUNTER_STATE.read_text("utf-8"))
    assert "a" in state["seen"]
    # دوباره همان آیتم → دیگر «تازه» نیست و پیامی هم نمیفرستد (بدون --always)
    stub = TelegramStub()
    stub_telegram(monkeypatch, hunter, stub)
    run_hunter(monkeypatch, alpha=[item("a", "A")], argv=["--telegram"])
    assert stub.calls == []
