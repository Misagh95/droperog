"""Tests for the Telegram message formatting in droperog.py and hunter.py.

Run with:  python -m pytest tests/ -q
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Make the repo root importable so the scripts can be loaded as modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import droperog  # noqa: E402
import hunter  # noqa: E402

MODULES = [droperog, hunter]
MODULE_IDS = ["droperog", "hunter"]


# ─── esc() ─────────────────────────────────────────────────

@pytest.mark.parametrize("mod", MODULES, ids=MODULE_IDS)
def test_esc_escapes_html_specials(mod):
    assert mod.esc("A & B") == "A &amp; B"
    assert mod.esc("<script>") == "&lt;script&gt;"
    assert mod.esc("a > b") == "a &gt; b"


@pytest.mark.parametrize("mod", MODULES, ids=MODULE_IDS)
def test_esc_leaves_plain_text_untouched(mod):
    assert mod.esc("Polymarket (POLY)") == "Polymarket (POLY)"


# ─── _truncate_html() ──────────────────────────────────────

@pytest.mark.parametrize("mod", MODULES, ids=MODULE_IDS)
def test_truncate_keeps_short_text(mod):
    text = "<b>Hello</b>\n🔗 https://x.io\n"
    assert mod._truncate_html(text) == text


@pytest.mark.parametrize("mod", MODULES, ids=MODULE_IDS)
def test_truncate_keeps_tags_balanced(mod):
    long = "\n".join(
        f"<b>Project {i}</b> 🟢 Mainnet\n🔗 https://x.io/{i}\n<blockquote>desc {i}</blockquote>\n"
        for i in range(300)
    )
    out = mod._truncate_html(long)
    assert len(out) <= 3800
    assert out.count("<b>") == out.count("</b>")
    assert out.count("<blockquote>") == out.count("</blockquote>")
    assert out.endswith("…")


# ─── droperog.py: send_telegram message building ──────────

def _droperog_sample_projects():
    return [
        {"id": "ad_1", "name": "PIN AI", "trust": 95, "tasks": ["Social", "Fill The Form"],
         "url": "https://x.io/pin", "desc": "", "chains": [], "categories": ["social"],
         "cost": 0, "time": 5, "reward_type": ""},
        {"id": "cr_1", "name": "Fomo & Friends", "trust": 85, "tasks": ["Trade <Perps>"],
         "url": "https://x.io/fomo", "desc": "", "chains": ["solana"], "categories": ["trading"],
         "cost": 0, "time": 5, "reward_type": ""},
    ]


def test_droperog_send_telegram_message_format(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"ok": True}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(droperog.requests, "post", fake_post)
    monkeypatch.setattr(droperog, "BOT_TOKEN", "test")
    monkeypatch.setattr(droperog, "CHAT_ID", "test")

    categorized = {"testnet": [None] * 3, "task_farmer": [None] * 279, "mainnet": [None] * 75}
    droperog.send_telegram(_droperog_sample_projects(), categorized)

    payload = captured["json"]
    assert payload["parse_mode"] == "HTML"
    assert payload["disable_web_page_preview"] is True

    text = payload["text"]
    # bold name + category next to it
    assert "<b>PIN AI</b> 🟡 Social Tasks" in text
    assert "<b>Fomo &amp; Friends</b> 🟢 Mainnet" in text
    # link below the name
    assert "🔗 https://x.io/pin" in text
    assert "🔗 https://x.io/fomo" in text
    # quoted description (escaped)
    assert "<blockquote>Social, Fill The Form</blockquote>" in text
    assert "<blockquote>Trade &lt;Perps&gt;</blockquote>" in text
    # summary
    assert "🟣 Testnet: 3" in text
    assert "<b>Total: 357</b>" in text


def test_droperog_send_telegram_skips_when_no_new_projects(monkeypatch):
    monkeypatch.setattr(droperog, "BOT_TOKEN", "test")
    monkeypatch.setattr(droperog, "CHAT_ID", "test")
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return None

    monkeypatch.setattr(droperog.requests, "post", fake_post)
    droperog.send_telegram([], {})
    assert calls == []


# ─── hunter.py: build_telegram_message ─────────────────────

def _hunter_sample_items():
    now = datetime.now(timezone.utc)
    return [
        {"id": "t1", "name": "PIN AI", "category": "task", "source": "alphadrops",
         "url": "https://alphadrops.net/airdrops/pin-ai", "desc": "Social, Fill The Form",
         "date": now},
        {"id": "t2", "name": "Fermah", "category": "testnet", "source": "alphadrops",
         "url": "https://alphadrops.net/airdrops/fermah", "desc": "Predictions & Points",
         "date": now},
    ]


def test_hunter_build_telegram_message_format():
    fresh = {"testnet": 3, "task": 5, "mainnet": 9}
    msg = hunter.build_telegram_message(_hunter_sample_items(), fresh)

    assert "<b>DroperOG Hunter</b>" in msg
    assert "<b>2 مورد تازه:</b>" in msg
    # bold name + category + age
    assert "<b>PIN AI</b> 🟡 تسک/کمپین" in msg
    assert "<b>Fermah</b> 🟣 تست‌نت" in msg
    # link below the name
    assert "🔗 https://alphadrops.net/airdrops/pin-ai" in msg
    assert "🔗 https://alphadrops.net/airdrops/fermah" in msg
    # quoted description (escaped)
    assert "<blockquote>Social, Fill The Form</blockquote>" in msg
    assert "<blockquote>Predictions &amp; Points</blockquote>" in msg
    # category section headers + summary
    assert "🟣 تست‌نت (1):" in msg
    assert "🟡 تسک/کمپین (1):" in msg
    assert "🟢 مین‌نت: 9" in msg


def test_hunter_build_telegram_message_no_items():
    msg = hunter.build_telegram_message([], {"testnet": 0})
    assert "هیچ کمپین تازه‌ای" in msg
    assert "<b>DroperOG Hunter</b>" in msg
