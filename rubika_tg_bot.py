# app.py — v71 (native-rp-session + no-relogin + keepalive + joiner + channel-send)
import os, sys, ssl, json, socket, asyncio, time, glob, re, threading, secrets, queue
import logging, traceback, concurrent.futures, inspect
import html as _html
import builtins

VERSION = "v71"

def _detect_data_dir():
    env = os.environ.get("DATA_DIR", "").strip()
    if env and os.path.isdir(env) and os.access(env, os.W_OK): return env
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        for c in ["/data", "/app/data"]:
            if os.path.isdir(c) and os.access(c, os.W_OK): return c
    return os.path.dirname(os.path.abspath(__file__))

DATA_DIR = _detect_data_dir()
print(f"[+] VERSION: {VERSION}")
print(f"[+] DATA_DIR: {DATA_DIR}")

try:
    import asyncio.unix_events as _ue
    _orig_add_signal = _ue._UnixSelectorEventLoop.add_signal_handler
    def _safe_add_signal(self, sig, callback, *args):
        try: return _orig_add_signal(self, sig, callback, *args)
        except (RuntimeError, ValueError, NotImplementedError, AttributeError): return None
    _ue._UnixSelectorEventLoop.add_signal_handler = _safe_add_signal
except Exception: pass

_rl = logging.getLogger("rubpy"); _rl.setLevel(logging.WARNING)
_h = logging.StreamHandler(sys.stderr); _h.setFormatter(logging.Formatter('[rubpy] %(message)s'))
_rl.addHandler(_h); _rl.propagate = False
for _n in ("urllib3","urllib3.connectionpool","requests","httpx","httpcore",
           "telegram.ext.Updater","telegram.request"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)
    logging.getLogger(_n).propagate = False

import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["SSL_CERT_DIR"] = ""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SESSION_REQ = requests.Session()
SESSION_REQ.mount("https://", HTTPAdapter(pool_connections=32, pool_maxsize=32,
    max_retries=Retry(total=2, backoff_factor=0.3)))

_orig_gai = socket.getaddrinfo
_doh_cache = {}; _doh_lock = threading.Lock()
def _doh(h):
    h = str(h).strip().rstrip(".")
    with _doh_lock:
        if h in _doh_cache: return _doh_cache[h]
    ip = False
    for u in ("https://1.1.1.1/dns-query","https://8.8.8.8/resolve"):
        try:
            r = SESSION_REQ.get(u, params={"name": h, "type":"A"},
                headers={"accept":"application/dns-json"}, timeout=5)
            ips = [a["data"] for a in r.json().get("Answer",[]) if a.get("type")==1]
            if ips: ip = ips[0]; break
        except Exception: pass
    with _doh_lock: _doh_cache[h] = ip
    return ip
def _patched_gai(host, port, *a, **kw):
    try:
        h = host.decode() if isinstance(host, bytes) else host
        if isinstance(h, str) and h.endswith(".iranlms.ir"):
            ip = _doh(h)
            if ip: return _orig_gai(ip, port, *a, **kw)
    except Exception: pass
    return _orig_gai(host, port, *a, **kw)
socket.getaddrinfo = _patched_gai

try:
    r = SESSION_REQ.get("https://getdcmess.iranlms.ir/", timeout=10)
    DC = list(r.json()["data"]["API"].values())
    print(f"[+] {len(DC)} DC")
except Exception as e:
    print(f"[x] DC fetch: {e}"); DC = []

import rulog.GtM as GtM
GtM.list_servers.clear(); GtM.list_servers.extend(DC)
if len(GtM.list_servers) > 1: GtM.list_servers.pop(1)
GtM.Server_Rubika = lambda: None
if DC:
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(_doh, [s.get("ip") if isinstance(s, dict) else str(s) for s in DC[:60]]))

from rubpy import Client as _C

# ══════════════════════════════════════════════════════════════
# ACCOUNT LOCKS
# ══════════════════════════════════════════════════════════════
_ACCOUNT_LOCKS = {}
_ACCOUNT_LOCKS_GUARD = threading.Lock()

def _get_account_lock(aid):
    if not aid: return None
    with _ACCOUNT_LOCKS_GUARD:
        if aid not in _ACCOUNT_LOCKS:
            _ACCOUNT_LOCKS[aid] = asyncio.Lock()
        return _ACCOUNT_LOCKS[aid]


# ══════════════════════════════════════════════════════════════
# ★ SafeClient — باریک، فقط lock + no-prompt.
#   auth و session توسط rubpy در فایل {name}.rp مدیریت میشه.
# ══════════════════════════════════════════════════════════════
class SafeClient(_C):
    """rubpy Client با قفل per-account + جلوگیری از بلاک شدن روی input().

    فایل session ({name}.rp) هرگز حذف نمیشه — rubpy خودش پس از هر
    اتصال، auth چرخیده رو داخلش می‌نویسه و بار بعد از همون می‌خونه.
    """

    def __init__(self, *args, **kwargs):
        self._aid = kwargs.pop("_aid", None)
        self._lock = _get_account_lock(self._aid) if self._aid else None
        name = kwargs.get("name") or (args[0] if args else "")
        if not name:
            name = f"session_{self._aid or secrets.token_hex(4)}"
            if args: args = (name,) + args[1:]
            else: kwargs["name"] = name
        super().__init__(*args, **kwargs)

    async def __aenter__(self):
        if self._lock: await self._lock.acquire()
        try:
            await self.start()
            return self
        except Exception:
            if self._lock:
                try: self._lock.release()
                except Exception: pass
            raise

    async def start(self, phone_number=None):
        # rubpy خودش از فایل {name}.rp می‌خونه. اگر فایل نبود یا auth باطل
        # بود، rubpy از input() استفاده می‌کنه — ما اون رو بلاک می‌کنیم تا
        # نخوایم روی سرور بی‌کار بایسته.
        def _no_prompt(prompt=""):
            raise RuntimeError("NO_SESSION: session file missing or expired")

        old_input = builtins.input
        builtins.input = _no_prompt
        try:
            await super().start(phone_number=phone_number)
        finally:
            builtins.input = old_input

        # تأیید سلامت اتصال
        try:
            me = await self.get_me()
            self.guid = me.user.user_guid
        except Exception as e:
            raise RuntimeError(f"NO_SESSION: get_me failed — {e}")
        return self

    async def __aexit__(self, *args, **kwargs):
        try:
            return await super().__aexit__(*args, **kwargs)
        finally:
            if self._lock:
                try: self._lock.release()
                except Exception: pass


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def _g(o, *names, default=None):
    for n in names:
        if o is None: return default
        if isinstance(o, dict):
            if n in o: return o[n]
        else:
            v = getattr(o, n, None)
            if v is not None: return v
    return default

def _to_dict(o):
    if o is None: return None
    if isinstance(o, dict): return o
    if hasattr(o, "to_dict"):
        try: return o.to_dict()
        except Exception: pass
    try: return {k: v for k, v in vars(o).items() if not k.startswith("_")}
    except Exception: return None

def _to_plain(o, depth=0):
    if depth > 6: return str(o)[:80]
    if o is None or isinstance(o, (str, int, float, bool)): return o
    if isinstance(o, dict): return {str(k): _to_plain(v, depth+1) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_to_plain(x, depth+1) for x in o]
    d = _to_dict(o)
    if isinstance(d, dict): return _to_plain(d, depth+1)
    return str(o)[:80]

