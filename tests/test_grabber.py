"""Tests for grabber.py — the pure helpers and the duck-typed media describing.

No telethon and no network needed: describe_media() works on plain fakes whose
class names match telethon's, which is exactly why it is duck-typed.

Run with:  python -m pytest tests/ -q
"""

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Make the repo root importable so the scripts can be loaded as modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import grabber  # noqa: E402


# ─── fakes mirroring telethon's class names ────────────────

class PhotoSize:
    def __init__(self, size):
        self.size = size


class PhotoSizeProgressive:
    def __init__(self, sizes):
        self.sizes = sizes


class Photo:
    def __init__(self, id=7, sizes=()):
        self.id = id
        self.sizes = list(sizes)


class MessageMediaPhoto:
    def __init__(self, photo):
        self.photo = photo


class MessageMediaWebPage:
    def __init__(self, webpage=None):
        self.webpage = webpage


class DocumentAttributeFilename:
    def __init__(self, file_name):
        self.file_name = file_name


class DocumentAttributeVideo:
    def __init__(self, round_message=False):
        self.round_message = round_message


class DocumentAttributeAudio:
    def __init__(self, voice=False):
        self.voice = voice


class DocumentAttributeSticker:
    pass


class DocumentAttributeAnimated:
    pass


class Document:
    def __init__(self, id=1, size=1000, mime_type="", attributes=()):
        self.id = id
        self.size = size
        self.mime_type = mime_type
        self.attributes = list(attributes)


class MessageMediaDocument:
    def __init__(self, document):
        self.document = document


# ─── fake telethon client for the end-to-end grab_chat loop ─

class FakeMessage:
    def __init__(self, id, media, date=None):
        self.id = id
        self.media = media
        self.date = date or datetime(2026, 2, 1, tzinfo=timezone.utc)


class FakeClient:
    """Yields the given messages and writes placeholder bytes to `file`."""

    def __init__(self, messages):
        self._messages = messages
        self.calls = []

    def iter_messages(self, entity, **kwargs):
        self.calls.append(kwargs)

        async def gen():
            for m in self._messages:
                yield m

        return gen()

    async def download_media(self, msg, file=None, progress_callback=None, thumb=None):
        Path(file).parent.mkdir(parents=True, exist_ok=True)
        Path(file).write_bytes(b"payload")
        if progress_callback:
            progress_callback(7, 7)
        return file


def _stats():
    return {k: 0 for k in ("found", "downloaded", "already", "planned", "errors",
                           "bytes", "downloaded_bytes")}


# ─── parse_size / format_bytes ─────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("10MB", 10 * 1024 ** 2),
    ("1.5 gb", int(1.5 * 1024 ** 3)),
    ("500k", 500 * 1024),
    ("20480", 20480),
    ("0", 0),
])
def test_parse_size_accepts_units(text, expected):
    assert grabber.parse_size(text) == expected


@pytest.mark.parametrize("bad", ["", "abc", "10 furlongs", "-", None])
def test_parse_size_rejects_junk(bad):
    assert grabber.parse_size(bad) is None


def test_format_bytes():
    assert grabber.format_bytes(0) == "0 B"
    assert grabber.format_bytes(512) == "512 B"
    assert grabber.format_bytes(1536) == "1.5 KB"
    assert grabber.format_bytes(1024 ** 2) == "1.0 MB"
    assert grabber.format_bytes(5 * 1024 ** 3) == "5.0 GB"
    assert grabber.format_bytes(None) == "?"


# ─── sanitize_filename ─────────────────────────────────────

def test_sanitize_strips_path_separators_and_illegal_chars():
    assert grabber.sanitize_filename('a/b\\c:d"e|f?g*h') == "a_b_c_d_e_f_g_h"


def test_sanitize_neutralizes_traversal_and_empty():
    assert grabber.sanitize_filename("..") == "file"
    assert grabber.sanitize_filename("../etc/passwd", fallback="x") == "_etc_passwd"
    assert grabber.sanitize_filename("   ", fallback="x") == "x"


