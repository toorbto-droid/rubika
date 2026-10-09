"""Rubika Web Panel — FastAPI + Bot (v12 — clean logs + app.py support)"""

# ══════════════════════════════════════════════════════════════
# ★ گام ۱: همه لاگرها رو قبل از هر کاری خفه کن
# ══════════════════════════════════════════════════════════════
import sys, os, io, contextlib, logging

REAL_STDOUT = sys.stdout
REAL_STDERR = sys.stderr

logging.basicConfig(level=logging.CRITICAL, stream=io.StringIO())
for _name in ("", "uvicorn", "uvicorn.error", "uvicorn.access",
              "httpx", "httpcore", "telegram", "telegram.ext",
              "urllib3", "aiohttp", "asyncio", "fastapi",
              "multipart", "rubpy", "requests", "web"):
    _lg = logging.getLogger(_name)
    _lg.setLevel(logging.CRITICAL)
    _lg.propagate = False
    _lg.handlers = [logging.NullHandler()]

# ─── patch signal handler (برای thread-safe بودن asyncio روی Railway) ───
try:
    import asyncio.unix_events as _ue
    _orig_add_signal = _ue._UnixSelectorEventLoop.add_signal_handler
    def _safe_add_signal(self, sig, callback, *args):
        try:
            return _orig_add_signal(self, sig, callback, *args)
        except (RuntimeError, ValueError, NotImplementedError, AttributeError):
            return None
    _ue._UnixSelectorEventLoop.add_signal_handler = _safe_add_signal
except Exception:
    pass

import json, time, secrets, asyncio, importlib.util, tempfile, threading, runpy, re
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import (FastAPI, Response, HTTPException, WebSocket, WebSocketDisconnect,
                     UploadFile, File, Cookie, Depends, Query, Request, Form)
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = Path(__file__).parent.resolve()
LOG_FILE = HERE / "bot_runtime.log"
log = logging.getLogger("web")   # دیگه چیزی چاپ نمی‌کنه

PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"


def pyd_dict(obj, exclude_none=True):
    if hasattr(obj, "model_dump"): return obj.model_dump(exclude_none=exclude_none)
    return obj.dict(exclude_none=exclude_none)


# ══════════════════════════════════════════════════════════════
# ★ پیدا کردن فایل ربات — هم app.py هم rubika_tg_bot.py
# ══════════════════════════════════════════════════════════════
BOT_FILENAMES = ("app.py", "rubika_tg_bot.py")


def _find_bot():
    env = os.environ.get("RUBIKA_BOT_DIR")
    if env:
        base = Path(env).expanduser().resolve()
        for name in BOT_FILENAMES:
            p = base / name
            if p.is_file(): return p.parent, p

    candidates = []
    for name in BOT_FILENAMES:
        candidates += [
            HERE / name,
            HERE.parent / name,
            HERE / "webapp" / name,
            HERE.parent / "webapp" / name,
            Path("/app") / name,
            Path("/home/container") / name,
            Path("/storage/emulated/0/rubika") / name,
            Path("/storage/emulated/0") / name,
            Path("/sdcard/rubika") / name,
        ]
    for c in candidates:
        try:
            if c.is_file(): return c.parent.resolve(), c.resolve()
        except Exception: continue

    for base in (Path.cwd(), HERE):
        for parent in [base] + list(base.parents):
            for name in BOT_FILENAMES:
                c = parent / name
                try:
                    if c.is_file(): return c.parent.resolve(), c.resolve()
                except Exception: continue
    return None, None


BOT_DIR, BOT_PATH = _find_bot()
if not BOT_PATH:
    print("❌  نه app.py پیدا شد نه rubika_tg_bot.py", file=REAL_STDERR)
    sys.exit(1)
os.chdir(BOT_DIR)


# ══════════════════════════════════════════════════════════════
# ★ گام ۲: خروجی ربات رو کامل بگیر و بریز توی فایل لاگ
# ══════════════════════════════════════════════════════════════
_import_buf = io.StringIO()
with contextlib.redirect_stdout(_import_buf), contextlib.redirect_stderr(_import_buf):
    spec = importlib.util.spec_from_file_location("rubika_bot", str(BOT_PATH))
    bot = importlib.util.module_from_spec(spec)
    sys.modules["rubika_bot"] = bot
    spec.loader.exec_module(bot)

# ذخیره خروجی import در فایل لاگ
try:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n===== import @ {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        f.write(_import_buf.getvalue())
except Exception:
    pass


from telegram import Bot as TGBot

_TG_TOKEN = getattr(bot, "TG_TOKEN", None) or os.environ.get("TG_TOKEN", "")
if not _TG_TOKEN or ":" not in _TG_TOKEN:
    print("❌  TG_TOKEN پیدا نشد. مقدارش رو در app.py ست کن یا env بذار.", file=REAL_STDERR)
    sys.exit(1)
TG = TGBot(token=_TG_TOKEN)

SESS_FILE = "web_sessions.json"
LOGIN_CTX: Dict[int, Dict[str, Any]] = {}
PENDING: Dict[int, Dict[str, Any]] = {}
SESSIONS: Dict[str, Dict[str, Any]] = {}
if os.path.exists(SESS_FILE):
    try: SESSIONS = json.load(open(SESS_FILE, encoding="utf-8"))
    except: SESSIONS = {}
LOGS: List[dict] = []
MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None


def save_sessions():
    with open(SESS_FILE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(SESSIONS, f, ensure_ascii=False, indent=2)
    os.replace(SESS_FILE + ".tmp", SESS_FILE)


def get_owner():
    try:
        with open("tg_owner.json", encoding="utf-8") as f:
            return json.load(f).get("owner")
    except: return None


def gen_code():
    return str(secrets.randbelow(900000) + 100000)


class Conn:
    def __init__(self, ws: WebSocket, uid: int):
        self.ws = ws; self.uid = uid
        self.q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.subs: set = set(); self.alive = True
        self.writer: Optional[asyncio.Task] = None
    def push(self, msg) -> bool:
        if not self.alive: return False
        try: self.q.put_nowait(msg); return True
        except asyncio.QueueFull: self.alive = False; return False
    async def _write(self):
        try:
            while True:
                msg = await self.q.get()
                if isinstance(msg, str): await self.ws.send_text(msg)
                else: await self.ws.send_json(msg)
        except asyncio.CancelledError: raise
        except Exception: pass
        finally: self.alive = False


class Hub:
    def __init__(self): self.conns: set = set()
    async def connect(self, ws, uid):
        await ws.accept(); c = Conn(ws, uid)
        c.writer = asyncio.create_task(c._write())
        self.conns.add(c); return c
    def disconnect(self, c):
        c.alive = False; self.conns.discard(c)
        if c.writer: c.writer.cancel()
    async def broadcast(self, msg, uid=None):
        for c in list(self.conns):
            if uid and c.uid != uid: continue
            if not c.push(msg): self.disconnect(c)


HUB = Hub()


def wlog(msg):
    """لاگ رو فقط می‌ریزه توی بافر داخلی — به کنسول چیزی نمی‌ره."""
    entry = {"text": str(msg)[:600], "ts": time.time()}
    LOGS.append(entry)
    if len(LOGS) > 500: LOGS.pop(0)
    try:
        if MAIN_LOOP and MAIN_LOOP.is_running():
            asyncio.run_coroutine_threadsafe(
                HUB.broadcast({"type": "log", "text": entry["text"], "ts": entry["ts"]}),
                MAIN_LOOP)
    except Exception:
        pass


try: bot.log_cb = wlog
except: pass

app = FastAPI(title="Rubika Web Panel")
STATIC = next((c for c in [HERE/"static", HERE.parent/"static",
                            BOT_DIR/"webapp"/"static", BOT_DIR/"static"]
               if c.is_dir() and (c/"login.html").exists()), HERE/"static")
if STATIC.is_dir(): app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.on_event("startup")
async def _startup():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()


def _get_token(request: Request) -> Optional[str]:
    tok = request.cookies.get("session")
    if tok: return tok
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        tok = auth[7:].strip()
        if tok: return tok
    return request.query_params.get("token")


def _check_token(tok):
    if not tok or tok not in SESSIONS: return None
    s = SESSIONS[tok]
    if time.time() > s["exp"]:
        SESSIONS.pop(tok, None); save_sessions(); return None
    return s


async def get_uid(request: Request) -> int:
    s = _check_token(_get_token(request))
    if not s: raise HTTPException(401, "unauth")
    return s["uid"]


def _page(n): return FileResponse(str(STATIC / n))
def _require(req, page):
    if not _check_token(_get_token(req)):
        return RedirectResponse("/login", status_code=302)
    return _page(page)


# ══════════════════════════════════════════════════════════════
# HTML Pages
# ══════════════════════════════════════════════════════════════
@app.get("/")
async def root(req: Request):
    return RedirectResponse("/dash" if _check_token(_get_token(req)) else "/login", status_code=302)

@app.get("/login")
async def p_login(): return _page("login.html")

@app.get("/dash")
async def p_dash(request: Request): return _require(request, "dash.html")

@app.get("/accounts")
async def p_accs(request: Request): return _require(request, "accounts.html")

@app.get("/chats")
async def p_chats(request: Request): return _require(request, "chats.html")

@app.get("/chat/{aid}/{guid}")
async def p_chat_detail(request: Request, aid: str, guid: str):
    if not _check_token(_get_token(request)):
        return RedirectResponse("/login", status_code=302)
    return _page("chat.html")

@app.get("/send")
async def p_send(request: Request): return _require(request, "send.html")

@app.get("/channels")
async def p_chan(request: Request): return _require(request, "channels.html")

@app.get("/extract")
async def p_extr(request: Request): return _require(request, "extract.html")

@app.get("/reports")
async def p_rep(request: Request): return _require(request, "reports.html")

@app.get("/settings/{aid}")
async def p_settings_acc(request: Request, aid: str):
    if not _check_token(_get_token(request)):
        return RedirectResponse("/login", status_code=302)
    return _page("settings.html")

@app.get("/settings")
async def p_set(request: Request): return _require(request, "settings.html")

@app.get("/logs")
async def p_logs(request: Request): return _require(request, "logs.html")


class LoginReq(BaseModel): telegram_id: int
class VerifyReq(BaseModel): telegram_id: int; code: str


@app.post("/api/auth/request")
async def auth_request(req: LoginReq):
    owner = get_owner()
    if not owner: raise HTTPException(400, "مالک تعیین نشده")
    if req.telegram_id != owner: raise HTTPException(403, "فقط مالک")
    code = gen_code()
    PENDING[req.telegram_id] = {"code": code, "exp": time.time() + 300, "tries": 0}
    try:
        await TG.send_message(chat_id=req.telegram_id,
            text=f"🔐 <b>کد ورود پنل</b>\n\n<code>{code}</code>\n\n<i>۵ دقیقه</i>",
            parse_mode="HTML")
    except Exception as e:
        raise HTTPException(500, f"ارسال نشد: {e}")
    return {"ok": True}


@app.post("/api/auth/verify")
async def auth_verify(req: VerifyReq, response: Response):
    p = PENDING.get(req.telegram_id)
    if not p: raise HTTPException(400, "اول کد بگیر")
    if time.time() > p["exp"]:
        PENDING.pop(req.telegram_id, None); raise HTTPException(400, "منقضی")
    if p["code"] != req.code.strip():
        p["tries"] += 1
        if p["tries"] >= 5: PENDING.pop(req.telegram_id, None)
        raise HTTPException(400, f"کد اشتباه ({p['tries']}/5)")
    PENDING.pop(req.telegram_id, None)
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"uid": req.telegram_id, "exp": time.time() + 7*86400}
    save_sessions()
    response.set_cookie("session", token, httponly=True, samesite="lax",
                        secure=True, path="/", max_age=7*86400)
    return {"ok": True, "token": token}


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response):
    tok = _get_token(request)
    if tok: SESSIONS.pop(tok, None); save_sessions()
    response.delete_cookie("session", path="/")
    return {"ok": True}


