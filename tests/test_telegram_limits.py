"""H3/M11: telegram UTF-16 limit, tag-balanced splitting, plain-text fallback, escaped URLs."""

import droperog
import hunter
from health_helpers import Resp, project, item, stub_telegram


def test_split_messages_stay_under_utf16_limit_and_balanced():
    blocks = []
    for i in range(120):
        blocks.append(f"<b>پروژه شماره {i}</b> 🟢 مین‌نت\n🔗 https://x.io/{i}\n"
                      f"<blockquote>{'توضیح ' * 10} {i}</blockquote>")
    msgs = droperog.split_messages(blocks)
    assert len(msgs) > 1                                    # واقعاً چند پیام شد
    for m in msgs:
        assert droperog.utf16_len(m) <= droperog.MESSAGE_BUDGET
        assert m.count("<b>") == m.count("</b>")
        assert m.count("<blockquote>") == m.count("</blockquote>")
    joined = "\n".join(msgs)
    for i in (0, 47, 119):
        assert f"پروژه شماره {i}" in joined                 # هیچ بلوکی گم نشد


def test_truncate_html_never_cuts_inside_a_tag():
    text = "<b>" + "a" * 5000 + "</b>\n🔗 https://x.io"
    for mod in (droperog, hunter):
        out = mod._truncate_html(text)
        assert mod.utf16_len(out) <= mod.MESSAGE_BUDGET
        assert out.count("<b>") == out.count("</b>")
        assert out.endswith("…")


def test_plain_text_fallback_when_html_rejected(monkeypatch):
    class Flaky:
        def __init__(self):
            self.calls = []

        def __call__(self, url, json=None, timeout=None):
            self.calls.append(json)
            # HTML رد میشود، متن ساده قبول میشود
            return Resp(ok=json.get("parse_mode") != "HTML",
                        code=400 if json.get("parse_mode") == "HTML" else 200)

    flaky = Flaky()
    stub_telegram(monkeypatch, droperog, flaky)
    ok = droperog.send_telegram([project()], {"testnet": [], "task_farmer": [None],
                                              "mainnet": []})
    assert ok is True
    assert len(flaky.calls) == 2                            # HTML → plain
    assert "parse_mode" not in flaky.calls[1]
    assert "<b>" not in flaky.calls[1]["text"]              # متن ساده است


def test_telegram_urls_are_html_escaped():
    blocks = droperog.build_telegram_blocks([project(url="https://x.io/a?b=1&c=2")], {})
    assert "https://x.io/a?b=1&amp;c=2" in "\n".join(blocks)

    msg = hunter.build_telegram_message([item("x", "X", url="https://x.io/?a=1&b=2")],
                                        {"task": 1})
    assert "a=1&amp;b=2" in msg


def test_hunter_messages_split_under_limit():
    # موارد را بین دستهها پخش میکنیم (هر دسته سقف نمایش دارد)
    cats = {"testnet": 20, "task": 20, "mainnet": 20, "network": 20,
            "newtracked": 20, "points": 20}
    items = []
    i = 0
    for cat, count in cats.items():
        for _ in range(count):
            items.append(item(f"id{i}", f"پروژه تستی {'ب' * 30} {i}", category=cat,
                              desc="توضیح نمونه " * 20))
            i += 1
    fresh = {c: n for c, n in cats.items()}
    msgs = hunter.build_telegram_messages(items, fresh)
    assert len(msgs) > 1
    for m in msgs:
        assert hunter.utf16_len(m) <= hunter.MESSAGE_BUDGET
        assert m.count("<b>") == m.count("</b>")
