# Soroosh_tg_bot.py — v27.9.3 (PV fix final + notify + pv:menu)
import os, sys, json, ssl, socket, asyncio, time, glob, re, threading, secrets, queue
import logging, traceback, concurrent.futures, inspect, random, hashlib
import html as _html
import builtins
from typing import Optional, Dict, Any, List, Set, Tuple

VERSION = "Soroosh v27.9.3"

def _detect_data_dir():
    env = os.environ.get("DATA_DIR", "").strip()
    if env and os.path.isdir(env) and os.access(env, os.W_OK): return env
    rv = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if rv and os.path.isdir(rv) and os.access(rv, os.W_OK): return rv
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        for c in ["/data", "/app/data"]:
            if os.path.isdir(c) and os.access(c, os.W_OK): return c
    return os.path.dirname(os.path.abspath(__file__))

DATA_DIR = _detect_data_dir()
SOROOSH_DIR = os.path.join(DATA_DIR, "soroosh")
os.makedirs(SOROOSH_DIR, exist_ok=True)
LOG_FILE = os.path.join(SOROOSH_DIR, "soroosh.log")
UPLOADS_DIR = os.path.join(SOROOSH_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

logging.basicConfig(level=logging.CRITICAL, stream=open(os.devnull, "w"))
for _n in ("urllib3", "urllib3.connectionpool", "requests", "httpx",
           "httpcore", "telegram.ext.Updater", "telegram.request", "telethon", "splusthon"):
    logging.getLogger(_n).setLevel(logging.CRITICAL); logging.getLogger(_n).propagate = False

print(f"[+] VERSION: {VERSION}")
print(f"[+] DATA_DIR: {DATA_DIR}")

try: FORCED_OWNER = int(os.environ.get("TG_OWNER_ID", "8389746549"))
except Exception: FORCED_OWNER = 8389746549
print(f"[+] OWNER: {FORCED_OWNER}")

try:
    import asyncio.unix_events as _ue
    _orig_add_signal = _ue._UnixSelectorEventLoop.add_signal_handler
    def _safe_add_signal(self, sig, callback, *args):
        try: return _orig_add_signal(self, sig, callback, *args)
        except (RuntimeError, ValueError, NotImplementedError, AttributeError): return None
    _ue._UnixSelectorEventLoop.add_signal_handler = _safe_add_signal
except Exception: pass

_flog = logging.getLogger("soroosh_file"); _flog.setLevel(logging.DEBUG); _flog.propagate = False
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    _flog.addHandler(_fh)
except Exception: pass

def flog(msg: str, level="info"):
    try: print(f"[soroosh] {msg}", flush=True)
    except Exception: pass
    try: getattr(_flog, level)(msg)
    except Exception: pass


# ═══════════════ SPLUSTHON IMPORTS ═══════════════
try:
    from splusthon import SoroushClient, events
    from splusthon.sessions import StringSession
    from splusthon.errors import RPCError, FloodWaitError
    from splusthon.tl.functions.messages import ImportChatInviteRequest, DeleteChatUserRequest
    from splusthon.tl.functions.channels import LeaveChannelRequest, JoinChannelRequest
    from splusthon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
    from splusthon.tl.types import InputUserSelf

    try: from splusthon.tl.functions.messages import EditMessageRequest
    except Exception: EditMessageRequest = None
    try: from splusthon.tl.functions.messages import CheckChatInviteRequest
    except Exception: CheckChatInviteRequest = None
    try: from splusthon.tl.functions.account import UpdatePersonalChannelRequest
    except Exception: UpdatePersonalChannelRequest = None
    try: from splusthon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
    except Exception: UploadProfilePhotoRequest = None; DeletePhotosRequest = None
    try: from splusthon.tl.types import InputPhoto, InputPhotoEmpty
    except Exception: InputPhoto = None; InputPhotoEmpty = None

    InputChannel = None
    for mod in ("splusthon.tl.types", "splusthon.tl.types.channels"):
        try:
            o = __import__(mod, fromlist=["InputChannel"])
            if hasattr(o, "InputChannel"): InputChannel = o.InputChannel; break
        except Exception: pass

    InputPeerChannel = None
    for mod in ("splusthon.tl.types", "splusthon.tl.types.channels"):
        try:
            o = __import__(mod, fromlist=["InputPeerChannel"])
            if hasattr(o, "InputPeerChannel"): InputPeerChannel = o.InputPeerChannel; break
        except Exception: pass

    InputPeerUser = None
    try:
        from splusthon.tl.types import InputPeerUser as _IPU
        InputPeerUser = _IPU
    except Exception: pass

    CreateChannelRequest = ExportChatInviteRequest = EditTitleRequest = None
    EditPhotoRequest = GetFullChannelRequest = None

    for mod_name, attr_name, target in [
        ("splusthon.tl.functions.channels", "CreateChannelRequest", "CreateChannelRequest"),
        ("splusthon.tl.functions.channels", "EditTitleRequest", "EditTitleRequest"),
        ("splusthon.tl.functions.channels", "EditPhotoRequest", "EditPhotoRequest"),
        ("splusthon.tl.functions.channels", "GetFullChannelRequest", "GetFullChannelRequest"),
        ("splusthon.tl.functions.messages", "ExportChatInviteRequest", "ExportChatInviteRequest"),
        ("splusthon.tl.functions.messages", "EditChatAboutRequest", "EditTitleRequest"),
        ("splusthon.tl.functions.messages", "EditChatTitleRequest", "EditTitleRequest"),
    ]:
        try:
            m = __import__(mod_name, fromlist=[attr_name])
            if hasattr(m, attr_name):
                if target == "CreateChannelRequest": CreateChannelRequest = getattr(m, attr_name)
                elif target == "ExportChatInviteRequest": ExportChatInviteRequest = getattr(m, attr_name)
                elif target == "EditTitleRequest" and EditTitleRequest is None: EditTitleRequest = getattr(m, attr_name)
                elif target == "EditPhotoRequest" and EditPhotoRequest is None: EditPhotoRequest = getattr(m, attr_name)
                elif target == "GetFullChannelRequest" and GetFullChannelRequest is None: GetFullChannelRequest = getattr(m, attr_name)
        except Exception: pass

    print(f"[+] InputChannel: {'OK' if InputChannel else 'NO'}")
    print(f"[+] InputPeerUser: {'OK' if InputPeerUser else 'NO'}")
    print(f"[+] CreateChannel: {'OK' if CreateChannelRequest else 'NO'}")
    print(f"[+] ExportInvite: {'OK' if ExportChatInviteRequest else 'NO'}")
    print(f"[+] GetFullChannel: {'OK' if GetFullChannelRequest else 'NO'}")

    try:
        from splusthon.tl.functions.photos import UploadProfilePhotoRequest
    except Exception: UploadProfilePhotoRequest = None

    SOROOSH_AVAILABLE = True
except ImportError as _e:
    print(f"[x] splusthon not installed: {_e}"); sys.exit(1)


# ═══════════════ HELPERS ═══════════════
def _load(path, default):
    if not os.path.exists(path):
        return dict(default) if isinstance(default, dict) else default
    try:
        with open(path, encoding="utf-8") as f: d = json.load(f)
        if isinstance(default, dict) and isinstance(d, dict): return {**default, **d}
        return d
    except Exception: return dict(default) if isinstance(default, dict) else default

def _save(path, data):
    try: os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    except Exception: pass
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(path + ".tmp", path)

def _fmt_error(e):
    if e is None: return "—"
    s = str(e)
    if isinstance(e, dict): return str(e)[:300]
    if hasattr(e, "message"): return str(e.message)[:300]
    return s[:300]

def _is_rate_limit(ex):
    return any(k in str(ex).upper() for k in ("FLOOD", "TOO_MANY", "RATE_LIMIT", "TOO_REQUESTS"))

def _is_perm_error(ex):
    msg = str(ex).upper()
    return any(k in msg for k in ("CHAT_WRITE_FORBIDDEN", "USER_BANNED_IN_CHANNEL",
                                  "CHANNEL_PRIVATE", "CHAT_ADMIN_REQUIRED",
                                  "NOT_ENOUGH_RIGHTS", "SEND_MESSAGES_FORBIDDEN",
                                  "MESSAGE_SEND_FAILED", "FORBIDDEN", "USER_KICKED",
                                  "USER_NOT_PARTICIPANT", "USER_SUSPENDED",
                                  "USER_DEACTIVATED", "SESSION_REVOKED",
                                  "AUTH_KEY_UNREGISTERED"))

def _is_suspended(ex):
    msg = str(ex).upper()
    return any(k in msg for k in ("USER_SUSPENDED", "USER_DEACTIVATED",
                                   "SESSION_REVOKED", "AUTH_KEY_UNREGISTERED"))

def _is_group_or_channel(ent) -> bool:
    if ent is None: return False
    try:
        cls = type(ent).__name__.lower()
        if "user" in cls or "bot" in cls: return False
        if any(k in cls for k in ("channel", "chat", "group", "megagroup")): return True
        fn = getattr(ent, "first_name", None)
        if fn: return False
        t = getattr(ent, "title", None)
        if t: return True
        if hasattr(ent, "megagroup"): return True
    except Exception: pass
    return False

def _is_actual_group(ent) -> bool:
    if ent is None: return False
    try:
        bc = getattr(ent, "broadcast", False)
        mg = getattr(ent, "megagroup", False)
        if bc and not mg: return False
        return _is_group_or_channel(ent)
    except Exception: return False

def normalize_phone(raw: str) -> str:
    if not raw: return ""
    s = re.sub(r"[^\d]", "", str(raw))
    if not s: return ""
    if s.startswith("00"): s = s[2:]
    if s.startswith("0"): s = s[1:]
    if not s.startswith("98"): s = "98" + s
    if len(s) < 11 or len(s) > 13: raise ValueError(f"شماره نامعتبر: {raw}")
    return s

def _hash_of(link):
    if not link: return ""
    s = link.strip().lower()
    if s.startswith("@"): return "u:" + s[1:]
    m = re.search(r"/joinchat/([A-Za-z0-9_\-]+)", s)
    if m: return "j:" + m.group(1)
    m = re.search(r"/joingroup/([A-Za-z0-9_\-]+)", s)
    if m: return "j:" + m.group(1)
    m = re.search(r"(?:splus\.ir|soroush\.ir)/([A-Za-z0-9_\-]+)", s)
    if m: return "u:" + m.group(1)
    return "x:" + s[:60]


# ═══════════════ PERSISTENT STATE ═══════════════
SEEN_FILE        = os.path.join(SOROOSH_DIR, "seen_links.json")
BANNED_FILE      = os.path.join(SOROOSH_DIR, "banned_groups.json")
LDPROG_FILE      = os.path.join(SOROOSH_DIR, "linkdoni_progress.json")
PV_REPLIES_FILE  = os.path.join(SOROOSH_DIR, "pv_replies.json")
PV_ITEMS_FILE    = os.path.join(SOROOSH_DIR, "pv_items.json")
PV_REPORT_FILE   = os.path.join(SOROOSH_DIR, "pv_report.json")

_SEEN_CACHE: Optional[Set[str]] = None
_BANNED_CACHE: Optional[Dict[str, Any]] = None

def _load_seen() -> Set[str]:
    global _SEEN_CACHE
    if _SEEN_CACHE is None:
        d = _load(SEEN_FILE, {})
        _SEEN_CACHE = set(d.keys()) if isinstance(d, dict) else set()
    return _SEEN_CACHE

def _mark_seen(h: str):
    if not h: return
    global _SEEN_CACHE
    seen = _load_seen()
    if h in seen: return
    seen.add(h)
    try:
        d = {k: 1 for k in seen}
        if len(d) > 50000:
            d = dict(list(d.items())[-40000:])
            _SEEN_CACHE = set(d.keys())
        _save(SEEN_FILE, d)
    except Exception: pass

def _is_seen(h: str) -> bool:
    if not h: return False
    return h in _load_seen()

def _clear_seen():
    global _SEEN_CACHE
    _SEEN_CACHE = set()
    try: _save(SEEN_FILE, {})
    except Exception: pass

def _load_banned() -> Dict[str, Any]:
    global _BANNED_CACHE
    if _BANNED_CACHE is None:
        d = _load(BANNED_FILE, {})
        _BANNED_CACHE = d if isinstance(d, dict) else {}
    return _BANNED_CACHE

def _mark_banned(h: str, reason: str = ""):
    if not h: return
    global _BANNED_CACHE
    b = _load_banned()
    b[h] = {"reason": str(reason)[:120], "ts": int(time.time())}
    try: _save(BANNED_FILE, b)
    except Exception: pass

def _is_banned(h: str) -> bool:
    if not h: return False
    return h in _load_banned()

def _clear_banned():
    global _BANNED_CACHE
    _BANNED_CACHE = {}
    try: _save(BANNED_FILE, {})
    except Exception: pass

def _load_ldprog() -> Dict[str, int]:
    d = _load(LDPROG_FILE, {})
    return d if isinstance(d, dict) else {}

def _get_ld_last(url: str) -> int:
    try: return int(_load_ldprog().get(url, 0))
    except Exception: return 0

def _set_ld_last(url: str, max_id: int):
    if not url: return
    d = _load_ldprog()
    try:
        old = int(d.get(url, 0))
        new = int(max_id)
        if new > old:
            d[url] = new
            _save(LDPROG_FILE, d)
    except Exception: pass

def _reset_ld_progress():
    try: _save(LDPROG_FILE, {})
    except Exception: pass

def _load_pv_replies() -> Dict[str, Any]:
    d = _load(PV_REPLIES_FILE, {})
    return d if isinstance(d, dict) else {}

def _save_pv_replies(d): _save(PV_REPLIES_FILE, d)

def _mark_pv_replied(aid: str, user_id: str):
    d = _load_pv_replies()
    acc = d.setdefault(aid, {})
    acc[str(user_id)] = int(time.time())
    if len(acc) > 10000:
        sorted_items = sorted(acc.items(), key=lambda x: x[1])
        d[aid] = dict(sorted_items[-8000:])
    _save_pv_replies(d)

def _has_pv_replied(aid: str, user_id: str) -> bool:
    d = _load_pv_replies()
    return str(user_id) in (d.get(aid) or {})

def _clear_pv_replies():
    _save_pv_replies({})

DEFAULT_PV_ITEMS = {
    "enabled": False,
    "delay_seconds": 120,
    "reply_once": True,
    "notify": True,
    "items": [{"kind": "text", "text": "سلام 👋"}]
}

def _load_pv_items() -> Dict[str, Any]:
    d = _load(PV_ITEMS_FILE, DEFAULT_PV_ITEMS)
    if not isinstance(d, dict): return dict(DEFAULT_PV_ITEMS)
    for k, v in DEFAULT_PV_ITEMS.items():
        if k not in d: d[k] = v
    return d

def _save_pv_items(d): _save(PV_ITEMS_FILE, d)

def _load_pv_report() -> Dict[str, Any]:
    d = _load(PV_REPORT_FILE, {})
    return d if isinstance(d, dict) else {}

def _save_pv_report(d): _save(PV_REPORT_FILE, d)

def _record_pv_visit(aid: str, user_id: str, user_info: Dict[str, Any] = None):
    rep = _load_pv_report()
    acc = rep.setdefault(aid, {})
    uid = str(user_id)
    now = int(time.time())
    if uid in acc:
        acc[uid]["last_seen"] = now
        acc[uid]["count"] = acc[uid].get("count", 1) + 1
        if user_info:
            for k, v in user_info.items():
                if v is not None: acc[uid][k] = v
    else:
        entry = {"first_seen": now, "last_seen": now, "count": 1,
                 "replied": False, "reply_ok": False, "error": None, "blocked": False}
        if user_info:
            entry.update({k: v for k, v in user_info.items() if v is not None})
        acc[uid] = entry
    if len(acc) > 5000:
        sorted_items = sorted(acc.items(), key=lambda x: x[1].get("last_seen", 0))
        rep[aid] = dict(sorted_items[-4000:])
    _save_pv_report(rep)

def _record_pv_reply(aid: str, user_id: str, ok: bool, err: str = None):
    rep = _load_pv_report()
    acc = rep.setdefault(aid, {})
    uid = str(user_id)
    if uid not in acc:
        acc[uid] = {"first_seen": int(time.time()), "last_seen": int(time.time()),
                    "count": 1, "replied": False, "reply_ok": False}
    acc[uid]["replied"] = True
    acc[uid]["replied_at"] = int(time.time())
    acc[uid]["reply_ok"] = bool(ok)
    if err:
        acc[uid]["error"] = str(err)[:200]
        acc[uid]["blocked"] = "FORBIDDEN" in str(err).upper() or "SUSPENDED" in str(err).upper()
    else:
        acc[uid]["error"] = None
        acc[uid]["blocked"] = False
    _save_pv_report(rep)

def _clear_pv_report():
    _save_pv_report({})


# ═══════════════ LINK DONIES ═══════════════
LINK_DONIES_FILE = os.path.join(SOROOSH_DIR, "linkdonies.json")
DEFAULT_LINK_DONIES = ["https://splus.ir/sapt_iran", "https://splus.ir/Linkv",
                       "https://splus.ir/link_d", "https://splus.ir/Linkv29"]

def load_link_donies() -> List[str]:
    d = _load(LINK_DONIES_FILE, None)
    if not isinstance(d, list) or not d:
        _save(LINK_DONIES_FILE, DEFAULT_LINK_DONIES); return list(DEFAULT_LINK_DONIES)
    return d

def save_link_donies(lst): _save(LINK_DONIES_FILE, lst)

def add_link_doni(url: str) -> bool:
    url = url.strip()
    if not url: return False
    lst = load_link_donies()
    if url in lst: return False
    lst.append(url); save_link_donies(lst); return True

def remove_link_doni(idx: int) -> bool:
    lst = load_link_donies()
    if idx < 0 or idx >= len(lst): return False
    lst.pop(idx); save_link_donies(lst); return True


# ═══════════════ SOROOSH LOOP ═══════════════
_soroosh_loop: Optional[asyncio.AbstractEventLoop] = None
_soroosh_loop_thread: Optional[threading.Thread] = None
_soroosh_loop_lock = threading.Lock()

def _run_soroosh_loop():
    global _soroosh_loop
    _soroosh_loop = asyncio.new_event_loop(); asyncio.set_event_loop(_soroosh_loop)
    flog("[soroosh-loop] started"); _soroosh_loop.run_forever()

def ensure_soroosh_loop():
    global _soroosh_loop_thread
    with _soroosh_loop_lock:
        if _soroosh_loop_thread is None or not _soroosh_loop_thread.is_alive():
            _soroosh_loop_thread = threading.Thread(target=_run_soroosh_loop, daemon=True, name="soroosh-loop")
            _soroosh_loop_thread.start(); time.sleep(0.5)

_ACCOUNT_LOCKS_BY_LOOP: Dict[int, Dict[str, asyncio.Lock]] = {}
_ACCOUNT_LOCKS_GUARD = threading.Lock()

def _get_account_lock(aid):
    if not aid: return None
    try: loop = asyncio.get_running_loop()
    except RuntimeError: return None
    loop_id = id(loop)
    with _ACCOUNT_LOCKS_GUARD:
        per_loop = _ACCOUNT_LOCKS_BY_LOOP.setdefault(loop_id, {})
        if aid not in per_loop: per_loop[aid] = asyncio.Lock()
        return per_loop[aid]


class SafeSoroushClient:
    def __init__(self, aid, session_string, name=None, use_lock=True):
        self.aid = aid; self.session_string = session_string
        self.name = name or aid; self._client = None
        self._lock = _get_account_lock(aid) if use_lock else None
        self._locked = False

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        raw = self.__dict__.get("_client")
        if raw is None:
            raise AttributeError(f"SafeSoroushClient[{self.__dict__.get('aid','?')}]: not connected ({name})")
        return getattr(raw, name)

    async def __aenter__(self):
        if self._lock:
            try:
                await asyncio.wait_for(self._lock.acquire(), timeout=5); self._locked = True
            except (asyncio.TimeoutError, asyncio.CancelledError):
                flog(f"[client] lock timeout for {self.aid}", "warning")
                self._locked = False
                try:
                    if self._lock.locked():
                        self._lock._locked = False
                        self._lock._waiters = []
                except Exception: pass
        try:
            await self._connect(); return self
        except BaseException:
            if self._locked:
                try: self._lock.release()
                except Exception: pass
                self._locked = False
            raise

    async def __aexit__(self, *args, **kwargs):
        try: await self._disconnect()
        finally:
            if self._locked:
                try: self._lock.release()
                except Exception: pass
                self._locked = False

    async def _connect(self):
        if self._client is not None and self._client.is_connected(): return
        cli = SoroushClient(StringSession(self.session_string))
        await cli.connect()
        if not await cli.is_user_authorized():
            try: await cli.disconnect()
            except Exception: pass
            raise RuntimeError("NO_SESSION")
        self._client = cli

    async def _disconnect(self):
        if self._client is not None:
            try: await self._client.disconnect()
            except Exception: pass
            self._client = None

    @property
    def raw(self): return self._client
    async def get_me(self): return await self._client.get_me()
    async def get_dialogs(self, limit=None):
        if limit: return await self._client.get_dialogs(limit=limit)
        return await self._client.get_dialogs()
    async def get_messages(self, entity, limit=30, **kw):
        return await self._client.get_messages(entity, limit=limit, **kw)
    async def send_message(self, entity, text, **kw):
        return await self._client.send_message(entity, text, **kw)
    async def get_entity(self, x): return await self._client.get_entity(x)
    async def __call__(self, req): return await self._client(req)


async def _connect_with_retry(aid, session_string, name=None, tries=3, per_timeout=35):
    last_err = None
    for i in range(tries):
        cli = None
        try:
            cli = SafeSoroushClient(aid, session_string, name=name, use_lock=False)
            await asyncio.wait_for(cli.__aenter__(), timeout=per_timeout)
            return cli, None
        except asyncio.TimeoutError:
            last_err = f"TimeoutError (#{i+1}/{tries})"
            flog(f"[connect] {aid}: timeout {i+1}", "warning")
            try:
                if cli: await cli._disconnect()
            except Exception: pass
            await asyncio.sleep(2 + i)
        except asyncio.CancelledError:
            try:
                if cli: await cli._disconnect()
            except Exception: pass
            raise
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:120]}"
            flog(f"[connect] {aid}: {last_err}", "warning")
            try:
                if cli: await cli._disconnect()
            except Exception: pass
            await asyncio.sleep(2 + i)
    return None, last_err


# ═══════════════ PATHS / GLOBAL STATE ═══════════════
ACC_FILE       = os.path.join(SOROOSH_DIR, "accounts.json")
CFG_FILE       = os.path.join(SOROOSH_DIR, "config.json")
QUEUE_FILE     = os.path.join(SOROOSH_DIR, "queue.json")
ERRORS_FILE    = os.path.join(SOROOSH_DIR, "errors.json")
OPS_FILE       = os.path.join(SOROOSH_DIR, "ops.json")
TEMPLATES_FILE = os.path.join(SOROOSH_DIR, "templates.json")

_STATS_CACHE: Dict[str, Dict[str, Any]] = {}
_STATS_CACHE_TTL = 300

STATE: Dict[str, Any] = {
    "owner": None, "panel": {}, "conv": {},
    "listener_stops": {}, "op_panel": {}, "listener_new_count": 0,
}

_PAGE_STATE: Dict[int, str] = {}

def _set_page(cid, tag):
    try: _PAGE_STATE[int(cid)] = str(tag)
    except Exception: pass

def _is_page(cid, tag):
    try: return _PAGE_STATE.get(int(cid)) == tag
    except Exception: return False

_loop_ref: List[Optional[asyncio.AbstractEventLoop]] = [None]
TG_TOKEN: str = ""
APP = None

DEFAULT_CFG: Dict[str, Any] = {
    "listener": 1, "auto_join_linkdoni": 1,
    "wave_size": 50, "extract_limit": 300, "join_delay": 0.5,
    "deep_scan_pages": 30, "deep_scan_page_size": 100,
    "wait_for_links_sec": 90, "max_wait_rounds": 20,
}

def _load_errors() -> List[Dict[str, Any]]:
    d = _load(ERRORS_FILE, [])
    return d if isinstance(d, list) else []

def add_error(source: str, error: str, target: Any = None, account: Any = None):
    errs = _load_errors()
    errs.append({"time": int(time.time()), "source": str(source)[:40], "error": str(error)[:300],
                 "target": (str(target)[:120] if target is not None else None),
                 "account": (str(account)[:60] if account is not None else None)})
    if len(errs) > 500: errs = errs[-500:]
    try: _save(ERRORS_FILE, errs)
    except Exception: pass

def clear_errors():
    try: _save(ERRORS_FILE, [])
    except Exception: pass

def list_accounts(): return _load(ACC_FILE, {})
def save_accounts(a): _save(ACC_FILE, a)
def get_account(aid): return list_accounts().get(aid)

def add_account(aid, phone, name, session_string, user_id=None):
    accounts = list_accounts()
    accounts[aid] = {"phone": phone, "name": name, "session_string": session_string,
                     "user_id": user_id, "created": int(time.time()), "channels": []}
    save_accounts(accounts); return accounts[aid]

def remove_account(aid):
    accounts = list_accounts(); accounts.pop(aid, None); save_accounts(accounts)
    _STATS_CACHE.pop(aid, None)

def get_stored_channels(aid: str) -> List[Dict[str, Any]]:
    a = get_account(aid)
    return list(a.get("channels") or []) if a else []

def get_own_channel_ids(aid: str) -> Set[int]:
    out: Set[int] = set()
    try:
        for ch in get_stored_channels(aid):
            for k in ("id", "raw_id"):
                cid = ch.get(k)
                if cid is not None:
                    try: out.add(int(cid))
                    except Exception: pass
    except Exception: pass
    return out

def add_channel_to_storage(aid: str, ch_data: Dict[str, Any]):
    accounts = list_accounts()
    if aid not in accounts: return
    chans = accounts[aid].setdefault("channels", [])
    guid = ch_data.get("guid")
    if guid:
        for c in chans:
            if c.get("guid") == guid:
                c.update(ch_data); save_accounts(accounts); return
    chans.append(ch_data); save_accounts(accounts)

def remove_channel_from_storage(aid: str, idx: int):
    accounts = list_accounts()
    if aid not in accounts: return None
    chans = accounts[aid].get("channels") or []
    if idx < 0 or idx >= len(chans): return None
    removed = chans.pop(idx); accounts[aid]["channels"] = chans
    save_accounts(accounts); return removed

def update_channel_field(aid: str, idx: int, key: str, value):
    accounts = list_accounts()
    if aid not in accounts: return
    chans = accounts[aid].get("channels") or []
    if 0 <= idx < len(chans): chans[idx][key] = value; save_accounts(accounts)

def _channel_data_from_obj(ch_obj) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if ch_obj is None: return out
    def g(*keys):
        for k in keys:
            if isinstance(ch_obj, dict) and k in ch_obj and ch_obj[k] is not None: return ch_obj[k]
            v = getattr(ch_obj, k, None)
            if v is not None: return v
        return None
    cid = g("id", "channel_id", "chat_id")
    if cid is not None:
        try:
            cid_i = int(cid)
            out["id"] = cid_i
            out["guid"] = "c" + str(cid_i)
            if cid_i < 0:
                s = str(cid_i)
                if s.startswith("-100"): out["raw_id"] = int(s[4:])
                else: out["raw_id"] = abs(cid_i)
            else:
                out["raw_id"] = cid_i
        except Exception: pass
    ah = g("access_hash", "accessHash", "hash")
    if ah is not None:
        try: out["access_hash"] = str(int(ah))
        except Exception: out["access_hash"] = str(ah)
    t = g("title", "name")
    if t: out["title"] = str(t)
    u = g("username", "user_name", "uname")
    if u: out["username"] = str(u).lstrip("@")
    for lk in ("invite_link", "inviteLink", "join_link", "joinLink"):
        v = g(lk)
        if isinstance(v, str) and v.strip(): out["join_link"] = v.strip(); break
        if hasattr(v, "link"):
            l2 = getattr(v, "link", None)
            if isinstance(l2, str) and l2.strip(): out["join_link"] = l2.strip(); break
    return out


async def _resolve_channel_entity(cli, ch: Dict[str, Any], aid: str = None):
    tried: List[str] = []
    cid = ch.get("id"); ah = ch.get("access_hash"); raw_id = ch.get("raw_id")
    try: cid_int = int(cid) if cid is not None else None
    except Exception: cid_int = None
    try: raw_int = int(raw_id) if raw_id is not None else None
    except Exception: raw_int = None

    if cid_int is not None and ah and InputChannel is not None:
        candidates = []
        if cid_int: candidates.append(cid_int)
        if raw_int and raw_int != cid_int: candidates.append(raw_int)
        try:
            if cid_int and abs(cid_int) not in candidates: candidates.append(abs(cid_int))
        except Exception: pass
        for cand in candidates:
            try:
                inp = InputChannel(cand, int(ah))
                return inp, f"ic_raw:{cand}"
            except Exception as e:
                tried.append(f"ic_raw:{cand}:{type(e).__name__}"); continue

    try:
        dialogs = await cli.get_dialogs()
        if cid_int is not None:
            for d in dialogs or []:
                d_id = getattr(d, "id", None)
                match = False
                if d_id == cid_int: match = True
                elif raw_int is not None and d_id == raw_int: match = True
                elif d_id is not None and cid_int is not None:
                    try:
                        if abs(int(d_id)) == abs(int(cid_int)): match = True
                    except Exception: pass
                if match:
                    ent = getattr(d, "entity", None)
                    if ent is not None:
                        ah_new = getattr(ent, "access_hash", None)
                        if ah_new is not None and aid:
                            try:
                                accounts = list_accounts()
                                if aid in accounts:
                                    for c in accounts[aid].get("channels") or []:
                                        if c.get("id") == cid_int:
                                            c["access_hash"] = str(ah_new); save_accounts(accounts); break
                            except Exception: pass
                        return ent, "dialog_id"
        title = (ch.get("title") or "").strip()
        if title:
            for d in dialogs or []:
                ent = getattr(d, "entity", None)
                if ent is None: continue
                t2 = (getattr(ent, "title", None) or getattr(d, "name", None) or getattr(d, "title", None) or "")
                if t2 == title: return ent, "dialog_by_title"
    except Exception as e:
        tried.append(f"dialogs:{type(e).__name__}")

    un = (ch.get("username") or "").lstrip("@").strip()
    if un:
        for t in (un, "@" + un):
            try:
                ent = await cli.get_entity(t)
                if ent: return ent, f"username:{t}"
            except Exception as e: tried.append(f"un:{t}:{type(e).__name__}")

    if cid_int is not None:
        formats = []
        if cid_int > 0:
            formats = [cid_int, -cid_int, int(f"-100{cid_int}")]
        else:
            abs_id = abs(cid_int); s = str(abs_id)
            if s.startswith("100") and len(s) > 10:
                raw = int(s[3:]); formats = [cid_int, raw, -raw, int(f"-100{raw}")]
            else:
                formats = [cid_int, abs_id, int(f"-100{abs_id}")]
        formats += [str(cid_int), f"-100{cid_int}" if cid_int > 0 else str(cid_int)]
        seen_f = set()
        for fmt in formats:
            key = str(fmt)
            if key in seen_f: continue
            seen_f.add(key)
            try:
                ent = await cli.get_entity(fmt)
                if ent: return ent, f"ge:{fmt}"
            except Exception as e:
                tried.append(f"ge:{fmt}:{type(e).__name__}")

    if cid_int is not None and ah and InputChannel is not None and GetFullChannelRequest:
        for cand in ([cid_int, raw_int, abs(cid_int)]):
            if cand is None: continue
            try:
                inp = InputChannel(cand, int(ah))
                full = cli(GetFullChannelRequest(channel=inp))
                if asyncio.iscoroutine(full): full = await full
                if full: return inp, f"ic_verify:{cand}"
            except Exception as e: tried.append(f"ic_v:{cand}:{type(e).__name__}")

    g = ch.get("guid")
    if g:
        for t in (g, str(g).lstrip("c")):
            try:
                ent = await cli.get_entity(t)
                if ent: return ent, f"guid:{t}"
            except Exception as e: tried.append(f"g:{t}:{type(e).__name__}")

    return None, "|".join(tried[-8:]) if tried else "no_strategy"


async def send_to_channel(aid: str, idx: int, text: str):
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return False, "کانال نیست"
    a = get_account(aid)
    if not a: return False, "اکانت نیست"
    cli = None
    try:
        cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=2)
        if cli is None: return False, f"اتصال ناموفق: {err}"
        ent, method = await _resolve_channel_entity(cli, channels[idx], aid)
        if not ent: return False, f"resolve نشد · {method[:150]}"
        r = cli.send_message(ent, text)
        if asyncio.iscoroutine(r): r = await r
        return True, f"OK · {method}"
    except Exception as e:
        return False, f"{type(e).__name__}: {_fmt_error(e)}"
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass


