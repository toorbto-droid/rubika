# app.py — v60 (Fixed Session Persistence)
# pip install "python-telegram-bot>=21" rubpy rulog requests certifi pycryptodome httpx
import os, sys, ssl, json, socket, asyncio, time, glob, re, threading, secrets
import logging, traceback, concurrent.futures, tempfile, inspect
import html as _html

VERSION = "v60"

def _detect_data_dir():
    env = os.environ.get("DATA_DIR", "").strip()
    if env and os.path.isdir(env) and os.access(env, os.W_OK):
        return env
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        for c in ["/data", "/app/data"]:
            if os.path.isdir(c) and os.access(c, os.W_OK):
                return c
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

SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(pool_connections=32, pool_maxsize=32,
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
            r = SESSION.get(u, params={"name": h, "type":"A"},
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
    r = SESSION.get("https://getdcmess.iranlms.ir/", timeout=10)
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
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

def _import_rsa(pk):
    if isinstance(pk, bytes): pk = pk.decode()
    if not pk.startswith('-----BEGIN'):
        pk = f'-----BEGIN RSA PRIVATE KEY-----\n{pk}\n-----END RSA PRIVATE KEY-----'
    return pkcs1_15.new(RSA.import_key(pk.encode()))


# ══════════════════════════════════════════════════════════════
# SafeClient v60 — auth منبع حقیقت، بدون فایل .rp
# ══════════════════════════════════════════════════════════════
_AUTH_SAVE_LOCK = threading.Lock()


def _save_auth_now(aid, bot):
    """auth + key تازه رو توی accounts.json ذخیره کن."""
    if not aid: return False
    try:
        new_auth = getattr(bot, "auth", None)
        new_key = getattr(bot, "key", None)
        if not new_auth: return False
        with _AUTH_SAVE_LOCK:
            accounts = list_accounts()
            if aid not in accounts: return False
            changed = False
            if accounts[aid].get("auth") != new_auth:
                accounts[aid]["auth"] = new_auth
                changed = True
            # ★ key (passphrase) رو هم ذخیره کن — مثل سندر
            if new_key:
                key_str = new_key if isinstance(new_key, str) else str(new_key)
                if accounts[aid].get("key") != key_str:
                    accounts[aid]["key"] = key_str
                    changed = True
            if changed:
                save_accounts(accounts)
                return True
    except Exception as e:
        print(f"[auth-save] {e}")
    return False


class SafeClient(_C):
    def __init__(self, *args, **kwargs):
        self._aid = kwargs.pop("_aid", None)
        name = kwargs.get("name") or (args[0] if args else "")
        self._session_file = f"{name}.rp" if name else ""
        # ═══ CRITICAL FIX: فایل .rp رو حذف کن — auth قدیمی رو نمی‌خوایم ═══
        if self._session_file and os.path.exists(self._session_file):
            try:
                os.remove(self._session_file)
                print(f"[session] removed stale {self._session_file}")
            except Exception: pass
        # auth و private_key رو همیشه پاس بده
        super().__init__(*args, **kwargs)

    async def start(self, phone_number=None):
        if not hasattr(self, "connection"):
            await self.connect()
        from rubpy.crypto import Crypto
        if getattr(self, "auth", None):
            try: self.decode_auth = Crypto.decode_auth(self.auth)
            except Exception: pass
            try: self.key = Crypto.passphrase(self.auth)
            except Exception: pass
        if getattr(self, "private_key", None):
            try: self.import_key = _import_rsa(self.private_key)
            except Exception: pass
        last_err = None
        for attempt in range(4):
            try:
                r = await self.get_me()
                self.guid = r.user.user_guid
                _save_auth_now(self._aid, self)
                return self
            except Exception as e:
                last_err = e
                err = str(e).upper()
                if "NOT_REGISTERED" in err and attempt == 0:
                    try: await self.register_device(device_model=self.name)
                    except Exception as re: last_err = re
                    await asyncio.sleep(1.5); continue
                await asyncio.sleep(2)
        raise RuntimeError(f"AUTH_DEAD: {type(last_err).__name__}: {str(last_err)[:120]}")

    async def __aexit__(self, *args, **kwargs):
        # ★ قبل از بستن، auth رو ذخیره کن
        try: _save_auth_now(self._aid, self)
        except Exception: pass
        # ★ فایل .rp رو پاک کن — نمی‌خوایم هرگز session فایل داشته باشیم
        if self._session_file and os.path.exists(self._session_file):
            try: os.remove(self._session_file)
            except Exception: pass
        return await super().__aexit__(*args, **kwargs)


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
    return any(k in s for k in ("INVALID_AUTH", "NOT_REGISTERED", "AUTH_DEAD"))

BAD_STATUS = {"left", "kicked", "banned", "deleted", "removed", "restricted",
              "no_access", "blocked", "inactive", "closed"}

def _is_ok_response(r):
    if r is None: return True
    d = _to_dict(r)
    if not isinstance(d, dict): return True
    for k in ("status", "status_det"):
        s = str(d.get(k) or "").upper()
        if s and ("ERROR" in s or "INVALID" in s or "FAIL" in s or "NOT_" in s):
            return False
    nested = d.get("data") or d.get("result")
    if isinstance(nested, dict): return _is_ok_response(nested)
    return True

def _extract_join_link(r):
    if r is None: return None
    candidates = []
    if isinstance(r, dict):
        candidates.append(r)
        for k in ("data","result","chat","response","join_link"):
            nested = r.get(k)
            if isinstance(nested, dict): candidates.append(nested)
    for attr in ("join_link","link","url","invite_link","invite"):
        v = getattr(r, attr, None)
        if isinstance(v, str) and v.startswith("http"): return v
    d = _to_dict(r)
    if isinstance(d, dict):
        candidates.append(d)
        for k in ("data","result","chat","response"):
            nested = d.get(k)
            if isinstance(nested, dict): candidates.append(nested)
    for c in candidates:
        for key in ("join_link","link","url","invite_link","invite"):
            v = c.get(key)
            if isinstance(v, str) and v.startswith("http"): return v
    s = str(r); m = re.search(r'https?://[^\s"\'<>]+', s)
    if m: return m.group(0)
    return None

def _extract_joined_guid(r):
    if r is None: return None
    d = _to_dict(r) if not isinstance(r, dict) else r
    if not isinstance(d, dict): return None
    for k in ("chat","group","channel","object","result","data","response"):
        o = d.get(k)
        if isinstance(o, dict):
            g = _candidate_guid(o)
            if g: return g
            for k2 in ("chat","object","group","channel","result"):
                o2 = o.get(k2)
                if isinstance(o2, dict):
                    g = _candidate_guid(o2)
                    if g: return g
    return _candidate_guid(d)

def _is_rate_limit(ex):
    s = str(ex).upper()
    return any(k in s for k in ("TOO_REQUESTS","RATE_LIMIT","FLOOD","TOO_MANY",
                                 "استفاده بیش از حد","بیش از حد مجاز"))
def _is_auth_dead(ex): return "AUTH_DEAD" in str(ex)
def _is_username_limit(ex):
    s = str(ex)
    return ("10" in s and ("نام کاربری" in s or "username" in s.lower())) or \
           "maximum number of username" in s.lower() or "حداکثر تعداد نام کاربری" in s
def _is_3day_limit(ex):
    s = str(ex)
    return "3 روز" in s or "3 days" in s.lower() or "۳ روز" in s or \
           ("بایستی" in s and "روز" in s and "گذشته" in s)

def _load(path, default):
    if not os.path.exists(path): return dict(default) if isinstance(default, dict) else default
    try:
        with open(path, encoding="utf-8") as f: d = json.load(f)
        if isinstance(default, dict) and isinstance(d, dict): return {**default, **d}
        return d
    except Exception: return dict(default) if isinstance(default, dict) else default

def _save(path, data):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
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
        if msg:
            if isinstance(msg, dict):
                link = msg.get("link", {})
                alert = link.get("alert_data",{}).get("message") if isinstance(link, dict) else None
                if alert: parts.append(str(alert)[:150])
                else: parts.append(str(msg)[:150])
            else: parts.append(str(msg)[:150])
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
try: os.makedirs(MEDIA_DIR, exist_ok=True)
except Exception: pass

MAX_ERRORS = 100
RATE_LIMIT_WAIT = 20 * 60
ANCHORS = {}
JL_JOBS = {}

DEFAULT_CFG = {
    "delay": 5.0, "cooldown": 120, "max_parallel": 3,
    "batch_per_account": 2, "max_attempts": 3,
    "max_channels_per_account": 3,
    "channels": ["@linkdony_rubikas", "@lovo_lovoo0"],
}

TG_TOKEN = (os.environ.get("TG_TOKEN","").strip()
            or "8921325744:AAF77FCsmhkFBJ01gvMOi3HK8Ed00sf2ZmE")

_errors_lock = threading.Lock()

def _load_errors():
    data = _load(ERRORS_FILE, [])
    return data if isinstance(data, list) else []

def add_error(source, error, target=None, account=None):
    try:
        with _errors_lock:
            errors = _load_errors()
            errors.append({
                "time": int(time.time()),
                "source": str(source)[:40],
                "error": str(error or "")[:300],
                "target": str(target or "")[:120],
                "account": str(account or "")[:60],
            })
            if len(errors) > MAX_ERRORS: errors = errors[-MAX_ERRORS:]
            try: _save(ERRORS_FILE, errors)
            except Exception: pass
    except Exception: pass

def clear_errors():
    try:
        with _errors_lock: _save(ERRORS_FILE, [])
    except Exception: pass


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


def list_accounts(): return _load(ACC_FILE, {})
def save_accounts(a): _save(ACC_FILE, a)
def get_account(aid): return list_accounts().get(aid)

def remove_account(aid, keep_session=False):
    accounts = list_accounts(); a = accounts.pop(aid, None); save_accounts(accounts)
    if a and a.get("session_name"):
        for f in glob.glob(a["session_name"] + "*"):
            try: os.remove(f)
            except Exception: pass

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

def update_account_field(aid, key, value):
    accounts = list_accounts()
    if aid in accounts: accounts[aid][key] = value; save_accounts(accounts)


async def rubika_send_code(phone):
    from rubpy.crypto import Crypto
    sess = os.path.join(DATA_DIR, f"rubika_{phone}")
    for f in glob.glob(sess + "*"):
        try: os.remove(f)
        except Exception: pass
    c = SafeClient(name=sess, phone_number=phone, platform='Android', display_welcome=False)
    try: await c.connect()
    except Exception: pass
    pub, priv = Crypto.create_keys()
    res = await c.send_code(phone_number=phone, send_type='SMS')
    return {"client": c, "session_name": sess, "phone": phone, "pub": pub, "priv": priv,
            "phone_code_hash": res.phone_code_hash,
            "status": getattr(res, "status", None),
            "hint": getattr(res, "hint_pass_key", None)}

async def rubika_complete_login(ctx, code):
    from rubpy.crypto import Crypto
    c = ctx["client"]
    sign = await c.sign_in(phone_code=code, phone_number=ctx["phone"],
                            phone_code_hash=ctx["phone_code_hash"], public_key=ctx["pub"])
    if getattr(sign, "status", None) != "OK":
        return {"ok": False, "status": getattr(sign, "status","?")}
    auth = Crypto.decrypt_RSA_OAEP(ctx["priv"], sign.auth)
    c.auth = auth
    try: c.key = Crypto.passphrase(auth)
    except Exception: pass
    try: c.decode_auth = Crypto.decode_auth(auth)
    except Exception: pass
    try: c.import_key = _import_rsa(ctx["priv"])
    except Exception: pass
    try: await c.register_device(device_model=c.name)
    except Exception: pass
    name = getattr(sign.user, "first_name", None) or sign.user.phone
    phone = sign.user.phone
    accounts = list_accounts()
    for aid, acc in accounts.items():
        if acc.get("phone") == phone:
            accounts[aid].update({"auth": auth, "private_key": ctx["priv"], "name": name,
                                   "user_guid": sign.user.user_guid})
            accounts[aid].setdefault("channels",[])
            save_accounts(accounts)
            # ★ فایل .rp رو پاک کن
            for f in glob.glob(ctx["session_name"] + "*"):
                try: os.remove(f)
                except Exception: pass
            return {"ok": True, "aid": aid, "name": name, "relogin": True}
    aid = "acc_" + secrets.token_hex(4)
    accounts[aid] = {"phone": phone, "auth": auth, "private_key": ctx["priv"],
                     "session_name": ctx["session_name"], "name": name,
                     "created": int(time.time()),
                     "user_guid": sign.user.user_guid, "channels": []}
    save_accounts(accounts)
    # ★ فایل .rp رو پاک کن
    for f in glob.glob(ctx["session_name"] + "*"):
        try: os.remove(f)
        except Exception: pass
    return {"ok": True, "aid": aid, "name": name, "relogin": False}


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
async def rubika_get_my_profile(bot):
    try:
        me = await bot.get_me(); u = _g(me, "user", default=me)
        return {"first_name": _g(u,"first_name","firstName") or "",
                "last_name": _g(u,"last_name","lastName") or "",
                "bio": _g(u,"bio","about") or "",
                "username": _g(u,"username") or ""}
    except Exception: return {}

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
async def rubika_create_channel(bot, title, description=""):
    try:
        r = bot.add_channel(title=title, description=description or None)
        if asyncio.iscoroutine(r): r = await r
        guid = extract_chat_guid(r)
    except Exception as e:
        return False, _fmt_error(e), None
    if not guid:
        try:
            chats = await get_all_chats_raw(bot)
            for c in chats:
                if c["title"].strip() == title.strip() and c["type"] == "Channel":
                    guid = c["guid"]; break
        except Exception: pass
    return True, "add_channel", guid
async def rubika_create_join_link(bot, guid):
    if not hasattr(bot, "create_join_link"): return False, "متد create_join_link وجود نداره"
    variants = [dict(object_guid=guid, request_needed=False),
                dict(object_guid=guid, request_needed=False, usage_limit=0, expire_time=None),
                dict(object_guid=guid), dict(chat_id=guid)]
    last_err = None
    for base in variants:
        try:
            kw = _filter_kwargs(bot.create_join_link, base)
            if not kw: continue
            r = bot.create_join_link(**kw)
            if asyncio.iscoroutine(r): r = await r
            link = _extract_join_link(r)
            if link: return True, link
            last_err = f"بدون لینک در پاسخ: {str(r)[:200]}"
        except Exception as e:
            last_err = _fmt_error(e); continue
    for mname in ("get_join_links", "get_channel_link"):
        if hasattr(bot, mname):
            try:
                r = getattr(bot, mname)(**({"object_guid": guid} if mname == "get_join_links" else {"channel_guid": guid}))
                if asyncio.iscoroutine(r): r = await r
                link = _extract_join_link(r)
                if link: return True, link
            except Exception: pass
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
    is_link = ("://" in t) or ("rubika.ir" in t.lower()) or ("/joing/" in t.lower())
    if is_link:
        fn = getattr(bot, "get_link_from_app_url", None)
        if fn:
            try:
                r = fn(app_url=t)
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
            except Exception: pass
        for pname in ("channel_preview_by_join_link", "group_preview_by_join_link"):
            fn = getattr(bot, pname, None)
            if not fn: continue
            try:
                r = fn(link=t)
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
        return None, "__joing_link__"
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
    for name, kw in (("get_info", {"username": t}),
                     ("get_object_by_username", {"username": t})):
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


async def join_any(bot, target):
    t = target.strip() if isinstance(target, str) else target
    if not isinstance(t, str): return False, "not-str", None
    errors = []
    is_link = ("://" in t) or ("rubika.ir" in t.lower()) or ("/joing/" in t.lower())
    if is_link:
        fn = getattr(bot, "join_group", None)
        if fn:
            try:
                r = fn(link=t)
                if asyncio.iscoroutine(r): r = await r
                if _is_ok_response(r): return True, "join_group(link)", r
                err = _fmt_error(r)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_group(already)", None
                errors.append("join_group: " + err[:80])
            except Exception as e:
                err = _fmt_error(e)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_group(already)", None
                errors.append("join_group: " + err[:80])
        fn = getattr(bot, "join_channel_by_link", None)
        if fn:
            try:
                r = fn(link=t)
                if asyncio.iscoroutine(r): r = await r
                if _is_ok_response(r): return True, "join_channel_by_link", r
                err = _fmt_error(r)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_channel_by_link(already)", None
                errors.append("join_channel_by_link: " + err[:80])
            except Exception as e:
                err = _fmt_error(e)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_channel_by_link(already)", None
                errors.append("join_channel_by_link: " + err[:80])
        guid, kind = await _resolve_target(bot, t)
        if guid:
            if kind == "Channel" or guid[0].lower() == "c":
                fn = getattr(bot, "join_channel_action", None)
                if fn:
                    try:
                        r = fn(channel_guid=guid, action="Join")
                        if asyncio.iscoroutine(r): r = await r
                        if _is_ok_response(r): return True, "join_channel_action(resolved)", r
                        err = _fmt_error(r)
                        if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                            return True, "join_channel_action(already)", None
                        errors.append("join_channel_action: " + err[:80])
                    except Exception as e:
                        errors.append("join_channel_action: " + _fmt_error(e)[:80])
            fn = getattr(bot, "join_chat", None)
            if fn:
                try:
                    r = fn(chat=guid)
                    if asyncio.iscoroutine(r): r = await r
                    if _is_ok_response(r): return True, "join_chat(guid)", r
                    err = _fmt_error(r)
                    if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                        return True, "join_chat(already)", None
                    errors.append("join_chat(guid): " + err[:80])
                except Exception as e:
                    errors.append("join_chat(guid): " + _fmt_error(e)[:80])
        return False, " | ".join(errors[-3:]) or "all-failed", None
    guid, kind = await _resolve_target(bot, t)
    if not guid:
        return False, "resolve-failed: " + t[:40], None
    if kind == "Channel" or guid[0].lower() == "c":
        attempts = [
            ("join_channel_action", "join_channel_action",
             {"channel_guid": guid, "action": "Join"}),
            ("join_chat", "join_chat", {"chat": guid}),
        ]
    else:
        attempts = [
            ("join_chat", "join_chat", {"chat": guid}),
            ("join_channel_action", "join_channel_action",
             {"channel_guid": guid, "action": "Join"}),
        ]
    for label, name, kw in attempts:
        fn = getattr(bot, name, None)
        if not fn: continue
        try:
            r = fn(**kw)
            if asyncio.iscoroutine(r): r = await r
            if _is_ok_response(r): return True, label + " (kind=" + str(kind) + ")", r
            err = _fmt_error(r)
            if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                return True, label + "(already)", None
            errors.append(label + ": " + err[:80])
        except Exception as e:
            err = _fmt_error(e)
            if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                return True, label + "(already)", None
            errors.append(label + ": " + err[:80])
    return False, " | ".join(errors[-3:]), None


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

async def get_live_channels(bot):
    return [c for c in await get_all_chats_raw(bot) if c["type"] == "Channel"]

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

async def send_text(bot, target, text):
    r = bot.send_message(target, text)
    if asyncio.iscoroutine(r): r = await r
    return True


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
    else:
        ops.append(op)
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
    elif p.get("text"):
        base = f"💬 {p.get('text')[:n]}"
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


async def _get_chat_info_any(bot, guid, kind=""):
    kind = (kind or "").lower()
    if kind == "group":
        names = ("get_group_info", "get_chat_info", "get_info")
        kwargs_list = ({"group_guid": guid}, {"object_guid": guid}, {"chat_guid": guid})
    elif kind == "channel":
        names = ("get_channel_info", "get_chat_info", "get_info")
        kwargs_list = ({"channel_guid": guid}, {"object_guid": guid}, {"chat_guid": guid})
    else:
        names = ("get_group_info", "get_channel_info", "get_chat_info", "get_info")
        kwargs_list = ({"object_guid": guid}, {"chat_guid": guid})
    for name in names:
        fn = getattr(bot, name, None)
        if not fn: continue
        for kw in kwargs_list:
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                if r: return r
            except TypeError: continue
            except Exception as e:
                if _is_auth_error(e): raise
                return None
    return None


async def can_send_to(bot, guid, kind="", raw=None):
    if not kind or kind == "pv": return True, "pv"
    kind = kind.lower()
    try:
        info = await _get_chat_info_any(bot, guid, kind)
    except Exception as e:
        if _is_auth_error(e): raise
        return False, "info-error"
    if info is None: return False, "not-found"
    keys = ("access", "default_access", "status", "chat_status", "user_status",
            "member_status", "is_deleted", "deleted", "is_blocked", "blocked",
            "is_removed", "left", "kicked", "is_kicked", "is_banned",
            "can_send", "is_readonly", "read_only")
    found = {}
    if raw: _find_keys(raw, keys, found)
    _find_keys(_to_plain(info), keys, found)
    for k in ("is_deleted", "deleted", "is_blocked", "blocked", "is_removed",
              "left", "kicked", "is_kicked", "is_banned"):
        if found.get(k) is True: return False, k
    for k in ("status", "chat_status", "user_status", "member_status"):
        if str(found.get(k) or "").lower() in BAD_STATUS:
            return False, str(found[k]).lower()
    acc = found.get("access")
    if isinstance(acc, list):
        return (True, "ok") if "SendMessages" in acc else (False, "no-send-access")
    da = found.get("default_access")
    if isinstance(da, list) and "SendMessages" not in da:
        return False, "send-closed"
    if found.get("can_send") is False or found.get("is_readonly") or found.get("read_only"):
        return False, "readonly"
    return True, "ok"


async def _extract_links_from_bot(bot, guid, limit=500, want=None, log=None):
    found = set(); anchor = None; read_total = 0; batch = 25
    rounds = 0; max_rounds = 50; seen_ids = set()
    while read_total < limit and rounds < max_rounds:
        rounds += 1
        try:
            msgs_raw = await fetch_messages(bot, guid, limit=batch, max_id=anchor)
        except Exception as e:
            if log: log("   warn fetch_messages: " + _fmt_error(e)[:120])
            break
        if not msgs_raw:
            if log: log("   دور " + str(rounds) + ": هیچ پیامی نبود")
            break
        if log: log("   دور " + str(rounds) + ": " + str(len(msgs_raw)) + " پیام")
        new_msgs = []
        for m in msgs_raw:
            mid = m.get("id")
            if mid is None: continue
            if mid in seen_ids: continue
            seen_ids.add(mid); new_msgs.append(m)
        if not new_msgs:
            if log: log("   تکراری، توقف")
            break
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
            for attr in ("message_id", "messageId", "id"):
                v = getattr(r, attr, None)
                if v: return str(v)
            for attr in ("message_update", "messageUpdate", "message"):
                o = getattr(r, attr, None)
                if o is not None:
                    m = _extract_any_mid(o)
                    if m: return m
            return None
    for k in ("message_id", "messageId", "id"):
        v = r.get(k)
        if v: return str(v)
    for k in ("message_update", "messageUpdate", "message",
              "data", "result", "response", "update"):
        nested = r.get(k)
        if nested is not None:
            m = _extract_any_mid(nested)
            if m: return m
    for k in ("messages", "message_ids"):
        arr = r.get(k)
        if isinstance(arr, list) and arr:
            m = _extract_any_mid(arr[0])
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
    if not my_guid: raise RuntimeError("my_guid خالیه")
    if not target: raise RuntimeError("target خالیه")
    try:
        r = fn(from_object_guid=str(my_guid),
               message_ids=msg_ids,
               to_object_guid=str(target))
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

async def worker(aid, acc, queue, st, cfg, stop, log):
    nm = acc.get("name") or acc.get("phone") or aid
    while not stop.is_set():
        try:
            cli = SafeClient(name=acc["session_name"], auth=acc.get("auth"),
                             private_key=acc.get("private_key"),
                             phone_number=acc["phone"], _aid=aid,
                             platform='Android', display_welcome=False, timeout=120, max_retries=10)
            async with cli as bot:
                me = await bot.get_me(); nm = me.user.first_name or acc["phone"]
                my_guid = me.user.user_guid
                log(f"✅ {nm} آماده")
                while not stop.is_set():
                    rl_until = STATE.get("rate_limit_until", 0)
                    if time.time() < rl_until:
                        wait = int(rl_until - time.time())
                        await asyncio.sleep(min(max(wait, 1), 30)); continue
                    if not st.ready():
                        await asyncio.sleep(min(st.remaining(), 10)); continue
                    tasks = await queue.claim(aid, cfg["batch_per_account"])
                    if not tasks: await asyncio.sleep(3); continue
                    batch_rate_limited = False
                    for idx, t in enumerate(tasks):
                        if stop.is_set(): break
                        if time.time() < STATE.get("rate_limit_until", 0):
                            await queue.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                            batch_rate_limited = True; break
                        try:
                            payload = t.get("payload") or {"kind":"text","text":cfg.get("message","سلام")}
                            op_id = t.get("op_id","_")
                            use_forward = t.get("use_forward", True)
                            akey = (aid, op_id)
                            ids = ANCHORS.get(akey)
                            if use_forward and ids is None:
                                try:
                                    ids = await send_anchor(bot, my_guid, payload)
                                except Exception as e:
                                    if _is_rate_limit(e):
                                        await queue.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                                        batch_rate_limited = True; break
                                    ids = []
                                ANCHORS[akey] = ids
                            if use_forward and ids and t["target"] != my_guid:
                                await forward_from_anchor(bot, t["target"], my_guid, ids)
                            else:
                                await send_media(bot, t["target"], payload)
                            await queue.complete(t["id"], True, max_attempts=cfg["max_attempts"])
                            st.n += 1
                        except Exception as e:
                            err = _fmt_error(e)
                            if _is_rate_limit(e):
                                already = time.time() < STATE.get("rate_limit_until", 0)
                                if not already:
                                    STATE["rate_limit_until"] = time.time() + RATE_LIMIT_WAIT
                                    add_error("محدودیت", err, t.get("target"), nm)
                                    try:
                                        await tg_send(
                                            f"⏸ <b>محدودیت روبیکا</b>\n"
                                            f"اکانت: <b>{esc(nm)}</b>\n"
                                            f"⏳ ۲۰ دقیقه توقف."
                                        )
                                    except Exception: pass
                                await queue.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                                batch_rate_limited = True; break
                            if "INVALID_AUTH" in err:
                                session_ok = False
                                try: await bot.get_me(); session_ok = True
                                except Exception: session_ok = False
                                if not session_ok:
                                    await queue.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                                    add_error("احراز هویت", err, t.get("target"), nm)
                                    try:
                                        await tg_send(f"🔐 اکانت «{esc(nm)}» نیاز به ورود مجدد دارد.",
                                                      parse_mode="HTML")
                                    except Exception: pass
                                    return
                                add_error("بدون دسترسی", err, t.get("target"), nm)
                                await queue.complete(t["id"], False, err, max_attempts=1)
                                st.f += 1
                                await asyncio.sleep(cfg["delay"]); continue
                            add_error("ارسال", err, t.get("target"), nm)
                            await queue.complete(t["id"], False, err, max_attempts=cfg["max_attempts"])
                            st.f += 1
                        await asyncio.sleep(cfg["delay"])
                    if batch_rate_limited: continue
        except RuntimeError as e:
            if _is_auth_dead(e):
                add_error("احراز هویت", str(e)[:200], None, nm)
                log(f"❌ {acc.get('name')}: AUTH_DEAD"); return
            log(f"⚠️ {aid}: {str(e)[:100]}")
            await queue.requeue_account(aid); st.cooldown(30); await asyncio.sleep(10)
        except Exception as e:
            log(f"⚠️ {aid}: {type(e).__name__}")
            await queue.requeue_account(aid); st.cooldown(30); await asyncio.sleep(10)

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
        first_err = ""
        fn = getattr(bot, "join_group", None)
        if fn:
            try:
                r = fn(link=link)
                if asyncio.iscoroutine(r): r = await r
                if _is_ok_response(r): return True, "join_group"
                err = _fmt_error(r)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_group(already)"
                first_err = err
            except Exception as e:
                first_err = _fmt_error(e)
                if "ALREADY" in first_err.upper() or "MEMBER" in first_err.upper():
                    return True, "join_group(already)"
        else: first_err = "join_group missing"
        fn = getattr(bot, "join_channel_by_link", None)
        if fn:
            try:
                r = fn(link=link)
                if asyncio.iscoroutine(r): r = await r
                if _is_ok_response(r): return True, "join_channel_by_link"
                err = _fmt_error(r)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_channel_by_link(already)"
                return False, "link-failed: " + err[:100]
            except Exception as e:
                err = _fmt_error(e)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_channel_by_link(already)"
                return False, "link-failed: " + str(first_err)[:60] + " | " + err[:60]
        return False, "link-failed: " + str(first_err)[:100]
    if link.startswith("@"):
        bare = link[1:]
        guid = None
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
                    if g: guid = g; break
            except Exception: continue
        if not guid: return False, "no-guid-for:" + bare[:40]
        if guid[0].lower() == "c":
            fn = getattr(bot, "join_channel_action", None)
            if fn:
                try:
                    r = fn(channel_guid=guid, action="Join")
                    if asyncio.iscoroutine(r): r = await r
                    if _is_ok_response(r): return True, "join_channel_action"
                    err = _fmt_error(r)
                    if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                        return True, "join_channel_action(already)"
                except Exception as e:
                    err = _fmt_error(e)
                    if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                        return True, "join_channel_action(already)"
        fn = getattr(bot, "join_chat", None)
        if fn:
            try:
                r = fn(chat=guid)
                if asyncio.iscoroutine(r): r = await r
                if _is_ok_response(r): return True, "join_chat"
                err = _fmt_error(r)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_chat(already)"
                return False, "join_chat: " + err[:100]
            except Exception as e:
                err = _fmt_error(e)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                    return True, "join_chat(already)"
                return False, "join_chat: " + err[:100]
        return False, "no-method"
    return False, "unknown-format"


async def run_joiner_lefter(op, log):
    op_id = op["id"]
    accounts = list_accounts()
    sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    max_join = op.get("max_join", 0) or 0
    op["progress"] = {
        "joined": 0, "failed": 0, "total": 0,
        "phase": "شروع", "extracted": 0,
        "verified": 0, "new_chats": 0,
        "linkdoni_ok": [], "linkdoni_fail": [], "link_errors": [],
    }
    op["status"] = "running"; op["errors"] = []
    _save_op(op)
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        acc_name = a.get("name") or a.get("phone") or aid
        try:
            async def job(bot):
                op["progress"]["phase"] = "۱/۴ جوین لینکدونی‌ها"
                _save_op(op)
                linkdoni_guids = []
                for link in JOIN_DEFAULTS:
                    guid, kind = await _resolve_target(bot, link)
                    if not guid:
                        op["progress"]["linkdoni_fail"].append((link, "resolve"))
                        continue
                    ok = False
                    try:
                        if kind == "Channel" or guid[0].lower() == "c":
                            r = bot.join_channel_action(channel_guid=guid, action="Join")
                        else:
                            r = bot.join_chat(chat=guid)
                        if asyncio.iscoroutine(r): r = await r
                        ok = _is_ok_response(r)
                        err = _fmt_error(r)
                        if not ok and ("ALREADY" in err.upper() or "MEMBER" in err.upper()):
                            ok = True
                    except Exception as e:
                        err = _fmt_error(e)
                        if "ALREADY" in err.upper() or "MEMBER" in err.upper():
                            ok = True
                    if ok:
                        linkdoni_guids.append(guid)
                        op["progress"]["linkdoni_ok"].append(link)
                        log("✅ " + acc_name + ": " + link)
                    await asyncio.sleep(3)
                if not linkdoni_guids:
                    op["progress"]["phase"] = "هیچ لینکدونی"
                    _save_op(op); return
                op["progress"]["phase"] = "۲/۴ صبر برای سینک"
                _save_op(op); await asyncio.sleep(15)
                op["progress"]["phase"] = "۳/۴ استخراج لینک"
                _save_op(op)
                ordered_links = {}
                for guid in linkdoni_guids:
                    log("   خواندن " + guid[:15])
                    try:
                        found = await _extract_links_from_bot(bot, guid, limit=500, want=None, log=log)
                        for l in found:
                            if l not in ordered_links: ordered_links[l] = True
                        op["progress"]["extracted"] = len(ordered_links)
                        _save_op(op)
                    except Exception as e:
                        add_error("استخراج", _fmt_error(e), guid, acc_name)
                if not ordered_links:
                    op["progress"]["phase"] = "لینکی نبود"
                    _save_op(op); return
                all_links = list(ordered_links.keys())
                op["progress"]["total"] = len(all_links)
                op["progress"]["phase"] = "۴/۴ جوین"
                _save_op(op)
                log("🤝 " + acc_name + ": " + str(len(all_links)) + " لینک، هدف " + str(max_join))
                before_chats = set()
                try:
                    bc = await get_all_chats_raw(bot)
                    before_chats = {c["guid"] for c in bc}
                except Exception: pass
                seen_hashes = set()
                for i, link in enumerate(all_links):
                    if max_join and op["progress"]["joined"] >= max_join:
                        log("   ✅ به هدف رسیدیم")
                        break
                    if op["status"] == "cancelled": break
                    h = _hash_of(link)
                    if h in seen_hashes: continue
                    seen_hashes.add(h)
                    try:
                        ok, msg = await _try_join_single(bot, link)
                        if ok:
                            op["progress"]["joined"] += 1
                            log("   ✅ [" + str(op["progress"]["joined"]) + "] " + link[:55])
                        else:
                            op["progress"]["failed"] += 1
                            op["progress"]["link_errors"].append((link, str(msg)[:100]))
                    except Exception as e:
                        op["progress"]["failed"] += 1
                        op["progress"]["link_errors"].append((link, _fmt_error(e)[:100]))
                    if len(op["progress"]["link_errors"]) > 30:
                        op["progress"]["link_errors"] = op["progress"]["link_errors"][-30:]
                    _save_op(op)
                    await asyncio.sleep(4)
                op["progress"]["phase"] = "verify"
                _save_op(op); await asyncio.sleep(8)
                try:
                    after = await get_all_chats_raw(bot)
                    after_guids = {c["guid"] for c in after}
                    new_guids = after_guids - before_chats
                    op["progress"]["new_chats"] = len(new_guids)
                    log("   📊 چت جدید: " + str(len(new_guids)))
                except Exception: pass
            await with_bot(a, job, 3600, aid=aid)
        except asyncio.CancelledError:
            op["status"] = "cancelled"
            op["progress"]["phase"] = "لغو شد"
            _save_op(op); raise
        except Exception as e:
            op.setdefault("errors", []).append(acc_name + ": " + type(e).__name__)
    if op.get("status") != "cancelled":
        op["status"] = "done"; op["progress"]["phase"] = "تمام"
    op["finished_at"] = int(time.time())
    _save_op(op)


async def with_bot(acc, fn, timeout=90, aid=None):
    cli = SafeClient(name=acc["session_name"], auth=acc.get("auth"),
                     private_key=acc.get("private_key"),
                     phone_number=acc["phone"], _aid=aid,
                     platform='Android', display_welcome=False,
                     timeout=timeout, max_retries=10)
    async with cli as bot:
        return await fn(bot)


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
         "rate_limit_until": 0}
APP = None
_last_log = [0.0]
_loop_ref = [None]


def esc(s): return _html.escape(str(s if s is not None else ""))
def short(s, n=40):
    s = str(s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n-1] + "…"
def B(l, d): return InlineKeyboardButton(l, callback_data=d)
def kb_(*rows): return InlineKeyboardMarkup([list(r) for r in rows if r])
def head(icon, t): return f"<b>{icon} {esc(t)}</b>\n{HR}\n"

def authorized(update):
    if STATE["owner"] is None: return False
    try: return update.effective_chat.id == STATE["owner"]
    except Exception: return False

def load_owner(): return _load(OWNER_FILE, {}).get("owner")
def save_owner(cid): _save(OWNER_FILE, {"owner": cid})


async def tg_send(text, markup=None, parse_mode=None):
    if not STATE["owner"] or APP is None: return False
    text = str(text)[:4000]
    for attempt in range(3):
        try:
            await APP.bot.send_message(chat_id=STATE["owner"], text=text,
                                       reply_markup=markup, parse_mode=parse_mode)
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


async def show_main():
    accounts = list_accounts()
    ops = _load_ops()
    running_ops = [o for o in ops if _op_effective_status(o) == "running"]
    txt = head("🤖", f"پنل ربات روبیکا — {VERSION}")
    txt += f"📱 اکانت‌ها: <b>{len(accounts)}</b>\n"
    txt += f"📊 عملیات‌ها: <b>{len(ops)}</b>\n"
    if running_ops: txt += f"🟢 در حال اجرا: <b>{len(running_ops)}</b>\n"
    txt += f"\n💾 DATA_DIR: <code>{esc(DATA_DIR)}</code>\n"
    txt += "\nاز منوی زیر انتخاب کن:"
    await panel(txt, kb_(
        [B("📤 ارسال", "send:start")],
        [B("🤝 Joiner", "send:jl")],
        [B("📱 اکانت‌ها", "menu:acc"), B("📊 آمار", "menu:stats")],
        [B("⚙️ تنظیمات", "menu:cfg"), B("❓ راهنما", "menu:help")]))


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
    txt = (head("📱", a.get("name","?")) +
           f"📞 <code>{esc(a.get('phone','—'))}</code>\n"
           f"🆔 <code>{esc(aid)}</code>\n"
           f"📢 کانال‌ها: <b>{n_ch}</b>")
    await panel(txt, kb_(
        [B("📝 پروفایل", f"prof:menu:{aid}")],
        [B("📢 ساخت کانال", f"chan:new:{aid}"), B("📋 کانال‌ها", f"chan:list:{aid}")],
        [B("🔐 ورود مجدد", f"acc:relogin:{aid}"), B("🗑 حذف", f"acc:del:{aid}")],
        [B("⬅️ اکانت‌ها", "menu:acc"), B("🏠 منو", "menu:main")]))

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
        [B("✏️ اسم", f"chan:edit:title:{aid}:{idx}"), B("📖 بیو", f"chan:edit:desc:{aid}:{idx}")],
        [B("🔗 یوزرنیم", f"chan:edit:user:{aid}:{idx}"), B("🖼 عکس", f"chan:edit:photo:{aid}:{idx}")],
        [B("🔁 لینک جدید", f"chan:mklink:{aid}:{idx}"), B("🗑 حذف", f"chan:del:{aid}:{idx}")],
        [B("⬅️", f"chan:list:{aid}")]))


