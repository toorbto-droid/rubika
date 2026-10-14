# rubika_tg_bot.py — v102 (English SMS-style UI · plain buttons · no emoji in labels)
# Railway-ready · no self-start · token from app.py
# ═══════════════════════════════════════════════════════════════════

import os, sys, ssl, json, socket, asyncio, time, glob, re, threading, secrets, queue
import logging, traceback, concurrent.futures, inspect, random
import html as _html, builtins, hashlib
from typing import Optional, Dict, Any, List, Set, Tuple

VERSION = "Rubika v102"

# ═══════════════ STYLE ═══════════════
_SC = str.maketrans({
    'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ꜰ','g':'ɢ','h':'ʜ','i':'ɪ',
    'j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ','q':'ǫ','r':'ʀ',
    's':'ꜱ','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x','y':'ʏ','z':'ᴢ',
    'A':'ᴀ','B':'ʙ','C':'ᴄ','D':'ᴅ','E':'ᴇ','F':'ꜰ','G':'ɢ','H':'ʜ','I':'ɪ',
    'J':'ᴊ','K':'ᴋ','L':'ʟ','M':'ᴍ','N':'ɴ','O':'ᴏ','P':'ᴘ','Q':'ǫ','R':'ʀ',
    'S':'ꜱ','T':'ᴛ','U':'ᴜ','V':'ᴠ','W':'ᴡ','X':'x','Y':'ʏ','Z':'ᴢ',
})
def SC(s): return str(s).translate(_SC)
def HLINE(): return "━━━━━━━━━━━━━━━━━━━━━━"
TICK = "⤳"

# ═══════════════ DATA DIR ═══════════════
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
RB_DIR = os.path.join(DATA_DIR, "rubika")
os.makedirs(RB_DIR, exist_ok=True)
SESSIONS_DIR = os.path.join(RB_DIR, "sessions")
MEDIA_DIR = os.path.join(RB_DIR, "media")
UPLOADS_DIR = os.path.join(RB_DIR, "uploads")
for _d in (SESSIONS_DIR, MEDIA_DIR, UPLOADS_DIR):
    try: os.makedirs(_d, exist_ok=True)
    except Exception: pass
LOG_FILE = os.path.join(RB_DIR, "rubika.log")

print(f"[+] VERSION: {VERSION}")
print(f"[+] DATA_DIR: {DATA_DIR}")

# ═══════════════ signal patch ═══════════════
try:
    import asyncio.unix_events as _ue
    _orig_add_signal = _ue._UnixSelectorEventLoop.add_signal_handler
    def _safe_add_signal(self, sig, callback, *args):
        try: return _orig_add_signal(self, sig, callback, *args)
        except (RuntimeError, ValueError, NotImplementedError, AttributeError): return None
    _ue._UnixSelectorEventLoop.add_signal_handler = _safe_add_signal
except Exception: pass

# ═══════════════ logging ═══════════════
logging.basicConfig(level=logging.CRITICAL, stream=open(os.devnull, "w"))
for _n in ("urllib3","urllib3.connectionpool","requests","httpx","httpcore",
           "telegram.ext.Updater","telegram.request","rubpy","asyncio"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)
    logging.getLogger(_n).propagate = False
_flog = logging.getLogger("rubika"); _flog.setLevel(logging.DEBUG); _flog.propagate = False
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    _flog.addHandler(_fh)
except Exception: pass
def flog(msg, level="info"):
    try: print(f"[rubika] {msg}", flush=True)
    except Exception: pass
    try: getattr(_flog, level)(msg)
    except Exception: pass

# ═══════════════ certifi / DoH ═══════════════
try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["SSL_CERT_DIR"] = ""
except Exception: pass
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
    for u in ("https://1.1.1.1/dns-query", "https://8.8.8.8/resolve"):
        try:
            r = SESSION_REQ.get(u, params={"name": h, "type": "A"},
                headers={"accept": "application/dns-json"}, timeout=5)
            ips = [a["data"] for a in r.json().get("Answer", []) if a.get("type") == 1]
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
try:
    import rulog.GtM as GtM
    GtM.list_servers.clear(); GtM.list_servers.extend(DC)
    if len(GtM.list_servers) > 1: GtM.list_servers.pop(1)
    GtM.Server_Rubika = lambda: None
    if DC:
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
            list(ex.map(_doh, [s.get("ip") if isinstance(s, dict) else str(s) for s in DC[:60]]))
except Exception: pass
from rubpy import Client as _C

# ═══════════════ generic helpers ═══════════════
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
def _fmt_error(e):
    if e is None: return "—"
    if isinstance(e, dict):
        parts = []
        for k in ("status", "status_det"):
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
def _is_auth_dead(ex): return "AUTH_DEAD" in str(ex) or "NO_SESSION" in str(ex)
def _is_transient(ex): return "TRANSIENT" in str(ex)
def _is_rate_limit(ex):
    s = str(ex).upper()
    return any(k in s for k in ("TOO_REQUESTS","RATE_LIMIT","FLOOD","TOO_MANY",
                                 "استفاده بیش از حد","بیش از حد مجاز"))
def _is_ok_response(r):
    if r is None: return True
    d = _to_dict(r)
    if not isinstance(d, dict): return True
    for k in ("status", "status_det"):
        s = str(d.get(k) or "").upper()
        if s and ("ERROR" in s or "INVALID" in s or "FAIL" in s or "NOT_" in s): return False
    nested = d.get("data") or d.get("result")
    if isinstance(nested, dict): return _is_ok_response(nested)
    return True
def _load(path, default):
    if not os.path.exists(path):
        return dict(default) if isinstance(default, dict) else default
    try:
        with open(path, encoding="utf-8") as f: d = json.load(f)
        if isinstance(default, dict) and isinstance(d, dict): return {**default, **d}
        return d
    except Exception:
        return dict(default) if isinstance(default, dict) else default
def _save(path, data):
    try: os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    except Exception: pass
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(path + ".tmp", path)
    except Exception as e: flog(f"[save] {path}: {e}", "error")
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
    return False, None, " | ".join(errors[:4]) or "no method worked"

# ═══════════════ file paths ═══════════════
ACC_FILE        = os.path.join(RB_DIR, "accounts.json")
CFG_FILE        = os.path.join(RB_DIR, "config.json")
ERRORS_FILE     = os.path.join(RB_DIR, "errors.json")
OPS_FILE        = os.path.join(RB_DIR, "ops.json")
TEMPLATES_FILE  = os.path.join(RB_DIR, "templates.json")
SEEN_FILE       = os.path.join(RB_DIR, "seen_links.json")
BANNED_FILE     = os.path.join(RB_DIR, "banned_groups.json")
LDPROG_FILE     = os.path.join(RB_DIR, "linkdoni_progress.json")
LINK_DONIES_FILE= os.path.join(RB_DIR, "linkdonies.json")
PV_ITEMS_FILE   = os.path.join(RB_DIR, "pv_items.json")
PV_ACCOUNT_FILE = os.path.join(RB_DIR, "pv_per_account.json")
PV_REPORT_FILE  = os.path.join(RB_DIR, "pv_report.json")
PV_COUNTS_FILE  = os.path.join(RB_DIR, "pv_counts.json")
PV_WM_FILE      = os.path.join(RB_DIR, "pv_wm.json")

_SEEN_CACHE: Dict[str, Set[str]] = {}
_BANNED_CACHE: Dict[str, Dict[str, Any]] = {}
_LDPROG_CACHE: Dict[str, Dict[str, int]] = {}
_PV_WM: Optional[Dict[str, Dict[str, int]]] = None
_PV_WM_DIRTY = False

def _load_seen(aid):
    if not aid: return set()
    if aid in _SEEN_CACHE: return _SEEN_CACHE[aid]
    all_d = _load(SEEN_FILE, {})
    if not isinstance(all_d, dict): all_d = {}
    acc = all_d.get(aid) or {}
    _SEEN_CACHE[aid] = set(acc.keys()); return _SEEN_CACHE[aid]
def _mark_seen(aid, h):
    if not aid or not h: return
    seen = _load_seen(aid)
    if h in seen: return
    seen.add(h)
    try:
        all_d = _load(SEEN_FILE, {})
        if not isinstance(all_d, dict): all_d = {}
        acc = all_d.setdefault(aid, {}); acc[h] = 1
        if len(acc) > 50000:
            all_d[aid] = dict(list(acc.items())[-40000:])
            _SEEN_CACHE[aid] = set(all_d[aid].keys())
        _save(SEEN_FILE, all_d)
    except Exception: pass
def _is_seen(aid, h): return bool(aid and h and h in _load_seen(aid))
def _clear_seen(aid=None):
    if aid:
        _SEEN_CACHE.pop(aid, None)
        try:
            all_d = _load(SEEN_FILE, {})
            if isinstance(all_d, dict): all_d.pop(aid, None); _save(SEEN_FILE, all_d)
        except Exception: pass
    else:
        _SEEN_CACHE.clear()
        try: _save(SEEN_FILE, {})
        except Exception: pass
def _seen_count(aid): return len(_load_seen(aid))

def _load_banned(aid):
    if not aid: return {}
    if aid in _BANNED_CACHE: return _BANNED_CACHE[aid]
    all_d = _load(BANNED_FILE, {})
    if not isinstance(all_d, dict): all_d = {}
    acc = all_d.get(aid) or {}
    if not isinstance(acc, dict): acc = {}
    _BANNED_CACHE[aid] = acc; return acc
def _mark_banned(aid, h, reason=""):
    if not aid or not h: return
    try:
        all_d = _load(BANNED_FILE, {})
        if not isinstance(all_d, dict): all_d = {}
        acc = all_d.setdefault(aid, {})
        acc[h] = {"reason": str(reason)[:120], "ts": int(time.time())}
        _BANNED_CACHE[aid] = acc; _save(BANNED_FILE, all_d)
    except Exception: pass
def _is_banned(aid, h): return bool(aid and h and h in _load_banned(aid))
def _clear_banned(aid=None):
    if aid:
        _BANNED_CACHE.pop(aid, None)
        try:
            all_d = _load(BANNED_FILE, {})
            if isinstance(all_d, dict): all_d.pop(aid, None); _save(BANNED_FILE, all_d)
        except Exception: pass
    else:
        _BANNED_CACHE.clear()
        try: _save(BANNED_FILE, {})
        except Exception: pass
def _banned_count(aid): return len(_load_banned(aid))

def _load_ldprog(aid):
    if not aid: return {}
    if aid in _LDPROG_CACHE: return _LDPROG_CACHE[aid]
    all_d = _load(LDPROG_FILE, {})
    if not isinstance(all_d, dict): all_d = {}
    acc = all_d.get(aid) or {}
    if not isinstance(acc, dict): acc = {}
    _LDPROG_CACHE[aid] = acc; return acc
def _set_ld_last(aid, url, max_id):
    if not aid or not url: return
    try:
        all_d = _load(LDPROG_FILE, {})
        if not isinstance(all_d, dict): all_d = {}
        acc = all_d.setdefault(aid, {})
        old = int(acc.get(url, 0))
        if int(max_id) > old:
            acc[url] = int(max_id); _LDPROG_CACHE[aid] = acc; _save(LDPROG_FILE, all_d)
    except Exception: pass
def _reset_ld_progress(aid=None):
    if aid:
        _LDPROG_CACHE.pop(aid, None)
        try:
            all_d = _load(LDPROG_FILE, {})
            if isinstance(all_d, dict): all_d.pop(aid, None); _save(LDPROG_FILE, all_d)
        except Exception: pass
    else:
        _LDPROG_CACHE.clear()
        try: _save(LDPROG_FILE, {})
        except Exception: pass

def _pv_count(aid, uid):
    d = _load(PV_COUNTS_FILE, {}); return int((d.get(aid) or {}).get(str(uid), 0))
def _pv_count_add(aid, uid, delta):
    d = _load(PV_COUNTS_FILE, {}); acc = d.setdefault(aid, {})
    acc[str(uid)] = max(0, int(acc.get(str(uid), 0)) + delta); _save(PV_COUNTS_FILE, d)
def _pv_limit_reached(aid, uid, cfg):
    mx = int(cfg.get("max_replies", 1) or 0)
    return mx > 0 and _pv_count(aid, uid) >= mx
def _wm_load():
    global _PV_WM
    if _PV_WM is None:
        d = _load(PV_WM_FILE, {}); _PV_WM = d if isinstance(d, dict) else {}
    return _PV_WM
def _wm_get(aid, uid):
    try: return int((_wm_load().get(aid) or {}).get(str(uid), 0))
    except Exception: return 0
def _wm_set(aid, uid, mid):
    global _PV_WM_DIRTY
    w = _wm_load().setdefault(aid, {})
    if int(mid) > int(w.get(str(uid), 0)):
        w[str(uid)] = int(mid); _PV_WM_DIRTY = True
def _wm_flush():
    global _PV_WM_DIRTY
    if _PV_WM_DIRTY:
        try: _save(PV_WM_FILE, _wm_load())
        except Exception: pass
        _PV_WM_DIRTY = False

DEFAULT_PV_ITEMS = {
    "enabled": False, "delay_seconds": 0, "reply_once": True, "max_replies": 1,
    "notify": True, "notify_on_receive": True, "notify_on_reply": True,
    "poll_seconds": 5, "items": [{"kind": "text", "text": "hello 👋"}]
}
def _load_pv_items():
    d = _load(PV_ITEMS_FILE, DEFAULT_PV_ITEMS)
    if not isinstance(d, dict): return dict(DEFAULT_PV_ITEMS)
    for k, v in DEFAULT_PV_ITEMS.items():
        if k not in d: d[k] = v
    return d
def _load_pv_account(aid):
    base = _load_pv_items()
    if not aid: return base
    per = _load(PV_ACCOUNT_FILE, {})
    if not isinstance(per, dict): per = {}
    acc_cfg = per.get(aid) or {}
    if not isinstance(acc_cfg, dict): acc_cfg = {}
    merged = {**base, **acc_cfg}
    if not isinstance(merged.get("items"), list) or not merged.get("items"):
        merged["items"] = base.get("items") or []
    return merged
def _save_pv_account(aid, cfg):
    if not aid: return
    per = _load(PV_ACCOUNT_FILE, {})
    if not isinstance(per, dict): per = {}
    per[aid] = {k: cfg.get(k) for k in ("enabled","delay_seconds","reply_once",
        "max_replies","notify","notify_on_receive","notify_on_reply","poll_seconds","items")}
    _save(PV_ACCOUNT_FILE, per)
def _has_pv_account(aid):
    per = _load(PV_ACCOUNT_FILE, {})
    return isinstance(per, dict) and aid in per
def _delete_pv_account(aid):
    per = _load(PV_ACCOUNT_FILE, {})
    if isinstance(per, dict): per.pop(aid, None); _save(PV_ACCOUNT_FILE, per)
def _load_pv_report():
    d = _load(PV_REPORT_FILE, {}); return d if isinstance(d, dict) else {}
def _save_pv_report(d): _save(PV_REPORT_FILE, d)
def _record_pv_visit(aid, uid, info=None):
    rep = _load_pv_report(); acc = rep.setdefault(aid, {})
    uid = str(uid); now = int(time.time())
    if uid in acc:
        acc[uid]["last_seen"] = now
        acc[uid]["count"] = acc[uid].get("count", 1) + 1
        if info:
            for k, v in info.items():
                if v is not None: acc[uid][k] = v
    else:
        e = {"first_seen": now, "last_seen": now, "count": 1,
             "replied": False, "reply_ok": False, "error": None, "blocked": False}
        if info: e.update({k: v for k, v in info.items() if v is not None})
        acc[uid] = e
    _save_pv_report(rep)
def _record_pv_reply(aid, uid, ok, err=None):
    rep = _load_pv_report(); acc = rep.setdefault(aid, {}); uid = str(uid)
    if uid not in acc:
        acc[uid] = {"first_seen": int(time.time()), "last_seen": int(time.time()),
                    "count": 1, "replied": False, "reply_ok": False}
    acc[uid]["replied"] = True; acc[uid]["replied_at"] = int(time.time())
    acc[uid]["reply_ok"] = bool(ok)
    if err:
        acc[uid]["error"] = str(err)[:200]
        acc[uid]["blocked"] = "FORBIDDEN" in str(err).upper()
    else: acc[uid]["error"] = None; acc[uid]["blocked"] = False
    _save_pv_report(rep)

DEFAULT_LINK_DONIES = ["@linkdony_rubikas", "@lovo_lovoo0"]
def load_link_donies():
    d = _load(LINK_DONIES_FILE, None)
    if not isinstance(d, list) or not d:
        _save(LINK_DONIES_FILE, DEFAULT_LINK_DONIES); return list(DEFAULT_LINK_DONIES)
    return d
def save_link_donies(lst): _save(LINK_DONIES_FILE, lst)
def add_link_doni(url):
    url = url.strip()
    if not url: return False
    lst = load_link_donies()
    if url in lst: return False
    lst.append(url); save_link_donies(lst); return True
def remove_link_doni(idx):
    lst = load_link_donies()
    if idx < 0 or idx >= len(lst): return False
    lst.pop(idx); save_link_donies(lst); return True

DEFAULT_CFG = {
    "listener": 1, "listener_service_only": 1, "auto_join_linkdoni": 1,
    "wave_size": 50, "extract_limit": 300, "join_delay": 0.5,
    "wait_for_links_sec": 90, "max_wait_rounds": 20,
    "delay": 8.0, "cooldown": 180, "max_parallel": 2,
    "batch_per_account": 2, "max_attempts": 3, "max_channels_per_account": 3,
}

_errors_lock = threading.Lock()
def _load_errors():
    d = _load(ERRORS_FILE, []); return d if isinstance(d, list) else []
def add_error(source, error, target=None, account=None):
    err_up = str(error).upper()
    if "CHANNELPRIVATEERROR" in err_up or "REQUEST WAS UNSUCCESSFUL" in err_up: return
    try:
        with _errors_lock:
            errs = _load_errors()
            errs.append({"time": int(time.time()), "source": str(source)[:40],
                         "error": str(error)[:300],
                         "target": (str(target)[:120] if target is not None else None),
                         "account": (str(account)[:60] if account is not None else None)})
            if len(errs) > 500: errs = errs[-500:]
            _save(ERRORS_FILE, errs)
    except Exception: pass
def clear_errors():
    try:
        with _errors_lock: _save(ERRORS_FILE, [])
    except Exception: pass

def list_accounts(): return _load(ACC_FILE, {})
def save_accounts(a): _save(ACC_FILE, a)
def get_account(aid): return list_accounts().get(aid)
def add_account(aid, phone, name, user_guid):
    accounts = list_accounts(); sess = os.path.join(SESSIONS_DIR, aid)
    accounts[aid] = {"phone": phone, "name": name, "user_guid": user_guid,
                     "session_name": sess, "created": int(time.time()), "channels": []}
    save_accounts(accounts); return sess
def remove_account(aid):
    accounts = list_accounts(); accounts.pop(aid, None); save_accounts(accounts)
    try: _delete_pv_account(aid)
    except Exception: pass
    try: _clear_seen(aid); _clear_banned(aid); _reset_ld_progress(aid)
    except Exception: pass
    for f in glob.glob(os.path.join(SESSIONS_DIR, aid) + "*"):
        try: os.remove(f)
        except Exception: pass
def get_stored_channels(aid):
    a = get_account(aid); return list(a.get("channels") or []) if a else []
def add_channel_to_storage(aid, ch_data):
    accounts = list_accounts()
    if aid not in accounts: return
    chans = accounts[aid].setdefault("channels", [])
    guid = ch_data.get("guid")
    if guid:
        for c in chans:
            if c.get("guid") == guid: c.update(ch_data); save_accounts(accounts); return
    chans.append(ch_data); save_accounts(accounts)
def remove_channel_from_storage(aid, idx):
    accounts = list_accounts()
    if aid not in accounts: return None
    chans = accounts[aid].get("channels") or []
    if idx < 0 or idx >= len(chans): return None
    removed = chans.pop(idx); accounts[aid]["channels"] = chans
    save_accounts(accounts); return removed
def update_channel_field(aid, idx, key, value):
    accounts = list_accounts()
    if aid not in accounts: return
    chans = accounts[aid].get("channels") or []
    if 0 <= idx < len(chans): chans[idx][key] = value; save_accounts(accounts)

# ═══════════════ SafeClient ═══════════════
_ACCOUNT_LOCKS = {}; _ACCOUNT_LOCKS_GUARD = threading.Lock()
def _get_account_lock(aid):
    if not aid: return None
    with _ACCOUNT_LOCKS_GUARD:
        if aid not in _ACCOUNT_LOCKS: _ACCOUNT_LOCKS[aid] = asyncio.Lock()
        return _ACCOUNT_LOCKS[aid]
class SafeClient(_C):
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
            await self.start(); return self
        except Exception:
            if self._lock:
                try: self._lock.release()
                except Exception: pass
            raise
    async def start(self, phone_number=None):
        def _no_prompt(prompt=""): raise RuntimeError("NO_SESSION: session file missing or expired")
        old_input = builtins.input; builtins.input = _no_prompt
        try: await super().start(phone_number=phone_number)
        finally: builtins.input = old_input
        try:
            me = await self.get_me(); self.guid = me.user.user_guid
        except Exception as e: raise RuntimeError(f"NO_SESSION: get_me failed — {e}")
        return self
    async def __aexit__(self, *args, **kwargs):
        try: return await super().__aexit__(*args, **kwargs)
        finally:
            if self._lock:
                try: self._lock.release()
                except Exception: pass