def _find_keys(o, keys, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in keys and k not in out: out[k] = v
            _find_keys(v, keys, out)
    elif isinstance(o, list):
        for x in o: _find_keys(x, keys, out)
    return out

def _is_auth_error(ex):
    s = str(ex) + " " + _fmt_error(ex)
    return any(k in s for k in ("INVALID_AUTH","NOT_REGISTERED","AUTH_DEAD","NO_SESSION"))

def _is_ok_response(r):
    if r is None: return True
    d = _to_dict(r)
    if not isinstance(d, dict): return True
    for k in ("status","status_det"):
        s = str(d.get(k) or "").upper()
        if s and ("ERROR" in s or "INVALID" in s or "FAIL" in s or "NOT_" in s):
            return False
    nested = d.get("data") or d.get("result")
    if isinstance(nested, dict): return _is_ok_response(nested)
    return True

def _extract_join_link(r):
    if r is None: return None
    if isinstance(r, dict):
        for k in ("join_link","link","url","invite_link","invite"):
            v = r.get(k)
            if isinstance(v, str) and v.startswith("http"): return v
        for k in ("data","result","chat","response"):
            n = r.get(k)
            if isinstance(n, dict):
                x = _extract_join_link(n)
                if x: return x
    else:
        for k in ("join_link","link","url","invite_link","invite"):
            v = getattr(r, k, None)
            if isinstance(v, str) and v.startswith("http"): return v
    try:
        s = str(r); m = re.search(r'https?://[^\s"\'<>]+', s)
        if m: return m.group(0)
    except Exception: pass
    return None

def _is_rate_limit(ex):
    s = str(ex).upper()
    return any(k in s for k in ("TOO_REQUESTS","RATE_LIMIT","FLOOD","TOO_MANY",
                                 "استفاده بیش از حد","بیش از حد مجاز"))
def _is_auth_dead(ex): return "AUTH_DEAD" in str(ex) or "NO_SESSION" in str(ex)
def _is_transient(ex): return "TRANSIENT" in str(ex)
def _is_username_limit(ex):
    s = str(ex)
    return ("10" in s and ("نام کاربری" in s or "username" in s.lower())) or \
           "maximum number of username" in s.lower() or "حداکثر تعداد نام کاربری" in s

def _load(path, default):
    if not os.path.exists(path): return dict(default) if isinstance(default, dict) else default
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

def _candidate_guid(o):
    if o is None: return None
    for k in ("object_guid","objectGuid","chat_guid","chatGuid","guid",
              "channel_guid","group_guid","user_guid"):
        v = _g(o, k)
        if isinstance(v, str) and v: return v
    return None

def extract_chat_guid(r):
    if r is None: return None
    for key in ("chat","data","result","channel","group"):
        o = _g(r, key)
        if o:
            g = _candidate_guid(o)
            if g: return g
            for k2 in ("chat","object","data"):
                o2 = _g(o, k2)
                if o2:
                    g = _candidate_guid(o2)
                    if g: return g
    return _candidate_guid(r)

def _fmt_time(sec):
    sec = int(sec)
    if sec < 60: return f"{sec}s"
    m = sec // 60
    if m < 60: return f"{m}m {sec%60}s"
    return f"{m//60}h {m%60}m"

def _fmt_error(e):
    if e is None: return "—"
    if isinstance(e, dict):
        parts = []
        for k in ("status","status_det"):
            if k in e: parts.append(f"{k}={e[k]}")
        msg = _g(e, "client_show_message", "message")
        if msg: parts.append(str(msg)[:150])
        return " | ".join(parts) or str(e)[:200]
    s = str(e)
    if hasattr(e, "args") and e.args:
        try:
            if isinstance(e.args[0], dict): return _fmt_error(e.args[0])
        except Exception: pass
    return s[:200]

def _filter_kwargs(fn, kw):
    try: sig = inspect.signature(fn)
    except Exception: return kw
    for p in sig.parameters.values():
        if p.kind == inspect.Parameter.VAR_KEYWORD: return kw
    valid = set(sig.parameters.keys())
    return {k: v for k, v in kw.items() if k in valid}

async def _try_methods(bot, method_names, kw_variants):
    errors = []
    for name in method_names:
        fn = getattr(bot, name, None)
        if not fn: continue
        for base in kw_variants:
            kw = _filter_kwargs(fn, base)
            if not kw: continue
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                return True, f"{name}({list(kw.keys())})", None
            except Exception as e:
                errors.append(f"{name}: {_fmt_error(e)}"); continue
    return False, None, " | ".join(errors[:4]) or "هیچ متدی جواب نداد"

LINK_RE = re.compile(r'@([A-Za-z][A-Za-z0-9_]{4,40})')
URL_RE = re.compile(r'(?:rubika\.ir|ble\.rip)/joing/([A-Za-z0-9_\-]+)', re.I)
URL_RE2 = re.compile(r'rubika\.ir/([A-Za-z0-9_\-]{20,})', re.I)

ACC_FILE = os.path.join(DATA_DIR, "accounts.json")
CFG_FILE = os.path.join(DATA_DIR, "multi_config.json")
QUEUE_FILE = os.path.join(DATA_DIR, "queue.json")
OWNER_FILE = os.path.join(DATA_DIR, "tg_owner.json")
OPS_FILE = os.path.join(DATA_DIR, "ops.json")
ERRORS_FILE = os.path.join(DATA_DIR, "errors.json")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
try: os.makedirs(MEDIA_DIR, exist_ok=True)
except Exception: pass
try: os.makedirs(SESSIONS_DIR, exist_ok=True)
except Exception: pass

MAX_ERRORS = 100
RATE_LIMIT_WAIT = 20 * 60
ANCHORS = {}
JL_JOBS = {}

KEEPALIVE_SECONDS = 15 * 60   # ★ ۱۵ دقیقه — پینگ سبک برای زنده نگه‌داشتن سشن

JOINER_CONFIG = {
    "extract_max_rounds": 20, "join_per_batch": 100, "batch_pause": 2,
    "rate_limit_pause": 20 * 60, "max_join_per_hour": 500, "join_delay": 0.5,
}

JL_SPEEDS = [
    ("ultra", "🚀 فوق‌سریع", 0.3),
    ("fast", "⚡ سریع", 1.0),
    ("normal", "🐢 عادی", 3.0),
    ("slow", "🛡 امن", 8.0),
]

_OP_LOCKS = {}
def _get_op_lock(oid):
    if oid not in _OP_LOCKS:
        _OP_LOCKS[oid] = asyncio.Lock()
    return _OP_LOCKS[oid]


DEFAULT_CFG = {
    "delay": 8.0, "cooldown": 180, "max_parallel": 2,
    "batch_per_account": 2, "max_attempts": 3,
    "max_channels_per_account": 3,
    "listener": 1,
    "listener_service_only": 1,
    "channels": ["@linkdony_rubikas", "@lovo_lovoo0"],
}

TG_TOKEN = os.environ.get("TG_TOKEN","").strip()

# ══════════════════════════════════════════════════════════════
# LISTENER (بدون code capture — فقط forward)
# ══════════════════════════════════════════════════════════════
LISTENER_SEEN = {}
LISTENER_SEEN_LOCK = threading.Lock()
LISTENER_MAX_SEEN = 8000
LISTENER_TASKS = {}

def is_login_service_message(chat_title, text):
    title = (chat_title or "")
    txt = (text or "")
    tl = title.lower(); xl = txt.lower()
    if "اعلان" in title or "ورود" in title: return True
    if "login" in tl or "login" in xl: return True
    if "کد روبیکا" in txt or "code " in xl or "code:" in xl: return True
    return False

def _listener_should_show(chat_type):
    t = (chat_type or "").strip().lower()
    if t in ("group", "channel"): return False
    return True

def _listener_chat_kind(chat_type):
    t = (chat_type or "").strip().lower()
    if "bot" in t: return "🤖 ربات"
    if "service" in t or "system" in t: return "⚙️ سرویس"
    if t == "user": return "👤 شخصی"
    return f"📩 {chat_type or 'ناشناس'}"

def _listener_cfg_enabled():
    try: return bool(int(_load(CFG_FILE, DEFAULT_CFG).get("listener", 1)))
    except Exception: return True

def _listener_cfg_service_only():
    try: return bool(int(_load(CFG_FILE, DEFAULT_CFG).get("listener_service_only", 1)))
    except Exception: return True


async def report_new_message(acc_name, chat_title, chat_guid, chat_type, msg):
    text_raw = (msg.get("text") or "").strip()
    title_s = (chat_title or "")
    if _listener_cfg_service_only():
        if not is_login_service_message(title_s, text_raw): return
    if not STATE.get("owner") or APP is None: return
    STATE["listener_new_count"] = STATE.get("listener_new_count", 0) + 1
    kind = _listener_chat_kind(chat_type)
    typ = msg.get("type") or "Text"
    sender = str(msg.get("sender") or "")[:24]
    t = msg.get("time") or ""
    try:
        ts = int(t)
        tstr = time.strftime("%H:%M:%S", time.localtime(ts)) if ts > 1_000_000_000 else str(t)[:20]
    except Exception: tstr = str(t)[:20]
    body = (f"📥 <b>پیام جدید</b> · <code>{kind}</code>\n{HR}\n"
            f"📱 اکانت: <b>{esc(acc_name)}</b>\n"
            f"💬 چت: <b>{esc(chat_title or chat_guid[:14])}</b>\n"
            f"🆔 <code>{esc(chat_guid)}</code>\n"
            f"👤 فرستنده: <code>{esc(sender or '?')}</code>\n"
            f"🔖 نوع: <b>{esc(typ)}</b>\n")
    if tstr: body += f"🕐 {esc(tstr)}\n"
    body += "\n"
    body += (f"💬 <code>{esc(text_raw[:1200])}</code>" if text_raw
             else f"📎 <i>(بدون متن — {esc(typ)})</i>")
    try: await tg_send(body, parse_mode=ParseMode.HTML)
    except Exception as e: print(f"[report-err] {e}")


async def _listener_seed(bot, aid, my_guid, nm):
    try: chats = await get_all_chats_raw(bot)
    except Exception: return
    count = 0
    for c in chats:
        if not _listener_should_show(c.get("type")): continue
        if c["guid"] == my_guid: continue
        if c.get("is_blocked"): continue
        try:
            msgs = await fetch_messages(bot, c["guid"], limit=5, my_guid=my_guid)
            with LISTENER_SEEN_LOCK:
                for m in msgs:
                    key = f"{aid}:{c['guid']}:{m['id']}"
                    LISTENER_SEEN[key] = time.time(); count += 1
        except Exception: continue
    print(f"[listener-seed] {nm}: {count} messages marked")

async def _listener_check(bot, aid, my_guid, nm):
    try: chats = await get_all_chats_raw(bot)
    except Exception: return
    for c in chats:
        if not _listener_should_show(c.get("type")): continue
        if c["guid"] == my_guid: continue
        if c.get("is_blocked"): continue
        try: msgs = await fetch_messages(bot, c["guid"], limit=5, my_guid=my_guid)
        except Exception: continue
        for m in msgs:
            if m.get("is_mine"): continue
            key = f"{aid}:{c['guid']}:{m['id']}"
            with LISTENER_SEEN_LOCK:
                if key in LISTENER_SEEN: continue
                LISTENER_SEEN[key] = time.time()
                if len(LISTENER_SEEN) > LISTENER_MAX_SEEN:
                    oldest = sorted(LISTENER_SEEN.items(), key=lambda x: x[1])[:1500]
                    for k, _ in oldest: LISTENER_SEEN.pop(k, None)
            await report_new_message(nm, c["title"], c["guid"], c.get("type"), m)


async def pv_listener(aid, acc, stop_event):
    """لیسنر — چک و رها. هر N ثانیه قفل رو می‌گیره، چک می‌کنه، آزاد می‌کنه."""
    nm = acc.get("name") or acc.get("phone") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    print(f"[listener] {nm}: task started")
    seeded_once = False
    while not stop_event.is_set():
        try:
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot:
                me = await bot.get_me()
                my_guid = me.user.user_guid
                if not seeded_once:
                    try: await _listener_seed(bot, aid, my_guid, nm)
                    except Exception as e: print(f"[listener-seed-err] {nm}: {e}")
                    seeded_once = True
                # چند چک سریع با فاصله‌ی کوتاه، بعد آزاد کن و برو استراحت
                for _ in range(12):
                    if stop_event.is_set(): break
                    if not _listener_cfg_enabled():
                        await asyncio.sleep(5); continue
                    try: await _listener_check(bot, aid, my_guid, nm)
                    except Exception as e:
                        if _is_auth_error(e): raise
                        print(f"[listener-chk-err] {nm}: {type(e).__name__}")
                    await asyncio.sleep(5)
                try: await bot.get_me()
                except Exception: raise
        except asyncio.CancelledError:
            raise
        except RuntimeError as e:
            if _is_auth_dead(e):
                print(f"[listener] {nm}: NO_SESSION — stopped")
                return
            print(f"[listener] {nm}: runtime: {e}")
            await asyncio.sleep(20)
        except Exception as e:
            print(f"[listener-conn-err] {nm}: {type(e).__name__}")
            await asyncio.sleep(20)
        # استراحت بین چرخه‌ها تا worker بتونه از قفل استفاده کنه
        await asyncio.sleep(30)


async def start_all_listeners():
    accounts = list_accounts()
    for aid, acc in accounts.items():
        if aid in LISTENER_TASKS and not LISTENER_TASKS[aid].done(): continue
        stop = asyncio.Event()
        STATE.setdefault("listener_stops", {})[aid] = stop
        t = asyncio.create_task(pv_listener(aid, acc, stop))
        LISTENER_TASKS[aid] = t
        print(f"[listener] started for {aid}")

def _spawn_listener_for(aid):
    loop = _loop_ref[0]
    if loop is None: return
    def _go():
        try:
            acc = get_account(aid)
            if not acc: return
            if aid in LISTENER_TASKS and not LISTENER_TASKS[aid].done(): return
            stop = asyncio.Event()
            STATE.setdefault("listener_stops", {})[aid] = stop
            t = asyncio.create_task(pv_listener(aid, acc, stop))
            LISTENER_TASKS[aid] = t
        except Exception as e: print(f"[listener-spawn] {e}")
    try: loop.call_soon_threadsafe(_go)
    except Exception: pass

def _stop_listener_for(aid):
    loop = _loop_ref[0]
    if loop is None: return
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
        except Exception: pass
    for aid, t in list(LISTENER_TASKS.items()):
        if not t.done(): t.cancel()
    LISTENER_TASKS.clear()
    STATE["listener_stops"] = {}; STATE["listener_seeded"] = set()
    LISTENER_SEEN.clear()
    await asyncio.sleep(1)
    await start_all_listeners()

async def toggle_listener_cfg():
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    cfg["listener"] = 0 if int(cfg.get("listener",1)) else 1
    _save(CFG_FILE, cfg); return int(cfg["listener"])

async def toggle_service_only_cfg():
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    cfg["listener_service_only"] = 0 if int(cfg.get("listener_service_only",1)) else 1
    _save(CFG_FILE, cfg); return int(cfg["listener_service_only"])


# ══════════════════════════════════════════════════════════════
# KEEPALIVE LOOP — ★ قلب ماندگاری سشن
# ══════════════════════════════════════════════════════════════
async def keepalive_loop():
    """
    هر ۱۵ دقیقه یک ping سبک به هر اکانت. این تنها کاری‌ست که سشن روبیکا
    رو زنده نگه می‌داره — بدون این، سرور بعد از ۳۰-۶۰ دقیقه سشن رو
    invalidate می‌کنه.
    """
    print(f"[keepalive] started (interval={KEEPALIVE_SECONDS}s)")
    await asyncio.sleep(60)  # بذار listenerها اول خودشون وصل بشن
    while True:
        try:
            accounts = list_accounts()
            if not accounts:
                await asyncio.sleep(60); continue
            print(f"[keepalive] tick — {len(accounts)} accounts")
            for aid, acc in accounts.items():
                sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
                if not os.path.exists(sess + ".rp"):
                    print(f"[keepalive] {aid}: no .rp file — skip")
                    continue
                try:
                    cli = SafeClient(name=sess, _aid=aid)
                    async with cli as bot:
                        me = await bot.get_me()
                        nm = getattr(getattr(me, "user", me), "first_name", aid)
                        print(f"[keepalive] {aid}: ok ({nm})")
                except RuntimeError as e:
                    if _is_auth_dead(e):
                        print(f"[keepalive] {aid}: SESSION DEAD — needs relogin")
                        try:
                            await tg_send(
                                f"⚠️ <b>سشن مرده</b>\n"
                                f"📱 {esc(acc.get('name', aid))}\n"
                                f"<code>{esc(str(e)[:150])}</code>\n\n"
                                f"دوباره اضافه کن: ➕ افزودن اکانت")
                        except Exception: pass
                    else:
                        print(f"[keepalive] {aid}: runtime: {e}")
                except Exception as e:
                    print(f"[keepalive] {aid}: {type(e).__name__}: {e}")
                await asyncio.sleep(random.uniform(3, 8))
            await asyncio.sleep(KEEPALIVE_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[keepalive] loop err: {type(e).__name__}: {e}")
            await asyncio.sleep(60)


# ══════════════════════════════════════════════════════════════
# ERRORS
# ══════════════════════════════════════════════════════════════
_errors_lock = threading.Lock()

def _load_errors():
    data = _load(ERRORS_FILE, [])
    return data if isinstance(data, list) else []

def add_error(source, error, target=None, account=None):
    try:
        with _errors_lock:
            errors = _load_errors()
            errors.append({"time": int(time.time()), "source": str(source)[:40],
                "error": str(error or "")[:300], "target": str(target or "")[:120],
                "account": str(account or "")[:60]})
            if len(errors) > MAX_ERRORS: errors = errors[-MAX_ERRORS:]
            try: _save(ERRORS_FILE, errors)
            except Exception: pass
    except Exception: pass

def clear_errors():
    try:
        with _errors_lock: _save(ERRORS_FILE, [])
    except Exception: pass


# ══════════════════════════════════════════════════════════════
# QUEUE
# ══════════════════════════════════════════════════════════════
class TaskQueue:
    def __init__(self, path):
        self.path = path; self.lock = asyncio.Lock()
        self.tasks = _load(path, []) if os.path.exists(path) else []
        if not isinstance(self.tasks, list): self.tasks = []
    def _save(self): _save(self.path, self.tasks)
    async def add(self, items):
        async with self.lock:
            have = {(t.get("owner_account"), t["target"]) for t in self.tasks
                    if t["status"] in ("pending","in_progress")}
            n = 0
            for it in items:
                key = (it.get("owner_account"), it["target"])
                if key in have: continue
                it.setdefault("id", secrets.token_hex(8))
                it.setdefault("status","pending"); it.setdefault("attempts",0)
                it.setdefault("last_error",None); it.setdefault("assigned_to",None)
                self.tasks.append(it); n += 1; have.add(key)
            self._save(); return n
    async def claim(self, aid, n):
        async with self.lock:
            got = []
            for t in self.tasks:
                if len(got) >= n: break
                if t["status"] != "pending": continue
                owner = t.get("owner_account")
                if owner and owner != aid: continue
                t["status"] = "in_progress"; t["assigned_to"] = aid
                t["attempts"] = t.get("attempts",0) + 1
                got.append(dict(t))
            self._save(); return got
    async def complete(self, tid, ok, err=None, max_attempts=3):
        async with self.lock:
            for t in self.tasks:
                if t["id"] != tid: continue
                if ok: t["status"] = "done"; t["last_error"] = None
                else:
                    if t["attempts"] >= max_attempts: t["status"] = "failed"
                    else: t["status"] = "pending"; t["assigned_to"] = None
                    t["last_error"] = err
                break
            self._save()
    async def requeue_account(self, aid):
        async with self.lock:
            for t in self.tasks:
                if t["status"] == "in_progress" and t["assigned_to"] == aid:
                    t["status"] = "pending"; t["assigned_to"] = None
            self._save()
    async def requeue_no_attempt(self, ids):
        async with self.lock:
            idset = set(ids)
            for t in self.tasks:
                if t["id"] in idset and t["status"] in ("in_progress","pending"):
                    t["status"] = "pending"; t["assigned_to"] = None
                    if t.get("attempts", 0) > 0: t["attempts"] -= 1
            self._save()
    def stats(self):
        s = {"pending":0,"in_progress":0,"done":0,"failed":0}
        for t in self.tasks: s[t["status"]] = s.get(t["status"],0) + 1
        return s
    async def clear(self, *stat):
        async with self.lock:
            self.tasks = [t for t in self.tasks if t["status"] not in stat]; self._save()
    async def wipe(self):
        async with self.lock: self.tasks = []; self._save()


# ══════════════════════════════════════════════════════════════
# ACCOUNTS
# ══════════════════════════════════════════════════════════════
def list_accounts(): return _load(ACC_FILE, {})
def save_accounts(a): _save(ACC_FILE, a)
def get_account(aid): return list_accounts().get(aid)

def remove_account(aid, keep_session=False):
    accounts = list_accounts(); a = accounts.pop(aid, None); save_accounts(accounts)
    # ★ حذف فایل .rp هم
    if a:
        sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        for f in glob.glob(sess + "*"):
            try: os.remove(f)
            except Exception: pass

def add_account(aid, phone, name, user_guid):
    accounts = list_accounts()
    sess = os.path.join(SESSIONS_DIR, aid)
    accounts[aid] = {
        "phone": phone, "name": name, "user_guid": user_guid,
        "session_name": sess,
        "created": int(time.time()),
        "channels": [],
    }
    save_accounts(accounts)
    return sess

def remove_channel_from_storage(aid, idx):
    accounts = list_accounts()
    if aid not in accounts: return None
    chans = accounts[aid].get("channels",[])
    if idx < 0 or idx >= len(chans): return None
    removed = chans.pop(idx); accounts[aid]["channels"] = chans
    save_accounts(accounts); return removed

def add_channel_to_storage(aid, ch_data):
    accounts = list_accounts()
    if aid in accounts:
        accounts[aid].setdefault("channels",[]).append(ch_data)
        save_accounts(accounts)

def update_channel_field(aid, idx, key, value):
    accounts = list_accounts()
    if aid in accounts and idx < len(accounts[aid].get("channels",[])):
        accounts[aid]["channels"][idx][key] = value
        save_accounts(accounts)


# ══════════════════════════════════════════════════════════════
# LOGIN — ★ کاملاً از rubpy's native start(phone_number=) استفاده می‌کنه
# ══════════════════════════════════════════════════════════════
async def interactive_login_via_rubpy(admin_id, phone):
    """
    rubpy خودش phone → code → 2FA رو با input() مدیریت می‌کنه.
    ما input() رو patch می‌کنیم تا promptها به تلگرام رله بشن.
    نتیجه: فایل sessions/{aid}.rp ساخته میشه و از اون به بعد rubpy
    همیشه از همین فایل auth رو می‌خونه.
    """
    loop = asyncio.get_running_loop()
    q = queue.Queue()
    pending[admin_id] = {"step": "login", "q": q}

    def fake_input(prompt=""):
        msg = str(prompt).strip() or "مقدار بعدی رو بفرست:"
        asyncio.run_coroutine_threadsafe(
            bale_send(admin_id, f"📨 {msg}"), loop)
        return q.get(timeout=300)

    # ساخت aid جدید و session path
    aid = "acc_" + secrets.token_hex(4)
    sess_path = os.path.join(SESSIONS_DIR, aid)

    def worker():
        old = builtins.input
        builtins.input = fake_input
        try:
            async def run():
                c = _C(name=sess_path)
                await c.start(phone_number=phone)
                me = await c.get_me()
                try: await c.disconnect()
                except Exception: pass
                return me
            return asyncio.run(run())
        finally:
            builtins.input = old

    async def job():
        try:
            me = await asyncio.to_thread(worker)
            u = getattr(me, "user", me)
            name = getattr(u, "first_name", None) or phone
            guid = getattr(u, "user_guid", None) or getattr(u, "guid", None)
            # ثبت اکانت — session_name قطعی
            add_account(aid, phone, name, guid)
            # اسپاون listener
            _spawn_listener_for(aid)
            await bale_send(admin_id,
                            f"✅ وارد شد: {name}\n🆔 <code>{aid}</code>\n"
                            f"💾 {sess_path}.rp",
                            main_kb())
        except Exception as e:
            log.exception("login failed")
            # پاک‌سازی فایل نیم‌کاره
            for f in glob.glob(sess_path + "*"):
                try: os.remove(f)
                except Exception: pass
            await bale_send(admin_id, f"❌ لاگین ناموفق: {str(e)[:200]}", main_kb())
        finally:
            pending.pop(admin_id, None)

    asyncio.create_task(job())


# ══════════════════════════════════════════════════════════════
# Profile / Channels — دست‌نخورده
# ══════════════════════════════════════════════════════════════
async def rubika_set_name(bot, first_name, last_name=None):
    variants = [dict(first_name=first_name, last_name=last_name or ""), dict(first_name=first_name)]
    ok, info, err = await _try_methods(bot, ("update_profile","updateProfile","set_profile","setProfile"), variants)
    return (True, info) if ok else (False, err)
async def rubika_set_bio(bot, bio):
    variants = [dict(bio=bio), dict(bio=bio, first_name=None, last_name=None)]
    ok, info, err = await _try_methods(bot, ("update_profile","updateProfile","set_bio","setBio","update_bio","updateBio"), variants)
    return (True, info) if ok else (False, err)
async def rubika_set_username(bot, username):
    if username and not username.startswith("@"): username = "@" + username
    variants = [dict(username=username), dict(username=username.lstrip("@"))]
    ok, info, err = await _try_methods(bot, ("update_username","set_username","setUsername"), variants)
    return (True, info) if ok else (False, err)
async def rubika_set_photo(bot, my_guid, image_path):
    variants = [dict(object_guid=my_guid, image=image_path, thumbnail_file_id=None),
                dict(object_guid=my_guid, image=image_path)]
    ok, info, err = await _try_methods(bot, ("upload_avatar","uploadAvatar","set_avatar","setAvatar"), variants)
    return (True, info) if ok else (False, err)

async def rubika_check_channel_username(bot, username):
    uname = username.lstrip("@")
    try:
        r = bot.check_channel_username(username=uname)
        if asyncio.iscoroutine(r): r = await r
        status = str(_g(r,"status") or "").upper()
        if "OK" in status and "ERROR" not in status: return True, "آزاد"
        return True, f"status={status}"
    except Exception as e:
        err = _fmt_error(e)
        if _is_username_limit(err): return False, "__LIMIT__"
        if "TAKEN" in err.upper() or "NOT_AVAILABLE" in err.upper(): return False, f"@{uname} گرفته شده"
        return None, f"خطا: {err}"

async def rubika_set_chat_username(bot, chat_guid, username):
    uname = username.lstrip("@") if username else ""
    if not uname: return False, "یوزرنیم خالی"
    try:
        avail, info_chk = await rubika_check_channel_username(bot, uname)
        if avail is False: return False, info_chk
    except Exception: pass
    errors = []
    try:
        r = bot.update_channel_username(channel_guid=chat_guid, username=uname)
        if asyncio.iscoroutine(r): r = await r
        return True, "update_channel_username"
    except Exception as e: errors.append(f"بدون @: {_fmt_error(e)}")
    try:
        r = bot.update_channel_username(channel_guid=chat_guid, username="@" + uname)
        if asyncio.iscoroutine(r): r = await r
        return True, "update_channel_username(@)"
    except Exception as e: errors.append(f"با @: {_fmt_error(e)}")
    return False, " | ".join(errors)

async def rubika_set_chat_description(bot, guid, description):
    try:
        r = bot.edit_channel_info(channel_guid=guid, description=description)
        if asyncio.iscoroutine(r): r = await r
        return True, "edit_channel_info"
    except Exception as e: return False, _fmt_error(e)
async def rubika_set_chat_title(bot, guid, title):
    try:
        r = bot.edit_channel_info(channel_guid=guid, title=title)
        if asyncio.iscoroutine(r): r = await r
        return True, "edit_channel_info"
    except Exception as e: return False, _fmt_error(e)
async def rubika_set_chat_photo(bot, guid, image_path):
    variants = [dict(object_guid=guid, image=image_path, thumbnail_file_id=None),
                dict(object_guid=guid, image=image_path)]
    ok, info, err = await _try_methods(bot, ("upload_avatar","uploadAvatar","set_chat_photo","update_channel_photo"), variants)
    return (True, info) if ok else (False, err)


async def rubika_create_channel(bot, title, description="", channel_type="private"):
    try:
        r = bot.add_channel(title=title, description=description or None)
        if asyncio.iscoroutine(r): r = await r
        guid = extract_chat_guid(r)
    except Exception as e:
        return False, _fmt_error(e), None, None

    if not guid:
        for _ in range(3):
            await asyncio.sleep(1.5)
            try:
                chats = await get_all_chats_raw(bot)
                for c in chats:
                    if c["title"].strip() == title.strip() and c["type"] == "Channel":
                        guid = c["guid"]; break
            except Exception: pass
            if guid: break

    if not guid: return False, "guid پیدا نشد", None, None

    ctype = (channel_type or "private").lower()
    warnings = []

    if ctype == "private":
        await asyncio.sleep(1.5)
        for val in ("Private", "private"):
            fn = getattr(bot, "edit_channel_info", None) or getattr(bot, "editChannelInfo", None)
            if not fn: break
            try:
                r = fn(channel_guid=guid, channel_type=val)
                if asyncio.iscoroutine(r): r = await r
                break
            except Exception as e: warnings.append(f"private: {_fmt_error(e)}")
        await asyncio.sleep(1.5)

    join_link = None
    if ctype == "private":
        for attempt in range(3):
            try:
                fn = getattr(bot, "create_join_link", None)
                if fn:
                    r = fn(object_guid=guid, request_needed=False)
                    if asyncio.iscoroutine(r): r = await r
                    join_link = _extract_join_link(r)
                    if join_link: break
            except Exception as e: warnings.append(f"link attempt {attempt+1}: {_fmt_error(e)}")
            await asyncio.sleep(1.5 + attempt)

    return True, "add_channel+" + ctype, guid, join_link


async def rubika_create_join_link(bot, guid, attempts=3):
    last_err = None
    for attempt in range(attempts):
        variants = [
            dict(object_guid=guid, request_needed=False),
            dict(object_guid=guid, request_needed=False, usage_limit=0),
            dict(object_guid=guid, request_needed=False, expire_time=None),
            dict(object_guid=guid), dict(chat_id=guid), dict(channel_guid=guid),
        ]
        for mname in ("create_join_link","createJoinLink","add_join_link","addJoinLink"):
            fn = getattr(bot, mname, None)
            if not fn: continue
            for base in variants:
                try:
                    kw = _filter_kwargs(fn, base)
                    if not kw: continue
                    r = fn(**kw)
                    if asyncio.iscoroutine(r): r = await r
                    link = _extract_join_link(r)
                    if link: return True, link
                    last_err = f"بدون لینک: {str(r)[:180]}"
                except TypeError: continue
                except Exception as e: last_err = _fmt_error(e); continue
        for mname in ("get_join_links","getJoinLinks","get_channel_link","getChannelLink"):
            fn = getattr(bot, mname, None)
            if not fn: continue
            for base in ({"object_guid": guid}, {"channel_guid": guid}, {"chat_id": guid}):
                try:
                    kw = _filter_kwargs(fn, base)
                    if not kw: continue
                    r = fn(**kw)
                    if asyncio.iscoroutine(r): r = await r
                    link = _extract_join_link(r)
                    if link: return True, link
                except TypeError: continue
                except Exception as e: last_err = _fmt_error(e); continue
        if attempt < attempts - 1: await asyncio.sleep(1.5 + attempt)
    return False, last_err or "لینک پیدا نشد"

async def rubika_remove_channel(bot, guid):
    try:
        r = bot.remove_channel(channel_guid=guid)
        if asyncio.iscoroutine(r): r = await r
        return True, "remove_channel"
    except Exception as e: return False, _fmt_error(e)


async def _resolve_target(bot, t):
    if not t: return None, None
    t = t.strip()
    if len(t) >= 20 and t[0] in ("u","c","g") and "://" not in t and " " not in t:
        kind = {"u":"User","c":"Channel","g":"Group"}.get(t[0].lower(), "?")
        return t, kind
    if t.startswith("@"):
        bare = t[1:]
        for name, kw in (("get_info", {"username": bare}),
                         ("get_object_by_username", {"username": bare})):
            fn = getattr(bot, name, None)
            if not fn: continue
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                d = _to_plain(r) if r else {}
                if d:
                    found = {}
                    _find_keys(d, ("channel_guid","group_guid","object_guid",
                                   "chat_guid","guid"), found)
                    g = (found.get("channel_guid") or found.get("group_guid") or
                         found.get("object_guid") or found.get("chat_guid") or
                         found.get("guid"))
                    if g:
                        kind = {"u":"User","c":"Channel","g":"Group"}.get(g[0].lower())
                        return g, kind
            except Exception: continue
    return None, None


async def get_all_chats_raw(bot):
    try:
        chats = _g(await bot.get_chats(), "chats") or []
        out = []
        for c in chats:
            a = _g(c, "abs_object","absObject") or c
            guid = _candidate_guid(a) or _candidate_guid(c)
            if not guid: continue
            out.append({"guid": guid,
                        "type": _g(a,"type") or _g(c,"type"),
                        "title": _g(a,"first_name","firstName","title","name","display_name","displayName") or _g(c,"first_name","firstName","title","name") or "",
                        "username": _g(a,"username","user_name","userName") or "",
                        "is_blocked": bool(_g(a,"is_blocked") or _g(c,"is_blocked")),
                        "raw": _to_plain(c)})
        return out
    except Exception: return []

def _is_true_group(c):
    t = (c.get("type") or "").strip()
    if t != "Group": return False
    guid = str(c.get("guid") or "")
    if guid and guid[0].lower() == "c": return False
    return True

async def collect_pv(bot):
    chats = await get_all_chats_raw(bot)
    me = await bot.get_me(); my = me.user.user_guid
    return [{"type":"pv","target":c["guid"],"name":c["title"] or "دوست"}
            for c in chats if c["type"]=="User" and c["guid"]!=my and not c["is_blocked"]]

async def collect_groups(bot):
    chats = await get_all_chats_raw(bot)
    return [{"type":"group","target":c["guid"],"name":c["title"] or c["guid"][:15],
             "raw": c.get("raw")}
            for c in chats if _is_true_group(c)]


async def _call_get_messages(bot, guid, anchor, limit, sort):
    combos = [((guid,str(anchor),str(limit),sort),{}), ((guid,anchor,limit,sort),{}),
              ((guid,str(anchor),limit,sort),{}), ((guid,anchor,str(limit),sort),{})]
    last_err = None
    fn = getattr(bot, "get_messages", None)
    if not fn: raise RuntimeError("get_messages وجود نداره")
    for args, kwargs in combos:
        try:
            r = fn(*args, **kwargs)
            if asyncio.iscoroutine(r): r = await r
            return r
        except TypeError as e: last_err = e; continue
        except Exception as e: last_err = e; continue
    raise last_err or RuntimeError("get_messages: هیچ ترکیبی جواب نداد")

def normalize_message(m, my_guid=None):
    if m is None: return None
    mid = _g(m,"message_id") or _g(m,"messageId") or _g(m,"id") or ""
    sender = str(_g(m,"sender_id") or _g(m,"author_object_guid") or _g(m,"sender") or "")
    is_mine_raw = _g(m,"is_mine")
    if is_mine_raw is None: is_mine = bool(my_guid) and (sender == str(my_guid))
    else: is_mine = bool(is_mine_raw)
    reply = _g(m,"reply_to_message_id") or _g(m,"reply_to_id") or _g(m,"reply_to") or ""
    typ = _g(m,"type") or "Text"
    if isinstance(typ, int): typ = "Text"
    txt = _g(m,"text") or ""
    if not txt:
        f = _g(m,"file") or _g(m,"photo") or _g(m,"sticker") or _g(m,"voice")
        if isinstance(f, dict): txt = f.get("name") or f.get("file_name") or ""
        elif isinstance(f, str): txt = f
    t = _g(m,"time") or _g(m,"timestamp") or _g(m,"date") or ""
    return {"id":str(mid),"text":txt,"sender":sender,"time":str(t),
            "is_mine":is_mine,"type":typ,"reply_to":str(reply)}

async def fetch_messages(bot, guid, limit=30, my_guid=None, max_id=None, min_id=None,
                         before_id=None, after_id=None, offset_id=None,
                         from_max_id=None, from_min_id=None):
    if my_guid is None:
        try:
            me = await bot.get_me(); my_guid = me.user.user_guid
        except Exception: my_guid = None
    anchor_max = max_id or before_id or from_max_id or offset_id
    anchor_min = min_id or after_id or from_min_id
    if anchor_min: anchor = str(anchor_min); sort = "FromMin"
    else: anchor = str(anchor_max) if anchor_max else "0"; sort = "FromMax"
    if anchor != "0":
        try: _ = int(anchor)
        except (ValueError, TypeError): anchor = "0"; sort = "FromMax"
    r = await _call_get_messages(bot, guid, anchor, limit, sort)
    msgs = _g(r,"messages") or []
    if not isinstance(msgs, list): msgs = [msgs] if msgs else []
    return [normalize_message(m, my_guid) for m in msgs if m]

KIND_ICON = {"text":"💬","photo":"🖼","video":"🎬","voice":"🎙","audio":"🎵","document":"📄"}
SEND_METHODS = {
    "photo":    ("send_photo","send_image","send_document","send_file"),
    "video":    ("send_video","send_document","send_file"),
    "voice":    ("send_voice","send_document","send_file"),
    "audio":    ("send_music","send_audio","send_document","send_file"),
    "document": ("send_document","send_file"),
}
FILE_KEYS = ("file","document","photo","video","voice","music","audio","path")

async def send_media(bot, target, payload):
    text = (payload or {}).get("text") or ""
    path = (payload or {}).get("file")
    if not path or not os.path.exists(path):
        r = bot.send_message(target, text or "سلام")
        if asyncio.iscoroutine(r): r = await r
        return True
    errors = []
    for name in SEND_METHODS.get(payload.get("kind"), SEND_METHODS["document"]):
        fn = getattr(bot, name, None)
        if not fn: continue
        try:
            sig = inspect.signature(fn)
            params = None if any(x.kind == inspect.Parameter.VAR_KEYWORD
                                 for x in sig.parameters.values()) else set(sig.parameters)
        except Exception: params = None
        for fk in FILE_KEYS:
            if params is not None and fk not in params: continue
            kw = {fk: path}
            for gk in ("object_guid","chat_id","guid"):
                if params is None or gk in params: kw[gk] = target; break
            if text:
                for ck in ("caption","text","message"):
                    if params is None or ck in params: kw[ck] = text; break
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                return True
            except Exception as e:
                errors.append(f"{name}: {_fmt_error(e)}")
                if _is_rate_limit(e): raise
    raise RuntimeError(" | ".join(errors[-3:]) or "متد ارسال فایل پیدا نشد")

async def send_text_only(bot, target, text):
    errors = []
    for mname in ("send_message","sendMessage"):
        fn = getattr(bot, mname, None)
        if not fn: continue
        for kw in ({"object_guid": target, "text": text},
                   {"chat_id": target, "text": text},
                   {"object_guid": target, "message": text}):
            try:
                kw2 = _filter_kwargs(fn, kw)
                if not kw2: continue
                r = fn(**kw2)
                if asyncio.iscoroutine(r): r = await r
                return True
            except Exception as e: errors.append(_fmt_error(e))
        try:
            r = fn(target, text)
            if asyncio.iscoroutine(r): r = await r
            return True
        except Exception as e: errors.append(_fmt_error(e))
    raise RuntimeError(" | ".join(errors[-3:]) or "send_message پیدا نشد")

async def extract_tg_media(msg):
    obj = kind = name = None
    if msg.photo:        obj, kind, name = msg.photo[-1], "photo", "photo.jpg"
    elif msg.video:      obj, kind, name = msg.video, "video", msg.video.file_name or "video.mp4"
    elif msg.video_note: obj, kind, name = msg.video_note, "video", "note.mp4"
    elif msg.animation:  obj, kind, name = msg.animation, "video", msg.animation.file_name or "anim.mp4"
    elif msg.voice:      obj, kind, name = msg.voice, "voice", "voice.ogg"
    elif msg.audio:      obj, kind, name = msg.audio, "audio", msg.audio.file_name or "audio.mp3"
    elif msg.document:   obj, kind, name = msg.document, "document", msg.document.file_name or "file"
    if obj is None: return None
    if (getattr(obj, "file_size", 0) or 0) > 20*1024*1024:
        raise ValueError("حجم فایل بیشتر از ۲۰ مگابایت است")
    f = await obj.get_file()
    safe = re.sub(r'[^\w.\-]', '_', name)[-60:]
    os.makedirs(MEDIA_DIR, exist_ok=True)
    path = os.path.join(MEDIA_DIR, f"{int(time.time()*1000)}_{safe}")
    await f.download_to_drive(path)
    return {"kind": kind, "file": path, "file_name": name}


def _load_ops():
    ops = _load(OPS_FILE, [])
    return ops if isinstance(ops, list) else []
def _save_ops(ops): _save(OPS_FILE, ops)
def _get_op(oid):
    for o in _load_ops():
        if o.get("id") == oid: return o
    return None
def _save_op(op):
    ops = _load_ops()
    for i, o in enumerate(ops):
        if o.get("id") == op["id"]:
            ops[i] = op; break
    else: ops.append(op)
    _save_ops(ops)

def _op_stats(op):
    if op.get("type") == "joinlef":
        p = op.get("progress") or {}
        joined = p.get("joined", 0); failed = p.get("failed", 0)
        total = p.get("total", 0); done = joined + failed
        pending = max(0, total - done); st = op.get("status", "")
        in_prog = 1 if (st == "running" and (total == 0 or pending > 0)) else 0
        return {"done": joined, "failed": failed,
                "pending": pending, "in_progress": in_prog, "total": total}
    q = TaskQueue(QUEUE_FILE); ids = set(op.get("task_ids") or [])
    s = {"done":0,"failed":0,"pending":0,"in_progress":0,"total":0}
    for t in q.tasks:
        if t.get("id") in ids:
            st = t.get("status","pending")
            if st in s: s[st] += 1
            s["total"] += 1
    return s

def _op_effective_status(op):
    st = op.get("status","draft")
    if op.get("type") == "joinlef":
        if st in ("done","failed","cancelled","paused"): return st
        return "running"
    if st == "scheduled":
        if op.get("scheduled_at",0) > time.time(): return "scheduled"
        return "queued"
    if st in ("done","failed","cancelled","empty"): return st
    s = _op_stats(op)
    if s["total"] == 0 and st != "queued": return st
    if s["pending"] + s["in_progress"] == 0:
        if s["total"] == 0: return "empty"
        if s["failed"] > 0: return "failed"
        return "done"
    if st == "paused": return "paused"
    if s["in_progress"] > 0: return "running"
    return "queued"

def _op_short_title(op, n=32):
    if op.get("type") == "joinlef": return "🤝 Joiner"
    p = op.get("payload") or {}
    if p.get("file"):
        base = f"{KIND_ICON.get(p.get('kind'),'📎')} {p.get('file_name','فایل')}"
        if p.get("text"): base += " + 💬"
    elif p.get("text"): base = f"💬 {p.get('text')[:n]}"
    else: base = "(بدون پیام)"
    return base

def _op_target_label(op):
    t = op.get("target","both")
    return {"pv":"خصوصی","groups":"گروه‌ها","both":"هر دو"}.get(t,"?")

def _op_status_icon(st):
    return {"running":"🟢","paused":"⏸","queued":"⏳","done":"✅","failed":"❌",
            "cancelled":"⛔","scheduled":"⏰","empty":"⚪","draft":"📝"}.get(st,"⚪")

def _op_status_label(st):
    return {"running":"در حال اجرا","paused":"متوقف","queued":"در صف","done":"تکمیل",
            "failed":"با خطا","cancelled":"لغو شده","scheduled":"زمان‌بندی شده",
            "empty":"خالی","draft":"پیش‌نویس"}.get(st,"?")

def _op_progress_bar(op):
    s = _op_stats(op)
    done = s["done"] + s["failed"]; tot = s["total"] or 0
    if tot == 0:
        return ("▰"*8 + "▱"*8 + " در حال آماده‌سازی…", 0) if s["in_progress"] else ("▱"*16 + " 0%", 0)
    pct = int(done * 100 / tot); fill = int(done * 16 / tot)
    return "▰"*fill + "▱"*(16-fill) + f" {pct}%", pct


JOIN_DEFAULTS = ["@linkdony_rubikas", "@lovo_lovoo0",
                 "@CBkJCCFE1IZHOEMRXTHDONBZMQLEJJGK"]


async def _extract_links_from_bot(bot, guid, limit=500, want=None, log=None):
    found = set(); anchor = None; read_total = 0; batch = 25
    rounds = 0; max_rounds = JOINER_CONFIG["extract_max_rounds"]; seen_ids = set()
    while read_total < limit and rounds < max_rounds:
        rounds += 1
        try: msgs_raw = await fetch_messages(bot, guid, limit=batch, max_id=anchor)
        except Exception as e:
            if log: log("   warn: " + _fmt_error(e)[:120])
            break
        if not msgs_raw: break
        new_msgs = []
        for m in msgs_raw:
            mid = m.get("id")
            if mid is None or mid in seen_ids: continue
            seen_ids.add(mid); new_msgs.append(m)
        if not new_msgs: break
        for m in new_msgs:
            txt = m.get("text") or ""
            for u in LINK_RE.findall(txt): found.add("@" + u)
            for uid in URL_RE.findall(txt): found.add("https://rubika.ir/joing/" + uid)
            for uid in URL_RE2.findall(txt): found.add("https://rubika.ir/joing/" + uid)
        read_total += len(new_msgs)
        min_id = None
        for m in new_msgs:
            try:
                iv = int(m["id"])
                if min_id is None or iv < min_id: min_id = iv
            except Exception: pass
        if min_id is None: break
        new_anchor = str(min_id - 1)
        if new_anchor == anchor: break
        anchor = new_anchor
        if want and len(found) >= want: break
        await asyncio.sleep(1)
    return found


def _extract_any_mid(r):
    if r is None: return None
    if isinstance(r, (list, tuple)):
        for x in r:
            m = _extract_any_mid(x)
            if m: return m
        return None
    if not isinstance(r, dict):
        d = _to_dict(r)
        if isinstance(d, dict): r = d
        else:
            for attr in ("message_id","messageId","id"):
                v = getattr(r, attr, None)
                if v: return str(v)
            return None
    for k in ("message_id","messageId","id"):
        v = r.get(k)
        if v: return str(v)
    for k in ("message_update","messageUpdate","message","data","result","response","update"):
        nested = r.get(k)
        if nested is not None:
            m = _extract_any_mid(nested)
            if m: return m
    return None


async def send_anchor(bot, my_guid, payload):
    if not my_guid: return []
    ids = []
    text = (payload or {}).get("text") or ""
    path = (payload or {}).get("file")
    if not path or not os.path.exists(path):
        try:
            r = bot.send_message(my_guid, text or "سلام")
            if asyncio.iscoroutine(r): r = await r
            mid = _extract_any_mid(r)
            if mid: ids.append(str(mid))
        except Exception: pass
        return ids
    for name in SEND_METHODS.get(payload.get("kind"), SEND_METHODS["document"]):
        fn = getattr(bot, name, None)
        if not fn: continue
        try:
            sig = inspect.signature(fn)
            params = None if any(x.kind == inspect.Parameter.VAR_KEYWORD
                                 for x in sig.parameters.values()) else set(sig.parameters)
        except Exception: params = None
        for fk in FILE_KEYS:
            if params is not None and fk not in params: continue
            kw = {fk: path}
            for gk in ("object_guid","chat_id","guid"):
                if params is None or gk in params: kw[gk] = my_guid; break
            if text:
                for ck in ("caption","text","message"):
                    if params is None or ck in params: kw[ck] = text; break
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                mid = _extract_any_mid(r)
                if mid: ids.append(str(mid))
                return ids
            except Exception as e:
                if _is_rate_limit(e): raise
                continue
    return ids


async def forward_from_anchor(bot, target, my_guid, msg_ids):
    if not msg_ids: raise RuntimeError("anchor empty")
    fn = getattr(bot, "forward_messages", None) or getattr(bot, "forwardMessages", None)
    if not fn: raise RuntimeError("forward_messages وجود نداره")
    if isinstance(msg_ids, str): msg_ids = [msg_ids]
    msg_ids = [str(x) for x in msg_ids if x]
    if not msg_ids: raise RuntimeError("anchor empty after normalize")
    try:
        r = fn(from_object_guid=str(my_guid), message_ids=msg_ids, to_object_guid=str(target))
        if asyncio.iscoroutine(r): r = await r
        return True
    except Exception as e:
        if _is_rate_limit(e): raise
        raise RuntimeError(f"{type(e).__name__}: {_fmt_error(e)}")


class AState:
    def __init__(self, aid): self.aid = aid; self.cd = 0.0; self.n = 0; self.f = 0
    def ready(self): return time.time() >= self.cd
    def cooldown(self, s): self.cd = time.time() + s
    def remaining(self): return max(0, int(self.cd - time.time()))


async def worker(aid, acc, queue_obj, st, cfg, stop, log):
    nm = acc.get("name") or acc.get("phone") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    while not stop.is_set():
        try:
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot:
                me = await bot.get_me()
                nm = me.user.first_name or acc["phone"]
                my_guid = me.user.user_guid
                log(f"✅ {nm} آماده")
                while not stop.is_set():
                    rl_until = STATE.get("rate_limit_until", 0)
                    if time.time() < rl_until:
                        wait = int(rl_until - time.time())
                        await asyncio.sleep(min(max(wait, 1), 30)); continue
                    if not st.ready():
                        await asyncio.sleep(min(st.remaining(), 10)); continue
                    tasks = await queue_obj.claim(aid, cfg["batch_per_account"])
                    if not tasks: await asyncio.sleep(3); continue
                    batch_rate_limited = False
                    for idx, t in enumerate(tasks):
                        if stop.is_set(): break
                        if time.time() < STATE.get("rate_limit_until", 0):
                            await queue_obj.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                            batch_rate_limited = True; break
                        try:
                            payload = t.get("payload") or {"kind":"text","text":cfg.get("message","سلام")}
                            op_id = t.get("op_id","_")
                            use_forward = t.get("use_forward", True)
                            akey = (aid, op_id)
                            ids = ANCHORS.get(akey)
                            if use_forward and ids is None:
                                try: ids = await send_anchor(bot, my_guid, payload)
                                except Exception as e:
                                    if _is_rate_limit(e):
                                        await queue_obj.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                                        batch_rate_limited = True; break
                                    ids = []
                                ANCHORS[akey] = ids
                            if use_forward and ids and t["target"] != my_guid:
                                await forward_from_anchor(bot, t["target"], my_guid, ids)
                            else:
                                await send_media(bot, t["target"], payload)
                            await queue_obj.complete(t["id"], True, max_attempts=cfg["max_attempts"])
                            st.n += 1
                        except Exception as e:
                            err = _fmt_error(e)
                            if _is_rate_limit(e):
                                already = time.time() < STATE.get("rate_limit_until", 0)
                                if not already:
                                    STATE["rate_limit_until"] = time.time() + RATE_LIMIT_WAIT
                                    add_error("محدودیت", err, t.get("target"), nm)
                                await queue_obj.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                                batch_rate_limited = True; break
                            if "INVALID_AUTH" in err:
                                session_ok = False
                                try: await bot.get_me(); session_ok = True
                                except Exception: session_ok = False
                                if not session_ok:
                                    await queue_obj.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                                    add_error("احراز هویت", err, t.get("target"), nm)
                                    return
                                add_error("بدون دسترسی", err, t.get("target"), nm)
                                await queue_obj.complete(t["id"], False, err, max_attempts=1)
                                st.f += 1
                                await asyncio.sleep(cfg["delay"]); continue
                            add_error("ارسال", err, t.get("target"), nm)
                            await queue_obj.complete(t["id"], False, err, max_attempts=cfg["max_attempts"])
                            st.f += 1
                        await asyncio.sleep(cfg["delay"])
                    if batch_rate_limited: continue
        except RuntimeError as e:
            if _is_auth_dead(e):
                add_error("احراز هویت", str(e)[:200], None, nm)
                log(f"❌ {nm}: NO_SESSION — worker stopped"); return
            log(f"⚠️ {aid}: {str(e)[:100]}")
            await queue_obj.requeue_account(aid); st.cooldown(30); await asyncio.sleep(10)
        except Exception as e:
            if _is_transient(e):
                log(f"⚠️ {aid} transient: {str(e)[:80]} — cooldown 60s")
                await queue_obj.requeue_account(aid); st.cooldown(60); await asyncio.sleep(15)
            else:
                log(f"⚠️ {aid}: {type(e).__name__}")
                await queue_obj.requeue_account(aid); st.cooldown(30); await asyncio.sleep(10)


async def run_workers(cfg, log):
    accounts = list_accounts()
    if not accounts: log("❌ اکانتی نیست"); return
    q = TaskQueue(QUEUE_FILE); s0 = q.stats()
    if s0["pending"] + s0["in_progress"] == 0: log("❌ صف خالیه"); return
    log(f"🚀 شروع — {s0['pending']+s0['in_progress']} پیام")
    STATE["cancel"] = asyncio.Event(); stop = STATE["cancel"]
    STATE["rate_limit_until"] = 0
    ANCHORS.clear()
    sem = asyncio.Semaphore(cfg["max_parallel"])
    states = {}
    async def one(aid, acc):
        async with sem:
            st = AState(aid); states[aid] = st
            await worker(aid, acc, q, st, cfg, stop, log)
    tasks = [asyncio.create_task(one(a, acc)) for a, acc in accounts.items()]
    async def status_loop():
        while not stop.is_set():
            await asyncio.sleep(30)
            s = q.stats()
            if s["pending"] + s["in_progress"] == 0: stop.set(); break
    s_task = asyncio.create_task(status_loop())
    try: await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        s_task.cancel()
        try: await s_task
        except Exception: pass
        await q.clear("in_progress")
    s = q.stats()
    log(f"🎯 تمام! ✅{s['done']} ❌{s['failed']}")


def _hash_of(link):
    if not link: return ""
    s = link.strip()
    if s.startswith("@"): return "u:" + s.lower()
    m = re.search(r"/joing/([A-Za-z0-9_\-]+)", s)
    if m: return "j:" + m.group(1)
    m = re.search(r"rubika\.ir/([A-Za-z0-9_\-]+)", s)
    if m: return "r:" + m.group(1)
    return "x:" + s[:50]


async def _try_join_single(bot, link):
    is_link = ("://" in link) or ("rubika.ir" in link.lower()) or ("/joing/" in link.lower())
    if is_link:
        fn = getattr(bot, "join_group", None)
        if fn:
            try:
                r = fn(link=link)
                if asyncio.iscoroutine(r): r = await r
                if _is_ok_response(r):
                    guid = extract_chat_guid(r)
                    if not guid:
                        d = _to_plain(r) or {}
                        found = {}
                        _find_keys(d, ("object_guid","chat_guid","group_guid",
                                       "channel_guid","guid"), found)
                        guid = (found.get("object_guid") or found.get("chat_guid") or
                                found.get("group_guid") or found.get("channel_guid") or
                                found.get("guid"))
                    return True, guid, "join_group"
                err = _fmt_error(r)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, None, "already"
                return False, err, "join-failed"
            except Exception as e:
                err = _fmt_error(e)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, None, "already"
                return False, err, "join-failed"
        return False, "no-method", "join-failed"
    guid, kind = await _resolve_target(bot, link)
    if not guid: return False, "resolve-failed", "resolve"
    try:
        if kind == "Channel" or (guid and guid[0].lower() == "c"):
            r = bot.join_channel_action(channel_guid=guid, action="Join")
        else:
            r = bot.join_chat(chat=guid)
        if asyncio.iscoroutine(r): r = await r
        if _is_ok_response(r): return True, guid, "join"
        err = _fmt_error(r)
        if "ALREADY" in err.upper() or "MEMBER" in err.upper():
            return True, guid, "already"
        return False, err, "join-failed"
    except Exception as e:
        err = _fmt_error(e)
        if "ALREADY" in err.upper() or "MEMBER" in err.upper():
            return True, guid, "already"
        return False, err, "join-failed"


async def _joiner_worker_for_account(aid, acc, op_id, join_delay,
                                      max_join, auto_msg_text, log):
    acc_name = acc.get("name") or acc.get("phone") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    lock = _get_op_lock(op_id)

    async def job(bot):
        async with lock:
            op = _get_op(op_id)
            if not op: return
            op["progress"]["phase"] = f"۱/۴ لینکدونی ({acc_name[:15]})"
            _save_op(op)

        linkdoni_guids = []
        for link in JOIN_DEFAULTS:
            guid, kind = await _resolve_target(bot, link)
            if not guid: continue
            try:
                if kind == "Channel" or (guid and guid[0].lower() == "c"):
                    r = bot.join_channel_action(channel_guid=guid, action="Join")
                else:
                    r = bot.join_chat(chat=guid)
                if asyncio.iscoroutine(r): r = await r
                if _is_ok_response(r):
                    linkdoni_guids.append(guid)
                    async with lock:
                        op = _get_op(op_id)
                        if op:
                            op["progress"].setdefault("linkdoni_ok", []).append(link)
                            _save_op(op)
            except Exception: pass
            await asyncio.sleep(0.5)
        if not linkdoni_guids: return

        async with lock:
            op = _get_op(op_id)
            if op:
                op["progress"]["phase"] = f"۲/۴ استخراج ({acc_name[:15]})"
                _save_op(op)

        ordered = {}
        for guid in linkdoni_guids:
            try:
                found = await _extract_links_from_bot(bot, guid, limit=1000, log=log)
                for l in found:
                    if l not in ordered: ordered[l] = True
                async with lock:
                    op = _get_op(op_id)
                    if op:
                        op["progress"]["extracted"] = len(ordered)
                        _save_op(op)
            except Exception as e:
                add_error("استخراج", _fmt_error(e), guid, acc_name)
        if not ordered: return
        all_links = list(ordered.keys())

        async with lock:
            op = _get_op(op_id)
            if op:
                op["progress"]["total"] = op["progress"].get("total", 0) + len(all_links)
                op["progress"]["phase"] = f"۳/۴ جوین ({acc_name[:15]})"
                _save_op(op)

        seen = set(); joined = 0
        for link in all_links:
            if max_join and joined >= max_join: break
            async with lock:
                op = _get_op(op_id)
                if not op or op.get("status") == "cancelled": return
            h = _hash_of(link)
            if h in seen: continue
            seen.add(h)
            try:
                ok, res, tag = await _try_join_single(bot, link)
                if ok:
                    joined += 1
                    async with lock:
                        op = _get_op(op_id)
                        if op:
                            op["progress"]["joined"] = op["progress"].get("joined", 0) + 1
                            _save_op(op)
                    if auto_msg_text and res and isinstance(res, str) and len(res) > 5:
                        try:
                            await send_text_only(bot, res, auto_msg_text)
                            async with lock:
                                op = _get_op(op_id)
                                if op:
                                    op["progress"]["msg_sent"] = op["progress"].get("msg_sent", 0) + 1
                                    _save_op(op)
                        except Exception as e:
                            add_error("msg-after-join", _fmt_error(e), res, acc_name)
                            async with lock:
                                op = _get_op(op_id)
                                if op:
                                    op["progress"]["msg_fail"] = op["progress"].get("msg_fail", 0) + 1
                                    _save_op(op)
                else:
                    async with lock:
                        op = _get_op(op_id)
                        if op:
                            op["progress"]["failed"] = op["progress"].get("failed", 0) + 1
                            errs = op["progress"].setdefault("link_errors", [])
                            errs.append((link, str(res)[:100]))
                            if len(errs) > 40: op["progress"]["link_errors"] = errs[-40:]
                            _save_op(op)
            except Exception as e:
                async with lock:
                    op = _get_op(op_id)
                    if op:
                        op["progress"]["failed"] = op["progress"].get("failed", 0) + 1
                        _save_op(op)
            if join_delay > 0: await asyncio.sleep(join_delay)

    try:
        cli = SafeClient(name=sess, _aid=aid)
        async with cli as bot:
            await job(bot)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        async with lock:
            op = _get_op(op_id)
            if op:
                op["errors"] = op.get("errors") or []
                op["errors"].append(f"{acc_name}: {type(e).__name__}")
                _save_op(op)


async def run_joiner_lefter(op, log):
    accounts = list_accounts()
    sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    max_join = op.get("max_join", 0) or 0
    join_delay = float(op.get("join_delay", 0.5))
    auto_msg_text = (op.get("auto_msg") or "").strip()

    op["progress"] = {
        "joined": 0, "failed": 0, "total": 0,
        "phase": "شروع", "extracted": 0,
        "msg_sent": 0, "msg_fail": 0,
        "linkdoni_ok": [], "linkdoni_fail": [], "link_errors": []
    }
    op["status"] = "running"; op["errors"] = []
    _save_op(op)

    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        t = asyncio.create_task(
            _joiner_worker_for_account(aid, a, op["id"], join_delay,
                                       max_join, auto_msg_text, log))
        tasks.append(t)
    if tasks:
        try: log(f"🚀 Joiner: {len(tasks)} اکانت همزمان (delay={join_delay}s)")
        except Exception: pass
        await asyncio.gather(*tasks, return_exceptions=True)

    op2 = _get_op(op["id"])
    if op2 and op2.get("status") != "cancelled":
        op2["status"] = "done"
        op2["progress"]["phase"] = "تمام"
        op2["finished_at"] = int(time.time())
        _save_op(op2)
    _OP_LOCKS.pop(op["id"], None)


# ══════════════════════════════════════════════════════════════
# Bale bot wrapper (فقط برای login relay + notify)
# ══════════════════════════════════════════════════════════════
import aiohttp
BALE_TOKEN = os.environ.get("BALE_TOKEN", "").strip()
BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}"
_bale_session = None

async def bale_send(chat_id, text, kb=None):
    global _bale_session
    if not BALE_TOKEN: return
    if _bale_session is None:
        _bale_session = aiohttp.ClientSession()
    p = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"}
    if kb: p["reply_markup"] = {"inline_keyboard": kb}
    try:
        async with _bale_session.post(f"{BALE_API}/sendMessage", json=p,
                                       timeout=aiohttp.ClientTimeout(total=30)) as r:
            return await r.json()
    except Exception as e:
        print(f"[bale] {e}")
        return {}


# ══════════════════════════════════════════════════════════════
# Telegram UI
# ══════════════════════════════════════════════════════════════
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters as tg_filters)
from telegram.request import HTTPXRequest