SCHEDULE_OPTIONS = [
    ("0", "⚡️ آنی", 0), ("1h", "۱ ساعت بعد", 3600),
    ("3h", "۳ ساعت بعد", 3*3600), ("12h", "۱۲ ساعت بعد", 12*3600),
    ("24h", "۲۴ ساعت بعد", 24*3600),
]
MAX_OPTIONS = [50, 100, 500, 1000]

def _send_conv(cid):
    c = get_conv(cid)
    if "send" not in c: c["send"] = {"step":"accounts","accounts":[],"payload":None,
                                     "target":"both","max":0,"schedule":0}
    return c["send"]

async def show_send_step(cid):
    s = _send_conv(cid)
    step = s["step"]
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
        names = []
        for aid in accs[:3]:
            a = get_account(aid)
            if a: names.append(a.get("name","?"))
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
    txt += ("یک پیام بفرست:\n• فقط متن\n• فقط فایل\n• هر دو\n\n")
    txt += _send_summary(s)
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
    txt = head("📤","ارسال — مقصد") + "پیام رو کجا بفرستیم؟\n\n" + _send_summary(s)
    await panel(txt, kb_(*rows))

async def send_step_max(cid, s):
    mx = s.get("max",0)
    rows = []
    row = []
    for n in MAX_OPTIONS[:3]:
        row.append(B(("✅ " if mx==n else "")+f"{n}", f"send:max:{n}"))
    rows.append(row)
    row2 = []
    for n in MAX_OPTIONS[3:]:
        row2.append(B(("✅ " if mx==n else "")+f"{n}", f"send:max:{n}"))
    if row2: rows.append(row2)
    rows.append([B(("✅ " if mx==0 else "")+"♾ بدون محدودیت", "send:max:0")])
    rows.append([B("✏️ عدد دلخواه", "send:max:custom")])
    rows.append([B("▶️ مرحله بعد: زمان‌بندی", "send:maxnext")])
    rows.append([B("⬅️ مقصد","send:prev")])
    rows.append([B("🏠 منو","menu:main")])
    txt = head("📤","ارسال — حداکثر پیام") + "چند پیام حداکثر؟\n\n" + _send_summary(s)
    await panel(txt, kb_(*rows))