def test_sanitize_escapes_windows_reserved_names():
    assert grabber.sanitize_filename("CON.txt") == "_CON.txt"
    assert grabber.sanitize_filename("lpt1") == "_lpt1"


def test_sanitize_truncates_but_keeps_extension():
    name = "a" * 200 + ".mp4"
    out = grabber.sanitize_filename(name, max_len=110)
    assert len(out) <= 110
    assert out.endswith(".mp4")
    assert out.startswith("a" * 10)


# ─── parse_date ────────────────────────────────────────────

def test_parse_date_returns_aware_utc():
    d = grabber.parse_date("2026-01-31")
    assert d == datetime(2026, 1, 31, tzinfo=timezone.utc)
    assert d.tzinfo is not None


def test_parse_date_rejects_junk():
    assert grabber.parse_date("31/01/2026 x") is None
    assert grabber.parse_date("") is None
    assert grabber.parse_date(None) is None


# ─── format_progress ───────────────────────────────────────

def test_format_progress_with_total_has_bar_and_percent():
    out = grabber.format_progress(50, 100)
    assert "50.0%" in out
    assert out.count("#") + out.count("-") == 24


def test_format_progress_without_total_shows_bytes_only():
    out = grabber.format_progress(2048, None)
    assert "2.0 KB" in out
    assert "#" not in out


# ─── describe_media (duck-typed) ───────────────────────────

def test_describe_photo_picks_largest_size():
    photo = Photo(id=99, sizes=[PhotoSize(1200), PhotoSizeProgressive([300, 4000, 800]),
                                PhotoSize(2048)])
    entry = grabber.describe_media(MessageMediaPhoto(photo))
    assert entry["kind"] == "photo"
    assert entry["size"] == 4000
    assert entry["key"] == "p99"
    assert entry["ext"] == "jpg"


def test_describe_ignores_non_file_media():
    assert grabber.describe_media(None) is None
    assert grabber.describe_media(MessageMediaWebPage()) is None
    assert grabber.describe_media(MessageMediaPhoto(None)) is None
    # empty photo (deleted on server) has no downloadable size
    assert grabber.describe_media(MessageMediaPhoto(Photo(sizes=[])))["size"] is None


def test_describe_video_and_round_video():
    vid = MessageMediaDocument(Document(
        id=5, size=10 * 1024 ** 2, mime_type="video/mp4",
        attributes=[DocumentAttributeVideo(), DocumentAttributeFilename("clip.mp4")]))
    entry = grabber.describe_media(vid)
    assert entry["kind"] == "video"
    assert entry["name"] == "clip.mp4"
    assert entry["ext"] == "mp4"
    assert entry["key"] == "d5"

    note = MessageMediaDocument(Document(
        attributes=[DocumentAttributeVideo(round_message=True)]))
    assert grabber.describe_media(note)["kind"] == "video_note"


def test_describe_audio_voice_and_sticker():
    music = MessageMediaDocument(Document(
        mime_type="audio/mpeg", attributes=[DocumentAttributeAudio(voice=False),
                                            DocumentAttributeFilename("song.mp3")]))
    assert grabber.describe_media(music)["kind"] == "audio"

    voice = MessageMediaDocument(Document(mime_type="audio/ogg",
                                          attributes=[DocumentAttributeAudio(voice=True)]))
    assert grabber.describe_media(voice)["kind"] == "voice"

    sticker = MessageMediaDocument(Document(mime_type="image/webp",
                                            attributes=[DocumentAttributeSticker()]))
    assert grabber.describe_media(sticker)["kind"] == "sticker"


def test_describe_gif_by_attribute_or_mime():
    by_attr = MessageMediaDocument(Document(
        mime_type="video/mp4", attributes=[DocumentAttributeAnimated()]))
    assert grabber.describe_media(by_attr)["kind"] == "gif"

    by_mime = MessageMediaDocument(Document(mime_type="image/gif"))
    assert grabber.describe_media(by_mime)["kind"] == "gif"
    assert grabber.describe_media(by_mime)["ext"] == "gif"


