"""droperog.py: scan-health, exit codes, state-after-delivery, watchdog (C1/C2/C4/H2)."""

import json
from datetime import datetime, timedelta, timezone

import droperog
from health_helpers import TelegramStub, project, run_droperog, stub_telegram


def test_completes_with_one_broken_source(monkeypatch):
    def broken():
        droperog.FETCH_ERRORS.append(
            "https://api.cryptorank.io/v0/drop-hunting/activities/table/public")
        return []

    code = run_droperog(monkeypatch, cryptorank=broken)

    assert code == droperog.EXIT_DEGRADED                     # CI باید قرمز شود
    assert droperog.REPORT_FILE.exists()                      # گزارش نوشته میشود
    assert droperog.STATE_FILE.exists()                       # state ذخیره میشود
    assert (droperog.BASE / "docs" / "projects.json").exists()
    status = json.loads(droperog.STATUS_FILE.read_text("utf-8"))
    assert status["status"] == "degraded"
    assert status["failed_sources"] == ["cryptorank"]


def test_aborts_only_when_everything_fails(monkeypatch):
    def dead(host):
        def f():
            droperog.FETCH_ERRORS.append(f"https://{host}/x")
            return []
        return f

    code = run_droperog(monkeypatch, alpha=dead("alphadrops.net"),
                        cryptorank=dead("api.cryptorank.io"), dropjet=dead("dropjet.co"))
    assert code == droperog.EXIT_ABORTED
    assert not droperog.REPORT_FILE.exists()
    assert not droperog.STATE_FILE.exists()
    status = json.loads(droperog.STATUS_FILE.read_text("utf-8"))
    assert status["status"] == "aborted"


def test_ok_run_writes_healthy_status(monkeypatch):
    code = run_droperog(monkeypatch)
    assert code == droperog.EXIT_OK
    status = json.loads(droperog.STATUS_FILE.read_text("utf-8"))
    assert status["status"] == "ok"
    assert status["last_success"]
    assert status["failed_sources"] == []


def test_state_not_saved_when_telegram_fails(monkeypatch):
    stub_telegram(monkeypatch, droperog, TelegramStub(fail=True))
    code = run_droperog(monkeypatch)
    assert code == droperog.EXIT_DEGRADED
    assert not droperog.STATE_FILE.exists()                   # خبر گم نمیشود
    assert droperog.REPORT_FILE.exists()                      # ولی گزارش محلی میماند


def test_state_saved_when_telegram_delivered(monkeypatch):
    stub = TelegramStub()
    stub_telegram(monkeypatch, droperog, stub)
    code = run_droperog(monkeypatch)
    assert code == droperog.EXIT_OK
    assert droperog.STATE_FILE.exists()
    assert stub.calls                                         # پیام واقعاً رفت


def test_watchdog_warns_when_last_success_is_stale(monkeypatch):
    stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    droperog.STATUS_FILE.write_text(json.dumps({"status": "ok", "last_success": stale}),
                                    "utf-8")
    stub = TelegramStub()
    stub_telegram(monkeypatch, droperog, stub)
    run_droperog(monkeypatch)
    texts = "\n".join(c["text"] for c in stub.calls)
    assert "⚠" in texts and "ساعت پیش" in texts


def test_alert_cooldown_suppresses_repeat():
    prev = {"last_alert": datetime.now(timezone.utc).isoformat()}
    assert droperog.alert_due(prev, "⚠ x") is False
    prev = {"last_alert": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()}
    assert droperog.alert_due(prev, "⚠ x") is True
    assert droperog.alert_due({}, None) is False


def test_no_false_removed_when_a_source_is_down(monkeypatch):
    droperog.STATE_FILE.write_text(json.dumps({
        "schema": droperog.STATE_SCHEMA,
        "projects": {
            "cr only": {"name": "CR Only", "trust": 70, "ids": ["cr_x"]},
            "ad only": {"name": "AD Only", "trust": 70, "ids": ["ad_x"]},
        },
        "last_run": None,
    }), "utf-8")

    def broken_cr():
        droperog.FETCH_ERRORS.append("https://api.cryptorank.io/x")
        return []

    code = run_droperog(monkeypatch, alpha=[project()], cryptorank=broken_cr, dropjet=[])
    assert code == droperog.EXIT_DEGRADED
    report = droperog._strip_ansi(droperog.REPORT_FILE.read_text("utf-8"))
    assert "CR Only" not in report          # منبعش خراب است → حذف گزارش نمیشود
    assert "AD Only" in report              # منبعش سالم ولی نیست → حذف واقعی