# ═══════════════ Chats ═══════════════
async def get_all_chats_raw(bot):
    try:
        chats = _g(await bot.get_chats(), "chats") or []
        out = []
        for c in chats:
            a = _g(c, "abs_object", "absObject") or c
            guid = _candidate_guid(a) or _candidate_guid(c)
            if not guid: continue
            out.append({"guid": guid,
                        "type": _g(a, "type") or _g(c, "type"),
                        "title": _g(a,"first_name","firstName","title","name",
                                    "display_name","displayName") or
                                 _g(c,"first_name","firstName","title","name") or "",
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
def _is_broadcast_channel(c):
    t = (c.get("type") or "").strip()
    if t != "Channel": return False
    guid = str(c.get("guid") or "")
    return bool(guid and guid[0].lower() == "c")
async def collect_pv(bot, my_guid=None):
    chats = await get_all_chats_raw(bot)
    if my_guid is None:
        try:
            me = await bot.get_me(); my_guid = me.user.user_guid
        except Exception: my_guid = None
    return [{"type": "pv", "target": c["guid"], "name": c["title"] or "friend"}
            for c in chats if c["type"] == "User" and c["guid"] != my_guid and not c["is_blocked"]]
async def collect_groups(bot):
    chats = await get_all_chats_raw(bot)
    return [{"type": "group", "target": c["guid"],
             "name": c["title"] or c["guid"][:15], "raw": c.get("raw")}
            for c in chats if _is_true_group(c)]

async def _call_get_messages(bot, guid, anchor, limit, sort):
    combos = [((guid, str(anchor), str(limit), sort), {}),
              ((guid, anchor, limit, sort), {}),
              ((guid, str(anchor), limit, sort), {}),
              ((guid, anchor, str(limit), sort), {})]
    last_err = None
    fn = getattr(bot, "get_messages", None)
    if not fn: raise RuntimeError("get_messages unavailable")
    for args, kwargs in combos:
        try:
            r = fn(*args, **kwargs)
            if asyncio.iscoroutine(r): r = await r
            return r
        except Exception as e: last_err = e; continue
    raise last_err or RuntimeError("get_messages: no combo")
def normalize_message(m, my_guid=None):
    if m is None: return None
    mid = _g(m,"message_id") or _g(m,"messageId") or _g(m,"id") or ""
    sender = str(_g(m,"sender_id") or _g(m,"author_object_guid") or _g(m,"sender") or "")
    is_mine_raw = _g(m, "is_mine")
    if is_mine_raw is None: is_mine = bool(my_guid) and (sender == str(my_guid))
    else: is_mine = bool(is_mine_raw)
    reply = _g(m,"reply_to_message_id") or _g(m,"reply_to_id") or _g(m,"reply_to") or ""
    typ = _g(m, "type") or "Text"
    if isinstance(typ, int): typ = "Text"
    txt = _g(m, "text") or ""
    if not txt:
        f = _g(m,"file") or _g(m,"photo") or _g(m,"sticker") or _g(m,"voice")
        if isinstance(f, dict): txt = f.get("name") or f.get("file_name") or ""
        elif isinstance(f, str): txt = f
    t = _g(m,"time") or _g(m,"timestamp") or _g(m,"date") or ""
    return {"id": str(mid), "text": txt, "sender": sender, "time": str(t),
            "is_mine": is_mine, "type": typ, "reply_to": str(reply)}
async def fetch_messages(bot, guid, limit=30, my_guid=None, max_id=None, min_id=None):
    if my_guid is None:
        try:
            me = await bot.get_me(); my_guid = me.user.user_guid
        except Exception: my_guid = None
    anchor_max = max_id; anchor_min = min_id
    if anchor_min: anchor = str(anchor_min); sort = "FromMin"
    else: anchor = str(anchor_max) if anchor_max else "0"; sort = "FromMax"
    if anchor != "0":
        try: _ = int(anchor)
        except (ValueError, TypeError): anchor = "0"; sort = "FromMax"
    r = await _call_get_messages(bot, guid, anchor, limit, sort)
    msgs = _g(r, "messages") or []
    if not isinstance(msgs, list): msgs = [msgs] if msgs else []
    return [normalize_message(m, my_guid) for m in msgs if m]

# ═══════════════ Send helpers ═══════════════
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
        return await send_text_only(bot, target, text or "hello")
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
    raise RuntimeError(" | ".join(errors[-3:]) or "no send method worked")
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
    raise RuntimeError(" | ".join(errors[-3:]) or "send_message unavailable")
async def _send_with_edit_delay(bot, target, real_text, snd_cfg, log=None):
    placeholder = snd_cfg.get("placeholder_text") or "hi"
    plist = snd_cfg.get("placeholder_list") or ""
    if snd_cfg.get("placeholder_random") and plist.strip():
        opts = [p.strip() for p in plist.split(",") if p.strip()]
        if opts: placeholder = random.choice(opts)
    delay = float(snd_cfg.get("edit_delay_seconds", 3.0))
    if snd_cfg.get("edit_delay_random"):
        lo = float(snd_cfg.get("edit_delay_min", 2.0))
        hi = float(snd_cfg.get("edit_delay_max", 6.0))
        delay = random.uniform(lo, max(lo, hi))
    if delay <= 0 or placeholder == real_text:
        return await send_text_only(bot, target, real_text)
    try:
        r = bot.send_message(target, placeholder)
        if asyncio.iscoroutine(r): r = await r
    except Exception: return False
    mid = _extract_any_mid(r)
    if not mid: return True
    await asyncio.sleep(delay)
    await _edit_message(bot, target, mid, real_text)
    return True
async def _edit_message(bot, target, mid, new_text):
    for mname in ("edit_message","editMessage","edit_text","editText"):
        fn = getattr(bot, mname, None)
        if not fn: continue
        for kw in ({"object_guid": target, "message_id": mid, "text": new_text},
                   {"chat_id": target, "message_id": mid, "text": new_text},
                   {"object_guid": target, "message_id": mid, "message": new_text}):
            try:
                kw2 = _filter_kwargs(fn, kw)
                if not kw2: continue
                r = fn(**kw2)
                if asyncio.iscoroutine(r): r = await r
                return True
            except Exception: continue
        try:
            r = fn(target, mid, new_text)
            if asyncio.iscoroutine(r): r = await r
            return True
        except Exception: continue
    return False
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

# ═══════════════ profile / channel helpers ═══════════════
async def rubika_set_name(bot, first_name, last_name=None):
    variants = [dict(first_name=first_name, last_name=last_name or ""), dict(first_name=first_name)]
    ok, info, err = await _try_methods(bot, ("update_profile","updateProfile","set_profile","setProfile"), variants)
    return (True, info) if ok else (False, err)
async def rubika_set_bio(bot, bio):
    variants = [dict(bio=bio), dict(bio=bio, first_name=None, last_name=None)]
    ok, info, err = await _try_methods(bot, ("update_profile","updateProfile","set_bio","setBio"), variants)
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
async def rubika_delete_photo(bot, my_guid):
    for mname in ("delete_avatar","deleteAvatar","remove_avatar","removeAvatar"):
        fn = getattr(bot, mname, None)
        if not fn: continue
        try:
            r = fn(object_guid=my_guid)
            if asyncio.iscoroutine(r): r = await r
            return True, mname
        except Exception: continue
    return False, "API not supported"
async def rubika_set_chat_username(bot, guid, username):
    uname = username.lstrip("@") if username else ""
    if not uname: return False, "username empty"
    errors = []
    for variant in (uname, "@" + uname):
        try:
            r = bot.update_channel_username(channel_guid=guid, username=variant)
            if asyncio.iscoroutine(r): r = await r
            return True, "OK"
        except Exception as e: errors.append(_fmt_error(e))
    return False, " | ".join(errors)
async def rubika_set_chat_description(bot, guid, description):
    try:
        r = bot.edit_channel_info(channel_guid=guid, description=description)
        if asyncio.iscoroutine(r): r = await r
        return True, "OK"
    except Exception as e: return False, _fmt_error(e)
async def rubika_set_chat_title(bot, guid, title):
    try:
        r = bot.edit_channel_info(channel_guid=guid, title=title)
        if asyncio.iscoroutine(r): r = await r
        return True, "OK"
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
    except Exception as e: return False, _fmt_error(e), None, None
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
    if not guid: return False, "guid not found", None, None
    ctype = (channel_type or "private").lower()
    if ctype == "private":
        await asyncio.sleep(1.5)
        for val in ("Private","private"):
            fn = getattr(bot, "edit_channel_info", None)
            if not fn: break
            try:
                r = fn(channel_guid=guid, channel_type=val)
                if asyncio.iscoroutine(r): r = await r
                break
            except Exception: continue
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
            except Exception: pass
            await asyncio.sleep(1.5 + attempt)
    return True, "created+" + ctype, guid, join_link
async def rubika_create_join_link(bot, guid, attempts=3):
    last_err = None
    for attempt in range(attempts):
        variants = [dict(object_guid=guid, request_needed=False),
                    dict(object_guid=guid, request_needed=False, usage_limit=0),
                    dict(object_guid=guid), dict(channel_guid=guid)]
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
                    last_err = "no link in response"
                except TypeError: continue
                except Exception as e: last_err = _fmt_error(e); continue
        if attempt < attempts - 1: await asyncio.sleep(1.5 + attempt)
    return False, last_err or "link not found"
async def rubika_remove_channel(bot, guid):
    try:
        r = bot.remove_channel(channel_guid=guid)
        if asyncio.iscoroutine(r): r = await r
        return True, "OK"
    except Exception as e: return False, _fmt_error(e)
async def _resolve_target(bot, t):
    if not t: return None, None
    t = t.strip()
    if len(t) >= 20 and t[0] in ("u","c","g") and "://" not in t and " " not in t:
        return t, {"u":"User","c":"Channel","g":"Group"}.get(t[0].lower(), "?")
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
                    _find_keys(d, ("channel_guid","group_guid","object_guid","chat_guid","guid"), found)
                    g = (found.get("channel_guid") or found.get("group_guid") or
                         found.get("object_guid") or found.get("chat_guid") or found.get("guid"))
                    if g:
                        return g, {"u":"User","c":"Channel","g":"Group"}.get(g[0].lower())
            except Exception: continue
    return None, None

LINK_RE = re.compile(r'@([A-Za-z][A-Za-z0-9_]{4,40})')
URL_RE = re.compile(r'(?:rubika\.ir|ble\.rip)/joing/([A-Za-z0-9_\-]+)', re.I)
def _hash_of(link):
    if not link: return ""
    s = link.strip().lower()
    if s.startswith("@"): return "u:" + s[1:]
    m = re.search(r"/joing/([A-Za-z0-9_\-]+)", s)
    if m: return "j:" + m.group(1)
    m = re.search(r"rubika\.ir/([A-Za-z0-9_\-]+)", s)
    if m: return "r:" + m.group(1)
    return "x:" + s[:60]

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
                        _find_keys(d, ("object_guid","chat_guid","group_guid","channel_guid","guid"), found)
                        guid = (found.get("object_guid") or found.get("chat_guid") or
                                found.get("group_guid") or found.get("channel_guid") or found.get("guid"))
                    return True, guid, "invite"
                err = _fmt_error(r)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper(): return True, None, "already"
                return False, err, "join-failed"
            except Exception as e:
                err = _fmt_error(e)
                if "ALREADY" in err.upper() or "MEMBER" in err.upper(): return True, None, "already"
                if _is_rate_limit(e): raise
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
        if "ALREADY" in err.upper() or "MEMBER" in err.upper(): return True, guid, "already"
        return False, err, "join-failed"
    except Exception as e:
        err = _fmt_error(e)
        if "ALREADY" in err.upper() or "MEMBER" in err.upper(): return True, guid, "already"
        if _is_rate_limit(e): raise
        return False, err, "join-failed"

async def _extract_links_from_chat(bot, guid, limit=500, deep=False, log=None):
    found = set(); anchor = None; read_total = 0; batch = 25
    rounds = 0; max_rounds = 20 if not deep else 60
    seen_ids = set()
    while read_total < limit and rounds < max_rounds:
        rounds += 1
        try: msgs = await fetch_messages(bot, guid, limit=batch, max_id=anchor)
        except Exception: break
        if not msgs: break
        new_msgs = []
        for m in msgs:
            mid = m.get("id")
            if mid is None or mid in seen_ids: continue
            seen_ids.add(mid); new_msgs.append(m)
        if not new_msgs: break
        for m in new_msgs:
            txt = m.get("text") or ""
            for u in LINK_RE.findall(txt): found.add("@" + u)
            for uid in URL_RE.findall(txt): found.add("https://rubika.ir/joing/" + uid)
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
        if len(found) >= limit: break
        await asyncio.sleep(0.6)
    return list(found)
async def _auto_join_linkdoni(bot, url, log=None):
    try:
        ok, _g2, _tag = await _try_join_single(bot, url)
        if ok: await asyncio.sleep(0.8); return True
        return False
    except Exception: return False

# ═══════════════ Ops ═══════════════
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
_OP_LOCKS = {}
def _get_op_lock(oid):
    if oid not in _OP_LOCKS: _OP_LOCKS[oid] = asyncio.Lock()
    return _OP_LOCKS[oid]
def _op_stats(op):
    p = op.get("progress") or {}; t = op.get("type")
    if t in ("joinlef","lefter"):
        return {"done": p.get("joined", 0), "failed": p.get("failed", 0),
                "pending": 0, "in_progress": 1 if op.get("status") == "running" else 0,
                "total": op.get("max_join", 0) or (p.get("joined", 0) + p.get("failed", 0)),
                "already": p.get("already", 0), "sent": p.get("sent", 0),
                "left": p.get("left", 0), "wave": p.get("wave", 0),
                "tried": p.get("tried", 0),
                "skipped_seen": p.get("skipped_seen", 0),
                "skipped_banned": p.get("skipped_banned", 0),
                "rejected": p.get("rejected", 0), "round": p.get("round", 0)}
    if t == "autotar":
        return {"done": p.get("joined", 0), "failed": p.get("failed", 0),
                "pending": p.get("pending", 0), "in_progress": 1 if op.get("status") == "running" else 0,
                "total": p.get("total", 0), "already": p.get("already", 0),
                "sent": p.get("sent", 0), "left": p.get("left", 0),
                "wave": p.get("wave", 0), "tried": p.get("tried", 0),
                "skipped_seen": p.get("skipped_seen", 0),
                "skipped_banned": p.get("skipped_banned", 0),
                "rejected": p.get("rejected", 0), "round": p.get("round", 0)}
    return {"done": p.get("sent", 0), "failed": p.get("failed", 0),
            "pending": p.get("pending", 0), "in_progress": p.get("in_progress", 0),
            "total": p.get("total", 0), "blocked": p.get("blocked", 0),
            "round": p.get("round", 0)}
def _op_effective_status(op):
    st = op.get("status", "draft")
    if op.get("type") in ("joinlef","lefter","autotar"):
        if st in ("done","failed","cancelled","paused"): return st
        return "running"
    return st
def _op_short_title(op, n=32):
    t = op.get("type")
    if t == "joinlef": return f"joiner ({op.get('max_join', 0)})"
    if t == "lefter": return f"lefter ({op.get('leave_mode', '?')})"
    if t == "autotar":
        tpl = get_template(op.get("template_id"))
        return f"autotar: {short(tpl.get('name', '?'), 20)}" if tpl else "autotar"
    p = op.get("payload") or {}
    if p.get("text"): return f"send «{p.get('text')[:n]}»"
    return "send"
def _op_status_label(st):
    return {"running":"running", "paused":"paused", "queued":"queued",
            "done":"done", "failed":"failed", "cancelled":"cancelled",
            "empty":"empty", "draft":"draft"}.get(st, "?")
def _op_progress_bar(op):
    s = _op_stats(op); done = s["done"] + s["failed"]; tot = s["total"] or 0
    if tot == 0: return "▱" * 16 + " 0%", 0
    pct = int(done * 100 / tot); fill = min(16, int(done * 16 / tot))
    return "▰" * fill + "▱" * (16 - fill) + f" {pct}%", pct

# ═══════════════ Templates ═══════════════
def list_templates():
    d = _load(TEMPLATES_FILE, {}); return d if isinstance(d, dict) else {}
def save_templates(t): _save(TEMPLATES_FILE, t)
def get_template(tid): return list_templates().get(tid)
def add_template(tpl):
    ts = list_templates(); ts[tpl["id"]] = tpl; save_templates(ts)
def delete_template(tid):
    ts = list_templates(); ts.pop(tid, None); save_templates(ts)
def update_template(tid, section, field, value):
    ts = list_templates(); t = ts.get(tid)
    if not t: return
    if section == "meta": t[field] = value
    elif section == "sender_edit": t.setdefault("sender", {})[field] = value
    elif section == "pv": t.setdefault("pv", {})[field] = value
    else: t.setdefault(section, {})[field] = value
    save_templates(ts)
def new_template(name="new template"):
    return {
        "id": "tp_" + secrets.token_hex(4), "name": name, "created": int(time.time()),
        "channel": {"type":"private","title":"","username":"","about":"","photo_file":""},
        "profile": {"first_name":"","last_name":"","username":"","bio":"","photo_file":""},
        "joiner": {"max_join":0, "speed":"fast", "groups_only":True},
        "sender": {"text":"", "target":"groups", "mode":"send_only",
            "max_send":0, "delay":1.5,
            "edit_delay_enabled":False, "edit_delay_seconds":3.0,
            "edit_delay_random":False, "edit_delay_min":2.0, "edit_delay_max":6.0,
            "placeholder_text":"hi", "placeholder_random":False,
            "placeholder_list":"hi,hey,hello,yo",
            "multi_step_edit":False, "multi_step_middle":"Hi",
            "send_to_existing":True,
            "attach_file":"", "attach_caption":"",
            "infinite_loop":False, "loop_delay":3.0, "rescan_targets":True},
        "pv": {"enabled":False, "delay_seconds":0, "reply_once":True, "max_replies":1,
               "notify":True, "notify_on_receive":True, "notify_on_reply":True,
               "poll_seconds":5, "items":[{"kind":"text","text":"hello 👋"}],
               "apply_to_accounts":True},
        "lefter": {"leave_mode":"closed"},
    }
def _substitute(pattern, ctx):
    if not pattern: return ""
    s = str(pattern)
    for k, v in ctx.items(): s = s.replace("{" + k + "}", str(v))
    return s
def _build_ctx():
    now = time.time()
    return {"n": int(now) % 100000, "rnd": str(random.randint(100000, 999999)),
            "rnd4": str(random.randint(1000, 9999)),
            "date": time.strftime("%Y%m%d"), "time": time.strftime("%H%M%S"),
            "Link_private":"", "Title_private":"",
            "Link_public":"", "Username_public":"", "Title_public":""}

# ═══════════════ Joiner/Lefter/Sender/AutoTar ═══════════════
JL_SPEEDS = [("ultra","ultra",0.3), ("fast","fast",1.0),
             ("normal","normal",3.0), ("slow","safe",8.0)]
JL_JOBS = {}
def op_groups_only(oid):
    op = _get_op(oid); return bool(op.get("groups_only", True)) if op else True
def _op_is_cancelled(oid):
    op = _get_op(oid); return (not op) or op.get("status") == "cancelled"
async def _op_phase(oid, lock, phase):
    async with lock:
        op = _get_op(oid)
        if op: op["progress"]["phase"] = phase; _save_op(op)
    await _refresh_op_panel(oid)
async def _op_finish(oid, lock, phase):
    async with lock:
        op = _get_op(oid)
        if op:
            op["progress"]["phase"] = phase
            if op.get("status") == "running":
                op["status"] = "done"; op["finished_at"] = int(time.time())
            _save_op(op)
    await _refresh_op_panel(oid)

async def _joiner_worker(aid, acc, op_id, join_delay, max_join, auto_msg, log):
    acc_name = acc.get("name") or acc.get("phone") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    lock = _get_op_lock(op_id)
    link_donies = load_link_donies()
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    wave_size = int(cfg.get("wave_size", 50)); extract_limit = int(cfg.get("extract_limit", 300))
    try:
        cli = SafeClient(name=sess, _aid=aid)
        async with cli as bot:
            me = await bot.get_me()
            await _op_phase(op_id, lock, f"connected: {me.user.first_name or aid}")
            auto_join = int(cfg.get("auto_join_linkdoni", 1))
            linkdoni_guids = []
            for i, url in enumerate(link_donies, 1):
                await _op_phase(op_id, lock, f"auto-join {i}/{len(link_donies)}")
                try:
                    guid, kind = await _resolve_target(bot, url)
                    if auto_join: await _auto_join_linkdoni(bot, url, log=log)
                    if guid: linkdoni_guids.append(guid)
                except Exception: pass
            if not linkdoni_guids:
                await _op_finish(op_id, lock, "no active linkdoni"); return
            deep_done = False; wait_round = 0; wave_num = 0
            while True:
                if _op_is_cancelled(op_id): await _op_finish(op_id, lock, "cancelled"); return
                st = _get_op(op_id)
                if st and max_join and (st.get("progress", {}).get("joined", 0) >= max_join):
                    await _op_finish(op_id, lock, "limit reached"); return
                wave_num += 1
                await _op_phase(op_id, lock, f"wave {wave_num}: extracting")
                ordered = {}
                for guid in linkdoni_guids:
                    try:
                        found = await _extract_links_from_chat(bot, guid, limit=extract_limit, deep=False, log=log)
                        for l in found:
                            if l not in ordered: ordered[l] = True
                            if len(ordered) >= wave_size: break
                    except Exception: pass
                    if len(ordered) >= wave_size: break
                new_links = []
                for lk in ordered.keys():
                    h = _hash_of(lk)
                    if not h or _is_seen(aid, h) or _is_banned(aid, h): continue
                    new_links.append(lk)
                    if len(new_links) >= wave_size: break
                if not new_links and not deep_done:
                    deep_done = True
                    await _op_phase(op_id, lock, f"wave {wave_num}: deep scan")
                    for guid in linkdoni_guids:
                        try:
                            found = await _extract_links_from_chat(bot, guid, limit=300, deep=True, log=log)
                            for lk in found:
                                h = _hash_of(lk)
                                if not h or _is_seen(aid, h) or _is_banned(aid, h): continue
                                if lk not in new_links: new_links.append(lk)
                                if len(new_links) >= wave_size: break
                        except Exception: pass
                        if len(new_links) >= wave_size: break
                if not new_links:
                    wait_round += 1
                    max_wait = int(cfg.get("max_wait_rounds", 20))
                    if wait_round > max_wait:
                        await _op_finish(op_id, lock, "no new links"); return
                    ws = int(cfg.get("wait_for_links_sec", 90))
                    for k in range(ws):
                        if _op_is_cancelled(op_id): await _op_finish(op_id, lock, "cancelled"); return
                        await _op_phase(op_id, lock, f"wait {ws-k}s ({wait_round}/{max_wait})")
                        await asyncio.sleep(1)
                    wave_num -= 1; deep_done = False; continue
                else: wait_round = 0
                await _op_phase(op_id, lock, f"wave {wave_num}: {len(new_links)} links")
                sem = asyncio.Semaphore(8)
                async def join_one(lk):
                    async with sem:
                        if _op_is_cancelled(op_id): return
                        st2 = _get_op(op_id)
                        if st2 and max_join and (st2.get("progress", {}).get("joined", 0) >= max_join): return
                        h = _hash_of(lk)
                        if _is_seen(aid, h) or _is_banned(aid, h): return
                        try:
                            ok, guid, tag = await _try_join_single(bot, lk)
                            if ok:
                                _mark_seen(aid, h)
                                async with lock:
                                    op2 = _get_op(op_id)
                                    if op2:
                                        op2["progress"]["joined"] = op2["progress"].get("joined", 0) + 1
                                        if tag == "already": op2["progress"]["already"] = op2["progress"].get("already", 0) + 1
                                        _save_op(op2)
                                if auto_msg and guid:
                                    try:
                                        await send_text_only(bot, guid, auto_msg)
                                        async with lock:
                                            op2 = _get_op(op_id)
                                            if op2: op2["progress"]["sent"] = op2["progress"].get("sent", 0) + 1; _save_op(op2)
                                    except Exception: pass
                            else:
                                _mark_seen(aid, h)
                                if "BANNED" in str(guid).upper() or "KICKED" in str(guid).upper():
                                    _mark_banned(aid, h, str(guid)[:80])
                                async with lock:
                                    op2 = _get_op(op_id)
                                    if op2: op2["progress"]["failed"] = op2["progress"].get("failed", 0) + 1; _save_op(op2)
                        except Exception:
                            async with lock:
                                op2 = _get_op(op_id)
                                if op2: op2["progress"]["failed"] = op2["progress"].get("failed", 0) + 1; _save_op(op2)
                        if join_delay > 0: await asyncio.sleep(join_delay)
                await asyncio.gather(*[asyncio.create_task(join_one(lk)) for lk in new_links],
                                     return_exceptions=True)
                await _op_phase(op_id, lock, f"wave {wave_num} done")
    except asyncio.CancelledError:
        await _op_finish(op_id, lock, "cancelled"); raise
    except Exception as e:
        flog(f"[joiner] {acc_name}: {type(e).__name__}: {e}", "error")
        await _op_finish(op_id, lock, f"error: {type(e).__name__}")

async def run_joiner_lefter(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    op["progress"] = {"joined":0,"failed":0,"total":0,"phase":"start",
                      "already":0,"sent":0,"wave":0,"tried":0,
                      "skipped_seen":0,"skipped_banned":0,"rejected":0}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(
            _joiner_worker(aid, a, op["id"], float(op.get("join_delay", 0.5)),
                           op.get("max_join", 0) or 0, (op.get("auto_msg") or "").strip(), log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled", "done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)

async def _lefter_collect(bot, mode="all", exclude_guids=None):
    exclude_guids = exclude_guids or set()
    out = []
    try: chats = await get_all_chats_raw(bot)
    except Exception: return out
    for c in chats:
        try:
            if c["type"] == "User": continue
            guid = c["guid"]
            if guid in exclude_guids: continue
            kind = "channel" if _is_broadcast_channel(c) else "group"
            if mode == "groups" and kind != "group": continue
            if mode == "channels" and kind != "channel": continue
            if mode == "closed" and kind != "group": continue
            out.append({"guid": guid, "name": c["title"], "kind": kind})
        except Exception: continue
    return out
async def _lefter_leave_one(bot, target):
    guid = target.get("guid")
    if not guid: return False, "no_guid"
    kind = target.get("kind", "group")
    try:
        if kind == "channel":
            r = bot.join_channel_action(channel_guid=guid, action="Leave")
        else:
            r = bot.leave_group(group_guid=guid)
        if asyncio.iscoroutine(r): r = await r
        if _is_ok_response(r): return True, None
        return False, _fmt_error(r)
    except Exception as e: return False, _fmt_error(e)

async def _lefter_worker(aid, acc, op_id, mode, delay, log):
    acc_name = acc.get("name") or acc.get("phone") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    lock = _get_op_lock(op_id)
    left = 0; failed = 0
    try:
        cli = SafeClient(name=sess, _aid=aid)
        async with cli as bot:
            await _op_phase(op_id, lock, "collecting")
            own_guids = set()
            for ch in get_stored_channels(aid):
                if ch.get("guid"): own_guids.add(ch["guid"])
            targets = await _lefter_collect(bot, mode, exclude_guids=own_guids)
            if not targets: await _op_finish(op_id, lock, "nothing to leave"); return
            async with lock:
                op = _get_op(op_id)
                if op: op["progress"]["total"] = len(targets); _save_op(op)
            for t in targets:
                if _op_is_cancelled(op_id): await _op_finish(op_id, lock, "cancelled"); return
                try:
                    ok, err2 = await asyncio.wait_for(_lefter_leave_one(bot, t), timeout=30)
                    if ok: left += 1
                    else: failed += 1; add_error("lefter", err2, t.get("name"), acc_name)
                except Exception as e:
                    failed += 1; add_error("lefter", _fmt_error(e), t.get("name"), acc_name)
                async with lock:
                    op = _get_op(op_id)
                    if op:
                        op["progress"]["joined"] = left
                        op["progress"]["failed"] = failed
                        op["progress"]["phase"] = f"leaving {left}/{len(targets)}"
                        _save_op(op)
                if delay > 0: await asyncio.sleep(delay)
            await _op_finish(op_id, lock, f"left {left} / fail {failed}")
    except asyncio.CancelledError: await _op_finish(op_id, lock, "cancelled"); raise
    except Exception as e:
        flog(f"[lefter] {acc_name}: {e}", "error")
        await _op_finish(op_id, lock, f"error: {type(e).__name__}")

async def run_lefter(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    op["progress"] = {"joined":0,"failed":0,"total":0,"phase":"start"}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(
            _lefter_worker(aid, a, op["id"], op.get("leave_mode", "all"),
                           float(op.get("delay", 0.8)), log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled", "done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)

async def _send_worker(aid, acc, op_id, cfg, stop, log):
    acc_name = acc.get("name") or acc.get("phone") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    op = _get_op(op_id)
    if not op: return
    lock = _get_op_lock(op_id)
    sent = 0; failed = 0; blocked = 0
    delay = float(op.get("delay", 1.5))
    payload = op.get("payload") or {"text":"hello","kind":"text"}
    text = payload.get("text") or ""
    attach_file = op.get("attach_file") or ""
    infinite_loop = bool(op.get("infinite_loop", False))
    loop_delay = float(op.get("loop_delay", 3.0))
    rescan_targets = bool(op.get("rescan_targets", True))
    use_edit = bool(op.get("edit_delay_enabled", False))
    snd_cfg = {k: op.get(k) for k in ("edit_delay_seconds","edit_delay_random",
        "edit_delay_min","edit_delay_max","placeholder_text","placeholder_random",
        "placeholder_list","multi_step_edit","multi_step_middle")}
    try:
        cli = SafeClient(name=sess, _aid=aid)
        async with cli as bot:
            await _op_phase(op_id, lock, "collecting targets")
            own_guids = set()
            for ch in get_stored_channels(aid):
                if ch.get("guid"): own_guids.add(ch["guid"])
            target = op.get("target", "both")
            my_guid = None
            try: me = await bot.get_me(); my_guid = me.user.user_guid
            except Exception: pass
            all_chats = await get_all_chats_raw(bot)
            targets = []
            for c in all_chats:
                if c["guid"] in own_guids: continue
                if c["type"] == "User":
                    if my_guid and c["guid"] == my_guid: continue
                    if target in ("pv", "both") and not c["is_blocked"]:
                        targets.append({"guid": c["guid"], "name": c["title"], "type": "pv"})
                elif _is_true_group(c):
                    if target in ("groups", "both"):
                        targets.append({"guid": c["guid"], "name": c["title"], "type": "group"})
            max_send = int(op.get("max", 0) or 0)
            if max_send and len(targets) > max_send: targets = targets[:max_send]
            loop_round = 0; sent_ids = set()
            while True:
                loop_round += 1
                await _op_phase(op_id, lock,
                    f"loop {loop_round} - {len(targets)} targets" if infinite_loop
                    else f"sending to {len(targets)}" + (" (edit)" if use_edit else ""))
                if stop.is_set(): break
                async with lock:
                    op2 = _get_op(op_id)
                    if op2:
                        op2["progress"]["pending"] = len(targets)
                        op2["progress"]["total"] = len(targets)
                        if infinite_loop: op2["progress"]["round"] = loop_round
                        _save_op(op2)
                for i, t in enumerate(targets, 1):
                    if _op_is_cancelled(op_id): await _op_finish(op_id, lock, "cancelled"); return
                    if stop.is_set(): break
                    try:
                        if attach_file and os.path.exists(attach_file):
                            await send_media(bot, t["guid"], {"kind":"document",
                                "text": text, "file": attach_file})
                        elif use_edit and text:
                            await _send_with_edit_delay(bot, t["guid"], text, snd_cfg, log=log)
                        else:
                            await send_media(bot, t["guid"], payload)
                        sent += 1; sent_ids.add(t["guid"])
                    except Exception as e:
                        err = _fmt_error(e)
                        if "BLOCKED" in err.upper() or "FORBIDDEN" in err.upper(): blocked += 1
                        else:
                            failed += 1; add_error("sender", err, t.get("name"), acc_name)
                        if _is_rate_limit(e): await asyncio.sleep(60)
                    async with lock:
                        op2 = _get_op(op_id)
                        if op2:
                            op2["progress"]["sent"] = sent
                            op2["progress"]["failed"] = failed
                            op2["progress"]["blocked"] = blocked
                            op2["progress"]["pending"] = max(0, len(targets) - i)
                            _save_op(op2)
                    if delay > 0: await asyncio.sleep(delay)
                if not infinite_loop: break
                if _op_is_cancelled(op_id): await _op_finish(op_id, lock, "cancelled"); return
                if rescan_targets:
                    await _op_phase(op_id, lock, f"loop {loop_round}: rescanning")
                    try:
                        fresh = await get_all_chats_raw(bot)
                        old_guids = set(t["guid"] for t in targets)
                        for c in fresh:
                            if c["guid"] in old_guids or c["guid"] in sent_ids: continue
                            if c["type"] == "User" and target in ("pv", "both") and not c["is_blocked"]:
                                targets.append({"guid": c["guid"], "name": c["title"], "type": "pv"})
                            elif _is_true_group(c) and target in ("groups", "both"):
                                targets.append({"guid": c["guid"], "name": c["title"], "type": "group"})
                    except Exception: pass
                waited = 0.0
                while waited < loop_delay:
                    if stop.is_set(): return
                    if _op_is_cancelled(op_id): await _op_finish(op_id, lock, "cancelled"); return
                    await asyncio.sleep(min(1.0, loop_delay - waited)); waited += 1.0
            await _op_finish(op_id, lock, f"sent {sent} / fail {failed}" + (f" / blocked {blocked}" if blocked else ""))
    except asyncio.CancelledError: raise
    except Exception as e:
        flog(f"[sender] {acc_name}: {e}", "error")
        await _op_finish(op_id, lock, f"error: {type(e).__name__}")

async def run_sender(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    op["progress"] = {"sent":0,"failed":0,"total":0,"pending":0,
                      "in_progress":0,"phase":"start","blocked":0,"round":0}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    stop = asyncio.Event(); STATE.setdefault("cancel_events", {})[op["id"]] = stop
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(_send_worker(aid, a, op["id"], {}, stop, log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled", "done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)

async def _auto_tar_worker(aid, acc, op_id, tpl, log):
    acc_name = acc.get("name") or acc.get("phone") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    lock = _get_op_lock(op_id); ctx = _build_ctx()
    async def _is_cancelled(): return _op_is_cancelled(op_id)
    try:
        cli = SafeClient(name=sess, _aid=aid)
        async with cli as bot:
            me = await bot.get_me(); my_guid = me.user.user_guid
            await _op_phase(op_id, lock, f"connected: {me.user.first_name or aid}")
            pv_cfg = tpl.get("pv") or {}
            if pv_cfg.get("apply_to_accounts") and pv_cfg.get("items"):
                try:
                    cur = _load_pv_account(aid); cur.update({
                        "enabled": bool(pv_cfg.get("enabled", cur.get("enabled", False))),
                        "delay_seconds": int(pv_cfg.get("delay_seconds", cur.get("delay_seconds", 0))),
                        "max_replies": int(pv_cfg.get("max_replies", cur.get("max_replies", 1))),
                        "items": list(pv_cfg.get("items") or []),
                    })
                    _save_pv_account(aid, cur)
                except Exception: pass
            ch = tpl.get("channel") or {}
            if ch.get("title"):
                ctype = ch.get("type", "private"); is_pub = ctype == "public"
                title = _substitute(ch["title"], ctx)[:60] or f"channel {ctx['n']}"
                about = _substitute(ch.get("about", ""), ctx)
                await _op_phase(op_id, lock, f"creating channel: {title}")
                try:
                    ok, info, guid, link = await rubika_create_channel(bot, title, about, ctype)
                    if ok and guid:
                        if is_pub and ch.get("username"):
                            uname = _substitute(ch["username"], ctx).lstrip("@")
                            try: await rubika_set_chat_username(bot, guid, uname)
                            except Exception: pass
                        ch_data = {"title": title, "description": about, "guid": guid,
                                   "username": ch.get("username", ""), "is_public": is_pub,
                                   "type": ctype, "join_link": link or "",
                                   "created": int(time.time())}
                        add_channel_to_storage(aid, ch_data)
                        if ctype == "private":
                            if not link:
                                try: _ok2, link = await rubika_create_join_link(bot, guid)
                                except Exception: pass
                        un = ch.get("username", "")
                        ctx["Link_private"] = link or (f"@{un}" if un else "")
                        ctx["Title_private"] = title
                        ctx["Link_channel"] = ctx["Link_private"]
                        ctx["Title_channel"] = title
                        if ch.get("photo_file") and os.path.exists(ch["photo_file"]):
                            try: await rubika_set_chat_photo(bot, guid, ch["photo_file"])
                            except Exception: pass
                except Exception as e:
                    add_error("autotar-channel", _fmt_error(e), title, acc_name)
            p = tpl.get("profile") or {}
            if any(p.get(k) for k in ("first_name","last_name","bio","username","photo_file")):
                await _op_phase(op_id, lock, "updating profile")
                fn_ = _substitute(p.get("first_name", ""), ctx)[:64]
                ln_ = _substitute(p.get("last_name", ""), ctx)[:64]
                if fn_ or ln_:
                    try: await rubika_set_name(bot, fn_ or None, ln_ or None)
                    except Exception as e: add_error("autotar-profile", _fmt_error(e), None, acc_name)
                if p.get("bio"):
                    try: await rubika_set_bio(bot, _substitute(p["bio"], ctx)[:70])
                    except Exception as e: add_error("autotar-bio", _fmt_error(e), None, acc_name)
                if p.get("username"):
                    try: await rubika_set_username(bot, _substitute(p["username"], ctx).lstrip("@"))
                    except Exception as e: add_error("autotar-username", _fmt_error(e), None, acc_name)
                if p.get("photo_file") and os.path.exists(p["photo_file"]):
                    try: await rubika_set_photo(bot, my_guid, p["photo_file"])
                    except Exception: pass
            j = tpl.get("joiner") or {}
            snd = tpl.get("sender") or {}
            mode = snd.get("mode", "send_only")
            sender_text = _substitute(snd.get("text", ""), ctx) if snd.get("text") else ""
            send_during_join = (mode in ("join_send","join_send_leave")) and bool(sender_text)
            send_to_existing = bool(snd.get("send_to_existing", True))
            attach_file = snd.get("attach_file") or ""
            attach_caption = _substitute(snd.get("attach_caption", ""), ctx) if snd.get("attach_caption") else ""
            groups_only = bool(j.get("groups_only", True))
            max_join = int(j.get("max_join", 0) or 0)
            join_delay = {"ultra":0.3,"fast":1.0,"normal":3.0,"slow":8.0}.get(j.get("speed", "fast"), 1.0)
            joined_count = 0; already_count = 0; sent_count = 0; left_count = 0
            failed_count = 0; tried_count = 0
            if max_join > 0:
                lds = load_link_donies(); cfg = _load(CFG_FILE, DEFAULT_CFG)
                wave_size = int(cfg.get("wave_size", 50))
                linkdoni_guids = []
                auto_join = int(cfg.get("auto_join_linkdoni", 1))
                for url in lds:
                    try:
                        guid, kind = await _resolve_target(bot, url)
                        if guid:
                            if auto_join: await _auto_join_linkdoni(bot, url, log=log)
                            linkdoni_guids.append(guid)
                    except Exception: pass
                wave_num = 0
                while joined_count < max_join and wave_num < 100:
                    if await _is_cancelled(): await _op_finish(op_id, lock, "cancelled"); return
                    wave_num += 1
                    await _op_phase(op_id, lock, f"wave {wave_num} ({joined_count}/{max_join})")
                    ordered = {}
                    for guid in linkdoni_guids:
                        try:
                            found = await _extract_links_from_chat(bot, guid, limit=300, log=log)
                            for l in found:
                                if l not in ordered: ordered[l] = True
                                if len(ordered) >= wave_size: break
                        except Exception: pass
                        if len(ordered) >= wave_size: break
                    new_links = []
                    for lk in ordered.keys():
                        h = _hash_of(lk)
                        if not h or _is_seen(aid, h) or _is_banned(aid, h): continue
                        new_links.append(lk)
                        if len(new_links) >= wave_size: break
                    if not new_links: await asyncio.sleep(20); continue
                    sem = asyncio.Semaphore(6)
                    async def join_one(lk):
                        nonlocal joined_count, already_count, sent_count, left_count, failed_count, tried_count
                        async with sem:
                            if joined_count >= max_join: return
                            h = _hash_of(lk)
                            if _is_seen(aid, h) or _is_banned(aid, h): return
                            tried_count += 1
                            try:
                                ok, guid, tag = await _try_join_single(bot, lk)
                                if not ok:
                                    failed_count += 1
                                    if "BANNED" in str(guid).upper():
                                        _mark_banned(aid, h, str(guid)[:80])
                                    _mark_seen(aid, h); return
                                _mark_seen(aid, h)
                                if tag == "already": already_count += 1
                                else: joined_count += 1
                                if send_during_join and guid and sender_text:
                                    try:
                                        await asyncio.sleep(0.4)
                                        if attach_file and os.path.exists(attach_file):
                                            await send_media(bot, guid, {"kind":"document",
                                                "text": attach_caption or sender_text, "file": attach_file})
                                        else:
                                            await send_text_only(bot, guid, sender_text)
                                        sent_count += 1
                                        if mode == "join_send_leave":
                                            ok_l, _ = await _lefter_leave_one(bot, {"guid": guid, "kind": "group"})
                                            if ok_l: left_count += 1
                                    except Exception: pass
                            except Exception: failed_count += 1
                            if join_delay > 0: await asyncio.sleep(join_delay)
                    await asyncio.gather(*[asyncio.create_task(join_one(lk)) for lk in new_links],
                                         return_exceptions=True)
            should_send_final = False
            if sender_text or attach_file:
                if not send_during_join: should_send_final = True
                elif send_to_existing: should_send_final = True
            if should_send_final:
                target = snd.get("target", "groups")
                max_send = int(snd.get("max_send", 0) or 0)
                delay = float(snd.get("delay", 1.5))
                await _op_phase(op_id, lock, "final send")
                all_chats = await get_all_chats_raw(bot)
                own_guids = set(c.get("guid") for c in get_stored_channels(aid) if c.get("guid"))
                targets = []
                for c in all_chats:
                    if c["guid"] in own_guids or c["guid"] == my_guid: continue
                    if c["type"] == "User" and target in ("pv", "both") and not c["is_blocked"]:
                        targets.append(c["guid"])
                    elif _is_true_group(c) and target in ("groups", "both"):
                        targets.append(c["guid"])
                if max_send and len(targets) > max_send: targets = targets[:max_send]
                for guid in targets:
                    if await _is_cancelled(): await _op_finish(op_id, lock, "cancelled"); return
                    try:
                        if attach_file and os.path.exists(attach_file):
                            await send_media(bot, guid, {"kind":"document",
                                "text": attach_caption or sender_text, "file": attach_file})
                        else:
                            await send_text_only(bot, guid, sender_text)
                        sent_count += 1
                    except Exception as e:
                        failed_count += 1; add_error("autotar-send", _fmt_error(e), guid, acc_name)
                    if delay > 0: await asyncio.sleep(delay)
            lf = tpl.get("lefter") or {}
            if lf.get("leave_mode"):
                ml = lf["leave_mode"]
                await _op_phase(op_id, lock, f"leaving ({ml})")
                own_guids = set(c.get("guid") for c in get_stored_channels(aid) if c.get("guid"))
                targets = await _lefter_collect(bot, ml, exclude_guids=own_guids)
                for t in targets:
                    if await _is_cancelled(): await _op_finish(op_id, lock, "cancelled"); return
                    try:
                        ok_l, _ = await _lefter_leave_one(bot, t)
                        if ok_l: left_count += 1
                    except Exception: pass
                    await asyncio.sleep(0.6)
            await _op_finish(op_id, lock,
                f"join {joined_count} / send {sent_count} / left {left_count}")
    except asyncio.CancelledError:
        await _op_finish(op_id, lock, "cancelled"); raise
    except Exception as e:
        flog(f"[autotar] {acc_name}: {type(e).__name__}: {e}", "error")
        await _op_finish(op_id, lock, f"error: {type(e).__name__}")

async def run_auto_tar(op, log, tpl_override=None):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    tpl = tpl_override if tpl_override else get_template(op.get("template_id"))
    if not tpl:
        op["status"] = "failed"; op["progress"] = {"phase":"no template"}; _save_op(op); return
    op["progress"] = {"joined":0,"failed":0,"total":0,"pending":0,
                      "in_progress":0,"phase":"start","sent":0,"already":0,
                      "tried":0,"wave":0,"left":0,"round":0,
                      "skipped_seen":0,"skipped_banned":0,"rejected":0}
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

# ═══════════════ PV ═══════════════
PV_LISTENER_TASKS = {}
_PV_REPLY_TASKS = {}
_PV_STOP_EVENTS = {}
async def _sleep_or_stop(ev, sec):
    try: await asyncio.wait_for(ev.wait(), timeout=sec)
    except asyncio.TimeoutError: pass
async def _pv_send_reply(aid, acc, sender_guid, user_info, stop_event):
    name = acc.get("name") or aid; sender_str = str(sender_guid)
    key = f"{aid}:{sender_str}"; cfg = _load_pv_account(aid)
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    cli = None; connected = False; send_ok = True; send_err = None
    def _fail(msg):
        nonlocal send_ok, send_err
        send_ok = False; send_err = str(msg)[:150]
    try:
        for _ in range(int(cfg.get("delay_seconds", 0))):
            if stop_event.is_set(): _pv_count_add(aid, sender_str, -1); return
            await asyncio.sleep(1)
        cfg = _load_pv_account(aid)
        try:
            cli = SafeClient(name=sess, _aid=aid); await cli.__aenter__(); connected = True
        except Exception as e: _fail(f"connect: {_fmt_error(e)}")
        if connected and cli:
            for item in cfg.get("items") or []:
                if stop_event.is_set(): break
                kind = item.get("kind", "text")
                try:
                    if kind == "text" and item.get("text"):
                        await send_text_only(cli, sender_guid, item["text"])
                    elif kind == "file":
                        fp = item.get("file_path")
                        if fp and os.path.exists(fp):
                            await send_media(cli, sender_guid, {"kind":"document",
                                "text": item.get("caption") or "", "file": fp})
                        else: _fail("file missing")
                    elif kind == "delay":
                        await asyncio.sleep(int(item.get("seconds", 3))); continue
                    await asyncio.sleep(random.uniform(0.8, 1.8))
                except Exception as e: _fail(f"{type(e).__name__}: {str(e)[:100]}")
    except asyncio.CancelledError:
        if not connected: _pv_count_add(aid, sender_str, -1)
        raise
    except Exception as e: _fail(f"{type(e).__name__}: {str(e)[:100]}")
    finally:
        if cli:
            try: await cli.__aexit__(None, None, None)
            except Exception: pass
        _PV_REPLY_TASKS.pop(key, None)
    if not connected: _pv_count_add(aid, sender_str, -1)
    try: _record_pv_reply(aid, sender_str, ok=send_ok, err=send_err)
    except Exception: pass
    if cfg.get("notify", True) and cfg.get("notify_on_reply", True):
        u = user_info.get("first_name") or sender_str
        ok_txt = f"reply ok: {u}" if send_ok else f"reply failed: {u} ({send_err or '?'})"
        await tg_send(f"{{💬}} {SC(ok_txt)}")
async def _pv_handle_new_msg(bot, aid, acc, sender_guid, sender_title, msg):
    cfg = _load_pv_account(aid)
    if not cfg.get("enabled"): return
    uid = str(sender_guid); key = f"{aid}:{uid}"
    info = {"first_name": sender_title or "", "username": ""}
    try: _record_pv_visit(aid, uid, info)
    except Exception: pass
    if _pv_limit_reached(aid, uid, cfg): return
    ex = _PV_REPLY_TASKS.get(key)
    if ex and not ex.done(): return
    _pv_count_add(aid, uid, +1)
    if cfg.get("notify", True) and cfg.get("notify_on_receive", True):
        u = info["first_name"] or uid
        mt = (msg.get("text") or "")[:120]
        txt = (f"{{🔔}} {SC('new pv message')} ( {u} )\n\n"
               f"👥{TICK}{SC('from')} : {u}\n"
               f"✉️{TICK}{SC('text')} :\n<code>{esc(mt)}</code>")
        await tg_send(txt)
    ev = _PV_STOP_EVENTS.get(aid)
    if ev is None: ev = _PV_STOP_EVENTS[aid] = asyncio.Event()
    _PV_REPLY_TASKS[key] = asyncio.create_task(_pv_send_reply(aid, acc, sender_guid, info, ev))
async def _pv_poller_worker(aid, acc, stop_event):
    global _PV_WM_DIRTY
    name = acc.get("name") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    cli = None; my_guid = None
    flog(f"[pv] {name}: poller started")
    try:
        while not stop_event.is_set():
            cfg = _load_pv_account(aid)
            poll = max(3, int(cfg.get("poll_seconds", 5)))
            if not cfg.get("enabled"): await _sleep_or_stop(stop_event, poll); continue
            try:
                if cli is None:
                    cli = SafeClient(name=sess, _aid=aid)
                    await cli.__aenter__()
                    me = await cli.get_me(); my_guid = me.user.user_guid
                chats = await get_all_chats_raw(cli)
                first = not (_wm_load().get(aid) or {}).get("_init")
                for c in chats:
                    if c["type"] != "User" or c["is_blocked"]: continue
                    if c["guid"] == my_guid: continue
                    uid = c["guid"]
                    try: msgs = await fetch_messages(cli, uid, limit=2, my_guid=my_guid)
                    except Exception: continue
                    for m in msgs:
                        if m.get("is_mine"): continue
                        try: mid_int = int(m["id"])
                        except Exception: continue
                        if mid_int <= _wm_get(aid, uid): continue
                        _wm_set(aid, uid, mid_int)
                        if first: continue
                        try: await _pv_handle_new_msg(cli, aid, acc, uid, c["title"], m)
                        except Exception as he: flog(f"[pv] handle: {he}", "warning")
                if first:
                    _wm_load().setdefault(aid, {})["_init"] = 1; _PV_WM_DIRTY = True
                _wm_flush()
            except asyncio.CancelledError: raise
            except Exception as e:
                flog(f"[pv] {name}: {type(e).__name__}: {e}", "warning")
                if cli:
                    try: await cli.__aexit__(None, None, None)
                    except Exception: pass
                    cli = None
                await _sleep_or_stop(stop_event, 10); continue
            await _sleep_or_stop(stop_event, poll)
    finally:
        _wm_flush()
        if cli:
            try: await cli.__aexit__(None, None, None)
            except Exception: pass
        flog(f"[pv] {name}: poller stopped")
async def start_pv_responders():
    for aid, acc in list_accounts().items():
        cfg = _load_pv_account(aid)
        if not cfg.get("enabled"): continue
        ex = PV_LISTENER_TASKS.get(aid)
        if ex and not ex.done(): continue
        stop = asyncio.Event(); _PV_STOP_EVENTS[aid] = stop
        PV_LISTENER_TASKS[aid] = asyncio.create_task(_pv_poller_worker(aid, acc, stop))
def _stop_all_pv():
    for aid, st in list(_PV_STOP_EVENTS.items()):
        try: st.set()
        except Exception: pass
    for aid, t in list(PV_LISTENER_TASKS.items()):
        if not t.done(): t.cancel()
    for key, t in list(_PV_REPLY_TASKS.items()):
        if not t.done(): t.cancel()
    PV_LISTENER_TASKS.clear(); _PV_REPLY_TASKS.clear(); _PV_STOP_EVENTS.clear()
def _stop_pv_for_account(aid):
    st = _PV_STOP_EVENTS.pop(aid, None)
    if st:
        try: st.set()
        except Exception: pass
    t = PV_LISTENER_TASKS.pop(aid, None)
    if t and not t.done(): t.cancel()

# ═══════════════ Listener ═══════════════
LISTENER_TASKS = {}
LISTENER_SEEN = {}; LISTENER_SEEN_LOCK = threading.Lock(); LISTENER_MAX_SEEN = 8000
def _listener_cfg_enabled():
    try: return bool(int(_load(CFG_FILE, DEFAULT_CFG).get("listener", 1)))
    except Exception: return True
def _listener_cfg_service_only():
    try: return bool(int(_load(CFG_FILE, DEFAULT_CFG).get("listener_service_only", 1)))
    except Exception: return True
def is_login_service_message(chat_title, text):
    title = (chat_title or ""); txt = (text or "")
    tl = title.lower(); xl = txt.lower()
    if "اعلان" in title or "ورود" in title: return True
    if "login" in tl or "login" in xl: return True
    if "کد روبیکا" in txt: return True
    return False
async def _listener_loop(aid, acc, stop_event):
    name = acc.get("name") or acc.get("phone") or aid
    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    flog(f"[listener] {name}: started")
    while not stop_event.is_set():
        cli = None
        try:
            cli = SafeClient(name=sess, _aid=aid); await cli.__aenter__()
            me = await cli.get_me(); my_guid = me.user.user_guid
            while not stop_event.is_set():
                if not _listener_cfg_enabled(): await asyncio.sleep(5); continue
                try: chats = await get_all_chats_raw(cli)
                except Exception: await asyncio.sleep(10); continue
                for c in chats:
                    if c["type"] in ("Group", "Channel"): continue
                    if c["guid"] == my_guid or c["is_blocked"]: continue
                    try: msgs = await fetch_messages(cli, c["guid"], limit=3, my_guid=my_guid)
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
                        if _listener_cfg_service_only() and not is_login_service_message(c["title"], m.get("text", "")):
                            continue
                        STATE["listener_new_count"] = STATE.get("listener_new_count", 0) + 1
                        txt = m.get("text") or ""
                        body = (f"{{📨}} {SC('a new message for')} ( {name} )\n\n"
                                f"📞{TICK}{SC('sender')} : {c['title']}\n"
                                f"👥{TICK}{SC('from')} : {c['guid']}\n"
                                f"✉️{TICK}{SC('text')} :\n<code>{esc(txt[:1000]) or '(no text)'}</code>")
                        try: await tg_send(body)
                        except Exception: pass
                try: await cli.get_me()
                except Exception: raise
                for _ in range(12):
                    if stop_event.is_set(): break
                    await asyncio.sleep(5)
        except asyncio.CancelledError: raise
        except RuntimeError as e:
            if _is_auth_dead(e):
                flog(f"[listener] {name}: NO_SESSION"); return
            await asyncio.sleep(20)
        except Exception: await asyncio.sleep(20)
        finally:
            if cli:
                try: await cli.__aexit__(None, None, None)
                except Exception: pass
async def start_all_listeners():
    for aid, acc in list_accounts().items():
        if aid in LISTENER_TASKS and not LISTENER_TASKS[aid].done(): continue
        stop = asyncio.Event(); STATE.setdefault("listener_stops", {})[aid] = stop
        LISTENER_TASKS[aid] = asyncio.create_task(_listener_loop(aid, acc, stop))
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
    LISTENER_TASKS.clear(); STATE["listener_stops"] = {}
    await asyncio.sleep(1); await start_all_listeners()

KEEPALIVE_SECONDS = 15 * 60
PV_HEALTH_SECONDS = 5 * 60
async def keepalive_loop():
    flog(f"[keepalive] started"); await asyncio.sleep(60)
    pv_check_counter = 0
    while True:
        try:
            for aid, acc in list_accounts().items():
                sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
                if not os.path.exists(sess + ".rp"): continue
                cli = None
                try:
                    cli = SafeClient(name=sess, _aid=aid); await cli.__aenter__()
                    await cli.get_me()
                except RuntimeError as e:
                    if _is_auth_dead(e):
                        try: await tg_send(f"{{⚠️}} {SC('session dead')} : {acc.get('name', aid)}")
                        except Exception: pass
                except Exception: pass
                finally:
                    if cli:
                        try: await cli.__aexit__(None, None, None)
                        except Exception: pass
                await asyncio.sleep(random.uniform(3, 6))
            pv_check_counter += 1
            if pv_check_counter * KEEPALIVE_SECONDS >= PV_HEALTH_SECONDS:
                pv_check_counter = 0
                dead = [aid for aid, t in list(PV_LISTENER_TASKS.items()) if t is None or t.done()]
                if dead:
                    for aid in dead:
                        PV_LISTENER_TASKS.pop(aid, None)
                        st = _PV_STOP_EVENTS.pop(aid, None)
                        if st:
                            try: st.set()
                            except Exception: pass
                    await start_pv_responders()
            await asyncio.sleep(KEEPALIVE_SECONDS)
        except asyncio.CancelledError: raise
        except Exception: await asyncio.sleep(60)

# ═══════════════ Telegram imports ═══════════════
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.error import BadRequest, RetryAfter
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters as tg_filters)
from telegram.request import HTTPXRequest

PAGE_SIZE = 6
def esc(s): return _html.escape(str(s if s is not None else ""))
def short(s, n=40):
    s = str(s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n-1] + "…"

# ═══ BUTTON helpers (no emoji in labels) ═══
def B(label, data): return InlineKeyboardButton(label, callback_data=data)
def SEL(active, label):
    return ("[✓] " if active else "[ ] ") + label
def kb_(*rows): return InlineKeyboardMarkup([list(r) for r in rows if r])
def grid(btns, cols=2):
    return [btns[i:i+cols] for i in range(0, len(btns), cols)]
def nav(back=None, home=True):
    row = []
    if back: row.append(B("« back", back))
    if home: row.append(B("back to panel", "menu:main"))
    return row

# ═══ MESSAGE helpers (SMS style: emoji + small caps + ⤳) ═══
def head(icon, title, sub=None):
    s = f"{{{icon}}} {SC(title)}"
    if sub: s += f"  ({sub})"
    return "\n" + s + "\n" + HLINE() + "\n"
def mrow(emoji, key, value, key_width=16):
    k = SC(str(key))
    pad = " " * max(1, key_width - len(k))
    return f"{emoji}{TICK}{k}{pad}: {value}"
def dots(cur, total):
    return "".join("●" if i <= cur else "○" for i in range(1, total+1)) + f"  {cur}/{total}"
def _bar(pct, n=14):
    fill = max(0, min(n, round(pct * n / 100)))
    return "█" * fill + "░" * (n - fill)
def _eta(sec):
    sec = int(sec)
    if sec < 60: return f"{sec}s"
    if sec < 3600: return f"{sec // 60}m"
    return f"{sec // 3600}h {(sec % 3600) // 60}m"

def authorized(update):
    try: return update.effective_chat.id == FORCED_OWNER
    except Exception: return False

_PANEL_SIG = {}
def _sig(text, kb):
    try: k = json.dumps(kb.to_dict(), sort_keys=True) if kb else ""
    except Exception: k = repr(kb)
    return hashlib.md5((text + "|" + k).encode()).hexdigest()
async def panel(text, kb=None, page_tag=None):
    cid = STATE.get("owner")
    if not cid or APP is None: return
    if page_tag: _set_page(cid, page_tag)
    text = str(text)[:4000]; sig = _sig(text, kb)
    mid = STATE["panel"].get(cid)
    if mid:
        if _PANEL_SIG.get(cid) == (mid, sig): return
        try:
            await APP.bot.edit_message_text(chat_id=cid, message_id=mid, text=text,
                reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            _PANEL_SIG[cid] = (mid, sig); return
        except BadRequest as e:
            if "not modified" in str(e).lower(): _PANEL_SIG[cid] = (mid, sig); return
        except RetryAfter: return
        except Exception: pass
    for attempt in range(3):
        try:
            m = await APP.bot.send_message(chat_id=cid, text=text, reply_markup=kb,
                parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            STATE["panel"][cid] = m.message_id; _PANEL_SIG[cid] = (m.message_id, sig); return
        except RetryAfter as e: await asyncio.sleep(float(e.retry_after) + 0.5)
        except Exception: await asyncio.sleep(1.5 * (attempt + 1))
async def tg_send(text, markup=None, parse_mode=None):
    if not STATE.get("owner") or APP is None: return False
    text = str(text)[:4000]
    for attempt in range(3):
        try:
            await APP.bot.send_message(chat_id=STATE["owner"], text=text,
                reply_markup=markup, parse_mode=parse_mode or "HTML",
                disable_web_page_preview=True)
            return True
        except RetryAfter as e: await asyncio.sleep(float(e.retry_after) + 0.5)
        except Exception as e:
            if "parse entities" in str(e) and parse_mode: parse_mode = None; continue
            await asyncio.sleep(1.5 * (attempt + 1))
    return False
async def ask(text, note=None):
    body = (f"⚠️ {esc(note)}\n\n" if note else "") + text
    await panel(body, kb_([B("cancel", "conv:cancel")]), page_tag="ask")

def log_cb(msg):
    try:
        loop = _loop_ref[0]
        if loop: loop.create_task(tg_send(str(msg)))
    except Exception: pass
def get_conv(cid):
    c = STATE["conv"].get(cid)
    if not c: c = STATE["conv"][cid] = {}
    return c
def clear_conv(cid): STATE["conv"].pop(cid, None)
def _extract_media(msg):
    if msg is None: return None
    for attr in ("photo","video","animation","document","audio","voice","sticker"):
        try:
            v = getattr(msg, attr, None)
            if v:
                if isinstance(v, (list, tuple)) and v: return v[-1]
                return v
        except Exception: continue
    return None
async def _download_tg_file(media_obj, aid, prefix):
    if APP is None: raise RuntimeError("APP not ready")
    if media_obj is None: raise RuntimeError("no_media")
    file_id = getattr(media_obj, "file_id", None)
    if not file_id: raise RuntimeError("no_file_id")
    f = await APP.bot.get_file(file_id)
    ext = os.path.splitext(getattr(f, "file_path", "") or "")[1] or ".bin"
    fname = f"{prefix}_{aid}_{int(time.time())}_{secrets.token_hex(3)}{ext}"
    full = os.path.join(UPLOADS_DIR, fname)
    try: await f.download_to_drive(full)
    except AttributeError:
        data = await f.download_as_bytearray()
        with open(full, "wb") as fp: fp.write(bytes(data))
    if not os.path.exists(full) or os.path.getsize(full) == 0: raise RuntimeError("empty_file")
    return full

_PAGE_STATE = {}
def _set_page(cid, tag):
    try: _PAGE_STATE[int(cid)] = str(tag)
    except Exception: pass
def _is_page(cid, tag):
    try: return _PAGE_STATE.get(int(cid)) == tag
    except Exception: return False

# ═══════════════ STATE ═══════════════
STATE = {"owner": None, "panel": {}, "conv": {},
         "listener_stops": {}, "op_panel": {}, "listener_new_count": 0,
         "cancel_events": {}}
_loop_ref = [None]; TG_TOKEN = ""; FORCED_OWNER = 0; APP = None
_TMP_EDIT = {}

# ═══════════════ panels ═══════════════
async def show_main():
    accounts = list_accounts()
    running = [o for o in _load_ops() if _op_effective_status(o) == "running"]
    pv_enabled = sum(1 for aid in accounts if _load_pv_account(aid).get("enabled"))
    txt = head("🌀", "panel", VERSION)
    txt += mrow("👤", "accounts", len(accounts)) + "\n"
    txt += mrow("💬", "pv enabled", pv_enabled) + "\n"
    txt += mrow("📊", "running ops", len(running) if running else "idle") + "\n"
    txt += mrow("👂", "listener active", sum(1 for t in LISTENER_TASKS.values() if not t.done())) + "\n"
    txt += mrow("💾", "data dir", f"<code>{esc(DATA_DIR)}</code>")
    rows = []
    if running: rows.append([B(f"running ({len(running)})", f"op:view:{running[0]['id']}")])
    rows += [
        [B("send", "send:start"), B("joiner", "jl:start")],
        [B("lefter", "lf:start"), B("templates", "at:menu")],
        [B("accounts", "menu:acc"), B("pv", "menu:pv")],
        [B("stats", "menu:stats"), B("errors", "menu:errors"), B("cache", "menu:cache")],
        [B("listener", "menu:listen"), B("linkdonies", "ld:list:jl:back_to_settings")],
        [B("settings", "menu:cfg")],
    ]
    await panel(txt, kb_(*rows), page_tag="main")

async def show_cache_menu():
    accounts = list_accounts()
    txt = head("🗂", "cache manager") + SC("per-account cache") + "\n\n"
    rows = []
    for aid, a in accounts.items():
        sn = _seen_count(aid); bn = _banned_count(aid); ln = len(_load_ldprog(aid))
        rows.append([B(f"{short(a.get('name','?'), 14)} · seen {sn} · ban {bn} · ld {ln}",
                       f"cache:acc:{aid}")])
    if not accounts: txt += SC("empty")
    rows.append([B("wipe all accounts", "cache:clear_all_accounts")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="cache")

async def show_cache_account(aid):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="cache")
    sn = _seen_count(aid); bn = _banned_count(aid); ln = len(_load_ldprog(aid))
    txt = head("🗂", f"cache · {a.get('name','?')}")
    txt += mrow("🔍", "seen", sn) + "\n"
    txt += mrow("🚫", "banned", bn) + "\n"
    txt += mrow("📡", "linkdoni progress", ln)
    rows = [
        [B("clear seen", f"cache:acc:{aid}:clear_seen"),
         B("clear banned", f"cache:acc:{aid}:clear_banned")],
        [B("clear both", f"cache:acc:{aid}:clear_all"),
         B("reset ld progress", f"cache:acc:{aid}:reset_ld")],
        nav("menu:cache"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"cache:{aid}")

async def show_pv_menu():
    accounts = list_accounts()
    txt = head("💬", "auto-reply pv") + SC("select an account") + "\n\n"
    if not accounts:
        txt += SC("no accounts yet.")
        return await panel(txt, kb_([B("add account", "acc:add")], nav()), page_tag="pv_menu")
    rows = []
    for aid, a in accounts.items():
        cfg = _load_pv_account(aid)
        en = "[on] " if cfg.get("enabled") else "[off] "
        items_n = len(cfg.get("items") or [])
        rows.append([B(f"{en}{short(a.get('name','?'), 20)} · {items_n} msgs", f"pv:acc:{aid}")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="pv_menu")

async def show_pv_account_menu(aid):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="pv_menu")
    cfg = _load_pv_account(aid)
    en = bool(cfg.get("enabled"))
    mx = int(cfg.get("max_replies", 1) or 0)
    items = cfg.get("items") or []
    notify_on = bool(cfg.get("notify", True))
    poll_sec = int(cfg.get("poll_seconds", 5))
    delay_sec = int(cfg.get("delay_seconds", 0))
    pv_task = PV_LISTENER_TASKS.get(aid)
    poller_on = bool(pv_task and not pv_task.done())
    has_custom = _has_pv_account(aid)
    txt = head("💬", f"pv · {a.get('name','?')}")
    txt += mrow("📶", "status", ("on" if en else "off")) + "\n"
    txt += mrow("🔄", "poller", ("on" if poller_on else "off")) + "\n"
    txt += mrow("👥", "max/user", (mx if mx else "∞")) + "\n"
    txt += mrow("⏱", "delay", f"{delay_sec}s") + "\n"
    txt += mrow("🔔", "notify", ("on" if notify_on else "off")) + "\n"
    txt += mrow("🔄", "poll", f"{poll_sec}s") + "\n"
    txt += mrow("📨", "items", f"{len(items)}")
    if has_custom: txt += "  (custom)"
    txt += "\n\n"
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"{i}. text: <code>{esc(short(it.get('text',''), 40))}</code>\n"
        elif k == "file": txt += f"{i}. file: <code>{esc(os.path.basename(it.get('file_path','?')))}</code>\n"
        elif k == "delay": txt += f"{i}. delay {it.get('seconds',3)}s\n"
    rows = [
        [B("turn off" if en else "turn on", f"pv:acc:{aid}:toggle")],
        [B(f"max: {mx if mx else '∞'}", f"pv:acc:{aid}:cycle_max"),
         B("delay", f"pv:acc:{aid}:set_delay")],
        [B("+ text", f"pv:acc:{aid}:add_text"),
         B("+ file", f"pv:acc:{aid}:add_saved"),
         B("+ delay", f"pv:acc:{aid}:add_delay")],
        [B("items", f"pv:acc:{aid}:list"),
         B("report", f"pv:acc:{aid}:report:0")],
        [B("notify " + ("on" if notify_on else "off"), f"pv:acc:{aid}:toggle_notify"),
         B(f"poll {poll_sec}s", f"pv:acc:{aid}:set_poll")],
        [B("reset counter", f"pv:acc:{aid}:clear_replies"),
         B("reset custom", f"pv:acc:{aid}:reset_to_global")],
        [B("restart", f"pv:acc:{aid}:restart")],
        nav("menu:pv"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"pv_acc:{aid}")

async def show_pv_account_list(aid):
    cfg = _load_pv_account(aid); items = cfg.get("items") or []
    a = get_account(aid)
    txt = head("📋", f"pv items · {a.get('name','?') if a else aid}")
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"\n{i}. text: <code>{esc(short(it.get('text',''), 60))}</code>"
        elif k == "file": txt += f"\n{i}. file: <code>{esc(os.path.basename(it.get('file_path','?')))}</code>"
        elif k == "delay": txt += f"\n{i}. delay: {it.get('seconds',3)}s"
    rows = [[B(f"del {i+1}", f"pv:acc:{aid}:del:{i}")] for i in range(len(items))]
    rows.append([B("« back", f"pv:acc:{aid}")])
    await panel(txt, kb_(*rows), page_tag=f"pv_list:{aid}")

async def show_pv_account_report(aid, page=0):
    rep = _load_pv_report(); users = rep.get(aid) or {}
    rows_data = []
    for uid, data in users.items():
        rows_data.append({"uid": uid, "first_name": data.get("first_name") or "",
                          "count": data.get("count", 1), "replied": data.get("replied", False),
                          "reply_ok": data.get("reply_ok", False),
                          "blocked": data.get("blocked", False),
                          "error": data.get("error"), "last_seen": data.get("last_seen", 0)})
    rows_data.sort(key=lambda x: x["last_seen"], reverse=True)
    PER = 8; pages = max(1, -(-len(rows_data) // PER)); page = max(0, min(page, pages - 1))
    chunk = rows_data[page * PER:(page + 1) * PER]
    a = get_account(aid)
    txt = head("📊", f"pv report · {a.get('name','?') if a else aid}")
    txt += mrow("👥", "total", len(rows_data)) + f"   ·   page {page+1}/{pages}\n\n"
    for r in chunk:
        name = r["first_name"] or "?"
        st = "✓" if r["replied"] and r["reply_ok"] else ("✗" if r["replied"] else "·")
        if r["blocked"]: st += "!"
        ago = int(time.time() - r["last_seen"])
        txt += f"{st} <b>{esc(short(name, 20))}</b> · x{r['count']} · {_eta(ago)}\n"
        if r.get("error"): txt += f"   <code>{esc(short(r['error'], 50))}</code>\n"
    nav_btns = []
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("« prev", f"pv:acc:{aid}:report:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("next »", f"pv:acc:{aid}:report:{page+1}"))
        nav_btns.append(pr)
    nav_btns.append([B("« back", f"pv:acc:{aid}")])
    await panel(txt, kb_(*nav_btns), page_tag=f"pv_rep:{aid}:{page}")

def _accounts_view(page):
    accounts = list_accounts(); items = list(accounts.items())
    pages = max(1, -(-len(items) // PAGE_SIZE)); page = max(0, min(page, pages - 1))
    chunk = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    rows = []
    for aid, a in chunk:
        cfg = _load_pv_account(aid)
        pv = "on" if cfg.get("enabled") else "off"
        n_ch = len(a.get("channels", []))
        rows.append([B(f"{short(a.get('name','?'), 14)} · pv:{pv} · ch:{n_ch}",
                       f"acc:view:{aid}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("« prev", f"acc:page:{page - 1}"))
        pr.append(B(f"{page + 1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("next »", f"acc:page:{page + 1}"))
        rows.append(pr)
    rows.append([B("+ add account", "acc:add")])
    rows.append(nav())
    txt = head("👤", f"accounts", len(accounts))
    return txt, kb_(*rows), f"acc_list:{page}", chunk

async def show_accounts(page=0):
    txt, kb, tag, chunk = _accounts_view(page)
    await panel(txt, kb, page_tag=tag)

async def show_account_detail(aid):
    tag = f"acc:{aid}"; a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="main")
    t = LISTENER_TASKS.get(aid); on = bool(t and not t.done())
    pvt = PV_LISTENER_TASKS.get(aid); pvon = bool(pvt and not pvt.done())
    pvc = _load_pv_account(aid)
    sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    rp_exists = os.path.exists(sess + ".rp")
    txt = head("👤", a.get("name", "?"))
    txt += mrow("📞", "phone", f"<code>{esc(a.get('phone','—'))}</code>") + "\n"
    txt += mrow("🆔", "id", f"<code>{esc(aid)}</code>") + "\n"
    txt += mrow("📢", "channels", len(get_stored_channels(aid))) + "\n"
    txt += mrow("👂", "listener", ("on" if on else "off")) + "\n"
    txt += mrow("💬", "pv", ("on" if pvon else "off")) + "\n"
    txt += mrow("🔍", "seen", _seen_count(aid)) + "\n"
    txt += mrow("🚫", "banned", _banned_count(aid)) + "\n"
    txt += mrow("💾", "session.rp", ("yes" if rp_exists else "no"))
    rows = grid([
        B("auto-tar", f"acc:at:{aid}"), B("channels", f"ch:menu:{aid}"),
        B("profile", f"prof:menu:{aid}"), B(("turn listener off" if on else "turn listener on"), f"listen:toggle:{aid}"),
        B("pv", f"pv:acc:{aid}"), B("photo", f"accphoto:menu:{aid}"),
        B("lefter", f"acc:lf:{aid}"), B("cache", f"cache:acc:{aid}"),
    ])
    rows.append([B("delete account", f"acc:del:{aid}")])
    rows.append(nav("menu:acc"))
    await panel(txt, kb_(*rows), page_tag=tag)

async def show_profile_menu(aid):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="main")
    rows = grid([
        B("first name", f"prof:set:first:{aid}"),
        B("last name", f"prof:set:last:{aid}"),
        B("bio", f"prof:set:about:{aid}"),
        B("username", f"prof:set:username:{aid}"),
        B("photo", f"accphoto:menu:{aid}"),
    ])
    rows.append(nav(f"acc:view:{aid}"))
    txt = head("✏️", "profile", a.get("name", "?"))
    txt += mrow("📞", "phone", f"<code>{esc(a.get('phone','—'))}</code>")
    await panel(txt, kb_(*rows), page_tag=f"prof:{aid}")

async def show_acc_photo_menu(aid):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="main")
    rows = [
        [B("set new photo", f"accphoto:set:{aid}")],
        [B("delete photos", f"accphoto:del:{aid}")],
        nav(f"acc:view:{aid}"),
    ]
    await panel(head("🖼", "profile photo", a.get("name","?")), kb_(*rows), page_tag=f"accphoto:{aid}")

async def show_ch_photo_menu(aid, idx):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="main")
    chs = get_stored_channels(aid)
    if idx < 0 or idx >= len(chs): return await show_ch_list(aid)
    ch = chs[idx]
    rows = [
        [B("set new photo", f"chphoto:set:{aid}:{idx}")],
        [B("delete photo", f"chphoto:del:{aid}:{idx}")],
        nav(f"ch:view:{aid}:{idx}"),
    ]
    await panel(head("🖼", "channel photo", ch.get("title","?")), kb_(*rows), page_tag=f"chphoto:{aid}:{idx}")

def _ch_link(ch):
    un = (ch.get("username") or "").lstrip("@")
    return ch.get("join_link") or (f"@{un}" if un else "")

async def show_ch_menu(aid):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="main")
    n = len(get_stored_channels(aid))
    txt = head("📢", "channels", a.get("name", "?"))
    txt += mrow("✨", "created", n)
    rows = [[B(f"my channels ({n})", f"chlist:show:{aid}:0")],
            [B("create new channel", f"chnew:start:{aid}")],
            nav(f"acc:view:{aid}")]
    await panel(txt, kb_(*rows), page_tag=f"ch_menu:{aid}")

async def show_ch_list(aid, page=0):
    channels = get_stored_channels(aid); per = 6
    pages = max(1, -(-len(channels) // per)); page = max(0, min(page, pages - 1))
    rows = []
    for idx, ch in list(enumerate(channels))[page*per:(page+1)*per]:
        icon = "pub" if (ch.get("is_public") or ch.get("username")) else "prv"
        lbl = f"[{icon}] {short(ch.get('title','?'), 24)}"
        if ch.get("username"): lbl += f" · @{ch['username']}"
        rows.append([B(lbl, f"ch:view:{aid}:{idx}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("« prev", f"chlist:show:{aid}:{page - 1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("next »", f"chlist:show:{aid}:{page + 1}"))
        rows.append(pr)
    rows.append([B("create channel", f"chnew:start:{aid}")])
    rows.append(nav(f"ch:menu:{aid}"))
    txt = head("📋", "my channels", len(channels))
    if not channels: txt += SC("no channels created yet.")
    await panel(txt, kb_(*rows), page_tag=f"chlist:{aid}:{page}")

async def show_channel_view(aid, idx):
    if not get_account(aid): return await panel("not found.", kb_(nav()), page_tag="main")
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return await show_ch_list(aid)
    ch = channels[idx]
    un = ch.get("username") or ""
    is_pub = ch.get("is_public") or bool(un)
    link = _ch_link(ch)
    txt = head("📢", ch.get("title") or "?")
    txt += mrow("🔖", "type", ("public" if is_pub else "private")) + "\n"
    if un: txt += mrow("🔤", "username", f"@{esc(un)}") + "\n"
    txt += mrow("🔗", "link", (f"<code>{esc(link)}</code>" if link else "not set"))
    rows = grid([
        B("send", f"chsend:start:{aid}:{idx}"),
        B("profile", f"chprof:show:{aid}:{idx}"),
        B("get link", f"ch:getlink:{aid}:{idx}"),
        B("set link", f"ch:setlink:{aid}:{idx}"),
        B("photo", f"chphoto:menu:{aid}:{idx}"),
        B("file", f"chfile:start:{aid}:{idx}"),
        B("delete", f"ch:del:{aid}:{idx}"),
    ])
    rows.append(nav(f"chlist:show:{aid}:0"))
    await panel(txt, kb_(*rows), page_tag=f"chview:{aid}:{idx}")

async def show_ch_profile(aid, idx):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="main")
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return await show_ch_list(aid)
    ch = channels[idx]
    un = ch.get("username") or ""
    txt = head("✏️", ch.get("title", "?"))
    txt += mrow("🔖", "type", ("public" if (ch.get("is_public") or un) else "private")) + "\n"
    if un: txt += mrow("🔤", "username", f"@{esc(un)}") + "\n"
    link = _ch_link(ch)
    txt += mrow("🔗", "link", (f"<code>{esc(link)}</code>" if link else "—")) + "\n"
    txt += mrow("📖", "description", f"<code>{esc(short(ch.get('description',''), 100) or '—')}</code>")
    rows = [
        [B("title", f"chprof:edit:title:{aid}:{idx}"),
         B("description", f"chprof:edit:desc:{aid}:{idx}")],
        [B("username", f"chprof:edit:user:{aid}:{idx}"),
         B("photo", f"chphoto:menu:{aid}:{idx}")],
        [B("refresh link", f"ch:getlink:{aid}:{idx}")],
        nav(f"ch:view:{aid}:{idx}"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"chprof:{aid}:{idx}")

async def show_ch_new_type(aid, title):
    txt = head("🏗", "create channel") + mrow("📝", "title", title) + "\n\n" + SC("select type") + ":"
    await panel(txt, kb_(
        [B("public", f"chnew:pub:{aid}"), B("private", f"chnew:priv:{aid}")],
        [B("cancel", f"ch:menu:{aid}")]), page_tag=f"chnew_type:{aid}")

async def show_listen_menu():
    accounts = list_accounts()
    enabled = _listener_cfg_enabled(); service_only = _listener_cfg_service_only()
    txt = head("👂", "listener")
    txt += mrow("📶", "status", ("on" if enabled else "off")) + "\n"
    txt += mrow("🔍", "service only", ("on" if service_only else "off")) + "\n\n"
    rows = []
    for aid, a in accounts.items():
        t = LISTENER_TASKS.get(aid); run = t is not None and not t.done()
        rows.append([B(f"[{'on' if run else 'off'}] {short(a.get('name','?'), 14)}",
                       f"listen:toggle:{aid}")])
    rows.append([B("restart all", "listen:restart"), B("cfg", "listen:cfg")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="listen")

async def show_linkdonies(back_to="jl:back_to_settings"):
    lst = load_link_donies()
    auto = int(_load(CFG_FILE, DEFAULT_CFG).get("auto_join_linkdoni", 1))
    txt = head("📡", "linkdonies", len(lst))
    txt += mrow("🔁", "auto-join", ("on" if auto else "off")) + "\n"
    txt += SC("progress per account") + "\n\n"
    for i, url in enumerate(lst):
        txt += f"{i + 1}. <code>{esc(url)}</code>\n"
    rows = grid([B(f"del {i+1}. {short(u.split('/')[-1], 12)}", f"ld:del:{i}:{back_to}")
                 for i, u in enumerate(lst)])
    rows.append([B("+ add", f"ld:add:{back_to}"),
                 B(("turn auto off" if auto else "turn auto on"), f"ld:toggle_autojoin:{back_to}")])
    rows.append([B("reset all progress", f"ld:reset_prog:{back_to}")])
    rows.append([B("reset list", f"ld:reset:{back_to}")])
    rows.append(nav(back_to, home=False))
    await panel(txt, kb_(*rows), page_tag="linkdonies")

_OP_LAST = {}
def _op_view(op):
    oid = op["id"]; t = op.get("type")
    st = _op_effective_status(op); s = _op_stats(op); p = op.get("progress") or {}
    tot = s["total"] or 0; proc = s["done"] + s["failed"]
    pct = min(100, int(proc * 100 / tot)) if tot else 0
    icon = {"joinlef":"🤝","lefter":"🚪","autotar":"🎯","send":"📤"}.get(t, "⚙️")
    label = {"joinlef":"joiner","lefter":"lefter","autotar":"auto-tar","send":"send"}.get(t, "?")
    txt = head(icon, label, oid[-6:])
    txt += f"{SC(_op_status_label(st))}\n"
    txt += f"<code>{_bar(pct)} {pct}%</code>\n\n"
    if t in ("joinlef", "autotar"):
        txt += f"🤝 joined: <b>{s['done']}</b>   ✗ failed: <b>{s['failed']}</b>"
        if op.get("max_join"): txt += f"   🎯 {op['max_join']}"
        if s.get("already"): txt += f"\n♻️ already member: <b>{s['already']}</b>"
        if s.get("sent"):    txt += f"\n📤 sent: <b>{s['sent']}</b>"
        if s.get("left"):    txt += f"\n🚪 left: <b>{s['left']}</b>"
        if s.get("tried"):   txt += f"\n🔗 tried: <b>{s['tried']}</b>"
        if s.get("skipped_seen"):   txt += f"\n🔍 seen: <b>{s['skipped_seen']}</b>"
        if s.get("skipped_banned"): txt += f"\n🚫 banned: <b>{s['skipped_banned']}</b>"
        if s.get("rejected"): txt += f"\n🟡 inactive: <b>{s['rejected']}</b>"
        if s.get("wave"):  txt += f"\n🌊 wave: <b>{s['wave']}</b>"
        if s.get("round"): txt += f"   ·   🔁 round: <b>{s['round']}</b>"
    elif t == "lefter":
        txt += f"🚪 left: <b>{s['done']}</b>   ✗ failed: <b>{s['failed']}</b>"
    else:
        txt += f"✓ sent: <b>{s['done']}</b>   ✗ failed: <b>{s['failed']}</b>   pending: <b>{s['pending']}</b>"
        if s.get("blocked"): txt += f"\n🚫 blocked: {s['blocked']}"
        if s.get("round"):   txt += f"   ·   🔁 round: {s['round']}"
    txt += f"\n\n{SC('phase')} : {p.get('phase','—')}"
    rows = []
    if st == "running": rows.append([B("stop", f"op:stop:{oid}")])
    rows.append([B("« stats", "menu:stats"), B("back to panel", "menu:main")])
    return txt, kb_(*rows)

async def _refresh_op_panel(op_id, force=False):
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
    if not op: return await panel("not found.", kb_(nav()), page_tag="main")
    cid = STATE.get("owner")
    if cid: STATE.setdefault("op_panel", {})[cid] = oid
    txt, kb = _op_view(op)
    await panel(txt, kb, page_tag=f"op:{oid}")

async def show_stats():
    ops = _load_ops(); ops.sort(key=lambda o: o.get("created", 0), reverse=True)
    errs = _load_errors()
    done = sum(_op_stats(o)["done"] for o in ops); failed = sum(_op_stats(o)["failed"] for o in ops)
    running = [o for o in ops if _op_effective_status(o) == "running"]
    txt = head("📊", "stats")
    txt += mrow("✓", "done", done) + "\n"
    txt += mrow("✗", "failed", failed) + "\n"
    txt += mrow("⚠️", "errors", len(errs)) + "\n"
    txt += mrow("📥", "listener new", STATE.get("listener_new_count", 0))
    if running:
        txt += f"\n\n{SC('running now')}:\n"
        for o in running[:3]:
            s = _op_stats(o)
            txt += f"• {_op_short_title(o, 22)}  ✓{s['done']} ✗{s['failed']}\n"
    rows = []
    for o in ops[:8]:
        s = _op_stats(o); prog = f"{s['done']}/{s['total']}" if s["total"] else "—"
        rows.append([B(f"{_op_short_title(o, 20)} · {prog}", f"op:view:{o['id']}")])
    rows.append([B("errors", "menu:errors"), B("back to panel", "menu:main")])
    await panel(txt, kb_(*rows), page_tag="stats")

async def show_errors(page=0):
    errors = list(reversed(_load_errors()))
    if not errors:
        return await panel(head("⚠️", "errors") + SC("none"), kb_(nav()), page_tag="errors")
    PER = 4; pages = max(1, -(-len(errors) // PER)); page = max(0, min(page, pages - 1))
    txt = head("⚠️", "errors", len(errors))
    for e in errors[page * PER:(page + 1) * PER]:
        t = time.strftime("%m/%d %H:%M", time.localtime(e.get("time", 0)))
        txt += f"\n🕐 <code>{esc(t)}</code> · <b>{esc(e.get('source','?'))}</b>\n<code>{esc(str(e.get('error',''))[:220])}</code>\n"
    rows = []
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("« prev", f"err:page:{page - 1}"))
        pr.append(B(f"{page + 1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("next »", f"err:page:{page + 1}"))
        rows.append(pr)
    rows.append([B("clear", "err:clear"), B("back to panel", "menu:main")])
    await panel(txt, kb_(*rows), page_tag=f"errors:{page}")

async def show_cfg():
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    txt = head("⚙️", "settings")
    for k in ("join_delay","wave_size","extract_limit","wait_for_links_sec",
              "auto_join_linkdoni","listener"):
        txt += mrow("•", k, cfg.get(k, DEFAULT_CFG.get(k))) + "\n"
    rows = [
        [B("join delay", "cfg:set:join_delay"), B("wave size", "cfg:set:wave_size")],
        [B("extract limit", "cfg:set:extract_limit"),
         B("wait for links", "cfg:set:wait_for_links_sec")],
        [B("toggle auto-join", "cfg:toggle_autojoin")],
        [B("toggle listener", "cfg:toggle_listener")],
        nav(),
    ]
    await panel(txt, kb_(*rows), page_tag="cfg")

# ═══════════════ Send wizard ═══════════════
def _send_conv(cid):
    c = get_conv(cid)
    if "send" not in c:
        c["send"] = {"step":"accounts", "accounts":[], "payload":None,
                     "target":"both", "max":0, "auto_left":False,
                     "edit_delay_enabled":False, "edit_delay_seconds":3.0,
                     "edit_delay_random":False, "edit_delay_min":2.0, "edit_delay_max":6.0,
                     "placeholder_text":"hi", "placeholder_random":False,
                     "placeholder_list":"hi,hey,hello,yo",
                     "multi_step_edit":False, "multi_step_middle":"Hi",
                     "attach_file":"", "groups_only":True,
                     "infinite_loop":False, "loop_delay":3.0, "rescan_targets":True}
    return c["send"]
def _send_summary(s):
    accs = s.get("accounts") or []; all_a = list_accounts()
    if "all" in accs: al = f"all ({len(all_a)})"
    elif not accs: al = "—"
    else:
        names = [get_account(i).get("name","?") for i in accs[:2] if get_account(i)]
        al = ", ".join(names) + (f" +{len(accs) - 2}" if len(accs) > 2 else "")
    p = s.get("payload")
    tgt = {"pv":"pv", "groups":"groups", "both":"both"}.get(s.get("target","both"), "?")
    mx = s.get("max", 0) or 0
    ed = "on" if s.get("edit_delay_enabled") else "off"
    af = "yes" if s.get("attach_file") else "no"
    inf = "on" if s.get("infinite_loop") else "off"
    return (f"\n" + mrow("👤", "accounts", al) + "\n"
            + mrow("✉️", "message", (f"«{short(p.get('text'), 30)}»" if p else "—")) + "\n"
            + mrow("🎯", "target", tgt) + "\n"
            + mrow("🔢", "max", (mx if mx else "∞")) + "\n"
            + mrow("🎭", "edit delay", ed) + "\n"
            + mrow("📎", "attach", af) + "\n"
            + mrow("🔁", "loop", inf))

async def send_step_accounts(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel("add an account first.", kb_([B("add account", "acc:add")], nav()), page_tag="send:1")
    sel = set(s.get("accounts") or []); all_sel = "all" in sel
    btns = [B(SEL((all_sel or aid in sel), short(a.get('name','?'), 14)), f"send:acc:{aid}")
            for aid, a in accounts.items()]
    rows = grid(btns)
    rows.append([B(("unselect all" if all_sel else "select all"), "send:accall"),
                 B("next »", "send:accnext")])
    rows.append([B("cancel", "send:cancel")])
    txt = head("📤", "send", dots(1, 4)) + SC("select accounts") + _send_summary(s)
    await panel(txt, kb_(*rows), page_tag="send:1")

async def send_step_compose(cid, s):
    txt = head("📤", "send", dots(2, 4)) + SC("send the message text") + _send_summary(s)
    rows = []
    if s.get("payload"):
        rows.append([B("change message", "send:recompose"), B("next »", "send:composenext")])
    rows.append([B("« back", "send:prev"), B("cancel", "send:cancel")])
    await panel(txt, kb_(*rows), page_tag="send:2")

async def send_step_target(cid, s):
    t = s.get("target", "both")
    mk = lambda k, lbl: B(SEL(t == k, lbl), f"send:tgt:{k}")
    ed_on = bool(s.get("edit_delay_enabled", False))
    ed_sec = s.get("edit_delay_seconds", 3.0)
    grp_only = bool(s.get("groups_only", True))
    inf_on = bool(s.get("infinite_loop", False))
    ld = s.get("loop_delay", 3.0)
    rs = bool(s.get("rescan_targets", True))
    af = s.get("attach_file") or ""
    rows = [[mk("pv", "pv only"), mk("groups", "groups only"), mk("both", "both")],
            [B(SEL(grp_only, "real groups only"), "send:toggle_groups_only")],
            [B(SEL(inf_on, "infinite loop"), "send:toggle_infinite")],
            [B(f"loop delay: {ld}s", "send:loop_delay")],
            [B(SEL(rs, "rescan each round"), "send:toggle_rescan")],
            [B(SEL(ed_on, "edit delay"), "send:toggle_edit")],
            [B(f"{ed_sec}s", "send:edit_sec"),
             B(SEL(s.get("edit_delay_random"), "random"), "send:toggle_edit_rand")],
            [B(f"placeholder: {short(s.get('placeholder_text','hi'), 10)}", "send:edit_ph"),
             B(SEL(s.get("placeholder_random"), "list"), "send:toggle_ph_rand")],
            [B(SEL(s.get("multi_step_edit"), "multi-step edit"), "send:toggle_multi")],
            [B(f"attach: {short(os.path.basename(af), 15) if af else 'none'}", "send:attach")],
            [B(SEL(s.get("auto_left"), "auto leave"), "send:toggle_auto_left")],
            [B("next »", "send:tgtnext")],
            [B("« back", "send:prev"), B("cancel", "send:cancel")]]
    txt = head("📤", "send", dots(3, 4)) + SC("select target") + _send_summary(s)
    await panel(txt, kb_(*rows), page_tag="send:3")

async def send_step_max(cid, s):
    mx = s.get("max", 0)
    mk = lambda n: B(SEL(mx == n, str(n)), f"send:max:{n}")
    rows = [[mk(50), mk(100), mk(500)],
            [mk(1000), mk(2000), mk(5000)],
            [B(SEL(mx == 0, "unlimited"), "send:max:0"),
             B("custom", "send:max:custom")],
            [B("confirm »", "send:maxnext")],
            [B("« back", "send:prev"), B("cancel", "send:cancel")]]
    txt = head("📤", "send", dots(4, 4)) + SC("max messages") + _send_summary(s)
    await panel(txt, kb_(*rows), page_tag="send:4")

async def send_step_confirm(cid, s):
    accounts = list_accounts(); sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "accounts"; return await panel("no account selected.", kb_(nav()), page_tag="send:1")
    if not s.get("payload"):
        s["step"] = "compose"; return await panel("no message.", kb_(nav()), page_tag="send:2")
    extra = ""
    if s.get("infinite_loop"):
        extra = "\n" + mrow("🔁", "infinite loop", "on") + f"  ·  delay {s.get('loop_delay',3)}s"
    txt = head("📤", "confirm") + _send_summary(s) + extra
    await panel(txt, kb_(
        [B("start now", "send:go")],
        [B("edit", "send:back_edit"), B("cancel", "send:cancel")]),
        page_tag="send:confirm")

async def show_send_step(cid):
    s = _send_conv(cid); step = s["step"]
    if step == "accounts":  await send_step_accounts(cid, s)
    elif step == "compose": await send_step_compose(cid, s)
    elif step == "target":  await send_step_target(cid, s)
    elif step == "max":     await send_step_max(cid, s)
    elif step == "confirm": await send_step_confirm(cid, s)

# ═══════════════ Joiner UI ═══════════════
def _jl_conv(cid):
    c = get_conv(cid)
    if "jl" not in c:
        c["jl"] = {"step":"account", "accounts":[], "max_join":0, "speed":"fast", "groups_only":True}
    return c["jl"]
async def jl_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel("add an account first.", kb_([B("add account", "acc:add")], nav()), page_tag="jl:1")
    sel = set(s.get("accounts") or [])
    rows = grid([B(SEL(aid in sel, short(a.get('name','?'), 14)), f"jl:acc:{aid}")
                 for aid, a in accounts.items()])
    rows.append([B("next »", "jl:next")])
    rows.append([B("back to panel", "menu:main")])
    txt = head("🤝", "joiner", dots(1, 3)) + mrow("👤", "selected", len(sel))
    await panel(txt, kb_(*rows), page_tag="jl:1")
async def jl_step_settings(cid, s):
    speed = s.get("speed", "fast"); lds = load_link_donies()
    lbl = next((l for k, l, _ in JL_SPEEDS if k == speed), "—")
    grp = "on" if s.get("groups_only", True) else "off"
    txt = head("🤝", "joiner", dots(2, 3))
    txt += mrow("🚀", "speed", lbl) + "\n"
    txt += mrow("📡", "linkdonies", len(lds)) + "\n"
    txt += mrow("👥", "groups only", grp)
    rows = grid([B(SEL(speed == k, l), f"jl:speed:{k}") for k, l, _ in JL_SPEEDS])
    rows.append([B(f"linkdonies ({len(lds)})", "jl:linkdonies")])
    rows.append([B(SEL(s.get("groups_only", True), "real groups only"), "jl:toggle_groups_only")])
    rows.append([B("next »", "jl:next")])
    rows.append(nav("jl:back"))
    await panel(txt, kb_(*rows), page_tag="jl:2")
async def jl_step_max(cid, s):
    mx = s.get("max_join", 0)
    mk = lambda n: B(SEL(mx == n, str(n)), f"jl:max:{n}")
    txt = head("🤝", "joiner", dots(3, 3)) + mrow("🎯", "max join", (mx if mx else "unlimited"))
    rows = [[mk(50), mk(100), mk(200)],
            [mk(500), mk(1000), mk(2000)],
            [B("custom", "jl:max:custom")]]
    if mx: rows.append([B("start »", "jl:go")])
    rows.append(nav("jl:back"))
    await panel(txt, kb_(*rows), page_tag="jl:3")
async def show_jl_step(cid):
    s = _jl_conv(cid)
    if s["step"] == "account":  await jl_step_account(cid, s)
    if s["step"] == "settings": await jl_step_settings(cid, s)
    if s["step"] == "max":      await jl_step_max(cid, s)

# ═══════════════ Lefter UI ═══════════════
def _lf_conv(cid):
    c = get_conv(cid)
    if "lf" not in c: c["lf"] = {"step":"account", "accounts":[], "mode":"all", "delay":0.8}
    return c["lf"]
LF_MODES = [("all","all chats"),
            ("groups","groups only"),
            ("channels","channels only"),
            ("closed","closed groups")]
async def lf_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel("add an account first.", kb_([B("add account", "acc:add")], nav()), page_tag="lf:1")
    sel = set(s.get("accounts") or [])
    rows = grid([B(SEL(aid in sel, short(a.get('name','?'), 14)), f"lf:acc:{aid}")
                 for aid, a in accounts.items()])
    rows.append([B("next »", "lf:next")])
    rows.append([B("back to panel", "menu:main")])
    txt = head("🚪", "lefter", dots(1, 3)) + mrow("👤", "selected", len(sel))
    await panel(txt, kb_(*rows), page_tag="lf:1")
async def lf_step_mode(cid, s):
    mode = s.get("mode", "all")
    btns = [B(SEL(mode == k, l), f"lf:mode:{k}") for k, l in LF_MODES]
    rows = [[b] for b in btns]
    rows.append([B("next »", "lf:next")])
    rows.append(nav("lf:back"))
    txt = head("🚪", "lefter", dots(2, 3)) + SC("select mode")
    await panel(txt, kb_(*rows), page_tag="lf:2")
async def lf_step_delay(cid, s):
    d = s.get("delay", 0.8)
    mk = lambda n, l: B(SEL(abs(d - n) < 0.01, l), f"lf:delay:{n}")
    txt = head("🚪", "lefter", dots(3, 3)) + mrow("⏱", "delay", f"{d}s")
    rows = [[mk(0.3, "0.3s"), mk(0.8, "0.8s"), mk(1.5, "1.5s")],
            [mk(3.0, "3s")],
            [B("start »", "lf:go")],
            nav("lf:back")]
    await panel(txt, kb_(*rows), page_tag="lf:3")
async def show_lf_step(cid):
    s = _lf_conv(cid)
    if s["step"] == "account": await lf_step_account(cid, s)
    if s["step"] == "mode":    await lf_step_mode(cid, s)
    if s["step"] == "delay":   await lf_step_delay(cid, s)

# ═══════════════ Templates UI ═══════════════
async def show_at_menu():
    tpls = list_templates()
    txt = head("🎯", "templates", len(tpls))
    txt += SC("template = full config set") + "\n"
    rows = []
    for tid, t in list(tpls.items())[:8]:
        parts = []
        if t.get("channel", {}).get("title"):
            parts.append("pub" if t.get("channel", {}).get("type") == "public" else "prv")
        if t.get("profile", {}).get("first_name") or t.get("profile", {}).get("bio"): parts.append("prof")
        if int(t.get("joiner", {}).get("max_join", 0) or 0) > 0: parts.append("join")
        if t.get("sender", {}).get("text"): parts.append("send")
        if t.get("sender", {}).get("infinite_loop"): parts.append("loop")
        if t.get("sender", {}).get("attach_file"): parts.append("file")
        if t.get("pv", {}).get("items"): parts.append("pv")
        if t.get("lefter", {}).get("leave_mode"): parts.append("leave")
        badge = " ".join(parts) or "empty"
        rows.append([B(f"{short(t.get('name','?'), 16)} · {badge}", f"at:{tid}:view")])
    rows.append([B("+ new template", "at:new")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="at:menu")

async def show_at_view(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    ch = t.get("channel", {}); pr = t.get("profile", {})
    jn = t.get("joiner", {}); sn = t.get("sender", {})
    lf = t.get("lefter", {}); pv = t.get("pv", {})
    def badge(d, key): return "on" if d.get(key) else "off"
    def badge_n(d, key): return "on" if int(d.get(key, 0) or 0) > 0 else "off"
    txt = head("🎯", t.get("name", "?"))
    txt += mrow("🏗", "channel", badge(ch, "title"))
    if ch.get("title"): txt += f" ({esc(short(ch['title'],20))})"
    txt += "\n"
    txt += mrow("✏️", "profile", (badge(pr, "first_name") if pr.get("first_name") else badge(pr, "bio") if pr.get("bio") else badge(pr, "username"))) + "\n"
    txt += mrow("🤝", "join", badge_n(jn, "max_join"))
    if int(jn.get("max_join", 0) or 0) > 0: txt += f" ({jn['max_join']})"
    txt += "\n"
    txt += mrow("📤", "send", badge(sn, "text")) + "\n"
    txt += mrow("💬", "pv", (badge(pv, "enabled") + f" · {len(pv.get('items') or [])} items")) + "\n"
    txt += mrow("🚪", "lefter", lf.get("leave_mode", "?"))
    rows = grid([
        B("channel", f"at:{tid}:ch"), B("profile", f"at:{tid}:pr"),
        B("joiner", f"at:{tid}:jn"), B("sender", f"at:{tid}:sn"),
        B("pv", f"at:{tid}:pv"), B("lefter", f"at:{tid}:lf"),
        B("rename", f"at:{tid}:rename"),
    ])
    rows.append([B("run on accounts", f"at:{tid}:run")])
    rows.append([B("delete", f"at:{tid}:del"), B("back to panel", "menu:main")])
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:view")

async def show_at_channel(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    c = t.get("channel", {})
    is_pub = c.get("type", "private") == "public"
    txt = head("🏗", "channel", t.get("name", "?"))
    txt += mrow("🔖", "type", ("public" if is_pub else "private")) + "\n"
    txt += mrow("📝", "title", c.get("title") or "—") + "\n"
    if is_pub: txt += mrow("🔤", "username", c.get("username") or "—") + "\n"
    txt += mrow("📖", "about", short(c.get("about", ""), 40) or "—") + "\n"
    txt += mrow("🖼", "photo", os.path.basename(c.get("photo_file", "")) or "—") + "\n"
    txt += "\n" + SC("vars") + ": <code>{n} {rnd} {Link_private}</code>"
    rows = [
        [B(SEL(is_pub, "public"), f"at:{tid}:chtype:public"),
         B(SEL(not is_pub, "private"), f"at:{tid}:chtype:private")],
        [B("title", f"at:{tid}:chset:title")],
    ]
    if is_pub: rows.append([B("username", f"at:{tid}:chset:username")])
    rows.append([B("about", f"at:{tid}:chset:about")])
    rows.append([B("photo", f"at:{tid}:chset:photo_file")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:ch")

async def show_at_profile(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    p = t.get("profile", {})
    txt = head("✏️", "profile", t.get("name", "?"))
    txt += mrow("👤", "first name", p.get("first_name") or "—") + "\n"
    txt += mrow("👤", "last name", p.get("last_name") or "—") + "\n"
    txt += mrow("🔤", "username", p.get("username") or "—") + "\n"
    txt += mrow("📖", "bio", short(p.get("bio", ""), 60) or "—") + "\n"
    txt += mrow("🖼", "photo", os.path.basename(p.get("photo_file", "")) or "—")
    rows = [
        [B("first name", f"at:{tid}:prset:first_name"),
         B("last name", f"at:{tid}:prset:last_name")],
        [B("username", f"at:{tid}:prset:username"),
         B("bio", f"at:{tid}:prset:bio")],
        [B("photo", f"at:{tid}:prset:photo_file")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:pr")

async def show_at_joiner(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    j = t.get("joiner", {})
    txt = head("🤝", "joiner", t.get("name", "?"))
    txt += mrow("🎯", "max join", j.get("max_join", 0)) + "\n"
    txt += mrow("🚀", "speed", next((l for k, l, _ in JL_SPEEDS if k == j.get("speed")), j.get("speed"))) + "\n"
    txt += mrow("👥", "groups only", ("on" if j.get("groups_only", True) else "off"))
    rows = [[B("max join", f"at:{tid}:jnset:max_join")]]
    rows += grid([B(SEL(j.get("speed") == k, l), f"at:{tid}:jnspeed:{k}") for k, l, _ in JL_SPEEDS])
    rows.append([B(SEL(j.get("groups_only", True), "real groups only"), f"at:{tid}:jntoggle_groups_only")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:jn")

async def show_at_sender(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    s = t.get("sender", {})
    mode_labels = {"send_only":"send only", "join_send":"join + send", "join_send_leave":"join + send + leave"}
    ed_on = bool(s.get("edit_delay_enabled", False))
    ed_sec = s.get("edit_delay_seconds", 3.0)
    ed_rand = bool(s.get("edit_delay_random", False))
    ph = s.get("placeholder_text", "hi")
    ph_rand = bool(s.get("placeholder_random", False))
    ms_on = bool(s.get("multi_step_edit", False))
    af = s.get("attach_file") or ""
    inf_on = bool(s.get("infinite_loop", False))
    ld = s.get("loop_delay", 3.0)
    rs = bool(s.get("rescan_targets", True))
    txt = head("📤", "sender", t.get("name", "?"))
    txt += mrow("✉️", "text", short(s.get("text", ""), 50) or "—") + "\n"
    txt += mrow("🎯", "target", s.get("target", "?")) + "\n"
    txt += mrow("🔁", "mode", mode_labels.get(s.get("mode"), s.get("mode"))) + "\n"
    txt += mrow("🔢", "max send", s.get("max_send", 0) or "∞") + "\n"
    txt += mrow("⏱", "delay", f"{s.get('delay', 1.5)}s") + "\n"
    txt += mrow("🎭", "edit delay", ("on" if ed_on else "off"))
    if ed_on: txt += (" (random)" if ed_rand else f" {ed_sec}s")
    txt += "\n" + mrow("💬", "placeholder", ph) + "\n"
    txt += mrow("🔁", "loop", ("on" if inf_on else "off"))
    if inf_on:
        txt += f"  {ld}s\n" + mrow("🔄", "rescan", ("on" if rs else "off"))
    txt += "\n" + mrow("📎", "file", os.path.basename(af) if af else "—")
    rows = [
        [B("text", f"at:{tid}:snset:text")],
        [B("target", f"at:{tid}:snset:target"), B("max", f"at:{tid}:snset:max_send")],
        [B("delay", f"at:{tid}:snset:delay"), B("mode", f"at:{tid}:snmode")],
        [B(SEL(inf_on, "loop"), f"at:{tid}:sntoggle_loop"),
         B(f"loop delay {ld}s", f"at:{tid}:snset_loop_delay")],
        [B(SEL(rs, "rescan"), f"at:{tid}:sntoggle_rescan")],
        [B(SEL(ed_on, "edit delay"), f"at:{tid}:snedit:toggle")],
        [B(f"{ed_sec}s", f"at:{tid}:snedit:sec"), B("placeholder", f"at:{tid}:snedit:ph")],
        [B(SEL(ph_rand, "placeholder list"), f"at:{tid}:snedit:ph_rand"),
         B(SEL(ms_on, "multi step"), f"at:{tid}:snedit:multi_toggle")],
        [B(f"attach: {short(os.path.basename(af), 15) if af else 'none'}", f"at:{tid}:snedit:file")],
        [B("send to existing", f"at:{tid}:snedit:toggle_existing")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:sn")

async def show_at_sender_mode(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    cur = t["sender"].get("mode", "send_only")
    opts = [("send_only","send only"), ("join_send","join + send"),
            ("join_send_leave","join + send + leave")]
    txt = head("🔁", "sender mode", cur)
    rows = grid([B(SEL(cur == k, l), f"at:{tid}:snmode_set:{k}") for k, l in opts])
    rows.append(nav(f"at:{tid}:sn"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:snmode")

async def show_at_pv(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    pv = t.get("pv", {})
    en = bool(pv.get("enabled"))
    mx = int(pv.get("max_replies", 1) or 0)
    items = pv.get("items") or []
    apply_acc = bool(pv.get("apply_to_accounts", True))
    txt = head("💬", "pv", t.get("name", "?"))
    txt += mrow("📶", "status", ("on" if en else "off")) + "\n"
    txt += mrow("👥", "max/user", (mx if mx else "∞")) + "\n"
    txt += mrow("⏱", "delay", f"{pv.get('delay_seconds', 0)}s") + "\n"
    txt += mrow("🔄", "apply to accounts", ("on" if apply_acc else "off")) + "\n"
    txt += mrow("📨", "items", len(items)) + "\n\n"
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"{i}. text: <code>{esc(short(it.get('text',''), 40))}</code>\n"
        elif k == "file": txt += f"{i}. file: <code>{esc(os.path.basename(it.get('file_path','?')))}</code>\n"
        elif k == "delay": txt += f"{i}. delay {it.get('seconds',3)}s\n"
    rows = [
        [B("turn off" if en else "turn on", f"at:{tid}:pv:toggle")],
        [B(f"max: {mx if mx else '∞'}", f"at:{tid}:pv:cycle_max"),
         B("delay", f"at:{tid}:pv:set_delay")],
        [B("+ text", f"at:{tid}:pv:add_text"),
         B("+ file", f"at:{tid}:pv:add_saved"),
         B("+ delay", f"at:{tid}:pv:add_delay")],
        [B(SEL(apply_acc, "apply to accounts"), f"at:{tid}:pv:toggle_apply")],
        [B("items", f"at:{tid}:pv:list")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:pv")

async def show_at_pv_list(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    items = (t.get("pv") or {}).get("items") or []
    txt = head("📋", "pv items", len(items))
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"\n{i}. text: <code>{esc(short(it.get('text',''), 60))}</code>"
        elif k == "file": txt += f"\n{i}. file: <code>{esc(os.path.basename(it.get('file_path','?')))}</code>"
        elif k == "delay": txt += f"\n{i}. delay: {it.get('seconds',3)}s"
    rows = [[B(f"del {i+1}", f"at:{tid}:pv:del:{i}")] for i in range(len(items))]
    rows.append([B("« back", f"at:{tid}:pv")])
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:pv_list")

async def show_at_lefter(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    l = t.get("lefter", {})
    txt = head("🚪", "lefter", t.get("name", "?"))
    txt += mrow("🎯", "mode", l.get("leave_mode", "?"))
    rows = []
    for k, lbl in LF_MODES:
        rows.append([B(SEL(l.get("leave_mode") == k, lbl), f"at:{tid}:lfset:{k}")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:lf")

async def show_at_run(tid, page=0):
    t = get_template(tid)
    if not t: return await show_at_menu()
    accounts = list_accounts(); items = list(accounts.items())
    per = 6; pages = max(1, -(-len(items) // per)); page = max(0, min(page, pages - 1))
    chunk = items[page*per:(page+1)*per]
    cid = STATE.get("owner"); conv = get_conv(cid) if cid else {}
    selected = set((conv.get("at_run") or {}).get("accounts") or [])
    rows = []
    for aid, a in chunk:
        rows.append([B(SEL(aid in selected, short(a.get('name','?'), 20)), f"at:{tid}:run_acc:{aid}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("« prev", f"at:{tid}:run:{page - 1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages - 1: pr.append(B("next »", f"at:{tid}:run:{page + 1}"))
        rows.append(pr)
    rows.append([B("start »", f"at:{tid}:run_go")])
    rows.append(nav(f"at:{tid}:view"))
    txt = head("🎯", "run template", t.get("name", "?"))
    txt += mrow("👤", "selected", len(selected))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:run:{page}")

async def show_acc_at_menu(aid):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="main")
    tpls = list_templates()
    txt = head("🎯", "auto-tar on", a.get("name", "?"))
    if not tpls:
        return await panel(txt + "\n\n" + SC("no templates yet."),
                           kb_([B("+ new", "at:new"), B("back to panel", "menu:main")]),
                           page_tag=f"acc:at:{aid}")
    rows = []
    for tid, t in list(tpls.items())[:10]:
        rows.append([B(f"{short(t.get('name','?'), 22)}", f"acc:at:run:{aid}:{tid}")])
    rows.append(nav(f"acc:view:{aid}"))
    await panel(txt, kb_(*rows), page_tag=f"acc:at:{aid}")

async def show_acc_lf(aid):
    a = get_account(aid)
    if not a: return await panel("not found.", kb_(nav()), page_tag="main")
    txt = head("🚪", "lefter on", a.get("name", "?"))
    rows = []
    for k, lbl in LF_MODES:
        rows.append([B(lbl, f"acc:lf:go:{aid}:{k}")])
    rows.append(nav(f"acc:view:{aid}"))
    await panel(txt, kb_(*rows), page_tag=f"acc:lf:{aid}")

# ═══════════════ login relay ═══════════════
async def interactive_login_via_rubpy(admin_id, phone):
    loop = asyncio.get_running_loop(); q = queue.Queue()
    STATE.setdefault("pending_login", {})[admin_id] = {"q": q}
    def fake_input(prompt=""):
        msg = str(prompt).strip() or "send code:"
        asyncio.run_coroutine_threadsafe(tg_send(f"📨 {msg}"), loop)
        return q.get(timeout=300)
    aid = "acc_" + secrets.token_hex(4)
    sess_path = os.path.join(SESSIONS_DIR, aid)
    def worker():
        old = builtins.input; builtins.input = fake_input
        try:
            async def run():
                c = _C(name=sess_path)
                await c.start(phone_number=phone)
                me = await c.get_me()
                try: await c.disconnect()
                except Exception: pass
                return me
            return asyncio.run(run())
        finally: builtins.input = old
    async def job():
        try:
            me = await asyncio.to_thread(worker)
            u = getattr(me, "user", me)
            name = getattr(u, "first_name", None) or phone
            guid = getattr(u, "user_guid", None) or getattr(u, "guid", None)
            add_account(aid, phone, name, guid)
            try:
                async def start_listener_now():
                    acc = get_account(aid)
                    if not acc: return
                    stop = asyncio.Event(); STATE.setdefault("listener_stops", {})[aid] = stop
                    LISTENER_TASKS[aid] = asyncio.create_task(_listener_loop(aid, acc, stop))
                asyncio.create_task(start_listener_now())
            except Exception: pass
            try: await start_pv_responders()
            except Exception: pass
            await panel(head("✅", f"rubika: {name}") + f"🆔 <code>{esc(aid)}</code>",
                        kb_([B("account", f"acc:view:{aid}")], [B("back to panel", "menu:main")]),
                        page_tag=f"acc:{aid}")
        except Exception as e:
            try: traceback.print_exc()
            except Exception: pass
            for f in glob.glob(sess_path + "*"):
                try: os.remove(f)
                except Exception: pass
            await panel(f"login failed: <code>{esc(str(e)[:200])}</code>",
                        kb_([B("retry", "acc:add")], [B("back to panel", "menu:main")]),
                        page_tag="main")
        finally: STATE.get("pending_login", {}).pop(admin_id, None)
    asyncio.create_task(job())

# ═══════════════ message handler ═══════════════
async def _on_message_impl(update, context):
    if not authorized(update): return
    msg = update.message
    if msg is None: return
    cid = update.effective_chat.id
    conv = STATE["conv"].get(cid) or {}
    text = (msg.text or "").strip()

    if "acc" in conv and conv["acc"].get("step") == "login_pending":
        q = STATE.get("pending_login", {}).get(cid, {}).get("q")
        if q:
            try: q.put(text)
            except Exception: pass
        return

    if conv.get("pv_acc_wait"):
        w = conv.pop("pv_acc_wait"); aid = w.get("aid"); kind = w.get("kind")
        cfg = _load_pv_account(aid); items = cfg.get("items") or []
        if kind == "delay":
            try: cfg["delay_seconds"] = max(0, int(re.sub(r"[^\d]", "", text) or "0"))
            except Exception: cfg["delay_seconds"] = 0
        elif kind == "poll":
            try: cfg["poll_seconds"] = max(3, int(re.sub(r"[^\d]", "", text) or "5"))
            except Exception: cfg["poll_seconds"] = 5
        elif kind == "add_text":
            items.append({"kind": "text", "text": text}); cfg["items"] = items
        elif kind == "add_delay_sec":
            try: sec = max(0, int(re.sub(r"[^\d]", "", text) or "3"))
            except Exception: sec = 3
            items.append({"kind": "delay", "seconds": sec}); cfg["items"] = items
        _save_pv_account(aid, cfg); await tg_send("saved")
        return await show_pv_account_menu(aid)

    if conv.get("pv_acc_save_msg"):
        w = conv.pop("pv_acc_save_msg"); aid = w.get("aid")
        media = _extract_media(msg); caption = text or ""
        if not media and not caption: return await ask("send again:")
        local_path = None
        if media:
            try: local_path = await _download_tg_file(media, "pv", "pvitem")
            except Exception: pass
        cfg = _load_pv_account(aid); items = cfg.get("items") or []
        if local_path: items.append({"kind": "file", "file_path": local_path, "caption": caption})
        else: items.append({"kind": "text", "text": caption})
        cfg["items"] = items; _save_pv_account(aid, cfg); await tg_send("saved")
        return await show_pv_account_menu(aid)

    if conv.get("pv_tpl_wait"):
        w = conv.pop("pv_tpl_wait"); tid = w.get("tid"); kind = w.get("kind")
        t = get_template(tid)
        if not t: return await show_at_menu()
        pv = t.setdefault("pv", {}); items = pv.get("items") or []
        if kind == "delay":
            try: pv["delay_seconds"] = max(0, int(re.sub(r"[^\d]", "", text) or "0"))
            except Exception: pv["delay_seconds"] = 0
            update_template(tid, "pv", "delay_seconds", pv["delay_seconds"])
        elif kind == "add_text":
            items.append({"kind": "text", "text": text})
            update_template(tid, "pv", "items", items)
        elif kind == "add_delay_sec":
            try: sec = max(0, int(re.sub(r"[^\d]", "", text) or "3"))
            except Exception: sec = 3
            items.append({"kind": "delay", "seconds": sec})
            update_template(tid, "pv", "items", items)
        await tg_send("saved")
        return await show_at_pv(tid)

    if conv.get("pv_tpl_save_msg"):
        w = conv.pop("pv_tpl_save_msg"); tid = w.get("tid")
        t = get_template(tid)
        if not t: return await show_at_menu()
        media = _extract_media(msg); caption = text or ""
        if not media and not caption: return await ask("send again:")
        local_path = None
        if media:
            try: local_path = await _download_tg_file(media, "pvtpl", "pvtpl")
            except Exception: pass
        pv = t.setdefault("pv", {}); items = pv.get("items") or []
        if local_path: items.append({"kind": "file", "file_path": local_path, "caption": caption})
        else: items.append({"kind": "text", "text": caption})
        update_template(tid, "pv", "items", items); await tg_send("saved")
        return await show_at_pv(tid)

    if conv.get("accphoto_upload"):
        info = conv.pop("accphoto_upload"); aid = info["aid"]
        media = _extract_media(msg)
        if not media: return await ask("no photo:")
        try: fpath = await _download_tg_file(media, aid, "accphoto")
        except Exception as e: return await ask(f"err: {str(e)[:100]}")
        a = get_account(aid)
        if not a: return await panel("not found.", kb_(nav()), page_tag="main")
        STATE["panel"].pop(cid, None)
        await panel("uploading...", page_tag=f"accphoto:{aid}")
        cli = None; ok = False; msg_r = ""
        try:
            cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
            await cli.__aenter__(); me = await cli.get_me()
            ok, msg_r = await rubika_set_photo(cli, me.user.user_guid, fpath)
        except Exception as e: msg_r = _fmt_error(e)
        finally:
            if cli:
                try: await cli.__aexit__(None, None, None)
                except Exception: pass
        await tg_send("ok" if ok else f"err: {msg_r[:150]}")
        return await show_acc_photo_menu(aid)

    if conv.get("chphoto_upload"):
        info = conv.pop("chphoto_upload"); aid = info["aid"]; idx = info["idx"]
        media = _extract_media(msg)
        if not media: return await ask("no photo:")
        try: fpath = await _download_tg_file(media, aid, "chphoto")
        except Exception as e: return await ask(f"err: {str(e)[:100]}")
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel("not found.", kb_(nav()), page_tag="main")
        ch = chs[idx]; STATE["panel"].pop(cid, None)
        await panel("uploading...", page_tag=f"chphoto:{aid}:{idx}")
        cli = None; ok = False; msg_r = ""
        try:
            cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
            await cli.__aenter__(); ok, msg_r = await rubika_set_chat_photo(cli, ch["guid"], fpath)
        except Exception as e: msg_r = _fmt_error(e)
        finally:
            if cli:
                try: await cli.__aexit__(None, None, None)
                except Exception: pass
        await tg_send("ok" if ok else f"err: {msg_r[:150]}")
        return await show_ch_photo_menu(aid, idx)

    if conv.get("chfile_upload") and conv["chfile_upload"].get("step") == "wait_file":
        info = conv["chfile_upload"]; media = _extract_media(msg); fpath = None
        if media:
            try: fpath = await _download_tg_file(media, info["aid"], "chfile")
            except Exception as e: return await ask(f"err: {str(e)[:100]}")
        elif text and os.path.exists(text.strip()): fpath = text.strip()
        if not fpath: return await ask("no file:")
        info["file_path"] = fpath; info["step"] = "wait_caption"
        conv["chfile_upload"] = info
        return await ask("caption:")

    if conv.get("chfile_upload") and conv["chfile_upload"].get("step") == "wait_caption":
        info = conv.pop("chfile_upload"); aid = info["aid"]; idx = info["idx"]
        fpath = info.get("file_path"); caption = text.strip()
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel("not found.", kb_(nav()), page_tag="main")
        ch = chs[idx]; STATE["panel"].pop(cid, None)
        await panel("sending file...", page_tag=f"chview:{aid}:{idx}")
        cli = None; ok = False; msg_r = ""
        try:
            cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
            await cli.__aenter__()
            await send_media(cli, ch["guid"], {"kind": "document", "text": caption, "file": fpath})
            ok = True
        except Exception as e: msg_r = _fmt_error(e)
        finally:
            if cli:
                try: await cli.__aexit__(None, None, None)
                except Exception: pass
        await tg_send("ok" if ok else f"err: {msg_r[:150]}")
        return await show_channel_view(aid, idx)

    if conv.get("at_field_photo"):
        info = conv.pop("at_field_photo")
        tid = info["tid"]; section = info["section"]; field = info["field"]
        media = _extract_media(msg)
        if not media: return await ask("no file:")
        try: fpath = await _download_tg_file(media, "tpl", "tplfile")
        except Exception as e: return await ask(f"err: {str(e)[:100]}")
        update_template(tid, section, field, fpath); await tg_send("saved")
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
                except Exception: value = 0
            elif field == "delay":
                try: value = float(re.sub(r"[^\d\.]", "", text) or "1.5")
                except Exception: value = 1.5
            elif field == "edit_delay_seconds":
                try: value = max(0.0, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
                except Exception: value = 3.0
            elif field == "loop_delay":
                try: value = max(0.5, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
                except Exception: value = 3.0
            update_template(tid, section, field, value); await tg_send("saved")
            if section == "meta": return await show_at_view(tid)
            if section == "channel": return await show_at_channel(tid)
            if section == "profile": return await show_at_profile(tid)
            if section == "joiner": return await show_at_joiner(tid)
            if section == "sender": return await show_at_sender(tid)
            if section == "sender_edit": return await show_at_sender(tid)
            if section == "lefter": return await show_at_lefter(tid)

    if conv.get("send_edit_wait"):
        kind = conv.pop("send_edit_wait"); s = _send_conv(cid)
        if kind == "sec":
            try: s["edit_delay_seconds"] = max(0.0, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
            except Exception: s["edit_delay_seconds"] = 3.0
        elif kind == "ph": s["placeholder_text"] = text or "hi"
        elif kind == "loop_delay":
            try: s["loop_delay"] = max(0.5, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
            except Exception: s["loop_delay"] = 3.0
        return await show_send_step(cid)

    if conv.get("send_file_upload"):
        conv.pop("send_file_upload"); s = _send_conv(cid)
        media = _extract_media(msg)
        if media:
            try: fpath = await _download_tg_file(media, "send", "sendfile")
            except Exception as e: return await ask(f"err: {str(e)[:100]}")
            s["attach_file"] = fpath
        elif text and os.path.exists(text.strip()): s["attach_file"] = text.strip()
        else: return await ask("no file:")
        await tg_send("saved")
        return await show_send_step(cid)

    if conv.get("cfg_wait"):
        key = conv.pop("cfg_wait")
        cfg = _load(CFG_FILE, DEFAULT_CFG)
        try:
            v = text.strip()
            if "." in v: cfg[key] = float(v)
            else: cfg[key] = int(v)
            _save(CFG_FILE, cfg); await tg_send("saved")
        except Exception: await tg_send("invalid number")
        return await show_cfg()

    if conv.get("ld_wait") == "url":
        back = conv.pop("ld_back", "jl:back_to_settings")
        url = text.strip()
        if url.startswith("rubika.ir") or url.startswith("ble.rip"): url = "https://" + url
        if add_link_doni(url): await tg_send("added")
        else: await tg_send("already there or invalid")
        return await show_linkdonies(back)

    if conv.get("setlink"):
        info = conv.pop("setlink"); aid = info["aid"]; idx = info["idx"]
        url = text.strip()
        if not url: return await ask("empty:")
        update_channel_field(aid, idx, "join_link", url); await tg_send("saved")
        return await show_channel_view(aid, idx)

    if conv.get("chsend") and conv["chsend"].get("step") == "compose":
        info = conv.pop("chsend"); aid = info["aid"]; idx = info["idx"]
        STATE["panel"].pop(cid, None)
        await panel("sending...", page_tag=f"chview:{aid}:{idx}")
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel("not found.", kb_(nav()), page_tag="main")
        ch = chs[idx]; ok = False; msg_r = ""; cli = None
        try:
            cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
            await cli.__aenter__(); await send_text_only(cli, ch["guid"], text); ok = True
        except Exception as e: msg_r = _fmt_error(e)
        finally:
            if cli:
                try: await cli.__aexit__(None, None, None)
                except Exception: pass
        if ok:
            return await panel(head("✅", "sent") + f"💬 <code>{esc(text[:100])}</code>",
                               kb_([B("« back", f"ch:view:{aid}:{idx}")]), page_tag=f"chview:{aid}:{idx}")
        return await panel(f"err: <code>{esc(str(msg_r)[:400])}</code>",
                           kb_([B("« back", f"ch:view:{aid}:{idx}")]), page_tag=f"chview:{aid}:{idx}")

    if conv.get("chprof_edit"):
        info = conv.pop("chprof_edit"); aid = info["aid"]; idx = info["idx"]; field = info["field"]
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel("not found.", kb_(nav()), page_tag="main")
        ch = chs[idx]; STATE["panel"].pop(cid, None)
        await panel("updating...", page_tag=f"chprof:{aid}:{idx}")
        cli = None; ok = False; msg_r = ""
        try:
            cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
            await cli.__aenter__()
            if field == "title":
                ok, msg_r = await rubika_set_chat_title(cli, ch["guid"], text[:60])
                if ok: update_channel_field(aid, idx, "title", text[:60])
            elif field == "desc":
                ok, msg_r = await rubika_set_chat_description(cli, ch["guid"], text)
                if ok: update_channel_field(aid, idx, "description", text)
            elif field == "user":
                ok, msg_r = await rubika_set_chat_username(cli, ch["guid"], text)
                if ok:
                    update_channel_field(aid, idx, "username", text.lstrip("@"))
                    update_channel_field(aid, idx, "is_public", True)
        except Exception as e: msg_r = _fmt_error(e)
        finally:
            if cli:
                try: await cli.__aexit__(None, None, None)
                except Exception: pass
        await tg_send("ok" if ok else f"err: {msg_r[:150]}")
        return await show_ch_profile(aid, idx)

    if conv.get("chnew"):
        info = conv["chnew"]; step = info.get("step"); aid = info.get("aid")
        a = get_account(aid); STATE["panel"].pop(cid, None)
        if not a:
            conv.pop("chnew", None)
            return await panel("not found.", kb_(nav()), page_tag="main")
        if step == "title":
            title = text.strip()
            if not title: return await ask("title:")
            info["title"] = title[:60]; info["step"] = "type"; conv["chnew"] = info
            return await show_ch_new_type(aid, title)
        if step == "username":
            title = info.get("title"); uname = text.lstrip("@").strip()
            if not uname: return await ask("username:")
            conv.pop("chnew", None)
            await panel(f"creating «{esc(title)}»...", page_tag="chnew_run")
            cli = None; ok = False; msg_r = ""; guid = None; link = None
            try:
                cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
                await cli.__aenter__()
                ok, msg_r, guid, link = await rubika_create_channel(cli, title, "", "public")
                if ok and guid:
                    try: await rubika_set_chat_username(cli, guid, uname)
                    except Exception as ue: msg_r = f"username: {_fmt_error(ue)[:100]}"
            except Exception as e: ok, msg_r = False, f"{type(e).__name__}: {_fmt_error(e)}"
            finally:
                if cli:
                    try: await cli.__aexit__(None, None, None)
                    except Exception: pass
            if ok:
                add_channel_to_storage(aid, {"title": title, "description": "", "guid": guid,
                    "username": uname, "is_public": True, "type": "public",
                    "join_link": link or "", "created": int(time.time())})
                return await panel(head("✅", "created") + f"📝 {esc(title)}\n🔗 @{esc(uname)}",
                                   kb_([B("channels", f"chlist:show:{aid}:0")],
                                       [B("« back", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")
            return await panel(f"err: <code>{esc(str(msg_r)[:300])}</code>",
                               kb_([B("« back", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")

    if conv.get("prof_field"):
        info = conv.pop("prof_field"); field = info["field"]; aid = info["aid"]
        STATE["panel"].pop(cid, None); a = get_account(aid)
        if not a: return await panel("not found.", kb_(nav()), page_tag="main")
        await panel("updating...", page_tag=f"prof:{aid}")
        ok = False; msg_r = ""; cli = None
        try:
            cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
            await cli.__aenter__()
            if field == "first": ok, msg_r = await rubika_set_name(cli, text, None)
            elif field == "last": ok, msg_r = await rubika_set_name(cli, None, text)
            elif field == "about": ok, msg_r = await rubika_set_bio(cli, text)
            elif field == "username": ok, msg_r = await rubika_set_username(cli, text)
        except Exception as e: msg_r = _fmt_error(e)
        finally:
            if cli:
                try: await cli.__aexit__(None, None, None)
                except Exception: pass
        if ok:
            return await panel(head("✅", "ok") + f"<code>{esc(str(msg_r)[:200])}</code>",
                               kb_([B("« back", f"prof:menu:{aid}")]), page_tag=f"prof:{aid}")
        return await panel(f"err: <code>{esc(str(msg_r)[:300])}</code>",
                           kb_([B("« back", f"prof:menu:{aid}")]), page_tag=f"prof:{aid}")

    if "jl_wait" in conv:
        conv.pop("jl_wait"); jl = get_conv(cid).get("jl") or {}
        try: jl["max_join"] = max(0, int(re.sub(r"[^\d]", "", text) or "0"))
        except Exception: return await ask("number:")
        get_conv(cid)["jl"] = jl; return await jl_step_max(cid, jl)

    if "send_wait" in conv:
        conv.pop("send_wait"); s = _send_conv(cid)
        try: s["max"] = max(0, int(re.sub(r"[^\d]", "", text) or "0"))
        except Exception: return await ask("number:")
        return await show_send_step(cid)

    if "send" in conv:
        s = conv["send"]
        if s.get("step") == "compose":
            STATE["panel"].pop(cid, None)
            if not text: return await ask("message text:")
            s["payload"] = {"kind": "text", "text": text, "file": None}; s["step"] = "target"
            return await show_send_step(cid)

    if "acc" in conv:
        a = conv["acc"]; step = a.get("step")
        STATE["panel"].pop(cid, None)
        if step == "phone":
            ph = text.replace("+","").replace(" ","").replace("-","")
            if ph.startswith("0"): ph = "98" + ph[1:]
            if not ph.isdigit() or len(ph) < 10:
                return await ask("invalid phone:")
            a["step"] = "login_pending"; conv["acc"] = a; STATE["conv"][cid] = conv
            await panel("logging in...\nsend the code rubika sends you.", page_tag="login_pending")
            asyncio.create_task(interactive_login_via_rubpy(cid, ph))
            return

_on_message_orig = _on_message_impl
async def on_message(update, context):
    cid = None; had_conv = False; keep_msg = False
    try:
        cid = update.effective_chat.id
        had_conv = bool(STATE["conv"].get(cid)) or (cid in _TMP_EDIT)
        c = STATE["conv"].get(cid) or {}
        if any(c.get(k) for k in ("pv_acc_save_msg","pv_tpl_save_msg","accphoto_upload",
                                   "chphoto_upload","chfile_upload","at_field_photo",
                                   "send_file_upload")):
            keep_msg = True
    except Exception: pass
    await _on_message_orig(update, context)
    try:
        if had_conv and authorized(update) and update.message and not keep_msg:
            await update.message.delete()
    except Exception: pass

# ═══════════════ callback router ═══════════════
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
    if data == "menu:cfg": return await show_cfg()

    if h == "cache":
        sub = p[1] if len(p) > 1 else ""
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; act = p[3] if len(p) > 3 else ""
            if not act: return await show_cache_account(aid)
            if act == "clear_seen": _clear_seen(aid); await tg_send("cleared"); return await show_cache_account(aid)
            if act == "clear_banned": _clear_banned(aid); await tg_send("cleared"); return await show_cache_account(aid)
            if act == "clear_all": _clear_seen(aid); _clear_banned(aid); await tg_send("cleared"); return await show_cache_account(aid)
            if act == "reset_ld": _reset_ld_progress(aid); await tg_send("reset"); return await show_cache_account(aid)
        if sub == "clear_all_accounts":
            _clear_seen(); _clear_banned(); _reset_ld_progress()
            await tg_send("cleared all"); return await show_cache_menu()

    if h == "pv":
        sub = p[1] if len(p) > 1 else ""
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; act = p[3] if len(p) > 3 else ""
            if not act: return await show_pv_account_menu(aid)
            cfg = _load_pv_account(aid)
            if act == "toggle":
                cfg["enabled"] = not bool(cfg.get("enabled")); _save_pv_account(aid, cfg)
                if cfg["enabled"]:
                    ex = PV_LISTENER_TASKS.get(aid)
                    if not ex or ex.done():
                        acc = get_account(aid)
                        if acc:
                            stop = asyncio.Event(); _PV_STOP_EVENTS[aid] = stop
                            PV_LISTENER_TASKS[aid] = asyncio.create_task(_pv_poller_worker(aid, acc, stop))
                else: _stop_pv_for_account(aid)
                return await show_pv_account_menu(aid)
            if act == "cycle_max":
                seq = [1, 2, 3, 5, 0]; cur = int(cfg.get("max_replies", 1) or 0)
                cfg["max_replies"] = seq[(seq.index(cur) + 1) % len(seq)] if cur in seq else 1
                _save_pv_account(aid, cfg); return await show_pv_account_menu(aid)
            if act == "set_delay":
                get_conv(cid)["pv_acc_wait"] = {"aid": aid, "kind": "delay"}; return await ask("delay (0=instant):")
            if act == "set_poll":
                get_conv(cid)["pv_acc_wait"] = {"aid": aid, "kind": "poll"}; return await ask("poll seconds (>=3):")
            if act == "toggle_notify":
                cfg["notify"] = not bool(cfg.get("notify", True)); _save_pv_account(aid, cfg); return await show_pv_account_menu(aid)
            if act == "add_text":
                get_conv(cid)["pv_acc_wait"] = {"aid": aid, "kind": "add_text"}; return await ask("text:")
            if act == "add_saved":
                get_conv(cid)["pv_acc_save_msg"] = {"aid": aid}; return await ask("send msg/photo/file:")
            if act == "add_delay":
                get_conv(cid)["pv_acc_wait"] = {"aid": aid, "kind": "add_delay_sec"}; return await ask("seconds:")
            if act == "list": return await show_pv_account_list(aid)
            if act == "del" and len(p) >= 5:
                try: i = int(p[4])
                except Exception: return await show_pv_account_list(aid)
                items = cfg.get("items") or []
                if 0 <= i < len(items): items.pop(i)
                cfg["items"] = items; _save_pv_account(aid, cfg); await tg_send("deleted"); return await show_pv_account_list(aid)
            if act == "clear_replies":
                try:
                    d = _load(PV_COUNTS_FILE, {}); d.pop(aid, None); _save(PV_COUNTS_FILE, d)
                except Exception: pass
                try:
                    w = _wm_load(); w.pop(aid, None); _wm_flush()
                except Exception: pass
                await tg_send("reset"); return await show_pv_account_menu(aid)
            if act == "reset_to_global":
                _delete_pv_account(aid); await tg_send("reset"); return await show_pv_account_menu(aid)
            if act == "restart":
                _stop_pv_for_account(aid); await asyncio.sleep(0.5)
                cfg2 = _load_pv_account(aid)
                if cfg2.get("enabled"):
                    acc = get_account(aid)
                    if acc:
                        stop = asyncio.Event(); _PV_STOP_EVENTS[aid] = stop
                        PV_LISTENER_TASKS[aid] = asyncio.create_task(_pv_poller_worker(aid, acc, stop))
                await tg_send("restarted"); return await show_pv_account_menu(aid)
            if act == "report":
                try: pg = int(p[4]) if len(p) > 4 else 0
                except Exception: pg = 0
                return await show_pv_account_report(aid, pg)

    if h == "acc":
        if len(p) >= 5 and p[1] == "at" and p[2] == "run":
            aid = p[3]; tid = p[4]
            op = {"id": "at_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "autotar", "accounts": [aid], "template_id": tid, "status": "running",
                  "progress": {"joined":0,"failed":0,"total":0,"pending":0,"in_progress":0,
                               "phase":"start","sent":0,"already":0,"tried":0,"wave":0,
                               "left":0,"round":0,"skipped_seen":0,"skipped_banned":0,"rejected":0},
                  "errors": []}
            _save_op(op); asyncio.create_task(run_auto_tar(op, log_cb)); return await show_op_detail(op["id"])
        if len(p) >= 3 and p[1] == "at": return await show_acc_at_menu(p[2])
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_accounts(int(p[2]))
        if sub == "add":
            get_conv(cid)["acc"] = {"step": "phone"}
            return await ask("phone number:\nexample: <code>989121234567</code>")
        if sub == "view": return await show_account_detail(p[2])
        if sub == "del":
            a = get_account(p[2])
            if not a: return await panel("not found.", kb_(nav()), page_tag="main")
            return await panel(f"delete <b>{esc(a.get('name','?'))}</b>?",
                               kb_([B("yes", f"acc:delok:{p[2]}"), B("no", f"acc:view:{p[2]}")]),
                               page_tag=f"acc_del:{p[2]}")
        if sub == "delok":
            _stop_listener_for(p[2])
            try: _stop_pv_for_account(p[2])
            except Exception: pass
            remove_account(p[2]); await tg_send("deleted"); return await show_accounts()
        if sub == "lf" and len(p) >= 5 and p[3] == "go":
            aid = p[2]; mode = p[4]
            op = {"id": "lf_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "lefter", "accounts": [aid], "leave_mode": mode, "delay": 0.8,
                  "status": "running",
                  "progress": {"joined":0,"failed":0,"total":0,"phase":"start"}, "errors": []}
            _save_op(op); asyncio.create_task(run_lefter(op, log_cb)); return await show_op_detail(op["id"])
        if sub == "lf" and len(p) >= 3: return await show_acc_lf(p[2])

    if h == "accphoto":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu" and len(p) >= 3: return await show_acc_photo_menu(p[2])
        if sub == "set" and len(p) >= 3:
            get_conv(cid)["accphoto_upload"] = {"aid": p[2]}; return await ask("send photo:")
        if sub == "del" and len(p) >= 3:
            aid = p[2]; a = get_account(aid)
            if not a: return await panel("not found.", kb_(nav()), page_tag="main")
            await panel("deleting...", page_tag=f"accphoto:{aid}")
            cli = None; ok = False; msg_r = ""
            try:
                cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
                await cli.__aenter__(); me = await cli.get_me()
                ok, msg_r = await rubika_delete_photo(cli, me.user.user_guid)
            except Exception as e: msg_r = _fmt_error(e)
            finally:
                if cli:
                    try: await cli.__aexit__(None, None, None)
                    except Exception: pass
            await tg_send("ok" if ok else f"err: {msg_r[:150]}")
            return await show_acc_photo_menu(aid)

    if h == "chphoto":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu" and len(p) >= 4: return await show_ch_photo_menu(p[2], int(p[3]))
        if sub == "set" and len(p) >= 4:
            get_conv(cid)["chphoto_upload"] = {"aid": p[2], "idx": int(p[3])}
            return await ask("send channel photo:")
        if sub == "del" and len(p) >= 4:
            aid = p[2]; idx = int(p[3]); a = get_account(aid); chs = get_stored_channels(aid)
            if not a or idx >= len(chs): return await panel("not found.", kb_(nav()), page_tag="main")
            ch = chs[idx]; await panel("deleting...", page_tag=f"chphoto:{aid}:{idx}")
            cli = None; ok = False; msg_r = ""
            try:
                cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
                await cli.__aenter__()
                for mname in ("delete_chat_photo","remove_chat_photo","delete_channel_photo"):
                    fn = getattr(cli, mname, None)
                    if not fn: continue
                    try:
                        r = fn(channel_guid=ch["guid"])
                        if asyncio.iscoroutine(r): r = await r
                        ok = True; msg_r = mname; break
                    except Exception as e: msg_r = _fmt_error(e)
            except Exception as e: msg_r = _fmt_error(e)
            finally:
                if cli:
                    try: await cli.__aexit__(None, None, None)
                    except Exception: pass
            await tg_send("ok" if ok else f"err: {msg_r[:150]}")
            return await show_ch_photo_menu(aid, idx)

    if h == "chfile":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start" and len(p) >= 4:
            get_conv(cid)["chfile_upload"] = {"aid": p[2], "idx": int(p[3]), "step": "wait_file"}
            return await ask("send file:")

    if h == "prof":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu": return await show_profile_menu(p[2])
        if sub == "set":
            field = p[2]; aid = p[3]
            get_conv(cid)["prof_field"] = {"field": field, "aid": aid}
            prompts = {"first":"first name:","last":"last name:","about":"bio:","username":"username:"}
            return await ask(prompts.get(field, "value:"))

    if h == "ch":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu": return await show_ch_menu(p[2])
        if sub == "view" and len(p) >= 4: return await show_channel_view(p[2], int(p[3]))
        if sub == "getlink" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            a = get_account(aid); chs = get_stored_channels(aid)
            if not a or idx >= len(chs): return await panel("not found.", kb_(nav()), page_tag="main")
            await panel("fetching...", page_tag=f"chview:{aid}:{idx}")
            cli = None; ok = False; link = ""
            try:
                cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
                await cli.__aenter__()
                ok, link = await rubika_create_join_link(cli, chs[idx]["guid"])
                if ok: update_channel_field(aid, idx, "join_link", link)
            except Exception as e: link = _fmt_error(e)
            finally:
                if cli:
                    try: await cli.__aexit__(None, None, None)
                    except Exception: pass
            if ok:
                return await panel(head("🔗", "link") + f"\n\n<code>{esc(link)}</code>",
                                   kb_([B("set manually", f"ch:setlink:{aid}:{idx}")],
                                       [B("« back", f"ch:view:{aid}:{idx}")]), page_tag=f"chview:{aid}:{idx}")
            return await panel(f"err: {esc(str(link)[:200])}",
                               kb_([B("« back", f"ch:view:{aid}:{idx}")]), page_tag=f"chview:{aid}:{idx}")
        if sub == "setlink" and len(p) >= 4:
            get_conv(cid)["setlink"] = {"aid": p[2], "idx": int(p[3])}; return await ask("link:")
        if sub == "del" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            channels = get_stored_channels(aid)
            if idx >= len(channels): return await show_ch_list(aid)
            return await panel(f"delete?", kb_(
                [B("yes", f"ch:delok:{aid}:{idx}"), B("no", f"ch:view:{aid}:{idx}")]),
                page_tag=f"chview:{aid}:{idx}")
        if sub == "delok" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            remove_channel_from_storage(aid, idx); await tg_send("deleted")
            return await show_ch_list(aid)

    if h == "chlist":
        sub = p[1] if len(p) > 1 else ""
        if sub == "show": return await show_ch_list(p[2], int(p[3]) if len(p) > 3 else 0)

    if h == "chsend":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start" and len(p) >= 4:
            get_conv(cid)["chsend"] = {"aid": p[2], "idx": int(p[3]), "step": "compose"}
            return await ask("send text:")

    if h == "chprof":
        sub = p[1] if len(p) > 1 else ""
        if sub == "show" and len(p) >= 4: return await show_ch_profile(p[2], int(p[3]))
        if sub == "edit" and len(p) >= 5:
            field = p[2]; aid = p[3]; idx = int(p[4])
            get_conv(cid)["chprof_edit"] = {"aid": aid, "idx": idx, "field": field}
            prompts = {"title":"title:","desc":"description:","user":"username:"}
            return await ask(prompts.get(field, "value:"))

    if h == "chnew":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            get_conv(cid)["chnew"] = {"aid": p[2], "step": "title"}; return await ask("name:")
        if sub == "pub":
            aid = p[2]; info = get_conv(cid).get("chnew") or {}; title = info.get("title")
            if not title: return await panel("not found.", kb_(nav(f"ch:menu:{aid}")), page_tag=f"ch_menu:{aid}")
            get_conv(cid)["chnew"] = {"aid": aid, "step": "username", "title": title}
            return await ask("username:")
        if sub == "priv":
            aid = p[2]; info = get_conv(cid).get("chnew") or {}; title = info.get("title")
            if not title: return await panel("not found.", kb_(nav(f"ch:menu:{aid}")), page_tag=f"ch_menu:{aid}")
            get_conv(cid).pop("chnew", None); a = get_account(aid); STATE["panel"].pop(cid, None)
            if not a: return await panel("not found.", kb_(nav()), page_tag="main")
            await panel("creating...", page_tag="chnew_run")
            cli = None; ok = False; msg_r = ""; guid = None; link = None
            try:
                cli = SafeClient(name=a.get("session_name") or os.path.join(SESSIONS_DIR, aid), _aid=aid)
                await cli.__aenter__()
                ok, msg_r, guid, link = await rubika_create_channel(cli, title, "", "private")
            except Exception as e: ok, msg_r = False, _fmt_error(e)
            finally:
                if cli:
                    try: await cli.__aexit__(None, None, None)
                    except Exception: pass
            if ok:
                add_channel_to_storage(aid, {"title": title, "description": "", "guid": guid,
                    "username": "", "is_public": False, "type": "private",
                    "join_link": link or "", "created": int(time.time())})
                body = head("✅", "created") + f"📝 {esc(title)}"
                if link: body += f"\n🔗 <code>{esc(link)}</code>"
                return await panel(body, kb_([B("channels", f"chlist:show:{aid}:0")],
                                              [B("« back", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")
            return await panel(f"err: <code>{esc(str(msg_r)[:300])}</code>",
                               kb_([B("« back", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")

    if h == "listen":
        sub = p[1] if len(p) > 1 else ""
        if sub == "restart":
            await restart_all_listeners(); await tg_send("restarted"); return await show_listen_menu()
        if sub == "cfg":
            cfg = _load(CFG_FILE, DEFAULT_CFG)
            cfg["listener"] = 0 if int(cfg.get("listener", 1)) else 1
            _save(CFG_FILE, cfg); await tg_send("toggled"); return await show_listen_menu()
        if sub == "toggle" and len(p) >= 3:
            aid = p[2]; t = LISTENER_TASKS.get(aid)
            if t and not t.done(): _stop_listener_for(aid); await tg_send("off")
            else: await start_all_listeners(); await tg_send("on")
            await asyncio.sleep(0.3); return await show_listen_menu()

    if h == "ld":
        sub = p[1] if len(p) > 1 else ""
        back = p[3] if len(p) > 3 else (p[2] if len(p) > 2 else "jl:back_to_settings")
        if sub == "list": return await show_linkdonies(back)
        if sub == "add":
            get_conv(cid)["ld_wait"] = "url"; get_conv(cid)["ld_back"] = back
            return await ask("link:")
        if sub == "del" and len(p) >= 3:
            remove_link_doni(int(p[2])); await tg_send("deleted"); return await show_linkdonies(back)
        if sub == "reset":
            save_link_donies(list(DEFAULT_LINK_DONIES)); await tg_send("reset"); return await show_linkdonies(back)
        if sub == "reset_prog":
            _reset_ld_progress(); await tg_send("reset"); return await show_linkdonies(back)
        if sub == "toggle_autojoin":
            cfg = _load(CFG_FILE, DEFAULT_CFG)
            cfg["auto_join_linkdoni"] = 0 if int(cfg.get("auto_join_linkdoni", 1)) else 1
            _save(CFG_FILE, cfg); return await show_linkdonies(back)

    if h == "err":
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_errors(int(p[2]))
        if sub == "clear": clear_errors(); await tg_send("cleared"); return await show_errors()

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
                    st = STATE.get("cancel_events", {}).get(oid)
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
        if sub == "toggle_rescan": s["rescan_targets"] = not s.get("rescan_targets", True); return await show_send_step(cid)
        if sub == "loop_delay":
            get_conv(cid)["send_edit_wait"] = "loop_delay"; return await ask("seconds:")
        if sub == "toggle_edit": s["edit_delay_enabled"] = not s.get("edit_delay_enabled", False); return await show_send_step(cid)
        if sub == "edit_sec":
            get_conv(cid)["send_edit_wait"] = "sec"; return await ask("seconds:")
        if sub == "edit_ph":
            get_conv(cid)["send_edit_wait"] = "ph"; return await ask("placeholder text:")
        if sub == "toggle_edit_rand": s["edit_delay_random"] = not s.get("edit_delay_random", False); return await show_send_step(cid)
        if sub == "toggle_ph_rand": s["placeholder_random"] = not s.get("placeholder_random", False); return await show_send_step(cid)
        if sub == "toggle_multi": s["multi_step_edit"] = not s.get("multi_step_edit", False); return await show_send_step(cid)
        if sub == "attach":
            get_conv(cid)["send_file_upload"] = True; return await ask("send file:")
        if sub == "tgtnext": s["step"] = "max"; return await show_send_step(cid)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["send_wait"] = "max"; return await ask("number (0=∞):")
            try: s["max"] = int(v)
            except Exception: pass
            return await show_send_step(cid)
        if sub == "maxnext": s["step"] = "confirm"; return await show_send_step(cid)
        if sub == "back": s["step"] = "accounts"; return await show_send_step(cid)
        if sub == "prev":
            order = ["accounts", "compose", "target", "max", "confirm"]
            i = order.index(s.get("step", "accounts"))
            s["step"] = order[max(0, i - 1)]; return await show_send_step(cid)
        if sub == "back_edit": s["step"] = "accounts"; return await show_send_step(cid)
        if sub == "cancel": clear_conv(cid); return await show_main()
        if sub == "go":
            accounts = list_accounts(); sel = s.get("accounts") or []
            if "all" in sel: sel = list(accounts.keys())
            op = {"id": "sd_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "send", "accounts": sel, "target": s.get("target", "both"),
                  "max": s.get("max", 0) or 0, "payload": s.get("payload") or {"text": "hello", "kind": "text"},
                  "delay": 1.5, "auto_left": bool(s.get("auto_left", False)), "status": "running",
                  "groups_only": bool(s.get("groups_only", True)),
                  "attach_file": s.get("attach_file", ""),
                  "infinite_loop": bool(s.get("infinite_loop", False)),
                  "loop_delay": float(s.get("loop_delay", 3.0)),
                  "rescan_targets": bool(s.get("rescan_targets", True)),
                  "edit_delay_enabled": bool(s.get("edit_delay_enabled", False)),
                  "edit_delay_seconds": float(s.get("edit_delay_seconds", 3.0)),
                  "edit_delay_random": bool(s.get("edit_delay_random", False)),
                  "edit_delay_min": float(s.get("edit_delay_min", 2.0)),
                  "edit_delay_max": float(s.get("edit_delay_max", 6.0)),
                  "placeholder_text": s.get("placeholder_text", "hi"),
                  "placeholder_random": bool(s.get("placeholder_random", False)),
                  "placeholder_list": s.get("placeholder_list", ""),
                  "multi_step_edit": bool(s.get("multi_step_edit", False)),
                  "multi_step_middle": s.get("multi_step_middle", "Hi"),
                  "progress": {"sent":0,"failed":0,"total":0,"pending":0,"in_progress":0,
                               "phase":"start","blocked":0,"round":0},
                  "errors": []}
            _save_op(op); clear_conv(cid)
            asyncio.create_task(run_sender(op, log_cb)); return await show_op_detail(op["id"])

    if h == "jl":
        c = get_conv(cid)
        s = c.get("jl") or {"step":"account","accounts":[],"max_join":0,"speed":"fast","groups_only":True}
        c["jl"] = s; sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            c["jl"] = {"step":"account","accounts":[],"max_join":0,"speed":"fast","groups_only":True}
            return await jl_step_account(cid, c["jl"])
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await jl_step_account(cid, s)
        if sub == "speed" and len(p) >= 3: s["speed"] = p[2]; return await jl_step_settings(cid, s)
        if sub == "toggle_groups_only": s["groups_only"] = not s.get("groups_only", True); return await jl_step_settings(cid, s)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["jl_wait"] = "max"; return await ask("number:")
            try: s["max_join"] = int(v)
            except Exception: pass
            return await jl_step_max(cid, s)
        if sub == "next":
            if s["step"] == "account":
                if not s.get("accounts"): return await panel("no account selected.", kb_([B("« back", "jl:back")]), page_tag="jl:1")
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
            if not s.get("max_join"): return await panel("set max first.", kb_([B("« back", "jl:back")]), page_tag="jl:3")
            if not s.get("accounts"): return await panel("no account selected.", kb_([B("« back", "jl:back")]), page_tag="jl:1")
            speed_map = {"ultra":0.3, "fast":1.0, "normal":3.0, "slow":8.0}
            spd = s.get("speed", "fast")
            op = {"id": "jl_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "joinlef", "accounts": s.get("accounts") or [],
                  "max_join": s.get("max_join", 0), "status": "running", "speed": spd,
                  "join_delay": speed_map.get(spd, 1.0),
                  "groups_only": bool(s.get("groups_only", True)),
                  "auto_msg": (s.get("auto_msg") or "").strip(),
                  "progress": {"joined":0,"failed":0,"total":0,"phase":"start",
                               "already":0,"sent":0,"wave":0,"tried":0,
                               "skipped_seen":0,"skipped_banned":0,"rejected":0},
                  "errors": []}
            _save_op(op); c.pop("jl", None)
            JL_JOBS[op["id"]] = asyncio.create_task(run_joiner_lefter(op, log_cb))
            return await show_op_detail(op["id"])

    if h == "lf":
        c = get_conv(cid)
        s = c.get("lf") or {"step":"account","accounts":[],"mode":"all","delay":0.8}
        c["lf"] = s; sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            c["lf"] = {"step":"account","accounts":[],"mode":"all","delay":0.8}
            return await lf_step_account(cid, c["lf"])
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await lf_step_account(cid, s)
        if sub == "mode" and len(p) >= 3: s["mode"] = p[2]; return await lf_step_mode(cid, s)
        if sub == "delay" and len(p) >= 3:
            try: s["delay"] = float(p[2])
            except Exception: s["delay"] = 0.8
            return await lf_step_delay(cid, s)
        if sub == "next":
            if s["step"] == "account":
                if not s.get("accounts"): return await panel("no account selected.", kb_([B("« back", "lf:back")]), page_tag="lf:1")
                s["step"] = "mode"; return await lf_step_mode(cid, s)
            elif s["step"] == "mode":
                s["step"] = "delay"; return await lf_step_delay(cid, s)
        if sub == "back":
            if s["step"] == "mode": s["step"] = "account"
            elif s["step"] == "delay": s["step"] = "mode"
            return await show_lf_step(cid)
        if sub == "cancel": c.pop("lf", None); return await show_main()
        if sub == "go":
            if not s.get("accounts"): return await panel("no account selected.", kb_([B("« back", "lf:back")]), page_tag="lf:1")
            op = {"id": "lf_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "lefter", "accounts": s.get("accounts") or [],
                  "leave_mode": s.get("mode", "all"), "delay": s.get("delay", 0.8),
                  "status": "running",
                  "progress": {"joined":0,"failed":0,"total":0,"phase":"start"}, "errors": []}
            _save_op(op); c.pop("lf", None)
            asyncio.create_task(run_lefter(op, log_cb)); return await show_op_detail(op["id"])

    if h == "at":
        if data == "at:menu": return await show_at_menu()
        if data == "at:new":
            tpl = new_template("template " + secrets.token_hex(2))
            add_template(tpl); return await show_at_view(tpl["id"])
        if len(p) >= 3 and p[1].startswith("tp_"):
            tid = p[1]; act = p[2]
            if act == "view": return await show_at_view(tid)
            if act == "del":
                t = get_template(tid)
                if not t: return await show_at_menu()
                return await panel(f"delete <b>{esc(t.get('name','?'))}</b>?",
                                   kb_([B("yes", f"at:{tid}:delok"), B("no", f"at:{tid}:view")]),
                                   page_tag=f"at:{tid}:view")
            if act == "delok": delete_template(tid); await tg_send("deleted"); return await show_at_menu()
            if act == "rename":
                _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"meta","field":"name"}
                return await ask("name:")
            if act == "ch": return await show_at_channel(tid)
            if act == "pr": return await show_at_profile(tid)
            if act == "jn": return await show_at_joiner(tid)
            if act == "sn": return await show_at_sender(tid)
            if act == "pv": return await show_at_pv(tid)
            if act == "lf": return await show_at_lefter(tid)
            if act == "snmode": return await show_at_sender_mode(tid)
            if act == "chtype" and len(p) >= 4:
                update_template(tid, "channel", "type", p[3]); return await show_at_channel(tid)
            if act == "chset" and len(p) >= 4:
                field = p[3]
                if field == "photo_file":
                    get_conv(cid)["at_field_photo"] = {"tid": tid, "section": "channel", "field": "photo_file"}
                    return await ask("channel photo:")
                _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"channel","field":field}
                prompts = {"title":"title:","username":"username:","about":"about:"}
                return await ask(prompts.get(field, "value:"))
            if act == "prset" and len(p) >= 4:
                field = p[3]
                if field == "photo_file":
                    get_conv(cid)["at_field_photo"] = {"tid": tid, "section": "profile", "field": "photo_file"}
                    return await ask("profile photo:")
                _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"profile","field":field}
                prompts = {"first_name":"first name:","last_name":"last name:",
                           "username":"username:","bio":"bio:"}
                return await ask(prompts.get(field, "value:"))
            if act == "jnset" and len(p) >= 4:
                _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"joiner","field":p[3]}
                return await ask("max join:")
            if act == "jnspeed" and len(p) >= 4:
                update_template(tid, "joiner", "speed", p[3]); return await show_at_joiner(tid)
            if act == "jntoggle_groups_only":
                t = get_template(tid)
                if t: update_template(tid, "joiner", "groups_only", not bool(t.get("joiner", {}).get("groups_only", True)))
                return await show_at_joiner(tid)
            if act == "snset" and len(p) >= 4:
                field = p[3]
                _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"sender","field":field}
                prompts = {"text":"text:","target":"target (pv/groups/both):",
                           "max_send":"max (0=∞):","delay":"delay:"}
                return await ask(prompts.get(field, "value:"))
            if act == "snmode_set" and len(p) >= 4:
                update_template(tid, "sender", "mode", p[3]); return await show_at_sender(tid)
            if act == "sntoggle_loop":
                t = get_template(tid)
                if t:
                    snd = t.setdefault("sender", {})
                    snd["infinite_loop"] = not bool(snd.get("infinite_loop", False))
                    ts = list_templates(); ts[tid] = t; save_templates(ts)
                return await show_at_sender(tid)
            if act == "sntoggle_rescan":
                t = get_template(tid)
                if t:
                    snd = t.setdefault("sender", {})
                    snd["rescan_targets"] = not bool(snd.get("rescan_targets", True))
                    ts = list_templates(); ts[tid] = t; save_templates(ts)
                return await show_at_sender(tid)
            if act == "snset_loop_delay":
                _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"sender","field":"loop_delay"}
                return await ask("loop delay:")
            if act == "snedit" and len(p) >= 4:
                sub_act = p[3]
                ts = list_templates(); t2 = ts.get(tid)
                if sub_act in ("toggle","ph_rand","multi_toggle","toggle_existing"):
                    if t2:
                        snd2 = t2.setdefault("sender", {})
                        if sub_act == "toggle": snd2["edit_delay_enabled"] = not bool(snd2.get("edit_delay_enabled", False))
                        elif sub_act == "ph_rand": snd2["placeholder_random"] = not bool(snd2.get("placeholder_random", False))
                        elif sub_act == "multi_toggle": snd2["multi_step_edit"] = not bool(snd2.get("multi_step_edit", False))
                        elif sub_act == "toggle_existing": snd2["send_to_existing"] = not bool(snd2.get("send_to_existing", True))
                        save_templates(ts)
                    return await show_at_sender(tid)
                if sub_act == "sec":
                    _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"sender_edit","field":"edit_delay_seconds"}
                    return await ask("seconds:")
                if sub_act == "ph":
                    _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"sender_edit","field":"placeholder_text"}
                    return await ask("placeholder:")
                if sub_act == "file":
                    get_conv(cid)["at_field_photo"] = {"tid": tid, "section": "sender_edit", "field": "attach_file"}
                    return await ask("send file:")
            if act == "pv" and len(p) >= 4:
                sub_act = p[3]
                t2 = get_template(tid)
                if not t2: return await show_at_menu()
                pv2 = t2.setdefault("pv", {}); items = pv2.get("items") or []
                if sub_act == "toggle":
                    pv2["enabled"] = not bool(pv2.get("enabled", False))
                    update_template(tid, "pv", "enabled", pv2["enabled"]); return await show_at_pv(tid)
                if sub_act == "cycle_max":
                    seq = [1, 2, 3, 5, 0]; cur = int(pv2.get("max_replies", 1) or 0)
                    nv = seq[(seq.index(cur) + 1) % len(seq)] if cur in seq else 1
                    update_template(tid, "pv", "max_replies", nv); return await show_at_pv(tid)
                if sub_act == "set_delay":
                    get_conv(cid)["pv_tpl_wait"] = {"tid": tid, "kind": "delay"}; return await ask("delay:")
                if sub_act == "toggle_apply":
                    update_template(tid, "pv", "apply_to_accounts", not bool(pv2.get("apply_to_accounts", True)))
                    return await show_at_pv(tid)
                if sub_act == "add_text":
                    get_conv(cid)["pv_tpl_wait"] = {"tid": tid, "kind": "add_text"}; return await ask("text:")
                if sub_act == "add_saved":
                    get_conv(cid)["pv_tpl_save_msg"] = {"tid": tid}; return await ask("message:")
                if sub_act == "add_delay":
                    get_conv(cid)["pv_tpl_wait"] = {"tid": tid, "kind": "add_delay_sec"}; return await ask("seconds:")
                if sub_act == "list": return await show_at_pv_list(tid)
                if sub_act == "del" and len(p) >= 5:
                    try: i = int(p[4])
                    except Exception: return await show_at_pv_list(tid)
                    if 0 <= i < len(items): items.pop(i)
                    update_template(tid, "pv", "items", items)
                    await tg_send("deleted"); return await show_at_pv_list(tid)
            if act == "lfset" and len(p) >= 4:
                update_template(tid, "lefter", "leave_mode", p[3]); return await show_at_lefter(tid)
            if act == "run": return await show_at_run(tid)
            if act == "run_acc" and len(p) >= 4:
                aid = p[3]; c = get_conv(cid)
                ar = c.setdefault("at_run", {"template_id": tid, "accounts": []})
                sel = ar.setdefault("accounts", [])
                if aid in sel: sel.remove(aid)
                else: sel.append(aid)
                return await show_at_run(tid)
            if act == "run_go":
                c = get_conv(cid); ar = c.get("at_run") or {}; sel = ar.get("accounts") or []
                if not sel: return await panel("no account selected.", kb_(nav(f"at:{tid}:view")), page_tag=f"at:{tid}:run:0")
                op = {"id": "at_" + secrets.token_hex(5), "created": int(time.time()),
                      "type": "autotar", "accounts": sel, "template_id": tid, "status": "running",
                      "progress": {"joined":0,"failed":0,"total":0,"pending":0,"in_progress":0,
                                   "phase":"start","sent":0,"already":0,"tried":0,"wave":0,
                                   "left":0,"round":0,"skipped_seen":0,"skipped_banned":0,"rejected":0},
                      "errors": []}
                _save_op(op); c.pop("at_run", None)
                asyncio.create_task(run_auto_tar(op, log_cb)); return await show_op_detail(op["id"])
            if len(p) == 3 and p[2].isdigit(): return await show_at_run(tid, int(p[2]))

    if h == "cfg":
        sub = p[1] if len(p) > 1 else ""
        if sub == "set" and len(p) >= 3:
            key = p[2]; get_conv(cid)["cfg_wait"] = key; return await ask(f"new value for {key}:")
        if sub == "toggle_autojoin":
            cfg = _load(CFG_FILE, DEFAULT_CFG)
            cfg["auto_join_linkdoni"] = 0 if int(cfg.get("auto_join_linkdoni", 1)) else 1
            _save(CFG_FILE, cfg); return await show_cfg()
        if sub == "toggle_listener":
            cfg = _load(CFG_FILE, DEFAULT_CFG)
            cfg["listener"] = 0 if int(cfg.get("listener", 1)) else 1
            _save(CFG_FILE, cfg); return await show_cfg()

# ═══════════════ boot ═══════════════
async def _post_init(app):
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "start"),
            BotCommand("menu", "menu"),
        ])
    except Exception: pass
    try: _loop_ref[0] = asyncio.get_running_loop()
    except Exception: pass
    try:
        await start_all_listeners()
        await start_pv_responders()
        asyncio.create_task(keepalive_loop())
    except Exception as e: flog(f"[post_init] {type(e).__name__}: {e}", "error")
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
        flog(f"[callback] {data}: {traceback.format_exc()}", "error")
        await tg_send(f"err: {type(e).__name__}: {str(e)[:200]}")
def main(token=None, owner_id=None):
    global APP, TG_TOKEN, FORCED_OWNER
    if token: TG_TOKEN = token
    else: TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
    if not TG_TOKEN or ":" not in TG_TOKEN:
        print("[x] no TG_TOKEN."); return
    if owner_id: FORCED_OWNER = int(owner_id)
    else:
        try: FORCED_OWNER = int(os.environ.get("TG_OWNER_ID", "8389746549"))
        except Exception: FORCED_OWNER = 8389746549
    STATE["owner"] = FORCED_OWNER
    try: os.makedirs(DATA_DIR, exist_ok=True)
    except Exception: pass
    print(f"[+] VERSION: {VERSION}")
    print(f"[+] DATA_DIR: {DATA_DIR}")
    print(f"[+] OWNER: {FORCED_OWNER}")
    req = HTTPXRequest(connection_pool_size=8, connect_timeout=30.0,
                       read_timeout=30.0, write_timeout=30.0, pool_timeout=30.0)
    APP = (Application.builder().token(TG_TOKEN).request(req)
           .get_updates_request(req).post_init(_post_init).build())
    APP.add_handler(CommandHandler("start", cmd_start))
    APP.add_handler(CommandHandler("menu", cmd_menu))
    APP.add_handler(CallbackQueryHandler(on_callback))
    APP.add_handler(MessageHandler(tg_filters.ALL & ~tg_filters.COMMAND, on_message))
    APP.add_error_handler(_on_error)
    print("[+] polling...")
    APP.run_polling(allowed_updates=Update.ALL_TYPES, poll_interval=2.0, timeout=30.0)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n[!] stop")