def test_describe_plain_document_keeps_mime_extension():
    entry = grabber.describe_media(MessageMediaDocument(Document(
        mime_type="application/pdf", attributes=[DocumentAttributeFilename("paper")])))
    assert entry["kind"] == "document"
    assert entry["ext"] == "pdf"


def test_guess_ext_falls_back_to_bin():
    assert grabber.guess_ext(None, None, "document") == "bin"
    assert grabber.guess_ext("no-extension-here", "application/x-weird", "document") == "bin"


# ─── entry_filename ────────────────────────────────────────

def test_entry_filename_includes_date_and_message_id():
    when = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
    entry = {"kind": "video", "name": "clip.mp4", "ext": "mp4"}
    assert grabber.entry_filename(entry, 42, when) == "20260131_42_clip.mp4"


def test_entry_filename_adds_missing_extension_and_handles_anonymous():
    entry = {"kind": "document", "name": "report", "ext": "pdf"}
    assert grabber.entry_filename(entry, 7, None) == "7_report.pdf"

    anon = {"kind": "voice", "name": "", "ext": "ogg"}
    assert grabber.entry_filename(anon, 8, None) == "8_voice.ogg"


def test_entry_filename_sanitizes_original_name():
    entry = {"kind": "document", "name": '../../evil.exe', "ext": "exe"}
    out = grabber.entry_filename(entry, 1, None)
    assert "/" not in out and "\\" not in out and ".." not in out


# ─── wanted ────────────────────────────────────────────────

def test_wanted_filters_by_kind_and_size():
    entry = {"kind": "video", "size": 10 * 1024 ** 2}
    assert grabber.wanted(entry, {"video"}, 0, 0)
    assert not grabber.wanted(entry, {"photo"}, 0, 0)
    assert not grabber.wanted(entry, {"video"}, 20 * 1024 ** 2, 0)
    assert not grabber.wanted(entry, {"video"}, 0, 1024)
    assert grabber.wanted(entry, {"video"}, 1024, 20 * 1024 ** 2)


def test_wanted_keeps_unknown_size_unless_size_filter_is_set():
    entry = {"kind": "photo", "size": None}
    assert grabber.wanted(entry, {"photo"}, 0, 0)


# ─── chat_title / chat_dir_name ────────────────────────────

class _Entity:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_short_path_is_relative_inside_the_repo_and_absolute_outside(tmp_path):
    inside = Path(grabber.BASE) / "data" / "x.json"
    assert grabber.short_path(inside) == "data/x.json"
    # anything outside the repo must still render instead of blowing up
    assert grabber.short_path(tmp_path / "state.json") == str(tmp_path / "state.json")


def test_chat_title_prefers_title_then_full_name_then_username():
    assert grabber.chat_title(_Entity(id=1, title="My Group")) == "My Group"
    assert grabber.chat_title(_Entity(id=2, first_name="Ali", last_name="B")) == "Ali B"
    assert grabber.chat_title(_Entity(id=3, username="solo")) == "solo"
    assert grabber.chat_title(None) == "unknown"


def test_chat_dir_name_keeps_id_suffix_to_avoid_collisions():
    out = grabber.chat_dir_name("My Group: 2026", "-1001234")
    assert out == "My Group_ 2026_-1001234"
    assert grabber.chat_dir_name("", "5") == "chat_5"


# ─── parse_args ────────────────────────────────────────────

def test_parse_args_defaults():
    args = grabber.parse_args(["--chat", "me"])
    assert args["error"] is None
    assert args["chats"] == ["me"]
    assert args["types"] == list(grabber.DEFAULT_KINDS)
    assert "sticker" not in args["types"]
    assert args["sleep"] == 1.0
    assert args["thumbs"] is False and args["dry_run"] is False