HR = "━━━━━━━━━━━━"
PAGE_SIZE = 6

STATE = {"owner": None, "cancel": None, "job": None, "conv": {}, "panel": {},
         "rate_limit_until": 0, "listener_seeded": set(),
         "listener_stops": {}, "listener_new_count": 0}
APP = None
_last_log = [0.0]
_loop_ref = [None]
pending = {}   # ★ برای login relay


def esc(s): return _html.escape(str(s if s is not None else ""))
def short(s, n=40):
    s = str(s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n-1] + "…"
def B(l, d): return InlineKeyboardButton(l, callback_data=d)
def kb_(*rows): return InlineKeyboardMarkup([list(r) for r in rows if r])
def head(icon, t): return f"<b>{icon} {esc(t)}</b>\n{HR}\n"

_FORCED_OWNER = 8389746549

def authorized(update):
    try:
        return update.effective_chat.id == _FORCED_OWNER
    except Exception:
        return False

def load_owner():
    return _FORCED_OWNER

def save_owner(cid):
    _save(OWNER_FILE, {"owner": _FORCED_OWNER})



async def tg_send(text, markup=None, parse_mode=None):
    if not STATE["owner"] or APP is None: return False
    text = str(text)[:4000]
    for attempt in range(3):
        try:
            await APP.bot.send_message(chat_id=STATE["owner"], text=text,
                                       reply_markup=markup, parse_mode=parse_mode or "HTML",
                                       disable_web_page_preview=True)
            return True
        except Exception as e:
            if "parse entities" in str(e) and parse_mode: parse_mode = None; continue
            await asyncio.sleep(1.5*(attempt+1))
    return False


