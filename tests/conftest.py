"""Shared test isolation for the DroperOG suite.

Run with:  python -m pytest tests/ -q

هر تست مسیرهای data/* (log / report / state / status) را به یک پوشهی موقت
منتقل میکند تا اجرای تست هیچوقت فایلهای واقعی پروژه را تغییر ندهد.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def isolate_data_paths(tmp_path, monkeypatch):
    """Redirect every on-disk path of all three modules into a temp dir."""
    import droperog
    import grabber
    import hunter

    def redirect(mod, attrs):
        for attr in attrs:
            if not hasattr(mod, attr):
                continue
            suffix = Path(getattr(mod, attr)).suffix or ".json"
            monkeypatch.setattr(mod, attr, tmp_path / f"{mod.__name__}_{attr}{suffix}")

    redirect(droperog, ("STATE_FILE", "REPORT_FILE", "LOG_FILE", "STATUS_FILE"))
    monkeypatch.setattr(droperog, "BASE", tmp_path)  # docs/projects.json هم جدا میشود

    redirect(hunter, ("HUNTER_STATE", "HUNTER_REPORT", "HUNTER_REPORT_MD", "TRIAGE_CSV",
                      "HUNTER_LOG", "HUNTER_STATUS"))
    monkeypatch.setattr(hunter, "DOCS_DIR", tmp_path)

    redirect(grabber, ("STATE_FILE", "REPORT_FILE", "SELFTEST_REPORT", "DEMO_STATE"))

    # FETCH_ERRORS یک لیست گلوبال است — بین تست‌ها صفر شود
    monkeypatch.setattr(droperog, "FETCH_ERRORS", [])
    monkeypatch.setattr(hunter, "FETCH_ERRORS", [])
    yield