def test_parse_args_types_all_and_subset():
    assert grabber.parse_args(["--types", "all"])["types"] == list(grabber.ALL_KINDS)
    assert grabber.parse_args(["--types", "video,photo"])["types"] == ["video", "photo"]
    bad = grabber.parse_args(["--types", "video,bogus"])
    assert "bogus" in bad["error"]


def test_parse_args_repeatable_chat_and_sizes():
    args = grabber.parse_args(["--chat", "@a", "--chat", "12345",
                               "--min-size", "5MB", "--max-size", "2GB"])
    assert args["chats"] == ["@a", "12345"]
    assert args["min_size"] == 5 * 1024 ** 2
    assert args["max_size"] == 2 * 1024 ** 3


def test_parse_args_until_is_inclusive_of_the_whole_day():
    args = grabber.parse_args(["--since", "2026-01-01", "--until", "2026-01-31"])
    assert args["since"] == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert args["until"] == datetime(2026, 1, 31, tzinfo=timezone.utc) + timedelta(days=1)


def test_parse_args_flags_and_errors():
    args = grabber.parse_args(["--all", "--full", "--dry-run", "--thumbs",
                               "--limit", "50", "--sleep", "0", "--out", "D:/tg"])
    assert (args["all"], args["full"], args["dry_run"], args["thumbs"]) == (True,) * 4
    assert args["limit"] == 50 and args["sleep"] == 0.0
    assert args["out"] == "D:/tg"

    assert "unknown option" in grabber.parse_args(["--nope"])["error"]
    assert grabber.parse_args(["--min-size", "banana"])["error"]
    assert grabber.parse_args(["--since", "31/01/2026"])["error"]
    assert grabber.parse_args(["--sleep", "fast"])["error"]
    assert grabber.parse_args(["--chat"])["error"]  # missing value


# ─── env / state / report ──────────────────────────────────

def test_load_env_reads_dotenv_and_aliases(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "# comment\nTG_API_ID=1234567\nTG_API_HASH=deadbeef\nTG_PHONE=+989120000000\n",
        "utf-8")
    monkeypatch.setattr(grabber, "BASE", tmp_path)
    for name in ("TG_API_ID", "TELEGRAM_API_ID", "API_ID", "TG_API_HASH",
                 "TELEGRAM_API_HASH", "API_HASH", "TG_PHONE", "PHONE"):
        monkeypatch.delenv(name, raising=False)

    env = grabber.load_env()
    assert env == {"api_id": "1234567", "api_hash": "deadbeef", "phone": "+989120000000"}


def test_check_env_reports_missing_and_non_numeric_api_id():
    assert grabber.check_env({"api_id": "12", "api_hash": "x"}) is None
    assert grabber.check_env({}) is not None
    assert "عدد" in grabber.check_env({"api_id": "nope", "api_hash": "x"})


def test_state_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(grabber, "STATE_FILE", tmp_path / "state.json")
    assert grabber.load_state() == {"chats": {}, "files": {}}

    state = grabber.load_state()
    state["chats"]["-100"] = {"title": "G", "last_id": 99}
    state["files"]["p1"] = "downloads/G/x.jpg"
    grabber.save_state(state)

    again = grabber.load_state()
    assert again["chats"]["-100"]["last_id"] == 99
    assert again["files"]["p1"] == "downloads/G/x.jpg"


def test_load_state_survives_corrupt_file(monkeypatch, tmp_path):
    bad = tmp_path / "state.json"
    bad.write_text("{not json", "utf-8")
    monkeypatch.setattr(grabber, "STATE_FILE", bad)
    assert grabber.load_state() == {"chats": {}, "files": {}}


def test_build_report_shows_download_and_dry_run_totals():
    stats = {"found": 3, "downloaded": 2, "already": 1, "planned": 0,
             "errors": 0, "bytes": 3 * 1024 ** 2, "downloaded_bytes": 2 * 1024 ** 2}
    report = grabber.build_report({"dry_run": False, "out": "downloads"}, stats)
    assert "DroperOG Grabber" in report
    assert "downloaded     : 2" in report
    assert "3.0 MB" in report

    dry = grabber.build_report({"dry_run": True, "out": "d"}, {**stats, "planned": 3})
    assert "would download : 3" in dry


