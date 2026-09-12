#!/usr/bin/env python3
"""
DroperOG Grabber — bulk download of media/files from your own Telegram chats.

Unlike droperog.py / hunter.py (Bot API — بات فقط پیام می‌فرستد و سقف ۲۰MB دارد)
this module talks MTProto through YOUR user account, so it can read and download
from the private chats, groups and channels that your account is a member of.

Quality: Telegram keeps one file per message. We always fetch that original —
the largest size for photos, the untouched document for videos and files — never
the compressed preview. Thumbnails are opt-in via --thumbs.

Usage:
    python grabber.py --list
    python grabber.py --login
    python grabber.py --chat me
    python grabber.py --chat @my_channel --types video,document --min-size 10MB
    python grabber.py --all --since 2026-01-01
    python grabber.py --chat @my_channel --dry-run

Needs TG_API_ID / TG_API_HASH (https://my.telegram.org) in .env or the env.
Install once:  pip install telethon
"""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
STATE_FILE = DATA_DIR / "grabber_state.json"
REPORT_FILE = DATA_DIR / "grabber_report.txt"
SESSION_FILE = DATA_DIR / "grabber"
DEFAULT_OUT = BASE / "downloads"
DATA_DIR.mkdir(exist_ok=True)

try:  # Windows consoles default to cp1252 and choke on the progress glyphs
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ─── LOGGING ───────────────────────────────────────────────

QUIET = False  # در self-test خاموش می‌شود تا فقط نتیجه‌ی نهایی دیده شود


def log(msg: str):
    if QUIET:
        return
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ─── SMALL PURE HELPERS (unit-tested, no telethon needed) ───

_SIZE_UNITS = {
    "": 1, "b": 1,
    "k": 1024, "kb": 1024, "kib": 1024,
    "m": 1024 ** 2, "mb": 1024 ** 2, "mib": 1024 ** 2,
    "g": 1024 ** 3, "gb": 1024 ** 3, "gib": 1024 ** 3,
    "t": 1024 ** 4, "tb": 1024 ** 4, "tib": 1024 ** 4,
}


