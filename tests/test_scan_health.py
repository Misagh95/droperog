"""droperog.py: scan-health, exit codes, state-after-delivery, watchdog (C1/C2/C4/H2)."""

import json
from datetime import datetime, timedelta, timezone

import droperog
from health_helpers import TelegramStub, project, run_droperog, stub_telegram


def test_completes_with_one_broken_source(monkeypatch):
    def broken():
        droperog.FETCH_ERRORS.append("https://api.llama.fi/protocols")
        return []

    code = run_droperog(monkeypatch, defillama=broken)

    assert code == droperog.EXIT_DEGRADED                     # CI باید قرمز شود
    assert droperog.REPORT_FILE.exists()                      # گزارش نوشته میشود
    assert droperog.STATE_FILE.exists()                       # state ذخیره میشود
    assert (droperog.BASE / "docs" / "projects.json").exists()
    status = json.loads(droperog.STATUS_FILE.read_text("utf-8"))
    assert status["status"] == "degraded"
    assert status["failed_sources"] == ["defillama"]


def test_aborts_only_when_everything_fails(monkeypatch):
    def dead(host):
        def f():
            droperog.FETCH_ERRORS.append(f"https://{host}/x")
            return []
        return f

    code = run_droperog(monkeypatch, alpha=dead("alphadrops.net"),
                        dropjet=dead("dropjet.co"),
                        defillama=dead("api.llama.fi"))
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
    """منبعِ خطادار نباید باعث «REMOVED» کاذب شود."""
    droperog.STATE_FILE.write_text(json.dumps({
        "schema": droperog.STATE_SCHEMA,
        "projects": {
            "dl only": {"name": "DL Only", "trust": 70, "ids": ["dl_x"]},
            "ad only": {"name": "AD Only", "trust": 70, "ids": ["ad_x"]},
        },
        "last_run": None,
    }), "utf-8")

    def broken_dl():
        droperog.FETCH_ERRORS.append("https://api.llama.fi/protocols")
        return []

    code = run_droperog(monkeypatch, alpha=[project()], defillama=broken_dl)
    assert code == droperog.EXIT_DEGRADED
    report = droperog._strip_ansi(droperog.REPORT_FILE.read_text("utf-8"))
    assert "DL Only" not in report          # منبعش خراب است → حذف گزارش نمیشود
    assert "AD Only" in report              # منبعش سالم ولی نیست → حذف واقعی


def test_retired_source_does_not_cause_mass_false_removed(monkeypatch):
    """CryptoRank از چرخه خارج شده؛ پروژه‌های قدیمیِ او نباید «REMOVED» شوند.

    اگر این گارد نبود، اولین اجرای بعد از بازنشستگی منبع یک اعلان «REMOVED»
    برای صدها پروژه می‌فرستاد که اصلاً حذف نشده‌اند — فقط دیگر fetch نمی‌شوند.
    """
    droperog.STATE_FILE.write_text(json.dumps({
        "schema": droperog.STATE_SCHEMA,
        "projects": {
            "gone but was cryptorank": {"name": "Legacy CR", "trust": 70, "ids": ["cr_x"]},
            "gone and was alphadrops": {"name": "Legacy AD", "trust": 70, "ids": ["ad_x"]},
        },
        "last_run": None,
    }), "utf-8")

    run_droperog(monkeypatch, alpha=[project()])
    report = droperog._strip_ansi(droperog.REPORT_FILE.read_text("utf-8"))
    assert "Legacy CR" not in report       # منبع بازنشسته → حذف قطعی نیست
    assert "Legacy AD" in report           # منبعِ فعال ولی غایب → حذف واقعی


def test_cryptorank_is_not_in_the_active_scan(monkeypatch):
    """بازنشستگی واقعاً یعنی دیگر صدا زده نمی‌شود (و پس‌زمینه ۴۰۳ نمی‌دهد)."""
    calls = []
    monkeypatch.setattr(droperog, "fetch_cryptorank", lambda: calls.append(1) or [])
    run_droperog(monkeypatch)
    assert calls == []
    assert droperog.RETIRED_SOURCES == {"cryptorank"}
    assert "cryptorank" not in droperog.SOURCE_HOSTS


def test_removed_is_not_reported_forever(monkeypatch):
    """پروژه‌ی حذف‌شده نباید هر اجرا دوباره «REMOVED» اعلام شود.

    state قبلاً فقط رکورد اضافه می‌کرد و هرگز پاک نمی‌کرد، پس یک پروژه
    می‌توانست ماه‌ها هر ۴ ساعت «REMOVED» تکرار شود.
    """
    droperog.STATE_FILE.write_text(json.dumps({
        "schema": droperog.STATE_SCHEMA,
        "projects": {"dead project": {"name": "Dead Project", "trust": 70, "ids": ["ad_x"]}},
        "last_run": None,
    }), "utf-8")

    run_droperog(monkeypatch, alpha=[project()])
    first = droperog._strip_ansi(droperog.REPORT_FILE.read_text("utf-8"))
    assert "Dead Project" in first                    # بار اول: خبر واقعی

    saved = json.loads(droperog.STATE_FILE.read_text("utf-8"))
    assert "dead project" not in saved["projects"]     # از state پاک شد

    run_droperog(monkeypatch, alpha=[project()])
    second = droperog._strip_ansi(droperog.REPORT_FILE.read_text("utf-8"))
    assert "Dead Project" not in second                # بار دوم: ساکت
    assert "REMOVED" not in second


def test_state_keeps_records_from_failed_and_retired_sources(monkeypatch):
    """پروژه‌های منبع خطادار/بازنشسته در state می‌مانند تا دوباره «NEW» نشوند."""
    droperog.STATE_FILE.write_text(json.dumps({
        "schema": droperog.STATE_SCHEMA,
        "projects": {
            "cr legacy": {"name": "CR Legacy", "trust": 70, "ids": ["cr_x"]},
            "dl hidden": {"name": "DL Hidden", "trust": 70, "ids": ["dl_x"]},
            "ad stale": {"name": "AD Stale", "trust": 70, "ids": ["ad_x"]},
        },
        "last_run": None,
    }), "utf-8")

    def broken_dl():
        droperog.FETCH_ERRORS.append("https://api.llama.fi/protocols")
        return []

    run_droperog(monkeypatch, alpha=[project()], defillama=broken_dl)
    saved = json.loads(droperog.STATE_FILE.read_text("utf-8"))["projects"]
    assert "cr legacy" in saved          # منبع بازنشسته → حفظ
    assert "dl hidden" in saved          # منبع خطادار → حفظ
    assert "ad stale" not in saved       # منبع سالم ولی غایب → حذف واقعی