# ─── end-to-end grab_chat loop (fake client, real filesystem) ───

def _three_messages():
    return [
        # 1: a photo (thumbnail-only messages must still count as downloadable)
        FakeMessage(1, MessageMediaPhoto(Photo(id=10, sizes=[PhotoSize(2048)]))),
        # 2: plain text — no media, must be ignored
        FakeMessage(2, None),
        # 3: a PDF document
        FakeMessage(3, MessageMediaDocument(Document(
            id=20, size=7, mime_type="application/pdf",
            attributes=[DocumentAttributeFilename("paper.pdf")]))),
    ]


def _run(args, state, messages, tmp_path):
    import asyncio
    client = FakeClient(messages)
    stats = _stats()
    asyncio.run(grabber.grab_chat(client, _Entity(id=1, title="My Group"), "me",
                                  args, state, {"photo", "document"}, stats))
    return client, stats


def test_grab_chat_downloads_only_matching_media(monkeypatch, tmp_path):
    monkeypatch.setattr(grabber, "STATE_FILE", tmp_path / "state.json")
    args = grabber.parse_args(["--chat", "me", "--out", str(tmp_path / "out"),
                               "--sleep", "0"])
    state = grabber.load_state()
    client, stats = _run(args, state, _three_messages(), tmp_path)

    assert stats["found"] == 2          # text message left out
    assert stats["downloaded"] == 2
    assert stats["errors"] == 0
    assert stats["downloaded_bytes"] == 14

    names = sorted(p.name for p in (tmp_path / "out").rglob("*") if p.is_file())
    assert len(names) == 2
    assert any(n.endswith("_1_photo.jpg") for n in names)
    assert any(n.endswith("_3_paper.pdf") for n in names)
    assert all("My Group_1" in str(p.parent) for p in (tmp_path / "out").rglob("*") if p.is_file())

    # state remembers the newest id + every file, for incremental re-runs
    assert state["chats"]["1"]["last_id"] == 3
    assert set(state["files"]) == {"p10", "d20"}
    # incremental mode asks telethon only for messages newer than last_id
    assert client.calls[0]["min_id"] == 0
    assert client.calls[0]["reverse"] is True


def test_grab_chat_second_run_skips_everything(monkeypatch, tmp_path):
    monkeypatch.setattr(grabber, "STATE_FILE", tmp_path / "state.json")
    args = grabber.parse_args(["--chat", "me", "--out", str(tmp_path / "out"),
                               "--sleep", "0"])
    state = grabber.load_state()
    _run(args, state, _three_messages(), tmp_path)

    client, stats = _run(args, state, _three_messages(), tmp_path)
    assert stats["downloaded"] == 0
    assert stats["already"] == 2
    assert client.calls[0]["min_id"] == 3      # incremental from the saved watermark


def test_grab_chat_dry_run_writes_nothing_and_keeps_watermark(monkeypatch, tmp_path):
    monkeypatch.setattr(grabber, "STATE_FILE", tmp_path / "state.json")
    args = grabber.parse_args(["--chat", "me", "--out", str(tmp_path / "out"),
                               "--dry-run", "--sleep", "0"])
    state = grabber.load_state()
    _, stats = _run(args, state, _three_messages(), tmp_path)

    assert stats["planned"] == 2
    assert stats["downloaded"] == 0
    assert not (tmp_path / "out").exists()
    # a dry run must not advance the watermark, or the files would be missed later
    assert "1" not in state["chats"]
    assert state["files"] == {}