async def export_invite_link(aid: str, idx: int):
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return False, "کانال نیست"
    a = get_account(aid)
    if not a: return False, "اکانت نیست"
    ch = channels[idx]
    cli = None; last_errs: List[str] = []
    try:
        cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=2)
        if cli is None: return False, f"اتصال ناموفق: {err}"
        ent, method = await _resolve_channel_entity(cli, ch, aid)
        if not ent: return False, f"resolve نشد · {method[:150]}"
        for attr in ("invite_link", "inviteLink", "link", "join_link", "joinLink",
                     "chat_invite", "exported_invite", "exportedInvite"):
            try:
                v = getattr(ent, attr, None)
                if v:
                    if hasattr(v, "link"): v = v.link
                    if isinstance(v, str) and v.strip():
                        update_channel_field(aid, idx, "join_link", v); return True, v
            except Exception: pass
        if GetFullChannelRequest:
            try:
                full = cli(GetFullChannelRequest(channel=ent))
                if asyncio.iscoroutine(full): full = await full
                fc = getattr(full, "full_chat", None) or getattr(full, "fullChat", None)
                if fc is None:
                    chats = getattr(full, "chats", None) or []
                    if chats: fc = chats[0]
                if fc:
                    for attr in ("exported_invite", "exportedInvite", "invite_link",
                                 "inviteLink", "link", "chat_invite"):
                        v = getattr(fc, attr, None)
                        if v:
                            if hasattr(v, "link"): v = v.link
                            if isinstance(v, str) and v.strip():
                                update_channel_field(aid, idx, "join_link", v); return True, v
            except Exception as e: last_errs.append(f"full:{type(e).__name__}")
        cid_int = ch.get("id")
        if cid_int:
            try:
                dialogs = await cli.get_dialogs()
                for d in dialogs or []:
                    if getattr(d, "id", None) == int(cid_int):
                        for attr in ("invite_link", "inviteLink", "link", "username"):
                            v = getattr(d, attr, None)
                            if isinstance(v, str) and v.strip():
                                link = v if v.startswith("http") else (f"https://splus.ir/{v.lstrip('@')}" if attr == "username" else v)
                                update_channel_field(aid, idx, "join_link", link); return True, link
                        break
            except Exception: pass
        un = (ch.get("username") or getattr(ent, "username", None) or "").lstrip("@").strip()
        if un:
            link = f"https://splus.ir/{un}"
            update_channel_field(aid, idx, "join_link", link); return True, link
        if ExportChatInviteRequest:
            peers: List[Any] = []
            ah = ch.get("access_hash")
            try: cid_int2 = int(ch["id"]) if ch.get("id") else None
            except Exception: cid_int2 = None
            if InputPeerChannel is not None and cid_int2 is not None and ah:
                try: peers.append(InputPeerChannel(cid_int2, int(ah)))
                except Exception: pass
            if InputChannel is not None and cid_int2 is not None and ah:
                try: peers.append(InputChannel(cid_int2, int(ah)))
                except Exception: pass
            if ent: peers.append(ent)
            seen_p = set(); uniq = []
            for p in peers:
                pid = id(p)
                if pid in seen_p: continue
                seen_p.add(pid); uniq.append(p)
            for p in uniq:
                for kw in ({"peer": p}, {"peer": p, "request_needed": False},
                           {"peer": p, "legacy_revoke_permanent": False}):
                    try:
                        r = cli(ExportChatInviteRequest(**kw))
                        if asyncio.iscoroutine(r): r = await r
                        link = getattr(r, "link", None)
                        if not link and isinstance(r, dict): link = r.get("link")
                        if link:
                            update_channel_field(aid, idx, "join_link", str(link)); return True, str(link)
                    except TypeError: continue
                    except Exception as e:
                        last_errs.append(type(e).__name__)
                        if "NOT_SUPPORTED" in str(e).upper(): break
                        continue
                    break
        return False, "لینک قابل دریافت نیست · " + " | ".join(last_errs[-3:])
    except Exception as e:
        return False, f"{type(e).__name__}: {_fmt_error(e)}"
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass


async def diagnose_channel(aid: str, idx: int) -> str:
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return "کانال نیست"
    ch = channels[idx]
    lines = ["=== STORED ==="]
    for k, v in ch.items(): lines.append(f"  {k} = {repr(v)[:100]}")
    return "\n".join(lines)

async def _get_full_channel_info(cli, ch: Dict[str, Any], aid: str = None) -> Dict[str, Any]:
    out = {"title": ch.get("title") or "", "username": ch.get("username") or "",
           "description": ch.get("description") or "", "id": ch.get("id"),
           "members": None, "join_link": ch.get("join_link") or ""}
    ent, method = await _resolve_channel_entity(cli, ch, aid)
    if not ent:
        out["error"] = f"resolve نشد: {method[:100]}"; return out
    if GetFullChannelRequest:
        try:
            full = cli(GetFullChannelRequest(channel=ent))
            if asyncio.iscoroutine(full): full = await full
            if full:
                for k in ("full_chat", "fullChat", "chats"):
                    fc = getattr(full, k, None)
                    if fc:
                        if isinstance(fc, list) and fc: fc = fc[0]
                        for fkey in ("about", "description"):
                            v = getattr(fc, fkey, None)
                            if v: out["description"] = str(v)
                        mc = getattr(fc, "participants_count", None)
                        if mc is not None: out["members"] = int(mc)
                        break
        except Exception: pass
    for k in ("title", "name"):
        v = getattr(ent, k, None)
        if v: out["title"] = str(v); break
    v = getattr(ent, "username", None)
    if v: out["username"] = str(v).lstrip("@")
    return out

async def edit_channel_title(aid, idx, new_title): return False, "غیرفعال"
async def edit_channel_about(aid, idx, new_about): return False, "غیرفعال"
async def edit_channel_username(aid, idx, new_username): return False, "غیرفعال"

async def get_account_stats(aid: str, force: bool = False) -> Dict[str, Any]:
    now = time.time()
    c = _STATS_CACHE.get(aid)
    if c and not force and (now - c["ts"]) < _STATS_CACHE_TTL: return c["data"]
    acc = get_account(aid)
    if not acc: return {"groups": 0, "pvs": 0, "channels": 0, "bots": 0, "total": 0, "error": "اکانت نیست"}
    stats = {"groups": 0, "pvs": 0, "channels": 0, "bots": 0, "total": 0}
    cli = None
    try:
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=acc.get("name"), tries=2)
        if cli is None: return {**stats, "error": f"connect: {err}"}
        try: me = await cli.get_me(); my_id = me.id
        except Exception: my_id = None
        try: dialogs = await cli.get_dialogs()
        except Exception: return {**stats, "error": "dialogs fail"}
        for d in dialogs or []:
            try:
                is_user = getattr(d, "is_user", False); is_group = getattr(d, "is_group", False)
                is_channel = getattr(d, "is_channel", False); is_bot = getattr(d, "is_bot", False)
                eid = getattr(d, "id", None)
                if is_user and my_id and eid == my_id: continue
                if is_user and is_bot: stats["bots"] += 1
                elif is_user: stats["pvs"] += 1
                elif is_group: stats["groups"] += 1
                elif is_channel: stats["channels"] += 1
                stats["total"] += 1
            except Exception: continue
    except Exception: pass
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass
    _STATS_CACHE[aid] = {"ts": now, "data": stats}; return stats


# ═══════════════ LOGIN ═══════════════
_LOGIN_TMP: Dict[str, Dict[str, Any]] = {}

async def soroosh_send_code(phone_raw):
    ensure_soroosh_loop()
    phone = normalize_phone(phone_raw)
    fut = asyncio.run_coroutine_threadsafe(_do_send_code(phone), _soroosh_loop)
    return fut.result(timeout=90)

async def _do_send_code(phone):
    cli = SoroushClient(StringSession())
    try: await cli.connect()
    except Exception as e: return {"ok": False, "status": f"CONNECT_FAIL: {_fmt_error(e)}"}
    last_err = "unknown"
    for variant in (f"+{phone}", phone):
        try:
            result = await cli.send_code_request(variant)
            h = getattr(result, "phone_code_hash", None)
            _LOGIN_TMP[phone] = {"cli": cli, "hash": h, "variant": variant}
            return {"ok": True, "phone": phone, "variant": variant, "phone_code_hash": h, "status": "SendCode"}
        except Exception as e:
            last_err = f"{type(e).__name__}: {_fmt_error(e)}"; continue
    try: await cli.disconnect()
    except Exception: pass
    return {"ok": False, "status": last_err}

async def soroosh_complete_login(phone_raw, code):
    ensure_soroosh_loop()
    phone = normalize_phone(phone_raw)
    fut = asyncio.run_coroutine_threadsafe(_do_complete_login(phone, code), _soroosh_loop)
    return fut.result(timeout=120)

async def _do_complete_login(phone, code):
    entry = _LOGIN_TMP.get(phone)
    if not entry: return {"ok": False, "status": "no_send_code"}
    cli = entry["cli"]; hash_ = entry.get("hash"); variant = entry.get("variant") or f"+{phone}"
    errors = []; me = None; used_method = ""; unoccupied = False
    for tag, fn in [("sign_in", lambda: cli.sign_in(phone=variant, code=code, phone_code_hash=hash_)),
                    ("sign_in2", lambda: cli.sign_in(code=code, phone_code_hash=hash_))]:
        try:
            r = fn()
            if asyncio.iscoroutine(r): r = await r
            me = await cli.get_me(); used_method = tag; break
        except Exception as e:
            emsg = _fmt_error(e); errors.append(f"{tag}: {type(e).__name__}: {emsg}")
            if "Unoccupied" in type(e).__name__ or "UNOCCUPIED" in emsg.upper():
                unoccupied = True; break
    if unoccupied and me is None:
        try:
            r = cli.sign_up(phone=variant, code=code, first_name="کاربر", last_name="سروش", phone_code_hash=hash_)
            if asyncio.iscoroutine(r): r = await r
            me = await cli.get_me(); used_method = "sign_up"
        except Exception as e: errors.append(f"sign_up: {type(e).__name__}")
    if me is not None:
        try:
            sess = cli.session.save()
            name = (f"{me.first_name or ''} {me.last_name or ''}").strip() or phone
            aid = "sr_" + secrets.token_hex(4)
            add_account(aid, phone, name, sess, getattr(me, "id", None))
            _LOGIN_TMP.pop(phone, None)
            try: await cli.disconnect()
            except Exception: pass
            return {"ok": True, "aid": aid, "name": name, "method": used_method}
        except Exception as e: errors.append(f"save: {type(e).__name__}")
    try: await cli.disconnect()
    except Exception: pass
    _LOGIN_TMP.pop(phone, None)
    if unoccupied: return {"ok": False, "need_signup": True, "phone": phone}
    return {"ok": False, "status": " | ".join(errors[:4])}

async def soroosh_update_profile(cli, first_name=None, last_name=None, about=None):
    try:
        kwargs = {}
        if first_name is not None: kwargs["first_name"] = first_name
        if last_name is not None: kwargs["last_name"] = last_name
        if about is not None: kwargs["about"] = about
        if not kwargs: return False, "چیزی نداد"
        r = cli(UpdateProfileRequest(**kwargs))
        if asyncio.iscoroutine(r): r = await r
        return True, "OK"
    except Exception as e: return False, f"{type(e).__name__}: {_fmt_error(e)}"

async def soroosh_update_username(cli, new_username):
    try:
        uname = new_username.lstrip("@").strip()
        r = cli(UpdateUsernameRequest(username=uname))
        if asyncio.iscoroutine(r): r = await r
        return True, f"@{uname}"
    except Exception as e: return False, f"{type(e).__name__}: {_fmt_error(e)}"

async def soroosh_create_channel(cli, title, about=None):
    if CreateChannelRequest is None: return False, None, "CreateChannelRequest نیست"
    last_err = None
    for kwargs in (
        {"title": title, "about": about or "", "broadcast": True, "megagroup": False},
        {"title": title, "about": about or "", "broadcast": True},
        {"title": title, "about": about or ""},
        {"title": title, "broadcast": True, "megagroup": False},
        {"title": title, "megagroup": False},
    ):
        try:
            r = cli(CreateChannelRequest(**kwargs))
            if asyncio.iscoroutine(r): r = await r
            channel = None
            try:
                upd = getattr(r, "updates", None) or r
                chats = getattr(upd, "chats", None) or []
                for c in chats:
                    if getattr(c, "title", None) == title: channel = c; break
                if channel is None and chats: channel = chats[0]
            except Exception: pass
            ah_now = getattr(channel, "access_hash", None) if channel is not None else None
            cid_now = getattr(channel, "id", None) if channel is not None else None
            if (channel is None) or (ah_now is None) or (cid_now is None):
                try:
                    await asyncio.sleep(1.0)
                    dialogs = await cli.get_dialogs()
                    for d in dialogs or []:
                        ent = getattr(d, "entity", None)
                        d_id = getattr(d, "id", None)
                        d_title = (getattr(ent, "title", None) or getattr(d, "name", None) or getattr(d, "title", None) or "")
                        if cid_now is not None and d_id == cid_now and ent is not None:
                            channel = ent; break
                        if cid_now is None and d_title == title and ent is not None:
                            channel = ent; break
                except Exception: pass
            if channel is not None and getattr(channel, "access_hash", None) is None:
                try:
                    await asyncio.sleep(2.0)
                    dialogs = await cli.get_dialogs()
                    for d in dialogs or []:
                        ent = getattr(d, "entity", None)
                        t = (getattr(ent, "title", None) or getattr(d, "name", None) or getattr(d, "title", None) or "")
                        if t == title and ent is not None:
                            channel = ent; break
                except Exception: pass
            return True, channel, "created"
        except TypeError as e:
            last_err = e; continue
        except Exception as e:
            return False, None, f"{type(e).__name__}: {_fmt_error(e)}"
    return False, None, f"TypeError: {last_err}"


# ═══════════════ ACTIVE CHECK ═══════════════
async def _is_group_active(cli, entity) -> Tuple[bool, str]:
    if entity is None: return False, "no_entity"
    try:
        br = getattr(entity, "banned_rights", None)
        if br and getattr(br, "send_messages", False): return False, "banned_send"
        dbr = getattr(entity, "default_banned_rights", None)
        if dbr and getattr(dbr, "send_messages", False): return False, "default_banned_send"
        if getattr(entity, "left", False): return False, "left"
        if getattr(entity, "kicked", False): return False, "kicked"
        if getattr(entity, "deactivated", False): return False, "deactivated"
        if GetFullChannelRequest:
            try:
                full = cli(GetFullChannelRequest(channel=entity))
                if asyncio.iscoroutine(full): full = await full
                fc = getattr(full, "full_chat", None) or getattr(full, "fullChat", None)
                if fc is None:
                    chats = getattr(full, "chats", None) or []
                    if chats: fc = chats[0]
                if fc:
                    br2 = getattr(fc, "banned_rights", None)
                    if br2 and getattr(br2, "send_messages", False): return False, "full_banned"
                    dbr2 = getattr(fc, "default_banned_rights", None)
                    if dbr2 and getattr(dbr2, "send_messages", False): return False, "full_default_banned"
            except Exception:
                return True, "check_failed_but_ok"
        return True, "ok"
    except Exception as e:
        return True, f"exc:{type(e).__name__}"

async def _check_link_type(cli, link: str) -> Tuple[str, Any]:
    is_private = ("/joinchat/" in link) or ("/joingroup/" in link)
    if is_private:
        h = link.rstrip("/").split("/")[-1]
        if CheckChatInviteRequest is not None:
            try:
                info = cli(CheckChatInviteRequest(h))
                if asyncio.iscoroutine(info): info = await info
                chat = getattr(info, "chat", None)
                if chat is not None:
                    bc = getattr(chat, "broadcast", False)
                    mg = getattr(chat, "megagroup", False)
                    if bc and not mg: return "channel", chat
                    elif mg or not bc: return "group", chat
            except Exception: pass
        return "unknown", None
    else:
        uname = link.replace("@", "").strip()
        try:
            ent = await cli.get_entity(uname)
            if ent is not None:
                bc = getattr(ent, "broadcast", False)
                mg = getattr(ent, "megagroup", False)
                if bc and not mg: return "channel", ent
                elif mg or not bc: return "group", ent
        except Exception: pass
        return "unknown", None


# ═══════════════ SEND HELPERS ═══════════════
async def _do_edit_msg(cli, entity, mid, new_text):
    try:
        em = getattr(cli, "edit_message", None)
        if em:
            rr = em(entity, mid, new_text)
            if asyncio.iscoroutine(rr): rr = await rr
            return True, None
    except Exception as e:
        last_err = f"helper:{type(e).__name__}"
    else:
        last_err = ""
    if EditMessageRequest is not None:
        for kw in ({"peer": entity, "id": mid, "message": new_text},
                   {"peer": entity, "id": mid, "message": new_text, "no_webpage": True}):
            try:
                rr = cli(EditMessageRequest(**kw))
                if asyncio.iscoroutine(rr): rr = await rr
                return True, None
            except TypeError as te:
                last_err = f"TypeErr:{te}"; continue
            except Exception as e:
                last_err = f"{type(e).__name__}"; continue
    for mname in ("edit_message", "edit_message_text"):
        fn = getattr(cli, mname, None)
        if not fn: continue
        for kw in ({"entity": entity, "message_id": mid, "text": new_text},
                   {"peer": entity, "id": mid, "text": new_text}):
            try:
                rr = fn(**kw)
                if asyncio.iscoroutine(rr): rr = await rr
                return True, None
            except TypeError: continue
            except Exception as e:
                last_err = f"{mname}:{type(e).__name__}"; continue
    return False, last_err

async def _send_with_edit_delay(cli, entity, real_text: str, placeholder: str = "سلام",
                                edit_delay: float = 3.0, log=None, placeholder_list: str = "",
                                delay_random: bool = False, delay_min: float = 2.0, delay_max: float = 6.0,
                                multi_step: bool = False, multi_middle: str = "Hi"):
    if not real_text: return False, "empty_text"
    if placeholder_list and placeholder_list.strip():
        opts = [p.strip() for p in placeholder_list.split(",") if p.strip()]
        if opts: placeholder = random.choice(opts)
    if delay_random:
        try:
            d1 = max(0.0, float(delay_min)); d2 = max(d1, float(delay_max))
            edit_delay = random.uniform(d1, d2)
        except Exception: pass
    if edit_delay <= 0 or placeholder == real_text:
        try:
            r = cli.send_message(entity, real_text)
            if asyncio.iscoroutine(r): r = await r
            return True, None
        except FloodWaitError as fe: return False, f"Flood {fe.seconds}s"
        except Exception as e: return False, f"send:{type(e).__name__}: {_fmt_error(e)}"
    msg_obj = None
    try:
        r = cli.send_message(entity, placeholder)
        if asyncio.iscoroutine(r): r = await r
        msg_obj = r
    except FloodWaitError as fe: return False, f"Flood {fe.seconds}s"
    except Exception as e: return False, f"send:{type(e).__name__}: {_fmt_error(e)}"
    def _find_mid(mo):
        if mo is None: return None
        try:
            mid = getattr(mo, "id", None)
            if mid is not None: return mid
        except Exception: pass
        try:
            upd = getattr(mo, "updates", None) or mo
            msgs = getattr(upd, "updates", None) or getattr(upd, "messages", None) or []
            for m in msgs:
                mid = getattr(m, "id", None)
                if mid is not None: return mid
        except Exception: pass
        return None
    msg_id = _find_mid(msg_obj)
    if msg_id is None: return True, "no_msg_id"
    try: await asyncio.sleep(edit_delay)
    except asyncio.CancelledError: raise
    if multi_step and multi_middle and multi_middle != real_text:
        _ok, _err = await _do_edit_msg(cli, entity, msg_id, multi_middle)
        try: await asyncio.sleep(max(0.8, edit_delay / 2))
        except asyncio.CancelledError: raise
    edit_ok, edit_err = await _do_edit_msg(cli, entity, msg_id, real_text)
    if edit_ok:
        if log: flog(f"[edit-delay] OK — msg={msg_id} delay={edit_delay:.1f}s")
        return True, None
    if log: flog(f"[edit-delay] FAILED: {edit_err[:120]}", "warning")
    return True, f"edit_failed:{edit_err[:80]}"

async def _send_to_entity(cli, entity, text, snd_cfg: Dict[str, Any], log=None):
    use_edit = bool(snd_cfg.get("edit_delay_enabled", False))
    if use_edit:
        return await _send_with_edit_delay(cli, entity, text,
            placeholder=snd_cfg.get("placeholder_text", "سلام") or "سلام",
            edit_delay=float(snd_cfg.get("edit_delay_seconds", 3.0)), log=log,
            placeholder_list=snd_cfg.get("placeholder_list", "") if snd_cfg.get("placeholder_random") else "",
            delay_random=bool(snd_cfg.get("edit_delay_random", False)),
            delay_min=float(snd_cfg.get("edit_delay_min", 2.0)),
            delay_max=float(snd_cfg.get("edit_delay_max", 6.0)),
            multi_step=bool(snd_cfg.get("multi_step_edit", False)),
            multi_middle=snd_cfg.get("multi_step_middle", "Hi") or "Hi")
    else:
        try:
            r = cli.send_message(entity, text)
            if asyncio.iscoroutine(r): r = await r
            return True, None
        except FloodWaitError as fe: return False, f"Flood {fe.seconds}s"
        except Exception as e:
            err_s = str(e).upper()
            if "USER_SUSPENDED" in err_s:
                raise RuntimeError("ACCOUNT_SUSPENDED")
            if "FORBIDDEN" in err_s or "CHAT_WRITE_FORBIDDEN" in err_s:
                return False, f"BLOCKED:{_fmt_error(e)[:100]}"
            return False, f"{type(e).__name__}: {_fmt_error(e)}"

async def _set_personal_channel(cli, pub_ent) -> Tuple[bool, str]:
    if UpdatePersonalChannelRequest is None: return False, "API_not_available"
    if pub_ent is None: return False, "no_entity"
    last_err = "unknown"
    try:
        for kw in ({"channel": pub_ent, "peer": pub_ent}, {"peer": pub_ent}, {"channel": pub_ent}):
            try:
                r = cli(UpdatePersonalChannelRequest(**kw))
                if asyncio.iscoroutine(r): r = await r
                return True, "OK"
            except TypeError: continue
            except Exception as e:
                err = str(e).upper()
                if "NOT_IMPLEMENTED" in err or "NOT_SUPPORTED" in err or "UNKNOWN" in err:
                    return False, f"unsupported:{_fmt_error(e)[:80]}"
                last_err = _fmt_error(e); continue
        return False, f"all_failed:{last_err[:80]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {_fmt_error(e)[:80]}"

def _detect_file_kind(file_path: str) -> str:
    ext = (os.path.splitext(file_path)[1] or "").lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"): return "photo"
    if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"): return "video"
    return "document"


async def _send_file_to_entity(cli, entity, file_path: str, caption: str = "") -> Tuple[bool, str]:
    """v27.9.3: ارسال فایل با fallback چند سطحی + لاگ خطای واقعی RPC"""
    if not file_path:
        if caption:
            try:
                r = cli.send_message(entity, caption)
                if asyncio.iscoroutine(r): r = await r
                return True, "text_only"
            except Exception as e:
                return False, f"text:{type(e).__name__}:{_fmt_error(e)[:80]}"
        return False, "no_path"
    if not os.path.exists(file_path):
        return False, f"not_found:{os.path.basename(file_path)}"

    kind = _detect_file_kind(file_path)
    fsize = os.path.getsize(file_path)
    flog(f"[send-file] kind={kind} name={os.path.basename(file_path)} size={fsize}")

    tried: List[str] = []
    details: List[str] = []

    def _log(prefix, e):
        m = _fmt_error(e) or str(e)
        details.append(f"{prefix}={m[:150]}")
        flog(f"[send-file] {prefix} EXC {type(e).__name__}: {m[:300]}", "warning")

    candidates = []
    sf = getattr(cli, "send_file", None)
    if sf: candidates.append(("send_file", sf))
    if kind == "photo":
        sp = getattr(cli, "send_photo", None)
        if sp: candidates.append(("send_photo", sp))
    if kind == "video":
        sv = getattr(cli, "send_video", None)
        if sv: candidates.append(("send_video", sv))
    sd = getattr(cli, "send_document", None)
    if sd: candidates.append(("send_document", sd))

    for name, fn in candidates:
        for kw in ({"caption": caption}, {}):
            try:
                r = fn(entity, file_path, **kw)
                if asyncio.iscoroutine(r): r = await r
                flog(f"[send-file] OK {name}")
                return True, "OK"
            except TypeError:
                tried.append(f"{name}:TypeErr"); continue
            except FloodWaitError as fe:
                return False, f"Flood {fe.seconds}s"
            except Exception as e:
                _log(name, e)
                tried.append(f"{name}:{type(e).__name__}")
                break

    sm = getattr(cli, "send_media", None)
    if sm:
        for kw in ({"caption": caption}, {}):
            try:
                r = sm(entity, file_path, **kw)
                if asyncio.iscoroutine(r): r = await r
                flog("[send-file] OK send_media")
                return True, "OK"
            except TypeError:
                tried.append("sm:TypeErr"); continue
            except FloodWaitError as fe:
                return False, f"Flood {fe.seconds}s"
            except Exception as e:
                _log("send_media", e)
                tried.append(f"sm:{type(e).__name__}")
                break

    try:
        from splusthon.tl.functions.messages import SendMediaRequest
        from splusthon.tl.types import (
            InputMediaUploadedDocument, InputMediaUploadedPhoto,
            DocumentAttributeFilename,
        )
        _IPU = InputPeerUser
        if _IPU is None:
            try:
                from splusthon.tl.types import InputPeerUser as _IPU  # noqa
            except Exception:
                _IPU = None

        raw = getattr(cli, "raw", None) or cli
        peer = None
        try:
            peer = await raw.get_input_entity(entity)
            flog("[send-file] peer= get_input_entity")
        except Exception as pe:
            _log("get_input_entity", pe)
            try:
                eid = getattr(entity, "id", None)
                eah = getattr(entity, "access_hash", None)
                if eid and eah and _IPU is not None:
                    peer = _IPU(int(eid), int(eah))
                    flog("[send-file] peer= InputPeerUser fallback")
            except Exception as e2:
                _log("InputPeerUser", e2)

        if peer is None:
            tried.append("no_peer")
        else:
            uploaded = await raw.upload_file(file_path)
            fname = os.path.basename(file_path); low = fname.lower()
            if kind == "photo":
                media = InputMediaUploadedPhoto(file=uploaded)
            else:
                if   low.endswith((".mp4", ".mov", ".mkv", ".webm")): mime = "video/mp4"
                elif low.endswith((".jpg", ".jpeg")):                   mime = "image/jpeg"
                elif low.endswith(".png"):                              mime = "image/png"
                elif low.endswith(".gif"):                              mime = "image/gif"
                elif low.endswith(".pdf"):                              mime = "application/pdf"
                else:                                                   mime = "application/octet-stream"
                media = InputMediaUploadedDocument(
                    file=uploaded, mime_type=mime,
                    attributes=[DocumentAttributeFilename(file_name=fname)],
                )

            for variant in (
                dict(peer=peer, media=media, message=caption or "",
                     random_id=random.randint(-2**63, 2**63 - 1)),
                dict(peer=peer, media=media, message=caption or "",
                     random_id=random.randint(-2**63, 2**63 - 1),
                     silent=False, background=False, clear_draft=False),
            ):
                try:
                    r = raw(SendMediaRequest(**variant))
                    if asyncio.iscoroutine(r): r = await r
                    flog("[send-file] OK raw SendMediaRequest")
                    return True, "OK"
                except TypeError as te:
                    tried.append(f"rawType:{str(te)[:40]}"); continue
                except Exception as e:
                    _log("raw_SendMedia", e)
                    tried.append(f"raw:{type(e).__name__}"); break
    except ImportError as ie:
        tried.append(f"raw_imp:{ie}")
    except Exception as e:
        _log("raw_block", e)
        tried.append(f"raw_block:{type(e).__name__}")

    if caption:
        try:
            r = cli.send_message(entity, caption)
            if asyncio.iscoroutine(r): r = await r
            flog("[send-file] WARN fallback to text_only")
            return True, "text_only_fallback"
        except Exception as e:
            _log("text_fallback", e)

    err_sum = " | ".join(tried[:6]) if tried else "no_methods"
    detail  = " || ".join(details[:3])
    flog(f"[send-file] FAILED {err_sum}  <-  {detail}", "error")
    return False, f"all_failed:{err_sum} <- {detail[:220]}"


async def soroosh_set_profile_photo(cli, file_path: str) -> Tuple[bool, str]:
    if not os.path.exists(file_path): return False, "فایل پیدا نشد"
    try:
        sp = getattr(cli, "set_profile_photo", None)
        if sp:
            try:
                r = sp(file=file_path)
                if asyncio.iscoroutine(r): r = await r
                return True, "OK"
            except Exception: pass
        if UploadProfilePhotoRequest is not None:
            try:
                up = getattr(cli, "upload_file", None)
                if up:
                    uf = up(file_path)
                    if asyncio.iscoroutine(uf): uf = await uf
                    r = cli(UploadProfilePhotoRequest(file=uf))
                    if asyncio.iscoroutine(r): r = await r
                    return True, "OK"
            except Exception as e:
                return False, f"upload:{type(e).__name__}: {_fmt_error(e)[:80]}"
        return False, "API_not_supported"
    except FloodWaitError as fe: return False, f"Flood {fe.seconds}s"
    except Exception as e: return False, f"{type(e).__name__}: {_fmt_error(e)[:100]}"

async def soroosh_delete_profile_photos(cli) -> Tuple[bool, str]:
    try:
        dp = getattr(cli, "delete_profile_photos", None)
        if dp:
            try:
                r = dp()
                if asyncio.iscoroutine(r): r = await r
                return True, "OK"
            except Exception: pass
        try:
            photos = []
            gp = getattr(cli, "get_profile_photos", None)
            if gp:
                pf = gp()
                if asyncio.iscoroutine(pf): pf = await pf
                photos = getattr(pf, "photos", None) or pf or []
            if photos and DeletePhotosRequest is not None and InputPhoto is not None:
                ids = []
                for p in photos[:50]:
                    try:
                        aid_obj = getattr(p, "id", None); ah = getattr(p, "access_hash", None)
                        if aid_obj and ah: ids.append(InputPhoto(aid_obj, ah, b""))
                    except Exception: continue
                if ids:
                    r = cli(DeletePhotosRequest(id=ids))
                    if asyncio.iscoroutine(r): r = await r
                    return True, f"deleted:{len(ids)}"
            return False, "no_photos_or_api"
        except Exception as e:
            return False, f"manual:{type(e).__name__}: {_fmt_error(e)[:80]}"
    except Exception as e: return False, f"{type(e).__name__}: {_fmt_error(e)[:100]}"

async def soroosh_set_channel_photo(cli, ch_entity, file_path: str) -> Tuple[bool, str]:
    if not os.path.exists(file_path): return False, "فایل پیدا نشد"
    try:
        sc = getattr(cli, "set_chat_photo", None) or getattr(cli, "edit_chat_photo", None)
        if sc:
            try:
                r = sc(ch_entity, file=file_path)
                if asyncio.iscoroutine(r): r = await r
                return True, "OK"
            except TypeError:
                try:
                    r = sc(ch_entity, file_path)
                    if asyncio.iscoroutine(r): r = await r
                    return True, "OK"
                except Exception: pass
            except Exception: pass
        if EditPhotoRequest is not None:
            try:
                up = getattr(cli, "upload_file", None)
                if not up: return False, "no_upload_method"
                uf = up(file_path)
                if asyncio.iscoroutine(uf): uf = await uf
                r = cli(EditPhotoRequest(channel=ch_entity, photo=uf))
                if asyncio.iscoroutine(r): r = await r
                return True, "OK"
            except Exception as e:
                return False, f"edit:{type(e).__name__}: {_fmt_error(e)[:80]}"
        return False, "API_not_supported"
    except FloodWaitError as fe: return False, f"Flood {fe.seconds}s"
    except Exception as e: return False, f"{type(e).__name__}: {_fmt_error(e)[:100]}"