@app.get("/api/me")
async def me(uid: int = Depends(get_uid)): return {"telegram_id": uid}


CLIENTS: Dict[str, Dict[str, Any]] = {}
_LOCKS: Dict[str, asyncio.Lock] = {}
CLIENT_RECENT_SEC = 120
CLIENT_HC_TIMEOUT = 15.0


def _lock_for(aid: str) -> asyncio.Lock:
    l = _LOCKS.get(aid)
    if l is None:
        l = asyncio.Lock()
        _LOCKS[aid] = l
    return l


def _cli_alive(cli) -> bool:
    for attr in ("session", "_session", "http_session", "aiohttp_session"):
        s = getattr(cli, attr, None)
        if s is None: continue
        closed = getattr(s, "closed", None)
        if closed is not None: return not closed
    return True


def _is_dead_session_error(e) -> bool:
    s = str(e).lower()
    return any(k in s for k in (
        "session is closed", "connector is closed",
        "client session has been closed", "cannot connect",
        "connection reset", "server disconnected",
        "event loop is closed", "unclosed client session",
        "invalid_auth", "invalid auth", "not_registered",
        "auth_dead", "unauthorized", "auth_invalid",
    ))


async def _make_client(aid: str):
    acc = bot.get_account(aid)
    if not acc: raise HTTPException(404, "اکانت نیست")
    cli = bot.SafeClient(
        name=acc["session_name"], auth=acc["auth"],
        private_key=acc["private_key"], phone_number=acc["phone"],
        platform='Android', display_welcome=False,
        timeout=30, max_retries=3,
    )
    try:
        await cli.__aenter__()
    except RuntimeError as er:
        raise HTTPException(401, f"AUTH_DEAD: {str(er)[:150]}")
    return cli


async def _safe_exit(cli):
    try: await cli.__aexit__(None, None, None)
    except Exception: pass


async def get_client(aid: str):
    now = time.time()
    entry = CLIENTS.get(aid)
    if entry and _cli_alive(entry["cli"]):
        if (now - entry["ts"]) < CLIENT_RECENT_SEC:
            return entry["cli"]

    async with _lock_for(aid):
        entry = CLIENTS.get(aid)
        if entry and _cli_alive(entry["cli"]):
            age = time.time() - entry["ts"]
            if age < CLIENT_RECENT_SEC:
                return entry["cli"]
            try:
                await asyncio.wait_for(entry["cli"].get_me(), timeout=CLIENT_HC_TIMEOUT)
                entry["ts"] = time.time()
                return entry["cli"]
            except asyncio.TimeoutError:
                entry["ts"] = time.time()
                return entry["cli"]
            except Exception as e:
                estr = str(e).lower()
                if (_is_dead_session_error(e) or "invalid_auth" in estr
                        or "not_registered" in estr or "invalid auth" in estr):
                    CLIENTS.pop(aid, None)
                    try:
                        asyncio.get_running_loop().create_task(_safe_exit(entry["cli"]))
                    except RuntimeError: pass
                    raise HTTPException(401, "AUTH_DEAD: session expired, relogin needed")
                else:
                    entry["ts"] = time.time()
                    return entry["cli"]

        cli = await _make_client(aid)
        CLIENTS[aid] = {"cli": cli, "ts": time.time()}
        return cli


async def get_client_cached(aid: str):
    entry = CLIENTS.get(aid)
    if entry and _cli_alive(entry["cli"]):
        return entry["cli"]
    return None


async def drop_client(aid: str):
    _CHAT_LIST_CACHE.pop(aid, None)
    async with _lock_for(aid):
        entry = CLIENTS.pop(aid, None)
    if entry:
        try: await entry["cli"].__aexit__(None, None, None)
        except Exception: pass


def invalidate_client(aid: str):
    entry = CLIENTS.pop(aid, None)
    if entry:
        try:
            asyncio.get_running_loop().create_task(_safe_exit(entry["cli"]))
        except RuntimeError: pass


_MY_GUID: Dict[str, str] = {}
_MY_GUID_LOCKS: Dict[str, asyncio.Lock] = {}


async def get_my_guid(aid: str) -> Optional[str]:
    if aid in _MY_GUID: return _MY_GUID[aid]
    lock = _MY_GUID_LOCKS.setdefault(aid, asyncio.Lock())
    async with lock:
        if aid in _MY_GUID: return _MY_GUID[aid]
        try:
            cli = await get_client(aid)
            me_ = await cli.get_me()
            g = me_.user.user_guid
            _MY_GUID[aid] = g; return g
        except Exception: return None


_CHAT_LIST_CACHE: Dict[str, Dict[str, Any]] = {}
CHAT_LIST_TTL = 180

_ACCOUNT_IDS_CACHE = {"data": set(), "ts": 0.0}


def _account_ids_cached():
    now = time.time()
    if now - _ACCOUNT_IDS_CACHE["ts"] > 5:
        try: _ACCOUNT_IDS_CACHE["data"] = set(bot.list_accounts().keys())
        except Exception: pass
        _ACCOUNT_IDS_CACHE["ts"] = now
    return _ACCOUNT_IDS_CACHE["data"]


@app.get("/api/accounts")
async def api_accounts(uid: int = Depends(get_uid)):
    out = []
    for aid, a in bot.list_accounts().items():
        out.append({"id": aid, "name": a.get("name"), "phone": a.get("phone"),
                    "user_guid": a.get("user_guid"), "created": a.get("created", 0),
                    "channels_count": len(a.get("channels", []))})
    return {"accounts": out}


class AddAccReq(BaseModel): phone: str

@app.post("/api/accounts/add")
async def api_acc_add(req: AddAccReq, uid: int = Depends(get_uid)):
    p = req.phone.replace("+", "").replace(" ", "").replace("-", "")
    if p.startswith("0"): p = "98" + p[1:]
    if not p.isdigit() or len(p) < 10: raise HTTPException(400, "شماره نامعتبر")
    try: ctx = await bot.rubika_send_code(p)
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    LOGIN_CTX[uid] = ctx
    st = ctx.get("status")
    return {"ok": True, "need_passkey": st == "SendPassKey", "hint": ctx.get("hint"), "status": st}


class VerifyAccReq(BaseModel): code: str = ""; pass_key: Optional[str] = None

@app.post("/api/accounts/verify")
async def api_acc_verify(req: VerifyAccReq, uid: int = Depends(get_uid)):
    ctx = LOGIN_CTX.get(uid)
    if not ctx: raise HTTPException(400, "اول شماره رو بفرست")
    if req.pass_key:
        try:
            res = await ctx["client"].send_code(phone_number=ctx["phone"], pass_key=req.pass_key)
            if getattr(res, "status", None) != "OK": raise HTTPException(400, "رمز غلط")
            ctx["phone_code_hash"] = res.phone_code_hash
        except HTTPException: raise
        except Exception as e: raise HTTPException(400, bot._fmt_error(e))
        return {"ok": True, "step": "code"}
    try: res = await bot.rubika_complete_login(ctx, req.code)
    except Exception as e: raise HTTPException(400, bot._fmt_error(e))
    if not res.get("ok"): raise HTTPException(400, f"کد اشتباه ({res.get('status')})")
    LOGIN_CTX.pop(uid, None)
    _MY_GUID.pop(res["aid"], None)
    _ACCOUNT_IDS_CACHE["ts"] = 0
    wlog(f"✅ اکانت جدید: {res['name']}")
    return {"ok": True, "aid": res["aid"], "name": res["name"]}


@app.delete("/api/accounts/{aid}")
async def api_acc_del(aid: str, uid: int = Depends(get_uid)):
    await drop_client(aid); bot.remove_account(aid); _MY_GUID.pop(aid, None)
    _ACCOUNT_IDS_CACHE["ts"] = 0
    return {"ok": True}


@app.post("/api/accounts/{aid}/relogin")
async def api_acc_relogin(aid: str, uid: int = Depends(get_uid)):
    a = bot.get_account(aid)
    if not a: raise HTTPException(404, "اکانت نیست")
    try: ctx = await bot.rubika_send_code(a["phone"])
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    LOGIN_CTX[uid] = ctx
    return {"ok": True, "need_passkey": ctx.get("status") == "SendPassKey", "hint": ctx.get("hint")}