async def send_step_schedule(cid, s):
    sch = s.get("schedule",0)
    rows = [[B(("✅ " if sch==0 else "")+"⚡️ آنی", "send:sch:0")]]
    row = []
    for code, label, secs in SCHEDULE_OPTIONS[1:3]:
        row.append(B(("✅ " if sch==secs else "")+label, f"send:sch:{code}"))
    if row: rows.append(row)
    row = []
    for code, label, secs in SCHEDULE_OPTIONS[3:]:
        row.append(B(("✅ " if sch==secs else "")+label, f"send:sch:{code}"))
    if row: rows.append(row)
    rows.append([B("▶️ آنالیز و تایید", "send:schedulenext")])
    rows.append([B("⬅️ حداکثر","send:prev")])
    rows.append([B("🏠 منو","menu:main")])
    txt = head("📤","ارسال — زمان‌بندی") + "چه زمانی شروع بشه؟\n\n" + _send_summary(s)
    await panel(txt, kb_(*rows))

async def send_step_confirm(cid, s):
    await panel("⏳ در حال آنالیز...")
    accounts = list_accounts()
    sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "accounts"
        return await panel("⚠️ اکانت انتخاب نشده.", kb_([B("🏠 منو","menu:main")]))
    tgt = s.get("target","both")
    total_targets = []; skipped = []; errors = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        acc_name = a.get("name") or a.get("phone") or aid
        try:
            async def collect_all(bot):
                pv = await collect_pv(bot) if tgt in ("pv","both") else []
                gr = await collect_groups(bot) if tgt in ("groups","both") else []
                return pv, gr
            pv, gr = await with_bot(a, collect_all, 90, aid=aid)
            for it in pv:
                it["owner_account"] = aid
                it["payload"] = s.get("payload") or {"kind":"text","text":"سلام"}
                total_targets.append(it)
            sem = asyncio.Semaphore(6)
            async def check(bot, it, raw_map):
                async with sem:
                    kind = it.get("type","group")
                    if kind == "pv": return True
                    try:
                        ok, reason = await can_send_to(bot, it["target"], kind,
                                                        raw_map.get(it["target"]))
                    except Exception as e:
                        if _is_auth_error(e): raise
                        ok, reason = False, f"check-error:{type(e).__name__}"
                    if not ok:
                        nm_target = it.get("name") or it["target"][:12]
                        skipped.append((nm_target, reason))
                        add_error("رد شده", reason, nm_target, acc_name)
                    return ok
            async def validate_all(bot):
                raw_map = {c["guid"]: c.get("raw") for c in await get_all_chats_raw(bot)}
                return await asyncio.gather(*[check(bot, it, raw_map) for it in gr])
            try:
                valid_flags = await with_bot(a, validate_all, 120, aid=aid)
            except Exception as e:
                errors.append(f"{a.get('name','?')}: validation {type(e).__name__}")
                valid_flags = [True] * len(gr)
            for it, ok in zip(gr, valid_flags):
                if not ok: continue
                it["owner_account"] = aid
                it["payload"] = s.get("payload") or {"kind":"text","text":"سلام"}
                total_targets.append(it)
        except Exception as e:
            errors.append(f"{a.get('name','?')}: {type(e).__name__}")
    mx = s.get("max",0) or 0
    if mx and len(total_targets) > mx: total_targets = total_targets[:mx]
    s["_targets"] = total_targets
    s["_analysis_errors"] = errors; s["_skipped"] = skipped
    txt = head("📊","آنالیز")
    txt += f"📦 مقصد تایید شده: <b>{len(total_targets)}</b>\n"
    if skipped: txt += f"🚫 رد شده: <b>{len(skipped)}</b>\n"
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
            f"⚠️ خطاهای اخیر: <b>{len(errs)}</b>\n\n"
            f"📁 آخرین عملیات‌ها ({min(10,len(ops))} از {len(ops)}):")
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
    errors = _load_errors()
    errors = list(reversed(errors))
    if not errors:
        return await panel(head("⚠️","خطاها") + "هیچ خطایی ثبت نشده.",
                           kb_([B("🏠 منو","menu:main")]))
    PER = 5
    pages = max(1, -(-len(errors) // PER))
    page = max(0, min(page, pages-1))
    chunk = errors[page*PER:(page+1)*PER]
    txt = head("⚠️", f"خطاها ({len(errors)} از ۱۰۰)")
    txt += f"<i>صفحه {page+1}/{pages}</i>\n"
    for e in chunk:
        t = time.strftime('%m/%d %H:%M', time.localtime(e.get("time",0)))
        src = e.get("source","?")
        acc = e.get("account") or ""
        tgt = e.get("target") or ""
        txt += f"\n🕐 <code>{esc(t)}</code> · <b>{esc(src)}</b>\n"
        if acc or tgt:
            line = []
            if acc: line.append(f"👤 {esc(acc)}")
            if tgt: line.append(f"🎯 {esc(short(tgt,25))}")
            txt += " · ".join(line) + "\n"
        txt += f"❗️ <code>{esc(str(e.get('error',''))[:220])}</code>\n"
    rows = []
    pr = []
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
        txt += f"📍 مرحله: <b>{esc(p.get('phase','—'))}</b>\n\n"
        txt += f"✅ جوین شده: <b>{s['done']}</b>\n"
        txt += f"❌ ناموفق: <b>{s['failed']}</b>\n"
        txt += f"⏳ در انتظار: <b>{s['pending']}</b>\n"
        txt += f"📊 مجموع: <b>{s['total']}</b>\n\n"
        if p.get("extracted"): txt += f"🔗 لینک استخراج‌شده: <b>{p.get('extracted')}</b>\n"
        if p.get("new_chats") is not None: txt += f"📈 چت‌های جدید: <b>{p.get('new_chats',0)}</b>\n"
        txt += f"🔢 حداکثر: <b>{op.get('max_join',0) or 'بدون محدودیت'}</b>\n"
        ok_l = p.get("linkdoni_ok") or []; fail_l = p.get("linkdoni_fail") or []
        if ok_l or fail_l:
            txt += f"\n📥 <b>لینکدونی‌ها:</b> ✅{len(ok_l)} ❌{len(fail_l)}\n"
            for link, err in fail_l[:3]:
                txt += f"  ❌ {esc(link)} → <code>{esc(str(err)[:60])}</code>\n"
        lerrs = p.get("link_errors") or []
        if lerrs:
            txt += f"\n⚠️ <b>خطاهای جوین ({len(lerrs)}):</b>\n"
            for link, err in lerrs[-5:]:
                txt += f"  • <code>{esc(str(link)[:40])}</code>\n    → {esc(str(err)[:70])}\n"
        created = op.get("created", 0)
        if created:
            txt += f"\n📅 شروع: <b>{esc(time.strftime('%Y/%m/%d %H:%M', time.localtime(created)))}</b>\n"
        if op.get("finished_at"):
            txt += f"🏁 پایان: <b>{esc(time.strftime('%Y/%m/%d %H:%M', time.localtime(op['finished_at'])))}</b>\n"
        rows = []
        if st == "running": rows.append([B("⏹ توقف", f"op:stop:{oid}")])
        rows.append([B("⬅️ آمار","menu:stats"), B("🏠 منو","menu:main")])
        return await panel(txt, kb_(*rows))
    txt += f"✅ موفق: <b>{s['done']}</b>\n"
    txt += f"❌ ناموفق: <b>{s['failed']}</b>\n"
    txt += f"⏳ انتظار: <b>{s['pending']}</b>\n"
    txt += f"🔄 جاری: <b>{s['in_progress']}</b>\n\n"
    p = op.get("payload") or {}
    if p.get("file"): txt += f"📎 فایل: <b>{esc(p.get('file_name','?'))}</b>\n"
    if p.get("text"): txt += f"💬 متن: <code>{esc(short(p.get('text'),200))}</code>\n"
    txt += f"\n🎯 مقصد: <b>{esc(_op_target_label(op))}</b>\n"
    created = op.get("created",0)
    txt += f"📅 ارسال شده در: <b>{esc(time.strftime('%Y/%m/%d %H:%M', time.localtime(created)) if created else '—')}</b>\n"
    rows = []
    if st == "running": rows.append([B("⏹ توقف ارسال", f"op:stop:{oid}")])
    elif st == "paused": rows.append([B("▶️ از سرگیری", f"op:resume:{oid}")])
    elif st == "scheduled":
        rows.append([B("⚡️ شروع فوری", f"op:force:{oid}")])
        rows.append([B("❌ لغو زمان‌بندی", f"op:cancel:{oid}")])
    elif st in ("done","failed","empty"):
        rows.append([B("🔁 تکرار این پیام", f"op:repeat:{oid}")])
    rows.append([B("⬅️ آمار","menu:stats"), B("🏠 منو","menu:main")])
    await panel(txt, kb_(*rows))


OP_VIEW_TASKS = {}
async def op_view_loop(cid, oid):
    try:
        for _ in range(400):
            await asyncio.sleep(4)
            op = _get_op(oid)
            if not op: return
            st = _op_effective_status(op)
            await show_op_detail(oid)
            if st in ("done","failed","cancelled"): return
    except asyncio.CancelledError: raise
def stop_op_view(cid):
    t = OP_VIEW_TASKS.pop(cid, None)
    if t: t.cancel()
def start_op_view(cid, oid):
    stop_op_view(cid)
    OP_VIEW_TASKS[cid] = asyncio.create_task(op_view_loop(cid, oid))


CFG_FIELDS = [
    ("delay","⏱ تاخیر","s",1,0,120),
    ("cooldown","❄️ استراحت","s",30,0,3600),
    ("batch_per_account","📦 دسته","",1,1,20),
    ("max_parallel","🚀 هم‌زمان","",1,1,10),
    ("max_attempts","🔁 تلاش","",1,1,10),
]
def _fmt_num(v):
    try:
        v = float(v)
        return str(int(v)) if v == int(v) else str(round(v,1))
    except Exception: return str(v)

async def show_cfg():
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    txt = head("⚙️","تنظیمات")
    rows = []
    for key, label, unit, step, lo, hi in CFG_FIELDS:
        v = cfg.get(key, DEFAULT_CFG[key])
        v_str = _fmt_num(v) + unit
        txt += f"{label}: <b>{esc(v_str)}</b>\n"
        rows.append([B("➖", f"cfg:adj:{key}:-1"), B(v_str, "noop"), B("➕", f"cfg:adj:{key}:1")])
    txt += f"\n⏸ محدودیت: <b>{RATE_LIMIT_WAIT//60} دقیقه</b>"
    txt += f"\n💾 DATA_DIR: <code>{esc(DATA_DIR)}</code>"
    txt += f"\n🔖 نسخه: <b>{VERSION}</b>"
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
    _save(CFG_FILE, cfg)
    await show_cfg()


async def show_help():
    txt = (head("❓","راهنما") +
           f"🔖 نسخه: <b>{VERSION}</b>\n\n"
           "📤 ارسال — پیام به گروه‌ها و PV\n"
           "🤝 Joiner — جوین در لینکدونی‌ها و استخراج لینک\n"
           "📊 آمار — جزئیات زنده\n"
           "⚠️ خطاها — ۱۰۰ خطای اخیر\n"
           f"💾 همه فایل‌ها در <code>{esc(DATA_DIR)}</code>\n\n"
           "🔐 session: auth تو <code>accounts.json</code> نگه داشته می‌شه، بدون فایل .rp.\n"
           "⏸ محدودیت: ۲۰ دقیقه توقف خودکار.")
    await panel(txt, kb_([B("🏠 منو","menu:main")]))


def _jl_conv(cid):
    c = get_conv(cid)
    if "jl" not in c: c["jl"] = {"step":"account","accounts":[],"max_join":0}
    return c["jl"]

async def show_jl_step(cid):
    s = _jl_conv(cid)
    if s["step"] == "account": return await jl_step_account(cid, s)
    if s["step"] == "max":     return await jl_step_max(cid, s)
    if s["step"] == "confirm": return await jl_step_confirm(cid, s)

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
    txt = (head("🤝","Joiner") + "کدوم اکانت(ها)؟\n\n" +
           f"🎯 لینکدونی‌ها: <code>{esc(', '.join(JOIN_DEFAULTS))}</code>")
    await panel(txt, kb_(*rows))

async def jl_step_max(cid, s):
    mx = s.get("max_join",0)
    rows = []
    row = []
    for n in [50, 100, 200]:
        row.append(B(("✅ " if mx==n else "")+f"{n}", f"jl:max:{n}"))
    rows.append(row)
    row = []
    for n in [500, 1000, 2000]:
        row.append(B(("✅ " if mx==n else "")+f"{n}", f"jl:max:{n}"))
    rows.append(row)
    rows.append([B(("✅ " if mx==0 else "")+"♾ بدون محدودیت", "jl:max:0")])
    rows.append([B("✏️ عدد دلخواه", "jl:max:custom")])
    rows.append([B("▶️ مرحله بعد", "jl:next")])
    rows.append([B("⬅️", "jl:back")])
    txt = (head("🤝","Joiner — حداکثر") +
           f"حداکثر چند لینک؟\n\n🎯 فعلاً: <b>{'بدون محدودیت' if mx==0 else mx}</b>")
    await panel(txt, kb_(*rows))

async def jl_step_confirm(cid, s):
    accounts = list_accounts()
    sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "account"
        return await panel("⚠️ اکانت انتخاب نشده.", kb_([B("🏠 منو","menu:main")]))
    txt = head("🤝","تایید Joiner")
    txt += f"👤 اکانت: <b>{len(sel)}</b>\n"
    txt += f"🎯 لینکدونی: <b>{len(JOIN_DEFAULTS)}</b>\n"
    txt += f"🔢 حداکثر جوین: <b>{'بدون محدودیت' if not s.get('max_join') else s['max_join']}</b>\n\nشروع کنم؟"
    await panel(txt, kb_(
        [B("✅ شروع", "jl:go")],
        [B("✏️ ویرایش", "jl:back")],
        [B("❌ لغو", "jl:cancel")]))


async def cmd_start(update, context):
    cid = update.effective_chat.id
    if STATE["owner"] is None:
        STATE["owner"] = cid; save_owner(cid)
        await update.message.reply_text(f"🔒 ربات از حالا برای شماست.\n🔖 {VERSION}\n💾 {DATA_DIR}")
    elif STATE["owner"] != cid:
        await update.message.reply_text("⛔"); return
    STATE["panel"].pop(cid, None)
    await show_main()

async def cmd_menu(update, context):
    if not authorized(update): return
    STATE["panel"].pop(update.effective_chat.id, None)
    clear_conv(update.effective_chat.id)
    await show_main()

async def cmd_version(update, context):
    if not authorized(update): return
    accounts = list_accounts()
    txt = f"🔖 <b>{VERSION}</b>\n💾 <code>{DATA_DIR}</code>\n📱 اکانت‌ها: {len(accounts)}"
    if accounts:
        txt += "\n\n"
        for aid, a in accounts.items():
            has_rp = os.path.exists(a.get("session_name","") + ".rp")
            txt += f"• {a.get('name','?')} — .rp: {'❌' if not has_rp else '✅'}\n"
    await update.message.reply_text(txt, parse_mode="HTML")


PROF_PROMPT = {"name":"👤 اسم جدید:","bio":"📖 بیو جدید:",
               "user":"🔤 یوزرنیم جدید:","photo":"🖼 عکس جدید:"}
CHAN_PROMPT = {"title":"✏️ اسم جدید:","desc":"📖 توضیح جدید:",
               "user":"🔗 یوزرنیم کانال:","photo":"🖼 عکس جدید:"}


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
    p = data.split(":")
    h = p[0]
    if data == "conv:cancel": clear_conv(cid); return await show_main()
    if data == "menu:main":
        stop_op_view(cid); clear_conv(cid); return await show_main()
    if data == "menu:acc": stop_op_view(cid); return await show_accounts()
    if data == "menu:stats": stop_op_view(cid); return await show_stats()
    if data == "menu:errors": return await show_errors()
    if data == "menu:cfg": return await show_cfg()
    if data == "menu:help": return await show_help()

    if h == "err":
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_errors(int(p[2]))
        if sub == "clear":
            clear_errors(); await tg_send("🗑 خطاها پاک شد")
            return await show_errors()

    if h == "send":
        s = _send_conv(cid)
        sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            s["step"] = "accounts"; s["accounts"] = s.get("accounts") or []
            return await show_send_step(cid)
        if sub == "jl":
            c = get_conv(cid); c["jl"] = {"step":"account","accounts":[],"max_join":0}
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
                return await ask("🔢 عدد حداکثر (0 = بدون محدودیت):")
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
            if not targets: return await panel("⚠️ چیزی برای ارسال نیست.", kb_([B("🏠 منو","menu:main")]))
            op = {"id": "op_" + secrets.token_hex(5), "created": int(time.time()),
                  "scheduled_at": int(time.time()) + s.get("schedule",0),
                  "payload": payload, "target": s.get("target","both"),
                  "max": s.get("max",0) or 0, "accounts": sel,
                  "status": "draft", "task_ids": [], "_targets": targets}
            if s.get("schedule",0) > 0:
                op["status"] = "scheduled"; _save_op(op); clear_conv(cid)
                await panel(head("⏰","زمان‌بندی شد") +
                            f"📦 تعداد: <b>{len(targets)}</b>",
                            kb_([B("📊 مشاهده","menu:stats")],[B("🏠 منو","menu:main")]))
            else:
                n = await op_start_now(op); clear_conv(cid)
                await panel(head("🚀","ارسال شروع شد") + f"📦 تعداد: <b>{n}</b>",
                            kb_([B("📊 آمار","menu:stats")],
                                [B("⏹ توقف","op:stop:"+op["id"])],
                                [B("🏠 منو","menu:main")]))
                if not (STATE["job"] and not STATE["job"].done()):
                    cfg = _load(CFG_FILE, DEFAULT_CFG)
                    async def _job():
                        try: await run_workers(cfg, log_cb)
                        except Exception as e: await tg_send(f"❌ {type(e).__name__}")
                        finally: STATE["cancel"] = None
                    STATE["job"] = asyncio.create_task(_job())
            return

    if h == "op":
        sub = p[1] if len(p) > 1 else ""
        oid = p[2] if len(p) > 2 else None
        if sub == "view" and oid: start_op_view(cid, oid); return await show_op_detail(oid)
        if sub == "stop" and oid:
            op = _get_op(oid)
            if op:
                if op.get("type") == "joinlef":
                    t = JL_JOBS.get(oid)
                    if t and not t.done(): t.cancel()
                    op["status"] = "cancelled"; op["finished_at"] = int(time.time())
                    _save_op(op); await tg_send("⛔ Joiner لغو شد")
                else:
                    op["status"] = "paused"
                    q = TaskQueue(QUEUE_FILE)
                    for t in q.tasks:
                        if t.get("op_id") == oid and t["status"] in ("pending","in_progress"):
                            t["status"] = "paused"
                    q._save(); _save_op(op); await tg_send("⏸ توقف داده شد")
            return await show_op_detail(oid)
        if sub == "resume" and oid:
            op = _get_op(oid)
            if op and op.get("type") != "joinlef":
                op["status"] = "queued"
                q = TaskQueue(QUEUE_FILE)
                for t in q.tasks:
                    if t.get("op_id") == oid and t["status"] == "paused":
                        t["status"] = "pending"; t["assigned_to"] = None
                q._save(); _save_op(op)
                if not (STATE["job"] and not STATE["job"].done()):
                    cfg = _load(CFG_FILE, DEFAULT_CFG)
                    async def _job():
                        try: await run_workers(cfg, log_cb)
                        except Exception as e: await tg_send(f"❌ {type(e).__name__}")
                        finally: STATE["cancel"] = None
                    STATE["job"] = asyncio.create_task(_job())
                await tg_send("▶️ از سرگیری")
            return await show_op_detail(oid)
        if sub == "force" and oid:
            await op_activate_scheduled(oid); await tg_send("⚡️ شروع شد")
            return await show_op_detail(oid)
        if sub == "cancel" and oid:
            op = _get_op(oid)
            if op: op["status"] = "cancelled"; op.pop("_targets", None); _save_op(op); await tg_send("⛔ لغو شد")
            return await show_op_detail(oid)
        if sub == "repeat" and oid:
            op = _get_op(oid)
            if not op: return await show_stats()
            s = _send_conv(cid)
            s["step"] = "accounts"; s["accounts"] = op.get("accounts") or []
            s["payload"] = op.get("payload"); s["target"] = op.get("target","both")
            s["max"] = op.get("max",0); s["schedule"] = 0
            return await show_send_step(cid)

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
            remove_account(p[2]); await tg_send("🗑 حذف شد")
            return await show_accounts()
        if sub == "relogin":
            aid = p[2]; a = get_account(aid)
            if not a: return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
            await panel(f"⏳ ارسال کد به {esc(a.get('phone','?'))}...")
            try: ctx = await rubika_send_code(a["phone"])
            except Exception as e:
                return await panel(f"❌ {esc(str(e)[:200])}", kb_([B("⬅️", f"acc:view:{aid}")]))
            if ctx.get("status") == "SendPassKey":
                get_conv(cid)["acc"] = {"step":"passkey","ctx":ctx,"relogin":aid}
                return await ask(f"🔐 2FA\n{esc(ctx.get('hint') or '—')}")
            get_conv(cid)["acc"] = {"step":"code","ctx":ctx,"relogin":aid}
            return await ask("📩 کد:")

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
            if not a or idx >= len(chans): return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
            await panel("⏳ در حال ساخت لینک...")
            try: ok, link = await with_bot(a, lambda b: rubika_create_join_link(b, chans[idx]["guid"]), aid=aid)
            except Exception as e: ok, link = False, _fmt_error(e)
            if ok: update_channel_field(aid, idx, "join_link", link)
            return await panel((f"✅ لینک:\n<code>{esc(link)}</code>" if ok
                                else f"⚠️ {esc(str(link)[:200])}"),
                               kb_([B("⬅️", f"chan:view:{aid}:{idx}")]))
        if sub == "del":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans): return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
            return await panel(f"🗑 حذف کانال <b>{esc(chans[idx].get('title','?'))}</b>؟",
                               kb_([B("✅ بله", f"chan:delok:{aid}:{idx}")],
                                   [B("❌ انصراف", f"chan:view:{aid}:{idx}")]))
        if sub == "delok":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans): return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
            await panel("⏳ در حال حذف...")
            try: ok, info = await with_bot(a, lambda b: rubika_remove_channel(b, chans[idx]["guid"]), aid=aid)
            except Exception as e: ok, info = False, _fmt_error(e)
            if ok: remove_channel_from_storage(aid, idx)
            return await panel(("✅ حذف شد" if ok else f"⚠️ {esc(str(info)[:200])}"),
                               kb_([B("⬅️", f"chan:list:{aid}")]))

    if h == "jl":
        c = get_conv(cid)
        s = c.get("jl") or {"step":"account","accounts":[],"max_join":0}
        c["jl"] = s
        sub = p[1] if len(p) > 1 else ""
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await jl_step_account(cid, s)
        if sub == "next":
            if s["step"] == "account": s["step"] = "max"; return await jl_step_max(cid, s)
            elif s["step"] == "max": s["step"] = "confirm"; return await jl_step_confirm(cid, s)
        if sub == "back":
            if s["step"] == "max": s["step"] = "account"
            elif s["step"] == "confirm": s["step"] = "max"
            return await show_jl_step(cid)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["jl_wait"] = "max"
                return await ask("🔢 عدد حداکثر (0 = بدون محدودیت):")
            try: s["max_join"] = int(v)
            except: pass
            return await jl_step_max(cid, s)
        if sub == "cancel": c.pop("jl", None); return await show_main()
        if sub == "go":
            op = {"id": "jl_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "joinlef", "accounts": s.get("accounts") or [],
                  "max_join": s.get("max_join",0) or 0, "status": "running",
                  "progress": {"joined":0,"failed":0,"total":0,"phase":"شروع",
                               "linkdoni_ok":[], "linkdoni_fail":[], "link_errors":[]},
                  "errors": []}
            _save_op(op); c.pop("jl", None)
            task = asyncio.create_task(run_joiner_lefter(op, log_cb))
            JL_JOBS[op["id"]] = task
            start_op_view(cid, op["id"])
            return await show_op_detail(op["id"])

    if h == "cfg" and p[1] == "adj":
        return await adjust_cfg(p[2], int(p[3]))


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