def parse_size(text: Any) -> int | None:
    """'10MB' / '1.5 gb' / '500k' / 20480 -> bytes. None if unparsable."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    m = re.fullmatch(r"\s*([\d.]+)\s*([a-zA-Z]*)\s*", str(text))
    if not m:
        return None
    unit = m.group(2).lower()
    if unit not in _SIZE_UNITS:
        return None
    try:
        return int(float(m.group(1)) * _SIZE_UNITS[unit])
    except ValueError:
        return None


def format_bytes(n: float | None) -> str:
    """1536 -> '1.5 KB' (binary units, one decimal)."""
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}


def sanitize_filename(name: Any, fallback: str = "file", max_len: int = 110) -> str:
    """Make a string safe as a single path component (no traversal, no reserved names)."""
    name = _ILLEGAL.sub("_", str(name or ""))
    name = re.sub(r"\.{2,}", ".", name)  # '../..' must not survive as '..'
    name = re.sub(r"\s+", " ", name).strip().strip(". ")
    if name.upper().split(".")[0] in _RESERVED:
        name = "_" + name
    if not name:
        return fallback
    if len(name) > max_len:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 10:
            name = stem[: max_len - len(ext) - 1] + "." + ext
        else:
            name = name[:max_len]
    return name or fallback


def parse_date(text: Any) -> datetime | None:
    """'2026-01-31' or full ISO -> aware UTC datetime."""
    if not text:
        return None
    try:
        d = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            d = datetime.strptime(str(text).strip(), "%Y-%m-%d")
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def format_progress(done: float, total: float | None, width: int = 24) -> str:
    """ASCII progress bar used during a single file download."""
    if not total:
        return f"  {format_bytes(done)}"
    pct = max(0.0, min(1.0, done / total))
    filled = int(width * pct)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {pct * 100:5.1f}%  {format_bytes(done)}/{format_bytes(total)}"


# ─── MEDIA DESCRIBING (duck-typed: works with telethon objects AND fakes) ───

ALL_KINDS = ("photo", "video", "video_note", "document", "audio", "voice", "gif", "sticker")
# پیش‌فرض: همه‌چیز جز استیکر (استیکرها معمولاً انبوه و بی‌ارزش‌اند) — با --types all
DEFAULT_KINDS = ("photo", "video", "video_note", "document", "audio", "voice", "gif")

_MIME_EXT = {
    "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif",
    "video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm",
    "video/x-matroska": "mkv", "audio/mpeg": "mp3", "audio/ogg": "ogg",
    "audio/mp4": "m4a", "audio/flac": "flac", "audio/wav": "wav",
    "application/pdf": "pdf", "application/zip": "zip", "application/x-7z-compressed": "7z",
    "application/vnd.rar": "rar", "application/x-tar": "tar", "text/plain": "txt",
    "application/x-msdownload": "exe", "application/vnd.android.package-archive": "apk",
}


def photo_size(photo: Any) -> int | None:
    """Largest available size of a Photo object (newest Telegram clients send progressive)."""
    best = 0
    for s in getattr(photo, "sizes", None) or []:
        size = getattr(s, "size", None)
        if size is None:
            progressive = getattr(s, "sizes", None)
            size = max(progressive) if progressive else 0
        best = max(best, int(size or 0))
    return best or None


def guess_ext(name: str | None, mime: str | None, kind: str) -> str:
    if name and "." in name:
        ext = name.rpartition(".")[2]
        if 0 < len(ext) <= 10 and re.fullmatch(r"[A-Za-z0-9]+", ext):
            return ext.lower()
    if mime and mime.lower() in _MIME_EXT:
        return _MIME_EXT[mime.lower()]
    return {"photo": "jpg", "video": "mp4", "video_note": "mp4", "audio": "mp3",
            "voice": "ogg", "gif": "mp4", "sticker": "webp"}.get(kind, "bin")


def describe_media(media: Any) -> dict | None:
    """Turn a Telethon MessageMedia* into a plain dict, or None if it has no file.

    Returns {kind, key, size, name, mime, ext, date}. Duck-typed on purpose so it
    can be tested with lightweight fakes instead of real telethon objects.
    """
    if media is None:
        return None
    cls = type(media).__name__

    if cls == "MessageMediaPhoto":
        photo = getattr(media, "photo", None)
        if photo is None:
            return None
        pid = getattr(photo, "id", 0)
        return {"kind": "photo", "key": f"p{pid}", "size": photo_size(photo),
                "name": "", "mime": "image/jpeg", "ext": "jpg",
                "date": getattr(photo, "date", None)}

    if cls != "MessageMediaDocument":
        return None  # webpage previews, polls, geo, contact cards ...

    doc = getattr(media, "document", None)
    if doc is None or type(doc).__name__ != "Document":
        return None

    attrs = list(getattr(doc, "attributes", None) or [])
    names = {type(a).__name__ for a in attrs}
    mime = (getattr(doc, "mime_type", "") or "").lower()
    fname = ""
    for a in attrs:
        if getattr(a, "file_name", None):
            fname = a.file_name
            break

    kind = "document"
    if "DocumentAttributeSticker" in names:
        kind = "sticker"
    elif "DocumentAttributeVideo" in names:
        round_msg = any(getattr(a, "round_message", False) for a in attrs
                        if type(a).__name__ == "DocumentAttributeVideo")
        kind = "video_note" if round_msg else "video"
    elif "DocumentAttributeAudio" in names:
        is_voice = any(getattr(a, "voice", False) for a in attrs
                       if type(a).__name__ == "DocumentAttributeAudio")
        kind = "voice" if is_voice else "audio"
    elif "DocumentAttributeAnimated" in names or mime == "image/gif":
        kind = "gif"
    elif mime.startswith("image/"):
        kind = "photo"
    elif mime.startswith("audio/"):
        kind = "audio"

    return {
        "kind": kind,
        "key": f"d{getattr(doc, 'id', 0)}",
        "size": getattr(doc, "size", None),
        "name": fname,
        "mime": mime,
        "ext": guess_ext(fname, mime, kind),
        "date": getattr(doc, "date", None),
    }


def entry_filename(entry: dict, msg_id: int, date: Any = None) -> str:
    """<date>_<msgid>_<original name>.<ext> — keeps uploads sorted and collision-free."""
    ts = ""
    d = date or entry.get("date")
    if isinstance(d, datetime):
        ts = d.strftime("%Y%m%d")
    base = sanitize_filename(entry.get("name") or "", fallback="")
    if base:
        stem, dot, ext = base.rpartition(".")
        if not dot or len(ext) > 10:
            stem, ext = base, entry.get("ext") or "bin"
    else:
        stem, ext = entry.get("kind") or "file", entry.get("ext") or "bin"
    prefix = f"{ts}_" if ts else ""
    return f"{prefix}{msg_id}_{stem}.{ext}"


def wanted(entry: dict, kinds: set[str], min_size: int, max_size: int) -> bool:
    if entry.get("kind") not in kinds:
        return False
    size = entry.get("size")
    if size is not None:
        if min_size and size < min_size:
            return False
        if max_size and size > max_size:
            return False
    return True


def short_path(p: Any) -> str:
    """Path relative to the repo when possible — absolute otherwise. Never raises."""
    try:
        return Path(p).relative_to(BASE).as_posix()
    except (ValueError, TypeError, OSError):
        return str(p)


def chat_title(entity: Any) -> str:
    if entity is None:
        return "unknown"
    title = getattr(entity, "title", None)
    if title:
        return str(title)
    first = getattr(entity, "first_name", None) or ""
    last = getattr(entity, "last_name", None) or ""
    full = f"{first} {last}".strip()
    if full:
        return full
    uname = getattr(entity, "username", None)
    if uname:
        return str(uname)
    return f"chat_{getattr(entity, 'id', 'unknown')}"


def chat_dir_name(title: str, chat_key: str) -> str:
    """Folder per chat — id suffix keeps two same-named groups apart."""
    base = sanitize_filename(title, fallback="chat")
    return sanitize_filename(f"{base}_{chat_key}", fallback=f"chat_{chat_key}")


# ─── STATE (احترام به الگوی state پروژه: data/*.json) ──────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text("utf-8"))
            if isinstance(data, dict):
                data.setdefault("chats", {})
                data.setdefault("files", {})
                return data
        except Exception:
            pass
    return {"chats": {}, "files": {}}


def save_state(state: dict):
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), "utf-8")
    except Exception as e:
        log(f"  State save failed: {e}")


# ─── ENV ───────────────────────────────────────────────────

ENV_ALIASES = {
    "api_id": ("TG_API_ID", "TELEGRAM_API_ID", "API_ID"),
    "api_hash": ("TG_API_HASH", "TELEGRAM_API_HASH", "API_HASH"),
    "phone": ("TG_PHONE", "TELEGRAM_PHONE", "PHONE"),
}


def load_env() -> dict:
    """Read .env (same tolerant parser as droperog.py) + process env."""
    values: dict[str, str] = {}
    env_file = BASE / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text("utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip().strip("\"'")
        except Exception:
            pass
    for k, v in os.environ.items():
        values.setdefault(k, v)
    out = {}
    for field, names in ENV_ALIASES.items():
        for n in names:
            if values.get(n):
                out[field] = values[n]
                break
    return out


# ─── CLI ───────────────────────────────────────────────────

USAGE = """
DroperOG Grabber — دانلود گروهی فایل‌های چت‌های خودت

  python grabber.py --list                     لیست چت‌ها (برای پیدا کردن هدف)
  python grabber.py --login                    ورود/بررسی سشن
  python grabber.py --chat me                  Saved Messages
  python grabber.py --chat @channel --chat 1234567890
  python grabber.py --all                      همه‌ی چت‌های اکانت