@app.get("/api/accounts/{aid}/profile")
async def api_profile(aid: str, uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    p = await bot.rubika_get_my_profile(cli)
    try:
        me_ = await cli.get_me(); p["user_guid"] = me_.user.user_guid
    except Exception: pass
    return p


class ProfileReq(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    username: Optional[str] = None


@app.post("/api/accounts/{aid}/profile")
async def api_profile_upd(aid: str, req: ProfileReq, uid: int = Depends(get_uid)):
    cli = await get_client(aid); results = []
    if req.first_name is not None:
        ok, info = await bot.rubika_set_name(cli, req.first_name, req.last_name or "")
        results.append({"field": "name", "ok": ok, "info": str(info)[:200]})
        if ok: bot.update_account_field(aid, "name", req.first_name)
    if req.bio is not None:
        ok, info = await bot.rubika_set_bio(cli, req.bio)
        results.append({"field": "bio", "ok": ok, "info": str(info)[:200]})
    if req.username:
        ok, info = await bot.rubika_set_username(cli, req.username.strip())
        results.append({"field": "username", "ok": ok, "info": str(info)[:200]})
    return {"results": results}


@app.get("/api/accounts/{aid}/chats")
async def api_chats(aid: str, uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    try:
        raw = await bot.get_all_chats_raw(cli)
        me_ = await cli.get_me(); my = me_.user.user_guid
        pv = [c for c in raw if c["type"] == "User" and c["guid"] != my and not c["is_blocked"]]
        gr = [c for c in raw if c["type"] == "Group"]
        ch = [c for c in raw if c["type"] == "Channel"]
        return {"pv": pv, "groups": gr, "channels": ch, "total": len(raw)}
    except Exception as e:
        if _is_dead_session_error(e): invalidate_client(aid)
        raise HTTPException(500, bot._fmt_error(e))


@app.get("/api/accounts/{aid}/chat-list")
async def api_chat_list(aid: str, force: bool = False, uid: int = Depends(get_uid)):
    now = time.time()
    c = _CHAT_LIST_CACHE.get(aid)
    if c and not force and (now - c["ts"]) < CHAT_LIST_TTL:
        return c["data"]

    cli = await get_client(aid)
    try:
        raw = await bot.get_all_chats_raw(cli)
        me_ = await cli.get_me()
        my = me_.user.user_guid
        _MY_GUID[aid] = my

        for x in raw:
            t = (x.get("type") or "").lower()
            if t == "user":     x["type"] = "User"
            elif t == "group":  x["type"] = "Group"
            elif t == "channel":x["type"] = "Channel"
            elif t == "bot":    x["type"] = "Bot"
            elif t == "service":x["type"] = "Service"

        sem = asyncio.Semaphore(12)

        async def fetch_last(x):
            async with sem:
                try:
                    msgs = await bot.fetch_messages(cli, x["guid"], 1, my)
                    if msgs:
                        m = msgs[0] or {}
                        t = m.get("time") or 0
                        try: t = int(t)
                        except: t = 0
                        if t > 1_000_000_000_000: t //= 1000
                        return {**x, "last_text": (m.get("text") or "")[:140],
                                "last_time": t,
                                "last_is_mine": bool(m.get("is_mine")),
                                "last_type": m.get("type") or "Text"}
                except Exception:
                    pass
                return {**x, "last_text": "", "last_time": 0,
                        "last_is_mine": False, "last_type": ""}

        enriched = list(await asyncio.gather(*[fetch_last(x) for x in raw]))
        enriched.sort(key=lambda y: y.get("last_time") or 0, reverse=True)

        pv, gr, ch, bots = [], [], [], []
        for y in enriched:
            t = y.get("type") or ""
            g = y.get("guid") or ""
            if g == my: continue
            if t == "User":
                if y.get("is_blocked"): continue
                pv.append(y)
            elif t == "Group":   gr.append(y)
            elif t == "Channel": ch.append(y)
            elif t in ("Bot", "Service"): bots.append(y)

        data = {"pv": pv, "groups": gr, "channels": ch, "bots": bots,
                "total": len(enriched)}
        _CHAT_LIST_CACHE[aid] = {"ts": now, "data": data}
        return data
    except Exception as e:
        if _is_dead_session_error(e): invalidate_client(aid)
        raise HTTPException(500, bot._fmt_error(e))


@app.get("/api/accounts/{aid}/chats/{guid}/info")
async def api_chat_info(aid: str, guid: str, uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    try:
        info = None
        for m in ("get_chat_info", "getChatInfo", "get_object_info",
                  "getObjectInfo", "get_channel_info", "getChannelInfo"):
            fn = getattr(cli, m, None)
            if not fn: continue
            try:
                for kwargs in ({"object_guid": guid}, {"chat_id": guid}):
                    try:
                        r = fn(**kwargs)
                        if asyncio.iscoroutine(r): r = await r
                        if r: info = r; break
                    except TypeError: continue
                if info: break
            except Exception: continue
        if not info:
            raw = await bot.get_all_chats_raw(cli)
            info = next((c for c in raw if c["guid"] == guid), {})
        g = lambda *ks, d=None: bot._g(info, *ks, default=d)
        return {"guid": guid,
                "title": g("first_name", "firstName", "title", "name") or "",
                "username": g("username", "user_name") or "",
                "bio": g("bio", "about", "description") or "",
                "type": g("type") or "", "phone": g("phone") or "",
                "avatar": g("avatar", "avatar_url", "avatarUrl", "profile_photo",
                            "profilePhoto", "photo", "photo_url") or ""}
    except Exception as e:
        raise HTTPException(500, bot._fmt_error(e))


async def _bot_fetch(cli, guid, limit, my, **kw):
    try: return await bot.fetch_messages(cli, guid, limit, my, **kw)
    except TypeError: return None


def _inc_id(mid: str) -> str:
    try: return str(int(mid) + 1)
    except (TypeError, ValueError): return mid


def _attach_reply_previews(msgs):
    by_id = {str(m.get("id") or ""): m for m in msgs if m.get("id")}
    for m in msgs:
        rid = m.get("reply_to_message_id") or m.get("reply_to")
        if rid is None: continue
        p = by_id.get(str(rid))
        if not p: continue
        m["reply_preview"] = {
            "id": str(rid), "text": (p.get("text") or "")[:120],
            "sender": p.get("sender") or ("شما" if p.get("is_mine") else ""),
            "type": p.get("type") or "Text"}


def _mtime(m):
    try: t = int(m.get("time") or 0)
    except Exception: t = 0
    return t // 1000 if t > 1_000_000_000_000 else t


async def _fetch_before(cli, guid, before_id, limit, my):
    last_err = None
    for anchor in (before_id, _inc_id(before_id)):
        for kw in ({"max_id": anchor}, {"from_max_id": anchor},
                   {"before_id": anchor}, {"offset_id": anchor}):
            try: r = await _bot_fetch(cli, guid, limit, my, **kw)
            except HTTPException: raise
            except Exception as e: last_err = e; continue
            if r is not None: return r
    if last_err: raise last_err
    raise HTTPException(501, "fetch_messages: max_id پشتیبانی نمی‌شود")


async def _fetch_after(cli, guid, mid, limit, my):
    for anchor in (mid, _inc_id(mid)):
        for kw in ({"min_id": anchor}, {"from_min_id": anchor}, {"after_id": anchor}):
            try: r = await _bot_fetch(cli, guid, limit, my, **kw)
            except Exception: continue
            if r is not None: return r
    return None


async def _fetch_around(cli, guid, mid, limit, my):
    half = max(limit // 2, 5)
    older = await _fetch_before(cli, guid, mid, half + 2, my)
    try: newer = await _fetch_after(cli, guid, mid, half + 2, my)
    except Exception: newer = None
    combined = list(reversed(older or [])) + (newer or [])
    combined.sort(key=_mtime)
    seen, out = set(), []
    for m in combined:
        i = str(m.get("id") or "")
        if i and i in seen: continue
        if i: seen.add(i)
        out.append(m)
    if len(out) > limit:
        idx = next((i for i, m in enumerate(out)
                    if str(m.get("id") or "") == str(mid)), len(out) // 2)
        start = max(0, idx - limit // 2)
        end = start + limit
        if end > len(out): end = len(out); start = max(0, end - limit)
        out = out[start:end]
    return out


@app.get("/api/accounts/{aid}/chats/{guid}/messages")
async def api_chat_msgs(aid: str, guid: str, limit: int = 30,
                        before_id: Optional[str] = None,
                        around: Optional[str] = None,
                        uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    my = _MY_GUID.get(aid) or await get_my_guid(aid)
    limit = max(1, min(int(limit), 100))
    try:
        if around:
            try:
                msgs = await _fetch_around(cli, guid, str(around), limit, my)
                if msgs:
                    _attach_reply_previews(msgs)
                    return {"messages": msgs, "has_more": False, "around": True}
            except Exception as e:
                if _is_dead_session_error(e): invalidate_client(aid)
            try:
                msgs = await bot.fetch_messages(cli, guid, limit, my)
                _attach_reply_previews(msgs)
                return {"messages": msgs, "has_more": True, "around_failed": True}
            except Exception as e2:
                if _is_dead_session_error(e2): invalidate_client(aid)
                raise HTTPException(500, bot._fmt_error(e2))
        if before_id:
            try: msgs = await _fetch_before(cli, guid, str(before_id), limit, my)
            except Exception as e:
                if _is_dead_session_error(e): invalidate_client(aid)
                raise HTTPException(500, bot._fmt_error(e))
        else:
            try: msgs = await bot.fetch_messages(cli, guid, limit, my)
            except Exception as e:
                if _is_dead_session_error(e): invalidate_client(aid)
                raise HTTPException(500, bot._fmt_error(e))
        has_more = len(msgs) >= limit
        _attach_reply_previews(msgs)
        return {"messages": msgs, "has_more": has_more}
    except HTTPException: raise
    except Exception as e:
        if _is_dead_session_error(e): invalidate_client(aid)
        raise HTTPException(500, bot._fmt_error(e))


@app.get("/api/accounts/{aid}/search")
async def api_search(aid: str, q: str = Query(""), limit: int = 60,
                     uid: int = Depends(get_uid)):
    q = q.strip()
    if not q: return {"results": []}
    cli = await get_client(aid)
    my = _MY_GUID.get(aid) or await get_my_guid(aid)
    try: raw = await bot.get_all_chats_raw(cli)
    except Exception as e:
        if _is_dead_session_error(e): invalidate_client(aid)
        raise HTTPException(500, bot._fmt_error(e))
    sem = asyncio.Semaphore(8); q_low = q.lower(); results = []
    async def search(c):
        async with sem:
            try:
                msgs = await bot.fetch_messages(cli, c["guid"], 50, my)
                for m in msgs:
                    if q_low in (m.get("text") or "").lower():
                        results.append({"chat": {"guid": c["guid"], "type": c["type"],
                                                "title": c["title"] or c["guid"][:20],
                                                "username": c.get("username") or ""},
                                        "message": m})
                        if len(results) >= limit * 2: return
            except Exception: pass
    await asyncio.gather(*[search(c) for c in raw])
    results.sort(key=lambda x: int(x["message"].get("time") or 0), reverse=True)
    return {"results": results[:limit]}


class SendReq(BaseModel): target: str; text: str

@app.post("/api/accounts/{aid}/send")
async def api_send(aid: str, req: SendReq, uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    try: await bot.send_text(cli, req.target, req.text)
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    return {"ok": True}


def _err_text(e): return getattr(e, "detail", None) or bot._fmt_error(e)
def _mid(m):
    v = m.get("id"); return str(v) if v not in (None, "") else None


async def _call(cli, names, variants):
    last = None
    for n in names:
        fn = getattr(cli, n, None)
        if not fn: continue
        for kw in variants:
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                return r
            except TypeError as e: last = e; continue
    if last: raise HTTPException(501, f"آرگومان‌ها سازگار نیست: {last}")
    raise HTTPException(501, "پشتیبانی نمی‌شود")


def _extract_mid(res):
    for path in (("message_update","message_id"),("message_id",),
                 ("message","message_id"),("id",)):
        o = res
        for k in path:
            o = o.get(k) if isinstance(o, dict) else getattr(o, k, None)
            if o is None: break
        if o: return str(o)
    return None


async def _last_mid(cli, guid):
    try:
        msgs = await bot.fetch_messages(cli, guid, 1)
        return _mid(msgs[0]) if msgs else None
    except Exception: return None


class SendMsgReq(BaseModel):
    text: str
    reply_to: Optional[str] = None


@app.post("/api/accounts/{aid}/chats/{guid}/messages")
async def api_msg_send(aid: str, guid: str, req: SendMsgReq, uid: int = Depends(get_uid)):
    text = req.text.strip()
    if not text: raise HTTPException(400, "پیام خالی است")
    if len(text) > 4096: raise HTTPException(400, "پیام بیش از ۴۰۹۶ کاراکتر")
    cli = await get_client(aid); mid = None
    try:
        if req.reply_to:
            res = await _call(cli, ["send_message", "sendMessage"], [
                {"object_guid": guid, "text": text, "reply_to_message_id": req.reply_to},
                {"chat_id": guid, "text": text, "reply_to_message_id": req.reply_to}])
            mid = _extract_mid(res)
        else:
            r = cli.send_message(guid, text)
            if asyncio.iscoroutine(r): r = await r
            mid = _extract_mid(r)
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    return {"ok": True, "id": mid}


class EditMsgReq(BaseModel): text: str


@app.put("/api/accounts/{aid}/chats/{guid}/messages/{mid}")
async def api_msg_edit(aid: str, guid: str, mid: str, req: EditMsgReq,
                       uid: int = Depends(get_uid)):
    text = req.text.strip()
    if not text: raise HTTPException(400, "پیام خالی است")
    cli = await get_client(aid)
    try:
        await _call(cli, ["edit_message", "editMessage"], [
            {"object_guid": guid, "message_id": mid, "text": text},
            {"chat_id": guid, "message_id": mid, "text": text}])
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    f = FEEDS.get((aid, guid))
    if f and mid in f.snap: f.snap[mid] = {**f.snap[mid], "text": text}
    return {"ok": True}


@app.delete("/api/accounts/{aid}/chats/{guid}/messages/{mid}")
async def api_msg_del(aid: str, guid: str, mid: str, for_all: bool = True,
                      uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    t = "Global" if for_all else "Local"
    try:
        await _call(cli, ["delete_messages", "deleteMessages"], [
            {"object_guid": guid, "message_ids": [mid], "type": t},
            {"chat_id": guid, "message_ids": [mid], "type": t}])
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    f = FEEDS.get((aid, guid))
    if f: f.snap.pop(mid, None)
    feed_emit(aid, guid, {"type": "deleted_messages", "ids": [mid]})
    return {"ok": True}


class ForwardReq(BaseModel):
    to: str
    message_ids: List[str]


@app.post("/api/accounts/{aid}/chats/{guid}/forward")
async def api_msg_forward(aid: str, guid: str, req: ForwardReq,
                          uid: int = Depends(get_uid)):
    if not req.message_ids: raise HTTPException(400, "پیامی انتخاب نشده")
    cli = await get_client(aid)
    try:
        await _call(cli, ["forward_messages", "forwardMessages"], [
            {"from_object_guid": guid, "message_ids": req.message_ids, "to_object_guid": req.to},
            {"from_chat_id": guid, "message_ids": req.message_ids, "to_chat_id": req.to}])
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    return {"ok": True}


@app.post("/api/accounts/{aid}/chats/{guid}/file")
async def api_send_file(aid: str, guid: str, file: UploadFile = File(...),
                        caption: str = Form(""), uid: int = Depends(get_uid)):
    data = await file.read()
    if not data: raise HTTPException(400, "فایل خالی است")
    if len(data) > 50*1024*1024: raise HTTPException(413, "حجم بیش از ۵۰ مگابایت")
    cli = await get_client(aid)
    suffix = Path(file.filename or "file").suffix
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f: f.write(data)
        is_img = (file.content_type or "").startswith("image/")
        names = (["send_photo"] if is_img else []) + ["send_document", "send_file"]
        variants = []
        for key in (("photo",) if is_img else ()) + ("document", "file"):
            variants.append({"object_guid": guid, key: tmp, "caption": caption})
            variants.append({"chat_id": guid, key: tmp, "caption": caption})
        await _call(cli, names, variants)
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    finally:
        try: os.remove(tmp)
        except Exception: pass
    return {"ok": True}


@app.post("/api/accounts/{aid}/chats/{guid}/seen")
async def api_seen(aid: str, guid: str, uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    await _mark_seen(cli, guid)
    return {"ok": True}


async def _mark_seen(cli, guid, mid=None):
    try:
        mid = mid or await _last_mid(cli, guid)
        if not mid: return
        await _call(cli, ["seen_chats", "seenChats"], [{"seen_list": {guid: mid}}])
    except Exception: pass


async def _send_activity(aid, guid):
    try:
        cli = await get_client(aid)
        await _call(cli, ["send_chat_activity", "sendChatActivity"], [
            {"object_guid": guid, "activity": "Typing"},
            {"chat_id": guid, "activity": "Typing"}])
    except Exception: pass


class ChatOpReq(BaseModel): type: str = "User"


async def _leave(cli, guid, typ):
    if typ == "Group":
        await _call(cli, ["leave_group", "leaveGroup"],
                    [{"group_guid": guid}, {"object_guid": guid}, {"chat_id": guid}])
    elif typ == "Channel":
        await _call(cli, ["join_channel_action", "joinChannelAction"], [
            {"channel_guid": guid, "action": "Leave"},
            {"object_guid": guid, "action": "Leave"}])
    else: raise HTTPException(400, "فقط گروه و کانال")


@app.post("/api/accounts/{aid}/chats/{guid}/leave")
async def api_chat_leave(aid: str, guid: str, req: ChatOpReq,
                        uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    try: await _leave(cli, guid, req.type)
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    return {"ok": True}


@app.post("/api/accounts/{aid}/chats/{guid}/clear")
async def api_chat_clear(aid: str, guid: str, uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    last = await _last_mid(cli, guid)
    if not last: return {"ok": True}
    try:
        await _call(cli, ["delete_chat_history", "deleteChatHistory"], [
            {"object_guid": guid, "last_message_id": last},
            {"chat_id": guid, "last_message_id": last}])
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    feed_emit(aid, guid, {"type": "cleared"})
    return {"ok": True}


@app.post("/api/accounts/{aid}/chats/{guid}/remove")
async def api_chat_remove(aid: str, guid: str, req: ChatOpReq,
                          uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    try:
        if req.type == "User":
            last = await _last_mid(cli, guid)
            await _call(cli, ["delete_user_chat", "deleteUserChat"], [
                {"user_guid": guid, "last_deleted_message_id": last},
                {"object_guid": guid, "last_deleted_message_id": last}])
        else:
            await _leave(cli, guid, req.type)
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    return {"ok": True}


@app.get("/api/accounts/{aid}/channels")
async def api_channels(aid: str, uid: int = Depends(get_uid)):
    a = bot.get_account(aid)
    if not a: raise HTTPException(404, "اکانت نیست")
    return {"channels": a.get("channels", [])}


@app.get("/api/accounts/{aid}/collect/{kind}")
async def api_collect(aid: str, kind: str, uid: int = Depends(get_uid)):
    cli = await get_client(aid)
    try:
        if kind == "pv": items = await bot.collect_pv(cli)
        elif kind == "groups": items = await bot.collect_groups(cli)
        else: raise HTTPException(400, "kind باید pv یا groups")
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, bot._fmt_error(e))
    return {"items": items}


@app.get("/api/settings")
async def api_cfg(uid: int = Depends(get_uid)):
    return bot._load(bot.CFG_FILE, bot.DEFAULT_CFG)


class CfgReq(BaseModel):
    message: Optional[str] = None
    delay: Optional[float] = None
    cooldown: Optional[float] = None
    max_parallel: Optional[int] = None
    batch_per_account: Optional[int] = None
    max_attempts: Optional[int] = None
    max_channels_per_account: Optional[int] = None
    channels: Optional[List[str]] = None


@app.post("/api/settings")
async def api_cfg_upd(req: CfgReq, uid: int = Depends(get_uid)):
    cfg = bot._load(bot.CFG_FILE, bot.DEFAULT_CFG)
    for k, v in pyd_dict(req, exclude_none=True).items(): cfg[k] = v
    bot._save(bot.CFG_FILE, cfg)
    return {"ok": True, "cfg": cfg}


@app.get("/api/queue")
async def api_q(uid: int = Depends(get_uid)):
    return bot.TaskQueue(bot.QUEUE_FILE).stats()


@app.get("/api/queue/tasks")
async def api_q_tasks(status: Optional[str] = None, uid: int = Depends(get_uid)):
    q = bot.TaskQueue(bot.QUEUE_FILE); tasks = q.tasks
    if status: tasks = [t for t in tasks if t["status"] == status]
    return {"tasks": tasks[-500:]}


@app.post("/api/queue/clear")
async def api_q_clear(what: str = Query(...), uid: int = Depends(get_uid)):
    q = bot.TaskQueue(bot.QUEUE_FILE)
    if what == "all": await q.wipe()
    elif what == "done": await q.clear("done")
    elif what == "failed": await q.clear("failed")
    return {"ok": True, "stats": q.stats()}


@app.get("/api/reports")
async def api_reports(uid: int = Depends(get_uid)):
    q = bot.TaskQueue(bot.QUEUE_FILE); s = q.stats()
    by_account, failed_samples = {}, []
    for t in q.tasks:
        st = t.get("status", "?"); acc = t.get("owner_account") or "?"
        by_account.setdefault(acc, {"done":0,"failed":0,"pending":0,"in_progress":0})
        if st in by_account[acc]: by_account[acc][st] += 1
        if st == "failed" and len(failed_samples) < 30:
            failed_samples.append({"target": t.get("target"),
                                    "error": (t.get("last_error") or "")[:150],
                                    "attempts": t.get("attempts")})
    return {"totals": s, "by_account": by_account, "failed_samples": failed_samples}


@app.post("/api/job/start")
async def api_job_start(uid: int = Depends(get_uid)):
    j = bot.STATE.get("job")
    if j and not j.done(): raise HTTPException(400, "در جریانه")
    cfg = bot._load(bot.CFG_FILE, bot.DEFAULT_CFG)
    q = bot.TaskQueue(bot.QUEUE_FILE); s = q.stats()
    if s["pending"] + s["in_progress"] == 0: raise HTTPException(400, "صف خالیه")
    async def _job():
        try: await bot.run_workers(cfg, wlog)
        except Exception as e: wlog(f"❌ job: {e}")
    bot.STATE["job"] = asyncio.create_task(_job())
    return {"ok": True}


@app.post("/api/job/stop")
async def api_job_stop(uid: int = Depends(get_uid)):
    if bot.STATE.get("cancel"): bot.STATE["cancel"].set()
    return {"ok": True}


@app.get("/api/job/status")
async def api_job_status(uid: int = Depends(get_uid)):
    j = bot.STATE.get("job")
    return {"running": bool(j and not j.done())}


@app.get("/api/logs")
async def api_logs(uid: int = Depends(get_uid)):
    return {"logs": LOGS[-200:]}


@app.get("/api/extract/channels")
async def api_extract_channels(uid: int = Depends(get_uid)):
    cfg = bot._load(bot.CFG_FILE, bot.DEFAULT_CFG)
    return {"channels": cfg.get("channels", [])}


class ExtractChReq(BaseModel): channels: List[str]


@app.post("/api/extract/channels")
async def api_extract_set(req: ExtractChReq, uid: int = Depends(get_uid)):
    cfg = bot._load(bot.CFG_FILE, bot.DEFAULT_CFG)
    cfg["channels"] = [c.strip() for c in req.channels if c.strip()]
    bot._save(bot.CFG_FILE, cfg)
    return {"ok": True, "channels": cfg["channels"]}


class RunExtractReq(BaseModel):
    aid: str
    max_count: int = 0


@app.post("/api/extract/run")
async def api_extract_run(req: RunExtractReq, uid: int = Depends(get_uid)):
    acc = bot.get_account(req.aid)
    if not acc: raise HTTPException(404, "اکانت نیست")
    cfg = bot._load(bot.CFG_FILE, bot.DEFAULT_CFG)
    channels = cfg.get("channels", [])
    if not channels: raise HTTPException(400, "کانالی نیست")
    asyncio.create_task(_run_extract_bg(req.aid, channels, req.max_count, uid))
    return {"ok": True, "started": True}


async def _run_extract_bg(aid, channels, max_count, uid):
    try:
        cli = await get_client(aid)
        await HUB.broadcast({"type": "extract_start", "channels": channels}, uid)
        bot.STATE["cancel"] = asyncio.Event()
        joined = await bot.joiner(cli, channels, max_count, wlog)
        await HUB.broadcast({"type": "extract_done", "joined": joined}, uid)
    except Exception as e:
        wlog(f"❌ extract: {bot._fmt_error(e)}")
        await HUB.broadcast({"type": "extract_error", "error": bot._fmt_error(e)}, uid)
    finally:
        bot.STATE["cancel"] = None


@app.post("/api/extract/stop")
async def api_extract_stop(uid: int = Depends(get_uid)):
    if bot.STATE.get("cancel"): bot.STATE["cancel"].set()
    return {"ok": True}


class ChatFeed:
    def __init__(self, aid, guid):
        self.aid = aid; self.guid = guid
        self.active_subs = set()
        self.passive_subs = set()
        self.task = None; self.snap = {}

    @property
    def subs(self): return self.active_subs | self.passive_subs

    @property
    def interval(self): return 2.0 if self.active_subs else 15.0

    @property
    def _fetch_count(self): return 40 if self.active_subs else 15

    def start(self):
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self._run())

    def stop(self):
        if self.task and not self.task.done(): self.task.cancel()

    def add(self, conn, passive=False):
        if passive:
            if conn not in self.active_subs: self.passive_subs.add(conn)
        else:
            self.active_subs.add(conn); self.passive_subs.discard(conn)

    def emit(self, msg):
        for c in list(self.active_subs) + list(self.passive_subs):
            if not c.push(msg):
                self.active_subs.discard(c); self.passive_subs.discard(c)

    def _diff(self, msgs):
        cur = {}
        for m in msgs:
            i = _mid(m)
            if i: cur[i] = m
        if not cur: return
        for m in msgs:
            rid = (m.get("reply_to_message_id") or m.get("reply_to_id") or m.get("reply_to"))
            if rid and str(rid) in self.snap:
                p = self.snap[str(rid)]
                m["reply_preview"] = {
                    "id": str(rid), "text": (p.get("text") or "")[:120],
                    "sender": p.get("sender") or ("شما" if p.get("is_mine") else ""),
                    "type": p.get("type") or "Text"}
        newest_prev = max((_mtime(m) for m in self.snap.values()), default=0)
        oldest_cur = min(_mtime(m) for m in cur.values())
        new = [m for i, m in cur.items() if i not in self.snap and _mtime(m) >= newest_prev]
        edited = [m for i, m in cur.items()
                  if i in self.snap and (m.get("text") or "") != (self.snap[i].get("text") or "")]
        deleted = [i for i, m in self.snap.items() if i not in cur and _mtime(m) > oldest_cur]
        self.snap = cur
        new.sort(key=_mtime)
        base = {"aid": self.aid, "guid": self.guid}
        if new:     self.emit({"type": "new_messages", **base, "messages": new})
        if edited:  self.emit({"type": "edited_messages", **base, "messages": edited})
        if deleted: self.emit({"type": "deleted_messages", **base, "ids": deleted})

    async def _run(self):
        key = (self.aid, self.guid)
        fails = 0; cli = None
        try:
            if not self.active_subs:
                await asyncio.sleep(0.3 + (hash(self.guid) % 30) / 10.0)
                if not self.subs: return
            cli = await get_client(self.aid)
            my = _MY_GUID.get(self.aid) or await get_my_guid(self.aid)
            first = await bot.fetch_messages(cli, self.guid, self._fetch_count, my)
            self.snap = {_mid(m): m for m in first if _mid(m)}
            while self.subs:
                await asyncio.sleep(self.interval)
                if not self.subs: break
                try:
                    if cli is None: cli = await get_client(self.aid)
                    msgs = await bot.fetch_messages(cli, self.guid, self._fetch_count, my)
                except asyncio.CancelledError: raise
                except Exception as e:
                    cli = None; fails += 1
                    if _is_dead_session_error(e) and fails >= 3:
                        invalidate_client(self.aid)
                    if fails >= 5:
                        self.emit({"type": "chat_error", "aid": self.aid,
                                   "guid": self.guid, "error": _err_text(e)}); break
                    await asyncio.sleep(min(15.0, 2.0 * fails)); continue
                fails = 0
                self._diff(msgs)
        except asyncio.CancelledError: raise
        except Exception as e:
            self.emit({"type": "chat_error", "aid": self.aid, "guid": self.guid,
                       "error": _err_text(e)})
        finally:
            if FEEDS.get(key) is self: FEEDS.pop(key, None)


FEEDS: Dict[tuple, ChatFeed] = {}
MAX_SUBS_PER_CONN = 30


def feed_subscribe(conn, aid, guid, passive=False):
    if aid not in _account_ids_cached():
        conn.push({"type": "chat_error", "aid": aid, "guid": guid, "error": "اکانت نیست"})
        return
    key = (aid, guid)
    if key not in conn.subs and len(conn.subs) >= MAX_SUBS_PER_CONN:
        conn.push({"type": "chat_error", "aid": aid, "guid": guid,
                   "error": "تعداد اشتراک بیش از حد"}); return
    f = FEEDS.get(key)
    if not f or (f.task and f.task.done()):
        f = ChatFeed(aid, guid); FEEDS[key] = f; f.start()
    f.add(conn, passive=passive); conn.subs.add(key)
    conn.push({"type": "subscribed", "aid": aid, "guid": guid})


def feed_unsubscribe(conn, key, passive=False):
    f = FEEDS.get(key)
    if not f: return
    if passive: f.passive_subs.discard(conn)
    else:       f.active_subs.discard(conn)
    if conn not in f.active_subs and conn not in f.passive_subs:
        conn.subs.discard(key)
    if not f.subs:
        f.stop(); FEEDS.pop(key, None)


def feed_unsub_all(conn, key):
    f = FEEDS.get(key)
    if f:
        f.active_subs.discard(conn); f.passive_subs.discard(conn)
        if not f.subs:
            f.stop(); FEEDS.pop(key, None)
    conn.subs.discard(key)


def feed_emit(aid, guid, msg):
    f = FEEDS.get((aid, guid))
    if f: f.emit({**msg, "aid": aid, "guid": guid})


@app.websocket("/ws")
async def ws_ep(ws: WebSocket, token: str = Query("")):
    s = _check_token(token) or _check_token(ws.cookies.get("session"))
    if not s: await ws.close(code=1008); return
    uid = s["uid"]
    conn = await HUB.connect(ws, uid)
    conn.push({"type": "hello", "uid": uid})
    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=55)
            except asyncio.TimeoutError: break
            if raw == "ping": conn.push("pong"); continue
            try: msg = json.loads(raw)
            except Exception: continue
            if not isinstance(msg, dict): continue
            t = msg.get("type")
            aid, guid = msg.get("aid"), msg.get("guid")
            if t == "chat_subscribe" and aid and guid:
                feed_subscribe(conn, str(aid), str(guid), passive=False)
            elif t == "chat_unsubscribe" and aid and guid:
                feed_unsubscribe(conn, (str(aid), str(guid)), passive=False)
            elif t == "list_subscribe" and aid:
                for g in (msg.get("guids") or [])[:12]:
                    try: feed_subscribe(conn, str(aid), str(g), passive=True)
                    except Exception: pass
            elif t == "list_unsubscribe" and aid:
                for g in (msg.get("guids") or [])[:12]:
                    feed_unsubscribe(conn, (str(aid), str(g)), passive=True)
            elif t == "typing" and aid and guid:
                asyncio.create_task(_send_activity(str(aid), str(guid)))
            elif t == "seen" and aid and guid:
                async def _seen(a=str(aid), g=str(guid), m=msg.get("mid")):
                    try: await _mark_seen(await get_client(a), g, str(m) if m else None)
                    except Exception: pass
                asyncio.create_task(_seen())
    except WebSocketDisconnect: pass
    except Exception: pass
    finally:
        for key in list(conn.subs): feed_unsub_all(conn, key)
        HUB.disconnect(conn)
        try: await ws.close()
        except Exception: pass


# ══════════════════════════════════════════════════════════════
# Avatar gallery
# ══════════════════════════════════════════════════════════════
from fastapi.responses import Response as _AvResp
import os as _av_os

_AVATAR_CACHE = {}
_AVATAR_TTL = 1800
_AVATAR_NEG = {}
_AVATAR_NEG_TTL = 60
_AVATAR_MY_GUID = {}


class _AvInline:
    def __init__(self, d):
        self.dc_id = int(d.get("dc_id") or 0)
        self.file_id = str(d.get("file_id") or "")
        self.mime = str(d.get("mime") or "image/jpeg")
        self.size = int(d.get("size") or 0)
        self.access_hash_rec = str(d.get("access_hash_rec") or "")
        self.type = "Image"


async def _av_resolve_guid(aid, guid, cli):
    if guid and guid != aid and not guid.startswith("acc_"):
        return guid
    if aid in _AVATAR_MY_GUID:
        return _AVATAR_MY_GUID[aid]
    try:
        me = await cli.get_me()
        g = me.user.user_guid
        if g:
            _AVATAR_MY_GUID[aid] = g
            return g
    except Exception:
        pass
    return guid


async def _av_list(cli, guid):
    fn = getattr(cli, "get_avatars", None)
    if not fn: return []
    try:
        u = fn(object_guid=guid)
        if asyncio.iscoroutine(u): u = await u
        ou = getattr(u, "original_update", {}) or {}
        if isinstance(ou, dict):
            return list(ou.get("avatars", []) or [])
    except Exception:
        pass
    return []


async def _av_dl_obj(cli, d):
    return None


async def _av_dl_by_idx(cli, real_guid, idx):
    fn = getattr(cli, "get_avatars", None)
    if not fn: return None
    try:
        u = fn(object_guid=real_guid)
        if asyncio.iscoroutine(u): u = await u
    except Exception:
        return None

    ou = getattr(u, "original_update", {}) or {}
    avatars = ou.get("avatars", []) if isinstance(ou, dict) else []
    if idx < 0 or idx >= len(avatars): return None
    av = avatars[idx]
    if not isinstance(av, dict): return None
    file_data = av.get("main") or av.get("thumbnail")
    if not isinstance(file_data, dict): return None
    dl = getattr(cli, "download", None)
    if not dl: return None

    try:
        u.file_inline = file_data
        u.is_file_inline = True
        r = dl(file_inline=u)
        if asyncio.iscoroutine(r): r = await r
        if isinstance(r, (bytes, bytearray)) and r: return bytes(r)
    except Exception: pass

    class _U1:
        def __init__(self):
            self.file_inline = file_data
            self.is_file_inline = True
            self.file = None
            self.photo = None
    try:
        r = dl(file_inline=_U1())
        if asyncio.iscoroutine(r): r = await r
        if isinstance(r, (bytes, bytearray)) and r: return bytes(r)
    except Exception: pass

    class _IN:
        def __init__(self):
            self.file_id = str(file_data.get("file_id") or "")
            self.dc_id = int(file_data.get("dc_id") or 0)
            self.mime = str(file_data.get("mime") or "image/jpeg")
            self.size = int(file_data.get("size") or 0)
            self.access_hash_rec = str(file_data.get("access_hash_rec") or "")
    class _U2:
        def __init__(self):
            self.file_inline = _IN()
            self.is_file_inline = True
    try:
        r = dl(file_inline=_U2())
        if asyncio.iscoroutine(r): r = await r
        if isinstance(r, (bytes, bytearray)) and r: return bytes(r)
    except Exception: pass

    try:
        r = dl(file_inline=file_data)
        if asyncio.iscoroutine(r): r = await r
        if isinstance(r, (bytes, bytearray)) and r: return bytes(r)
    except Exception: pass

    return None


async def _av_dl_main(cli, guid):
    fn = getattr(cli, "download_profile_picture", None)
    if not fn: return None
    try:
        r = fn(object_guid=guid)
        if asyncio.iscoroutine(r): r = await r
        if isinstance(r, (bytes, bytearray)) and r: return bytes(r)
    except Exception: pass
    return None


def _av_clear_cache(aid):
    for k in list(_AVATAR_CACHE.keys()):
        if k.startswith(aid + ":"): del _AVATAR_CACHE[k]
    for k in list(_AVATAR_NEG.keys()):
        if k.startswith(aid + ":"): del _AVATAR_NEG[k]


@app.get("/api/accounts/{aid}/avatars/{guid}")
async def api_avatar_list(aid: str, guid: str):
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(404, f"no client: {str(e)[:100]}")
    real_guid = await _av_resolve_guid(aid, guid, cli)
    avatars = await _av_list(cli, real_guid)
    items = []
    for i, av in enumerate(avatars):
        if not isinstance(av, dict): continue
        items.append({
            "idx": i,
            "avatar_id": av.get("avatar_id") or "",
            "main": bool(av.get("main")),
            "create_time": int(av.get("create_time") or 0),
            "url": f"/api/accounts/{aid}/avatar/{guid}?idx={i}"})
    items.sort(key=lambda a: (not a["main"], -a["create_time"]))
    for i, a in enumerate(items): a["pos"] = i
    return {"guid": guid, "real_guid": real_guid,
            "count": len(items), "avatars": items}


@app.get("/api/accounts/{aid}/avatar/{guid}")
async def api_avatar(aid: str, guid: str, idx: int = -1):
    now = time.time()
    key = f"{aid}:{guid}:{idx}"
    c = _AVATAR_CACHE.get(key)
    if c and (now - c["ts"]) < _AVATAR_TTL:
        return _AvResp(content=c["bytes"], media_type=c.get("mime") or "image/jpeg",
                       headers={"Cache-Control": "public, max-age=1800"})
    n = _AVATAR_NEG.get(key)
    if n and (now - n) < _AVATAR_NEG_TTL:
        raise HTTPException(404, "no avatar (cached)")
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(404, f"no client: {str(e)[:100]}")
    real_guid = await _av_resolve_guid(aid, guid, cli)
    data = None
    if idx >= 0:
        data = await _av_dl_by_idx(cli, real_guid, idx)
    if not data:
        data = await _av_dl_main(cli, real_guid)
    if not data:
        _AVATAR_NEG[key] = now
        raise HTTPException(404, "no avatar")
    _AVATAR_CACHE[key] = {"ts": now, "bytes": data, "mime": "image/jpeg"}
    return _AvResp(content=data, media_type="image/jpeg",
                   headers={"Cache-Control": "public, max-age=1800"})


@app.post("/api/accounts/{aid}/avatar")
async def api_avatar_upload(aid: str, file: UploadFile = File(...),
                             uid: int = Depends(get_uid)):
    import tempfile as _tmp
    data = await file.read()
    if not data: raise HTTPException(400, "فایل خالی")
    if len(data) > 10 * 1024 * 1024: raise HTTPException(413, "حجم بیش از ۱۰ مگابایت")
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    suffix = Path(file.filename or "img.jpg").suffix or ".jpg"
    fd, tmp = _tmp.mkstemp(suffix=suffix)
    try:
        with _av_os.fdopen(fd, "wb") as f: f.write(data)
        me = await cli.get_me()
        my_guid = me.user.user_guid
        last = None
        for name in ("upload_avatar", "uploadAvatar", "set_avatar", "setAvatar"):
            fn = getattr(cli, name, None)
            if not fn: continue
            for kw in ({"object_guid": my_guid, "image": tmp},
                       {"object_guid": my_guid, "image": tmp, "thumbnail_file_id": None}):
                try:
                    r = fn(**kw)
                    if asyncio.iscoroutine(r): r = await r
                    _av_clear_cache(aid)
                    return {"ok": True, "method": name}
                except Exception as e:
                    last = f"{name}: {type(e).__name__}: {str(e)[:150]}"
                    continue
        raise HTTPException(501, f"آپلود نشد: {last}")
    finally:
        try: _av_os.remove(tmp)
        except Exception: pass


@app.delete("/api/accounts/{aid}/avatar")
async def api_avatar_delete(aid: str, avatar_id: str = Query(""),
                             uid: int = Depends(get_uid)):
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    me = await cli.get_me()
    my_guid = me.user.user_guid
    if not avatar_id:
        avs = await _av_list(cli, my_guid)
        for av in avs:
            if isinstance(av, dict) and av.get("main"):
                avatar_id = av.get("avatar_id") or ""; break
        if not avatar_id and avs and isinstance(avs[0], dict):
            avatar_id = avs[0].get("avatar_id") or ""
    last = None
    for name in ("delete_avatar", "deleteAvatar"):
        fn = getattr(cli, name, None)
        if not fn: continue
        variants = [
            {"object_guid": my_guid, "avatar_id": avatar_id} if avatar_id else None,
            {"object_guid": my_guid},
            {"chat_id": my_guid, "avatar_id": avatar_id} if avatar_id else None,
            {"chat_id": my_guid}]
        for kw in variants:
            if not kw: continue
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                _av_clear_cache(aid)
                return {"ok": True, "method": name, "avatar_id": avatar_id}
            except TypeError:
                last = f"{name}/{list(kw.keys())}: TypeError"; continue
            except Exception as e:
                last = f"{name}: {type(e).__name__}: {str(e)[:150]}"; continue
    raise HTTPException(501, f"حذف نشد: {last}")


@app.post("/api/accounts/{aid}/avatars/{guid}/prefetch")
async def api_avatar_prefetch(aid: str, guid: str):
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(404, f"no client: {str(e)[:100]}")
    real_guid = await _av_resolve_guid(aid, guid, cli)
    avs = await _av_list(cli, real_guid)
    if not avs: return {"ok": True, "count": 0}
    ordered = [(i, av) for i, av in enumerate(avs) if isinstance(av, dict)]
    ordered.sort(key=lambda t: (not bool(t[1].get("main")),
                                 -int(t[1].get("create_time") or 0)))
    async def one(pos, av):
        key = f"{aid}:{guid}:{pos}"
        now = time.time()
        c = _AVATAR_CACHE.get(key)
        if c and (now - c["ts"]) < _AVATAR_TTL: return
        for field in ("thumbnail", "main"):
            d = av.get(field)
            if not d: continue
            try:
                r = await _av_dl_obj(cli, d)
                if r:
                    _AVATAR_CACHE[key] = {"ts": time.time(), "bytes": r, "mime": "image/jpeg"}
                    return
            except Exception: continue
    sem = asyncio.Semaphore(3)
    async def bounded(pos, av):
        async with sem: await one(pos, av)
    asyncio.create_task(asyncio.gather(*[bounded(p, a) for p, a in ordered]))
    return {"ok": True, "count": len(ordered)}


@app.get("/account/{aid}")
async def p_account(request: Request, aid: str):
    if not _check_token(_get_token(request)):
        return RedirectResponse("/login", status_code=302)
    return _page("account_manage.html")


@app.get("/api/accounts/{aid}/diag")
async def api_diag(aid: str, uid: int = Depends(get_uid)):
    out = {"aid": aid}
    entry = CLIENTS.get(aid)
    out["has_cached_client"] = bool(entry)
    if entry:
        out["cli_alive"] = _cli_alive(entry["cli"])
        out["client_age_sec"] = int(time.time() - entry["ts"])
    try:
        cli = await get_client(aid)
        out["get_client"] = "ok"
    except Exception as e:
        out["get_client"] = f"ERR {type(e).__name__}: {str(e)[:200]}"
        return out
    try:
        me = await cli.get_me()
        out["my_guid"] = me.user.user_guid
        out["my_name"] = me.user.first_name
        out["get_me"] = "ok"
    except Exception as e:
        out["get_me"] = f"ERR {type(e).__name__}: {str(e)[:200]}"
        return out
    try:
        raw = await bot.get_all_chats_raw(cli)
        out["total_chats"] = len(raw)
        types = {}
        for c in raw:
            t = c.get("type") or "?"
            types[t] = types.get(t, 0) + 1
        out["types"] = types
    except Exception as e:
        out["get_chats"] = f"ERR {type(e).__name__}: {str(e)[:200]}"
    return out


# ══════════════════════════════════════════════════════════════
# Batch system
# ══════════════════════════════════════════════════════════════
BATCHES_FILE = "batches.json"


def _load_batches(): return bot._load(BATCHES_FILE, [])
def _save_batches(b): bot._save(BATCHES_FILE, b)


def _get_batch(bid):
    for b in _load_batches():
        if b.get("id") == bid: return b
    return None


@app.get("/api/batches")
async def api_batches(uid: int = Depends(get_uid)):
    batches = _load_batches()
    q = bot.TaskQueue(bot.QUEUE_FILE)
    by_batch = {}
    for t in q.tasks:
        bid = t.get("batch_id")
        if not bid: continue
        d = by_batch.setdefault(bid, {"done":0,"failed":0,"pending":0,"in_progress":0})
        st = t.get("status", "pending")
        if st in d: d[st] += 1
    out = []
    for b in batches:
        stats = by_batch.get(b["id"], {"done":0,"failed":0,"pending":0,"in_progress":0})
        out.append({**b, "stats": stats, "total": sum(stats.values())})
    out.sort(key=lambda x: x.get("created", 0), reverse=True)
    return {"batches": out[:200]}


@app.get("/api/batches/{bid}")
async def api_batch_detail(bid: str, uid: int = Depends(get_uid)):
    b = _get_batch(bid)
    if not b: raise HTTPException(404, "پیدا نشد")
    q = bot.TaskQueue(bot.QUEUE_FILE)
    tasks = [t for t in q.tasks if t.get("batch_id") == bid]
    by_acc = {}
    for t in tasks:
        aid = t.get("owner_account") or "?"
        d = by_acc.setdefault(aid, {"done":0,"failed":0,"pending":0,
                                    "in_progress":0, "samples": []})
        st = t.get("status", "pending")
        if st in d: d[st] += 1
        if st == "failed" and len(d["samples"]) < 8:
            d["samples"].append({"target": t.get("target"),
                                  "error": (t.get("last_error") or "")[:200],
                                  "attempts": t.get("attempts", 0)})
    stats = {"done":0,"failed":0,"pending":0,"in_progress":0}
    for d in by_acc.values():
        for k in stats: stats[k] += d.get(k, 0)
    return {"batch": b, "stats": stats, "by_account": by_acc, "total": len(tasks)}


@app.delete("/api/batches/{bid}")
async def api_batch_delete(bid: str, uid: int = Depends(get_uid)):
    b = _get_batch(bid)
    if not b: raise HTTPException(404, "پیدا نشد")
    _save_batches([x for x in _load_batches() if x.get("id") != bid])
    q = bot.TaskQueue(bot.QUEUE_FILE)
    q.tasks = [t for t in q.tasks
               if t.get("batch_id") != bid or t.get("status") == "done"]
    q._save()
    return {"ok": True}


class EnqueueReq(BaseModel):
    items: List[Dict[str, Any]]
    owner_account: str
    batch_id: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    file_name: Optional[str] = None


@app.post("/api/enqueue")
async def api_enqueue(req: EnqueueReq, uid: int = Depends(get_uid)):
    bid = (req.batch_id or "").strip() or ("b_" + secrets.token_hex(6))
    batches = _load_batches()
    existing = next((b for b in batches if b.get("id") == bid), None)
    if not existing:
        existing = {"id": bid, "created": int(time.time()),
                    "message": (req.message or "")[:500],
                    "type": req.type or "both",
                    "file_name": req.file_name or "",
                    "owner_account": req.owner_account}
        batches.append(existing)
        _save_batches(batches)
    q = bot.TaskQueue(bot.QUEUE_FILE)
    for it in req.items:
        it["owner_account"] = req.owner_account
        it["batch_id"] = bid
    n = await q.add(req.items)
    return {"ok": True, "added": n, "batch_id": bid, "stats": q.stats()}


@app.get("/api/batches-jobs/status")
async def api_batches_job_status(uid: int = Depends(get_uid)):
    j = bot.STATE.get("job")
    q = bot.TaskQueue(bot.QUEUE_FILE)
    return {"running": bool(j and not j.done()), "queue": q.stats()}


# ══════════════════════════════════════════════════════════════
# Channel management
# ══════════════════════════════════════════════════════════════

def _ch_friendly_err(e):
    s = str(e)
    s_low = s.lower()
    if "10" in s and ("username" in s_low or "یوزر" in s or "نام کاربری" in s):
        return {"code": "USERNAME_LIMIT",
                "message": "بیشتر از ۱۰ نام کاربری نمی‌تونی بزنی."}
    if "3" in s and ("روز" in s or "day" in s_low):
        return {"code": "3DAY_LIMIT",
                "message": "باید از نشست شما ۳ روز گذشته باشد."}
    if "owner" in s_low or "مالک" in s:
        return {"code": "OWNER_ONLY",
                "message": "حذف کانال فقط توسط مالک کانال."}
    if "not_found" in s_low or "پیدا" in s:
        return {"code": "NOT_FOUND", "message": "کانال پیدا نشد."}
    return {"code": "UNKNOWN", "message": str(e)[:300]}


@app.get("/api/accounts/{aid}/channels-all")
async def api_all_channels(aid: str, uid: int = Depends(get_uid)):
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    out = []
    try:
        raw = await bot.get_live_channels(cli)
        for c in raw:
            out.append({"guid": c.get("guid") or "",
                        "title": c.get("title") or "",
                        "username": c.get("username") or "",
                        "type": "public" if c.get("username") else "private",
                        "source": "live"})
    except Exception: pass
    acc = bot.get_account(aid) or {}
    local = {c.get("guid"): c for c in (acc.get("channels") or []) if c.get("guid")}
    seen = set()
    for c in out:
        seen.add(c["guid"])
        if c["guid"] in local:
            lc = local[c["guid"]]
            if not c.get("title") and lc.get("title"): c["title"] = lc["title"]
            if not c.get("username") and lc.get("username"):
                c["username"] = lc["username"]; c["type"] = "public"
    for g, lc in local.items():
        if g not in seen:
            out.append({"guid": g, "title": lc.get("title") or "",
                        "username": lc.get("username") or "",
                        "type": "public" if lc.get("username") else "private",
                        "source": "local"})
    return {"count": len(out), "channels": out}


@app.get("/api/accounts/{aid}/channels/{guid}")
async def api_channel_info(aid: str, guid: str, uid: int = Depends(get_uid)):
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    info = None
    for mname in ("get_channel_info", "getChannelInfo", "get_info", "getInfo",
                  "get_chat_info", "getChatInfo"):
        fn = getattr(cli, mname, None)
        if not fn: continue
        try:
            r = fn(object_guid=guid)
            if asyncio.iscoroutine(r): r = await r
            if r: info = r; break
        except Exception: continue
    def g(*keys, d=None):
        if info is None: return d
        for k in keys:
            if isinstance(info, dict) and k in info and info[k]: return info[k]
            v = getattr(info, k, None)
            if v: return v
        return d
    title = g("title", "first_name", "name") or ""
    username = (g("username") or "").lstrip("@")
    description = g("description", "bio", "about") or ""
    if not title or not description:
        acc = bot.get_account(aid) or {}
        for ch in (acc.get("channels") or []):
            if ch.get("guid") == guid:
                if not title: title = ch.get("title") or ""
                if not description: description = ch.get("description") or ""
                if not username: username = (ch.get("username") or "").lstrip("@")
                break
    return {"guid": guid, "title": title, "username": username,
            "description": description, "is_public": bool(username)}


@app.put("/api/accounts/{aid}/channels/{guid}")
async def api_channel_edit(aid: str, guid: str, req: dict, uid: int = Depends(get_uid)):
    title = (req.get("title") or "").strip()
    desc = (req.get("description") or "").strip()
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    last_err = None; ok = False
    for mname in ("edit_channel_info", "editChannelInfo", "update_channel_info"):
        fn = getattr(cli, mname, None)
        if not fn: continue
        kw = {"channel_guid": guid}
        if title: kw["title"] = title
        if desc is not None: kw["description"] = desc
        try:
            r = fn(**kw)
            if asyncio.iscoroutine(r): r = await r
            ok = True; break
        except TypeError:
            try:
                kw2 = {"object_guid": guid}
                if title: kw2["title"] = title
                if desc is not None: kw2["description"] = desc
                r = fn(**kw2)
                if asyncio.iscoroutine(r): r = await r
                ok = True; break
            except Exception as e2: last_err = e2; continue
        except Exception as e: last_err = e; continue
    if not ok:
        fe = _ch_friendly_err(last_err)
        raise HTTPException(501, fe["message"])
    try:
        accounts = bot.list_accounts()
        if aid in accounts:
            for ch in (accounts[aid].get("channels") or []):
                if ch.get("guid") == guid:
                    if title: ch["title"] = title
                    if desc is not None: ch["description"] = desc
                    break
            bot.save_accounts(accounts)
    except Exception: pass
    return {"ok": True}


@app.get("/api/accounts/{aid}/channels/{guid}/invite")
async def api_channel_invite_get(aid: str, guid: str, uid: int = Depends(get_uid)):
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    for mname in ("get_join_links", "getJoinLinks", "get_channel_link",
                  "getChannelLink", "get_link", "getLink"):
        fn = getattr(cli, mname, None)
        if not fn: continue
        for kw in ({"object_guid": guid}, {"channel_guid": guid}, {"chat_id": guid}):
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                link = _ch_extract_join_link(r)
                if link: return {"ok": True, "link": link, "existing": True}
            except Exception: continue
    ok, link = await _ch_create_join_link_robust(cli, guid)
    if ok: return {"ok": True, "link": link, "existing": False}
    return {"ok": True, "link": "", "empty": True, "error": str(link)[:200]}


@app.post("/api/accounts/{aid}/channels/{guid}/invite")
async def api_channel_invite_new(aid: str, guid: str, uid: int = Depends(get_uid)):
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    ok, link = await _ch_create_join_link_robust(cli, guid)
    if ok:
        try:
            accounts = bot.list_accounts()
            if aid in accounts:
                for ch in (accounts[aid].get("channels") or []):
                    if ch.get("guid") == guid: ch["join_link"] = link; break
                bot.save_accounts(accounts)
        except Exception: pass
        return {"ok": True, "link": link, "existing": False}
    raise HTTPException(501, f"ساخت لینک نشد: {link}")


@app.post("/api/accounts/{aid}/channels/{guid}/username")
async def api_channel_set_username(aid: str, guid: str, req: dict,
                                    uid: int = Depends(get_uid)):
    username = (req.get("username") or "").strip().lstrip("@")
    if not username: raise HTTPException(400, "نام کاربری لازم است")
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    ok, msg = await _ch_set_username_robust(cli, guid, username)
    if not ok: raise HTTPException(501, msg)
    try:
        accounts = bot.list_accounts()
        if aid in accounts:
            for ch in (accounts[aid].get("channels") or []):
                if ch.get("guid") == guid:
                    ch["username"] = "@" + username
                    ch["is_public"] = True
                    break
            bot.save_accounts(accounts)
    except Exception: pass
    return {"ok": True, "username": "@" + username}


@app.post("/api/accounts/{aid}/channels/{guid}/make-private")
async def api_channel_make_private(aid: str, guid: str, uid: int = Depends(get_uid)):
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    has_uname = await _ch_get_username(cli, guid)
    cleared = False; clear_msg = ""
    if has_uname:
        cleared, clear_msg = await _ch_clear_username(cli, guid)
        if not cleared:
            raise HTTPException(501, f"یوزرنیم {has_uname} پاک نشد: {clear_msg}")
        await asyncio.sleep(1.5)
    join_link = None
    for attempt in range(3):
        join_link = await _ch_create_join_link(cli, guid)
        if join_link: break
        await asyncio.sleep(1.5 + attempt)
    try:
        accounts = bot.list_accounts()
        if aid in accounts:
            for ch in (accounts[aid].get("channels") or []):
                if ch.get("guid") == guid:
                    ch["username"] = ""; ch["is_public"] = False
                    ch["type"] = "private"
                    if join_link: ch["join_link"] = join_link
                    break
            bot.save_accounts(accounts)
    except Exception: pass
    return {"ok": True, "was_username": has_uname or "",
            "cleared": cleared, "join_link": join_link}


async def _ch_remove_username(cli, guid):
    attempts = [
        ("update_channel_username", {"channel_guid": guid, "username": ""}),
        ("update_channel_username", {"object_guid": guid, "username": ""}),
        ("edit_channel_info", {"channel_guid": guid, "username": ""}),
    ]
    for mname, kw in attempts:
        fn = getattr(cli, mname, None)
        if not fn: continue
        try:
            r = fn(**kw)
            if asyncio.iscoroutine(r): r = await r
            return True, f"{mname}"
        except Exception: continue
    return False, "no method"


async def _ch_create_join_link(cli, guid):
    variants = [
        dict(object_guid=guid, request_needed=False),
        dict(object_guid=guid, request_needed=False, usage_limit=0),
        dict(object_guid=guid), dict(chat_id=guid), dict(channel_guid=guid)]
    for mname in ("create_join_link", "createJoinLink", "add_join_link", "addJoinLink"):
        fn = getattr(cli, mname, None)
        if not fn: continue
        for kw in variants:
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                link = _ch_extract_join_link(r)
                if link: return link
            except Exception: continue
    return None


async def _ch_create_join_link_robust(cli, guid):
    link = await _ch_create_join_link(cli, guid)
    if link: return True, link
    return False, "no join link method"


async def _ch_set_username_robust(cli, guid, username):
    last = None
    for mname in ("update_channel_username", "updateChannelUsername",
                  "set_channel_username", "setChannelUsername"):
        fn = getattr(cli, mname, None)
        if not fn: continue
        for kw in ({"channel_guid": guid, "username": username},
                   {"channel_guid": guid, "username": "@" + username},
                   {"object_guid": guid, "username": username},
                   {"object_guid": guid, "username": "@" + username}):
            try:
                r = fn(**kw)
                if asyncio.iscoroutine(r): r = await r
                return True, "ok"
            except Exception as e: last = e; continue
    return False, f"no method: {last}"


async def _ch_get_username(cli, guid):
    for mname in ("get_channel_info", "getChannelInfo"):
        fn = getattr(cli, mname, None)
        if not fn: continue
        try:
            r = fn(object_guid=guid)
            if asyncio.iscoroutine(r): r = await r
            u = getattr(r, "username", None) or (r.get("username") if isinstance(r, dict) else None)
            if u: return u
        except Exception: continue
    return None


async def _ch_clear_username(cli, guid):
    return await _ch_remove_username(cli, guid)


def _ch_extract_join_link(r):
    if r is None: return None
    if isinstance(r, dict):
        for k in ("join_link", "link", "url", "invite_link", "invite"):
            v = r.get(k)
            if isinstance(v, str) and v.startswith("http"): return v
        for k in ("data", "result", "chat", "response"):
            n = r.get(k)
            if isinstance(n, dict):
                x = _ch_extract_join_link(n)
                if x: return x
    else:
        for k in ("join_link", "link", "url", "invite_link", "invite"):
            v = getattr(r, k, None)
            if isinstance(v, str) and v.startswith("http"): return v
    try:
        s = str(r); m = re.search(r'https?://[^\s"\'<>]+', s)
        if m: return m.group(0)
    except Exception: pass
    return None


@app.get("/api/debug/channel-methods")
async def api_debug_channel_methods(aid: str = Query(...)):
    try:
        cli = await get_client(aid)
    except Exception as e:
        return {"error": str(e)}
    out = []
    for attr in sorted(dir(cli)):
        if attr.startswith("_"): continue
        low = attr.lower()
        if "channel" in low or "username" in low or "join" in low or "avatar" in low:
            try:
                import inspect as _ins
                sig = str(_ins.signature(getattr(cli, attr)))
            except Exception: sig = "?"
            out.append({"name": attr, "sig": sig})
    return {"methods": out}


def _ch_link(r):
    if r is None: return None
    if isinstance(r, dict):
        for k in ("join_link", "link", "url", "invite_link"):
            v = r.get(k)
            if isinstance(v, str) and v.startswith("http"): return v
        for k in ("data", "result", "chat", "response"):
            n = r.get(k)
            if isinstance(n, dict):
                x = _ch_link(n)
                if x: return x
    else:
        for k in ("join_link", "link", "url", "invite_link"):
            v = getattr(r, k, None)
            if isinstance(v, str) and v.startswith("http"): return v
    s = str(r); m = re.search(r"https?://[^\s\"<>]+", s)
    return m.group(0) if m else None


@app.post("/api/accounts/{aid}/channels")
async def api_channel_create(aid: str, req: dict, uid: int = Depends(get_uid)):
    title = (req.get("title") or "").strip()
    desc = (req.get("description") or "").strip()
    ctype = (req.get("type") or "private").lower()
    username = (req.get("username") or "").strip().lstrip("@")
    if not title: raise HTTPException(400, "نام کانال لازم است")
    if ctype == "public" and not username:
        raise HTTPException(400, "برای عمومی یوزرنیم لازم است")
    try:
        cli = await get_client(aid)
    except Exception as e:
        raise HTTPException(500, f"no client: {e}")
    try:
        r = cli.add_channel(title=title, description=desc or None)
        if asyncio.iscoroutine(r): r = await r
        guid = bot.extract_chat_guid(r)
    except Exception as e:
        raise HTTPException(501, f"ساخت نشد: {bot._fmt_error(e)}")
    if not guid: raise HTTPException(501, "guid پیدا نشد")
    await asyncio.sleep(1.5)
    warnings = []
    if ctype == "private":
        for val in ("Private", "private"):
            try:
                r = cli.edit_channel_info(channel_guid=guid, channel_type=val)
                if asyncio.iscoroutine(r): r = await r
                break
            except Exception as e: warnings.append(f"private: {bot._fmt_error(e)}")
        await asyncio.sleep(1.5)
    if ctype == "public":
        u_ok = False
        for u in (username, "@" + username):
            try:
                r = cli.update_channel_username(channel_guid=guid, username=u)
                if asyncio.iscoroutine(r): r = await r
                u_ok = True; break
            except Exception as e: warnings.append(f"username: {bot._fmt_error(e)}")
        if u_ok:
            try:
                r = cli.edit_channel_info(channel_guid=guid, channel_type="Public")
                if asyncio.iscoroutine(r): r = await r
            except Exception: pass
    join_link = None
    if ctype == "private":
        for attempt in range(3):
            try:
                r = cli.create_join_link(object_guid=guid, request_needed=False)
                if asyncio.iscoroutine(r): r = await r
                join_link = _ch_link(r)
                if join_link: break
            except Exception: pass
            await asyncio.sleep(1.5)
    try:
        bot.add_channel_to_storage(aid, {
            "guid": guid, "title": title, "description": desc,
            "username": ("@" + username) if ctype == "public" else "",
            "join_link": join_link,
            "is_public": (ctype == "public"),
            "type": ctype, "created": int(time.time())})
    except Exception: pass
    return {"ok": True, "guid": guid, "type": ctype,
            "invite_link": join_link, "warnings": warnings}


@app.get("/manage/{aid}")
async def p_manage(request: Request, aid: str):
    if not _check_token(_get_token(request)):
        return RedirectResponse("/login", status_code=302)
    return _page("account_manage.html")


@app.get("/channel/{aid}/{guid}")
async def p_channel(request: Request, aid: str, guid: str):
    if not _check_token(_get_token(request)):
        return RedirectResponse("/login", status_code=302)
    return _page("channel_manage.html")


# ══════════════════════════════════════════════════════════════
# ★ launcher threads — با لاگ تمیز
# ══════════════════════════════════════════════════════════════
def _web_worker():
    import uvicorn
    try:
        uvicorn.run(
            app,
            host=HOST,
            port=PORT,
            log_level="critical",     # فقط خطاهای مهم
            access_log=False,         # هیچ access log
            proxy_headers=True,
            forwarded_allow_ips="*",
        )
    except BaseException as e:
        print(f"[panel] crashed: {type(e).__name__}: {e}", file=REAL_STDERR, flush=True)


def _bot_worker():
    """ربات رو توی thread جدا با loop اختصاصی اجرا می‌کنه.
    همه‌ی خروجی ربات (print / logger / traceback) می‌ره تو فایل لاگ."""
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(_buf):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try: _loop_ref[0] = loop
            except Exception: pass
            if callable(getattr(bot, "main", None)):
                bot.main()
            else:
                runpy.run_path(str(BOT_PATH), run_name="__main__")
        except SystemExit:
            _buf.write("[bot] SystemExit\n")
        except BaseException as e:
            _buf.write(f"[bot] {type(e).__name__}: {e}\n")
            import traceback as _tb
            _tb.print_exc(file=_buf)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n===== bot exit @ {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            f.write(_buf.getvalue())
    except Exception:
        pass


if __name__ == "__main__":
    # ─── بنر ───
    print("=" * 56, file=REAL_STDOUT, flush=True)
    print("   🌐  Rubika Web Panel   +   🤖  Telegram Bot", file=REAL_STDOUT, flush=True)
    print(f"   فایل ربات: {BOT_PATH}", file=REAL_STDOUT, flush=True)
    print("=" * 56, file=REAL_STDOUT, flush=True)

    # ─── ۱) پنل وب ───
    tp = threading.Thread(target=_web_worker, daemon=True, name="panel")
    tp.start()
    time.sleep(2.0)
    panel_ok = tp.is_alive()
    print(f"   پنل وب     : {'🟢 UP  ' if panel_ok else '🔴 DOWN'}   0.0.0.0:{PORT}",
          file=REAL_STDOUT, flush=True)

    # ─── ۲) ربات تلگرام ───
    tb = threading.Thread(target=_bot_worker, daemon=True, name="bot")
    tb.start()
    time.sleep(3.0)
    bot_ok = tb.is_alive()
    print(f"   ربات تلگرام: {'🟢 UP  ' if bot_ok else '🔴 DOWN'}   polling",
          file=REAL_STDOUT, flush=True)

    print("-" * 56, file=REAL_STDOUT, flush=True)
    if panel_ok and bot_ok:
        print("   ✅  هر دو سرویس در حال اجرا هستن", file=REAL_STDOUT, flush=True)
    else:
        print("   ⚠️  یکی از سرویس‌ها بالا نیومد — bot_runtime.log رو چک کن",
              file=REAL_STDOUT, flush=True)
    print("-" * 56, file=REAL_STDOUT, flush=True)

    # main thread زنده بمونه
    try:
        while True:
            time.sleep(60)
            # چک سلامت دوره‌ای (فقط اگه یکی مرد)
            if not tp.is_alive() or not tb.is_alive():
                print(f"   ⚠️ healthcheck: panel={'🟢' if tp.is_alive() else '🔴'} "
                      f"bot={'🟢' if tb.is_alive() else '🔴'}",
                      file=REAL_STDOUT, flush=True)
                break
    except KeyboardInterrupt:
        print("\n[main] خاموش شد.", file=REAL_STDOUT, flush=True)