async def panel(text, kb=None):
    cid = STATE["owner"]
    if not cid or APP is None: return
    text = str(text)[:4000]
    mid = STATE["panel"].get(cid)
    if mid:
        try:
            await APP.bot.edit_message_text(chat_id=cid, message_id=mid, text=text,
                                            reply_markup=kb, parse_mode=ParseMode.HTML,
                                            disable_web_page_preview=True)
            return
        except BadRequest as e:
            if "not modified" in str(e).lower(): return
        except Exception: pass
    for attempt in range(3):
        try:
            m = await APP.bot.send_message(chat_id=cid, text=text, reply_markup=kb,
                                           parse_mode=ParseMode.HTML,
                                           disable_web_page_preview=True)
            STATE["panel"][cid] = m.message_id; return
        except Exception:
            await asyncio.sleep(1.5*(attempt+1))


async def ask(text, note=None):
    body = (f"⚠️ {esc(note)}\n\n" if note else "") + text
    await panel(body, kb_([B("❌ لغو", "conv:cancel")]))


def log_cb(msg):
    now = time.time()
    if now - _last_log[0] < 1.5: return
    _last_log[0] = now
    try:
        loop = _loop_ref[0] or asyncio.get_event_loop()
        loop.create_task(tg_send(str(msg)))
    except Exception as e: print(f"[!] log_cb: {e}")