def test_selftest_verdict_when_credentials_are_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(grabber, "DEMO_DELAY", 0)
    monkeypatch.setattr(grabber, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(grabber, "SELFTEST_REPORT", tmp_path / "selftest.txt")
    monkeypatch.setattr(grabber, "load_env", lambda: {})

    args = grabber.parse_args(["--selftest", "--out", str(tmp_path / "out")])
    assert args["selftest"] is True
    assert grabber.selftest(args) == 1          # usable, but not ready for the real thing

    out = capsys.readouterr().out
    assert "[ OK ] download pipeline" in out
    assert "[FAIL] credentials" in out
    assert "[ -- ] session" in out
    assert (tmp_path / "selftest.txt").exists()


def test_selftest_sees_credentials_and_a_healthy_pipeline(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(grabber, "DEMO_DELAY", 0)
    monkeypatch.setattr(grabber, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(grabber, "SELFTEST_REPORT", tmp_path / "selftest.txt")
    monkeypatch.setattr(grabber, "load_env",
                        lambda: {"api_id": "1", "api_hash": "h", "phone": "+1"})

    args = grabber.parse_args(["--selftest", "--out", str(tmp_path / "out")])
    code = grabber.selftest(args)
    out = capsys.readouterr().out

    assert "[FAIL] credentials" not in out
    assert "[ OK ] credentials" in out          # the credentials really travel through
    assert "[ OK ] download pipeline" in out
    # green overall only when telethon is actually importable — CI may not install it
    assert code == (0 if importlib.util.find_spec("telethon") else 1)


def test_demo_runs_offline_and_leaves_real_state_alone(monkeypatch, tmp_path):
    import asyncio
    monkeypatch.setattr(grabber, "DEMO_DELAY", 0)          # no fake progress pauses
    monkeypatch.setattr(grabber, "DEMO_STATE", tmp_path / "demo_state.json")
    monkeypatch.setattr(grabber, "STATE_FILE", tmp_path / "real_state.json")

    assert grabber.parse_args(["--demo"])["demo"] is True
    args = grabber.parse_args(["--demo", "--out", str(tmp_path / "dl")])
    assert asyncio.run(grabber.run_demo(args)) == 0

    files = sorted(p.name for p in (tmp_path / "dl" / "_demo").rglob("*") if p.is_file())
    assert len(files) == 4          # text-only message and nothing else slipped in
    for suffix in ("_1_photo.jpg", "_3_clip.mp4", "_4_report.pdf", "_5_voice.ogg"):
        assert any(n.endswith(suffix) for n in files), suffix

    # the demo keeps its own scratch state so the real archive is never polluted
    assert (tmp_path / "demo_state.json").exists()
    assert not (tmp_path / "real_state.json").exists()


def test_grab_chat_respects_size_and_date_filters(monkeypatch, tmp_path):
    monkeypatch.setattr(grabber, "STATE_FILE", tmp_path / "state.json")
    args = grabber.parse_args(["--chat", "me", "--out", str(tmp_path / "out"),
                               "--min-size", "4KB", "--since", "2026-02-01",
                               "--sleep", "0"])
    state = grabber.load_state()
    messages = [
        FakeMessage(1, MessageMediaPhoto(Photo(id=10, sizes=[PhotoSize(2048)]))),
        FakeMessage(2, MessageMediaDocument(Document(
            id=20, size=5 * 1024 ** 2, mime_type="application/pdf",
            attributes=[DocumentAttributeFilename("big.pdf")])),
            date=datetime(2025, 12, 31, tzinfo=timezone.utc)),  # too old
        FakeMessage(3, MessageMediaDocument(Document(
            id=21, size=5 * 1024 ** 2, mime_type="application/pdf",
            attributes=[DocumentAttributeFilename("fresh.pdf")]))),
    ]
    _, stats = _run(args, state, messages, tmp_path)

    assert stats["found"] == 1   # 2 KB photo below --min-size, old pdf before --since
    downloaded = [p.name for p in (tmp_path / "out").rglob("*") if p.is_file()]
    assert len(downloaded) == 1 and downloaded[0].endswith("_3_fresh.pdf")