async def soroosh_delete_channel_photos(cli, ch_entity) -> Tuple[bool, str]:
    try:
        sc = getattr(cli, "delete_chat_photo", None) or getattr(cli, "edit_chat_photo", None)
        if sc:
            try:
                r = sc(ch_entity)
                if asyncio.iscoroutine(r): r = await r
                return True, "OK"
            except Exception: pass
        if EditPhotoRequest is not None:
            try:
                if InputPhotoEmpty is not None:
                    r = cli(EditPhotoRequest(channel=ch_entity, photo=InputPhotoEmpty()))
                    if asyncio.iscoroutine(r): r = await r
                    return True, "OK"
            except Exception as e:
                return False, f"edit:{type(e).__name__}: {_fmt_error(e)[:80]}"
        return False, "API_not_supported"
    except Exception as e: return False, f"{type(e).__name__}: {_fmt_error(e)[:100]}"


# ═══════════════ LEFTER ═══════════════
async def _lefter_collect(cli, mode: str = "all", exclude_ids: Set[int] = None) -> List[Dict[str, Any]]:
    exclude_ids = exclude_ids or set()
    out: List[Dict[str, Any]] = []
    try: dialogs = await cli.get_dialogs()
    except Exception: return out
    for d in dialogs or []:
        try:
            if getattr(d, "is_user", False): continue
            is_group = getattr(d, "is_group", False); is_channel = getattr(d, "is_channel", False)
            eid = getattr(d, "id", None)
            if not eid: continue
            try:
                if int(eid) in exclude_ids: continue
                if abs(int(eid)) in exclude_ids: continue
            except Exception: pass
            ent = getattr(d, "entity", None)
            name = getattr(d, "name", None) or getattr(d, "title", None) or str(eid)
            kind = "channel" if (is_channel and not is_group) else "group"
            if mode == "groups" and kind != "group": continue
            if mode == "channels" and kind != "channel": continue
            if mode == "closed" and kind == "group":
                active, _r = await _is_group_active(cli, ent)
                if active: continue
            out.append({"entity": ent, "name": name, "kind": kind, "id": eid})
        except Exception: continue
    return out

async def _lefter_leave_one(cli, target: Dict[str, Any]):
    ent = target.get("entity")
    if ent is None: return False, "no_entity"
    try:
        r = cli(LeaveChannelRequest(ent))
        if asyncio.iscoroutine(r): r = await r
        return True, None
    except Exception as e:
        msg = str(e).upper()
        if "NOT_PARTICIPANT" in msg or "USER_NOT_PARTICIPANT" in msg: return True, "already_left"
        if "BANNED" in msg or "KICKED" in msg or "FORBIDDEN" in msg: return True, "banned_from_group"
        return False, _fmt_error(e)

async def _lefter_worker(aid, acc, op_id, mode, delay, log):
    name = acc.get("name") or acc.get("phone") or aid
    op = _get_op(op_id)
    if not op: return
    lock = _get_op_lock(op_id)
    left = 0; failed = 0
    cli = None

    async def _set_phase(phase):
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["progress"]["phase"] = phase; _save_op(op2)
        await _refresh_op_panel(op_id)

    async def _finish(phase):
        async with lock:
            op2 = _get_op(op_id)
            if op2:
                op2["progress"]["phase"] = phase
                if op2.get("status") == "running": op2["status"] = "done"; op2["finished_at"] = int(time.time())
                _save_op(op2)
        await _refresh_op_panel(op_id)

    async def _live():
        cid = STATE.get("owner")
        if not cid or not _is_page(cid, f"op:{op_id}"): return
        while True:
            try:
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") != "running": return
                if not _is_page(cid, f"op:{op_id}"): return
                await _refresh_op_panel(op_id)
            except asyncio.CancelledError: raise
            except Exception: pass
            await asyncio.sleep(1.5)

    live_task = asyncio.create_task(_live())
    try:
        await _set_phase("🔌 اتصال")
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
        if cli is None:
            await _finish(f"❌ اتصال ناموفق: {err}"); return
        await _set_phase("📋 جمع‌آوری")
        own_ids = get_own_channel_ids(aid)
        targets = await _lefter_collect(cli, mode, exclude_ids=own_ids)
        if not targets: await _finish("✨ چیزی نیست"); return
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["progress"]["total"] = len(targets); _save_op(op2)
        for t in targets:
            async with lock:
                op2 = _get_op(op_id)
                if not op2 or op2.get("status") == "cancelled": await _finish("⛔ لغو"); return
            try:
                ok, err2 = await asyncio.wait_for(_lefter_leave_one(cli, t), timeout=30)
                if ok:
                    left += 1
                    if err2 == "banned_from_group":
                        h = _hash_of("@c" + str(t.get("id", "")))
                        _mark_banned(h, "banned_from_group")
                else:
                    failed += 1; add_error("ترک", err2, t.get("name"), name)
            except Exception as e: failed += 1; add_error("ترک", _fmt_error(e), t.get("name"), name)
            async with lock:
                op2 = _get_op(op_id)
                if op2:
                    op2["progress"]["joined"] = left; op2["progress"]["failed"] = failed
                    op2["progress"]["phase"] = f"🚪 {left}/{len(targets)}"; _save_op(op2)
            if delay > 0: await asyncio.sleep(delay)
        await _finish(f"✅ {left} ترک · {failed} خطا")
    except asyncio.CancelledError: await _finish("⛔ لغو"); raise
    except Exception as e: await _finish(f"❌ {type(e).__name__}")
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass
        live_task.cancel()
        try: await live_task
        except Exception: pass