async def on_message(update, context):
    if not authorized(update): return
    msg = update.message
    if msg is None: return
    cid = update.effective_chat.id
    conv = STATE["conv"].get(cid) or {}
    text = (msg.text or "").strip()

    if "jl_wait" in conv:
        wait = conv.pop("jl_wait")
        jl = get_conv(cid).get("jl") or {}
        if wait == "max":
            try: v = int(text); jl["max_join"] = max(0, v)
            except Exception: return await ask("🔢 عدد نامعتبر. دوباره:")
            get_conv(cid)["jl"] = jl
            return await jl_step_max(cid, jl)

    if "send_wait" in conv:
        wait = conv.pop("send_wait")
        s = _send_conv(cid)
        if wait == "max":
            try: s["max"] = max(0, int(text))
            except Exception: return await ask("🔢 عدد نامعتبر. دوباره:")
            return await show_send_step(cid)
        if wait == "sch":
            try: s["schedule"] = max(0, int(text)*60)
            except Exception: return await ask("⏰ عدد نامعتبر. دوباره:")
            return await show_send_step(cid)

    if "send" in conv:
        s = conv["send"]
        if s.get("step") == "compose":
            STATE["panel"].pop(cid, None)
            try: media = await extract_tg_media(msg)
            except Exception as e: return await ask("✉️ پیام را دوباره بفرست:", note=str(e)[:150])
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
            if not ph.isdigit() or len(ph) < 10: return await ask("📞 شماره نامعتبر. دوباره:")
            await panel("⏳ ارسال کد...")
            try: ctx = await rubika_send_code(ph)
            except Exception as e:
                STATE["conv"].pop(cid, None)
                return await panel(f"❌ {esc(str(e)[:200])}", kb_([B("🏠 منو","menu:main")]))
            if ctx.get("status") == "SendPassKey":
                a["step"] = "passkey"; a["ctx"] = ctx
                return await ask(f"🔐 2FA\n{esc(ctx.get('hint') or '—')}")
            a["step"] = "code"; a["ctx"] = ctx
            return await ask("📩 کد:")
        if step == "passkey":
            ctx = a.get("ctx") or {}
            try:
                res = await ctx["client"].send_code(phone_number=ctx["phone"], pass_key=text)
                if getattr(res, "status", None) == "OK":
                    ctx["phone_code_hash"] = res.phone_code_hash
                    a["step"] = "code"
                    return await ask("📩 کد:")
                return await ask("🔐 رمز اشتباه. دوباره:")
            except Exception as e:
                return await ask("🔐 خطا. دوباره:", note=_fmt_error(e)[:150])
        if step == "code":
            ctx = a.get("ctx") or {}
            is_relogin = a.get("relogin")
            await panel("⏳ در حال ورود...")
            try: res = await rubika_complete_login(ctx, text)
            except Exception as e:
                return await ask("📩 خطا. دوباره:", note=_fmt_error(e)[:150])
            STATE["conv"].pop(cid, None)
            if not res.get("ok"):
                return await panel("❌ ورود ناموفق.", kb_([B("🏠 منو","menu:main")]))
            await panel(f"✅ ورود موفق\n🔖 {VERSION}",
                        kb_([B("⬅️ اکانت‌ها", "menu:acc")]))
            if is_relogin: return await show_account_detail(res["aid"])
            return await show_accounts()

    if "prof" in conv:
        pr = conv["prof"]; field = pr.get("field"); aid = pr.get("aid")
        STATE["panel"].pop(cid, None)
        a = get_account(aid)
        if not a: STATE["conv"].pop(cid, None); return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
        media = None
        if field == "photo":
            try: media = await extract_tg_media(msg)
            except Exception as e: return await ask(PROF_PROMPT["photo"], note=str(e)[:150])
            if not media: return await ask(PROF_PROMPT["photo"], note="فقط عکس:")
        elif not text:
            return await ask(PROF_PROMPT.get(field,"مقدار:"), note="متن لازمه")
        STATE["conv"].pop(cid, None)
        await panel("⏳ در حال اعمال...")
        async def job(bot):
            me = await bot.get_me(); my = me.user.user_guid
            if field == "name": return await rubika_set_name(bot, text)
            if field == "bio": return await rubika_set_bio(bot, text)
            if field == "user": return await rubika_set_username(bot, text)
            if field == "photo": return await rubika_set_photo(bot, my, media["file"])
            return False, "?"
        try: ok, info = await with_bot(a, job, aid=aid)
        except Exception as e: ok, info = False, _fmt_error(e)
        if media:
            try: os.remove(media["file"])
            except Exception: pass
        return await panel(("✅ انجام شد" if ok else f"⚠️ {esc(str(info)[:200])}"),
                           kb_([B("⬅️", f"prof:menu:{aid}")]))

    if "chan" in conv:
        ch = conv["chan"]; step = ch.get("step")
        STATE["panel"].pop(cid, None)
        if step == "title":
            aid = ch.get("aid"); public = ch.get("public", True)
            STATE["conv"].pop(cid, None)
            if not text: return await show_main()
            a = get_account(aid)
            if not a: return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
            await panel(f"⏳ ساخت «{esc(text[:60])}»...")
            async def job(bot):
                ok, info, guid = await rubika_create_channel(bot, text[:60], "")
                link = None
                if ok and not public:
                    await asyncio.sleep(1)
                    ok2, l = await rubika_create_join_link(bot, guid)
                    link = l if ok2 else None
                return ok, info, guid, link
            try: ok, info, guid, link = await with_bot(a, job, 120, aid=aid)
            except Exception as e:
                return await panel(f"❌ {esc(type(e).__name__)}: {esc(str(e)[:200])}",
                                   kb_([B("⬅️", f"acc:view:{aid}")]))
            if not ok:
                return await panel(f"⚠️ {esc(str(info)[:300])}",
                                   kb_([B("⬅️", f"acc:view:{aid}")]))
            add_channel_to_storage(aid, {"title": text[:60], "description": "",
                "guid": guid, "username": None, "is_public": public,
                "join_link": link, "created": int(time.time())})
            idx = len(get_account(aid).get("channels",[])) - 1
            txt = head("✅", text[:60]) + f"🆔 <code>{esc(guid)}</code>"
            if not public: txt += f"\n🔗 {esc(link)}" if link else "\n⚠️ لینک ساخته نشد"
            return await panel(txt, kb_([B("⚙️ مدیریت", f"chan:view:{aid}:{idx}")],
                                         [B("⬅️", f"chan:list:{aid}")]))
        if step == "edit":
            aid = ch.get("aid"); idx = ch.get("idx"); field = ch.get("field")
            STATE["conv"].pop(cid, None)
            a = get_account(aid); chans = (a or {}).get("channels",[])
            if not a or idx >= len(chans): return await panel("⚠️ پیدا نشد.", kb_([B("🏠 منو","menu:main")]))
            media = None
            if field == "photo":
                try: media = await extract_tg_media(msg)
                except Exception as e: return await ask(CHAN_PROMPT["photo"], note=str(e)[:150])
                if not media: return await ask(CHAN_PROMPT["photo"], note="فقط عکس:")
            elif not text:
                return await ask(CHAN_PROMPT.get(field,"مقدار:"), note="متن لازمه")
            await panel("⏳ در حال اعمال...")
            guid = chans[idx].get("guid")
            async def job(bot):
                if field == "title": return await rubika_set_chat_title(bot, guid, text)
                if field == "desc": return await rubika_set_chat_description(bot, guid, text)
                if field == "user": return await rubika_set_chat_username(bot, guid, text)
                if field == "photo": return await rubika_set_chat_photo(bot, guid, media["file"])
                return False, "?"
            try: ok, info = await with_bot(a, job, aid=aid)
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