def get_conv(cid):
    c = STATE["conv"].get(cid)
    if not c: c = STATE["conv"][cid] = {}
    return c
def clear_conv(cid): STATE["conv"].pop(cid, None)


# ══════════════════════════════════════════════════════════════
# UI — Main / Accounts
# ══════════════════════════════════════════════════════════════
def main_kb():
    rows = [[{"text": f"📱 {p}", "callback_data": f"acc:{p}"}] for p in list_accounts().keys()]
    rows.append([{"text": "➕ افزودن اکانت", "callback_data": "add"}])
    return rows


def acc_kb(phone):
    return [
        [{"text": "🎲 اسم رندوم", "callback_data": f"rn:{phone}"}],
        [{"text": "📊 وضعیت", "callback_data": f"st:{phone}"}],
        [{"text": "🗑 حذف سشن", "callback_data": f"ds:{phone}"},
         {"text": "⚠️ حذف اکانت", "callback_data": f"da:{phone}"}],
        [{"text": "⬅️ برگشت", "callback_data": "home"}],
    ]


async def show_main():
    accounts = list_accounts()
    ops = _load_ops()
    running_ops = [o for o in ops if _op_effective_status(o) == "running"]
    listening = sum(1 for t in LISTENER_TASKS.values() if not t.done())
    txt = head("🤖", f"پنل ربات روبیکا — {VERSION}")
    txt += f"📱 اکانت‌ها: <b>{len(accounts)}</b>\n"
    txt += f"📊 عملیات‌ها: <b>{len(ops)}</b>\n"
    if running_ops: txt += f"🟢 در حال اجرا: <b>{len(running_ops)}</b>\n"
    txt += f"👂 لیسنر فعال: <b>{listening}</b>\n"
    txt += f"🔄 Keepalive: هر <b>{KEEPALIVE_SECONDS//60} دقیقه</b>\n"
    txt += f"\n💾 DATA_DIR: <code>{esc(DATA_DIR)}</code>\n"
    await panel(txt, kb_(
        [B("📤 ارسال", "send:start")],
        [B("🤝 Joiner فوق‌سریع", "send:jl")],
        [B("📱 اکانت‌ها", "menu:acc"), B("📊 آمار", "menu:stats")],
        [B("👂 لیسنر", "menu:listen")],
        [B("⚙️ تنظیمات", "menu:cfg"), B("❓ راهنما", "menu:help")]))


async def show_listen_menu():
    accounts = list_accounts()
    enabled = _listener_cfg_enabled()
    service_only = _listener_cfg_service_only()
    txt = head("👂", "لیسنر پیام‌های سرویس")
    txt += f"وضعیت: <b>{'🟢 فعال' if enabled else '🔴 غیرفعال'}</b>\n"
    txt += f"فقط سرویس: <b>{'🟢' if service_only else '🔴'}</b>\n\n"
    txt += f"📱 اکانت‌ها ({len(accounts)}):\n"
    rows = []
    for aid, a in accounts.items():
        t = LISTENER_TASKS.get(aid)
        running = t is not None and not t.done()
        icon = "🟢" if running else "⚪"
        rows.append([B(f"{icon} {short(a.get('name','?'),24)}", f"listen:toggle:{aid}")])
    rows.append([B("🔄 ری‌استارت همه", "listen:restart")])
    rows.append([B("⬅️", "menu:main")])
    await panel(txt, kb_(*rows))


