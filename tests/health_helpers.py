"""Shared stubs/runners for the scan-health test modules (not a test file)."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import droperog  # noqa: E402
import hunter  # noqa: E402


def project(name="Good Project", trust=70, **kw):
    p = {"id": f"ad_{name}", "name": name, "desc": "", "chains": [], "categories": [],
         "tasks": [], "url": "https://x.io/p", "date": "", "funding": "",
         "trust": trust, "cost": 0, "time": 5, "reward_type": ""}
    p.update(kw)
    return p


def item(id_, name, **kw):
    it = {"id": id_, "name": name, "category": "task", "source": "alphadrops",
          "url": "https://x.io/p", "desc": "", "date": datetime.now(timezone.utc),
          "cost": 0}
    it.update(kw)
    return it


class Resp:
    def __init__(self, ok=True, code=200):
        self.status_code = code
        self.text = "" if ok else '{"ok":false,"description":"can\'t parse entities"}'

    def json(self):
        return {"ok": self.status_code == 200}


class TelegramStub:
    """Captures posts; fail=True makes every call look rejected."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __call__(self, url, json=None, timeout=None):
        self.calls.append(json)
        return Resp(ok=not self.fail, code=200 if not self.fail else 400)


def stub_telegram(monkeypatch, mod, stub):
    monkeypatch.setattr(mod, "BOT_TOKEN", "t")
    monkeypatch.setattr(mod, "CHAT_ID", "c")
    monkeypatch.setattr(mod.requests, "post", stub)


def dead_fetcher(mod_errors, host):
    def f():
        mod_errors.append(f"https://{host}/x")
        return []
    return f


def dead_hunter_fetcher(host):
    def f(days=7):
        hunter.FETCH_ERRORS.append(f"https://{host}/x")
        return []
    return f


def _as_fetcher(value, default):
    """callable → همان را بهعنوان fetcher استفاده کن؛ در غیر این صورت لیست برگردان."""
    if callable(value):
        return value
    if value is not None:
        return lambda: value
    return lambda: default


def _as_hunter_fetcher(value):
    if callable(value):
        return value
    if value is not None:
        return lambda days=7: value
    return lambda days=7: []


def run_droperog(monkeypatch, alpha=None, cryptorank=None, dropjet=None):
    monkeypatch.setattr(droperog, "fetch_alphadrops", _as_fetcher(alpha, [project()]))
    monkeypatch.setattr(droperog, "fetch_cryptorank", _as_fetcher(cryptorank, []))
    monkeypatch.setattr(droperog, "fetch_dropjet", _as_fetcher(dropjet, []))
    monkeypatch.setattr(sys, "argv", ["droperog.py"])
    return droperog.main()


def run_hunter(monkeypatch, alpha=None, cryptorank=None, dropjet=None, news=None,
               argv=()):
    monkeypatch.setattr(hunter, "fetch_alpha_drops_fresh", _as_hunter_fetcher(alpha))
    monkeypatch.setattr(hunter, "fetch_crypto_rank_fresh", _as_hunter_fetcher(cryptorank))
    monkeypatch.setattr(hunter, "fetch_dropjet_fresh", _as_hunter_fetcher(dropjet))
    monkeypatch.setattr(hunter, "fetch_airdrop_news", _as_hunter_fetcher(news))
    monkeypatch.setattr(sys, "argv", ["hunter.py", *argv])
    return hunter.main()