async def _post_init(app):
    try:
        from telegram import BotCommand
        await app.bot.set_my_commands([BotCommand("start","شروع"),
                                       BotCommand("menu","منوی اصلی"),
                                       BotCommand("version","نسخه")])
    except Exception: pass

async def _on_error(update, context):
    print(f"[!] {type(context.error).__name__}: {context.error}")

def main():
    global APP
    if not TG_TOKEN:
        print("[x] TG_TOKEN نیست."); sys.exit(1)
    STATE["owner"] = load_owner()
    print(f"[+] VERSION: {VERSION}")
    print(f"[+] DATA_DIR: {DATA_DIR}")
    print(f"[+] owner: {STATE['owner']}" if STATE["owner"] else "[i] اولین /start مالک")

    _loop_ref[0] = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop_ref[0])

    req = HTTPXRequest(connection_pool_size=8, connect_timeout=30.0,
                       read_timeout=30.0, write_timeout=30.0, pool_timeout=30.0)
    APP = (Application.builder().token(TG_TOKEN).request(req)
           .get_updates_request(req).post_init(_post_init).build())
    APP.add_handler(CommandHandler("start", cmd_start))
    APP.add_handler(CommandHandler("menu", cmd_menu))
    APP.add_handler(CommandHandler("version", cmd_version))
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