async def show_accounts(page=0):
    accounts = list_accounts()
    items = list(accounts.items())
    pages = max(1, -(-len(items) // PAGE_SIZE))
    page = max(0, min(page, pages-1))
    chunk = items[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    rows = []
    for aid, a in chunk:
        n_ch = len(a.get("channels",[]))
        label = f"📱 {short(a.get('name','?'),18)} · {a.get('phone','?')}"
        if n_ch: label += f" · {n_ch}📢"
        rows.append([B(label, f"acc:view:{aid}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"acc:page:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B("▶️", f"acc:page:{page+1}"))
        rows.append(pr)
    rows.append([B("➕ افزودن اکانت", "acc:add")])
    rows.append([B("🏠 منو", "menu:main")])
    txt = head("📱", f"اکانت‌ها ({len(accounts)})")
    if not accounts: txt += "هنوز اکانتی نداری."
    await panel(txt, kb_(*rows))


async def show_account_detail(aid):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو", "menu:main")]))
    n_ch = len(a.get("channels",[]))
    t = LISTENER_TASKS.get(aid)
    ls = "🟢 فعال" if (t and not t.done()) else "⚪ خاموش"
    sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    rp_exists = os.path.exists(sess + ".rp")
    rp_size = os.path.getsize(sess + ".rp") if rp_exists else 0
    txt = (head("📱", a.get("name","?")) +
           f"📞 <code>{esc(a.get('phone','—'))}</code>\n"
           f"🆔 <code>{esc(aid)}</code>\n"
           f"📢 کانال‌ها: <b>{n_ch}</b>\n"
           f"👂 لیسنر: <b>{ls}</b>\n"
           f"💾 session.rp: <b>{'✅' if rp_exists else '❌'}</b> ({rp_size}B)")
    await panel(txt, kb_(
        [B("📝 پروفایل", f"prof:menu:{aid}")],
        [B("📢 ساخت کانال", f"chan:new:{aid}"), B("📋 کانال‌ها", f"chan:list:{aid}")],
        [B("👂 لیسنر", f"listen:toggle:{aid}")],
        [B("🗑 حذف", f"acc:del:{aid}")],
        [B("⬅️ اکانت‌ها", "menu:acc"), B("🏠 منو", "menu:main")]))


# ══════════════════════════════════════════════════════════════
# UI — Profile / Channels (unchanged from v70tg)
# ══════════════════════════════════════════════════════════════
async def show_profile_menu(aid):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو", "menu:main")]))
    await panel(head("📝", f"پروفایل · {a.get('name','?')}") + "چی رو تغییر بدم؟", kb_(
        [B("👤 اسم", f"prof:set:name:{aid}"), B("📖 بیو", f"prof:set:bio:{aid}")],
        [B("🔤 یوزرنیم", f"prof:set:user:{aid}"), B("🖼 عکس", f"prof:set:photo:{aid}")],
        [B("⬅️", f"acc:view:{aid}")]))

async def show_channel_new(aid):
    if not get_account(aid): return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
    await panel(head("📢","ساخت کانال") + "🌐 عمومی — با یوزرنیم\n🔒 خصوصی — با لینک",
                kb_([B("🌐 عمومی", f"chan:new_pub:{aid}"), B("🔒 خصوصی", f"chan:new_priv:{aid}")],
                    [B("⬅️", f"acc:view:{aid}")]))

async def show_channel_list(aid, page=0):
    a = get_account(aid)
    if not a: return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
    chans = list(enumerate(a.get("channels",[])))
    if not chans:
        return await panel(head("📋","کانال‌ها") + "خالیه.",
                           kb_([B("➕ ساخت", f"chan:new:{aid}")], [B("⬅️", f"acc:view:{aid}")]))
    pages = max(1, -(-len(chans) // PAGE_SIZE))
    page = max(0, min(page, pages-1))
    chunk = chans[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    rows = [[B(f"{'🌐' if c.get('is_public') else '🔒'} {short(c.get('title','?'),28)}",
               f"chan:view:{aid}:{i}")] for i, c in chunk]
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"chan:page:{aid}:{page-1}"))
        pr.append(B(f"{page+1}/{pages}","noop"))
        if page < pages-1: pr.append(B("▶️", f"chan:page:{aid}:{page+1}"))
        rows.append(pr)
    rows.append([B("➕ جدید", f"chan:new:{aid}")])
    rows.append([B("⬅️", f"acc:view:{aid}")])
    await panel(head("📋", f"کانال‌ها ({len(chans)})"), kb_(*rows))

async def show_channel_view(aid, idx):
    a = get_account(aid); chans = (a or {}).get("channels",[])
    if not a or idx >= len(chans): return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
    ch = chans[idx]
    link = ("@"+ch["username"]) if ch.get("username") else (ch.get("join_link") or "—")
    txt = (head("⚙️", ch.get("title","—")) +
           f"{'🌐 عمومی' if ch.get('is_public') else '🔒 خصوصی'}\n🔗 {esc(link)}")
    await panel(txt, kb_(
        [B("📤 ارسال پیام به کانال", f"chan:send:{aid}:{idx}")],
        [B("✏️ اسم", f"chan:edit:title:{aid}:{idx}"), B("📖 بیو", f"chan:edit:desc:{aid}:{idx}")],
        [B("🔗 یوزرنیم", f"chan:edit:user:{aid}:{idx}"), B("🖼 عکس", f"chan:edit:photo:{aid}:{idx}")],
        [B("🔁 لینک جدید", f"chan:mklink:{aid}:{idx}"), B("🗑 حذف", f"chan:del:{aid}:{idx}")],
        [B("⬅️", f"chan:list:{aid}")]))


# ══════════════════════════════════════════════════════════════
# Send flow / Stats / Errors / Op detail / Cfg / Help (unchanged)
# ══════════════════════════════════════════════════════════════
SCHEDULE_OPTIONS = [("0", "⚡️ آنی", 0), ("1h", "۱ ساعت بعد", 3600),
                    ("3h", "۳ ساعت بعد", 3*3600), ("12h", "۱۲ ساعت بعد", 12*3600),
                    ("24h", "۲۴ ساعت بعد", 24*3600)]
MAX_OPTIONS = [50, 100, 500, 1000]

def _send_conv(cid):
    c = get_conv(cid)
    if "send" not in c: c["send"] = {"step":"accounts","accounts":[],"payload":None,
                                     "target":"both","max":0,"schedule":0}
    return c["send"]

async def show_send_step(cid):
    s = _send_conv(cid); step = s["step"]
    if step == "accounts":   await send_step_accounts(cid, s)
    elif step == "compose":  await send_step_compose(cid, s)
    elif step == "target":   await send_step_target(cid, s)
    elif step == "max":      await send_step_max(cid, s)
    elif step == "schedule": await send_step_schedule(cid, s)
    elif step == "confirm":  await send_step_confirm(cid, s)

def _send_summary(s):
    accs = s.get("accounts") or []
    all_a = list_accounts()
    if "all" in accs: acc_label = f"همه ({len(all_a)})"
    elif not accs: acc_label = "—"
    elif len(accs) == 1:
        a = get_account(accs[0]); acc_label = a.get("name","?") if a else "?"
    else:
        names = [get_account(aid).get("name","?") for aid in accs[:3] if get_account(aid)]
        acc_label = "، ".join(names) + (f" +{len(accs)-3}" if len(accs)>3 else "")
    p = s.get("payload")
    if not p: msg_label = "—"
    elif p.get("file"):
        msg_label = f"{KIND_ICON.get(p.get('kind'),'📎')} {p.get('file_name','فایل')}"
        if p.get("text"): msg_label += f" + «{short(p.get('text'),20)}»"
    else: msg_label = f"💬 «{short(p.get('text'),30)}»"
    tgt = {"pv":"خصوصی","groups":"گروه‌ها","both":"هر دو"}.get(s.get("target","both"),"?")
    mx = s.get("max",0) or 0
    mx_label = f"{mx}" if mx else "بدون محدودیت"
    sch = s.get("schedule",0); sch_label = "آنی"
    if sch > 0:
        for code, label, secs in SCHEDULE_OPTIONS:
            if secs == sch: sch_label = label; break
        else: sch_label = _fmt_time(sch) + " بعد"
    return (f"📋 <b>خلاصه</b>\n"
            f"👤 {esc(acc_label)}\n✉️ {esc(msg_label)}\n"
            f"🎯 مقصد: <b>{esc(tgt)}</b>\n"
            f"🔢 حداکثر: <b>{esc(mx_label)}</b>\n"
            f"⏰ زمان: <b>{esc(sch_label)}</b>")

async def send_step_accounts(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel("⚠️ اول یک اکانت اضافه کن.",
                           kb_([B("➕ افزودن اکانت","acc:add")], [B("🏠 منو","menu:main")]))
    sel = set(s.get("accounts") or [])
    rows = []
    for aid, a in accounts.items():
        check = "☑" if (aid in sel or "all" in sel) else "☐"
        rows.append([B(f"{check} {short(a.get('name','?'),22)} · {a.get('phone','?')}",
                       f"send:acc:{aid}")])
    all_sel = ("all" in sel) or (len(sel) >= len(accounts) and accounts)
    rows.append([B("✅ لغو انتخاب همه" if all_sel else "☑ همه", "send:accall")])
    rows.append([B("▶️ مرحله بعد: پیام", "send:accnext")])
    rows.append([B("🏠 منو","menu:main")])
    txt = head("📤","ارسال — انتخاب اکانت") + "کدام اکانت(ها)؟\n\n" + _send_summary(s)
    await panel(txt, kb_(*rows))

async def send_step_compose(cid, s):
    txt = head("📤","ارسال — تنظیم پیام")
    txt += "یک پیام بفرست:\n• فقط متن\n• فقط فایل\n• هر دو\n\n" + _send_summary(s)
    rows = []
    if s.get("payload"):
        rows.append([B("✏️ تغییر پیام", "send:recompose")])
        rows.append([B("▶️ مرحله بعد: مقصد", "send:composenext")])
    rows.append([B("⬅️ اکانت","send:back")])
    rows.append([B("🏠 منو","menu:main")])
    await panel(txt, kb_(*rows))

async def send_step_target(cid, s):
    tgt = s.get("target","both")
    rows = [
        [B(("✅ " if tgt=="pv" else "")+"👤 خصوصی (PV)", "send:tgt:pv")],
        [B(("✅ " if tgt=="groups" else "")+"👥 گروه‌ها", "send:tgt:groups")],
        [B(("✅ " if tgt=="both" else "")+"📨 هر دو", "send:tgt:both")],
        [B("▶️ مرحله بعد: حداکثر", "send:tgtnext")],
        [B("⬅️ پیام","send:prev")],
        [B("🏠 منو","menu:main")],
    ]
    await panel(head("📤","ارسال — مقصد") + "پیام رو کجا بفرستیم؟\n\n" + _send_summary(s), kb_(*rows))

async def send_step_max(cid, s):
    mx = s.get("max",0); rows = []
    row = []
    for n in MAX_OPTIONS[:3]: row.append(B(("✅ " if mx==n else "")+f"{n}", f"send:max:{n}"))
    rows.append(row); row2 = []
    for n in MAX_OPTIONS[3:]: row2.append(B(("✅ " if mx==n else "")+f"{n}", f"send:max:{n}"))
    if row2: rows.append(row2)
    rows.append([B(("✅ " if mx==0 else "")+"♾ بدون محدودیت", "send:max:0")])
    rows.append([B("✏️ عدد دلخواه", "send:max:custom")])
    rows.append([B("▶️ مرحله بعد: زمان‌بندی", "send:maxnext")])
    rows.append([B("⬅️ مقصد","send:prev")])
    rows.append([B("🏠 منو","menu:main")])
    await panel(head("📤","ارسال — حداکثر پیام") + "چند پیام حداکثر؟\n\n" + _send_summary(s), kb_(*rows))

async def send_step_schedule(cid, s):
    sch = s.get("schedule",0)
    rows = [[B(("✅ " if sch==0 else "")+"⚡️ آنی", "send:sch:0")]]
    row = [B(("✅ " if sch==secs else "")+label, f"send:sch:{code}")
           for code, label, secs in SCHEDULE_OPTIONS[1:3]]
    if row: rows.append(row)
    row = [B(("✅ " if sch==secs else "")+label, f"send:sch:{code}")
           for code, label, secs in SCHEDULE_OPTIONS[3:]]
    if row: rows.append(row)
    rows.append([B("▶️ آنالیز و تایید", "send:schedulenext")])
    rows.append([B("⬅️ حداکثر","send:prev")])
    rows.append([B("🏠 منو","menu:main")])
    await panel(head("📤","ارسال — زمان‌بندی") + "چه زمانی شروع بشه؟\n\n" + _send_summary(s), kb_(*rows))

async def send_step_confirm(cid, s):
    await panel("⏳ در حال آنالیز...")
    accounts = list_accounts()
    sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "accounts"
        return await panel("⚠️ اکانت انتخاب نشده.", kb_([B("🏠 منو","menu:main")]))
    tgt = s.get("target","both")
    total_targets = []; errors = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        try:
            async def collect_all(bot):
                pv = await collect_pv(bot) if tgt in ("pv","both") else []
                gr = await collect_groups(bot) if tgt in ("groups","both") else []
                return pv, gr
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot:
                pv, gr = await collect_all(bot)
            for it in pv:
                it["owner_account"] = aid
                it["payload"] = s.get("payload") or {"kind":"text","text":"سلام"}
                total_targets.append(it)
            for it in gr:
                it["owner_account"] = aid
                it["payload"] = s.get("payload") or {"kind":"text","text":"سلام"}
                total_targets.append(it)
        except Exception as e:
            errors.append(f"{a.get('name','?')}: {type(e).__name__}")
    mx = s.get("max",0) or 0
    if mx and len(total_targets) > mx: total_targets = total_targets[:mx]
    s["_targets"] = total_targets; s["_analysis_errors"] = errors
    txt = head("📊","آنالیز")
    txt += f"📦 مقصد تایید شده: <b>{len(total_targets)}</b>\n"
    if errors: txt += f"\n⚠️ خطا: <b>{len(errors)}</b>\n"
    txt += "\n" + _send_summary(s)
    rows = []
    if total_targets: rows.append([B("✅ تایید و شروع ارسال", "send:go")])
    rows.append([B("⚠️ مشاهده خطاها", "menu:errors")])
    rows.append([B("✏️ ویرایش", "send:back_edit")])
    rows.append([B("❌ لغو", "send:cancel")])
    await panel(txt, kb_(*rows))


async def show_stats():
    ops = _load_ops()
    ops.sort(key=lambda o: o.get("created",0), reverse=True)
    total_done = total_failed = 0
    q = TaskQueue(QUEUE_FILE)
    for t in q.tasks:
        if t.get("status") == "done": total_done += 1
        elif t.get("status") == "failed": total_failed += 1
    errs = _load_errors()
    txt = head("📊","آمار")
    txt += (f"✅ کل ارسال شده: <b>{total_done}</b>\n"
            f"❌ کل ناموفق: <b>{total_failed}</b>\n"
            f"⚠️ خطاهای اخیر: <b>{len(errs)}</b>\n"
            f"📥 پیام‌های دریافتی: <b>{STATE.get('listener_new_count',0)}</b>\n\n"
            f"📁 آخرین عملیات‌ها:")
    rows = []
    if ops:
        for op in ops[:10]:
            st = _op_effective_status(op)
            ico = _op_status_icon(st)
            s = _op_stats(op)
            prog = f"{s['done']+s['failed']}/{s['total']}" if s['total'] else "—"
            rows.append([B(f"{ico} {short(_op_short_title(op,28),32)} · {prog}",
                           f"op:view:{op['id']}")])
    else: txt += "\n\nهنوز عملیاتی ثبت نشده."
    rows.append([B("⚠️ خطاها", "menu:errors")])
    rows.append([B("🏠 منو","menu:main")])
    await panel(txt, kb_(*rows))


async def show_errors(page=0):
    errors = _load_errors(); errors = list(reversed(errors))
    if not errors:
        return await panel(head("⚠️","خطاها") + "هیچ خطایی ثبت نشده.",
                           kb_([B("🏠 منو","menu:main")]))
    PER = 5
    pages = max(1, -(-len(errors) // PER)); page = max(0, min(page, pages-1))
    chunk = errors[page*PER:(page+1)*PER]
    txt = head("⚠️", f"خطاها ({len(errors)} از ۱۰۰)") + f"<i>صفحه {page+1}/{pages}</i>\n"
    for e in chunk:
        t = time.strftime('%m/%d %H:%M', time.localtime(e.get("time",0)))
        txt += f"\n🕐 <code>{esc(t)}</code> · <b>{esc(e.get('source','?'))}</b>\n"
        txt += f"❗️ <code>{esc(str(e.get('error',''))[:220])}</code>\n"
    rows = []; pr = []
    if page > 0: pr.append(B("◀️", f"err:page:{page-1}"))
    pr.append(B(f"{page+1}/{pages}", "noop"))
    if page < pages-1: pr.append(B("▶️", f"err:page:{page+1}"))
    if len(pr) > 1: rows.append(pr)
    rows.append([B("🗑 پاک کردن همه", "err:clear")])
    rows.append([B("📊 آمار", "menu:stats"), B("🏠 منو","menu:main")])
    await panel(txt, kb_(*rows))


async def show_op_detail(oid):
    op = _get_op(oid)
    if not op: return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
    st = _op_effective_status(op)
    ico = _op_status_icon(st); ttl = _op_status_label(st)
    s = _op_stats(op); bar, _ = _op_progress_bar(op)
    txt = head("📋", f"جزئیات {op['id']}")
    txt += f"{ico} <b>{esc(ttl)}</b>\n\n<code>{esc(bar)}</code>\n\n"
    if op.get("type") == "joinlef":
        p = op.get("progress") or {}
        txt += f"📍 مرحله: <b>{esc(p.get('phase','—'))}</b>\n"
        txt += f"✅ جوین: <b>{s['done']}</b> · ❌ <b>{s['failed']}</b>\n"
        ms = p.get("msg_sent", 0); mf = p.get("msg_fail", 0)
        if ms or mf: txt += f"✉️ پیام: <b>{ms}</b> · ❌ <b>{mf}</b>\n"
        spd = op.get("speed")
        if spd:
            spd_lbl = next((label for k, label, _ in JL_SPEEDS if k == spd), spd)
            txt += f"🚀 سرعت: <b>{spd_lbl}</b>\n"
        rows = []
        if st == "running": rows.append([B("⏹ توقف", f"op:stop:{oid}")])
        rows.append([B("⬅️ آمار","menu:stats"), B("🏠 منو","menu:main")])
        return await panel(txt, kb_(*rows))
    txt += f"✅ موفق: <b>{s['done']}</b> · ❌ <b>{s['failed']}</b>\n"
    txt += f"⏳ انتظار: <b>{s['pending']}</b> · 🔄 <b>{s['in_progress']}</b>\n"
    rows = []
    if st == "running": rows.append([B("⏹ توقف", f"op:stop:{oid}")])
    rows.append([B("⬅️ آمار","menu:stats"), B("🏠 منو","menu:main")])
    await panel(txt, kb_(*rows))


CFG_FIELDS = [
    ("delay","⏱ تاخیر","s",1,0,120),
    ("cooldown","❄️ استراحت","s",30,0,3600),
    ("batch_per_account","📦 دسته","",1,1,20),
    ("max_parallel","🚀 هم‌زمان","",1,1,10),
    ("max_attempts","🔁 تلاش","",1,1,10),
]
def _fmt_num(v):
    try:
        v = float(v); return str(int(v)) if v == int(v) else str(round(v,1))
    except Exception: return str(v)

async def show_cfg():
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    txt = head("⚙️","تنظیمات"); rows = []
    for key, label, unit, step, lo, hi in CFG_FIELDS:
        v = cfg.get(key, DEFAULT_CFG[key]); v_str = _fmt_num(v) + unit
        txt += f"{label}: <b>{esc(v_str)}</b>\n"
        rows.append([B("➖", f"cfg:adj:{key}:-1"), B(v_str, "noop"), B("➕", f"cfg:adj:{key}:1")])
    lv = int(cfg.get("listener", 1))
    sv = int(cfg.get("listener_service_only", 1))
    txt += f"\n👂 لیسنر: <b>{'🟢' if lv else '🔴'}</b>\n"
    txt += f"🔍 فقط سرویس: <b>{'🟢' if sv else '🔴'}</b>\n"
    rows.append([B("👂 لیسنر", "cfg:toggle_listener"), B("🔍 فقط سرویس", "cfg:toggle_service_only")])
    txt += f"\n🔖 نسخه: <b>{VERSION}</b>"
    txt += f"\n🔄 Keepalive: <b>{KEEPALIVE_SECONDS//60} دقیقه</b>"
    rows.append([B("🏠 منو","menu:main")])
    await panel(txt, kb_(*rows))

async def adjust_cfg(key, sign):
    spec = next((f for f in CFG_FIELDS if f[0]==key), None)
    if not spec: return
    _, _, _, step, lo, hi = spec
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    v = float(cfg.get(key, DEFAULT_CFG[key])) + sign*step
    v = max(lo, min(hi, v))
    cfg[key] = round(v,1) if key in ("delay","cooldown") else int(v)
    _save(CFG_FILE, cfg); await show_cfg()


async def show_help():
    txt = (head("❓","راهنما") + f"🔖 نسخه: <b>{VERSION}</b>\n\n"
           "📤 ارسال — پیام به گروه‌ها و PV\n"
           "📢 کانال‌ها — ساخت + ارسال پیام/عکس/فایل\n"
           "🤝 Joiner — جوین همزمان + پیام خودکار\n"
           "👂 لیسنر — پیام‌های سرویس\n"
           f"🔄 Keepalive — هر {KEEPALIVE_SECONDS//60} دقیقه ping\n\n"
           "📊 آمار — جزئیات زنده\n"
           "⚠️ خطاها — ۱۰۰ خطای اخیر\n\n"
           "🔑 <b>سشن ماندگار</b>:\n"
           "auth در فایل <code>sessions/{aid}.rp</code> ذخیره میشه.\n"
           "اگه روزی سرور سشن رو باطل کرد، اکانت رو حذف و دوباره اضافه کن.")
    await panel(txt, kb_([B("🏠 منو","menu:main")]))


# ══════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════
async def cmd_start(update, context):
    cid = update.effective_chat.id
    if cid != _FORCED_OWNER:
        if update.effective_message:
            await update.effective_message.reply_text("⛔ این ربات خصوصی است.")
        return

    STATE["owner"] = _FORCED_OWNER
    STATE["panel"].pop(cid, None)
    await update.effective_message.reply_text(
        f"🔒 خوش آمدی مالک.\n🔖 {VERSION}\n💾 {DATA_DIR}"
    )
    await show_main()

async def cmd_menu(update, context):
    if not authorized(update): return
    STATE["panel"].pop(update.effective_chat.id, None)
    clear_conv(update.effective_chat.id)
    await show_main()

async def cmd_version(update, context):
    if not authorized(update): return
    accounts = list_accounts()
    txt = f"🔖 <b>{VERSION}</b>\n💾 <code>{DATA_DIR}</code>\n📱 {len(accounts)}"
    await update.message.reply_text(txt, parse_mode="HTML")

async def cmd_keepalive(update, context):
    if not authorized(update): return
    await update.message.reply_text("⏳ ping به همه اکانت‌ها...")
    for aid, acc in list_accounts().items():
        sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        try:
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot:
                await bot.get_me()
            await update.message.reply_text(f"✅ {aid}")
        except Exception as e:
            await update.message.reply_text(f"❌ {aid}: {str(e)[:120]}")


# ══════════════════════════════════════════════════════════════
# on_message (interactive login relay only — no /code /pass)
# ══════════════════════════════════════════════════════════════
async def on_message(update, context):
    if not authorized(update): return
    msg = update.message
    if msg is None: return
    cid = update.effective_chat.id
    conv = STATE["conv"].get(cid) or {}
    text = (msg.text or "").strip()

    # ★ رله پاسخ‌های مرحله لاگین rubpy
    if "acc" in conv and conv["acc"].get("step") == "login_pending":
        q = pending.get(cid, {}).get("q")
        if q:
            try: q.put(text)
            except Exception: pass
        return

    if "jl_wait" in conv:
        wait_kind = conv.pop("jl_wait")
        jl = get_conv(cid).get("jl") or {}
        if wait_kind == "max":
            try: jl["max_join"] = max(0, int(text))
            except Exception:
                get_conv(cid)["jl_wait"] = "max"
                return await ask("🔢 نامعتبر. دوباره:")
            get_conv(cid)["jl"] = jl
            return await jl_step_max(cid, jl)
        elif wait_kind == "auto_msg":
            jl["auto_msg"] = text[:500]
            get_conv(cid)["jl"] = jl
            return await jl_step_settings(cid, jl)

    if "send_wait" in conv:
        conv.pop("send_wait")
        s = _send_conv(cid)
        try: s["max"] = max(0, int(text))
        except Exception: return await ask("🔢 نامعتبر. دوباره:")
        return await show_send_step(cid)

    if "send" in conv:
        s = conv["send"]
        if s.get("step") == "compose":
            STATE["panel"].pop(cid, None)
            try: media = await extract_tg_media(msg)
            except Exception as e: return await ask("✉️ دوباره بفرست:", note=str(e)[:150])
            cap = (msg.caption or msg.text or "").strip()
            if not media and not cap: return await ask("✉️ یک متن یا فایل بفرست:")
            s["payload"] = ({**media, "text": cap} if media
                            else {"kind":"text","text":cap,"file":None})
            s["step"] = "target"; return await show_send_step(cid)

    if "acc" in conv:
        a = conv["acc"]; step = a.get("step")
        STATE["panel"].pop(cid, None)
        if step == "phone":
            ph = text.replace("+","").replace(" ","").replace("-","")
            if ph.startswith("0"): ph = "98" + ph[1:]
            if not ph.isdigit() or len(ph) < 10: return await ask("📞 نامعتبر:")
            await panel("⏳ در حال لاگین...\nکد رو که روبیکا فرستاد، همینجا بفرست.")
            a["step"] = "login_pending"
            # ★ شروع لاگین interactive rubpy
            asyncio.create_task(interactive_login_via_rubpy(cid, ph))
            return

    if "prof" in conv:
        pr = conv["prof"]; field = pr.get("field"); aid = pr.get("aid")
        STATE["panel"].pop(cid, None)
        a = get_account(aid)
        if not a: STATE["conv"].pop(cid, None); return await panel("⚠️", kb_([B("🏠 منو","menu:main")]))
        media = None
        if field == "photo":
            try: media = await extract_tg_media(msg)
            except Exception as e: return await ask(PROF_PROMPT["photo"], note=str(e)[:150])
            if not media: return await ask(PROF_PROMPT["photo"], note="فقط عکس:")
        elif not text:
            return await ask(PROF_PROMPT.get(field,"مقدار:"), note="متن لازمه")
        STATE["conv"].pop(cid, None)
        await panel("⏳ ...")
        async def job(bot):
            me = await bot.get_me(); my = me.user.user_guid
            if field == "name": return await rubika_set_name(bot, text)
            if field == "bio": return await rubika_set_bio(bot, text)
            if field == "user": return await rubika_set_username(bot, text)
            if field == "photo": return await rubika_set_photo(bot, my, media["file"])
            return False, "?"
        sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        try:
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot: ok, info = await job(bot)
        except Exception as e: ok, info = False, _fmt_error(e)
        if media:
            try: os.remove(media["file"])
            except Exception: pass
        return await panel(("✅ انجام شد" if ok else f"⚠️ {esc(str(info)[:200])}"),
                           kb_([B("⬅️", f"prof:menu:{aid}")]))

    if "chan_send" in conv:
        cs = conv["chan_send"]
        STATE["panel"].pop(cid, None)
        if cs.get("step") == "compose":
            try: media = await extract_tg_media(msg)
            except Exception as e: return await ask("📤 دوباره بفرست:", note=str(e)[:150])
            cap = (msg.caption or msg.text or "").strip()
            if not media and not cap: return await ask("📤 یک متن یا فایل بفرست:")
            payload = ({**media, "text": cap} if media
                       else {"kind":"text","text":cap,"file":None})
            cs["payload"] = payload; cs["step"] = "confirm"
            aid = cs["aid"]; idx = cs["idx"]
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans):
                STATE["conv"].pop(cid, None)
                return await panel("⚠️ کانال پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
            ch = chans[idx]
            txt = head("📤", "تایید ارسال به کانال")
            txt += f"📢 کانال: <b>{esc(ch.get('title','?'))}</b>\n"
            if media:
                txt += f"📎 نوع: <b>{esc(KIND_ICON.get(payload.get('kind'),'📎'))}</b>\n"
                txt += f"📄 نام: <code>{esc(payload.get('file_name','file'))}</code>\n"
            if cap: txt += f"\n💬 متن:\n<code>{esc(cap[:800])}</code>\n"
            return await panel(txt, kb_(
                [B("✅ ارسال", "chan:sendgo")],
                [B("✏️ تغییر پیام", "chan:sendredo")],
                [B("❌ لغو", f"chan:view:{aid}:{idx}")]))

    if "chan" in conv:
        ch = conv["chan"]; step = ch.get("step")
        STATE["panel"].pop(cid, None)
        if step == "title":
            aid = ch.get("aid"); public = ch.get("public", True)
            STATE["conv"].pop(cid, None)
            if not text: return await show_main()
            a = get_account(aid)
            if not a: return await panel("⚠️", kb_([B("🏠 منو","menu:main")]))
            await panel(f"⏳ ساخت «{esc(text[:60])}»...")
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            async def job(bot):
                ctype = "public" if public else "private"
                ok, info, guid, link = await rubika_create_channel(bot, text[:60], "", ctype)
                return ok, info, guid, link
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot: ok, info, guid, link = await job(bot)
            except Exception as e:
                return await panel(f"❌ {esc(str(e)[:200])}",
                                   kb_([B("⬅️", f"acc:view:{aid}")]))
            if not ok:
                return await panel(f"⚠️ {esc(str(info)[:300])}",
                                   kb_([B("⬅️", f"acc:view:{aid}")]))
            add_channel_to_storage(aid, {"title": text[:60], "description": "",
                "guid": guid, "username": None, "is_public": public,
                "type": "public" if public else "private",
                "join_link": link, "created": int(time.time())})
            idx = len(get_account(aid).get("channels",[])) - 1
            txt = head("✅", text[:60]) + f"🆔 <code>{esc(guid)}</code>"
            txt += "\n🔒 خصوصی" if not public else "\n🌐 عمومی"
            if not public and link: txt += f"\n🔗 <code>{esc(link)}</code>"
            return await panel(txt, kb_([B("⚙️", f"chan:view:{aid}:{idx}")],
                                         [B("📤 ارسال پیام", f"chan:send:{aid}:{idx}")],
                                         [B("⬅️", f"chan:list:{aid}")]))
        if step == "edit":
            aid = ch.get("aid"); idx = ch.get("idx"); field = ch.get("field")
            STATE["conv"].pop(cid, None)
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans): return await panel("⚠️", kb_([B("🏠 منو","menu:main")]))
            media = None
            if field == "photo":
                try: media = await extract_tg_media(msg)
                except Exception as e: return await ask(CHAN_PROMPT["photo"], note=str(e)[:150])
                if not media: return await ask(CHAN_PROMPT["photo"], note="فقط عکس:")
            elif not text:
                return await ask(CHAN_PROMPT.get(field,"مقدار:"), note="متن لازمه")
            await panel("⏳ ...")
            guid = chans[idx].get("guid")
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            async def job(bot):
                if field == "title": return await rubika_set_chat_title(bot, guid, text)
                if field == "desc": return await rubika_set_chat_description(bot, guid, text)
                if field == "user": return await rubika_set_chat_username(bot, guid, text)
                if field == "photo": return await rubika_set_chat_photo(bot, guid, media["file"])
                return False, "?"
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot: ok, info = await job(bot)
            except Exception as e: ok, info = False, _fmt_error(e)
            if media:
                try: os.remove(media["file"])
                except Exception: pass
            if ok:
                if field == "title": update_channel_field(aid, idx, "title", text)
                elif field == "desc": update_channel_field(aid, idx, "description", text)
                elif field == "user":
                    update_channel_field(aid, idx, "username", text.lstrip("@"))
                    update_channel_field(aid, idx, "is_public", True)
            return await panel(("✅ انجام شد" if ok else f"⚠️ {esc(str(info)[:200])}"),
                               kb_([B("⬅️", f"chan:view:{aid}:{idx}")]))


PROF_PROMPT = {"name":"👤 اسم جدید:","bio":"📖 بیو جدید:",
               "user":"🔤 یوزرنیم جدید:","photo":"🖼 عکس جدید:"}
CHAN_PROMPT = {"title":"✏️ اسم جدید:","desc":"📖 توضیح جدید:",
               "user":"🔗 یوزرنیم کانال:","photo":"🖼 عکس جدید:"}


# ══════════════════════════════════════════════════════════════
# Callback router (adapted — no relogin, no refresh-all)
# ══════════════════════════════════════════════════════════════
async def on_callback(update, context):
    q = update.callback_query
    try: await q.answer()
    except Exception: pass
    if not authorized(update): return
    cid = update.effective_chat.id
    data = q.data or ""
    if data == "noop": return
    if q.message: STATE["panel"][cid] = q.message.message_id
    try: await route_cb(cid, data)
    except Exception as e:
        traceback.print_exc()
        await panel(f"❌ {esc(type(e).__name__)}: {esc(str(e)[:200])}",
                    kb_([B("🏠 منو","menu:main")]))


async def route_cb(cid, data):
    p = data.split(":"); h = p[0]
    if data == "conv:cancel": clear_conv(cid); return await show_main()
    if data == "menu:main": clear_conv(cid); return await show_main()
    if data == "menu:acc": return await show_accounts()
    if data == "menu:stats": return await show_stats()
    if data == "menu:errors": return await show_errors()
    if data == "menu:cfg": return await show_cfg()
    if data == "menu:help": return await show_help()
    if data == "menu:listen": return await show_listen_menu()
    if data == "home":
        return await bale_send(cid, "مدیریت سشن‌ها:", main_kb())

    if h == "err":
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_errors(int(p[2]))
        if sub == "clear":
            clear_errors(); await tg_send("🗑 پاک شد")
            return await show_errors()

    if h == "listen":
        sub = p[1] if len(p) > 1 else ""
        if sub == "restart":
            await restart_all_listeners()
            await tg_send("🔄 لیسنرها ری‌استارت شدن")
            return await show_listen_menu()
        if sub == "toggle" and len(p) >= 3:
            aid = p[2]
            t = LISTENER_TASKS.get(aid)
            if t and not t.done():
                _stop_listener_for(aid); await tg_send(f"👂 {aid} خاموش")
            else:
                _spawn_listener_for(aid); await tg_send(f"👂 {aid} روشن")
            await asyncio.sleep(0.5)
            return await show_listen_menu()

    if h == "send":
        s = _send_conv(cid); sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            s["step"] = "accounts"; s["accounts"] = s.get("accounts") or []
            return await show_send_step(cid)
        if sub == "jl":
            c = get_conv(cid)
            c["jl"] = {"step":"account","accounts":[],"max_join":0,"speed":"fast","auto_msg":""}
            return await jl_step_account(cid, c["jl"])
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if "all" in sel: sel.remove("all")
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await show_send_step(cid)
        if sub == "accall":
            if "all" in (s.get("accounts") or []): s["accounts"] = []
            else: s["accounts"] = ["all"]
            return await show_send_step(cid)
        if sub == "accnext":
            if not s.get("accounts"): return await show_send_step(cid)
            s["step"] = "compose"; return await show_send_step(cid)
        if sub == "recompose": s["step"] = "compose"; s["payload"] = None; return await show_send_step(cid)
        if sub == "composenext":
            if not s.get("payload"): return await show_send_step(cid)
            s["step"] = "target"; return await show_send_step(cid)
        if sub == "tgt" and len(p) >= 3: s["target"] = p[2]; return await show_send_step(cid)
        if sub == "tgtnext": s["step"] = "max"; return await show_send_step(cid)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["send_wait"] = "max"
                return await ask("🔢 عدد حداکثر (0 = بدون):")
            try: s["max"] = int(v)
            except: pass
            return await show_send_step(cid)
        if sub == "maxnext": s["step"] = "schedule"; return await show_send_step(cid)
        if sub == "sch" and len(p) >= 3:
            code = p[2]
            for c2, label, secs in SCHEDULE_OPTIONS:
                if c2 == code: s["schedule"] = secs; break
            return await show_send_step(cid)
        if sub == "schedulenext": s["step"] = "confirm"; return await show_send_step(cid)
        if sub == "back": s["step"] = "accounts"; return await show_send_step(cid)
        if sub == "prev":
            order = ["accounts","compose","target","max","schedule","confirm"]
            i = order.index(s.get("step","accounts"))
            s["step"] = order[max(0, i-1)]
            return await show_send_step(cid)
        if sub == "back_edit": s["step"] = "accounts"; return await show_send_step(cid)
        if sub == "cancel": clear_conv(cid); return await show_main()
        if sub == "go":
            accounts = list_accounts()
            sel = s.get("accounts") or []
            if "all" in sel: sel = list(accounts.keys())
            payload = s.get("payload") or {"kind":"text","text":"سلام"}
            targets = s.get("_targets") or []
            if not targets: return await panel("⚠️ چیزی برای ارسال نیست.",
                                               kb_([B("🏠 منو","menu:main")]))
            op = {"id": "op_" + secrets.token_hex(5), "created": int(time.time()),
                  "scheduled_at": int(time.time()) + s.get("schedule",0),
                  "payload": payload, "target": s.get("target","both"),
                  "max": s.get("max",0) or 0, "accounts": sel,
                  "status": "draft", "task_ids": [], "_targets": targets}
            if s.get("schedule",0) > 0:
                op["status"] = "scheduled"; _save_op(op); clear_conv(cid)
                await panel(head("⏰","زمان‌بندی شد") + f"📦 {len(targets)}",
                            kb_([B("🏠 منو","menu:main")]))
            else:
                n = await op_start_now(op); clear_conv(cid)
                await panel(head("🚀","شروع شد") + f"📦 {n}",
                            kb_([B("📊 آمار","menu:stats")], [B("🏠 منو","menu:main")]))
                if not (STATE["job"] and not STATE["job"].done()):
                    cfg = _load(CFG_FILE, DEFAULT_CFG)
                    async def _job():
                        try: await run_workers(cfg, log_cb)
                        except Exception as e: await tg_send(f"❌ {type(e).__name__}")
                        finally: STATE["cancel"] = None
                    STATE["job"] = asyncio.create_task(_job())
            return

    if h == "op":
        sub = p[1] if len(p) > 1 else ""; oid = p[2] if len(p) > 2 else None
        if sub == "view" and oid: return await show_op_detail(oid)
        if sub == "stop" and oid:
            op = _get_op(oid)
            if op:
                if op.get("type") == "joinlef":
                    t = JL_JOBS.get(oid)
                    if t and not t.done(): t.cancel()
                    op["status"] = "cancelled"; op["finished_at"] = int(time.time())
                    _save_op(op)
                else:
                    op["status"] = "paused"
                    q = TaskQueue(QUEUE_FILE)
                    for t in q.tasks:
                        if t.get("op_id") == oid and t["status"] in ("pending","in_progress"):
                            t["status"] = "paused"
                    q._save(); _save_op(op)
            return await show_op_detail(oid)

    if h == "acc":
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_accounts(int(p[2]))
        if sub == "add":
            get_conv(cid)["acc"] = {"step":"phone"}
            return await ask("📞 شماره:\nمثال: <code>989121234567</code>")
        if sub == "view": return await show_account_detail(p[2])
        if sub == "del":
            a = get_account(p[2])
            if not a: return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
            return await panel(f"🗑 حذف <b>{esc(a.get('name','?'))}</b>؟",
                               kb_([B("✅ بله", f"acc:delok:{p[2]}")],
                                   [B("❌ انصراف", f"acc:view:{p[2]}")]))
        if sub == "delok":
            _stop_listener_for(p[2]); remove_account(p[2])
            await tg_send("🗑 حذف شد")
            return await show_accounts()

    if h == "prof":
        sub = p[1]; aid = p[-1]
        if sub == "menu": return await show_profile_menu(aid)
        if sub == "set":
            field = p[2]
            get_conv(cid)["prof"] = {"step":"value","aid":aid,"field":field}
            return await ask(PROF_PROMPT.get(field, "مقدار:"))

    if h == "chan":
        sub = p[1]
        if sub == "new": return await show_channel_new(p[2])
        if sub == "new_pub":
            get_conv(cid)["chan"] = {"step":"title","aid":p[2],"public":True}
            return await ask("📢 اسم کانال عمومی:")
        if sub == "new_priv":
            get_conv(cid)["chan"] = {"step":"title","aid":p[2],"public":False}
            return await ask("📢 اسم کانال خصوصی:")
        if sub == "list": return await show_channel_list(p[2])
        if sub == "page": return await show_channel_list(p[2], int(p[3]))
        if sub == "view": return await show_channel_view(p[2], int(p[3]))
        if sub == "edit":
            get_conv(cid)["chan"] = {"step":"edit","aid":p[3],"idx":int(p[4]),"field":p[2]}
            return await ask(CHAN_PROMPT.get(p[2], "مقدار:"))
        if sub == "mklink":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans): return await panel("⚠️", kb_([B("🏠 منو","menu:main")]))
            await panel("⏳ در حال ساخت لینک...")
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot:
                    ok, link = await rubika_create_join_link(bot, chans[idx]["guid"])
            except Exception as e: ok, link = False, _fmt_error(e)
            if ok: update_channel_field(aid, idx, "join_link", link)
            return await panel((f"✅ <code>{esc(link)}</code>" if ok
                                else f"⚠️ {esc(str(link)[:200])}"),
                               kb_([B("⬅️", f"chan:view:{aid}:{idx}")]))
        if sub == "del":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans): return await panel("⚠️", kb_([B("🏠 منو","menu:main")]))
            return await panel(f"🗑 حذف <b>{esc(chans[idx].get('title','?'))}</b>؟",
                               kb_([B("✅ بله", f"chan:delok:{aid}:{idx}")],
                                   [B("❌ انصراف", f"chan:view:{aid}:{idx}")]))
        if sub == "delok":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans): return await panel("⚠️", kb_([B("🏠 منو","menu:main")]))
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot:
                    ok, info = await rubika_remove_channel(bot, chans[idx]["guid"])
            except Exception as e: ok, info = False, _fmt_error(e)
            if ok: remove_channel_from_storage(aid, idx)
            return await panel(("✅ حذف شد" if ok else f"⚠️ {esc(str(info)[:200])}"),
                               kb_([B("⬅️", f"chan:list:{aid}")]))
        if sub == "send":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans): return await panel("⚠️", kb_([B("🏠 منو","menu:main")]))
            get_conv(cid)["chan_send"] = {"aid": aid, "idx": idx, "step": "compose", "payload": None}
            return await ask("📤 پیام را بفرستید:\n• متن\n• عکس\n• فایل\n\nبرای لغو /menu")
        if sub == "sendgo":
            cs = get_conv(cid).get("chan_send")
            if not cs: return await show_main()
            aid = cs["aid"]; idx = cs["idx"]; payload = cs["payload"]
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans):
                STATE["conv"].pop(cid, None)
                return await panel("⚠️", kb_([B("🏠 منو","menu:main")]))
            ch = chans[idx]; guid = ch.get("guid")
            await panel("⏳ در حال ارسال...")
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot:
                    if payload.get("file") and os.path.exists(payload["file"]):
                        await send_media(bot, guid, payload)
                    else:
                        await send_text_only(bot, guid, payload.get("text") or "—")
                ok = True; err = None
            except Exception as e:
                ok = False; err = _fmt_error(e)
            if payload and payload.get("file"):
                try: os.remove(payload["file"])
                except Exception: pass
            STATE["conv"].pop(cid, None)
            if ok:
                return await panel(f"✅ پیام به <b>{esc(ch.get('title','?'))}</b> ارسال شد",
                                   kb_([B("📤 ارسال دیگر", f"chan:send:{aid}:{idx}")],
                                       [B("⬅️", f"chan:view:{aid}:{idx}")]))
            return await panel(f"❌ {esc(str(err)[:250])}",
                               kb_([B("🔁 تلاش دوباره", f"chan:send:{aid}:{idx}")],
                                   [B("⬅️", f"chan:view:{aid}:{idx}")]))
        if sub == "sendredo":
            cs = get_conv(cid).get("chan_send")
            if not cs: return await show_main()
            if cs.get("payload") and cs["payload"].get("file"):
                try: os.remove(cs["payload"]["file"])
                except Exception: pass
            cs["step"] = "compose"; cs["payload"] = None
            return await ask("📤 پیام جدید را بفرستید:")

    if h == "jl":
        c = get_conv(cid)
        s = c.get("jl") or {"step":"account","accounts":[],"max_join":0,"speed":"fast","auto_msg":""}
        c["jl"] = s
        sub = p[1] if len(p) > 1 else ""
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await jl_step_account(cid, s)
        if sub == "speed" and len(p) >= 3:
            s["speed"] = p[2]; return await jl_step_settings(cid, s)
        if sub == "setauto":
            get_conv(cid)["jl_wait"] = "auto_msg"
            return await ask("✉️ متن پیامی که پس از جوین فرستاده بشه:")
        if sub == "clrauto":
            s["auto_msg"] = ""
            return await jl_step_settings(cid, s)
        if sub == "next":
            if s["step"] == "account": s["step"] = "settings"; return await jl_step_settings(cid, s)
            elif s["step"] == "settings": s["step"] = "max"; return await jl_step_max(cid, s)
            elif s["step"] == "max": s["step"] = "confirm"; return await jl_step_confirm(cid, s)
        if sub == "back":
            if s["step"] == "settings": s["step"] = "account"
            elif s["step"] == "max": s["step"] = "settings"
            elif s["step"] == "confirm": s["step"] = "max"
            return await show_jl_step(cid)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["jl_wait"] = "max"
                return await ask("🔢 عدد حداکثر (0 = بدون):")
            try: s["max_join"] = int(v)
            except: pass
            return await jl_step_max(cid, s)
        if sub == "cancel":
            c.pop("jl", None); return await show_main()
        if sub == "go":
            speed_map = {"ultra": 0.3, "fast": 1.0, "normal": 3.0, "slow": 8.0}
            spd = s.get("speed", "fast")
            op = {"id": "jl_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "joinlef",
                  "accounts": s.get("accounts") or [],
                  "max_join": s.get("max_join", 0) or 0,
                  "status": "running", "speed": spd,
                  "join_delay": speed_map.get(spd, 1.0),
                  "auto_msg": (s.get("auto_msg") or "").strip(),
                  "progress": {"joined":0,"failed":0,"total":0,"phase":"شروع","extracted":0,
                               "msg_sent":0,"msg_fail":0,"linkdoni_ok":[],"linkdoni_fail":[],
                               "link_errors":[]},
                  "errors": []}
            _save_op(op); c.pop("jl", None)
            task = asyncio.create_task(run_joiner_lefter(op, log_cb))
            JL_JOBS[op["id"]] = task
            return await show_op_detail(op["id"])

    if h == "cfg" and p[1] == "adj":
        return await adjust_cfg(p[2], int(p[3]))
    if h == "cfg" and p[1] == "toggle_listener":
        new = await toggle_listener_cfg()
        await tg_send(f"👂 لیسنر {'🟢' if new else '🔴'}")
        return await show_cfg()
    if h == "cfg" and p[1] == "toggle_service_only":
        new = await toggle_service_only_cfg()
        await tg_send(f"🔍 فقط سرویس {'🟢' if new else '🔴'}")
        return await show_cfg()


def _jl_conv(cid):
    c = get_conv(cid)
    if "jl" not in c:
        c["jl"] = {"step":"account","accounts":[],"max_join":0,"speed":"fast","auto_msg":""}
    return c["jl"]

async def show_jl_step(cid):
    s = _jl_conv(cid)
    if s["step"] == "account":  return await jl_step_account(cid, s)
    if s["step"] == "settings": return await jl_step_settings(cid, s)
    if s["step"] == "max":      return await jl_step_max(cid, s)
    if s["step"] == "confirm":  return await jl_step_confirm(cid, s)

async def jl_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel("⚠️ اول اکانت اضافه کن.",
                           kb_([B("➕ اکانت","acc:add")],[B("🏠 منو","menu:main")]))
    sel = set(s.get("accounts") or [])
    rows = []
    for aid, a in accounts.items():
        check = "☑" if aid in sel else "☐"
        rows.append([B(f"{check} {short(a.get('name','?'),22)} · {a.get('phone','?')}",
                       f"jl:acc:{aid}")])
    rows.append([B("▶️ مرحله بعد", "jl:next")])
    rows.append([B("🏠 منو","menu:main")])
    await panel(head("🤝","Joiner فوق‌سریع") + "کدوم اکانت(ها)؟ (همه همزمان اجرا میشن)", kb_(*rows))

async def jl_step_settings(cid, s):
    speed = s.get("speed", "fast")
    speed_label = next((label for k, label, _ in JL_SPEEDS if k == speed), "—")
    auto = (s.get("auto_msg") or "").strip()
    txt = head("⚙️", "تنظیمات Joiner")
    txt += f"🚀 سرعت: <b>{speed_label}</b>\n"
    txt += f"✉️ پیام پس از جوین: <b>{'🟢 فعال' if auto else '🔴 خاموش'}</b>\n"
    if auto: txt += f"\n💬 <code>{esc(auto[:300])}</code>\n"
    txt += "\n<i>سرعت بالا = احتمال ریسک محدودیت بیشتر</i>"
    rows = []; row = []
    for k, label, _ in JL_SPEEDS:
        row.append(B(("✅ " if speed == k else "") + label, f"jl:speed:{k}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([B("✏️ " + ("تغییر پیام" if auto else "پیام پس از جوین"), "jl:setauto")])
    if auto: rows.append([B("🗑 حذف پیام", "jl:clrauto")])
    rows.append([B("▶️ ادامه", "jl:next")])
    rows.append([B("⬅️ اکانت‌ها", "jl:back")])
    rows.append([B("🏠 منو", "menu:main")])
    await panel(txt, kb_(*rows))

async def jl_step_max(cid, s):
    mx = s.get("max_join",0); rows = []
    row = [B(("✅ " if mx==n else "")+f"{n}", f"jl:max:{n}") for n in [50,100,200]]
    rows.append(row)
    row = [B(("✅ " if mx==n else "")+f"{n}", f"jl:max:{n}") for n in [500,1000,2000]]
    rows.append(row)
    rows.append([B(("✅ " if mx==0 else "")+"♾ بدون محدودیت", "jl:max:0")])
    rows.append([B("✏️ عدد دلخواه", "jl:max:custom")])
    rows.append([B("▶️ مرحله بعد", "jl:next")])
    rows.append([B("⬅️", "jl:back")])
    await panel(head("🤝","Joiner — حداکثر هر اکانت"), kb_(*rows))

async def jl_step_confirm(cid, s):
    accounts = list_accounts(); sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "account"
        return await panel("⚠️ اکانت انتخاب نشده.", kb_([B("🏠 منو","menu:main")]))
    speed = s.get("speed", "fast")
    speed_label = next((label for k, label, _ in JL_SPEEDS if k == speed), "—")
    auto = (s.get("auto_msg") or "").strip()
    txt = head("🤝", "تایید Joiner")
    txt += f"👤 اکانت‌ها: <b>{len(sel)}</b> (همزمان)\n"
    txt += f"🚀 سرعت: <b>{speed_label}</b>\n"
    txt += f"🔢 حداکثر هر اکانت: <b>{'بدون' if not s.get('max_join') else s['max_join']}</b>\n"
    txt += f"✉️ پیام پس از جوین: <b>{'🟢 فعال' if auto else '🔴 خاموش'}</b>\n"
    if auto: txt += f"\n💬 <code>{esc(auto[:300])}</code>"
    await panel(txt, kb_(
        [B("🚀 شروع فوق‌سریع", "jl:go")],
        [B("✏️ ویرایش", "jl:back")],
        [B("❌ لغو", "jl:cancel")]))


async def op_start_now(op):
    q = TaskQueue(QUEUE_FILE)
    targets = op.get("_targets") or []
    tid_map = []
    for t in targets:
        t.setdefault("id", secrets.token_hex(8))
        t["op_id"] = op["id"]; t["use_forward"] = True
        tid_map.append(t["id"])
    n = await q.add(targets)
    op["task_ids"] = tid_map; op["status"] = "queued"
    op["started_at"] = time.time(); op.pop("_targets", None)
    _save_op(op); return n

async def op_activate_scheduled(op_id):
    op = _get_op(op_id)
    if not op or op.get("status") != "scheduled": return
    targets = op.get("_targets") or []
    if not targets: op["status"] = "empty"; _save_op(op); return
    await op_start_now(op)


async def _scheduler_loop():
    while True:
        await asyncio.sleep(20)
        try:
            now = time.time()
            for op in _load_ops():
                if op.get("status") != "scheduled": continue
                if op.get("scheduled_at", 0) <= now:
                    await op_activate_scheduled(op["id"])
        except Exception as e:
            print(f"[scheduler] {type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# Boot
# ══════════════════════════════════════════════════════════════
async def _post_init(app):
    try:
        from telegram import BotCommand
        await app.bot.set_my_commands([
            BotCommand("start","شروع"),
            BotCommand("menu","منوی اصلی"),
            BotCommand("version","نسخه"),
            BotCommand("keepalive","ping همه اکانت‌ها"),
        ])
    except Exception: pass
    try:
        asyncio.create_task(start_all_listeners())
        print("[listener] boot scheduled")
    except Exception as e: print(f"[listener-boot] {e}")
    try:
        asyncio.create_task(keepalive_loop())
        print("[keepalive] boot scheduled")
    except Exception as e: print(f"[keepalive-boot] {e}")


async def _on_error(update, context):
    print(f"[!] {type(context.error).__name__}: {context.error}")


def main():
    global APP
    if not TG_TOKEN:
        print("[x] TG_TOKEN توی env نیست."); sys.exit(1)
    STATE["owner"] = load_owner()
    try:
        _save(OWNER_FILE, {"owner": _FORCED_OWNER})
    except Exception as e:
        print(f"[owner] Could not save owner file: {e}", flush=True)
    print(f"[+] VERSION: {VERSION}")
    print(f"[+] DATA_DIR: {DATA_DIR}")

    _loop_ref[0] = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop_ref[0])

    req = HTTPXRequest(connection_pool_size=8, connect_timeout=30.0,
                       read_timeout=30.0, write_timeout=30.0, pool_timeout=30.0)
    APP = (Application.builder().token(TG_TOKEN).request(req)
           .get_updates_request(req).post_init(_post_init).build())
    APP.add_handler(CommandHandler("start", cmd_start))
    APP.add_handler(CommandHandler("menu", cmd_menu))
    APP.add_handler(CommandHandler("version", cmd_version))
    APP.add_handler(CommandHandler("keepalive", cmd_keepalive))
    APP.add_handler(CallbackQueryHandler(on_callback))
    APP.add_handler(MessageHandler(tg_filters.ALL & ~tg_filters.COMMAND, on_message))
    APP.add_error_handler(_on_error)

    loop = asyncio.get_event_loop()
    loop.create_task(_scheduler_loop())

    print("[+] polling...")
    APP.run_polling(allowed_updates=Update.ALL_TYPES, poll_interval=2.0, timeout=30.0)


if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n[!] قطع")