async def run_lefter(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    op["progress"] = {"joined": 0, "failed": 0, "total": 0, "phase": "شروع"}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(_lefter_worker(aid, a, op["id"],
                     op.get("leave_mode", "all"), float(op.get("delay", 0.8)), log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled", "done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)


# ═══════════════ TEMPLATES ═══════════════
def list_templates() -> Dict[str, Dict[str, Any]]:
    d = _load(TEMPLATES_FILE, {})
    return d if isinstance(d, dict) else {}

def save_templates(t): _save(TEMPLATES_FILE, t)
def get_template(tid): return list_templates().get(tid)

def add_template(tpl):
    ts = list_templates(); ts[tpl["id"]] = tpl; save_templates(ts)

def delete_template(tid):
    ts = list_templates(); ts.pop(tid, None); save_templates(ts)

def update_template(tid, section, field, value):
    ts = list_templates()
    t = ts.get(tid)
    if not t: return
    if section == "meta": t[field] = value
    elif section == "sender_edit": t.setdefault("sender", {})[field] = value
    elif section == "channel_public": t.setdefault("channel", {})[field] = value
    else: t.setdefault(section, {})[field] = value
    save_templates(ts)

def new_template(name: str = "قالب جدید") -> Dict[str, Any]:
    return {
        "id": "tp_" + secrets.token_hex(4), "name": name, "created": int(time.time()),
        "channel": {
            "type": "private", "title": "", "username": "", "about": "",
            "public_for_profile": False,
            "public_title": "", "public_username": "", "public_about": "",
            "set_as_personal": True, "post_to_public": True,
            "post_text": "🎯 کانال اصلی:\n{Link_private}\n\n👤 {Title_private}",
            "photo_file": "",
        },
        "profile": {"first_name": "", "last_name": "", "username": "", "bio": "", "photo_file": ""},
        "joiner": {"max_join": 0, "speed": "fast", "auto_leave_on_fail": True, "groups_only": True},
        "sender": {
            "text": "", "target": "groups", "mode": "send_only",
            "max_send": 0, "delay": 1.5,
            "edit_delay_enabled": False, "edit_delay_seconds": 3.0,
            "edit_delay_random": False, "edit_delay_min": 2.0, "edit_delay_max": 6.0,
            "placeholder_text": "سلام", "placeholder_random": False,
            "placeholder_list": "سلام,درود,hi,salam,خوبی؟,چطوری",
            "multi_step_edit": False, "multi_step_middle": "Hi",
            "send_to_existing": True,
            "attach_file": "", "attach_caption": "",
        },
        "lefter": {"leave_mode": "closed", "after_send": True},
    }

def _substitute(pattern: str, ctx: Dict[str, Any]) -> str:
    if not pattern: return ""
    s = str(pattern)
    for k, v in ctx.items():
        s = s.replace("{" + k + "}", str(v)).replace("{" + k.lower() + "}", str(v)).replace("{" + k.upper() + "}", str(v))
    return s

def _build_ctx() -> Dict[str, Any]:
    now = time.time()
    return {"n": int(now) % 100000, "rnd": str(random.randint(100000, 999999)),
            "rnd4": str(random.randint(1000, 9999)),
            "date": time.strftime("%Y%m%d"), "time": time.strftime("%H%M%S"),
            "Link_channel": "", "Username_channel": "", "Title_channel": "",
            "Link_private": "", "Title_private": "",
            "Link_public": "", "Username_public": "", "Title_public": ""}


# ═══════════════ EXTRACT / JOIN ═══════════════
JL_SPEEDS = [("ultra", "🚀 فوق‌سریع", 0.3), ("fast", "⚡ سریع", 1.0),
             ("normal", "🐢 عادی", 3.0), ("slow", "🛡 امن", 8.0)]
JL_JOBS: Dict[str, asyncio.Task] = {}

def _extract_links_from_text(txt: str) -> List[str]:
    out = []
    if not txt: return out
    for m in re.finditer(r'(?:https?://)?(?:splus\.ir|soroush\.ir)/(?:joinchat|joingroup|join)/([A-Za-z0-9_\-]{15,})', txt, re.I):
        out.append(f"https://splus.ir/joinchat/{m.group(1)}")
    for m in re.finditer(r'(?:https?://)?(?:splus\.ir|soroush\.ir)/([A-Za-z][A-Za-z0-9_]{4,40})(?:[/\s]|$)', txt, re.I):
        u = m.group(1)
        if u.lower() in ("joinchat", "joingroup", "join"): continue
        out.append("@" + u)
    for m in re.finditer(r'(?<![A-Za-z0-9_@])@([A-Za-z][A-Za-z0-9_]{4,40})', txt):
        out.append("@" + m.group(1))
    seen = set(); res = []
    for lk in out:
        k = _hash_of(lk)
        if k and k not in seen: seen.add(k); res.append(lk)
    return res

async def _resolve_entity(cli, ident: str):
    ident = ident.strip()
    if "/joinchat/" in ident or "/joingroup/" in ident:
        return None, ident.rstrip("/").split("/")[-1], "invite"
    if ident.startswith("http"): ident = ident.rstrip("/").split("/")[-1]
    if ident.startswith("@"): ident = ident[1:]
    for name_try in (ident, "@" + ident):
        try:
            ent = await cli.get_entity(name_try)
            if ent: return ent, None, "entity"
        except Exception: continue
    return None, None, "notfound"

async def _auto_join_linkdoni(cli, url: str, log=None) -> bool:
    try:
        ent, inv_hash, kind = await _resolve_entity(cli, url)
        if kind == "invite" and inv_hash:
            try:
                await cli(ImportChatInviteRequest(inv_hash)); await asyncio.sleep(1.0); return True
            except Exception as e:
                if "ALREADY" in str(e).upper(): return True
                return False
        if ent:
            try:
                await cli(JoinChannelRequest(ent)); await asyncio.sleep(1.0); return True
            except Exception as e:
                if "ALREADY" in str(e).upper(): return True
                return False
    except Exception: pass
    return False

async def _extract_from_linkdoni(cli, url: str, limit: int = 300, log=None, deep_scan: bool = False) -> List[str]:
    links: List[str] = []
    try:
        ent, inv_hash, kind = await _resolve_entity(cli, url)
        if kind == "notfound": return []
        auto_join = int(_load(CFG_FILE, DEFAULT_CFG).get("auto_join_linkdoni", 1))
        if auto_join:
            if kind == "invite" and inv_hash:
                try: await cli(ImportChatInviteRequest(inv_hash)); await asyncio.sleep(1.0)
                except Exception: pass
            elif ent:
                try: await cli(JoinChannelRequest(ent)); await asyncio.sleep(1.0)
                except Exception: pass
        if ent is None or kind == "invite":
            ent, _, _ = await _resolve_entity(cli, url)
            if ent is None: return []
        cfg = _load(CFG_FILE, DEFAULT_CFG)
        page_size = int(cfg.get("deep_scan_page_size", 100))
        max_pages = int(cfg.get("deep_scan_pages", 30))
        if not deep_scan:
            last_max = _get_ld_last(url)
            msgs = None
            if last_max > 0:
                try: msgs = await cli.get_messages(ent, limit=limit, min_id=last_max)
                except TypeError: msgs = None
                except Exception: msgs = None
            if msgs is None:
                for kw in ({"limit": limit}, {"limit": min(limit, 100)}):
                    try: msgs = await cli.get_messages(ent, **kw); break
                    except Exception: continue
            if not msgs: return []
            max_seen_id = last_max
            for m in msgs:
                try:
                    mid = getattr(m, "id", None)
                    if mid and int(mid) > max_seen_id: max_seen_id = int(mid)
                except Exception: pass
                txt = getattr(m, "text", None) or getattr(m, "message", None) or ""
                if txt: links.extend(_extract_links_from_text(txt))
            if max_seen_id > last_max: _set_ld_last(url, max_seen_id)
            return links
        offset_id = 0; pages_done = 0; total_msgs = 0
        while pages_done < max_pages:
            pages_done += 1
            msgs = None
            try:
                if offset_id > 0:
                    try: msgs = await cli.get_messages(ent, limit=page_size, offset_id=offset_id)
                    except TypeError: break
                else:
                    msgs = await cli.get_messages(ent, limit=page_size)
            except FloodWaitError as fe:
                await asyncio.sleep(fe.seconds + 1); pages_done -= 1; continue
            except Exception: break
            if not msgs: break
            total_msgs += len(msgs)
            min_id_in_page = None
            for m in msgs:
                try:
                    mid = getattr(m, "id", None)
                    if mid is None: continue
                    mid_i = int(mid)
                    if min_id_in_page is None or mid_i < min_id_in_page: min_id_in_page = mid_i
                except Exception: pass
                txt = getattr(m, "text", None) or getattr(m, "message", None) or ""
                if txt: links.extend(_extract_links_from_text(txt))
            if min_id_in_page is None or min_id_in_page <= 1: break
            if len(msgs) < page_size: break
            offset_id = min_id_in_page
            await asyncio.sleep(0.4)
        return links
    except Exception: pass
    return links

async def _try_join(cli, link):
    is_private = ("/joinchat/" in link) or ("/joingroup/" in link)
    if is_private:
        h = link.rstrip("/").split("/")[-1]
        try:
            r = cli(ImportChatInviteRequest(h))
            if asyncio.iscoroutine(r): r = await r
            entity = None
            try:
                chat_obj = getattr(r, "chat", None)
                if chat_obj is not None and _is_group_or_channel(chat_obj): entity = chat_obj
                else:
                    chats = getattr(r, "chats", None)
                    if chats is None:
                        upd = getattr(r, "updates", None)
                        if upd is not None: chats = getattr(upd, "chats", None)
                    if chats:
                        for c in chats:
                            if _is_group_or_channel(c): entity = c; break
            except Exception: pass
            return True, None, "invite", entity
        except Exception as e:
            msg = str(e).upper()
            if "USER_ALREADY" in msg or "ALREADY" in msg: return True, None, "already", None
            if _is_rate_limit(e): raise
            return False, _fmt_error(e), "invite", None
    else:
        uname = link.replace("@", "").strip()
        try:
            ent = await cli.get_entity(uname)
            if not _is_group_or_channel(ent): return False, "not a group/channel", "username", None
            await cli(JoinChannelRequest(ent))
            return True, None, "username", ent
        except Exception as e:
            msg = str(e).upper()
            if "USER_ALREADY" in msg or "ALREADY" in msg:
                try:
                    ent = await cli.get_entity(uname)
                    if _is_group_or_channel(ent): return True, None, "already", ent
                except Exception: pass
                return True, None, "already", None
            if _is_rate_limit(e): raise
            return False, _fmt_error(e), "username", None


# ═══════════════ OPS ═══════════════
def _load_ops():
    d = _load(OPS_FILE, []); return d if isinstance(d, list) else []

def _save_ops(ops): _save(OPS_FILE, ops)

def _get_op(oid):
    for o in _load_ops():
        if o.get("id") == oid: return o
    return None

def _save_op(op):
    ops = _load_ops()
    for i, o in enumerate(ops):
        if o.get("id") == op["id"]: ops[i] = op; break
    else: ops.append(op)
    _save_ops(ops)

def _get_op_lock(oid):
    key = "oplock_" + oid
    if key not in STATE: STATE[key] = asyncio.Lock()
    return STATE[key]

def _op_stats(op):
    p = op.get("progress") or {}
    t = op.get("type")
    if t in ("joinlef", "lefter"):
        return {"done": p.get("joined", 0), "failed": p.get("failed", 0), "pending": 0,
                "in_progress": 1 if op.get("status") == "running" else 0,
                "total": op.get("max_join", 0) or (p.get("joined", 0) + p.get("failed", 0))}
    if t == "autotar":
        return {"done": p.get("joined", 0), "failed": p.get("failed", 0),
                "pending": p.get("pending", 0), "in_progress": 1 if op.get("status") == "running" else 0,
                "total": p.get("total", 0), "already": p.get("already", 0),
                "sent": p.get("sent", 0), "left": p.get("left", 0),
                "wave": p.get("wave", 0), "tried": p.get("tried", 0),
                "skipped_seen": p.get("skipped_seen", 0),
                "skipped_banned": p.get("skipped_banned", 0), "rejected": p.get("rejected", 0)}
    return {"done": p.get("sent", 0), "failed": p.get("failed", 0),
            "pending": p.get("pending", 0), "in_progress": p.get("in_progress", 0),
            "total": p.get("total", 0), "blocked": p.get("blocked", 0), "round": p.get("round", 0)}

def _op_effective_status(op):
    st = op.get("status", "draft")
    if op.get("type") in ("joinlef", "lefter", "autotar"):
        if st in ("done", "failed", "cancelled", "paused"): return st
        return "running"
    return st

def _op_short_title(op, n=32):
    t = op.get("type")
    if t == "joinlef": return f"🤝 Joiner ({op.get('max_join', 0)})"
    if t == "lefter": return f"🚪 Lefter ({op.get('leave_mode', '?')})"
    if t == "autotar":
        tpl = get_template(op.get("template_id"))
        return f"🎯 {short(tpl.get('name', '?'), 20)}" if tpl else "🎯 AutoTar"
    p = op.get("payload") or {}
    if p.get("text"): return f"📤 «{p.get('text')[:n]}»"
    return "📤 ارسال"

def _op_status_icon(st):
    return {"running": "🟢", "paused": "⏸", "queued": "⏳", "done": "✅",
            "failed": "❌", "cancelled": "⛔", "empty": "⚪", "draft": "📝"}.get(st, "⚪")

def _op_status_label(st):
    return {"running": "در حال اجرا", "paused": "متوقف", "queued": "در صف",
            "done": "تکمیل", "failed": "با خطا", "cancelled": "لغو شده",
            "empty": "خالی", "draft": "پیش‌نویس"}.get(st, "?")

def _op_progress_bar(op):
    s = _op_stats(op); done = s["done"] + s["failed"]; tot = s["total"] or 0
    if tot == 0: return "▱" * 16 + " 0%", 0
    pct = int(done * 100 / tot); fill = int(done * 16 / tot)
    if fill > 16: fill = 16
    return "▰" * fill + "▱" * (16 - fill) + f" {pct}%", pct

async def _collect_targets(cli, target: str, exclude_ids: Set[int] = None, groups_only: bool = False):
    exclude_ids = exclude_ids or set()
    out = []
    try: dialogs = await cli.get_dialogs()
    except Exception: return out
    try: me = await cli.get_me(); my_id = me.id
    except Exception: my_id = None
    for d in dialogs or []:
        try:
            is_user = getattr(d, "is_user", False); is_group = getattr(d, "is_group", False)
            is_channel = getattr(d, "is_channel", False); is_bot = getattr(d, "is_bot", False)
            title = getattr(d, "name", None) or getattr(d, "title", None) or ""
            ent = getattr(d, "entity", None); eid = getattr(d, "id", None)
            if is_user and is_bot: continue
            try:
                if eid is not None and int(eid) in exclude_ids: continue
                if eid is not None and abs(int(eid)) in exclude_ids: continue
            except Exception: pass
            if groups_only and not is_user:
                if not _is_actual_group(ent): continue
            kind = "pv" if is_user else ("groups" if (is_group or is_channel) else None)
            if kind is None: continue
            if is_user and my_id and eid == my_id: continue
            if target == "pv" and kind != "pv": continue
            if target == "groups" and kind != "groups": continue
            out.append({"type": kind, "target": eid, "entity": ent, "name": title or str(eid)})
        except Exception: continue
    return out


# ═══════════════ AUTO-TAR WORKER ═══════════════
async def _auto_tar_worker(aid, acc, op_id, tpl, log):
    name = acc.get("name") or acc.get("phone") or aid
    op = _get_op(op_id)
    if not op: return
    lock = _get_op_lock(op_id)
    ctx = _build_ctx()
    cli = None

    async def _phase(ph):
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["progress"]["phase"] = ph; _save_op(op2)
        await _refresh_op_panel(op_id)

    async def _stat(**kw):
        async with lock:
            op2 = _get_op(op_id)
            if op2:
                for k, v in kw.items(): op2["progress"][k] = v
                _save_op(op2)

    async def _finish(ph):
        async with lock:
            op2 = _get_op(op_id)
            if op2:
                op2["progress"]["phase"] = ph
                if op2.get("status") == "running": op2["status"] = "done"; op2["finished_at"] = int(time.time())
                _save_op(op2)
        await _refresh_op_panel(op_id)

    async def _live():
        cid = STATE.get("owner")
        if not cid or not _is_page(cid, f"op:{op_id}"): return
        while True:
            try:
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") != "running": return
                if not _is_page(cid, f"op:{op_id}"): return
                await _refresh_op_panel(op_id)
            except asyncio.CancelledError: raise
            except Exception: pass
            await asyncio.sleep(1.5)

    async def _is_cancelled():
        async with lock:
            op2 = _get_op(op_id)
            return (not op2) or op2.get("status") == "cancelled"

    live_task = asyncio.create_task(_live())
    try:
        await _phase("🔌 اتصال (3 تلاش)")
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
        if cli is None:
            await _finish(f"❌ اتصال ناموفق: {err}"); return
        try:
            me = await asyncio.wait_for(cli.get_me(), timeout=25)
            await _phase(f"✅ {me.first_name or aid}")
        except Exception as e:
            try: await cli._disconnect()
            except Exception: pass
            await _finish(f"⚠️ get_me: {type(e).__name__}"); return

        own_channel_ids: Set[int] = get_own_channel_ids(aid)
        cfg = _load(CFG_FILE, DEFAULT_CFG)
        wait_seconds = int(cfg.get("wait_for_links_sec", 90))
        max_wait_rounds = int(cfg.get("max_wait_rounds", 20))

        ch = tpl.get("channel") or {}
        private_link = ""
        private_title = ""
        if ch.get("title"):
            ctype = ch.get("type", "private")
            is_pub = ctype == "public"
            title = _substitute(ch["title"], ctx)[:60] or f"کانال {ctx['n']}"
            about = _substitute(ch.get("about", ""), ctx)
            await _phase(f"🏗 ساخت «{title}»")
            try:
                ok, ch_obj, msg = await soroosh_create_channel(cli, title, about)
                if ok and ch_obj:
                    ch_data = _channel_data_from_obj(ch_obj)
                    if not ch_data.get("access_hash"):
                        try:
                            await asyncio.sleep(1.5)
                            dialogs = await cli.get_dialogs()
                            cid_now = ch_data.get("id")
                            for d in dialogs or []:
                                ent = getattr(d, "entity", None)
                                if ent is None: continue
                                d_id = getattr(d, "id", None)
                                d_title = getattr(ent, "title", None) or ""
                                if (cid_now is not None and d_id == cid_now) or (cid_now is None and d_title == title):
                                    full = _channel_data_from_obj(ent)
                                    ch_data.update({k: v for k, v in full.items() if v not in (None, "")})
                                    ch_obj = ent; break
                        except Exception: pass
                    if is_pub and ch.get("username"):
                        uname = _substitute(ch["username"], ctx)
                        try:
                            ent2, _ = await _resolve_channel_entity(cli, ch_data, aid)
                            if ent2:
                                r = cli(UpdateUsernameRequest(channel=ent2, username=uname))
                                if asyncio.iscoroutine(r): r = await r
                                ch_data["username"] = uname
                        except Exception: pass
                    ch_data["type"] = ctype; ch_data["created"] = int(time.time())
                    add_channel_to_storage(aid, ch_data)
                    try:
                        _new_cid = ch_data.get("id")
                        if _new_cid is not None: own_channel_ids.add(int(_new_cid))
                        _new_rid = ch_data.get("raw_id")
                        if _new_rid is not None: own_channel_ids.add(int(_new_rid))
                    except Exception: pass
                    await asyncio.sleep(1.0)
                    try:
                        chs = get_stored_channels(aid)
                        target_guid = ch_data.get("guid"); target_id = ch_data.get("id")
                        for i2, c2 in enumerate(chs):
                            hit = False
                            if target_guid and c2.get("guid") == target_guid: hit = True
                            elif target_id is not None and c2.get("id") == target_id: hit = True
                            if hit:
                                ok2, link = await export_invite_link(aid, i2)
                                if ok2: private_link = link
                                break
                    except Exception: pass
                    if not private_link and ch_obj is not None and ExportChatInviteRequest:
                        try:
                            ent3, _m3 = await _resolve_channel_entity(cli, ch_data, aid)
                            if ent3:
                                try:
                                    r3 = cli(ExportChatInviteRequest(peer=ent3))
                                    if asyncio.iscoroutine(r3): r3 = await r3
                                    lk = getattr(r3, "link", None)
                                    if lk: private_link = str(lk)
                                except Exception: pass
                        except Exception: pass
                    if not private_link and ch_data.get("username"):
                        private_link = f"https://splus.ir/{ch_data['username']}"
                    private_title = ch_data.get("title", "") or ""
                    ctx["Link_channel"] = private_link
                    ctx["Username_channel"] = ch_data.get("username", "") or ""
                    ctx["Title_channel"] = private_title
                    ctx["Link_private"] = private_link
                    ctx["Title_private"] = private_title
                    if ch.get("photo_file") and os.path.exists(ch["photo_file"]):
                        try:
                            ent_ph, _ = await _resolve_channel_entity(cli, ch_data, aid)
                            if ent_ph:
                                pok, perr = await soroosh_set_channel_photo(cli, ent_ph, ch["photo_file"])
                                if pok: flog(f"[autotar] {name}: private channel photo ✅")
                                else: flog(f"[autotar] {name}: private photo FAILED: {perr}", "warning")
                        except Exception: pass
                    flog(f"[autotar] {name}: private link = {private_link or '(EMPTY!)'}")
                else:
                    add_error("autotar-کانال", msg, title, name)
            except Exception as e:
                add_error("autotar-کانال", _fmt_error(e), title, name)

        if ch.get("public_for_profile") and ch.get("public_title"):
            pub_title = _substitute(ch["public_title"], ctx)[:60] or f"Public {ctx['n']}"
            pub_username = _substitute(ch.get("public_username", ""), ctx)
            pub_about = _substitute(ch.get("public_about", ""), ctx)
            await _phase(f"📢 ساخت کانال عمومی «{pub_title}»")
            public_link = ""
            try:
                ok2, pub_obj, msg2 = await soroosh_create_channel(cli, pub_title, pub_about)
                if ok2 and pub_obj:
                    pub_data = _channel_data_from_obj(pub_obj)
                    if not pub_data.get("access_hash"):
                        try:
                            await asyncio.sleep(1.5)
                            dialogs = await cli.get_dialogs()
                            cid_now = pub_data.get("id")
                            for d in dialogs or []:
                                ent = getattr(d, "entity", None)
                                if ent is None: continue
                                d_id = getattr(d, "id", None)
                                d_title = getattr(ent, "title", None) or ""
                                if (cid_now is not None and d_id == cid_now) or (cid_now is None and d_title == pub_title):
                                    full = _channel_data_from_obj(ent)
                                    pub_data.update({k: v for k, v in full.items() if v not in (None, "")})
                                    pub_obj = ent; break
                        except Exception: pass
                    if pub_username:
                        try:
                            ent2, _ = await _resolve_channel_entity(cli, pub_data, aid)
                            if ent2:
                                r = cli(UpdateUsernameRequest(channel=ent2, username=pub_username))
                                if asyncio.iscoroutine(r): r = await r
                                pub_data["username"] = pub_username
                        except Exception: pass
                    pub_data["type"] = "public"; pub_data["created"] = int(time.time())
                    pub_data["is_public_for_profile"] = True
                    add_channel_to_storage(aid, pub_data)
                    try:
                        _new_cid = pub_data.get("id")
                        if _new_cid is not None: own_channel_ids.add(int(_new_cid))
                        _new_rid = pub_data.get("raw_id")
                        if _new_rid is not None: own_channel_ids.add(int(_new_rid))
                    except Exception: pass
                    await asyncio.sleep(1.0)
                    try:
                        chs2 = get_stored_channels(aid)
                        for i2, c2 in enumerate(chs2):
                            if (pub_data.get("guid") and c2.get("guid") == pub_data.get("guid")) or \
                               (pub_data.get("id") is not None and c2.get("id") == pub_data.get("id")):
                                ok3, lk2 = await export_invite_link(aid, i2)
                                if ok3: public_link = lk2
                                break
                    except Exception: pass
                    if not public_link and pub_data.get("username"):
                        public_link = f"https://splus.ir/{pub_data['username']}"
                    ctx["Link_public"] = public_link
                    ctx["Username_public"] = pub_data.get("username", "")
                    ctx["Title_public"] = pub_data.get("title", "")
                    flog(f"[autotar] {name}: public link = {public_link or '(EMPTY!)'}")
                    if ch.get("photo_file") and os.path.exists(ch["photo_file"]):
                        try:
                            ent_pub, _ = await _resolve_channel_entity(cli, pub_data, aid)
                            if ent_pub: await soroosh_set_channel_photo(cli, ent_pub, ch["photo_file"])
                        except Exception: pass
                    if ch.get("set_as_personal"):
                        try:
                            ent_p, _ = await _resolve_channel_entity(cli, pub_data, aid)
                            if ent_p:
                                pok, perr = await _set_personal_channel(cli, ent_p)
                                if pok: flog(f"[autotar] personal channel ✅")
                                else: flog(f"[autotar] personal FAILED: {perr}", "warning")
                        except Exception as e:
                            flog(f"[autotar] personal EXC: {type(e).__name__}", "warning")
                    if ch.get("post_to_public"):
                        post_tpl = ch.get("post_text", "")
                        post_text = _substitute(post_tpl, ctx) if post_tpl else private_link
                        try:
                            ent_pub2, _ = await _resolve_channel_entity(cli, pub_data, aid)
                            if ent_pub2 and post_text:
                                r = cli.send_message(ent_pub2, post_text)
                                if asyncio.iscoroutine(r): r = await r
                                flog(f"[autotar] {name}: posted ✅")
                        except Exception as pe:
                            flog(f"[autotar] post FAILED: {type(pe).__name__}", "warning")
                else:
                    add_error("autotar-کانال-عمومی", msg2, pub_title, name)
            except Exception as e:
                add_error("autotar-کانال-عمومی", _fmt_error(e), pub_title, name)

        p = tpl.get("profile") or {}
        if p.get("first_name") or p.get("last_name") or p.get("bio") or p.get("username") or p.get("photo_file"):
            await _phase("📝 پروفایل")
            kwargs = {}
            if p.get("first_name"): kwargs["first_name"] = _substitute(p["first_name"], ctx)[:64]
            if p.get("last_name"): kwargs["last_name"] = _substitute(p["last_name"], ctx)[:64]
            if p.get("bio"): kwargs["about"] = _substitute(p["bio"], ctx)[:70]
            if kwargs:
                try:
                    r = cli(UpdateProfileRequest(**kwargs))
                    if asyncio.iscoroutine(r): r = await r
                except Exception as e: add_error("autotar-پروفایل", _fmt_error(e), None, name)
            if p.get("username"):
                try:
                    r = cli(UpdateUsernameRequest(username=_substitute(p["username"], ctx)))
                    if asyncio.iscoroutine(r): r = await r
                except Exception as e: add_error("autotar-یوزنیم", _fmt_error(e), None, name)
            if p.get("photo_file") and os.path.exists(p["photo_file"]):
                try:
                    pok, perr = await soroosh_set_profile_photo(cli, p["photo_file"])
                    if pok: flog(f"[autotar] {name}: profile photo ✅")
                    else: flog(f"[autotar] {name}: profile photo FAILED: {perr}", "warning")
                except Exception: pass

        j = tpl.get("joiner") or {}
        snd = tpl.get("sender") or {}
        mode = snd.get("mode", "send_only")
        sender_text = _substitute(snd.get("text", ""), ctx) if snd.get("text") else ""
        send_during_join = (mode in ("join_send", "join_send_leave")) and bool(sender_text)
        send_to_existing = bool(snd.get("send_to_existing", True))
        attach_file = snd.get("attach_file") or ""
        attach_caption = _substitute(snd.get("attach_caption", ""), ctx) if snd.get("attach_caption") else ""
        groups_only = bool(j.get("groups_only", True))
        max_join = int(j.get("max_join", 0) or 0)
        joiner_enabled = max_join > 0
        join_delay = {"ultra": 0.3, "fast": 1.0, "normal": 3.0, "slow": 8.0}.get(j.get("speed", "fast"), 1.0)
        wave_size = 50; max_waves = 200
        joined_count = already_count = sent_count = left_count = failed_count = tried_count = 0
        skipped_seen = 0; skipped_banned = 0; rejected_inactive = 0; skipped_channel = 0
        failed_queue: List[str] = []
        sent_ids: Set[int] = set()

        if joiner_enabled:
            lds = list(load_link_donies())
            await _stat(total=max_join, joined=0, already=0, failed=0, tried=0, wave=0,
                        sent=0, left=0, skipped_seen=0, skipped_banned=0, rejected=0)
            wave_num = 0; deep_scan_done = False; wait_round = 0

            async def _extract_wave(use_deep: bool = False):
                nonlocal skipped_seen, skipped_banned
                tasks = []
                for url in lds:
                    async def _one(u=url):
                        try:
                            return await asyncio.wait_for(
                                _extract_from_linkdoni(cli, u, limit=300, log=log, deep_scan=use_deep),
                                timeout=180)
                        except Exception: return []
                    tasks.append(asyncio.create_task(_one()))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                new_links = []
                for r in results:
                    if isinstance(r, list):
                        for lk in r:
                            h = _hash_of(lk)
                            if not h: continue
                            if _is_seen(h): skipped_seen += 1; continue
                            if _is_banned(h): skipped_banned += 1; continue
                            if lk in new_links: continue
                            new_links.append(lk)
                            if len(new_links) >= wave_size: break
                    if len(new_links) >= wave_size: break
                return new_links

            async def _find_new_entity():
                try:
                    await asyncio.sleep(0.6)
                    for d in (await cli.get_dialogs()) or []:
                        eid = getattr(d, "id", None)
                        if not eid: continue
                        if getattr(d, "is_user", False): continue
                        ent = getattr(d, "entity", None)
                        if ent is None: continue
                        if not _is_group_or_channel(ent): continue
                        return ent
                except Exception: pass
                return None

            async def _join_one(lk):
                nonlocal joined_count, already_count, sent_count, left_count, failed_count, tried_count, rejected_inactive, skipped_channel
                if joined_count >= max_join: return
                if await _is_cancelled(): return
                h = _hash_of(lk)
                if not h: return
                if _is_seen(h): return
                if _is_banned(h): return
                if groups_only:
                    kind, _pre = await _check_link_type(cli, lk)
                    if kind == "channel":
                        skipped_channel += 1
                        flog(f"[autotar] skip channel: {lk}")
                        _mark_seen(h)
                        return
                tried_count += 1
                try:
                    ok, err2, tag, joined_ent = await asyncio.wait_for(_try_join(cli, lk), timeout=30)
                except Exception as e:
                    ok, err2, tag, joined_ent = False, _fmt_error(e), "exc", None
                if not ok:
                    failed_count += 1
                    if err2 and ("BANNED" in err2.upper() or "KICKED" in err2.upper() or
                                  "CHANNEL_PRIVATE" in err2.upper()):
                        _mark_banned(h, err2[:80])
                    elif err2 and not _is_perm_error(err2):
                        failed_queue.append(lk)
                    else:
                        add_error("autotar-جوین", err2, lk, name)
                    _mark_seen(h)
                    await _stat(joined=joined_count, already=already_count,
                                failed=failed_count, tried=tried_count)
                    if join_delay > 0: await asyncio.sleep(join_delay)
                    return
                if tag == "already":
                    already_count += 1; _mark_seen(h)
                else:
                    joined_count += 1; _mark_seen(h)
                ent_for_check = joined_ent
                if ent_for_check is None: ent_for_check = await _find_new_entity()
                if ent_for_check is None and lk.startswith("@"):
                    try: ent_for_check = await cli.get_entity(lk.lstrip("@"))
                    except Exception: pass
                active = True
                if ent_for_check is not None and _is_group_or_channel(ent_for_check):
                    active, reason = await _is_group_active(cli, ent_for_check)
                    if not active:
                        rejected_inactive += 1
                        _mark_banned(h, f"inactive:{reason}")
                        if tag != "already":
                            try: await _lefter_leave_one(cli, {"entity": ent_for_check, "kind": "group"})
                            except Exception: pass
                        await _stat(joined=joined_count, already=already_count,
                                    failed=failed_count, tried=tried_count, rejected=rejected_inactive)
                        if join_delay > 0: await asyncio.sleep(join_delay)
                        return
                if send_during_join and active and ent_for_check is not None:
                    try:
                        await asyncio.sleep(0.4)
                        if attach_file and os.path.exists(attach_file):
                            _ok, _err = await _send_file_to_entity(cli, ent_for_check, attach_file, attach_caption or sender_text)
                        else:
                            _ok, _err = await _send_to_entity(cli, ent_for_check, sender_text, snd, log=log)
                        if _ok:
                            sent_count += 1
                            try:
                                _seid = getattr(ent_for_check, "id", None)
                                if _seid is not None: sent_ids.add(int(_seid))
                            except Exception: pass
                            if mode == "join_send_leave":
                                ok_l, _ = await _lefter_leave_one(cli, {"entity": ent_for_check, "kind": "group"})
                                if ok_l: left_count += 1
                        else:
                            failed_count += 1
                            add_error("autotar-ارسال", _err or "send_failed", lk, name)
                            if _err and "SUSPENDED" in _err.upper():
                                await _finish(f"🚫 اکانت {name} معلق شده")
                                return
                    except RuntimeError as re:
                        if "ACCOUNT_SUSPENDED" in str(re):
                            await _finish(f"🚫 اکانت {name} معلق شده")
                            return
                        raise
                    except Exception as e:
                        failed_count += 1
                        add_error("autotar-ارسال", _fmt_error(e), lk, name)
                await _stat(joined=joined_count, already=already_count, sent=sent_count,
                            failed=failed_count, tried=tried_count, left=left_count,
                            rejected=rejected_inactive)
                if join_delay > 0: await asyncio.sleep(join_delay)

            while joined_count < max_join and wave_num < max_waves:
                if await _is_cancelled(): await _finish("⛔ لغو"); return
                wave_num += 1
                await _stat(wave=wave_num)
                await _phase(f"🌊 موج {wave_num}: استخراج ({joined_count}/{max_join})")
                new_links = await _extract_wave(use_deep=False)
                retry_links = []
                for lk in failed_queue[:]:
                    h = _hash_of(lk)
                    if h and not _is_seen(h) and not _is_banned(h):
                        if lk not in new_links: retry_links.append(lk)
                failed_queue = []
                for lk in retry_links: new_links.append(lk)
                if not new_links and not deep_scan_done:
                    deep_scan_done = True
                    await _phase(f"🔎 موج {wave_num}: deep scan")
                    deep_links = await _extract_wave(use_deep=True)
                    for lk in deep_links:
                        if lk not in new_links: new_links.append(lk)
                    for lk in retry_links:
                        if lk not in new_links: new_links.append(lk)
                if not new_links:
                    wait_round += 1
                    if wait_round > max_wait_rounds:
                        await _phase(f"⚠️ پس از {max_wait_rounds} دور انتظار — پایان")
                        break
                    await _phase(f"⏸ موج {wave_num}: انتظار {wait_seconds}ث ({wait_round}/{max_wait_rounds})")
                    for _ in range(wait_seconds):
                        if await _is_cancelled(): await _finish("⛔ لغو"); return
                        await asyncio.sleep(1)
                    wave_num -= 1; deep_scan_done = False; continue
                else:
                    wait_round = 0
                await _phase(f"🌊 موج {wave_num}: {len(new_links)} لینک")
                sem = asyncio.Semaphore(8)
                async def _limited(lk):
                    async with sem: await _join_one(lk)
                await asyncio.gather(*[asyncio.create_task(_limited(lk)) for lk in new_links],
                                     return_exceptions=True)
                await _phase(f"✅ موج {wave_num} تمام — {joined_count}/{max_join}")

            if joined_count < max_join and failed_queue:
                if await _is_cancelled(): await _finish("⛔ لغو"); return
                await _phase(f"🔄 تلاش نهایی روی {len(failed_queue)} لینک")
                final = failed_queue[:]; failed_queue = []
                for lk in final:
                    if joined_count >= max_join: break
                    await _join_one(lk)

        should_send_final = False
        if sender_text or attach_file:
            if not send_during_join: should_send_final = True
            elif send_to_existing: should_send_final = True
        if should_send_final:
            target = snd.get("target", "groups")
            max_send = int(snd.get("max_send", 0) or 0)
            delay = float(snd.get("delay", 1.5))
            use_edit = bool(snd.get("edit_delay_enabled", False))
            await _phase("📤 ارسال" + (" (Edit-Delay)" if use_edit else "") +
                         (" + قبلی‌ها" if send_to_existing and send_during_join else ""))
            targets = await _collect_targets(cli, target, exclude_ids=own_channel_ids, groups_only=groups_only)
            if sent_ids:
                filtered = []
                for t in targets:
                    _eid = None
                    try:
                        _e = t.get("entity")
                        if _e is not None: _eid = getattr(_e, "id", None)
                        if _eid is None:
                            _tid = t.get("target")
                            if isinstance(_tid, int): _eid = _tid
                    except Exception: pass
                    if _eid is not None and int(_eid) in sent_ids: continue
                    filtered.append(t)
                targets = filtered
            if max_send and len(targets) > max_send: targets = targets[:max_send]
            await _stat(total=len(targets))
            for i, t in enumerate(targets, 1):
                if await _is_cancelled(): await _finish("⛔ لغو"); return
                try:
                    ent = t.get("entity") or t["target"]
                    if not _is_group_or_channel(ent) and t.get("type") != "pv": continue
                    if attach_file and os.path.exists(attach_file):
                        _ok, _err = await _send_file_to_entity(cli, ent, attach_file, attach_caption or sender_text)
                        if not _ok and sender_text:
                            try:
                                _r = cli.send_message(ent, sender_text)
                                if asyncio.iscoroutine(_r): _r = await _r
                                _ok, _err = True, "file_failed_text_sent"
                                flog(f"[autotar] file failed -> text fallback: {t.get('name')}")
                            except Exception as _te:
                                flog(f"[autotar] text fallback also failed: {_te}", "warning")
                    else:
                        _ok, _err = await _send_to_entity(cli, ent, sender_text, snd, log=log)
                    if _ok: sent_count += 1
                    else:
                        failed_count += 1
                        add_error("autotar-ارسال", _err or "send_failed", t.get("name"), name)
                        if _err and "SUSPENDED" in _err.upper():
                            await _finish(f"🚫 اکانت {name} معلق شده")
                            return
                except RuntimeError as re:
                    if "ACCOUNT_SUSPENDED" in str(re):
                        await _finish(f"🚫 اکانت {name} معلق شده"); return
                    raise
                except FloodWaitError as fe:
                    failed_count += 1; add_error("autotar-ارسال", f"Flood {fe.seconds}s", t.get("name"), name)
                except Exception as e:
                    failed_count += 1; add_error("autotar-ارسال", _fmt_error(e), t.get("name"), name)
                await _stat(sent=sent_count, failed=failed_count, pending=max(0, len(targets) - i))
                if delay > 0: await asyncio.sleep(delay)

        lf = tpl.get("lefter") or {}
        if lf.get("leave_mode"):
            ml = lf["leave_mode"]
            await _phase(f"🚪 ترک ({ml})")
            for t in await _lefter_collect(cli, ml, exclude_ids=own_channel_ids):
                if await _is_cancelled(): await _finish("⛔ لغو"); return
                try:
                    ok_l, _ = await _lefter_leave_one(cli, t)
                    if ok_l: left_count += 1; await _stat(left=left_count)
                except Exception: pass
                await asyncio.sleep(0.6)

        await _finish(f"✅ جوین {joined_count} · ارسال {sent_count} · ترک {left_count} · "
                      f"غیرفعال {rejected_inactive} · رد‌کانال {skipped_channel} · seen {skipped_seen}")
    except asyncio.CancelledError: await _finish("⛔ لغو"); raise
    except Exception as e:
        flog(f"[autotar] FATAL: {traceback.format_exc()}", "error")
        await _finish(f"❌ {type(e).__name__}")
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass
        live_task.cancel()
        try: await live_task
        except Exception: pass


async def run_auto_tar(op, log, tpl_override=None):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    tpl = tpl_override if tpl_override else get_template(op.get("template_id"))
    if not tpl:
        op["status"] = "failed"; op["progress"]["phase"] = "❌ قالب نیست"; _save_op(op); return
    op["progress"] = {"joined": 0, "failed": 0, "total": 0, "pending": 0,
                      "in_progress": 0, "phase": "شروع", "sent": 0, "already": 0,
                      "tried": 0, "wave": 0, "left": 0,
                      "skipped_seen": 0, "skipped_banned": 0, "rejected": 0}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(_auto_tar_worker(aid, a, op["id"], tpl, log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled", "done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)


# ═══════════════ JOINER ═══════════════
async def _joiner_worker(aid, acc, op_id, join_delay, max_join, auto_msg, log):
    name = acc.get("name") or acc.get("phone") or aid
    op = _get_op(op_id)
    if not op: return
    link_donies = op.get("link_donies") or list(DEFAULT_LINK_DONIES)
    wave_size = int(op.get("wave_size") or 50); extract_limit = int(op.get("extract_limit") or 300)
    groups_only = bool(op.get("groups_only", True))
    lock = _get_op_lock(op_id)
    joined = 0; failed = 0; wave_num = 0
    skipped_seen = 0; skipped_banned = 0; rejected_inactive = 0; skipped_channel = 0
    cli = None
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    wait_seconds = int(cfg.get("wait_for_links_sec", 90))
    max_wait_rounds = int(cfg.get("max_wait_rounds", 20))

    async def _set_phase(phase):
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["progress"]["phase"] = phase; _save_op(op2)
        await _refresh_op_panel(op_id)

    async def _finish(phase):
        async with lock:
            op2 = _get_op(op_id)
            if op2:
                op2["progress"]["phase"] = phase
                if op2.get("status") == "running": op2["status"] = "done"; op2["finished_at"] = int(time.time())
                _save_op(op2)
        await _refresh_op_panel(op_id)

    async def _live():
        cid = STATE.get("owner")
        if not cid or not _is_page(cid, f"op:{op_id}"): return
        while True:
            try:
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") != "running": return
                if not _is_page(cid, f"op:{op_id}"): return
                await _refresh_op_panel(op_id)
            except asyncio.CancelledError: raise
            except Exception: pass
            await asyncio.sleep(1.5)

    live_task = asyncio.create_task(_live())
    try:
        await _set_phase("🔌 اتصال (3 تلاش)")
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
        if cli is None:
            await _finish(f"❌ اتصال ناموفق: {err}"); return
        try:
            me = await asyncio.wait_for(cli.get_me(), timeout=25)
            await _set_phase(f"✅ {me.first_name or aid}")
        except Exception as e:
            try: await cli._disconnect()
            except Exception: pass
            await _finish(f"⚠️ get_me: {type(e).__name__}"); return
        auto_join = int(cfg.get("auto_join_linkdoni", 1))
        if auto_join:
            for i, url in enumerate(link_donies, 1):
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") == "cancelled": await _finish("⛔"); return
                await _set_phase(f"📡 auto {i}/{len(link_donies)}")
                try: await asyncio.wait_for(_auto_join_linkdoni(cli, url, log=log), timeout=30)
                except Exception: pass
        deep_scan_done = False; wait_round = 0
        while True:
            async with lock:
                op2 = _get_op(op_id)
                if not op2 or op2.get("status") == "cancelled": await _finish("⛔"); return
            if max_join and joined >= max_join: await _finish(f"✅ سقف"); return
            wave_num += 1
            await _set_phase(f"🔍 موج {wave_num}: استخراج")
            tasks = []
            for url in link_donies:
                async def _one(u=url, deep=False):
                    try: return await asyncio.wait_for(_extract_from_linkdoni(cli, u, limit=extract_limit, log=log, deep_scan=deep), timeout=180)
                    except Exception: return []
                tasks.append(asyncio.create_task(_one()))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            new_links = []
            for r in results:
                if isinstance(r, list):
                    for lk in r:
                        h = _hash_of(lk)
                        if not h: continue
                        if _is_seen(h): skipped_seen += 1; continue
                        if _is_banned(h): skipped_banned += 1; continue
                        if lk in new_links: continue
                        new_links.append(lk)
                        if len(new_links) >= wave_size: break
                if len(new_links) >= wave_size: break
            if not new_links and not deep_scan_done:
                deep_scan_done = True
                await _set_phase(f"🔎 موج {wave_num}: deep scan")
                tasks2 = []
                for url in link_donies:
                    async def _one2(u=url):
                        try: return await asyncio.wait_for(_extract_from_linkdoni(cli, u, limit=300, log=log, deep_scan=True), timeout=180)
                        except Exception: return []
                    tasks2.append(asyncio.create_task(_one2()))
                results2 = await asyncio.gather(*tasks2, return_exceptions=True)
                for r in results2:
                    if isinstance(r, list):
                        for lk in r:
                            h = _hash_of(lk)
                            if not h: continue
                            if _is_seen(h): skipped_seen += 1; continue
                            if _is_banned(h): skipped_banned += 1; continue
                            if lk in new_links: continue
                            new_links.append(lk)
                            if len(new_links) >= wave_size: break
                    if len(new_links) >= wave_size: break
            if not new_links:
                wait_round += 1
                if wait_round > max_wait_rounds:
                    await _finish(f"⚠️ پس از {max_wait_rounds} دور انتظار لینکی نیامد"); return
                await _set_phase(f"⏸ موج {wave_num}: انتظار {wait_seconds}ث ({wait_round}/{max_wait_rounds})")
                for _ in range(wait_seconds):
                    async with lock:
                        op2 = _get_op(op_id)
                        if not op2 or op2.get("status") == "cancelled": await _finish("⛔"); return
                    await asyncio.sleep(1)
                wave_num -= 1; deep_scan_done = False; continue
            else:
                wait_round = 0
            await _set_phase(f"🌊 {len(new_links)} لینک")
            async with lock:
                op2 = _get_op(op_id)
                if op2: op2["progress"]["total"] = op2["progress"].get("total", 0) + len(new_links); _save_op(op2)
            sem = asyncio.Semaphore(8)
            async def join_one(lk):
                nonlocal joined, failed, rejected_inactive, skipped_channel
                async with sem:
                    if max_join and joined >= max_join: return
                    async with lock:
                        op2 = _get_op(op_id)
                        if not op2 or op2.get("status") == "cancelled": return
                    h = _hash_of(lk)
                    if _is_seen(h) or _is_banned(h): return
                    if groups_only:
                        kind, _pre = await _check_link_type(cli, lk)
                        if kind == "channel":
                            skipped_channel += 1; _mark_seen(h); return
                    try:
                        ok, err2, tag, ent_new = await asyncio.wait_for(_try_join(cli, lk), timeout=30)
                        if ok:
                            _mark_seen(h)
                            if ent_new is not None and _is_group_or_channel(ent_new):
                                active, reason = await _is_group_active(cli, ent_new)
                                if not active:
                                    rejected_inactive += 1
                                    _mark_banned(h, f"inactive:{reason}")
                                    if tag != "already":
                                        try: await _lefter_leave_one(cli, {"entity": ent_new, "kind": "group"})
                                        except Exception: pass
                                    return
                            joined += 1
                        else:
                            failed += 1; add_error("جوین", err2, lk, name)
                            if err2 and ("BANNED" in err2.upper() or "KICKED" in err2.upper() or
                                          "CHANNEL_PRIVATE" in err2.upper()):
                                _mark_banned(h, err2[:80])
                            _mark_seen(h)
                    except Exception as e:
                        failed += 1; add_error("جوین", _fmt_error(e), lk, name)
                        try: _mark_seen(h)
                        except Exception: pass
                    async with lock:
                        op2 = _get_op(op_id)
                        if op2:
                            op2["progress"]["joined"] = joined
                            op2["progress"]["failed"] = failed
                            op2["progress"]["skipped_seen"] = skipped_seen
                            op2["progress"]["skipped_banned"] = skipped_banned
                            op2["progress"]["rejected"] = rejected_inactive
                            _save_op(op2)
                    if join_delay > 0: await asyncio.sleep(join_delay)
            await asyncio.gather(*[asyncio.create_task(join_one(lk)) for lk in new_links], return_exceptions=True)
            await _set_phase(f"✅ موج {wave_num} — ✅{joined} ❌{failed} 🚫{rejected_inactive} رد‌کانال{skipped_channel}")
    except asyncio.CancelledError: await _finish("⛔ لغو"); raise
    except Exception as e:
        flog(f"[joiner] FATAL: {traceback.format_exc()}", "error")
        await _finish(f"❌ {type(e).__name__}")
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass
        live_task.cancel()
        try: await live_task
        except Exception: pass


async def run_joiner_lefter(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    op["progress"] = {"joined": 0, "failed": 0, "total": 0, "phase": "شروع", "extracted": 0,
                      "skipped_seen": 0, "skipped_banned": 0, "rejected": 0}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(_joiner_worker(aid, a, op["id"],
                     float(op.get("join_delay", 0.5)), op.get("max_join", 0) or 0,
                     (op.get("auto_msg") or "").strip(), log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled", "done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)


# ═══════════════ SENDER (with infinite loop) ═══════════════
async def _send_worker(aid, acc, op_id, cfg, stop, log):
    name = acc.get("name") or acc.get("phone") or aid
    op = _get_op(op_id)
    if not op: return
    lock = _get_op_lock(op_id); sent = 0; failed = 0; blocked = 0
    delay = float(op.get("delay", 1.5)); payload = op.get("payload") or {"text": "سلام"}
    text = payload.get("text") or "سلام"
    auto_left = bool(op.get("auto_left", False))
    groups_only = bool(op.get("groups_only", True))
    attach_file = op.get("attach_file") or ""
    infinite_loop = bool(op.get("infinite_loop", False))
    loop_delay = float(op.get("loop_delay", 3.0))
    cli = None

    async def _set_phase(phase):
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["progress"]["phase"] = phase; _save_op(op2)
        await _refresh_op_panel(op_id)

    async def _live():
        cid = STATE.get("owner")
        if not cid or not _is_page(cid, f"op:{op_id}"): return
        while True:
            try:
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") != "running": return
                if not _is_page(cid, f"op:{op_id}"): return
                await _refresh_op_panel(op_id)
            except asyncio.CancelledError: raise
            except Exception: pass
            await asyncio.sleep(1.5)

    live_task = asyncio.create_task(_live())
    try:
        await _set_phase("🔌 اتصال")
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
        if cli is None:
            async with lock:
                op2 = _get_op(op_id)
                if op2: op2["progress"]["phase"] = f"❌ اتصال: {err}"; op2["status"] = "done"; _save_op(op2)
            return
        await _set_phase("📋 مخاطبین")
        own_ids = get_own_channel_ids(aid)
        targets = await _collect_targets(cli, op.get("target", "both"), exclude_ids=own_ids, groups_only=groups_only)
        if not targets:
            async with lock:
                op2 = _get_op(op_id)
                if op2: op2["progress"]["phase"] = "❌ مخاطبی نیست"; op2["status"] = "done"; _save_op(op2)
            return
        max_send = int(op.get("max", 0) or 0)
        if max_send and len(targets) > max_send: targets = targets[:max_send]
        snd_cfg = {
            "edit_delay_enabled": bool(op.get("edit_delay_enabled", False)),
            "edit_delay_seconds": float(op.get("edit_delay_seconds", 3.0)),
            "edit_delay_random": bool(op.get("edit_delay_random", False)),
            "edit_delay_min": float(op.get("edit_delay_min", 2.0)),
            "edit_delay_max": float(op.get("edit_delay_max", 6.0)),
            "placeholder_text": op.get("placeholder_text", "سلام"),
            "placeholder_random": bool(op.get("placeholder_random", False)),
            "placeholder_list": op.get("placeholder_list", ""),
            "multi_step_edit": bool(op.get("multi_step_edit", False)),
            "multi_step_middle": op.get("multi_step_middle", "Hi"),
        }
        use_edit = snd_cfg["edit_delay_enabled"]

        loop_round = 0
        while True:
            loop_round += 1
            if infinite_loop:
                await _set_phase(f"🔁 دور {loop_round} — {len(targets)} مقصد")
            else:
                await _set_phase(f"📤 {len(targets)}" + (" (Edit-Delay)" if use_edit else ""))

            async with lock:
                op2 = _get_op(op_id)
                if not op2 or op2.get("status") == "cancelled": return
            if stop.is_set(): break

            async with lock:
                op2 = _get_op(op_id)
                if op2:
                    op2["progress"]["pending"] = len(targets)
                    op2["progress"]["in_progress"] = 1
                    op2["progress"]["total"] = len(targets)
                    if infinite_loop: op2["progress"]["round"] = loop_round
                    _save_op(op2)

            for i, t in enumerate(targets, 1):
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") == "cancelled": return
                if stop.is_set(): break
                try:
                    ent = t.get("entity") or t["target"]
                    if attach_file and os.path.exists(attach_file):
                        _ok, _err = await _send_file_to_entity(cli, ent, attach_file, text)
                        if not _ok and text:
                            try:
                                _r = cli.send_message(ent, text)
                                if asyncio.iscoroutine(_r): _r = await _r
                                _ok, _err = True, "file_failed_text_sent"
                                flog(f"[send] file failed -> text fallback: {t.get('name')}")
                            except Exception as _te:
                                flog(f"[send] text fallback also failed: {_te}", "warning")
                    else:
                        _ok, _err = await _send_to_entity(cli, ent, text, snd_cfg, log=log)
                    if _ok:
                        sent += 1
                    else:
                        if _err and _err.startswith("BLOCKED:"):
                            blocked += 1
                        else:
                            failed += 1
                            add_error("ارسال", _err or "send_failed", t.get("name"), name)
                        if _err and "SUSPENDED" in _err.upper():
                            async with lock:
                                op2 = _get_op(op_id)
                                if op2:
                                    op2["status"] = "failed"
                                    op2["progress"]["phase"] = f"🚫 اکانت {name} معلق شده"
                                    _save_op(op2)
                            add_error("حساب-معلق", f"اکانت {name} معلق", None, name)
                            return
                except RuntimeError as re:
                    if "ACCOUNT_SUSPENDED" in str(re):
                        async with lock:
                            op2 = _get_op(op_id)
                            if op2:
                                op2["status"] = "failed"
                                op2["progress"]["phase"] = f"🚫 اکانت {name} معلق شده"
                                _save_op(op2)
                        add_error("حساب-معلق", f"اکانت {name} معلق", None, name)
                        return
                    raise
                except FloodWaitError as fe:
                    failed += 1
                    add_error("ارسال", f"Flood {fe.seconds}s", t.get("name"), name)
                    await asyncio.sleep(fe.seconds + 1)
                except Exception as e:
                    failed += 1
                    add_error("ارسال", _fmt_error(e), t.get("name"), name)
                    if auto_left and _is_perm_error(e):
                        try: await _lefter_leave_one(cli, {"entity": ent, "kind": "group"})
                        except Exception: pass
                async with lock:
                    op2 = _get_op(op_id)
                    if op2:
                        op2["progress"]["sent"] = sent
                        op2["progress"]["failed"] = failed
                        op2["progress"]["blocked"] = blocked
                        op2["progress"]["pending"] = max(0, len(targets) - i)
                        if infinite_loop: op2["progress"]["round"] = loop_round
                        _save_op(op2)
                await asyncio.sleep(delay)

            if stop.is_set(): break
            async with lock:
                op2 = _get_op(op_id)
                if not op2 or op2.get("status") == "cancelled": return

            if not infinite_loop: break

            await _set_phase(f"🔁 دور {loop_round} تمام · انتظار {loop_delay:.0f}ث ...")
            waited = 0.0
            while waited < loop_delay:
                if stop.is_set(): return
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") == "cancelled": return
                chunk = min(1.0, loop_delay - waited)
                await asyncio.sleep(chunk)
                waited += chunk

        async with lock:
            op2 = _get_op(op_id)
            if op2:
                op2["progress"]["phase"] = f"✅ {sent} · {failed}" + (f" · 🚫 {blocked}" if blocked else "")
                op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)
    except asyncio.CancelledError: raise
    except Exception as e:
        flog(f"[sender] FATAL: {traceback.format_exc()}", "error")
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["status"] = "done"; _save_op(op2)
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass
        live_task.cancel()
        try: await live_task
        except Exception: pass


async def run_sender(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    op["progress"] = {"sent": 0, "failed": 0, "total": 0, "pending": 0, "in_progress": 0, "phase": "شروع", "blocked": 0, "round": 0}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    stop = asyncio.Event(); STATE["cancel_" + op["id"]] = stop
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(_send_worker(aid, a, op["id"], _load(CFG_FILE, DEFAULT_CFG), stop, log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled", "done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)


# ═══════════════ LISTENER / KEEPALIVE / PV ═══════════════
LISTENER_TASKS: Dict[str, asyncio.Task] = {}
PV_LISTENER_TASKS: Dict[str, asyncio.Task] = {}

async def _listener_loop(aid, acc, stop_event):
    name = acc.get("name") or acc.get("phone") or aid
    flog(f"[listener] {name}: started")
    while not stop_event.is_set():
        cli = None
        try:
            cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
            if cli is None:
                flog(f"[listener] {name}: connect fail: {err}", "warning")
                await asyncio.sleep(30); continue
            raw = cli.raw
            @raw.on(events.NewMessage(incoming=True))
            async def _on_new(event):
                try:
                    if not getattr(event, "is_private", False): return
                    if getattr(event, "out", False): return
                    STATE["listener_new_count"] = STATE.get("listener_new_count", 0) + 1
                    try: await event.reply("سلام 👋")
                    except Exception: pass
                except Exception: pass
            while not stop_event.is_set(): await asyncio.sleep(2)
            try: await raw.disconnect()
            except Exception: pass
        except asyncio.CancelledError: raise
        except Exception as e:
            flog(f"[listener] {name}: {type(e).__name__}", "warning"); await asyncio.sleep(20)
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass

async def start_all_listeners():
    for aid, acc in list_accounts().items():
        if aid in LISTENER_TASKS and not LISTENER_TASKS[aid].done(): continue
        stop = asyncio.Event(); STATE.setdefault("listener_stops", {})[aid] = stop
        t = asyncio.create_task(_listener_loop(aid, acc, stop))
        LISTENER_TASKS[aid] = t; flog(f"[listener] started {aid}")

def _stop_listener_for(aid):
    loop = _loop_ref[0]
    if loop is None:
        try: loop = asyncio.get_event_loop()
        except Exception: return
    def _go():
        st = STATE.setdefault("listener_stops", {}).get(aid)
        if st: st.set()
        t = LISTENER_TASKS.pop(aid, None)
        if t and not t.done(): t.cancel()
    try: loop.call_soon_threadsafe(_go)
    except Exception: pass

async def restart_all_listeners():
    for aid, st in list(STATE.get("listener_stops", {}).items()):
        try: st.set()
        except: pass
    for aid, t in list(LISTENER_TASKS.items()):
        if not t.done(): t.cancel()
    LISTENER_TASKS.clear(); STATE["listener_stops"] = {}
    await asyncio.sleep(1); await start_all_listeners()


# ══════════════════════════════════════════════════════════════════
# ⭐ v27.9.3 — PV responder بازنویسی‌شده (fallback کامل + debug)
# ══════════════════════════════════════════════════════════════════
async def _pv_responder_worker(aid, acc, stop_event):
    name = acc.get("name") or acc.get("phone") or aid
    flog(f"[pv] {name}: worker started")
    while not stop_event.is_set():
        cli = None
        try:
            cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
            if cli is None:
                flog(f"[pv] {name}: connect fail: {err}", "warning")
                await asyncio.sleep(30); continue
            raw = cli.raw
            if raw is None:
                await asyncio.sleep(10); continue

            flog(f"[pv] {name}: raw connected — registering handler")

            async def _on_pv(event):
                sender_id = None
                user_info = {}
                try:
                    cfg = _load_pv_items()
                    flog(f"[pv] {name}: event received type={type(event).__name__}")
                    if not cfg.get("enabled"):
                        flog(f"[pv] {name}: skip → not enabled"); return

                    try:
                        sender = await event.get_sender()
                    except Exception as se:
                        flog(f"[pv] {name}: get_sender err: {se}", "warning"); return
                    if sender is None:
                        flog(f"[pv] {name}: skip → no sender"); return

                    sender_id = getattr(sender, "id", None)
                    if sender_id is None:
                        flog(f"[pv] {name}: skip → no sender_id"); return

                    try:
                        me = await cli.get_me()
                        if getattr(me, "id", None) == sender_id:
                            flog(f"[pv] {name}: skip → from me"); return
                    except Exception: pass

                    if getattr(sender, "bot", False):
                        flog(f"[pv] {name}: skip → bot"); return

                    is_private = True
                    if hasattr(event, "is_private"):
                        try: is_private = bool(getattr(event, "is_private"))
                        except Exception: is_private = True
                    if is_private:
                        try:
                            chat = await event.get_chat()
                            chat_id = getattr(chat, "id", None)
                            if chat_id is not None and chat_id != sender_id:
                                is_private = False
                        except Exception: pass
                    if is_private and hasattr(event, "chat_id"):
                        try:
                            cid_ev = getattr(event, "chat_id", None)
                            if cid_ev is not None and cid_ev != sender_id:
                                is_private = False
                        except Exception: pass

                    if not is_private:
                        flog(f"[pv] {name}: skip → not private"); return

                    user_info = {
                        "first_name": getattr(sender, "first_name", "") or "",
                        "last_name": getattr(sender, "last_name", "") or "",
                        "username": getattr(sender, "username", "") or "",
                    }
                    flog(f"[pv] {name}: PV from {sender_id} ({user_info.get('first_name')})")

                    try: _record_pv_visit(aid, str(sender_id), user_info)
                    except Exception as re:
                        flog(f"[pv] record err: {type(re).__name__}", "warning")

                    if cfg.get("reply_once", True) and _has_pv_replied(aid, str(sender_id)):
                        flog(f"[pv] {name}: skip → already replied"); return

                    delay_sec = int(cfg.get("delay_seconds", 120))
                    flog(f"[pv] {name}: waiting {delay_sec}s before reply")
                    if delay_sec > 0:
                        for _ in range(delay_sec):
                            if stop_event.is_set(): return
                            await asyncio.sleep(1)

                    items = cfg.get("items") or []
                    send_ok = True
                    send_err = None
                    for item in items:
                        if stop_event.is_set(): return
                        kind = item.get("kind", "text")
                        try:
                            if kind == "text":
                                txt = item.get("text") or ""
                                if txt:
                                    r = cli.send_message(sender_id, txt)
                                    if asyncio.iscoroutine(r): r = await r
                                    await asyncio.sleep(random.uniform(1.0, 2.5))
                            elif kind == "forward":
                                mid = item.get("message_id")
                                fcid = item.get("from_chat_id") or FORCED_OWNER
                                if mid and APP:
                                    try:
                                        await APP.bot.copy_message(
                                            chat_id=sender_id, from_chat_id=fcid,
                                            message_id=int(mid))
                                        await asyncio.sleep(random.uniform(1.0, 2.5))
                                    except Exception as fe:
                                        send_ok = False
                                        send_err = f"copy: {str(fe)[:100]}"
                            elif kind == "delay":
                                sec = int(item.get("seconds", 3))
                                await asyncio.sleep(sec)
                        except FloodWaitError as fe:
                            await asyncio.sleep(fe.seconds + 1)
                            send_ok = False; send_err = f"Flood {fe.seconds}s"
                        except Exception as e:
                            flog(f"[pv] send step err: {type(e).__name__}: {e}", "warning")
                            send_ok = False; send_err = f"{type(e).__name__}: {str(e)[:120]}"

                    if cfg.get("reply_once", True):
                        _mark_pv_replied(aid, str(sender_id))
                    try: _record_pv_reply(aid, str(sender_id), ok=send_ok, err=send_err)
                    except Exception: pass

                    if cfg.get("notify", True):
                        u_label = (user_info.get("first_name") or
                                   (("@" + user_info["username"]) if user_info.get("username") else None) or
                                   str(sender_id))
                        try:
                            if send_ok:
                                await tg_send(f"✅ پیام PV به <b>{esc(u_label)}</b> ارسال شد")
                            else:
                                await tg_send(f"❌ پیام PV به <b>{esc(u_label)}</b> خطا: <code>{esc(send_err or '?')}</code>")
                        except Exception as ne:
                            flog(f"[pv] notify err: {type(ne).__name__}", "warning")

                    flog(f"[pv] {name}: replied to {sender_id} ({'OK' if send_ok else 'FAIL'})")
                except Exception as e:
                    flog(f"[pv] handler err: {type(e).__name__}: {e}", "warning")
                    try:
                        if sender_id:
                            _record_pv_reply(aid, str(sender_id), ok=False, err=str(e)[:200])
                    except Exception: pass

            registered = False
            try:
                if hasattr(raw, "add_event_handler"):
                    raw.add_event_handler(_on_pv, events.NewMessage(incoming=True))
                    registered = True
                    flog(f"[pv] {name}: registered via add_event_handler")
            except Exception as e1:
                flog(f"[pv] {name}: add_event_handler fail: {e1}", "warning")
            if not registered:
                try:
                    raw.on(events.NewMessage(incoming=True))(_on_pv)
                    registered = True
                    flog(f"[pv] {name}: registered via on()")
                except Exception as e2:
                    flog(f"[pv] {name}: on() fail: {e2}", "warning")
            if not registered:
                try:
                    raw.add_event_handler(_on_pv, events.NewMessage)
                    registered = True
                    flog(f"[pv] {name}: registered via add_event_handler (no filter)")
                except Exception as e3:
                    flog(f"[pv] {name}: all registration methods failed: {e3}", "error")
            if not registered:
                flog(f"[pv] {name}: ❌ PV DISABLED for this account", "error")
                await asyncio.sleep(60); continue

            while not stop_event.is_set():
                await asyncio.sleep(2)
            try: await raw.disconnect()
            except Exception: pass

        except asyncio.CancelledError: raise
        except Exception as e:
            flog(f"[pv] {name}: worker loop err: {type(e).__name__}: {e}", "warning")
            await asyncio.sleep(20)
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass


async def start_pv_responders():
    cfg = _load_pv_items()
    if not cfg.get("enabled"):
        flog("[pv] disabled — skip"); return
    for aid, acc in list_accounts().items():
        existing = PV_LISTENER_TASKS.get(aid)
        if existing and not existing.done():
            continue
        if existing and existing.done():
            flog(f"[pv] restarting dead worker for {aid}")
            try: existing.exception()
            except Exception: pass
        stop = asyncio.Event()
        STATE.setdefault("pv_stops", {})[aid] = stop
        t = asyncio.create_task(_pv_responder_worker(aid, acc, stop))
        PV_LISTENER_TASKS[aid] = t
        flog(f"[pv] started for {aid}")

def _stop_all_pv():
    for aid, st in list(STATE.get("pv_stops", {}).items()):
        try: st.set()
        except: pass
    for aid, t in list(PV_LISTENER_TASKS.items()):
        if not t.done(): t.cancel()
    PV_LISTENER_TASKS.clear()
    STATE["pv_stops"] = {}

async def restart_all_pv():
    _stop_all_pv()
    await asyncio.sleep(1)
    await start_pv_responders()

KEEPALIVE_SECONDS = 15 * 60
PV_HEALTH_SECONDS = 5 * 60

async def keepalive_loop():
    flog(f"[keepalive] started"); await asyncio.sleep(60)
    pv_check_counter = 0
    while True:
        try:
            for aid, acc in list_accounts().items():
                cli = None
                try:
                    cli, err = await _connect_with_retry(aid, acc["session_string"], name=acc.get("name"), tries=2)
                    if cli:
                        await cli.get_me()
                        flog(f"[keepalive] {aid}: ok")
                except Exception: pass
                finally:
                    if cli:
                        try: await cli._disconnect()
                        except Exception: pass
                await asyncio.sleep(random.uniform(3, 6))

            pv_check_counter += 1
            if pv_check_counter * KEEPALIVE_SECONDS >= PV_HEALTH_SECONDS:
                pv_check_counter = 0
                cfg = _load_pv_items()
                if cfg.get("enabled"):
                    dead = []
                    for aid, t in list(PV_LISTENER_TASKS.items()):
                        if t is None or t.done():
                            dead.append(aid)
                    if dead:
                        flog(f"[pv-health] dead workers: {dead} — restarting")
                        for aid in dead:
                            PV_LISTENER_TASKS.pop(aid, None)
                            st = STATE.get("pv_stops", {}).pop(aid, None)
                            if st:
                                try: st.set()
                                except: pass
                        await start_pv_responders()
                    else:
                        flog(f"[pv-health] all workers alive ({len(PV_LISTENER_TASKS)})")

            await asyncio.sleep(KEEPALIVE_SECONDS)
        except asyncio.CancelledError: raise
        except Exception as e:
            flog(f"[keepalive] err: {type(e).__name__}", "warning")
            await asyncio.sleep(60)


# ═══════════════ UI ═══════════════
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest, RetryAfter
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters as tg_filters)
from telegram.request import HTTPXRequest

HR = "━━━━━━━━━━━━"; PAGE_SIZE = 6

def esc(s): return _html.escape(str(s if s is not None else ""))
def short(s, n=40):
    s = str(s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n-1] + "…"
def B(l, d): return InlineKeyboardButton(l, callback_data=d)
def kb_(*rows): return InlineKeyboardMarkup([list(r) for r in rows if r])

def head(icon, t, sub=None):
    s = f"<b>{icon} {esc(t)}</b>"
    if sub: s += f"  <i>{esc(sub)}</i>"
    return s + "\n" + HR + "\n"

def grid(btns, cols=2):
    return [btns[i:i + cols] for i in range(0, len(btns), cols)]

def nav(back=None, home=True):
    row = []
    if back: row.append(B("⬅️ بازگشت", back))
    if home: row.append(B("🏠 منو", "menu:main"))
    return row

def dots(cur, total):
    return "".join("●" if i <= cur else "○" for i in range(1, total + 1)) + f"  {cur}/{total}"

def _bar(pct, n=14):
    fill = max(0, min(n, round(pct * n / 100)))
    return "█" * fill + "░" * (n - fill)

def _eta(sec):
    sec = int(sec)
    if sec < 60: return f"{sec}ث"
    if sec < 3600: return f"{sec // 60}د"
    return f"{sec // 3600}س {(sec % 3600) // 60}د"

def authorized(update):
    try: return update.effective_chat.id == FORCED_OWNER
    except Exception: return False

_PANEL_SIG: Dict[int, Tuple[int, str]] = {}

def _sig(text, kb):
    try: k = json.dumps(kb.to_dict(), sort_keys=True) if kb else ""
    except Exception: k = repr(kb)
    return hashlib.md5((text + "|" + k).encode()).hexdigest()

async def panel(text, kb=None, page_tag=None):
    cid = STATE.get("owner")
    if not cid or APP is None: return
    if page_tag: _set_page(cid, page_tag)
    text = str(text)[:4000]
    sig = _sig(text, kb)
    mid = STATE["panel"].get(cid)
    if mid:
        if _PANEL_SIG.get(cid) == (mid, sig): return
        try:
            await APP.bot.edit_message_text(chat_id=cid, message_id=mid, text=text, reply_markup=kb,
                                            parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            _PANEL_SIG[cid] = (mid, sig); return
        except BadRequest as e:
            if "not modified" in str(e).lower(): _PANEL_SIG[cid] = (mid, sig); return
        except RetryAfter: return
        except Exception: pass
    for attempt in range(3):
        try:
            m = await APP.bot.send_message(chat_id=cid, text=text, reply_markup=kb,
                                           parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            STATE["panel"][cid] = m.message_id
            _PANEL_SIG[cid] = (m.message_id, sig); return
        except RetryAfter as e: await asyncio.sleep(float(e.retry_after) + 0.5)
        except Exception: await asyncio.sleep(1.5 * (attempt + 1))

async def _autodel(mid, delay=4.0):
    await asyncio.sleep(delay)
    try: await APP.bot.delete_message(chat_id=STATE["owner"], message_id=mid)
    except Exception: pass

async def tg_send(text, markup=None, parse_mode=None):
    if not STATE.get("owner") or APP is None: return False
    text = str(text)[:4000]
    ephemeral = (markup is None and len(text) <= 40)
    for attempt in range(3):
        try:
            m = await APP.bot.send_message(chat_id=STATE["owner"], text=text, reply_markup=markup,
                                           parse_mode=parse_mode or "HTML", disable_web_page_preview=True)
            if ephemeral: asyncio.create_task(_autodel(m.message_id))
            return True
        except RetryAfter as e: await asyncio.sleep(float(e.retry_after) + 0.5)
        except Exception as e:
            if "parse entities" in str(e) and parse_mode: parse_mode = None; continue
            await asyncio.sleep(1.5 * (attempt + 1))
    return False

async def ask(text, note=None):
    body = (f"⚠️ {esc(note)}\n\n" if note else "") + text
    await panel(body, kb_([B("❌ لغو", "conv:cancel")]), page_tag="ask")

def log_cb(msg):
    try:
        try: loop = asyncio.get_running_loop()
        except RuntimeError: loop = _loop_ref[0]
        if loop is None: return
        loop.create_task(tg_send(str(msg)))
    except Exception: pass

def get_conv(cid):
    c = STATE["conv"].get(cid)
    if not c: c = STATE["conv"][cid] = {}
    return c

def clear_conv(cid): STATE["conv"].pop(cid, None)

def _extract_media(msg):
    if msg is None: return None
    try:
        if msg.photo: return msg.photo[-1]
    except Exception: pass
    try:
        if msg.video: return msg.video
    except Exception: pass
    try:
        if msg.animation: return msg.animation
    except Exception: pass
    try:
        if msg.document: return msg.document
    except Exception: pass
    try:
        if msg.audio: return msg.audio
    except Exception: pass
    try:
        if msg.voice: return msg.voice
    except Exception: pass
    try:
        if msg.sticker: return msg.sticker
    except Exception: pass
    return None

async def _download_tg_file(media_obj, aid: str, prefix: str) -> str:
    if APP is None: raise RuntimeError("APP not ready")
    if media_obj is None: raise RuntimeError("no_media")
    file_id = None
    if isinstance(media_obj, (list, tuple)):
        if not media_obj: raise RuntimeError("empty_media_list")
        media_obj = media_obj[-1]
    try: file_id = getattr(media_obj, "file_id", None)
    except Exception: pass
    if not file_id:
        for attr in ("document", "photo", "video", "audio", "voice", "sticker"):
            try:
                sub = getattr(media_obj, attr, None)
                if sub is None: continue
                if isinstance(sub, (list, tuple)) and sub: sub = sub[-1]
                fid = getattr(sub, "file_id", None)
                if fid: file_id = fid; break
            except Exception: continue
    if not file_id:
        flog(f"[download] no file_id in {type(media_obj).__name__}", "error")
        raise RuntimeError(f"no_file_id:{type(media_obj).__name__}")
    f = None
    try:
        f = await APP.bot.get_file(file_id)
    except Exception as e:
        flog(f"[download] bot.get_file fail: {type(e).__name__}: {e}", "error")
        try: f = await media_obj.get_file()
        except Exception as e2: raise RuntimeError(f"get_file_failed:{type(e2).__name__}")
    if f is None: raise RuntimeError("no_file_object")
    ext = ""
    try:
        fp = getattr(f, "file_path", "") or ""
        ext = os.path.splitext(fp)[1]
    except Exception: pass
    if not ext:
        try:
            fn = getattr(media_obj, "file_name", None)
            if fn: ext = os.path.splitext(fn)[1]
        except Exception: pass
    if not ext: ext = ".bin"
    fname = f"{prefix}_{aid}_{int(time.time())}_{secrets.token_hex(3)}{ext}"
    full = os.path.join(UPLOADS_DIR, fname)
    try:
        await f.download_to_drive(full)
    except AttributeError:
        try:
            data = await f.download_as_bytearray()
            with open(full, "wb") as fp: fp.write(bytes(data))
        except Exception:
            try: await f.download(custom_path=full)
            except Exception as e: raise RuntimeError(f"download_failed:{type(e).__name__}")
    if not os.path.exists(full) or os.path.getsize(full) == 0:
        raise RuntimeError("empty_file")
    flog(f"[download] ✅ {os.path.basename(full)} ({os.path.getsize(full)} bytes)")
    return full


async def show_main():
    accounts = list_accounts(); ops = _load_ops()
    running = [o for o in ops if _op_effective_status(o) == "running"]
    listening = sum(1 for t in LISTENER_TASKS.values() if not t.done())
    pv_on = bool(_load_pv_items().get("enabled"))
    errs = len(_load_errors())
    tpls = len(list_templates())
    banned_n = len(_load_banned())
    seen_n = len(_load_seen())
    txt = head("🌀", "پنل سروش", VERSION)
    txt += f"👤 <b>{len(accounts)}</b>   ·   👂 <b>{listening}</b>   ·   🎯 <b>{tpls}</b>\n"
    txt += f"💬 PV: <b>{'🟢' if pv_on else '⚪'}</b>   ·   🔍 seen: <b>{seen_n}</b>   ·   🚫 ban: <b>{banned_n}</b>\n"
    txt += (f"🟢 <b>{len(running)}</b> در حال اجرا" if running else "⚪ فعال نیست")
    err_lbl = "⚠️ خطاها" + (f" ({errs})" if errs else "")
    rows = []
    if running:
        rows.append([B(f"🟢 فعال ({len(running)})", f"op:view:{running[0]['id']}")])
    rows += [
        [B("📤 ارسال", "send:start"), B("🤝 جوینر", "jl:start")],
        [B("🚪 لفتر", "lf:start"), B("🎯 قالب‌ها", "at:menu")],
        [B("📱 اکانت‌ها", "menu:acc"), B("📊 آمار", "menu:stats")],
        [B("👂 لیسنر", "menu:listen"), B("💬 PV", "menu:pv")],
        [B(err_lbl, "menu:errors"), B(f"🔍 Cache ({seen_n}/{banned_n})", "menu:cache")],
    ]
    await panel(txt, kb_(*rows), page_tag="main")

async def show_cache_menu():
    seen = _load_seen(); banned = _load_banned()
    txt = head("🔍", "مدیریت Cache")
    txt += f"🔍 <b>لینک‌های seen:</b> {len(seen)}\n"
    txt += f"🚫 <b>گروه‌های banned:</b> {len(banned)}\n\n"
    txt += "<i>seen = لینک‌هایی که یک‌بار تست شدن</i>\n"
    txt += "<i>banned = گروه‌های مسدود</i>"
    rows = [
        [B("🗑 پاک کردن seen", "cache:clear_seen")],
        [B("🗑 پاک کردن banned", "cache:clear_banned")],
        [B("🗑 پاک کردن هر دو", "cache:clear_all")],
        [B("🔄 ریست progress لینک‌دونی", "cache:reset_ld")],
        [B("🏠 منو", "menu:main")],
    ]
    await panel(txt, kb_(*rows), page_tag="cache")

async def show_pv_menu():
    cfg = _load_pv_items()
    enabled = bool(cfg.get("enabled"))
    delay = int(cfg.get("delay_seconds", 120))
    once = bool(cfg.get("reply_once", True))
    notify_on = bool(cfg.get("notify", True))
    items = cfg.get("items") or []
    txt = head("💬", "پاسخ خودکار PV")
    txt += f"وضعیت: <b>{'🟢 فعال' if enabled else '⚪ خاموش'}</b>\n"
    txt += f"⏱ تایمر: <b>{delay}s</b>  ·  🔁 یک‌بار: <b>{'🟢' if once else '⚪'}</b>\n"
    txt += f"🔔 نوتیف: <b>{'🟢' if notify_on else '⚪'}</b>\n"
    txt += f"📨 پیام‌ها: <b>{len(items)}</b> عدد\n\n"
    if items:
        for i, it in enumerate(items, 1):
            k = it.get("kind", "text")
            if k == "text": txt += f"{i}. 💬 <code>{esc(short(it.get('text', ''), 40))}</code>\n"
            elif k == "forward": txt += f"{i}. 📎 Forward (id:<code>{it.get('message_id', '?')}</code>)\n"
            elif k == "delay": txt += f"{i}. ⏸ تأخیر {it.get('seconds', 3)}s\n"
    else:
        txt += "<i>هیچ پیامی تنظیم نشده</i>\n\n"
        txt += "<i>💡 هر عکس/ویدیو/فایلی که تو همین چت PV بفرستی ذخیره می‌شه</i>"
    rows = [
        [B(("🔴 خاموش کن" if enabled else "🟢 روشن کن"), "pv:toggle")],
        [B(("🔔 نوتیف روشن" if notify_on else "🔕 نوتیف خاموش"), "pv:toggle_notify")],
        [B("⏱ تایمر", "pv:set_delay"), B("🔁 یک‌بار" + (" ✅" if once else ""), "pv:toggle_once")],
        [B("➕ متن", "pv:add_text")],
        [B("📎 ذخیره پیام (فایل/عکس)", "pv:add_saved")],
        [B("⏸ تأخیر", "pv:add_delay")],
    ]
    if items:
        rows.append([B("📋 مشاهده/حذف", "pv:list")])
        rows.append([B("🗑 پاک کردن همه", "pv:clear")])
    rows.append([B("📊 گزارش PV", "pv:report:0")])
    rows.append([B("🧪 تست اتصال PV", "pv:test")])
    rows.append([B("🔄 ری‌استارت", "pv:restart")])
    rows.append([B("🧹 پاک replied cache", "pv:clear_replies")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="pv_menu")

async def show_pv_list():
    cfg = _load_pv_items()
    items = cfg.get("items") or []
    txt = head("📋", f"پیام‌های PV ({len(items)})")
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"\n{i}. 💬 <code>{esc(short(it.get('text', ''), 60))}</code>"
        elif k == "forward": txt += f"\n{i}. 📎 Forward id=<code>{it.get('message_id', '?')}</code>"
        elif k == "delay": txt += f"\n{i}. ⏸ <b>{it.get('seconds', 3)}s</b>"
    rows = []
    for i in range(len(items)):
        rows.append([B(f"🗑 {i+1}", f"pv:del:{i}")])
    rows.append([B("⬅️", "pv:menu")])
    await panel(txt, kb_(*rows), page_tag="pv_list")


async def show_pv_report(page=0):
    rep = _load_pv_report()
    total_users = 0; total_replied = 0; total_ok = 0; total_blocked = 0
    rows_data = []
    accounts = list_accounts()
    for aid, users in rep.items():
        if not users: continue
        acc_name = (accounts.get(aid) or {}).get("name", aid)
        for uid, data in users.items():
            total_users += 1
            if data.get("replied"): total_replied += 1
            if data.get("reply_ok"): total_ok += 1
            if data.get("blocked"): total_blocked += 1
            rows_data.append({
                "aid": aid, "acc_name": acc_name, "uid": uid,
                "first_name": data.get("first_name") or "",
                "username": data.get("username") or "",
                "count": data.get("count", 1),
                "replied": data.get("replied", False),
                "reply_ok": data.get("reply_ok", False),
                "blocked": data.get("blocked", False),
                "error": data.get("error"),
                "first_seen": data.get("first_seen", 0),
                "last_seen": data.get("last_seen", 0),
                "replied_at": data.get("replied_at"),
            })
    rows_data.sort(key=lambda x: x["last_seen"], reverse=True)
    PER = 8
    pages = max(1, -(-len(rows_data) // PER))
    page = max(0, min(page, pages - 1))
    chunk = rows_data[page * PER:(page + 1) * PER]
    txt = head("📊", f"گزارش PV ({total_users})")
    txt += f"✅ <b>موفق:</b> {total_ok}   ·   📨 <b>پاسخ:</b> {total_replied}\n"
    txt += f"🚫 <b>بلاک:</b> {total_blocked}   ·   📄 {page+1}/{pages}\n"
    txt += HR + "\n\n"
    if not chunk:
        txt += "<i>هنوز کسی به PV نیومده</i>"
    else:
        for r in chunk:
            name = r["first_name"] or "?"
            un = f"@{r['username']}" if r["username"] else "—"
            status = []
            if r["replied"]:
                status.append("✅" if r["reply_ok"] else "❌")
            else:
                status.append("⏳")
            if r["blocked"]: status.append("🚫")
            status_str = " ".join(status)
            ago = int(time.time() - r["last_seen"])
            ago_str = _eta(ago) if ago > 0 else "الان"
            txt += f"👤 <b>{esc(short(name, 20))}</b>  ·  {esc(un)}\n"
            txt += f"   {status_str}  ·  📨×{r['count']}  ·  <i>{ago_str}</i>\n"
            if r.get("error"):
                txt += f"   <code>{esc(short(r['error'], 40))}</code>\n"
            txt += f"   🆔 <code>{esc(r['uid'])}</code>\n\n"
    nav_btns = []
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"pv:report:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("▶️", f"pv:report:{page+1}"))
        nav_btns.append(pr)
    nav_btns.append([B("🔄 بروزرسانی", f"pv:report:{page}")])
    nav_btns.append([B("🗑 پاک کردن گزارش", "pv:report_clear")])
    nav_btns.append([B("⬅️ بازگشت", "pv:menu")])
    await panel(txt, kb_(*nav_btns), page_tag=f"pv_report:{page}")


def _acc_label(aid, a):
    st = _STATS_CACHE.get(aid, {}).get("data") or {}
    return f"📱 {short(a.get('name', '?'), 16)} · 👥{st.get('groups', '…')} · 💬{st.get('pvs', '…')}"

def _accounts_view(page):
    accounts = list_accounts(); items = list(accounts.items())
    pages = max(1, -(-len(items) // PAGE_SIZE)); page = max(0, min(page, pages - 1))
    chunk = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    rows = [[B(_acc_label(aid, a), f"acc:view:{aid}")] for aid, a in chunk]
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"acc:page:{page - 1}"))
        pr.append(B(f"{page + 1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("▶️", f"acc:page:{page + 1}"))
        rows.append(pr)
    rows.append([B("➕ افزودن", "acc:add"), B("🔄 آمار", "acc:refresh")])
    rows.append(nav())
    txt = head("📱", f"اکانت‌ها ({len(accounts)})")
    txt += "خالی" if not accounts else "<i>👥 گروه · 💬 خصوصی</i>"
    return txt, kb_(*rows), f"acc_list:{page}", chunk

async def show_accounts(page=0):
    txt, kb, tag, chunk = _accounts_view(page)
    await panel(txt, kb, page_tag=tag)
    if chunk:
        stale = any(aid not in _STATS_CACHE or (time.time() - _STATS_CACHE[aid].get("ts", 0)) > 120 for aid, _ in chunk)
        if stale: asyncio.create_task(_bg_fetch_stats(page, 0, tag))

async def _bg_fetch_stats(page, pages, tag):
    try:
        _, _, _, chunk = _accounts_view(page)
        async def one(aid):
            try: await asyncio.wait_for(get_account_stats(aid), timeout=25)
            except Exception: pass
        await asyncio.gather(*[one(aid) for aid, _ in chunk])
        cid = STATE.get("owner")
        if not cid or not _is_page(cid, tag): return
        txt, kb, tag2, _ = _accounts_view(page)
        await panel(txt, kb, page_tag=tag2)
    except Exception: pass

async def show_account_detail(aid):
    tag = f"acc:{aid}"
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    t = LISTENER_TASKS.get(aid); on = bool(t and not t.done())
    pvt = PV_LISTENER_TASKS.get(aid); pvon = bool(pvt and not pvt.done())
    st = _STATS_CACHE.get(aid, {}).get("data") or {}
    g = lambda k: st.get(k, "…")
    txt = head("📱", a.get("name", "?"))
    txt += f"📞 <code>{esc(a.get('phone', '—'))}</code>\n"
    txt += f"👥 <b>{g('groups')}</b>  ·  💬 <b>{g('pvs')}</b>  ·  📢 <b>{g('channels')}</b>  ·  🤖 <b>{g('bots')}</b>\n"
    txt += f"✨ کانال ساخته: <b>{len(get_stored_channels(aid))}</b>\n"
    txt += f"👂 <b>{'🟢' if on else '⚪'}</b>   ·   💬 PV <b>{'🟢' if pvon else '⚪'}</b>"
    rows = grid([
        B("🎯 Auto-Tar", f"acc:at:{aid}"), B("📢 کانال‌ها", f"ch:menu:{aid}"),
        B("📝 پروفایل", f"prof:menu:{aid}"), B("👂 " + ("خاموش" if on else "روشن"), f"listen:toggle:{aid}"),
        B("🔄 بروزرسانی", f"acc:refresh_one:{aid}"), B("🚪 لفتر", f"acc:lf:{aid}"),
        B("🖼 عکس پروفایل", f"accphoto:menu:{aid}"), B("💬 PV", "menu:pv"),
    ])
    rows.append([B("🗑 حذف اکانت", f"acc:del:{aid}")])
    rows.append(nav("menu:acc"))
    await panel(txt, kb_(*rows), page_tag=tag)
    if (time.time() - (st.get("ts") or 0)) > 120:
        asyncio.create_task(_bg_refresh_one(aid, tag))

async def _bg_refresh_one(aid, tag):
    try:
        await asyncio.wait_for(get_account_stats(aid), timeout=30)
        cid = STATE.get("owner")
        if not cid or not _is_page(cid, tag): return
        await show_account_detail(aid)
    except Exception: pass

async def show_profile_menu(aid):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    rows = grid([
        B("👤 نام", f"prof:set:first:{aid}"), B("👤 نام‌خانوادگی", f"prof:set:last:{aid}"),
        B("📖 بیو", f"prof:set:about:{aid}"), B("🔤 یوزرنیم", f"prof:set:username:{aid}"),
        B("🖼 عکس پروفایل", f"accphoto:menu:{aid}"),
    ])
    rows.append(nav(f"acc:view:{aid}"))
    await panel(head("📝", "پروفایل", a.get("name", "?")) + f"📞 <code>{esc(a.get('phone', '—'))}</code>",
                kb_(*rows), page_tag=f"prof:{aid}")

async def show_acc_photo_menu(aid):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    txt = head("🖼", "عکس پروفایل", a.get("name", "?"))
    txt += "عکس رو بفرست، ربات آپلود و تنظیم می‌کنه."
    rows = [
        [B("🖼 تنظیم عکس جدید", f"accphoto:set:{aid}")],
        [B("🗑 حذف عکس‌ها", f"accphoto:del:{aid}")],
        nav(f"acc:view:{aid}"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"accphoto:{aid}")

async def show_ch_photo_menu(aid, idx):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    chs = get_stored_channels(aid)
    if idx < 0 or idx >= len(chs): return await show_ch_list(aid)
    ch = chs[idx]
    txt = head("🖼", "عکس کانال", ch.get("title", "?"))
    txt += "عکس رو بفرست، ربات آپلود و تنظیم می‌کنه."
    rows = [
        [B("🖼 تنظیم عکس جدید", f"chphoto:set:{aid}:{idx}")],
        [B("🗑 حذف عکس‌ها", f"chphoto:del:{aid}:{idx}")],
        nav(f"ch:view:{aid}:{idx}"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"chphoto:{aid}:{idx}")

def _ch_link(ch):
    un = (ch.get("username") or "").lstrip("@")
    return ch.get("join_link") or (f"https://splus.ir/{un}" if un else "")

async def show_ch_menu(aid):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    n = len(get_stored_channels(aid))
    txt = head("📢", "کانال‌ها", a.get("name", "?")) + f"✨ ساخته‌شده: <b>{n}</b>"
    rows = [[B(f"📋 کانال‌های من ({n})", f"chlist:show:{aid}:0")],
            [B("🏗 ساخت کانال جدید", f"chnew:start:{aid}")],
            nav(f"acc:view:{aid}")]
    await panel(txt, kb_(*rows), page_tag=f"ch_menu:{aid}")

async def show_ch_list(aid, page=0):
    channels = get_stored_channels(aid); per = 6
    pages = max(1, -(-len(channels) // per)); page = max(0, min(page, pages - 1))
    rows = []
    for idx, ch in list(enumerate(channels))[page * per:(page + 1) * per]:
        icon = "🌐" if (ch.get("type") == "public" or ch.get("username")) else "🔒"
        lbl = f"{icon} {short(ch.get('title', '?'), 24)}"
        if ch.get("username"): lbl += f" · @{ch['username']}"
        rows.append([B(lbl, f"ch:view:{aid}:{idx}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"chlist:show:{aid}:{page - 1}"))
        pr.append(B(f"{page + 1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("▶️", f"chlist:show:{aid}:{page + 1}"))
        rows.append(pr)
    rows.append([B("🏗 ساخت کانال", f"chnew:start:{aid}")])
    rows.append(nav(f"ch:menu:{aid}"))
    txt = head("📋", f"کانال‌های من ({len(channels)})")
    txt += "هنوز کانالی نساختی." if not channels else "<i>کانال‌هایی که با این ربات ساختی</i>"
    await panel(txt, kb_(*rows), page_tag=f"chlist:{aid}:{page}")

async def show_channel_view(aid, idx):
    if not get_account(aid): return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return await show_ch_list(aid)
    ch = channels[idx]
    un = ch.get("username") or ""
    is_pub = ch.get("type") == "public" or bool(un)
    link = _ch_link(ch)
    txt = head("📢", ch.get("title") or "?")
    txt += ("🌐 عمومی" + (f" · @{esc(un)}" if un else "") if is_pub else "🔒 خصوصی") + "\n"
    txt += f"🔗 <code>{esc(link)}</code>" if link else "🔗 <i>لینک ثبت نشده</i>"
    rows = grid([
        B("📤 ارسال", f"chsend:start:{aid}:{idx}"), B("📝 پروفایل", f"chprof:show:{aid}:{idx}"),
        B("🔗 دریافت لینک", f"ch:getlink:{aid}:{idx}"), B("✍️ ثبت لینک", f"ch:setlink:{aid}:{idx}"),
        B("🖼 عکس کانال", f"chphoto:menu:{aid}:{idx}"), B("📎 ارسال فایل", f"chfile:start:{aid}:{idx}"),
        B("🔍 عیب‌یابی", f"ch:diag:{aid}:{idx}"), B("🗑 حذف", f"ch:del:{aid}:{idx}"),
    ])
    rows.append(nav(f"chlist:show:{aid}:0"))
    await panel(txt, kb_(*rows), page_tag=f"chview:{aid}:{idx}")

def _ch_profile_view(aid, idx, ch, info, err=None, loading=False):
    title = info.get("title") or ch.get("title") or "?"
    un = info.get("username") or ch.get("username") or ""
    desc = info.get("description") or ch.get("description") or ""
    members = info.get("members")
    link = ch.get("join_link") or info.get("join_link") or (f"https://splus.ir/{un}" if un else "")
    txt = head("📝", title) + ("🌐 عمومی" if un else "🔒 خصوصی") + "\n\n"
    if un: txt += f"🔤 @{esc(un)}\n"
    txt += f"🔗 <code>{esc(link)}</code>\n" if link else "🔗 <i>ثبت نشده</i>\n"
    txt += "📖 " + (esc(desc[:200]) if desc else "—") + "\n"
    if members is not None: txt += f"👥 <b>{members}</b> عضو\n"
    if loading: txt += "\n⏳ <i>...</i>"
    elif err: txt += f"\n⚠️ <i>{esc(str(err)[:150])}</i>"
    rows = grid([
        B("✏️ نام", f"chprof:edit:title:{aid}:{idx}"), B("📖 توضیحات", f"chprof:edit:about:{aid}:{idx}"),
        B("🔤 یوزرنیم", f"chprof:edit:username:{aid}:{idx}"), B("🔗 دریافت لینک", f"ch:getlink:{aid}:{idx}"),
        B("✍️ ثبت لینک", f"ch:setlink:{aid}:{idx}"), B("🔄 بروزرسانی", f"chprof:show:{aid}:{idx}"),
    ])
    rows.append(nav(f"ch:view:{aid}:{idx}"))
    return txt, kb_(*rows)

async def show_ch_profile(aid, idx):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return await show_ch_list(aid)
    ch = channels[idx]; tag = f"chprof:{aid}:{idx}"
    txt, kb = _ch_profile_view(aid, idx, ch, dict(ch), loading=True)
    await panel(txt, kb, page_tag=tag)
    info = dict(ch); err = None
    cli = None
    try:
        cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=2)
        if cli:
            info = await _get_full_channel_info(cli, ch, aid)
            if info.get("error"): err = info.get("error")
        else: err = f"اتصال: {err}"
    except Exception as e: err = f"{type(e).__name__}: {_fmt_error(e)}"
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass
    cid = STATE.get("owner")
    if not cid or not _is_page(cid, tag): return
    txt, kb = _ch_profile_view(aid, idx, ch, info, err=err)
    await panel(txt, kb, page_tag=tag)

async def show_ch_new_type(aid, title):
    await panel(head("🏗", "ساخت کانال") + f"📝 <b>{esc(title)}</b>\n\nنوع کانال؟",
                kb_([B("🌐 عمومی", f"chnew:pub:{aid}"), B("🔒 خصوصی", f"chnew:priv:{aid}")],
                    [B("❌ لغو", f"ch:menu:{aid}")]),
                page_tag=f"chnew_type:{aid}")

async def show_listen_menu():
    accounts = list_accounts()
    txt = head("👂", "لیسنر")
    btns = []
    for aid, a in accounts.items():
        t = LISTENER_TASKS.get(aid); run = t is not None and not t.done()
        btns.append(B(f"{'🟢' if run else '⚪'} {short(a.get('name', '?'), 14)}", f"listen:toggle:{aid}"))
    rows = grid(btns)
    rows.append([B("🔄 ری‌استارت همه", "listen:restart")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="listen")

async def show_linkdonies(back_to: str = "jl:back_to_settings"):
    lst = load_link_donies()
    auto = int(_load(CFG_FILE, DEFAULT_CFG).get("auto_join_linkdoni", 1))
    prog = _load_ldprog()
    txt = head("📡", f"لینک‌دونی‌ها ({len(lst)})") + f"🔁 auto-join: <b>{'🟢' if auto else '🔴'}</b>\n"
    txt += f"📊 progress: <b>{len(prog)}</b> لینک‌دونی\n\n"
    for i, url in enumerate(lst):
        last = _get_ld_last(url)
        txt += f"{i + 1}. <code>{esc(url)}</code>"
        if last > 0: txt += f" · <i>last={last}</i>"
        txt += "\n"
    rows = grid([B(f"🗑 {i + 1}. {short(u.split('/')[-1], 12)}", f"ld:del:{i}:{back_to}") for i, u in enumerate(lst)])
    rows.append([B("➕ افزودن", f"ld:add:{back_to}"),
                 B("🔴 خاموش" if auto else "🟢 روشن", f"ld:toggle_autojoin:{back_to}")])
    rows.append([B("🔄 بازنشانی progress", f"ld:reset_prog:{back_to}")])
    rows.append([B("🔄 بازنشانی لیست", f"ld:reset:{back_to}")])
    rows.append(nav(back_to, home=False))
    await panel(txt, kb_(*rows), page_tag="linkdonies")

_OP_LAST: Dict[str, float] = {}

def _op_view(op):
    oid = op["id"]; t = op.get("type")
    st = _op_effective_status(op); s = _op_stats(op); p = op.get("progress") or {}
    tot = s["total"] or 0; proc = s["done"] + s["failed"]
    pct = min(100, int(proc * 100 / tot)) if tot else 0
    icon = {"joinlef": "🤝", "lefter": "🚪", "autotar": "🎯", "send": "📤"}.get(t, "⚙️")
    label = {"joinlef": "Joiner", "lefter": "Lefter", "autotar": "Auto-Tar", "send": "ارسال"}.get(t, "?")
    txt = head(icon, label, oid[-6:])
    txt += f"{_op_status_icon(st)} <b>{esc(_op_status_label(st))}</b>\n"
    txt += f"<code>{_bar(pct)} {pct}%</code>\n\n"
    if t == "joinlef":
        txt += f"✅ <b>{s['done']}</b>   ❌ <b>{s['failed']}</b>"
        if op.get("max_join"): txt += f"   🎯 <b>{op['max_join']}</b>"
        ss = s.get("skipped_seen", 0); sb = s.get("skipped_banned", 0); rj = s.get("rejected", 0)
        if ss or sb or rj:
            txt += f"\n🔍 seen: {ss} · 🚫 ban: {sb} · 🟡 غیرفعال: {rj}"
    elif t == "lefter":
        txt += f"🚪 <b>{s['done']}</b> ترک   ❌ <b>{s['failed']}</b>"
    elif t == "autotar":
        tpl = get_template(op.get("template_id"))
        if tpl: txt += f"📋 <b>{esc(tpl.get('name', '?'))}</b>\n\n"
        jj = s["done"]; al = s.get("already", 0); ss = s.get("sent", 0)
        ff = s["failed"]; ll = s.get("left", 0)
        wv = s.get("wave", 0); tr = s.get("tried", 0)
        skip_s = s.get("skipped_seen", 0); skip_b = s.get("skipped_banned", 0)
        rej = s.get("rejected", 0)
        txt += f"🤝 <b>جوین جدید:</b> {jj}"
        if al: txt += f"   ·   ♻️ قبلاً: {al}"
        txt += "\n"
        if ss: txt += f"📤 <b>ارسال:</b> {ss}\n"
        if ll: txt += f"🚪 <b>ترک:</b> {ll}\n"
        if tr: txt += f"🔗 <b>امتحان:</b> {tr}\n"
        if skip_s: txt += f"🔍 <b>seen (رد):</b> {skip_s}\n"
        if skip_b: txt += f"🚫 <b>banned (رد):</b> {skip_b}\n"
        if rej: txt += f"🟡 <b>غیرفعال (left):</b> {rej}\n"
        if ff: txt += f"❌ <b>خطا:</b> {ff}\n"
        if wv: txt += f"🌊 <b>موج:</b> {wv}"
    else:
        txt += f"✅ <b>{s['done']}</b>   ❌ <b>{s['failed']}</b>   ⏳ <b>{s['pending']}</b>"
        blk = p.get("blocked", 0); rnd = p.get("round", 0)
        if blk: txt += f"\n🚫 <b>بلاک:</b> {blk}"
        if rnd: txt += f"   ·   🔁 <b>دور:</b> {rnd}"
        if op.get("infinite_loop"): txt += f"\n🔁 <i>لوپ بی‌نهایت فعال</i>"
    if st == "running" and proc > 0 and tot > proc:
        el = max(1, time.time() - op.get("created", time.time()))
        txt += f"\n⏱ حدود <b>{_eta(el / proc * (tot - proc))}</b>"
    txt += f"\n\n📍 <i>{esc(p.get('phase', '—'))}</i>"
    rows = []
    if st == "running": rows.append([B("⏹ توقف", f"op:stop:{oid}")])
    rows.append([B("⬅️ آمار", "menu:stats"), B("🏠 منو", "menu:main")])
    return txt, kb_(*rows)

async def _refresh_op_panel(op_id, force: bool = False):
    try:
        op = _get_op(op_id); cid = STATE.get("owner")
        if not op or not cid: return
        if not force:
            if STATE.get("op_panel", {}).get(cid) != op_id: return
            if not _is_page(cid, f"op:{op_id}"): return
            if _op_effective_status(op) == "running":
                now = time.time()
                if now - _OP_LAST.get(op_id, 0) < 1.5: return
                _OP_LAST[op_id] = now
        txt, kb = _op_view(op)
        await panel(txt, kb, page_tag=f"op:{op_id}")
    except Exception: pass

async def show_op_detail(oid):
    op = _get_op(oid)
    if not op: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    cid = STATE.get("owner")
    if cid: STATE.setdefault("op_panel", {})[cid] = oid
    txt, kb = _op_view(op)
    await panel(txt, kb, page_tag=f"op:{oid}")

async def show_stats():
    ops = _load_ops(); ops.sort(key=lambda o: o.get("created", 0), reverse=True)
    errs = _load_errors()
    done = sum(_op_stats(o)["done"] for o in ops); failed = sum(_op_stats(o)["failed"] for o in ops)
    running = [o for o in ops if _op_effective_status(o) == "running"]
    txt = head("📊", "آمار")
    txt += f"✅ <b>{done}</b>   ❌ <b>{failed}</b>   ⚠️ <b>{len(errs)}</b>\n"
    if running:
        txt += "\n<b>🟢 در حال اجرا</b>\n"
        for o in running[:3]:
            s = _op_stats(o)
            txt += f"• {esc(_op_short_title(o, 22))}  ✅{s['done']} ❌{s['failed']}\n"
    rows = []
    for o in ops[:8]:
        s = _op_stats(o); prog = f"{s['done']}/{s['total']}" if s["total"] else "—"
        rows.append([B(f"{_op_status_icon(_op_effective_status(o))} {short(_op_short_title(o, 20), 22)} · {prog}",
                       f"op:view:{o['id']}")])
    rows.append([B("⚠️ خطاها", "menu:errors"), B("🏠 منو", "menu:main")])
    await panel(txt, kb_(*rows), page_tag="stats")

async def show_errors(page=0):
    errors = list(reversed(_load_errors()))
    if not errors:
        return await panel(head("⚠️", "خطاها") + "خالیه", kb_(nav()), page_tag="errors")
    PER = 4; pages = max(1, -(-len(errors) // PER)); page = max(0, min(page, pages - 1))
    txt = head("⚠️", f"خطاها ({len(errors)})")
    for e in errors[page * PER:(page + 1) * PER]:
        t = time.strftime("%m/%d %H:%M", time.localtime(e.get("time", 0)))
        txt += f"\n🕐 <code>{esc(t)}</code> · <b>{esc(e.get('source', '?'))}</b>\n<code>{esc(str(e.get('error', ''))[:220])}</code>\n"
    rows = []
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"err:page:{page - 1}"))
        pr.append(B(f"{page + 1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("▶️", f"err:page:{page + 1}"))
        rows.append(pr)
    rows.append([B("🗑 پاک", "err:clear"), B("🏠 منو", "menu:main")])
    await panel(txt, kb_(*rows), page_tag=f"errors:{page}")


# ═══════════════ SEND WIZARD ═══════════════
def _send_conv(cid):
    c = get_conv(cid)
    if "send" not in c:
        c["send"] = {"step": "accounts", "accounts": [], "payload": None,
                     "target": "both", "max": 0, "auto_left": False,
                     "edit_delay_enabled": False, "edit_delay_seconds": 3.0,
                     "edit_delay_random": False, "edit_delay_min": 2.0, "edit_delay_max": 6.0,
                     "placeholder_text": "سلام", "placeholder_random": False,
                     "placeholder_list": "سلام,درود,hi,salam",
                     "multi_step_edit": False, "multi_step_middle": "Hi",
                     "attach_file": "", "groups_only": True,
                     "infinite_loop": False, "loop_delay": 3.0}
    return c["send"]

def _send_summary(s):
    accs = s.get("accounts") or []; all_a = list_accounts()
    if "all" in accs: al = f"همه ({len(all_a)})"
    elif not accs: al = "—"
    else:
        names = [get_account(i).get("name", "?") for i in accs[:2] if get_account(i)]
        al = "، ".join(names) + (f" +{len(accs) - 2}" if len(accs) > 2 else "")
    p = s.get("payload")
    tgt = {"pv": "خصوصی", "groups": "گروه‌ها", "both": "هر دو"}.get(s.get("target", "both"), "?")
    mx = s.get("max", 0) or 0
    al_ = "🟢" if s.get("auto_left") else "⚪"
    ed = "🟢" if s.get("edit_delay_enabled") else "⚪"
    af = "🟢" if s.get("attach_file") else "⚪"
    inf = "🔁" if s.get("infinite_loop") else "⚪"
    return (f"\n👤 {esc(al)}\n✉️ " + (f"«{esc(short(p.get('text'), 30))}»" if p else "—") +
            f"\n🎯 {esc(tgt)}   ·   🔢 {mx if mx else '∞'}\n🎭 Edit: {ed}   ·   📎: {af}   ·   Loop: {inf}")

async def send_step_accounts(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel("⚠️ اول اکانت اضافه کن.", kb_([B("➕", "acc:add")], nav()), page_tag="send:1")
    sel = set(s.get("accounts") or []); all_sel = "all" in sel
    btns = [B(f"{'☑' if (all_sel or aid in sel) else '☐'} {short(a.get('name', '?'), 14)}", f"send:acc:{aid}")
            for aid, a in accounts.items()]
    rows = grid(btns)
    rows.append([B("✅ لغو همه" if all_sel else "☑ همه", "send:accall"), B("▶️ بعدی", "send:accnext")])
    rows.append([B("❌ لغو", "send:cancel")])
    await panel(head("📤", "ارسال", dots(1, 4)) + "اکانت(ها)\n" + _send_summary(s),
                kb_(*rows), page_tag="send:1")

async def send_step_compose(cid, s):
    txt = head("📤", "ارسال", dots(2, 4)) + "✍️ متن را بفرست\n" + _send_summary(s)
    rows = []
    if s.get("payload"): rows.append([B("✏️ تغییر", "send:recompose"), B("▶️ بعدی", "send:composenext")])
    rows.append([B("⬅️ بازگشت", "send:prev"), B("❌ لغو", "send:cancel")])
    await panel(txt, kb_(*rows), page_tag="send:2")

async def send_step_target(cid, s):
    t = s.get("target", "both")
    mk = lambda k, l: B(("✅ " if t == k else "") + l, f"send:tgt:{k}")
    ed_on = bool(s.get("edit_delay_enabled", False))
    ed_sec = s.get("edit_delay_seconds", 3.0)
    grp_only = bool(s.get("groups_only", True))
    inf_on = bool(s.get("infinite_loop", False))
    ld = s.get("loop_delay", 3.0)
    af = s.get("attach_file") or ""
    rows = [[mk("pv", "💬 خصوصی"), mk("groups", "👥 گروه"), mk("both", "📨 هر دو")],
            [B(("🟢 " if grp_only else "⚪ ") + "فقط گروه‌های واقعی", "send:toggle_groups_only")],
            [B(("🟢 " if inf_on else "⚪ ") + "🔁 لوپ بی‌نهایت", "send:toggle_infinite")],
            [B(f"⏱ بین دورها: {ld}s", "send:loop_delay")],
            [B(("🟢 " if ed_on else "⚪ ") + "Edit-Delay", "send:toggle_edit")],
            [B(f"⏱ {ed_sec}s", "send:edit_sec"), B("🎲 تاخیر تصادفی", "send:toggle_edit_rand")],
            [B(f"💬 {esc(short(s.get('placeholder_text', 'سلام'), 10))}", "send:edit_ph"),
             B("🎲 لیست", "send:toggle_ph_rand")],
            [B(("🟢 " if s.get("multi_step_edit") else "⚪ ") + "Multi-step", "send:toggle_multi")],
            [B(f"📎 فایل: {esc(short(os.path.basename(af), 15) if af else 'خالی')}", "send:attach")],
            [B(("🟢 " if s.get("auto_left") else "⚪ ") + "AutoLeave", "send:toggle_auto_left")],
            [B("▶️ بعدی", "send:tgtnext")],
            [B("⬅️ بازگشت", "send:prev"), B("❌ لغو", "send:cancel")]]
    await panel(head("📤", "ارسال", dots(3, 4)) + "مقصد؟\n" + _send_summary(s), kb_(*rows), page_tag="send:3")

async def send_step_max(cid, s):
    mx = s.get("max", 0)
    mk = lambda n: B(("✅ " if mx == n else "") + str(n), f"send:max:{n}")
    rows = [[mk(50), mk(100), mk(500)], [mk(1000), mk(2000), mk(5000)],
            [B(("✅ " if mx == 0 else "") + "♾", "send:max:0"), B("✏️ دلخواه", "send:max:custom")],
            [B("▶️ تایید", "send:maxnext")],
            [B("⬅️ بازگشت", "send:prev"), B("❌ لغو", "send:cancel")]]
    await panel(head("📤", "ارسال", dots(4, 4)) + "حداکثر تعداد؟\n" + _send_summary(s), kb_(*rows), page_tag="send:4")

async def send_step_confirm(cid, s):
    accounts = list_accounts(); sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "accounts"; return await panel("⚠️ اکانت انتخاب نشده.", kb_(nav()), page_tag="send:1")
    if not s.get("payload"):
        s["step"] = "compose"; return await panel("⚠️ پیام تنظیم نشده.", kb_(nav()), page_tag="send:2")
    extra = ""
    if s.get("infinite_loop"):
        extra = f"\n🔁 <b>لوپ بی‌نهایت</b>  ·  ⏱ {s.get('loop_delay', 3)}s"
    await panel(head("📤", "تایید") + _send_summary(s) + extra,
                kb_([B("🚀 شروع", "send:go")],
                    [B("✏️ ویرایش", "send:back_edit"), B("❌ لغو", "send:cancel")]),
                page_tag="send:confirm")

async def show_send_step(cid):
    s = _send_conv(cid); step = s["step"]
    if step == "accounts":   await send_step_accounts(cid, s)
    elif step == "compose":  await send_step_compose(cid, s)
    elif step == "target":   await send_step_target(cid, s)
    elif step == "max":      await send_step_max(cid, s)
    elif step == "confirm":  await send_step_confirm(cid, s)


# ═══════════════ JOINER UI ═══════════════
def _jl_conv(cid):
    c = get_conv(cid)
    if "jl" not in c:
        c["jl"] = {"step": "account", "accounts": [], "max_join": 0,
                   "speed": "fast", "auto_left": False, "groups_only": True}
    return c["jl"]

async def jl_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel("⚠️ اول اکانت اضافه کن.", kb_([B("➕", "acc:add")], nav()), page_tag="jl:1")
    sel = set(s.get("accounts") or [])
    rows = grid([B(f"{'☑' if aid in sel else '☐'} {short(a.get('name', '?'), 14)}", f"jl:acc:{aid}")
                 for aid, a in accounts.items()])
    rows.append([B("▶️ ادامه", "jl:next")]); rows.append([B("🏠 منو", "menu:main")])
    await panel(head("🤝", "Joiner", dots(1, 3)) + f"کدام اکانت؟  <b>{len(sel)}</b>",
                kb_(*rows), page_tag="jl:1")

async def jl_step_settings(cid, s):
    speed = s.get("speed", "fast"); lds = load_link_donies()
    lbl = next((l for k, l, _ in JL_SPEEDS if k == speed), "—")
    al = "🟢" if s.get("auto_left") else "⚪"
    grp = "🟢" if s.get("groups_only", True) else "⚪"
    txt = (head("🤝", "Joiner", dots(2, 3))
           + f"🚀 سرعت: <b>{lbl}</b>\n📡 لینک‌دونی: <b>{len(lds)}</b>\n🚪 Auto-leave: <b>{al}</b>\n"
           + f"👥 فقط گروه واقعی: <b>{grp}</b>")
    rows = grid([B(("✅ " if speed == k else "") + l, f"jl:speed:{k}") for k, l, _ in JL_SPEEDS])
    rows.append([B(f"📡 لینک‌دونی ({len(lds)})", "jl:linkdonies"),
                 B("🚪 Auto-leave" + (" ✅" if s.get("auto_left") else ""), "jl:toggle_auto_left")])
    rows.append([B("👥 فقط گروه‌های واقعی" + (" ✅" if s.get("groups_only", True) else ""), "jl:toggle_groups_only")])
    rows.append([B("▶️ ادامه", "jl:next")])
    rows.append(nav("jl:back"))
    await panel(txt, kb_(*rows), page_tag="jl:2")

async def jl_step_max(cid, s):
    mx = s.get("max_join", 0)
    mk = lambda n: B(("✅ " if mx == n else "") + str(n), f"jl:max:{n}")
    txt = head("🤝", "Joiner", dots(3, 3)) + "چند گروه؟" + (f"\n✅ انتخاب: <b>{mx}</b>" if mx else "")
    rows = [[mk(50), mk(100), mk(200)], [mk(500), mk(1000), mk(2000)], [B("✏️ دلخواه", "jl:max:custom")]]
    if mx: rows.append([B("🚀 شروع", "jl:go")])
    rows.append(nav("jl:back"))
    await panel(txt, kb_(*rows), page_tag="jl:3")

async def show_jl_step(cid):
    s = _jl_conv(cid)
    if s["step"] == "account":  await jl_step_account(cid, s)
    if s["step"] == "settings": await jl_step_settings(cid, s)
    if s["step"] == "max":      await jl_step_max(cid, s)


# ═══════════════ LEFTER UI ═══════════════
def _lf_conv(cid):
    c = get_conv(cid)
    if "lf" not in c:
        c["lf"] = {"step": "account", "accounts": [], "mode": "all", "delay": 0.8}
    return c["lf"]

LF_MODES = [
    ("all", "🌐 همه گروه‌ها و کانال‌ها"),
    ("groups", "👥 فقط گروه‌ها"),
    ("channels", "📢 فقط کانال‌ها"),
    ("closed", "🔒 فقط گروه‌های بسته/غیرفعال"),
]

async def lf_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel("⚠️ اول اکانت اضافه کن.", kb_([B("➕", "acc:add")], nav()), page_tag="lf:1")
    sel = set(s.get("accounts") or [])
    rows = grid([B(f"{'☑' if aid in sel else '☐'} {short(a.get('name', '?'), 14)}", f"lf:acc:{aid}")
                 for aid, a in accounts.items()])
    rows.append([B("▶️ ادامه", "lf:next")]); rows.append([B("🏠 منو", "menu:main")])
    await panel(head("🚪", "Lefter", dots(1, 3)) + f"کدام اکانت؟  <b>{len(sel)}</b>",
                kb_(*rows), page_tag="lf:1")

async def lf_step_mode(cid, s):
    mode = s.get("mode", "all")
    btns = [B(("✅ " if mode == k else "") + l, f"lf:mode:{k}") for k, l in LF_MODES]
    rows = [[b] for b in btns]
    rows.append([B("▶️ ادامه", "lf:next")])
    rows.append(nav("lf:back"))
    await panel(head("🚪", "Lefter", dots(2, 3)) + "چی ترک بشه؟", kb_(*rows), page_tag="lf:2")

async def lf_step_delay(cid, s):
    d = s.get("delay", 0.8)
    mk = lambda n, l: B(("✅ " if abs(d - n) < 0.01 else "") + l, f"lf:delay:{n}")
    txt = head("🚪", "Lefter", dots(3, 3)) + f"تاخیر: <b>{d}s</b>"
    rows = [[mk(0.3, "🚀 0.3s"), mk(0.8, "⚡ 0.8s"), mk(1.5, "🐢 1.5s")],
            [mk(3.0, "🛡 3s")],
            [B("🚀 شروع", "lf:go")],
            nav("lf:back")]
    await panel(txt, kb_(*rows), page_tag="lf:3")

async def show_lf_step(cid):
    s = _lf_conv(cid)
    if s["step"] == "account": await lf_step_account(cid, s)
    if s["step"] == "mode":    await lf_step_mode(cid, s)
    if s["step"] == "delay":   await lf_step_delay(cid, s)


# ═══════════════ TEMPLATE UI ═══════════════
async def show_at_menu():
    tpls = list_templates()
    txt = head("🎯", f"قالب‌ها ({len(tpls)})")
    txt += "<i>قالب = ست کاملی از تنظیمات</i>"
    rows = []
    for tid, t in list(tpls.items())[:8]:
        parts = []
        ch_type = t.get("channel", {}).get("type", "private")
        if t.get("channel", {}).get("title"):
            parts.append("🌐" if ch_type == "public" else "🔒")
        if t.get("channel", {}).get("public_for_profile"): parts.append("📢")
        if t.get("profile", {}).get("first_name") or t.get("profile", {}).get("bio"): parts.append("📝")
        if t.get("profile", {}).get("photo_file"): parts.append("🖼")
        if int(t.get("joiner", {}).get("max_join", 0) or 0) > 0: parts.append("🤝")
        if t.get("sender", {}).get("text"): parts.append("📤")
        if t.get("sender", {}).get("edit_delay_enabled"): parts.append("🎭")
        if t.get("sender", {}).get("attach_file"): parts.append("📎")
        if t.get("lefter", {}).get("leave_mode"): parts.append("🚪")
        badge = " ".join(parts) or "∅"
        rows.append([B(f"🎯 {short(t.get('name', '?'), 18)}  ·  {badge}", f"at:{tid}:view")])
    rows.append([B("➕ ساخت قالب", "at:new")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="at:menu")

async def show_at_view(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    ch = t.get("channel", {}); pr = t.get("profile", {})
    jn = t.get("joiner", {}); sn = t.get("sender", {}); lf = t.get("lefter", {})
    def badge(d, key): return "🟢" if d.get(key) else "⚪"
    def badge_n(d, key): return "🟢" if int(d.get(key, 0) or 0) > 0 else "⚪"
    txt = head("🎯", t.get("name", "?"))
    type_icon = "🌐" if ch.get("type") == "public" else "🔒"
    txt += f"🏗 کانال: {badge(ch, 'title')}"
    if ch.get("title"): txt += f" {type_icon} <i>{esc(short(ch['title'], 20))}</i>"
    if ch.get("public_for_profile"): txt += f"\n📢 عمومی پروفایل: 🟢"
    txt += f"\n📝 پروفایل: {badge(pr, 'first_name') or badge(pr, 'bio') or badge(pr, 'username')}"
    if pr.get("photo_file"): txt += " 🖼"
    txt += f"\n🤝 جوین: {badge_n(jn, 'max_join')}"
    if int(jn.get('max_join', 0) or 0) > 0: txt += f" <i>({jn['max_join']})</i>"
    if jn.get("groups_only", True): txt += " 👥"
    txt += f"\n📤 ارسال: {badge(sn, 'text')}"
    if sn.get('text'): txt += f" <i>{sn.get('mode', 'send_only')}</i>"
    if sn.get('edit_delay_enabled'): txt += f" 🎭"
    if sn.get('attach_file'): txt += f" 📎"
    txt += f"\n🚪 ترک: 🟢 <i>{lf.get('leave_mode', '?')}</i>"
    rows = grid([
        B("🏗 کانال", f"at:{tid}:ch"), B("📝 پروفایل", f"at:{tid}:pr"),
        B("🤝 جوین", f"at:{tid}:jn"), B("📤 ارسال", f"at:{tid}:sn"),
        B("🚪 ترک", f"at:{tid}:lf"), B("✏️ نام", f"at:{tid}:rename"),
    ])
    rows.append([B("🚀 اجرا روی اکانت", f"at:{tid}:run")])
    rows.append([B("🗑 حذف", f"at:{tid}:del"), B("🏠 منو", "menu:main")])
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:view")

async def show_at_channel(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    c = t.get("channel", {})
    ctype = c.get("type", "private")
    is_pub = ctype == "public"
    pub_on = bool(c.get("public_for_profile", False))
    txt = head("🏗", "کانال در قالب", t.get("name", "?"))
    txt += f"🔖 نوع اصلی: <b>{'🌐 عمومی' if is_pub else '🔒 خصوصی'}</b>\n"
    txt += f"📝 عنوان: <code>{esc(c.get('title') or '—')}</code>\n"
    if is_pub: txt += f"🔤 یوزرنیم: <code>{esc(c.get('username') or '—')}</code>\n"
    txt += f"📖 about: <code>{esc(short(c.get('about', ''), 40) or '—')}</code>\n"
    txt += f"🖼 عکس: <code>{esc(os.path.basename(c.get('photo_file', '')) or '—')}</code>\n"
    if pub_on:
        txt += "\n<b>📢 کانال عمومی پروفایل: 🟢</b>\n"
        txt += f"عنوان: <code>{esc(c.get('public_title') or '—')}</code>\n"
        txt += f"یوزرنیم: <code>@{esc(c.get('public_username') or '—')}</code>\n"
        if c.get('set_as_personal'): txt += "🏠 کانال من: 🟢\n"
        if c.get('post_to_public'): txt += "📮 پست: 🟢\n"
        txt += f"<i>پست: {esc(short(c.get('post_text', ''), 40))}</i>"
    else:
        txt += "\n<b>📢 کانال عمومی پروفایل:</b> ⚪"
    txt += "\n\n<b>📌 متغیرها:</b> <code>{n} {rnd} {Link_private} {Link_public}</code>"
    rows = [
        [B(("✅ " if is_pub else "") + "🌐 عمومی", f"at:{tid}:chtype:public"),
         B(("✅ " if not is_pub else "") + "🔒 خصوصی", f"at:{tid}:chtype:private")],
        [B("📝 عنوان", f"at:{tid}:chset:title")],
    ]
    if is_pub: rows.append([B("🔤 یوزرنیم", f"at:{tid}:chset:username")])
    rows.append([B("📖 توضیحات", f"at:{tid}:chset:about")])
    rows.append([B("🖼 عکس کانال", f"at:{tid}:chset:photo_file")])
    rows.append([B(("🟢 " if pub_on else "⚪ ") + "کانال عمومی پروفایل", f"at:{tid}:chpub:toggle")])
    if pub_on:
        rows.append([B("📝 عنوان عمومی", f"at:{tid}:chpubset:public_title")])
        rows.append([B("🔤 یوزرنیم عمومی", f"at:{tid}:chpubset:public_username")])
        rows.append([B("📖 about عمومی", f"at:{tid}:chpubset:public_about")])
        rows.append([
            B(("🟢 " if c.get('set_as_personal') else "⚪ ") + "کانال من", f"at:{tid}:chpub:personal_toggle"),
            B(("🟢 " if c.get('post_to_public') else "⚪ ") + "پست", f"at:{tid}:chpub:post_toggle"),
        ])
        rows.append([B("✉️ متن پست", f"at:{tid}:chpubset:post_text")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:ch")

async def show_at_profile(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    p = t.get("profile", {})
    txt = head("📝", "پروفایل در قالب", t.get("name", "?"))
    txt += f"👤 نام: <code>{esc(p.get('first_name') or '—')}</code>\n"
    txt += f"👤 فامیل: <code>{esc(p.get('last_name') or '—')}</code>\n"
    txt += f"🔤 یوزرنیم: <code>{esc(p.get('username') or '—')}</code>\n"
    txt += f"📖 بیو: <code>{esc(short(p.get('bio', ''), 60) or '—')}</code>\n"
    txt += f"🖼 عکس: <code>{esc(os.path.basename(p.get('photo_file', '')) or '—')}</code>\n"
    txt += "\n<b>📌 متغیرها:</b> <code>{Link_private} {Link_public} {n} {rnd}</code>"
    rows = [
        [B("👤 نام", f"at:{tid}:prset:first_name"), B("👤 فامیل", f"at:{tid}:prset:last_name")],
        [B("🔤 یوزرنیم", f"at:{tid}:prset:username"), B("📖 بیو", f"at:{tid}:prset:bio")],
        [B("🖼 عکس پروفایل", f"at:{tid}:prset:photo_file")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:pr")

async def show_at_joiner(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    j = t.get("joiner", {})
    txt = head("🤝", "جوین در قالب", t.get("name", "?"))
    txt += f"🎯 سقف: <b>{j.get('max_join', 0)}</b>\n"
    txt += f"🚀 سرعت: <b>{next((l for k, l, _ in JL_SPEEDS if k == j.get('speed')), j.get('speed'))}</b>\n"
    txt += f"🚪 Auto-leave: <b>{'🟢' if j.get('auto_leave_on_fail') else '⚪'}</b>\n"
    txt += f"👥 فقط گروه‌های واقعی: <b>{'🟢' if j.get('groups_only', True) else '⚪'}</b>"
    rows = [[B("🎯 سقف", f"at:{tid}:jnset:max_join")]]
    rows += grid([B(("✅ " if j.get("speed") == k else "") + l, f"at:{tid}:jnspeed:{k}") for k, l, _ in JL_SPEEDS])
    rows.append([B("🚪 Auto-leave" + (" ✅" if j.get("auto_leave_on_fail") else ""), f"at:{tid}:jntoggle_auto_leave")])
    rows.append([B("👥 فقط گروه" + (" ✅" if j.get("groups_only", True) else ""), f"at:{tid}:jntoggle_groups_only")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:jn")

async def show_at_sender(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    s = t.get("sender", {})
    mode_labels = {"send_only": "فقط ارسال", "join_send": "joina+send", "join_send_leave": "join+send+leave"}
    ed_on = bool(s.get("edit_delay_enabled", False))
    ed_sec = s.get("edit_delay_seconds", 3.0)
    ed_rand = bool(s.get("edit_delay_random", False))
    ed_min = s.get("edit_delay_min", 2.0); ed_max = s.get("edit_delay_max", 6.0)
    ph = s.get("placeholder_text", "سلام")
    ph_rand = bool(s.get("placeholder_random", False))
    ms_on = bool(s.get("multi_step_edit", False))
    ms_mid = s.get("multi_step_middle", "Hi")
    send_existing = bool(s.get("send_to_existing", True))
    af = s.get("attach_file") or ""
    txt = head("📤", "ارسال در قالب", t.get("name", "?"))
    txt += f"✉️ متن: <code>{esc(short(s.get('text', ''), 50) or '—')}</code>\n"
    txt += f"🎯 مقصد: <b>{s.get('target', '?')}</b>\n"
    txt += f"🔁 حالت: <b>{mode_labels.get(s.get('mode'), s.get('mode'))}</b>\n"
    txt += f"🔢 سقف: <b>{s.get('max_send', 0) or '∞'}</b>  ·  ⏱ <b>{s.get('delay', 1.5)}s</b>\n"
    txt += f"\n<b>🎭 Edit:</b> {'🟢' if ed_on else '⚪'}"
    if ed_on:
        if ed_rand: txt += f"  🎲 <b>{ed_min}-{ed_max}s</b>"
        else: txt += f"  ⏱ <b>{ed_sec}s</b>"
        txt += f"\n💬 Placeholder: <code>{esc(ph)}</code>"
        if ph_rand: txt += "  🎲"
        if ms_on: txt += f"\n🔁 Multi: 🟢  mid: <code>{esc(ms_mid)}</code>"
    txt += f"\n📎 فایل: <code>{esc(os.path.basename(af) if af else '—')}</code>"
    txt += f"\n📨 به گروه‌های قبلی: {'🟢' if send_existing else '⚪'}"
    txt += "\n\n<b>📌 متغیرها:</b> <code>{Link_private} {n} {rnd}</code>"
    rows = [
        [B("✉️ متن", f"at:{tid}:snset:text")],
        [B("🎯 مقصد", f"at:{tid}:snset:target"), B("🔢 سقف", f"at:{tid}:snset:max_send")],
        [B("⏱ تاخیر", f"at:{tid}:snset:delay"), B("🔁 حالت", f"at:{tid}:snmode")],
        [B(("🟢 " if ed_on else "⚪ ") + "Edit-Delay", f"at:{tid}:snedit:toggle")],
        [B(("🎲 " if ed_rand else "⏱ ") + "تاخیر", f"at:{tid}:snedit:delay_mode"),
         B(f"{ed_sec}s", f"at:{tid}:snedit:sec")],
        [B(f"💬 {esc(short(ph, 12))}", f"at:{tid}:snedit:ph")],
        [B(("🎲 " if ph_rand else "📝 ") + "لیست", f"at:{tid}:snedit:ph_rand"),
         B("✏️ لیست", f"at:{tid}:snedit:ph_list")],
        [B(("🟢 " if ms_on else "⚪ ") + "Multi", f"at:{tid}:snedit:multi_toggle"),
         B(f"Mid", f"at:{tid}:snedit:multi_mid")],
        [B(f"📎 {esc(os.path.basename(af) if af else 'افزودن فایل')}", f"at:{tid}:snedit:file")],
        [B(("🟢 " if send_existing else "⚪ ") + "به گروه‌های قبلی", f"at:{tid}:snedit:toggle_existing")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:sn")

async def show_at_sender_mode(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    cur = t["sender"].get("mode", "send_only")
    opts = [("send_only", "📤 فقط ارسال"), ("join_send", "🤝 جوین + ارسال فوری"),
            ("join_send_leave", "🤝 جوین + ارسال + 🚪 ترک")]
    txt = head("🔁", "حالت ارسال") + f"فعلی: <b>{cur}</b>"
    rows = grid([B(("✅ " if cur == k else "") + l, f"at:{tid}:snmode_set:{k}") for k, l in opts])
    rows.append(nav(f"at:{tid}:sn"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:snmode")

async def show_at_lefter(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    l = t.get("lefter", {})
    txt = head("🚪", "ترک در قالب", t.get("name", "?"))
    txt += f"🎯 حالت: <b>{l.get('leave_mode', '?')}</b>"
    rows = []
    for k, lbl in LF_MODES:
        rows.append([B(("✅ " if l.get("leave_mode") == k else "") + lbl, f"at:{tid}:lfset:{k}")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:lf")

async def show_at_run(tid, page=0):
    t = get_template(tid)
    if not t: return await show_at_menu()
    accounts = list_accounts(); items = list(accounts.items())
    per = 6; pages = max(1, -(-len(items) // per)); page = max(0, min(page, pages - 1))
    chunk = items[page * per:(page + 1) * per]
    cid = STATE.get("owner")
    conv = get_conv(cid) if cid else {}
    selected = set((conv.get("at_run") or {}).get("accounts") or [])
    rows = []
    for aid, a in chunk:
        chk = "☑" if aid in selected else "☐"
        rows.append([B(f"{chk} {short(a.get('name', '?'), 20)}", f"at:{tid}:run_acc:{aid}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"at:{tid}:run:{page - 1}"))
        pr.append(B(f"{page + 1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("▶️", f"at:{tid}:run:{page + 1}"))
        rows.append(pr)
    rows.append([B("▶️ شروع", f"at:{tid}:run_go")])
    rows.append(nav(f"at:{tid}:view"))
    txt = head("🎯", "اجرای قالب", t.get("name", "?"))
    txt += f"انتخاب‌شده: <b>{len(selected)}</b> اکانت"
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:run:{page}")

async def show_acc_at_menu(aid):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    tpls = list_templates()
    txt = head("🎯", "Auto-Tar روی", a.get("name", "?"))
    if not tpls:
        txt += "\n\n⚠️ هیچ قالبی نداری."
        return await panel(txt, kb_([B("➕", "at:new"), B("🏠", "menu:main")]), page_tag=f"acc:at:{aid}")
    rows = []
    for tid, t in list(tpls.items())[:10]:
        rows.append([B(f"🎯 {short(t.get('name', '?'), 22)}", f"acc:at:run:{aid}:{tid}")])
    rows.append(nav(f"acc:view:{aid}"))
    await panel(txt, kb_(*rows), page_tag=f"acc:at:{aid}")

async def show_acc_lf(aid):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_(nav()), page_tag="main")
    txt = head("🚪", "Lefter روی", a.get("name", "?"))
    rows = []
    for k, lbl in LF_MODES:
        rows.append([B(lbl, f"acc:lf:go:{aid}:{k}")])
    rows.append(nav(f"acc:view:{aid}"))
    await panel(txt, kb_(*rows), page_tag=f"acc:lf:{aid}")


# ═══════════════ MESSAGE HANDLER ═══════════════
_TMP_EDIT: Dict[int, Dict[str, Any]] = {}

async def _on_message_impl(update, context):
    if not authorized(update): return
    msg = update.message
    if msg is None: return
    cid = update.effective_chat.id
    conv = STATE["conv"].get(cid) or {}
    text = (msg.text or "").strip()

    if "acc" in conv and conv["acc"].get("step") == "login_code":
        code = text; phone = conv["acc"].get("phone")
        STATE["panel"].pop(cid, None)
        await panel("⏳ تایید...", page_tag="login_verify")
        try: res = await soroosh_complete_login(phone, code)
        except Exception as e: res = {"ok": False, "status": _fmt_error(e)}
        clear_conv(cid)
        if res.get("ok"):
            await panel(head("✅", f"سروش: {res['name']}") + f"🆔 <code>{esc(res['aid'])}</code>",
                        kb_([B("🏠 منو", "menu:main")]), page_tag="main"); return
        if res.get("need_signup"):
            await panel("⚠️ بدون اکانت.", kb_([B("🏠 منو", "menu:main")]), page_tag="main"); return
        await panel(f"❌ <code>{esc(str(res.get('status'))[:400])}</code>",
                    kb_([B("🔄", "acc:add")], [B("🏠", "menu:main")]), page_tag="main"); return

    if conv.get("pv_wait"):
        kind = conv.pop("pv_wait")
        cfg = _load_pv_items()
        items = cfg.get("items") or []
        if kind == "delay":
            try: cfg["delay_seconds"] = max(0, int(re.sub(r"[^\d]", "", text) or "120"))
            except: cfg["delay_seconds"] = 120
        elif kind == "add_text":
            items.append({"kind": "text", "text": text})
            cfg["items"] = items
        elif kind == "add_delay_sec":
            try: sec = max(0, int(re.sub(r"[^\d]", "", text) or "3"))
            except: sec = 3
            items.append({"kind": "delay", "seconds": sec})
            cfg["items"] = items
        _save_pv_items(cfg)
        await tg_send("✅")
        return await show_pv_menu()

    if conv.get("pv_save_msg"):
        conv.pop("pv_save_msg")
        media = _extract_media(msg)
        if not media and not text:
            return await ask("❌ پیام معتبر نیست. دوباره بفرست:")
        cfg = _load_pv_items()
        items = cfg.get("items") or []
        items.append({"kind": "forward", "message_id": msg.message_id, "from_chat_id": cid})
        cfg["items"] = items
        _save_pv_items(cfg)
        await tg_send("✅ ذخیره شد (موقع پاسخ forward می‌شه)")
        return await show_pv_menu()

    if conv.get("accphoto_upload"):
        info = conv.pop("accphoto_upload")
        aid = info["aid"]
        media = _extract_media(msg)
        if not media: return await ask("❌ عکس نبود. دوباره بفرست:")
        try: fpath = await _download_tg_file(media, aid, "accphoto")
        except Exception as e: return await ask(f"❌ دانلود ناموفق: {str(e)[:100]}")
        a = get_account(aid)
        if not a: return await panel("⚠️", kb_(nav()), page_tag="main")
        STATE["panel"].pop(cid, None)
        await panel("⏳ آپلود عکس...", page_tag=f"accphoto:{aid}")
        cli = None; ok = False; msg_r = ""
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if cli: ok, msg_r = await soroosh_set_profile_photo(cli, fpath)
            else: msg_r = f"اتصال: {err}"
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        await tg_send("✅ عکس تنظیم شد" if ok else f"❌ {msg_r[:150]}")
        return await show_acc_photo_menu(aid)

    if conv.get("chphoto_upload"):
        info = conv.pop("chphoto_upload")
        aid = info["aid"]; idx = info["idx"]
        media = _extract_media(msg)
        if not media: return await ask("❌ عکس نبود. دوباره بفرست:")
        try: fpath = await _download_tg_file(media, aid, "chphoto")
        except Exception as e: return await ask(f"❌ دانلود ناموفق: {str(e)[:100]}")
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel("⚠️", kb_(nav()), page_tag="main")
        ch = chs[idx]
        STATE["panel"].pop(cid, None)
        await panel("⏳ آپلود عکس کانال...", page_tag=f"chphoto:{aid}:{idx}")
        cli = None; ok = False; msg_r = ""
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if cli:
                ent, _ = await _resolve_channel_entity(cli, ch, aid)
                if ent: ok, msg_r = await soroosh_set_channel_photo(cli, ent, fpath)
                else: msg_r = "resolve نشد"
            else: msg_r = f"اتصال: {err}"
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        await tg_send("✅ عکس تنظیم شد" if ok else f"❌ {msg_r[:150]}")
        return await show_ch_photo_menu(aid, idx)

    if conv.get("chfile_upload") and conv["chfile_upload"].get("step") == "wait_file":
        info = conv["chfile_upload"]
        aid = info["aid"]; idx = info["idx"]
        media = _extract_media(msg)
        fpath = None
        if media:
            try: fpath = await _download_tg_file(media, aid, "chfile")
            except Exception as e: return await ask(f"❌ دانلود ناموفق: {str(e)[:100]}")
        elif text and os.path.exists(text.strip()):
            fpath = text.strip()
        if not fpath: return await ask("❌ فایل ندیدم. دوباره بفرست:")
        info["file_path"] = fpath; info["step"] = "wait_caption"
        conv["chfile_upload"] = info
        return await ask("✍️ کپشن (اگه نمی‌خوای، خالی بفرست):")

    if conv.get("chfile_upload") and conv["chfile_upload"].get("step") == "wait_caption":
        info = conv.pop("chfile_upload")
        aid = info["aid"]; idx = info["idx"]
        fpath = info.get("file_path"); caption = text.strip()
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel("⚠️", kb_(nav()), page_tag="main")
        ch = chs[idx]
        STATE["panel"].pop(cid, None)
        await panel("⏳ ارسال فایل...", page_tag=f"chview:{aid}:{idx}")
        cli = None; ok = False; msg_r = ""
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if cli:
                ent, _ = await _resolve_channel_entity(cli, ch, aid)
                if ent: ok, msg_r = await _send_file_to_entity(cli, ent, fpath, caption)
                else: msg_r = "resolve نشد"
            else: msg_r = f"اتصال: {err}"
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        await tg_send("✅ ارسال شد" if ok else f"❌ {msg_r[:150]}")
        return await show_channel_view(aid, idx)

    if conv.get("at_field_photo"):
        info = conv.pop("at_field_photo")
        tid = info["tid"]; section = info["section"]; field = info["field"]
        media = _extract_media(msg)
        if not media: return await ask("❌ فایل نبود. دوباره بفرست:")
        try: fpath = await _download_tg_file(media, "tpl", "tplfile")
        except Exception as e: return await ask(f"❌ دانلود ناموفق: {str(e)[:100]}")
        update_template(tid, section, field, fpath)
        await tg_send("✅ ذخیره شد")
        if section == "channel": return await show_at_channel(tid)
        if section == "profile": return await show_at_profile(tid)
        if section == "sender_edit": return await show_at_sender(tid)
        return await show_at_view(tid)

    if cid in _TMP_EDIT:
        info = _TMP_EDIT.pop(cid)
        if info["kind"] == "at_field":
            tid = info["tid"]; section = info["section"]; field = info["field"]
            value = text
            if field in ("max_join", "max_send"):
                try: value = int(re.sub(r"[^\d]", "", text) or "0")
                except: value = 0
            elif field == "delay":
                try: value = float(re.sub(r"[^\d\.]", "", text) or "1.5")
                except: value = 1.5
            elif field == "edit_delay_seconds":
                try: value = max(0.0, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
                except: value = 3.0
            update_template(tid, section, field, value)
            await tg_send("✅")
            if section == "meta": return await show_at_view(tid)
            if section == "channel": return await show_at_channel(tid)
            if section == "profile": return await show_at_profile(tid)
            if section == "joiner": return await show_at_joiner(tid)
            if section == "sender": return await show_at_sender(tid)
            if section == "sender_edit": return await show_at_sender(tid)
            if section == "channel_public": return await show_at_channel(tid)
            if section == "lefter": return await show_at_lefter(tid)

    if conv.get("send_edit_wait"):
        kind = conv.pop("send_edit_wait")
        s = _send_conv(cid)
        if kind == "sec":
            try: s["edit_delay_seconds"] = max(0.0, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
            except: s["edit_delay_seconds"] = 3.0
        elif kind == "ph": s["placeholder_text"] = text or "سلام"
        elif kind == "loop_delay":
            try: s["loop_delay"] = max(0.5, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
            except: s["loop_delay"] = 3.0
        return await show_send_step(cid)

    if conv.get("send_file_upload"):
        conv.pop("send_file_upload")
        s = _send_conv(cid)
        media = _extract_media(msg)
        if media:
            try: fpath = await _download_tg_file(media, "send", "sendfile")
            except Exception as e: return await ask(f"❌ دانلود ناموفق: {str(e)[:100]}")
            s["attach_file"] = fpath
        elif text and os.path.exists(text.strip()):
            s["attach_file"] = text.strip()
        else:
            return await ask("❌ فایل نبود. دوباره بفرست یا مسیر بده:")
        await tg_send("✅ فایل ذخیره شد")
        return await show_send_step(cid)

    if conv.get("ld_wait") == "url":
        back = conv.pop("ld_back", "jl:back_to_settings")
        url = text.strip()
        if url.startswith("splus.ir"): url = "https://" + url
        if url.startswith("soroush.ir"): url = "https://" + url
        if add_link_doni(url): await tg_send("✅")
        else: await tg_send("ℹ️")
        return await show_linkdonies(back)

    if conv.get("setlink"):
        info = conv.pop("setlink")
        aid = info["aid"]; idx = info["idx"]
        url = text.strip()
        if not url: return await ask("❌ خالی:")
        if not url.startswith("http"): url = "https://" + url
        update_channel_field(aid, idx, "join_link", url)
        await tg_send("✅")
        return await show_channel_view(aid, idx)

    if conv.get("chsend") and conv["chsend"].get("step") == "compose":
        info = conv.pop("chsend")
        aid = info["aid"]; idx = info["idx"]
        STATE["panel"].pop(cid, None)
        await panel("⏳ ...", page_tag=f"chview:{aid}:{idx}")
        ok, msg_r = await send_to_channel(aid, idx, text)
        if ok:
            return await panel(head("✅", "ارسال شد") + f"💬 <code>{esc(text[:100])}</code>",
                               kb_([B("📤", f"chsend:start:{aid}:{idx}")],
                                   [B("⬅️", f"ch:view:{aid}:{idx}")]),
                               page_tag=f"chview:{aid}:{idx}")
        return await panel(f"❌ <code>{esc(str(msg_r)[:400])}</code>",
                           kb_([B("⬅️", f"ch:view:{aid}:{idx}")]),
                           page_tag=f"chview:{aid}:{idx}")

    if conv.get("chnew"):
        info = conv["chnew"]; step = info.get("step"); aid = info.get("aid")
        a = get_account(aid); STATE["panel"].pop(cid, None)
        if not a:
            conv.pop("chnew", None)
            return await panel("⚠️", kb_(nav()), page_tag="main")
        if step == "title":
            title = text.strip()
            if not title: return await ask("📝 اسم:")
            info["title"] = title[:60]; info["step"] = "type"; conv["chnew"] = info
            return await show_ch_new_type(aid, title)
        if step == "username":
            title = info.get("title"); uname = text.lstrip("@").strip()
            if not uname: return await ask("🔤 یوزرنیم:")
            conv.pop("chnew", None)
            await panel(f"⏳ ساخت «{esc(title)}»...", page_tag="chnew_run")
            cli = None
            ok = False; msg_r = ""; ch_obj = None
            try:
                cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
                if cli:
                    ok, ch_obj, msg_r = await soroosh_create_channel(cli, title)
                    if ok and ch_obj is not None:
                        ent_data = _channel_data_from_obj(ch_obj)
                        try:
                            inp_ent, _m = await _resolve_channel_entity(cli, ent_data, aid)
                            if inp_ent:
                                try:
                                    r = cli(UpdateUsernameRequest(channel=inp_ent, username=uname))
                                    if asyncio.iscoroutine(r): r = await r
                                except Exception as ue: msg_r = f"یوزرنیم: {_fmt_error(ue)[:100]}"
                        except Exception: pass
                else: ok, msg_r = False, f"اتصال: {err}"
            except Exception as e: ok, msg_r = False, f"{type(e).__name__}: {_fmt_error(e)}"
            finally:
                if cli:
                    try: await cli._disconnect()
                    except Exception: pass
            _STATS_CACHE.pop(aid, None)
            if ok:
                store = _channel_data_from_obj(ch_obj)
                store["username"] = uname; store["type"] = "public"
                store["created"] = int(time.time())
                add_channel_to_storage(aid, store)
                body = head("✅", "ساخته شد") + f"📝 {esc(title)}\n🔗 @{esc(uname)}"
                return await panel(body, kb_([B("⚙️", f"chlist:show:{aid}:0")],
                                             [B("⬅️", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")
            return await panel(f"❌ <code>{esc(str(msg_r)[:300])}</code>",
                               kb_([B("⬅️", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")

    if conv.get("prof_field"):
        info = conv.pop("prof_field"); field = info["field"]; aid = info["aid"]
        STATE["panel"].pop(cid, None)
        a = get_account(aid)
        if not a: return await panel("⚠️", kb_(nav()), page_tag="main")
        await panel("⏳ ...", page_tag=f"prof:{aid}")
        ok = False; msg_r = ""
        cli = None
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if cli is None:
                ok, msg_r = False, f"اتصال ناموفق: {err}"
            else:
                if field in ("first", "last", "about"):
                    kwargs = {}
                    if field == "first": kwargs["first_name"] = text
                    elif field == "last": kwargs["last_name"] = text
                    elif field == "about": kwargs["about"] = text
                    ok, msg_r = await soroosh_update_profile(cli, **kwargs)
                elif field == "username":
                    ok, msg_r = await soroosh_update_username(cli, text)
        except Exception as e:
            ok, msg_r = False, f"{type(e).__name__}: {_fmt_error(e)}"
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        if ok:
            return await panel(head("✅", "OK") + f"<code>{esc(str(msg_r)[:200])}</code>",
                               kb_([B("⬅️", f"prof:menu:{aid}")]), page_tag=f"prof:{aid}")
        return await panel(f"❌ <code>{esc(str(msg_r)[:300])}</code>",
                           kb_([B("⬅️", f"prof:menu:{aid}")]), page_tag=f"prof:{aid}")

    if "jl_wait" in conv:
        conv.pop("jl_wait")
        jl = get_conv(cid).get("jl") or {}
        try: jl["max_join"] = max(1, int(re.sub(r"[^\d]", "", text)))
        except: return await ask("🔢 عدد:")
        get_conv(cid)["jl"] = jl; return await jl_step_max(cid, jl)

    if "send_wait" in conv:
        conv.pop("send_wait")
        s = _send_conv(cid)
        try: s["max"] = max(0, int(re.sub(r"[^\d]", "", text)))
        except: return await ask("🔢 عدد:")
        return await show_send_step(cid)

    if "send" in conv:
        s = conv["send"]
        if s.get("step") == "compose":
            STATE["panel"].pop(cid, None)
            if not text: return await ask("✉️ متن:")
            s["payload"] = {"text": text}; s["step"] = "target"
            return await show_send_step(cid)

    if "acc" in conv:
        a = conv["acc"]; step = a.get("step")
        STATE["panel"].pop(cid, None)
        if step == "phone":
            try: ph = normalize_phone(text)
            except Exception as e: return await ask("📞 نامعتبر:", note=str(e)[:150])
            a["phone"] = ph
            await panel(f"⏳ ارسال کد به <code>{esc(ph)}</code>...", page_tag="login_send")
            try: res = await soroosh_send_code(ph)
            except Exception as e: res = {"ok": False, "status": _fmt_error(e)}
            if not res.get("ok"):
                clear_conv(cid)
                return await panel(f"❌ <code>{esc(str(res.get('status'))[:400])}</code>",
                                   kb_([B("🔄", "acc:add")], [B("🏠", "menu:main")]), page_tag="main")
            a["step"] = "login_code"; STATE["conv"][cid] = {"acc": a}
            return await panel(f"✅ کد به <code>{esc(ph)}</code> فرستاده شد\n\nکد:", page_tag="login_code")


_on_message_orig = _on_message_impl

async def on_message(update, context):
    cid = None; had_conv = False; pv_keep = False
    try:
        cid = update.effective_chat.id
        had_conv = bool(STATE["conv"].get(cid)) or (cid in _TMP_EDIT)
        c = STATE["conv"].get(cid) or {}
        if c.get("pv_save_msg"): pv_keep = True
    except Exception: pass
    await _on_message_orig(update, context)
    try:
        if had_conv and authorized(update) and update.message and not pv_keep:
            await update.message.delete()
    except Exception: pass


# ═══════════════ CALLBACK ROUTER ═══════════════
async def route_cb(cid, data):
    p = data.split(":"); h = p[0]
    if h not in ("op", "noop"): STATE.setdefault("op_panel", {}).pop(cid, None)
    if data == "conv:cancel": clear_conv(cid); _TMP_EDIT.pop(cid, None); return await show_main()
    if data == "menu:main": clear_conv(cid); _TMP_EDIT.pop(cid, None); return await show_main()
    if data == "menu:acc": return await show_accounts()
    if data == "menu:stats": return await show_stats()
    if data == "menu:errors": return await show_errors()
    if data == "menu:listen": return await show_listen_menu()
    if data == "menu:cache": return await show_cache_menu()
    if data == "menu:pv": return await show_pv_menu()

    if h == "pv":
        cfg = _load_pv_items()
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu":
            return await show_pv_menu()
        if sub == "test":
            lines = ["🧪 <b>تست اتصال PV</b>", ""]
            lines.append(f"enabled: <b>{cfg.get('enabled')}</b>")
            lines.append(f"tasks: <b>{len(PV_LISTENER_TASKS)}</b>")
            for aid, t in PV_LISTENER_TASKS.items():
                acc = get_account(aid)
                anm = acc.get("name", aid) if acc else aid
                st = "🟢 running" if (t and not t.done()) else "🔴 dead"
                lines.append(f"· {esc(anm)}: {st}")
            if not PV_LISTENER_TASKS:
                lines.append("")
                lines.append("⚠️ هیچ تسکی برای PV اجرا نمی‌شه")
                lines.append("<i>روشن کن یا ری‌استارت بزن</i>")
            return await panel(head("🧪", "تست PV") + "\n".join(lines),
                               kb_([B("🔄 ری‌استارت", "pv:restart"), B("⬅️", "pv:menu")]),
                               page_tag="pv_test")
        if sub == "toggle_notify":
            cfg["notify"] = not bool(cfg.get("notify", True))
            _save_pv_items(cfg)
            return await show_pv_menu()
        if sub == "toggle":
            cfg["enabled"] = not bool(cfg.get("enabled"))
            _save_pv_items(cfg)
            if cfg["enabled"]: await start_pv_responders()
            else: _stop_all_pv()
            return await show_pv_menu()
        if sub == "toggle_once":
            cfg["reply_once"] = not bool(cfg.get("reply_once", True))
            _save_pv_items(cfg); return await show_pv_menu()
        if sub == "set_delay":
            get_conv(cid)["pv_wait"] = "delay"
            return await ask("⏱ تایمر (ثانیه):")
        if sub == "add_text":
            get_conv(cid)["pv_wait"] = "add_text"
            return await ask("💬 متن پیام:")
        if sub == "add_delay":
            get_conv(cid)["pv_wait"] = "add_delay_sec"
            return await ask("⏸ تأخیر (ثانیه):")
        if sub == "add_saved":
            get_conv(cid)["pv_save_msg"] = True
            return await ask("📎 پیام/عکس/ویدیو/فایل رو بفرست:")
        if sub == "list": return await show_pv_list()
        if sub == "del" and len(p) >= 3:
            try: i = int(p[2])
            except: return await show_pv_list()
            items = cfg.get("items") or []
            if 0 <= i < len(items):
                items.pop(i); cfg["items"] = items; _save_pv_items(cfg)
            await tg_send("🗑"); return await show_pv_list()
        if sub == "clear":
            cfg["items"] = []; _save_pv_items(cfg)
            await tg_send("🗑"); return await show_pv_menu()
        if sub == "restart":
            await restart_all_pv(); await tg_send("🔄"); return await show_pv_menu()
        if sub == "clear_replies":
            _clear_pv_replies(); await tg_send("🧹"); return await show_pv_menu()
        if sub == "report":
            try: pg = int(p[2]) if len(p) > 2 else 0
            except: pg = 0
            return await show_pv_report(pg)
        if sub == "report_clear":
            _clear_pv_report(); await tg_send("🧹")
            return await show_pv_report(0)

    if h == "accphoto":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu" and len(p) >= 3: return await show_acc_photo_menu(p[2])
        if sub == "set" and len(p) >= 3:
            get_conv(cid)["accphoto_upload"] = {"aid": p[2]}
            return await ask("🖼 عکس رو بفرست:")
        if sub == "del" and len(p) >= 3:
            aid = p[2]
            a = get_account(aid)
            if not a: return await panel("⚠️", kb_(nav()), page_tag="main")
            await panel("⏳ حذف...", page_tag=f"accphoto:{aid}")
            cli = None; ok = False; msg_r = ""
            try:
                cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
                if cli: ok, msg_r = await soroosh_delete_profile_photos(cli)
                else: msg_r = f"اتصال: {err}"
            finally:
                if cli:
                    try: await cli._disconnect()
                    except Exception: pass
            await tg_send("✅" if ok else f"❌ {msg_r[:150]}")
            return await show_acc_photo_menu(aid)

    if h == "chphoto":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu" and len(p) >= 4: return await show_ch_photo_menu(p[2], int(p[3]))
        if sub == "set" and len(p) >= 4:
            get_conv(cid)["chphoto_upload"] = {"aid": p[2], "idx": int(p[3])}
            return await ask("🖼 عکس کانال رو بفرست:")
        if sub == "del" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            a = get_account(aid); chs = get_stored_channels(aid)
            if not a or idx >= len(chs): return await panel("⚠️", kb_(nav()), page_tag="main")
            ch = chs[idx]
            await panel("⏳ حذف...", page_tag=f"chphoto:{aid}:{idx}")
            cli = None; ok = False; msg_r = ""
            try:
                cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
                if cli:
                    ent, _ = await _resolve_channel_entity(cli, ch, aid)
                    if ent: ok, msg_r = await soroosh_delete_channel_photos(cli, ent)
                    else: msg_r = "resolve نشد"
                else: msg_r = f"اتصال: {err}"
            finally:
                if cli:
                    try: await cli._disconnect()
                    except Exception: pass
            await tg_send("✅" if ok else f"❌ {msg_r[:150]}")
            return await show_ch_photo_menu(aid, idx)

    if h == "chfile":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start" and len(p) >= 4:
            get_conv(cid)["chfile_upload"] = {"aid": p[2], "idx": int(p[3]), "step": "wait_file"}
            return await ask("📎 فایل/عکس/ویدیو رو بفرست:")

    if h == "cache":
        sub = p[1] if len(p) > 1 else ""
        if sub == "clear_seen": _clear_seen(); await tg_send("🗑 seen"); return await show_cache_menu()
        if sub == "clear_banned": _clear_banned(); await tg_send("🗑 banned"); return await show_cache_menu()
        if sub == "clear_all": _clear_seen(); _clear_banned(); await tg_send("🗑 all"); return await show_cache_menu()
        if sub == "reset_ld": _reset_ld_progress(); await tg_send("🔄"); return await show_cache_menu()

    if h == "jl":
        c = get_conv(cid)
        s = c.get("jl") or {"step": "account", "accounts": [], "max_join": 0, "speed": "fast", "auto_left": False, "groups_only": True}
        c["jl"] = s; sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            c["jl"] = {"step": "account", "accounts": [], "max_join": 0, "speed": "fast", "auto_left": False, "groups_only": True}
            return await jl_step_account(cid, c["jl"])
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await jl_step_account(cid, s)
        if sub == "speed" and len(p) >= 3: s["speed"] = p[2]; return await jl_step_settings(cid, s)
        if sub == "toggle_auto_left": s["auto_left"] = not s.get("auto_left", False); return await jl_step_settings(cid, s)
        if sub == "toggle_groups_only": s["groups_only"] = not s.get("groups_only", True); return await jl_step_settings(cid, s)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["jl_wait"] = "max"; return await ask("🔢 عدد:")
            try: s["max_join"] = int(v)
            except: pass
            return await jl_step_max(cid, s)
        if sub == "next":
            if s["step"] == "account":
                if not s.get("accounts"):
                    return await panel("⚠️", kb_([B("⬅️", "jl:back")]), page_tag="jl:1")
                s["step"] = "settings"; return await jl_step_settings(cid, s)
            elif s["step"] == "settings":
                s["step"] = "max"; return await jl_step_max(cid, s)
        if sub == "back":
            if s["step"] == "settings": s["step"] = "account"
            elif s["step"] == "max": s["step"] = "settings"
            return await show_jl_step(cid)
        if sub == "linkdonies": return await show_linkdonies("jl:back_to_settings")
        if sub == "back_to_settings": s["step"] = "settings"; return await jl_step_settings(cid, s)
        if sub == "cancel": c.pop("jl", None); return await show_main()
        if sub == "go":
            if not s.get("max_join"): return await panel("⚠️", kb_([B("⬅️", "jl:back")]), page_tag="jl:3")
            if not s.get("accounts"): return await panel("⚠️", kb_([B("⬅️", "jl:back")]), page_tag="jl:1")
            speed_map = {"ultra": 0.3, "fast": 1.0, "normal": 3.0, "slow": 8.0}
            spd = s.get("speed", "fast"); cfg = _load(CFG_FILE, DEFAULT_CFG)
            op = {"id": "jl_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "joinlef", "accounts": s.get("accounts") or [],
                  "max_join": s.get("max_join", 0), "status": "running", "speed": spd,
                  "join_delay": speed_map.get(spd, 1.0), "auto_msg": "",
                  "auto_left": bool(s.get("auto_left", False)),
                  "groups_only": bool(s.get("groups_only", True)),
                  "wave_size": int(cfg.get("wave_size", 50)),
                  "extract_limit": int(cfg.get("extract_limit", 300)),
                  "link_donies": list(load_link_donies()),
                  "progress": {"joined": 0, "failed": 0, "total": 0, "phase": "شروع", "extracted": 0,
                               "skipped_seen": 0, "skipped_banned": 0, "rejected": 0},
                  "errors": []}
            _save_op(op); c.pop("jl", None)
            JL_JOBS[op["id"]] = asyncio.create_task(run_joiner_lefter(op, log_cb))
            return await show_op_detail(op["id"])

    if h == "lf":
        c = get_conv(cid)
        s = c.get("lf") or {"step": "account", "accounts": [], "mode": "all", "delay": 0.8}
        c["lf"] = s; sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            c["lf"] = {"step": "account", "accounts": [], "mode": "all", "delay": 0.8}
            return await lf_step_account(cid, c["lf"])
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await lf_step_account(cid, s)
        if sub == "mode" and len(p) >= 3: s["mode"] = p[2]; return await lf_step_mode(cid, s)
        if sub == "delay" and len(p) >= 3:
            try: s["delay"] = float(p[2])
            except: s["delay"] = 0.8
            return await lf_step_delay(cid, s)
        if sub == "next":
            if s["step"] == "account":
                if not s.get("accounts"): return await panel("⚠️", kb_([B("⬅️", "lf:back")]), page_tag="lf:1")
                s["step"] = "mode"; return await lf_step_mode(cid, s)
            elif s["step"] == "mode":
                s["step"] = "delay"; return await lf_step_delay(cid, s)
        if sub == "back":
            if s["step"] == "mode": s["step"] = "account"
            elif s["step"] == "delay": s["step"] = "mode"
            return await show_lf_step(cid)
        if sub == "cancel": c.pop("lf", None); return await show_main()
        if sub == "go":
            if not s.get("accounts"): return await panel("⚠️", kb_([B("⬅️", "lf:back")]), page_tag="lf:1")
            op = {"id": "lf_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "lefter", "accounts": s.get("accounts") or [],
                  "leave_mode": s.get("mode", "all"), "delay": s.get("delay", 0.8),
                  "status": "running",
                  "progress": {"joined": 0, "failed": 0, "total": 0, "phase": "شروع"},
                  "errors": []}
            _save_op(op); c.pop("lf", None)
            asyncio.create_task(run_lefter(op, log_cb))
            return await show_op_detail(op["id"])

    if h == "at":
        if data == "at:menu": return await show_at_menu()
        if data == "at:new":
            tpl = new_template("قالب " + secrets.token_hex(2))
            add_template(tpl); return await show_at_view(tpl["id"])
        if len(p) >= 3 and p[1].startswith("tp_"):
            tid = p[1]; act = p[2]
            if act == "view": return await show_at_view(tid)
            if act == "del":
                t = get_template(tid)
                if not t: return await show_at_menu()
                return await panel(f"🗑 حذف <b>{esc(t.get('name', '?'))}</b>؟",
                                   kb_([B("✅", f"at:{tid}:delok"), B("❌", f"at:{tid}:view")]),
                                   page_tag=f"at:{tid}:view")
            if act == "delok": delete_template(tid); await tg_send("🗑"); return await show_at_menu()
            if act == "rename":
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "meta", "field": "name"}
                return await ask("✏️ نام:")
            if act == "ch": return await show_at_channel(tid)
            if act == "pr": return await show_at_profile(tid)
            if act == "jn": return await show_at_joiner(tid)
            if act == "sn": return await show_at_sender(tid)
            if act == "lf": return await show_at_lefter(tid)
            if act == "snmode": return await show_at_sender_mode(tid)
            if act == "chtype" and len(p) >= 4:
                update_template(tid, "channel", "type", p[3]); return await show_at_channel(tid)
            if act == "chset" and len(p) >= 4:
                field = p[3]
                if field == "photo_file":
                    get_conv(cid)["at_field_photo"] = {"tid": tid, "section": "channel", "field": "photo_file"}
                    return await ask("🖼 عکس کانال رو بفرست:")
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "channel", "field": field}
                prompts = {"title": "📝 عنوان:", "username": "🔤 یوزرنیم:", "about": "📖 توضیحات:"}
                return await ask(prompts.get(field, "مقدار:"))
            if act == "prset" and len(p) >= 4:
                field = p[3]
                if field == "photo_file":
                    get_conv(cid)["at_field_photo"] = {"tid": tid, "section": "profile", "field": "photo_file"}
                    return await ask("🖼 عکس پروفایل رو بفرست:")
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "profile", "field": field}
                prompts = {"first_name": "👤 نام:", "last_name": "👤 فامیل:",
                           "username": "🔤 یوزرنیم:", "bio": "📖 بیو ({Link_private} {Link_public}):"}
                return await ask(prompts.get(field, "مقدار:"))
            if act == "jnset" and len(p) >= 4:
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "joiner", "field": p[3]}
                return await ask("🎯 سقف جوین:")
            if act == "jnspeed" and len(p) >= 4:
                update_template(tid, "joiner", "speed", p[3]); return await show_at_joiner(tid)
            if act == "jntoggle_auto_leave":
                t = get_template(tid)
                if t: update_template(tid, "joiner", "auto_leave_on_fail", not bool(t.get("joiner", {}).get("auto_leave_on_fail", True)))
                return await show_at_joiner(tid)
            if act == "jntoggle_groups_only":
                t = get_template(tid)
                if t: update_template(tid, "joiner", "groups_only", not bool(t.get("joiner", {}).get("groups_only", True)))
                return await show_at_joiner(tid)
            if act == "snset" and len(p) >= 4:
                field = p[3]
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender", "field": field}
                prompts = {"text": "✉️ متن:", "target": "🎯 (pv/groups/both):",
                           "max_send": "🔢 سقف (0=∞):", "delay": "⏱ تاخیر:"}
                return await ask(prompts.get(field, "مقدار:"))
            if act == "snmode_set" and len(p) >= 4:
                update_template(tid, "sender", "mode", p[3]); return await show_at_sender(tid)
            if act == "lfset" and len(p) >= 4:
                update_template(tid, "lefter", "leave_mode", p[3]); return await show_at_lefter(tid)
            if act == "snedit" and len(p) >= 4:
                sub_act = p[3]
                ts = list_templates(); t2 = ts.get(tid)
                if sub_act in ("toggle", "delay_mode", "ph_rand", "multi_toggle", "toggle_existing"):
                    if t2:
                        snd2 = t2.setdefault("sender", {})
                        if sub_act == "toggle": snd2["edit_delay_enabled"] = not bool(snd2.get("edit_delay_enabled", False))
                        elif sub_act == "delay_mode": snd2["edit_delay_random"] = not bool(snd2.get("edit_delay_random", False))
                        elif sub_act == "ph_rand": snd2["placeholder_random"] = not bool(snd2.get("placeholder_random", False))
                        elif sub_act == "multi_toggle": snd2["multi_step_edit"] = not bool(snd2.get("multi_step_edit", False))
                        elif sub_act == "toggle_existing": snd2["send_to_existing"] = not bool(snd2.get("send_to_existing", True))
                        save_templates(ts)
                    return await show_at_sender(tid)
                if sub_act == "sec":
                    _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender_edit", "field": "edit_delay_seconds"}
                    return await ask("⏱ تاخیر (ثانیه):")
                if sub_act == "ph":
                    _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender_edit", "field": "placeholder_text"}
                    return await ask("💬 پیام اولیه:")
                if sub_act == "ph_list":
                    _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender_edit", "field": "placeholder_list"}
                    return await ask("🎲 لیست با کاما:")
                if sub_act == "multi_mid":
                    _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender_edit", "field": "multi_step_middle"}
                    return await ask("🔁 متن middle:")
                if sub_act == "file":
                    get_conv(cid)["at_field_photo"] = {"tid": tid, "section": "sender_edit", "field": "attach_file"}
                    return await ask("📎 فایل رو بفرست:")
            if act == "chpub" and len(p) >= 4:
                sub_act = p[3]
                ts = list_templates(); t2 = ts.get(tid)
                if t2:
                    ch2 = t2.setdefault("channel", {})
                    if sub_act == "toggle": ch2["public_for_profile"] = not bool(ch2.get("public_for_profile", False))
                    elif sub_act == "personal_toggle": ch2["set_as_personal"] = not bool(ch2.get("set_as_personal", True))
                    elif sub_act == "post_toggle": ch2["post_to_public"] = not bool(ch2.get("post_to_public", True))
                    save_templates(ts)
                return await show_at_channel(tid)
            if act == "chpubset" and len(p) >= 4:
                field = p[3]
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "channel_public", "field": field}
                prompts = {
                    "public_title": "📝 عنوان کانال عمومی:",
                    "public_username": "🔤 یوزرنیم عمومی:",
                    "public_about": "📖 about عمومی:",
                    "post_text": "✉️ متن پست ({Link_private}):"}
                return await ask(prompts.get(field, "مقدار:"))
            if act == "run": return await show_at_run(tid)
            if act == "run_acc" and len(p) >= 4:
                aid = p[3]
                c = get_conv(cid); ar = c.setdefault("at_run", {"template_id": tid, "accounts": []})
                sel = ar.setdefault("accounts", [])
                if aid in sel: sel.remove(aid)
                else: sel.append(aid)
                return await show_at_run(tid)
            if act == "run_go":
                c = get_conv(cid); ar = c.get("at_run") or {}
                sel = ar.get("accounts") or []
                if not sel: return await panel("⚠️", kb_(nav(f"at:{tid}:view")), page_tag=f"at:{tid}:run:0")
                op = {"id": "at_" + secrets.token_hex(5), "created": int(time.time()),
                      "type": "autotar", "accounts": sel, "template_id": tid,
                      "status": "running",
                      "progress": {"joined": 0, "failed": 0, "total": 0, "pending": 0,
                                   "in_progress": 0, "phase": "شروع", "sent": 0, "already": 0,
                                   "tried": 0, "wave": 0, "left": 0,
                                   "skipped_seen": 0, "skipped_banned": 0, "rejected": 0},
                      "errors": []}
                _save_op(op); c.pop("at_run", None)
                asyncio.create_task(run_auto_tar(op, log_cb))
                return await show_op_detail(op["id"])
            if len(p) == 3 and p[2].isdigit(): return await show_at_run(tid, int(p[2]))

    if h == "acc":
        if len(p) >= 5 and p[1] == "at" and p[2] == "run":
            aid = p[3]; tid = p[4]
            op = {"id": "at_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "autotar", "accounts": [aid], "template_id": tid,
                  "status": "running",
                  "progress": {"joined": 0, "failed": 0, "total": 0, "pending": 0,
                               "in_progress": 0, "phase": "شروع", "sent": 0, "already": 0,
                               "tried": 0, "wave": 0, "left": 0,
                               "skipped_seen": 0, "skipped_banned": 0, "rejected": 0},
                  "errors": []}
            _save_op(op); asyncio.create_task(run_auto_tar(op, log_cb))
            return await show_op_detail(op["id"])
        if len(p) >= 3 and p[1] == "at": return await show_acc_at_menu(p[2])
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_accounts(int(p[2]))
        if sub == "refresh":
            for aid in list(_STATS_CACHE.keys()): _STATS_CACHE.pop(aid, None)
            await tg_send("🔄"); return await show_accounts()
        if sub == "refresh_one" and len(p) >= 3:
            _STATS_CACHE.pop(p[2], None); await tg_send("🔄")
            return await show_account_detail(p[2])
        if sub == "add":
            get_conv(cid)["acc"] = {"step": "phone"}
            return await ask("📞 شماره:")
        if sub == "view": return await show_account_detail(p[2])
        if sub == "del":
            a = get_account(p[2])
            if not a: return await panel("⚠️", kb_(nav()), page_tag="main")
            return await panel(f"🗑 حذف <b>{esc(a.get('name','?'))}</b>؟",
                               kb_([B("✅", f"acc:delok:{p[2]}"), B("❌", f"acc:view:{p[2]}")]),
                               page_tag=f"acc_del:{p[2]}")
        if sub == "delok":
            _stop_listener_for(p[2])
            try:
                st = STATE.get("pv_stops", {}).get(p[2])
                if st: st.set()
                t = PV_LISTENER_TASKS.pop(p[2], None)
                if t and not t.done(): t.cancel()
            except Exception: pass
            remove_account(p[2]); await tg_send("🗑")
            return await show_accounts()
        if sub == "lf" and len(p) >= 5 and p[3] == "go":
            aid = p[2]; mode = p[4]
            op = {"id": "lf_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "lefter", "accounts": [aid], "leave_mode": mode, "delay": 0.8,
                  "status": "running",
                  "progress": {"joined": 0, "failed": 0, "total": 0, "phase": "شروع"},
                  "errors": []}
            _save_op(op); asyncio.create_task(run_lefter(op, log_cb))
            return await show_op_detail(op["id"])
        if sub == "lf" and len(p) >= 3: return await show_acc_lf(p[2])

    if h == "chprof":
        sub = p[1] if len(p) > 1 else ""
        if sub == "show" and len(p) >= 4: return await show_ch_profile(p[2], int(p[3]))
        if sub == "edit" and len(p) >= 5:
            field = p[2]; aid = p[3]; idx = int(p[4])
            get_conv(cid)["chprof_edit"] = {"field": field, "aid": aid, "idx": idx}
            prompts = {"title": "✏️:", "about": "📖:", "username": "🔤:"}
            if field == "photo":
                return await panel("🚧", kb_([B("⬅️", f"chprof:show:{aid}:{idx}")]), page_tag=f"chprof:{aid}:{idx}")
            return await ask(prompts.get(field, "مقدار:"))

    if h == "ch":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu": return await show_ch_menu(p[2])
        if sub == "view" and len(p) >= 4: return await show_channel_view(p[2], int(p[3]))
        if sub == "getlink" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            await panel("⏳ ...", page_tag=f"chview:{aid}:{idx}")
            ok, res = await export_invite_link(aid, idx)
            if ok:
                return await panel(head("🔗", "لینک") + f"\n\n<code>{esc(res)}</code>",
                                   kb_([B("🔄", f"ch:getlink:{aid}:{idx}")],
                                       [B("✍️ دستی", f"ch:setlink:{aid}:{idx}")],
                                       [B("⬅️", f"ch:view:{aid}:{idx}")]),
                                   page_tag=f"chview:{aid}:{idx}")
            return await panel(head("⚠️", "ناموفق") + f"\n{esc(str(res)[:600])}",
                               kb_([B("✍️ دستی", f"ch:setlink:{aid}:{idx}")],
                                   [B("🔍", f"ch:diag:{aid}:{idx}")],
                                   [B("⬅️", f"ch:view:{aid}:{idx}")]),
                               page_tag=f"chview:{aid}:{idx}")
        if sub == "setlink" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            get_conv(cid)["setlink"] = {"aid": aid, "idx": idx}
            return await ask("✍️ لینک:")
        if sub == "diag" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            await panel("🔍 ...", page_tag=f"chview:{aid}:{idx}")
            try: dump = await diagnose_channel(aid, idx)
            except Exception as e: dump = f"ERR: {type(e).__name__}: {e}"
            return await panel(head("🔍", "عیب‌یابی") + f"\n<pre>{esc(dump[:3500])}</pre>",
                               kb_([B("⬅️", f"ch:view:{aid}:{idx}")]), page_tag=f"chview:{aid}:{idx}")
        if sub == "del" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            channels = get_stored_channels(aid)
            if idx >= len(channels): return await show_ch_list(aid)
            return await panel(f"🗑 حذف <b>{esc(channels[idx].get('title','?'))}</b>؟",
                               kb_([B("✅", f"ch:delok:{aid}:{idx}"), B("❌", f"ch:view:{aid}:{idx}")]),
                               page_tag=f"chview:{aid}:{idx}")
        if sub == "delok" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            remove_channel_from_storage(aid, idx)
            await tg_send("🗑")
            return await show_ch_list(aid)

    if h == "chlist":
        sub = p[1] if len(p) > 1 else ""
        if sub == "show": return await show_ch_list(p[2], int(p[3]) if len(p) > 3 else 0)

    if h == "chsend":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            get_conv(cid)["chsend"] = {"aid": aid, "idx": idx, "step": "compose"}
            return await ask("📤 متن:")

    if h == "chnew":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            aid = p[2]
            get_conv(cid)["chnew"] = {"aid": aid, "step": "title"}
            return await ask("🏗 اسم کانال:")
        if sub == "pub":
            aid = p[2]; info = get_conv(cid).get("chnew") or {}
            title = info.get("title")
            if not title: return await panel("⚠️", kb_(nav(f"ch:menu:{aid}")), page_tag=f"ch_menu:{aid}")
            get_conv(cid)["chnew"] = {"aid": aid, "step": "username", "title": title}
            return await ask("🌐 یوزرنیم:")
        if sub == "priv":
            aid = p[2]; info = get_conv(cid).get("chnew") or {}
            title = info.get("title")
            if not title: return await panel("⚠️", kb_(nav(f"ch:menu:{aid}")), page_tag=f"ch_menu:{aid}")
            get_conv(cid).pop("chnew", None)
            a = get_account(aid); STATE["panel"].pop(cid, None)
            if not a: return await panel("⚠️", kb_(nav()), page_tag="main")
            await panel("⏳ ساخت...", page_tag="chnew_run")
            cli = None; ok = False; msg_r = ""; ch_obj = None
            try:
                cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
                if cli: ok, ch_obj, msg_r = await soroosh_create_channel(cli, title)
                else: ok, msg_r = False, f"اتصال: {err}"
            except Exception as e: ok, msg_r = False, f"{type(e).__name__}: {_fmt_error(e)}"
            finally:
                if cli:
                    try: await cli._disconnect()
                    except Exception: pass
            _STATS_CACHE.pop(aid, None)
            if ok:
                store = _channel_data_from_obj(ch_obj)
                store["type"] = "private"; store["created"] = int(time.time())
                add_channel_to_storage(aid, store)
                body = head("✅", "ساخته شد") + f"📝 {esc(title)}"
                return await panel(body, kb_([B("⚙️", f"chlist:show:{aid}:0")],
                                             [B("⬅️", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")
            return await panel(f"❌ <code>{esc(str(msg_r)[:300])}</code>",
                               kb_([B("⬅️", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")

    if h == "prof":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu": return await show_profile_menu(p[2])
        if sub == "set":
            field = p[2]; aid = p[3]
            get_conv(cid)["prof_field"] = {"field": field, "aid": aid}
            prompts = {"first": "👤:", "last": "👤:", "about": "📖:", "username": "🔤:"}
            return await ask(prompts.get(field, "مقدار:"))

    if h == "ld":
        sub = p[1] if len(p) > 1 else ""
        back = p[3] if len(p) > 3 else (p[2] if len(p) > 2 else "jl:back_to_settings")
        if sub == "list": return await show_linkdonies(back)
        if sub == "add":
            get_conv(cid)["ld_wait"] = "url"; get_conv(cid)["ld_back"] = back
            return await ask("📡 لینک:")
        if sub == "del" and len(p) >= 3:
            remove_link_doni(int(p[2])); await tg_send("🗑"); return await show_linkdonies(back)
        if sub == "reset":
            save_link_donies(list(DEFAULT_LINK_DONIES)); await tg_send("🔄"); return await show_linkdonies(back)
        if sub == "reset_prog":
            _reset_ld_progress(); await tg_send("🔄"); return await show_linkdonies(back)
        if sub == "toggle_autojoin":
            cfg = _load(CFG_FILE, DEFAULT_CFG)
            cfg["auto_join_linkdoni"] = 0 if int(cfg.get("auto_join_linkdoni", 1)) else 1
            _save(CFG_FILE, cfg); return await show_linkdonies(back)

    if h == "err":
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_errors(int(p[2]))
        if sub == "clear": clear_errors(); await tg_send("🗑"); return await show_errors()

    if h == "listen":
        sub = p[1] if len(p) > 1 else ""
        if sub == "restart":
            await restart_all_listeners(); await tg_send("🔄"); return await show_listen_menu()
        if sub == "toggle" and len(p) >= 3:
            aid = p[2]; t = LISTENER_TASKS.get(aid)
            if t and not t.done(): _stop_listener_for(aid); await tg_send("⚪")
            else: await start_all_listeners(); await tg_send("🟢")
            await asyncio.sleep(0.3); return await show_listen_menu()

    if h == "op":
        sub = p[1] if len(p) > 1 else ""; oid = p[2] if len(p) > 2 else None
        if sub == "view" and oid: return await show_op_detail(oid)
        if sub == "stop" and oid:
            op = _get_op(oid)
            if op:
                if op.get("type") in ("joinlef", "autotar"):
                    t = JL_JOBS.get(oid)
                    if t and not t.done(): t.cancel()
                else:
                    st = STATE.get("cancel_" + oid)
                    if st: st.set()
                op["status"] = "cancelled"; op["finished_at"] = int(time.time()); _save_op(op)
            return await show_op_detail(oid)

    if h == "send":
        s = _send_conv(cid); sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            s["step"] = "accounts"; s["accounts"] = s.get("accounts") or []
            return await show_send_step(cid)
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if "all" in sel: sel.remove("all")
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await show_send_step(cid)
        if sub == "accall":
            s["accounts"] = [] if "all" in (s.get("accounts") or []) else ["all"]
            return await show_send_step(cid)
        if sub == "accnext":
            if not s.get("accounts"): return await show_send_step(cid)
            s["step"] = "compose"; return await show_send_step(cid)
        if sub == "recompose": s["step"] = "compose"; s["payload"] = None; return await show_send_step(cid)
        if sub == "composenext":
            if not s.get("payload"): return await show_send_step(cid)
            s["step"] = "target"; return await show_send_step(cid)
        if sub == "tgt" and len(p) >= 3: s["target"] = p[2]; return await show_send_step(cid)
        if sub == "toggle_auto_left": s["auto_left"] = not s.get("auto_left", False); return await show_send_step(cid)
        if sub == "toggle_groups_only": s["groups_only"] = not s.get("groups_only", True); return await show_send_step(cid)
        if sub == "toggle_infinite": s["infinite_loop"] = not s.get("infinite_loop", False); return await show_send_step(cid)
        if sub == "loop_delay":
            get_conv(cid)["send_edit_wait"] = "loop_delay"; return await ask("⏱ تاخیر بین دورها (ثانیه):")
        if sub == "toggle_edit": s["edit_delay_enabled"] = not s.get("edit_delay_enabled", False); return await show_send_step(cid)
        if sub == "edit_sec":
            get_conv(cid)["send_edit_wait"] = "sec"; return await ask("⏱ تاخیر (ثانیه):")
        if sub == "edit_ph":
            get_conv(cid)["send_edit_wait"] = "ph"; return await ask("💬 پیام اولیه:")
        if sub == "toggle_edit_rand": s["edit_delay_random"] = not s.get("edit_delay_random", False); return await show_send_step(cid)
        if sub == "toggle_ph_rand": s["placeholder_random"] = not s.get("placeholder_random", False); return await show_send_step(cid)
        if sub == "toggle_multi": s["multi_step_edit"] = not s.get("multi_step_edit", False); return await show_send_step(cid)
        if sub == "attach":
            get_conv(cid)["send_file_upload"] = True
            return await ask("📎 فایل رو بفرست:")
        if sub == "tgtnext": s["step"] = "max"; return await show_send_step(cid)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["send_wait"] = "max"; return await ask("🔢 (0=∞):")
            try: s["max"] = int(v)
            except: pass
            return await show_send_step(cid)
        if sub == "maxnext": s["step"] = "confirm"; return await show_send_step(cid)
        if sub == "back": s["step"] = "accounts"; return await show_send_step(cid)
        if sub == "prev":
            order = ["accounts", "compose", "target", "max", "confirm"]
            i = order.index(s.get("step", "accounts"))
            s["step"] = order[max(0, i-1)]; return await show_send_step(cid)
        if sub == "back_edit": s["step"] = "accounts"; return await show_send_step(cid)
        if sub == "cancel": clear_conv(cid); return await show_main()
        if sub == "go":
            accounts = list_accounts(); sel = s.get("accounts") or []
            if "all" in sel: sel = list(accounts.keys())
            op = {"id": "sd_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "send", "accounts": sel, "target": s.get("target", "both"),
                  "max": s.get("max", 0) or 0, "payload": s.get("payload") or {"text": "سلام"},
                  "delay": 1.5, "auto_left": bool(s.get("auto_left", False)), "status": "running",
                  "groups_only": bool(s.get("groups_only", True)),
                  "attach_file": s.get("attach_file", ""),
                  "infinite_loop": bool(s.get("infinite_loop", False)),
                  "loop_delay": float(s.get("loop_delay", 3.0)),
                  "edit_delay_enabled": bool(s.get("edit_delay_enabled", False)),
                  "edit_delay_seconds": float(s.get("edit_delay_seconds", 3.0)),
                  "edit_delay_random": bool(s.get("edit_delay_random", False)),
                  "edit_delay_min": float(s.get("edit_delay_min", 2.0)),
                  "edit_delay_max": float(s.get("edit_delay_max", 6.0)),
                  "placeholder_text": s.get("placeholder_text", "سلام"),
                  "placeholder_random": bool(s.get("placeholder_random", False)),
                  "placeholder_list": s.get("placeholder_list", ""),
                  "multi_step_edit": bool(s.get("multi_step_edit", False)),
                  "multi_step_middle": s.get("multi_step_middle", "Hi"),
                  "progress": {"sent": 0, "failed": 0, "total": 0, "pending": 0, "in_progress": 0, "phase": "شروع", "blocked": 0, "round": 0},
                  "errors": []}
            _save_op(op); clear_conv(cid)
            asyncio.create_task(run_sender(op, log_cb))
            return await show_op_detail(op["id"])


# ═══════════════ BOOT ═══════════════
async def _post_init(app):
    try:
        from telegram import BotCommand
        await app.bot.set_my_commands([BotCommand("start", "شروع"), BotCommand("menu", "منو")])
    except Exception: pass
    try: _loop_ref[0] = asyncio.get_running_loop()
    except Exception: pass
    try:
        await start_all_listeners()
        await start_pv_responders()
        asyncio.create_task(keepalive_loop())
    except Exception as e:
        flog(f"[post_init] auto-start fail: {type(e).__name__}: {e}")

async def _on_error(update, context):
    flog(f"[!] {type(context.error).__name__}: {context.error}", "error")

async def cmd_start(update, context):
    cid = update.effective_chat.id
    if cid != FORCED_OWNER: return
    STATE["panel"].pop(cid, None)
    STATE.setdefault("op_panel", {}).pop(cid, None)
    _TMP_EDIT.pop(cid, None)
    await show_main()

async def cmd_menu(update, context):
    if not authorized(update): return
    await cmd_start(update, context)

async def on_callback(update, context):
    q = update.callback_query
    if q is None: return
    try: await q.answer()
    except Exception: pass
    if not authorized(update): return
    cid = update.effective_chat.id
    if q.message: STATE["panel"][cid] = q.message.message_id
    data = q.data or ""
    if data == "noop": return
    try: await route_cb(cid, data)
    except Exception as e:
        flog(f"[callback] {data} FAIL: {traceback.format_exc()}", "error")
        await tg_send(f"❌ {type(e).__name__}: {str(e)[:200]}")

def main(token=None, owner_id=None):
    global APP, TG_TOKEN, FORCED_OWNER
    if token: TG_TOKEN = token
    else: TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
    if not TG_TOKEN or ":" not in TG_TOKEN: print("[x] TG_TOKEN نیست."); return
    if owner_id: FORCED_OWNER = int(owner_id)
    else:
        try: FORCED_OWNER = int(os.environ.get("TG_OWNER_ID", "8389746549"))
        except: FORCED_OWNER = 8389746549
    STATE["owner"] = FORCED_OWNER; ensure_soroosh_loop()
    flog(f"[+] VERSION: {VERSION}"); flog(f"[+] DATA_DIR: {DATA_DIR}")
    req = HTTPXRequest(connection_pool_size=8, connect_timeout=30.0,
                       read_timeout=30.0, write_timeout=30.0, pool_timeout=30.0)
    APP = (Application.builder().token(TG_TOKEN).request(req)
           .get_updates_request(req).post_init(_post_init).build())
    APP.add_handler(CommandHandler("start", cmd_start))
    APP.add_handler(CommandHandler("menu", cmd_menu))
    APP.add_handler(CallbackQueryHandler(on_callback))
    APP.add_handler(MessageHandler(tg_filters.ALL & ~tg_filters.COMMAND, on_message))
    APP.add_error_handler(_on_error)
    flog("[+] polling...")
    APP.run_polling(allowed_updates=Update.ALL_TYPES, poll_interval=2.0, timeout=30.0)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n[!] قطع")