گزینه‌ها:
  --chat SPEC      قابل تکرار؛ me یا @username یا آیدی عددی
  --all            همه‌ی دیالوگ‌ها
  --types LIST     photo,video,video_note,document,audio,voice,gif,sticker
                   یا all  (پیش‌فرض: همه جز sticker)
  --min-size SZ    حداقل حجم مثل 5MB       --max-size SZ   حداکثر حجم
  --limit N        حداکثر پیام در هر چت     --since DATE    از تاریخ YYYY-MM-DD
  --until DATE     تا تاریخ                --out DIR       پوشه‌ی مقصد (پیش‌فرض downloads/)
  --sleep SEC      فاصله‌ی بین فایل‌ها (پیش‌فرض 1.0)
  --full           نادیده گرفتن state و اسکن کامل (فایل‌های موجود باز پرش می‌شوند)
  --thumbs         ذخیره‌ی تصویر بندانگشتی هم (پیش‌فرض: فقط فایل اصلی)
  --dry-run        فقط گزارش، بدون دانلود
  --demo           تست آفلاین: بدون اکانت، بدون اینترنت، یک چت ساختگی
  --selftest       چک‌آپ کامل: چه چیزی آماده است و قدم بعدی چیست
  --help
"""


def parse_args(argv: list[str]) -> dict:
    args: dict[str, Any] = {
        "list": False, "login": False, "all": False, "chats": [],
        "types": list(DEFAULT_KINDS), "min_size": 0, "max_size": 0,
        "limit": 0, "since": None, "until": None, "out": str(DEFAULT_OUT),
        "sleep": 1.0, "full": False, "thumbs": False, "dry_run": False,
        "demo": False, "selftest": False, "help": False, "error": None,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None

        def value(flag: str) -> str | None:
            nonlocal i
            if nxt is None:
                args["error"] = f"{flag} needs a value"
                return None
            i += 1
            return nxt

        if a in ("--help", "-h"):
            args["help"] = True
        elif a == "--list":
            args["list"] = True
        elif a == "--login":
            args["login"] = True
        elif a == "--all":
            args["all"] = True
        elif a == "--full":
            args["full"] = True
        elif a == "--thumbs":
            args["thumbs"] = True
        elif a == "--dry-run":
            args["dry_run"] = True
        elif a == "--demo":
            args["demo"] = True
        elif a == "--selftest":
            args["selftest"] = True
        elif a == "--chat":
            v = value(a)
            if v:
                args["chats"].append(v)
        elif a == "--types":
            v = value(a)
            if v:
                if v.strip().lower() == "all":
                    args["types"] = list(ALL_KINDS)
                else:
                    picked = [t.strip().lower() for t in v.split(",") if t.strip()]
                    bad = [t for t in picked if t not in ALL_KINDS]
                    if bad:
                        args["error"] = f"unknown type(s): {', '.join(bad)}"
                    else:
                        args["types"] = picked
        elif a == "--out":
            v = value(a)
            if v:
                args["out"] = v
        elif a in ("--min-size", "--max-size"):
            v = value(a)
            parsed = parse_size(v)
            if parsed is None:
                args["error"] = f"{a} needs a size like 5MB"
            else:
                args["min_size" if a == "--min-size" else "max_size"] = parsed
        elif a == "--limit":
            v = value(a)
            args["limit"] = int(v) if (v or "").isdigit() else 0
            if not (v or "").isdigit():
                args["error"] = "--limit needs a number"
        elif a in ("--since", "--until"):
            v = value(a)
            d = parse_date(v)
            if d is None:
                args["error"] = f"{a} needs YYYY-MM-DD"
            else:
                if a == "--until":
                    d = d + timedelta(days=1)  # inclusive whole day
                args[a[2:]] = d
        elif a == "--sleep":
            v = value(a)
            try:
                args["sleep"] = max(0.0, float(v))
            except (TypeError, ValueError):
                args["error"] = "--sleep needs a number"
        else:
            args["error"] = f"unknown option: {a}"
        if args["error"]:
            return args
        i += 1
    return args


# ─── THE ASYNC WORK (needs telethon) ───────────────────────

def _errors_module():
    """telethon.errors, or a stub so --demo works before `pip install telethon`."""
    try:
        from telethon import errors
        return errors
    except ImportError:
        class _Stub:
            class FloodWaitError(Exception):
                seconds = 0

            class ChannelPrivateError(Exception):
                pass
        return _Stub


class Progress:
    """Throttled \r progress line for one download."""

    def __init__(self, label: str):
        self.label = label
        self.last = 0.0

    def __call__(self, received: int, total: int | None):
        now = time.time()
        if QUIET or (now - self.last < 0.2 and (not total or received < total)):
            return
        self.last = now
        sys.stderr.write(f"\r    {format_progress(received, total)}  {self.label[:40]}")
        sys.stderr.flush()

    def finish(self):
        if QUIET:
            return
        sys.stderr.write("\r" + " " * 78 + "\r")
        sys.stderr.flush()


def check_env(env: dict) -> str | None:
    if not env.get("api_id") or not env.get("api_hash"):
        return ("TG_API_ID / TG_API_HASH تنظیم نشده‌اند.\n"
                "  از https://my.telegram.org ← API development tools بگیر و در .env بگذار:\n"
                "    TG_API_ID=1234567\n"
                "    TG_API_HASH=abcdef0123456789abcdef0123456789\n"
                "    TG_PHONE=+98912XXXXXXX")
    try:
        int(env["api_id"])
    except ValueError:
        return "TG_API_ID باید عدد باشد."
    return None


async def resolve_entity(client, spec: str):
    if spec.strip().lower() in ("me", "self", "saved"):
        return await client.get_me()
    if re.fullmatch(r"-?\d+", spec.strip()):
        return await client.get_entity(int(spec.strip()))
    return await client.get_entity(spec.strip())


async def download_with_retry(client, msg, path: Path, prog: "Progress", attempts: int = 4):
    """download_media + backoff on FloodWait. Returns the written path or None."""
    errors = _errors_module()

    for attempt in range(attempts):
        try:
            return await client.download_media(msg, file=str(path), progress_callback=prog)
        except errors.FloodWaitError as e:
            if attempt == attempts - 1:
                raise
            log(f"  ! flood wait {e.seconds}s — sleeping")
            prog.finish()
            await asyncio.sleep(e.seconds + 1)
    return None


async def grab_chat(client, entity, spec, args, state, kinds, stats) -> None:
    errors = _errors_module()

    title = chat_title(entity)
    chat_key = str(getattr(entity, "id", spec))
    log(f"\n▸ {title}  (id={chat_key})")

    last_id = 0
    if not args["full"]:
        last_id = int((state["chats"].get(chat_key) or {}).get("last_id") or 0)
    if last_id:
        log(f"  incremental: messages newer than id {last_id}")

    out_dir = Path(args["out"]).expanduser() / chat_dir_name(title, chat_key)
    limit = args["limit"] or None
    max_id_seen = last_id
    scanned = 0

    try:
        messages = client.iter_messages(entity, min_id=last_id, limit=limit, reverse=True)
        async for msg in messages:
            scanned += 1
            if scanned % 200 == 0:  # checkpoint: crash-safe incremental progress
                state["chats"][chat_key] = {"title": title, "last_id": max_id_seen,
                                            "updated": datetime.now(timezone.utc).isoformat()}
                save_state(state)
            if not msg.media:
                continue
            when = getattr(msg, "date", None)
            if args["since"] and when and when < args["since"]:
                continue
            if args["until"] and when and when >= args["until"]:
                continue

            entry = describe_media(msg.media)
            if entry is None or not wanted(entry, kinds, args["min_size"], args["max_size"]):
                continue

            stats["found"] += 1
            size = entry.get("size")
            stats["bytes"] += int(size or 0)
            name = entry_filename(entry, msg.id, when)

            known = state["files"].get(entry["key"])
            path = out_dir / name
            if known and Path(known).exists():
                stats["already"] += 1
                log(f"  = skip (downloaded before)  {name}")
                max_id_seen = max(max_id_seen, msg.id)
                continue
            if path.exists() and (size is None or path.stat().st_size == size):
                stats["already"] += 1
                state["files"][entry["key"]] = str(path)
                log(f"  = skip (on disk)           {name}")
                max_id_seen = max(max_id_seen, msg.id)
                continue

            if args["dry_run"]:
                stats["planned"] += 1
                log(f"  + would grab  {entry['kind']:<10} {format_bytes(size):>10}  {name}")
                max_id_seen = max(max_id_seen, msg.id)
                continue

            out_dir.mkdir(parents=True, exist_ok=True)
            prog = Progress(name)
            try:
                written = await download_with_retry(client, msg, path, prog)
            except Exception as e:
                stats["errors"] += 1
                log(f"  ! failed: {name} ({type(e).__name__}: {e})")
                continue
            finally:
                prog.finish()

            if written:
                real = Path(written)
                stats["downloaded"] += 1
                stats["downloaded_bytes"] += real.stat().st_size if real.exists() else int(size or 0)
                state["files"][entry["key"]] = str(real)
                log(f"  ✓ {entry['kind']:<10} {format_bytes(size):>10}  {real.name}")
                if args["thumbs"]:
                    try:
                        await client.download_media(msg, file=str(real.with_suffix(".thumb.jpg")),
                                                    thumb=-1)
                    except Exception:
                        pass
            max_id_seen = max(max_id_seen, msg.id)

            if not args["dry_run"] and args["sleep"]:
                await asyncio.sleep(args["sleep"])
    except errors.ChannelPrivateError:
        stats["errors"] += 1
        log("  ! no access to this chat (ChannelPrivateError) — skipping")
        return
    except Exception as e:
        stats["errors"] += 1
        log(f"  ! chat failed: {type(e).__name__}: {e}")
        return

    seen_any = scanned or args["limit"]
    log(f"  scanned {scanned} message(s), newest id {max_id_seen}")
    if not args["dry_run"] and max_id_seen > last_id and seen_any:
        state["chats"][chat_key] = {"title": title, "last_id": max_id_seen,
                                    "updated": datetime.now(timezone.utc).isoformat()}
        save_state(state)


async def run_async(args: dict, env: dict) -> int:
    from telethon import TelegramClient

    state = load_state()
    kinds = set(args["types"])
    stats = {k: 0 for k in ("found", "downloaded", "already", "planned", "errors",
                            "bytes", "downloaded_bytes")}

    client = TelegramClient(str(SESSION_FILE), int(env["api_id"]), env["api_hash"])

    if args["login"]:
        await client.start(phone=env.get("phone"))
        me = await client.get_me()
        log(f"logged in as {chat_title(me)} (@{getattr(me, 'username', '?')}, id={me.id})")
        await client.disconnect()
        return 0

    await client.start(phone=env.get("phone"))
    try:
        me = await client.get_me()
        log(f"account: {chat_title(me)} (@{getattr(me, 'username', '?')})")

        if args["list"]:
            log(f"{'id':>16}  {'type':<16} {'username':<28} title")
            async for d in client.iter_dialogs():
                ent = d.entity
                uname = getattr(ent, "username", None)
                log(f"{getattr(ent, 'id', '?'):>16}  {type(ent).__name__:<16}"
                    f" {'@' + uname if uname else '-':<28} {chat_title(ent)}")
            return 0

        if not args["chats"] and not args["all"]:
            log("هیچ هدفی انتخاب نشده — --chat @name یا --all یا --list")
            log(USAGE)
            return 2

        log(f"targets: {'ALL dialogs' if args['all'] else ', '.join(args['chats'])}")
        log(f"types: {','.join(args['types'])} | out: {args['out']}"
            f"{' | DRY RUN' if args['dry_run'] else ''}")

        pairs: list[tuple[Any, str]] = []
        if args["all"]:
            async for d in client.iter_dialogs():
                pairs.append((d.entity, chat_title(d.entity)))
        else:
            for spec in args["chats"]:
                try:
                    pairs.append((await resolve_entity(client, spec), spec))
                except Exception as e:
                    stats["errors"] += 1
                    log(f"! cannot resolve '{spec}': {type(e).__name__}: {e}")

        for entity, spec in pairs:
            await grab_chat(client, entity, spec, args, state, kinds, stats)
            save_state(state)
    finally:
        save_state(state)
        await client.disconnect()

    report = build_report(args, stats)
    print("\n" + report)
    REPORT_FILE.write_text(report, "utf-8")
    log(f"Report -> {REPORT_FILE}")
    return 0 if stats["errors"] == 0 else 1


def build_report(args: dict, stats: dict) -> str:
    sep = "=" * 58
    lines = [sep, f"  DroperOG Grabber — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", sep, ""]
    lines.append(f"  found media    : {stats['found']}  ({format_bytes(stats['bytes'])})")
    if args["dry_run"]:
        lines.append(f"  would download : {stats['planned']}  (last run of many)")
        lines.append(f"  already have   : {stats['already']}")
    else:
        lines.append(f"  downloaded     : {stats['downloaded']}"
                     f"  ({format_bytes(stats['downloaded_bytes'])})")
        lines.append(f"  skipped        : {stats['already']}")
    lines.append(f"  errors         : {stats['errors']}")
    lines.append("")
    lines.append(f"  output dir     : {args['out']}")
    lines.append(sep)
    return "\n".join(lines)


# ─── SELF-TEST (یک دستور، یک گزارش خوانا) ────────────────

SELFTEST_REPORT = DATA_DIR / "grabber_selftest.txt"


def _check_pipeline(tmp_root: Path) -> tuple[bool, str]:
    """مسیر واقعی دانلود را دو بار روی چت ساختگی اجرا می‌کند (بی‌صدا)."""
    global STATE_FILE, DEMO_DELAY, QUIET
    saved = (STATE_FILE, DEMO_DELAY, QUIET)
    STATE_FILE = tmp_root / "state.json"
    DEMO_DELAY = 0
    QUIET = True
    try:
        args = {"out": str(tmp_root / "out"), "dry_run": False, "sleep": 0,
                "types": list(DEFAULT_KINDS), "limit": 0, "full": False,
                "since": None, "until": None, "min_size": 0, "max_size": 0,
                "thumbs": False}
        runs = []
        for _ in range(2):
            state = load_state()
            stats = {k: 0 for k in ("found", "downloaded", "already", "planned",
                                    "errors", "bytes", "downloaded_bytes")}
            asyncio.run(grab_chat(DemoClient(demo_messages()), DemoChat(), "demo",
                                  args, state, set(args["types"]), stats))
            runs.append(stats)
        files = [p for p in (tmp_root / "out").rglob("*") if p.is_file()]
    finally:
        STATE_FILE, DEMO_DELAY, QUIET = saved
    first, second = runs
    ok = (first["downloaded"] == 4 and first["errors"] == 0
          and second["downloaded"] == 0 and second["already"] == 4
          and len(files) == 4)
    detail = (f"اجرای اول: {first['downloaded']} دانلود | اجرای دوم: "
              f"{second['already']} پرش، {second['downloaded']} دانلود")
    return ok, detail


def selftest(args: dict) -> int:
    """چک‌آپ کامل بدون اکانت. می‌گوید چه چیزی آماده است و قدم بعدی چیست."""
    import platform
    import shutil
    import tempfile

    rows: list[tuple[str, str, str]] = []  # (status, label, detail)

    def row(status: str, label: str, detail: str):
        rows.append((status, label, detail))

    py_ok = sys.version_info >= (3, 10)
    row("OK" if py_ok else "FAIL", "python",
        f"{platform.python_version()}" + ("" if py_ok else " — باید 3.10+ باشد"))

    try:
        import telethon
        row("OK", "telethon", getattr(telethon, "__version__", "?"))
    except ImportError:
        row("FAIL", "telethon", "نصب نیست → pip install -r requirements.txt")

    env = load_env()
    have = [n for n, alias in (("api_id", "TG_API_ID"), ("api_hash", "TG_API_HASH"))
            if env.get(n)]
    if len(have) == 2:
        row("OK", "credentials", "TG_API_ID + TG_API_HASH تنظیم شده")
    else:
        row("FAIL", "credentials",
            "TG_API_ID/TG_API_HASH نیست — برای تست واقعی لازم است؛"
            " همین حالا با --demo تست کن")

    session = Path(str(SESSION_FILE) + ".session")
    if session.exists():
        row("OK", "session", f"{session.name} موجود است (لاگین شده‌ای)")
    else:
        row("--", "session", "هنوز لاگین نکرده‌ای → python grabber.py --login")

    try:
        probe = STATE_FILE.parent / ".selftest_probe"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("x", "utf-8")
        probe.unlink()
        row("OK", "state file", f"{short_path(STATE_FILE)} قابل نوشتن")
    except Exception as e:
        row("FAIL", "state file", f"نمی‌توان در {short_path(STATE_FILE)} نوشت: {e}")

    out_dir = Path(args["out"]).expanduser()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        probe = out_dir / ".selftest_probe"
        probe.write_text("x", "utf-8")
        probe.unlink()
        row("OK", "output dir", f"{short_path(out_dir)} قابل نوشتن")
    except Exception as e:
        row("FAIL", "output dir", f"نمی‌توان در {short_path(out_dir)} نوشت: {e}")

    traversal = ["../../evil.exe", "..", "a/b", "CON.txt"]
    bad = [n for n in traversal
           if ".." in sanitize_filename(n) or "/" in sanitize_filename(n)
           or "\\" in sanitize_filename(n)]
    row("OK" if not bad else "FAIL", "filename rules",
        "نام‌ها امن‌سازی می‌شوند" if not bad else f"مشکل: {bad}")

    tmp_root = Path(tempfile.mkdtemp(prefix="grabber_selftest_"))
    try:
        pipe_ok, pipe_detail = _check_pipeline(tmp_root)
    except Exception as e:
        pipe_ok, pipe_detail = False, f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    row("OK" if pipe_ok else "FAIL", "download pipeline", pipe_detail)

    icons = {"OK": " OK ", "FAIL": "FAIL", "WARN": "WARN", "--": " -- "}
    lines = ["=" * 62, "  DroperOG Grabber — self-test", "=" * 62, ""]
    for status, label, detail in rows:
        lines.append(f"  [{icons[status]}] {label:<18} {detail}")
    lines.append("")

    fatal = [r for r in rows if r[0] == "FAIL" and r[1] != "credentials"]
    creds_missing = any(r[1] == "credentials" and r[0] == "FAIL" for r in rows)
    if fatal:
        lines.append("  نتیجه: نصب مشکل دارد — خط‌های FAIL بالا را ببین.")
        code = 1
    elif creds_missing:
        lines.append("  نتیجه: نصب سالم است. تست آفلاین: python grabber.py --demo")
        lines.append("  برای تست واقعی: TG_API_ID/TG_API_HASH را در .env بگذار،")
        lines.append("  بعد: python grabber.py --login && python grabber.py --list")
        code = 1
    else:
        lines.append("  نتیجه: همه‌چیز آماده. python grabber.py --list")
        code = 0
    lines.append("=" * 62)

    report = "\n".join(lines)
    print(report)
    try:
        SELFTEST_REPORT.write_text(report, "utf-8")
    except Exception:
        pass
    return code


# ─── OFFLINE DEMO (تست بدون اکانت و بدون اینترنت) ──────────
# این کلاس‌ها عمداً هم‌نام telethon هستند چون describe_media() عمداً
# duck-typed است و روی نام کلاس/attribute کار می‌کند، نه روی نوع واقعی.

DEMO_DELAY = 0.15  # فاصله‌ی تیک‌های پیشرفت جعلی (در تست‌ها صفر می‌شود)
DEMO_STATE = DATA_DIR / "demo_state.json"


class PhotoSize:
    def __init__(self, size):
        self.size = size


class PhotoSizeProgressive:
    def __init__(self, sizes):
        self.sizes = list(sizes)


class Photo:
    def __init__(self, id=1, sizes=()):
        self.id = id
        self.sizes = list(sizes)


class MessageMediaPhoto:
    def __init__(self, photo):
        self.photo = photo


class DocumentAttributeFilename:
    def __init__(self, file_name):
        self.file_name = file_name


class DocumentAttributeVideo:
    def __init__(self, round_message=False):
        self.round_message = round_message


class DocumentAttributeAudio:
    def __init__(self, voice=False):
        self.voice = voice


class Document:
    def __init__(self, id=1, size=0, mime_type="", attributes=()):
        self.id = id
        self.size = size
        self.mime_type = mime_type
        self.attributes = list(attributes)


class MessageMediaDocument:
    def __init__(self, document):
        self.document = document


class DemoMessage:
    def __init__(self, id, media, date):
        self.id = id
        self.media = media
        self.date = date


class DemoChat:
    id = -1001234567890
    title = "Demo Channel"


class DemoClient:
    """کلاینت جعلی: پیام‌های ساختگی را می‌دهد و واقعاً بایت روی دیسک می‌نویسد."""

    def __init__(self, messages):
        self.messages = messages

    def iter_messages(self, entity, **kwargs):
        async def gen():
            for m in self.messages:
                yield m
        return gen()

    async def download_media(self, msg, file=None, progress_callback=None, thumb=None):
        entry = describe_media(msg.media) or {}
        total = int(entry.get("size") or 16)
        Path(file).parent.mkdir(parents=True, exist_ok=True)
        with open(file, "wb") as fh:
            step = max(1, total // 4)
            written = 0
            while written < total:
                chunk = min(step, total - written)
                fh.write(b"\0" * chunk)
                written += chunk
                if progress_callback:
                    progress_callback(written, total)
                    await asyncio.sleep(DEMO_DELAY)
        return file


def demo_messages() -> list:
    """یک چت ساختگی با انواع فایل، از جمله یک پیام متنی که باید نادیده برود."""
    now = datetime.now(timezone.utc)
    return [
        DemoMessage(1, MessageMediaPhoto(Photo(id=101, sizes=[
            PhotoSize(9_000), PhotoSizeProgressive([1_000, 240_000])])), now),
        DemoMessage(2, None, now),
        DemoMessage(3, MessageMediaDocument(Document(
            id=202, size=2 * 1024 ** 2, mime_type="video/mp4",
            attributes=[DocumentAttributeVideo(),
                        DocumentAttributeFilename("clip.mp4")])), now),
        DemoMessage(4, MessageMediaDocument(Document(
            id=303, size=96 * 1024, mime_type="application/pdf",
            attributes=[DocumentAttributeFilename("report.pdf")])), now),
        DemoMessage(5, MessageMediaDocument(Document(
            id=404, size=18 * 1024, mime_type="audio/ogg",
            attributes=[DocumentAttributeAudio(voice=True)])), now),
    ]


async def run_demo(args: dict) -> int:
    """تست کامل آفلاین: همان grab_chat واقعی، روی یک چت ساختگی — دو بار،
    تا هم دانلود و هم رفتار «پرش در اجرای دوم» را ببینی."""
    import shutil

    global STATE_FILE

    out_root = Path(args["out"]).expanduser() / "_demo"
    shutil.rmtree(out_root, ignore_errors=True)
    DEMO_STATE.unlink(missing_ok=True)

    log("DEMO — تست آفلاین: هیچ اتصالی به تلگرام انجام نمی‌شود")
    log(f"خروجی موقت در {out_root} نوشته می‌شود (هر وقت خواستی پاکش کن)")

    real_state = STATE_FILE
    STATE_FILE = DEMO_STATE  # تا state واقعی پروژه آلوده نشود
    demo_args = dict(args)
    demo_args["out"] = str(out_root)
    demo_args["dry_run"] = False
    try:
        for i, label in enumerate(("اجرای اول — همه‌چیز تازه است",
                                  "اجرای دوم — باید همه را پرش کند"), start=1):
            log(f"\n── {label}")
            state = load_state()
            stats = {k: 0 for k in ("found", "downloaded", "already", "planned",
                                    "errors", "bytes", "downloaded_bytes")}
            await grab_chat(DemoClient(demo_messages()), DemoChat(), "demo",
                            demo_args, state, set(demo_args["types"]), stats)
            print("\n" + build_report(demo_args, stats))
    finally:
        STATE_FILE = real_state

    files = sorted(p.relative_to(out_root).as_posix()
                   for p in out_root.rglob("*") if p.is_file())
    log(f"\n{len(files)} فایل روی دیسک:")
    for f in files:
        log(f"  {f}")
    log("\nDEMO تمام شد. برای تست واقعی: TG_API_ID/TG_API_HASH در .env، "
        "سپس `python grabber.py --login`")
    return 0


def main():
    args = parse_args(sys.argv[1:])
    if args["error"]:
        log(f"error: {args['error']}")
        print(USAGE)
        sys.exit(2)
    if args["help"] or (not args["list"] and not args["login"] and not args["all"]
                        and not args["chats"] and not args["demo"]
                        and not args["selftest"]):
        print(USAGE)
        sys.exit(0 if args["help"] else 2)

    if args["selftest"]:
        sys.exit(selftest(args))

    if args["demo"]:
        try:
            sys.exit(asyncio.run(run_demo(args)))
        except KeyboardInterrupt:
            log("متوقف شد")
            sys.exit(130)

    env = load_env()
    problem = check_env(env)
    if problem:
        log(problem)
        sys.exit(2)

    try:
        import telethon  # noqa: F401
    except ImportError:
        log("telethon نصب نیست — یک بار اجرا کن:  pip install telethon")
        sys.exit(2)

    try:
        code = asyncio.run(run_async(args, env))
    except KeyboardInterrupt:
        log("stopped by user — state saved, run again to resume")
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
