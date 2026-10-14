# Soroosh_tg_bot.py — v27.9.20 (bilingual fa/en · small-caps UI)
import os, sys, json, socket, asyncio, time, re, threading, secrets, random, hashlib
import logging, traceback, html as _html
from typing import Optional, Dict, Any, List, Set, Tuple

VERSION = "Soroosh v27.9.20"

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
           "httpcore", "telegram.ext.Updater", "telegram.request",
           "telethon", "splusthon", "asyncio"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)
    logging.getLogger(_n).propagate = False

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
    except Exception: UploadPhotoRequest = None; DeletePhotosRequest = None
    try: from splusthon.tl.types import InputPhoto, InputPhotoEmpty
    except Exception: InputPhoto = None; InputPhotoEmpty = None

    SendMediaRequest = None; InputMediaUploadedDocument = None; InputMediaUploadedPhoto = None
    try: from splusthon.tl.functions.messages import SendMediaRequest
    except Exception: pass
    try: from splusthon.tl.types import InputMediaUploadedDocument
    except Exception: pass
    try: from splusthon.tl.types import InputMediaUploadedPhoto
    except Exception: pass

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
    if hasattr(e, "message"): return str(e.message)[:300]
    return str(e)[:300]

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

def _is_group_or_channel(ent) -> bool:
    if ent is None: return False
    try:
        cls = type(ent).__name__.lower()
        if "user" in cls or "bot" in cls: return False
        if any(k in cls for k in ("channel", "chat", "group", "megagroup")): return True
        if getattr(ent, "first_name", None): return False
        if getattr(ent, "title", None): return True
        if hasattr(ent, "megagroup"): return True
    except Exception: pass
    return False

def _is_broadcast_channel(ent) -> bool:
    if ent is None: return False
    try:
        bc = getattr(ent, "broadcast", False)
        mg = getattr(ent, "megagroup", False)
        if bc and not mg: return True
        cls = type(ent).__name__.lower()
        if "channel" in cls and hasattr(ent, "broadcast") and not mg: return True
    except Exception: pass
    return False

def _is_actual_group(ent) -> bool:
    if ent is None: return False
    try:
        if _is_broadcast_channel(ent): return False
        cls = type(ent).__name__.lower()
        if "user" in cls or "bot" in cls: return False
        if getattr(ent, "megagroup", False): return True
        if "chat" in cls and "channel" not in cls: return True
        if not hasattr(ent, "broadcast") and getattr(ent, "title", None): return True
    except Exception: pass
    return False

def normalize_phone(raw: str) -> str:
    if not raw: return ""
    s = re.sub(r"[^\d]", "", str(raw))
    if not s: return ""
    if s.startswith("00"): s = s[2:]
    if s.startswith("0"): s = s[1:]
    if not s.startswith("98"): s = "98" + s
    if len(s) < 11 or len(s) > 13: raise ValueError(f"invalid: {raw}")
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


# ═══════════════ I18N + STYLE ═══════════════
LANG_FILE = os.path.join(SOROOSH_DIR, "lang.json")
def _get_lang():
    d = _load(LANG_FILE, {"v": "fa"})
    return d.get("v", "fa") if isinstance(d, dict) else "fa"
def _set_lang(v):
    _save(LANG_FILE, {"v": v})

_SC = str.maketrans({
    'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ꜰ','g':'ɢ','h':'ʜ','i':'ɪ',
    'j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ','q':'ǫ','r':'ʀ',
    's':'ꜱ','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x','y':'ʏ','z':'ᴢ',
    'A':'ᴀ','B':'ʙ','C':'ᴄ','D':'ᴅ','E':'ᴇ','F':'ꜰ','G':'ɢ','H':'ʜ','I':'ɪ',
    'J':'ᴊ','K':'ᴋ','L':'ʟ','M':'ᴍ','N':'ɴ','O':'ᴏ','P':'ᴘ','Q':'ǫ','R':'ʀ',
    'S':'ꜱ','T':'ᴛ','U':'ᴜ','V':'ᴠ','W':'ᴡ','X':'x','Y':'ʏ','Z':'ᴢ',
})
def SC(s): return str(s).translate(_SC)
TICK = "⤳"
def _line(): return "━━━━━━━━━━━━━━━━━━━━━━"

_TR = {
"panel":       {"fa": "پنل",        "en": "panel"},
"accounts_n":  {"fa": "اکانت‌ها",   "en": "accounts"},
"pv_enabled":  {"fa": "PV فعال",    "en": "pv enabled"},
"running_ops": {"fa": "در حال اجرا","en": "running ops"},
"idle":        {"fa": "بیکار",      "en": "idle"},
"listener":    {"fa": "لیسنر",      "en": "listener"},
"data_dir":    {"fa": "مسیر داده",  "en": "data dir"},
"send":        {"fa": "ارسال",      "en": "send"},
"joiner":      {"fa": "جوینر",      "en": "joiner"},
"lefter":      {"fa": "لفتر",       "en": "lefter"},
"templates":   {"fa": "قالب‌ها",    "en": "templates"},
"pv":          {"fa": "PV",         "en": "pv"},
"stats":       {"fa": "آمار",       "en": "stats"},
"errors":      {"fa": "خطاها",      "en": "errors"},
"cache":       {"fa": "کش",         "en": "cache"},
"linkdonies":  {"fa": "لینک‌دونی",  "en": "linkdonies"},
"settings":    {"fa": "تنظیمات",    "en": "settings"},
"back_to_panel": {"fa": "بازگشت به پنل","en": "back to panel"},
"back":        {"fa": "بازگشت",     "en": "back"},
"cancel":      {"fa": "لغو",        "en": "cancel"},
"next":        {"fa": "بعدی »",     "en": "next »"},
"prev":        {"fa": "« قبلی",     "en": "« prev"},
"yes":         {"fa": "بله",        "en": "yes"},
"no":          {"fa": "خیر",        "en": "no"},
"confirm":     {"fa": "تایید",      "en": "confirm"},
"start":       {"fa": "شروع",       "en": "start"},
"stop":        {"fa": "توقف",       "en": "stop"},
"add":         {"fa": "افزودن",     "en": "add"},
"delete":      {"fa": "حذف",        "en": "delete"},
"clear":       {"fa": "پاک",        "en": "clear"},
"toggle_on":   {"fa": "روشن کن",    "en": "turn on"},
"toggle_off":  {"fa": "خاموش کن",   "en": "turn off"},
"on":          {"fa": "روشن",       "en": "on"},
"off":         {"fa": "خاموش",      "en": "off"},
"yes_short":   {"fa": "بله",        "en": "yes"},
"no_short":    {"fa": "خیر",        "en": "no"},
"all":         {"fa": "همه",        "en": "all"},
"none":        {"fa": "خالی",       "en": "none"},
"loading":     {"fa": "در حال بارگذاری...", "en": "loading..."},
"saved":       {"fa": "ذخیره شد",   "en": "saved"},
"deleted":     {"fa": "حذف شد",     "en": "deleted"},
"cleared":     {"fa": "پاک شد",     "en": "cleared"},
"restarted":   {"fa": "ری‌استارت شد","en": "restarted"},
"not_found":   {"fa": "پیدا نشد.",  "en": "not found."},
"empty":       {"fa": "خالی",       "en": "empty"},
"enter":       {"fa": "بفرست",      "en": "send"},
"phone":       {"fa": "شماره",      "en": "phone"},
"id":          {"fa": "شناسه",      "en": "id"},
"name":        {"fa": "نام",        "en": "name"},
"last_name":   {"fa": "فامیل",      "en": "last name"},
"username":    {"fa": "یوزرنیم",    "en": "username"},
"bio":         {"fa": "بیو",        "en": "bio"},
"about":       {"fa": "درباره",     "en": "about"},
"photo":       {"fa": "عکس",        "en": "photo"},
"profile":     {"fa": "پروفایل",    "en": "profile"},
"channels":    {"fa": "کانال‌ها",   "en": "channels"},
"my_channels": {"fa": "کانال‌های من","en": "my channels"},
"create_channel": {"fa": "ساخت کانال جدید","en": "create new channel"},
"channel_title": {"fa": "عنوان",    "en": "title"},
"description": {"fa": "توضیحات",    "en": "description"},
"public":      {"fa": "عمومی",      "en": "public"},
"private":     {"fa": "خصوصی",      "en": "private"},
"type":        {"fa": "نوع",        "en": "type"},
"link":        {"fa": "لینک",       "en": "link"},
"get_link":    {"fa": "دریافت لینک","en": "get link"},
"set_link":    {"fa": "ثبت لینک",   "en": "set link"},
"seen":        {"fa": "دیده‌شده",   "en": "seen"},
"banned":      {"fa": "بلاک‌شده",   "en": "banned"},
"ld_progress": {"fa": "پیشرفت لینک‌دونی","en": "linkdoni progress"},
"clear_seen":  {"fa": "پاک seen",   "en": "clear seen"},
"clear_banned":{"fa": "پاک banned", "en": "clear banned"},
"clear_both":  {"fa": "پاک هر دو",  "en": "clear both"},
"reset_ld":    {"fa": "ریست progress","en": "reset ld progress"},
"wipe_all":    {"fa": "پاک کردن همه اکانت‌ها","en": "wipe all accounts"},
"select_account": {"fa": "یک اکانت انتخاب کن","en": "select an account"},
"pv_auto":     {"fa": "پاسخ خودکار PV","en": "auto-reply pv"},
"pv_status":   {"fa": "وضعیت",      "en": "status"},
"pv_active":   {"fa": "فعال",       "en": "on"},
"pv_inactive": {"fa": "خاموش",      "en": "off"},
"pv_poller":   {"fa": "پولر",       "en": "poller"},
"pv_max":      {"fa": "سقف/کاربر",  "en": "max/user"},
"pv_delay":    {"fa": "تایمر",      "en": "delay"},
"pv_notify":   {"fa": "اعلان",      "en": "notify"},
"pv_poll":     {"fa": "هر چند ثانیه","en": "poll"},
"pv_items":    {"fa": "پیام‌ها",    "en": "items"},
"pv_custom":   {"fa": "سفارشی",     "en": "custom"},
"pv_add_text": {"fa": "افزودن متن", "en": "+ text"},
"pv_add_file": {"fa": "افزودن فایل","en": "+ file"},
"pv_add_delay":{"fa": "افزودن تأخیر","en": "+ delay"},
"pv_list":     {"fa": "لیست پیام‌ها","en": "items"},
"pv_report":   {"fa": "گزارش",      "en": "report"},
"pv_reset_counter": {"fa": "ریست شمارنده","en": "reset counter"},
"pv_reset_custom":  {"fa": "حذف سفارشی","en": "reset custom"},
"pv_restart":  {"fa": "ری‌استارت",  "en": "restart"},
"pv_delay_q":  {"fa": "تایمر (0=آنی):","en": "delay (0=instant):"},
"pv_poll_q":   {"fa": "هر چند ثانیه؟ (حداقل 2):","en": "poll seconds (>=2):"},
"pv_text_q":   {"fa": "متن:",       "en": "text:"},
"pv_file_q":   {"fa": "پیام/عکس/فایل:","en": "send msg/photo/file:"},
"pv_delaysec_q":{"fa": "ثانیه:",    "en": "seconds:"},
"pv_report_title": {"fa": "گزارش PV","en": "pv report"},
"pv_total":    {"fa": "کل",         "en": "total"},
"pv_page":     {"fa": "صفحه",       "en": "page"},
"pv_no_accounts": {"fa": "هیچ اکانتی نداری.","en": "no accounts yet."},
"accounts_title": {"fa": "اکانت‌ها", "en": "accounts"},
"add_account":  {"fa": "افزودن اکانت","en": "add account"},
"account_stats": {"fa": "آمار اکانت","en": "account stats"},
"groups":       {"fa": "گروه‌ها",    "en": "groups"},
"pvs":          {"fa": "خصوصی",      "en": "pvs"},
"bots":         {"fa": "ربات‌ها",    "en": "bots"},
"channels_created": {"fa": "کانال ساخته","en": "channels created"},
"listener_status": {"fa": "لیسنر",   "en": "listener"},
"delete_account":  {"fa": "حذف اکانت","en": "delete account"},
"auto_tar":        {"fa": "Auto-Tar", "en": "auto-tar"},
"add_account_q":   {"fa": "شماره:\nمثال: <code>989121234567</code>","en": "phone number:\nexample: <code>989121234567</code>"},
"invalid_phone":   {"fa": "شماره نامعتبر:", "en": "invalid phone:"},
"acc_delete_q":    {"fa": "حذف <b>{n}</b>؟","en": "delete <b>{n}</b>?"},
"prof_first_q": {"fa": "نام:",       "en": "first name:"},
"prof_last_q":  {"fa": "فامیل:",     "en": "last name:"},
"prof_bio_q":   {"fa": "بیو:",       "en": "bio:"},
"prof_user_q":  {"fa": "یوزرنیم:",   "en": "username:"},
"prof_photo_menu": {"fa": "عکس پروفایل","en": "profile photo"},
"prof_set_photo":  {"fa": "تنظیم عکس جدید","en": "set new photo"},
"prof_del_photo":  {"fa": "حذف عکس‌ها","en": "delete photos"},
"prof_send_photo": {"fa": "عکس رو بفرست:","en": "send photo:"},
"prof_no_photo":   {"fa": "عکس نبود:", "en": "no photo:"},
"prof_deleting":   {"fa": "در حال حذف...","en": "deleting..."},
"prof_uploading":  {"fa": "در حال آپلود...","en": "uploading..."},
"ch_photo_menu":   {"fa": "عکس کانال","en": "channel photo"},
"ch_new_type": {"fa": "نوع کانال:", "en": "channel type:"},
"ch_new_name_q": {"fa": "اسم کانال:","en": "channel name:"},
"ch_new_user_q": {"fa": "یوزرنیم:",  "en": "username:"},
"ch_creating":  {"fa": "در حال ساخت...","en": "creating..."},
"ch_created":   {"fa": "ساخته شد",  "en": "created"},
"ch_no_channels": {"fa": "هنوز کانالی نساختی.","en": "no channels yet."},
"ch_created_list": {"fa": "کانال‌هایی که ساخت","en": "channels you created"},
"ch_send_q":   {"fa": "متن:",       "en": "text:"},
"ch_file_q":   {"fa": "فایل:",      "en": "file:"},
"ch_caption_q":{"fa": "کپشن:",      "en": "caption:"},
"ch_link_fetch": {"fa": "در حال دریافت...","en": "fetching..."},
"ch_link_q":   {"fa": "لینک:",      "en": "link:"},
"ch_profile_edit_title": {"fa": "اسم:", "en": "title:"},
"ch_profile_edit_desc": {"fa": "توضیح:", "en": "description:"},
"ch_profile_edit_user": {"fa": "یوزرنیم:", "en": "username:"},
"ch_delete_q":{"fa": "حذف کانال؟","en": "delete channel?"},
"listener_on":  {"fa": "روشن",      "en": "on"},
"listener_off": {"fa": "خاموش",     "en": "off"},
"listener_restart_all": {"fa": "ری‌استارت همه","en": "restart all"},
"listener_cfg": {"fa": "تنظیمات",   "en": "cfg"},
"ld_auto_join":  {"fa": "auto-join", "en": "auto-join"},
"ld_progress_per_acc": {"fa": "progress هر اکانت جداست","en": "progress per account"},
"ld_add_q":      {"fa": "لینک:",     "en": "link:"},
"ld_reset_prog": {"fa": "بازنشانی progress همه","en": "reset all progress"},
"ld_reset_list": {"fa": "بازنشانی لیست","en": "reset list"},
"ld_add":        {"fa": "افزودن",    "en": "+ add"},
"op_joiner":     {"fa": "Joiner",    "en": "joiner"},
"op_lefter":     {"fa": "Lefter",    "en": "lefter"},
"op_autotar":    {"fa": "Auto-Tar",  "en": "auto-tar"},
"op_send":       {"fa": "ارسال",     "en": "send"},
"op_running":    {"fa": "در حال اجرا","en": "running"},
"op_paused":     {"fa": "متوقف",     "en": "paused"},
"op_queued":     {"fa": "در صف",     "en": "queued"},
"op_done":       {"fa": "تکمیل",     "en": "done"},
"op_failed":     {"fa": "خطا",       "en": "failed"},
"op_cancelled":  {"fa": "لغو شده",   "en": "cancelled"},
"op_empty":      {"fa": "خالی",      "en": "empty"},
"op_draft":      {"fa": "پیش‌نویس", "en": "draft"},
"op_joined":     {"fa": "جوین",      "en": "joined"},
"op_sent":       {"fa": "ارسال",     "en": "sent"},
"op_left":       {"fa": "ترک",       "en": "left"},
"op_failed_c":   {"fa": "خطا",       "en": "failed"},
"op_tried":      {"fa": "امتحان",    "en": "tried"},
"op_wave":       {"fa": "موج",       "en": "wave"},
"op_round":      {"fa": "دور",       "en": "round"},
"op_phase":      {"fa": "مرحله",     "en": "phase"},
"op_limit":      {"fa": "سقف",       "en": "limit"},
"op_already":    {"fa": "قبلا عضو",  "en": "already"},
"op_blocked":    {"fa": "بلاک",      "en": "blocked"},
"op_skipped_seen": {"fa": "seen",    "en": "seen"},
"op_skipped_banned": {"fa": "banned","en": "banned"},
"op_rejected":   {"fa": "غیرفعال",   "en": "inactive"},
"stats_title":   {"fa": "آمار",      "en": "stats"},
"stats_done":    {"fa": "موفق",      "en": "done"},
"stats_failed":  {"fa": "ناموفق",    "en": "failed"},
"stats_errors":  {"fa": "خطاها",     "en": "errors"},
"stats_running": {"fa": "در حال اجرا","en": "running now"},
"errors_none":   {"fa": "خالی",      "en": "empty"},
"send_step1":    {"fa": "اکانت(ها)","en": "accounts"},
"send_step2":    {"fa": "متن را بفرست","en": "send the message text"},
"send_step3":    {"fa": "مقصد؟",     "en": "select target"},
"send_step4":    {"fa": "حداکثر؟",   "en": "max messages"},
"send_target_pv":{"fa": "خصوصی",     "en": "pv only"},
"send_target_gr":{"fa": "گروه‌ها",   "en": "groups only"},
"send_target_both":{"fa": "هر دو",   "en": "both"},
"send_grp_only": {"fa": "فقط گروه‌های واقعی","en": "real groups only"},
"send_infinite": {"fa": "لوپ بی‌نهایت","en": "infinite loop"},
"send_loop_delay":{"fa": "بین دورها", "en": "loop delay"},
"send_rescan":   {"fa": "rescan در هر دور","en": "rescan each round"},
"send_edit":     {"fa": "Edit-Delay","en": "edit delay"},
"send_random":   {"fa": "تصادفی",    "en": "random"},
"send_ph_list":  {"fa": "لیست",      "en": "list"},
"send_multi":    {"fa": "Multi-step","en": "multi-step edit"},
"send_attach":   {"fa": "پیوست فایل","en": "attach file"},
"send_auto_left":{"fa": "AutoLeave", "en": "auto leave"},
"send_attach_q": {"fa": "فایل:",     "en": "send file:"},
"send_loop_q":   {"fa": "ثانیه بین دورها:","en": "seconds between loops:"},
"send_edit_q":   {"fa": "ثانیه:",    "en": "seconds:"},
"send_ph_q":     {"fa": "placeholder:", "en": "placeholder text:"},
"send_max_q":    {"fa": "عدد (0=∞):","en": "number (0=∞):"},
"send_unlimited":{"fa": "بی‌نهایت","en": "unlimited"},
"send_custom":   {"fa": "دلخواه",    "en": "custom"},
"send_start":    {"fa": "شروع",      "en": "start"},
"jl_title":      {"fa": "جوینر",     "en": "joiner"},
"jl_select":     {"fa": "کدام اکانت؟","en": "select accounts"},
"jl_selected":   {"fa": "انتخاب‌شده", "en": "selected"},
"jl_speed":      {"fa": "سرعت",      "en": "speed"},
"jl_grp_only":   {"fa": "فقط گروه‌ها","en": "groups only"},
"jl_max":        {"fa": "سقف",       "en": "max join"},
"jl_speed_ultra":{"fa": "فوق‌سریع",  "en": "ultra"},
"jl_speed_fast": {"fa": "سریع",      "en": "fast"},
"jl_speed_normal":{"fa": "عادی",     "en": "normal"},
"jl_speed_safe": {"fa": "امن",       "en": "safe"},
"jl_ld":         {"fa": "لینک‌دونی", "en": "linkdonies"},
"jl_max_q":      {"fa": "عدد:",      "en": "number:"},
"jl_no_account": {"fa": "اول اکانت اضافه کن.","en": "add an account first."},
"lf_title":      {"fa": "لفتر",      "en": "lefter"},
"lf_mode":       {"fa": "حالت ترک",  "en": "leave mode"},
"lf_mode_all":   {"fa": "همه گروه‌ها و کانال‌ها","en": "all chats"},
"lf_mode_groups":{"fa": "فقط گروه‌ها","en": "groups only"},
"lf_mode_channels":{"fa": "فقط کانال‌ها","en": "channels only"},
"lf_mode_closed":{"fa": "فقط گروه‌های بسته","en": "closed groups"},
"lf_delay":      {"fa": "تاخیر",     "en": "delay"},
"at_title":      {"fa": "قالب‌ها",   "en": "templates"},
"at_desc":       {"fa": "قالب = ست کامل از تنظیمات","en": "template = full config set"},
"at_new":        {"fa": "ساخت قالب", "en": "+ new template"},
"at_channel":    {"fa": "کانال",     "en": "channel"},
"at_profile":    {"fa": "پروفایل",   "en": "profile"},
"at_joiner":     {"fa": "جوین",      "en": "joiner"},
"at_sender":     {"fa": "ارسال",     "en": "sender"},
"at_pv":         {"fa": "PV",        "en": "pv"},
"at_lefter":     {"fa": "ترک",       "en": "lefter"},
"at_rename":     {"fa": "تغییر نام", "en": "rename"},
"at_run":        {"fa": "اجرا روی اکانت","en": "run on accounts"},
"at_delete":     {"fa": "حذف",       "en": "delete"},
"at_mode_only":  {"fa": "فقط ارسال", "en": "send only"},
"at_mode_js":    {"fa": "جوین + ارسال","en": "join + send"},
"at_mode_jsl":   {"fa": "جوین + ارسال + ترک","en": "join + send + leave"},
"at_apply_acc":  {"fa": "اعمال روی اکانت‌ها","en": "apply to accounts"},
"at_run_title":  {"fa": "اجرای قالب","en": "run template"},
"at_rename_q":   {"fa": "نام:",      "en": "name:"},
"at_delete_q":   {"fa": "حذف <b>{n}</b>؟","en": "delete <b>{n}</b>?"},
"cfg_title":     {"fa": "تنظیمات",   "en": "settings"},
"cfg_lang":      {"fa": "زبان",      "en": "language"},
"cfg_lang_fa":   {"fa": "فارسی",     "en": "persian"},
"cfg_lang_en":   {"fa": "انگلیسی",   "en": "english"},
"cfg_join_delay":{"fa": "تاخیر جوین","en": "join delay"},
"cfg_wave_size": {"fa": "اندازه موج","en": "wave size"},
"cfg_extract":   {"fa": "سقف استخراج","en": "extract limit"},
"cfg_wait":      {"fa": "انتظار لینک","en": "wait for links"},
"cfg_auto_join": {"fa": "auto-join لینک‌دونی","en": "auto-join linkdoni"},
"cfg_listener":  {"fa": "لیسنر",     "en": "listener"},
"cfg_value_q":   {"fa": "مقدار جدید برای {k}:","en": "new value for {k}:"},
"cfg_invalid":   {"fa": "عدد نامعتبر","en": "invalid number"},
"error_prefix":  {"fa": "خطا",       "en": "error"},
"mode":          {"fa": "حالت",      "en": "mode"},
"max":           {"fa": "سقف",       "en": "max"},
"text":          {"fa": "متن",       "en": "text"},
"target":        {"fa": "مقصد",      "en": "target"},
"delay":         {"fa": "تاخیر",     "en": "delay"},
"file":          {"fa": "فایل",      "en": "file"},
"file_send":     {"fa": "ارسال فایل","en": "send file"},
"vars":          {"fa": "متغیرها",   "en": "vars"},
"yes_no":        {"fa": "بله / خیر", "en": "yes / no"},
}

def T(k, **kw):
    e = _TR.get(k)
    if not e: return k
    lang = _get_lang()
    s = e.get(lang) or e.get("en") or k
    for a, b in kw.items():
        s = s.replace("{" + a + "}", str(b))
    return s

def is_fa(): return _get_lang() == "fa"
def is_en(): return _get_lang() == "en"


# ═══════════════ PATHS ═══════════════
ACC_FILE         = os.path.join(SOROOSH_DIR, "accounts.json")
CFG_FILE         = os.path.join(SOROOSH_DIR, "config.json")
ERRORS_FILE      = os.path.join(SOROOSH_DIR, "errors.json")
OPS_FILE         = os.path.join(SOROOSH_DIR, "ops.json")
TEMPLATES_FILE   = os.path.join(SOROOSH_DIR, "templates.json")
SEEN_FILE        = os.path.join(SOROOSH_DIR, "seen_links.json")
BANNED_FILE      = os.path.join(SOROOSH_DIR, "banned_groups.json")
LDPROG_FILE      = os.path.join(SOROOSH_DIR, "linkdoni_progress.json")
PV_REPLIES_FILE  = os.path.join(SOROOSH_DIR, "pv_replies.json")
PV_ITEMS_FILE    = os.path.join(SOROOSH_DIR, "pv_items.json")
PV_REPORT_FILE   = os.path.join(SOROOSH_DIR, "pv_report.json")
PV_COUNTS_FILE   = os.path.join(SOROOSH_DIR, "pv_counts.json")
PV_WM_FILE       = os.path.join(SOROOSH_DIR, "pv_wm.json")
PV_ACCOUNT_FILE  = os.path.join(SOROOSH_DIR, "pv_per_account.json")

_SEEN_CACHE: Dict[str, Set[str]] = {}
_BANNED_CACHE: Dict[str, Dict[str, Any]] = {}
_LDPROG_CACHE: Dict[str, Dict[str, int]] = {}
_PV_WM: Optional[Dict[str, Dict[str, int]]] = None
_PV_WM_DIRTY = False


def _load_seen(aid: str) -> Set[str]:
    if not aid: return set()
    if aid in _SEEN_CACHE: return _SEEN_CACHE[aid]
    all_d = _load(SEEN_FILE, {})
    if not isinstance(all_d, dict): all_d = {}
    acc = all_d.get(aid) or {}
    _SEEN_CACHE[aid] = set(acc.keys())
    return _SEEN_CACHE[aid]

def _mark_seen(aid: str, h: str):
    if not aid or not h: return
    seen = _load_seen(aid)
    if h in seen: return
    seen.add(h)
    try:
        all_d = _load(SEEN_FILE, {})
        if not isinstance(all_d, dict): all_d = {}
        acc = all_d.setdefault(aid, {})
        acc[h] = 1
        if len(acc) > 50000:
            all_d[aid] = dict(list(acc.items())[-40000:])
            _SEEN_CACHE[aid] = set(all_d[aid].keys())
        _save(SEEN_FILE, all_d)
    except Exception: pass

def _is_seen(aid: str, h: str) -> bool:
    if not aid or not h: return False
    return h in _load_seen(aid)

def _clear_seen(aid: str = None):
    if aid:
        _SEEN_CACHE.pop(aid, None)
        try:
            all_d = _load(SEEN_FILE, {})
            if isinstance(all_d, dict):
                all_d.pop(aid, None); _save(SEEN_FILE, all_d)
        except Exception: pass
    else:
        _SEEN_CACHE.clear()
        try: _save(SEEN_FILE, {})
        except Exception: pass

def _seen_count(aid: str) -> int:
    return len(_load_seen(aid))


def _load_banned(aid: str) -> Dict[str, Any]:
    if not aid: return {}
    if aid in _BANNED_CACHE: return _BANNED_CACHE[aid]
    all_d = _load(BANNED_FILE, {})
    if not isinstance(all_d, dict): all_d = {}
    acc = all_d.get(aid) or {}
    if not isinstance(acc, dict): acc = {}
    _BANNED_CACHE[aid] = acc
    return acc

def _mark_banned(aid: str, h: str, reason: str = ""):
    if not aid or not h: return
    try:
        all_d = _load(BANNED_FILE, {})
        if not isinstance(all_d, dict): all_d = {}
        acc = all_d.setdefault(aid, {})
        acc[h] = {"reason": str(reason)[:120], "ts": int(time.time())}
        _BANNED_CACHE[aid] = acc
        _save(BANNED_FILE, all_d)
    except Exception: pass

def _is_banned(aid: str, h: str) -> bool:
    if not aid or not h: return False
    return h in _load_banned(aid)

def _clear_banned(aid: str = None):
    if aid:
        _BANNED_CACHE.pop(aid, None)
        try:
            all_d = _load(BANNED_FILE, {})
            if isinstance(all_d, dict):
                all_d.pop(aid, None); _save(BANNED_FILE, all_d)
        except Exception: pass
    else:
        _BANNED_CACHE.clear()
        try: _save(BANNED_FILE, {})
        except Exception: pass

def _banned_count(aid: str) -> int:
    return len(_load_banned(aid))


def _load_ldprog(aid: str) -> Dict[str, int]:
    if not aid: return {}
    if aid in _LDPROG_CACHE: return _LDPROG_CACHE[aid]
    all_d = _load(LDPROG_FILE, {})
    if not isinstance(all_d, dict): all_d = {}
    acc = all_d.get(aid) or {}
    if not isinstance(acc, dict): acc = {}
    _LDPROG_CACHE[aid] = acc
    return acc

def _get_ld_last(aid: str, url: str) -> int:
    try: return int(_load_ldprog(aid).get(url, 0))
    except Exception: return 0

def _set_ld_last(aid: str, url: str, max_id: int):
    if not aid or not url: return
    try:
        all_d = _load(LDPROG_FILE, {})
        if not isinstance(all_d, dict): all_d = {}
        acc = all_d.setdefault(aid, {})
        old = int(acc.get(url, 0))
        if int(max_id) > old:
            acc[url] = int(max_id)
            _LDPROG_CACHE[aid] = acc
            _save(LDPROG_FILE, all_d)
    except Exception: pass

def _reset_ld_progress(aid: str = None):
    if aid:
        _LDPROG_CACHE.pop(aid, None)
        try:
            all_d = _load(LDPROG_FILE, {})
            if isinstance(all_d, dict):
                all_d.pop(aid, None); _save(LDPROG_FILE, all_d)
        except Exception: pass
    else:
        _LDPROG_CACHE.clear()
        try: _save(LDPROG_FILE, {})
        except Exception: pass


def _pv_count(aid, uid) -> int:
    d = _load(PV_COUNTS_FILE, {})
    return int((d.get(aid) or {}).get(str(uid), 0))

def _pv_count_add(aid, uid, delta):
    d = _load(PV_COUNTS_FILE, {})
    acc = d.setdefault(aid, {})
    acc[str(uid)] = max(0, int(acc.get(str(uid), 0)) + delta)
    _save(PV_COUNTS_FILE, d)

def _pv_limit_reached(aid, uid, cfg) -> bool:
    mx = int(cfg.get("max_replies", 1) or 0)
    return mx > 0 and _pv_count(aid, uid) >= mx

def _wm_load():
    global _PV_WM
    if _PV_WM is None:
        d = _load(PV_WM_FILE, {})
        _PV_WM = d if isinstance(d, dict) else {}
    return _PV_WM

def _wm_get(aid, uid) -> int:
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

def _load_pv_replies() -> Dict[str, Any]:
    d = _load(PV_REPLIES_FILE, {}); return d if isinstance(d, dict) else {}

def _save_pv_replies(d): _save(PV_REPLIES_FILE, d)

def _clear_pv_replies():
    _save(PV_COUNTS_FILE, {}); _save(PV_REPLIES_FILE, {})


DEFAULT_PV_ITEMS = {
    "enabled": False, "delay_seconds": 0, "reply_once": True, "max_replies": 1,
    "notify": True, "notify_on_receive": True, "notify_on_reply": True,
    "poll_seconds": 3, "items": [{"kind": "text", "text": "سلام 👋"}]
}

def _load_pv_items() -> Dict[str, Any]:
    d = _load(PV_ITEMS_FILE, DEFAULT_PV_ITEMS)
    if not isinstance(d, dict): return dict(DEFAULT_PV_ITEMS)
    for k, v in DEFAULT_PV_ITEMS.items():
        if k not in d: d[k] = v
    return d

def _save_pv_items(d): _save(PV_ITEMS_FILE, d)

def _load_pv_account(aid: str) -> Dict[str, Any]:
    base = _load_pv_items()
    if not aid: return base
    per = _load(PV_ACCOUNT_FILE, {})
    if not isinstance(per, dict): per = {}
    acc_cfg = per.get(aid)
    if not isinstance(acc_cfg, dict): acc_cfg = {}
    merged = {**base, **acc_cfg}
    if not isinstance(merged.get("items"), list) or not merged.get("items"):
        merged["items"] = base.get("items") or []
    return merged

def _save_pv_account(aid: str, cfg: Dict[str, Any]):
    if not aid: return
    per = _load(PV_ACCOUNT_FILE, {})
    if not isinstance(per, dict): per = {}
    per[aid] = {
        "enabled": bool(cfg.get("enabled", False)),
        "delay_seconds": int(cfg.get("delay_seconds", 0)),
        "reply_once": bool(cfg.get("reply_once", True)),
        "max_replies": int(cfg.get("max_replies", 1)),
        "notify": bool(cfg.get("notify", True)),
        "notify_on_receive": bool(cfg.get("notify_on_receive", True)),
        "notify_on_reply": bool(cfg.get("notify_on_reply", True)),
        "poll_seconds": int(cfg.get("poll_seconds", 3)),
        "items": list(cfg.get("items") or []),
    }
    _save(PV_ACCOUNT_FILE, per)

def _has_pv_account(aid: str) -> bool:
    per = _load(PV_ACCOUNT_FILE, {})
    return isinstance(per, dict) and aid in per

def _delete_pv_account(aid: str):
    per = _load(PV_ACCOUNT_FILE, {})
    if isinstance(per, dict): per.pop(aid, None); _save(PV_ACCOUNT_FILE, per)

def _load_pv_report() -> Dict[str, Any]:
    d = _load(PV_REPORT_FILE, {}); return d if isinstance(d, dict) else {}

def _save_pv_report(d): _save(PV_REPORT_FILE, d)

def _record_pv_visit(aid: str, user_id: str, user_info: Dict[str, Any] = None):
    rep = _load_pv_report()
    acc = rep.setdefault(aid, {})
    uid = str(user_id); now = int(time.time())
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


# ═══════════════ Loop ═══════════════
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

class _GlobalConns:
    def __init__(self):
        self._sem_by_loop: Dict[int, asyncio.Semaphore] = {}
        self._lock = threading.Lock()
    def get(self, limit=15):
        try: loop = asyncio.get_running_loop()
        except RuntimeError: return None
        key = id(loop)
        with self._lock:
            sem = self._sem_by_loop.get(key)
            if sem is None:
                sem = asyncio.Semaphore(limit)
                self._sem_by_loop[key] = sem
            return sem

_GLOBAL_CONNS = _GlobalConns()

class SafeSoroushClient:
    def __init__(self, aid, session_string, name=None, use_lock=True):
        self.aid = aid; self.session_string = session_string
        self.name = name or aid; self._client = None
        self._lock = _get_account_lock(aid) if use_lock else None
        self._locked = False
        self._global_sem = None; self._global_held = False

    def __getattr__(self, name):
        if name.startswith("_"): raise AttributeError(name)
        raw = self.__dict__.get("_client")
        if raw is None:
            raise AttributeError(f"SafeSoroushClient[{self.__dict__.get('aid','?')}]: not connected ({name})")
        return getattr(raw, name)

    async def __aenter__(self):
        self._global_sem = _GLOBAL_CONNS.get(limit=15)
        if self._global_sem is not None:
            try:
                await asyncio.wait_for(self._global_sem.acquire(), timeout=40)
                self._global_held = True
            except (asyncio.TimeoutError, asyncio.CancelledError):
                flog(f"[client] global sem timeout for {self.aid}", "warning")
        if self._lock:
            try:
                await asyncio.wait_for(self._lock.acquire(), timeout=5); self._locked = True
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._locked = False
                try:
                    if self._lock.locked():
                        self._lock._locked = False; self._lock._waiters = []
                except Exception: pass
        try:
            await self._connect(); return self
        except BaseException:
            if self._locked:
                try: self._lock.release()
                except Exception: pass
                self._locked = False
            if self._global_held and self._global_sem:
                try: self._global_sem.release()
                except Exception: pass
                self._global_held = False
            raise

    async def __aexit__(self, *args, **kwargs):
        try: await self._disconnect()
        finally:
            if self._locked:
                try: self._lock.release()
                except Exception: pass
                self._locked = False
            if self._global_held and self._global_sem:
                try: self._global_sem.release()
                except Exception: pass
                self._global_held = False

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
            try:
                if cli: await cli._disconnect()
            except Exception: pass
            await asyncio.sleep(2 + i)
    return None, last_err


# ═══════════════ State ═══════════════
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
    err_up = str(error).upper()
    if "CHANNELPRIVATEERROR" in err_up or "CHANNEL_PRIVATE" in err_up: return
    if "REQUEST WAS UNSUCCESSFUL" in err_up: return
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
    try: _delete_pv_account(aid)
    except Exception: pass
    try: _clear_seen(aid); _clear_banned(aid); _reset_ld_progress(aid)
    except Exception: pass

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
            out["id"] = cid_i; out["guid"] = "c" + str(cid_i)
            if cid_i < 0:
                s = str(cid_i)
                out["raw_id"] = int(s[4:]) if s.startswith("-100") else abs(cid_i)
            else: out["raw_id"] = cid_i
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
                inp = InputChannel(cand, int(ah)); return inp, f"ic_raw:{cand}"
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
                t2 = (getattr(ent, "title", None) or getattr(d, "name", None) or "")
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
        if cid_int > 0: formats = [cid_int, -cid_int, int(f"-100{cid_int}")]
        else:
            abs_id = abs(cid_int); s = str(abs_id)
            if s.startswith("100") and len(s) > 10:
                raw = int(s[3:]); formats = [cid_int, raw, -raw, int(f"-100{raw}")]
            else: formats = [cid_int, abs_id, int(f"-100{abs_id}")]
        formats += [str(cid_int), f"-100{cid_int}" if cid_int > 0 else str(cid_int)]
        seen_f = set()
        for fmt in formats:
            key = str(fmt)
            if key in seen_f: continue
            seen_f.add(key)
            try:
                ent = await cli.get_entity(fmt)
                if ent: return ent, f"ge:{fmt}"
            except Exception as e: tried.append(f"ge:{fmt}:{type(e).__name__}")

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
    if idx < 0 or idx >= len(channels): return False, "no channel"
    a = get_account(aid)
    if not a: return False, "no account"
    if not text or not text.strip(): return False, "empty"
    cli = None
    try:
        cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=2)
        if cli is None: return False, f"connect: {err}"
        ent, method = await _resolve_channel_entity(cli, channels[idx], aid)
        if not ent: return False, f"resolve: {method[:150]}"
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
    if idx < 0 or idx >= len(channels): return False, "no channel"
    a = get_account(aid)
    if not a: return False, "no account"
    ch = channels[idx]
    cli = None; last_errs: List[str] = []
    try:
        cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=2)
        if cli is None: return False, f"connect: {err}"
        ent, method = await _resolve_channel_entity(cli, ch, aid)
        if not ent: return False, f"resolve: {method[:150]}"
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
        return False, "no link · " + " | ".join(last_errs[-3:])
    except Exception as e:
        return False, f"{type(e).__name__}: {_fmt_error(e)}"
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass


async def diagnose_channel(aid: str, idx: int) -> str:
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return "no channel"
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
        out["error"] = f"resolve: {method[:100]}"; return out
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

async def get_account_stats(aid: str, force: bool = False) -> Dict[str, Any]:
    now = time.time()
    c = _STATS_CACHE.get(aid)
    if c and not force and (now - c["ts"]) < _STATS_CACHE_TTL: return c["data"]
    acc = get_account(aid)
    if not acc: return {"groups": 0, "pvs": 0, "channels": 0, "bots": 0, "total": 0, "error": "no account"}
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


# ═══════════════ Login ═══════════════
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
            r = cli.sign_up(phone=variant, code=code, first_name="User", last_name="Soroosh", phone_code_hash=hash_)
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
        if not kwargs: return False, "no data"
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
    if CreateChannelRequest is None: return False, None, "no CreateChannelRequest"
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
                        d_title = (getattr(ent, "title", None) or getattr(d, "name", None) or "")
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
                        t = (getattr(ent, "title", None) or getattr(d, "name", None) or "")
                        if t == title and ent is not None:
                            channel = ent; break
                except Exception: pass
            return True, channel, "created"
        except TypeError as e:
            last_err = e; continue
        except Exception as e:
            return False, None, f"{type(e).__name__}: {_fmt_error(e)}"
    return False, None, f"TypeError: {last_err}"


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
                cls = type(ent).__name__.lower()
                if "channel" in cls and not mg: return "channel", ent
                if mg: return "group", ent
                if "chat" in cls: return "group", ent
                if not hasattr(ent, "broadcast") and getattr(ent, "title", None):
                    return "group", ent
                return "group", ent
        except Exception: pass
        return "unknown", None


# ═══════════════ Send helpers ═══════════════
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


async def _send_with_edit_delay(cli, entity, real_text: str, placeholder: str = "hi",
                                edit_delay: float = 3.0, log=None, placeholder_list: str = "",
                                delay_random: bool = False, delay_min: float = 2.0, delay_max: float = 6.0,
                                multi_step: bool = False, multi_middle: str = "Hi"):
    if not real_text or not str(real_text).strip():
        return False, "empty_text"
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
        return True, None
    return True, f"edit_failed:{edit_err[:80]}"


async def _send_to_entity(cli, entity, text, snd_cfg: Dict[str, Any], log=None):
    if not text or not str(text).strip():
        return False, "empty_text"
    use_edit = bool(snd_cfg.get("edit_delay_enabled", False))
    if use_edit:
        return await _send_with_edit_delay(cli, entity, text,
            placeholder=snd_cfg.get("placeholder_text", "hi") or "hi",
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
    async def _aw(r):
        return (await r) if asyncio.iscoroutine(r) else r
    try:
        cap = caption if (caption and str(caption).strip()) else None
        if not file_path:
            if cap:
                try:
                    await _aw(cli.send_message(entity, cap)); return True, "text_only"
                except Exception as e:
                    return False, f"text:{type(e).__name__}"
            return False, "no_path"
        if not os.path.exists(file_path): return False, "not_found"
        fname = os.path.basename(file_path)
        try: fsize = os.path.getsize(file_path)
        except Exception: fsize = 0
        kind = _detect_file_kind(file_path)
        flog(f"[send-file] {fname} kind={kind} size={fsize}")
        errs: List[str] = []
        def _susp(e): return "USER_SUSPENDED" in str(e).upper()
        try:
            await asyncio.wait_for(cli.get_me(), timeout=15)
        except Exception: pass
        sf = getattr(cli, "send_file", None)
        sd = getattr(cli, "send_document", None)
        up = getattr(cli, "upload_file", None)
        if sf:
            if cap:
                variants_a = [
                    ("plain", {"caption": cap}),
                    ("workers1", {"caption": cap, "workers": 1, "file_size": fsize}),
                    ("doc", {"caption": cap, "force_document": True, "workers": 1, "file_size": fsize}),
                ]
            else:
                variants_a = [
                    ("no_cap", {}),
                    ("no_cap_doc", {"force_document": True}),
                    ("no_cap_workers", {"workers": 1, "file_size": fsize}),
                    ("no_cap_force_file", {"force_file": True}),
                ]
            for tag, kw in variants_a:
                try:
                    await _aw(sf(entity, file_path, **kw))
                    return True, f"OK-sf-{tag}"
                except TypeError as te:
                    errs.append(f"sf:{tag}:TypeErr:{str(te)[:50]}"); continue
                except FloodWaitError as fe:
                    await asyncio.sleep(min(fe.seconds + 1, 30))
                    errs.append(f"sf:{tag}:Flood{fe.seconds}"); continue
                except Exception as e:
                    errs.append(f"sf:{tag}:{type(e).__name__}:{str(e)[:55]}")
                    if _susp(e): return False, "ACCOUNT_SUSPENDED"
        if sd:
            try:
                if cap: await _aw(sd(entity, file_path, caption=cap))
                else: await _aw(sd(entity, file_path))
                return True, "OK-sd"
            except TypeError:
                try:
                    await _aw(sd(entity, file_path))
                    return True, "OK-sd-nocap"
                except Exception as e:
                    errs.append(f"sd:{type(e).__name__}:{str(e)[:55]}")
            except Exception as e:
                errs.append(f"sd:{type(e).__name__}:{str(e)[:55]}")
                if _susp(e): return False, "ACCOUNT_SUSPENDED"
        if up:
            for kb in (None, 512, 256, 128, 64, 32):
                up_kw: Dict[str, Any] = {"file_name": fname, "use_cache": False}
                if kb: up_kw["part_size_kb"] = kb
                handle = None
                try:
                    handle = await _aw(up(file_path, **up_kw))
                except TypeError:
                    try: handle = await _aw(up(file_path))
                    except Exception as e:
                        errs.append(f"up[{kb}]:{type(e).__name__}:{str(e)[:55]}"); continue
                except FloodWaitError as fe:
                    await asyncio.sleep(min(fe.seconds + 1, 30))
                    errs.append(f"up[{kb}]:Flood{fe.seconds}"); continue
                except Exception as e:
                    errs.append(f"up[{kb}]:{type(e).__name__}:{str(e)[:55]}")
                    if _susp(e): return False, "ACCOUNT_SUSPENDED"
                    continue
                if handle is None: continue
                if sf:
                    for tag_h, kw_h in (
                        ("h_plain", {"caption": cap} if cap else {}),
                        ("h_doc", {"caption": cap, "force_document": True} if cap else {"force_document": True}),
                    ):
                        try:
                            await _aw(sf(entity, handle, **kw_h))
                            return True, f"OK-sf-{tag_h}-{kb}"
                        except Exception as e:
                            errs.append(f"sf:{tag_h}[{kb}]:{type(e).__name__}:{str(e)[:45]}")
        try:
            me = await cli.get_me()
            if me and sf:
                try:
                    r = await _aw(sf(me, file_path))
                    mid = getattr(r, "id", None)
                    if mid is None:
                        upd = getattr(r, "updates", None) or r
                        for m in (getattr(upd, "updates", None) or getattr(upd, "messages", None) or []):
                            mid = getattr(m, "id", None)
                            if mid: break
                    if mid:
                        fm = getattr(cli, "forward_messages", None)
                        if fm:
                            await _aw(fm(entity, mid, me))
                            if cap:
                                try: await _aw(cli.send_message(entity, cap))
                                except Exception: pass
                            return True, "OK-self-fwd"
                except Exception as e:
                    errs.append(f"self:{type(e).__name__}:{str(e)[:45]}")
        except Exception: pass
        if cap:
            try:
                await _aw(cli.send_message(entity, cap))
                return True, "text_fallback"
            except Exception: pass
        tail = " | ".join(errs[-5:])[:250] if errs else "no_variants"
        flog(f"[send-file] ALL FAILED: {tail}", "error")
        return False, f"all_failed: {tail}"
    except asyncio.CancelledError: raise
    except Exception as e:
        return False, f"exception:{type(e).__name__}:{str(e)[:120]}"


async def soroosh_set_profile_photo(cli, file_path: str) -> Tuple[bool, str]:
    if not os.path.exists(file_path): return False, "file not found"
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
    if not os.path.exists(file_path): return False, "file not found"
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


# ═══════════════ Lefter workers ═══════════════
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
        await _set_phase("connect")
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
        if cli is None:
            await _finish(f"✗ connect: {err}"); return
        await _set_phase("collect")
        own_ids = get_own_channel_ids(aid)
        targets = await _lefter_collect(cli, mode, exclude_ids=own_ids)
        if not targets: await _finish("nothing"); return
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["progress"]["total"] = len(targets); _save_op(op2)
        for t in targets:
            async with lock:
                op2 = _get_op(op_id)
                if not op2 or op2.get("status") == "cancelled": await _finish("cancelled"); return
            try:
                ok, err2 = await asyncio.wait_for(_lefter_leave_one(cli, t), timeout=30)
                if ok:
                    left += 1
                    if err2 == "banned_from_group":
                        h = _hash_of("@c" + str(t.get("id", "")))
                        _mark_banned(aid, h, "banned_from_group")
                else:
                    failed += 1; add_error("lefter", err2, t.get("name"), name)
            except Exception as e: failed += 1; add_error("lefter", _fmt_error(e), t.get("name"), name)
            async with lock:
                op2 = _get_op(op_id)
                if op2:
                    op2["progress"]["joined"] = left; op2["progress"]["failed"] = failed
                    op2["progress"]["phase"] = f"{left}/{len(targets)}"; _save_op(op2)
            if delay > 0: await asyncio.sleep(delay)
        await _finish(f"left {left} · failed {failed}")
    except asyncio.CancelledError: await _finish("cancelled"); raise
    except Exception as e: await _finish(f"✗ {type(e).__name__}")
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
    op["progress"] = {"joined": 0, "failed": 0, "total": 0, "phase": "start"}
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


# ═══════════════ Templates ═══════════════
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
    elif section == "pv": t.setdefault("pv", {})[field] = value
    else: t.setdefault(section, {})[field] = value
    save_templates(ts)

def new_template(name: str = "new template") -> Dict[str, Any]:
    return {
        "id": "tp_" + secrets.token_hex(4), "name": name, "created": int(time.time()),
        "channel": {"type": "private", "title": "", "username": "", "about": "", "photo_file": ""},
        "profile": {"first_name": "", "last_name": "", "username": "", "bio": "", "photo_file": ""},
        "joiner": {"max_join": 0, "speed": "fast", "groups_only": True},
        "sender": {
            "text": "", "target": "groups", "mode": "send_only",
            "max_send": 0, "delay": 1.5,
            "edit_delay_enabled": False, "edit_delay_seconds": 3.0,
            "edit_delay_random": False, "edit_delay_min": 2.0, "edit_delay_max": 6.0,
            "placeholder_text": "hi", "placeholder_random": False,
            "placeholder_list": "hi,hey,hello,yo",
            "multi_step_edit": False, "multi_step_middle": "Hi",
            "send_to_existing": True,
            "attach_file": "", "attach_caption": "",
            "infinite_loop": False, "loop_delay": 3.0, "rescan_targets": True,
        },
        "pv": {
            "enabled": False, "delay_seconds": 0, "reply_once": True, "max_replies": 1,
            "notify": True, "notify_on_receive": True, "notify_on_reply": True,
            "poll_seconds": 3, "items": [{"kind": "text", "text": "hi 👋"}],
            "apply_to_accounts": True,
        },
        "lefter": {"leave_mode": "closed"},
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


# ═══════════════ Extract / Join ═══════════════
JL_SPEEDS = [("ultra", "ultra", 0.3), ("fast", "fast", 1.0),
             ("normal", "normal", 3.0), ("slow", "safe", 8.0)]
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

async def _extract_from_linkdoni(aid: str, cli, url: str, limit: int = 300, log=None, deep_scan: bool = False) -> List[str]:
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
            last_max = _get_ld_last(aid, url)
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
            if max_seen_id > last_max: _set_ld_last(aid, url, max_seen_id)
            return links
        offset_id = 0; pages_done = 0
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
            if entity is not None and _is_broadcast_channel(entity):
                try: await _lefter_leave_one(cli, {"entity": entity, "kind": "channel"})
                except Exception: pass
                return False, "is_broadcast_channel", "channel", entity
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
            if _is_broadcast_channel(ent):
                return False, "is_broadcast_channel", "channel", ent
            await cli(JoinChannelRequest(ent))
            return True, None, "username", ent
        except Exception as e:
            msg = str(e).upper()
            if "USER_ALREADY" in msg or "ALREADY" in msg:
                try:
                    ent = await cli.get_entity(uname)
                    if _is_group_or_channel(ent):
                        if _is_broadcast_channel(ent):
                            return False, "is_broadcast_channel", "channel", ent
                        return True, None, "already", ent
                except Exception: pass
                return True, None, "already", None
            if _is_rate_limit(e): raise
            return False, _fmt_error(e), "username", None


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
                "skipped_banned": p.get("skipped_banned", 0), "rejected": p.get("rejected", 0),
                "round": p.get("round", 0)}
    return {"done": p.get("sent", 0), "failed": p.get("failed", 0),
            "pending": p.get("pending", 0), "in_progress": p.get("in_progress", 0),
            "total": p.get("total", 0), "blocked": p.get("blocked", 0), "round": p.get("round", 0)}

def _op_effective_status(op):
    st = op.get("status", "draft")
    if op.get("type") in ("joinlef", "lefter", "autotar"):
        if st in ("done", "failed", "cancelled", "paused"): return st
        return "running"
    return st

def _op_status_label(st):
    return T("op_" + st) if ("op_" + st) in _TR else st

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
                if _is_broadcast_channel(ent): continue
                if not _is_actual_group(ent): continue
            kind = "pv" if is_user else ("groups" if (is_group or is_channel) else None)
            if kind is None: continue
            if is_user and my_id and eid == my_id: continue
            if target == "pv" and kind != "pv": continue
            if target == "groups" and kind != "groups": continue
            out.append({"type": kind, "target": eid, "entity": ent, "name": title or str(eid)})
        except Exception: continue
    return out


# ═══════════════ Joiner worker ═══════════════
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
        await _set_phase("connecting")
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
        if cli is None:
            await _finish(f"✗ connect: {err}"); return
        try:
            me = await asyncio.wait_for(cli.get_me(), timeout=25)
            await _set_phase(f"ok: {me.first_name or aid}")
        except Exception as e:
            try: await cli._disconnect()
            except Exception: pass
            await _finish(f"✗ get_me: {type(e).__name__}"); return
        auto_join = int(cfg.get("auto_join_linkdoni", 1))
        if auto_join:
            for i, url in enumerate(link_donies, 1):
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") == "cancelled": await _finish("cancelled"); return
                await _set_phase(f"auto-join {i}/{len(link_donies)}")
                try: await asyncio.wait_for(_auto_join_linkdoni(cli, url, log=log), timeout=30)
                except Exception: pass
        deep_scan_done = False; wait_round = 0
        while True:
            async with lock:
                op2 = _get_op(op_id)
                if not op2 or op2.get("status") == "cancelled": await _finish("cancelled"); return
            if max_join and joined >= max_join: await _finish("limit"); return
            wave_num += 1
            await _set_phase(f"wave {wave_num}: extracting")
            tasks = []
            for url in link_donies:
                async def _one(u=url, deep=False):
                    try: return await asyncio.wait_for(_extract_from_linkdoni(aid, cli, u, limit=extract_limit, log=log, deep_scan=deep), timeout=180)
                    except Exception: return []
                tasks.append(asyncio.create_task(_one()))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            new_links = []
            for r in results:
                if isinstance(r, list):
                    for lk in r:
                        h = _hash_of(lk)
                        if not h: continue
                        if _is_seen(aid, h): skipped_seen += 1; continue
                        if _is_banned(aid, h): skipped_banned += 1; continue
                        if lk in new_links: continue
                        new_links.append(lk)
                        if len(new_links) >= wave_size: break
                if len(new_links) >= wave_size: break
            if not new_links and not deep_scan_done:
                deep_scan_done = True
                await _set_phase(f"wave {wave_num}: deep scan")
                tasks2 = []
                for url in link_donies:
                    async def _one2(u=url):
                        try: return await asyncio.wait_for(_extract_from_linkdoni(aid, cli, u, limit=300, log=log, deep_scan=True), timeout=180)
                        except Exception: return []
                    tasks2.append(asyncio.create_task(_one2()))
                results2 = await asyncio.gather(*tasks2, return_exceptions=True)
                for r in results2:
                    if isinstance(r, list):
                        for lk in r:
                            h = _hash_of(lk)
                            if not h: continue
                            if _is_seen(aid, h): skipped_seen += 1; continue
                            if _is_banned(aid, h): skipped_banned += 1; continue
                            if lk in new_links: continue
                            new_links.append(lk)
                            if len(new_links) >= wave_size: break
                    if len(new_links) >= wave_size: break
            if not new_links:
                wait_round += 1
                if wait_round > max_wait_rounds:
                    await _finish(f"no new links"); return
                await _set_phase(f"waiting {wait_seconds}s ({wait_round}/{max_wait_rounds})")
                for _ in range(wait_seconds):
                    async with lock:
                        op2 = _get_op(op_id)
                        if not op2 or op2.get("status") == "cancelled": await _finish("cancelled"); return
                    await asyncio.sleep(1)
                wave_num -= 1; deep_scan_done = False; continue
            else:
                wait_round = 0
            await _set_phase(f"{len(new_links)} links")
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
                    if _is_seen(aid, h) or _is_banned(aid, h): return
                    if groups_only:
                        kind, _pre = await _check_link_type(cli, lk)
                        if kind == "channel":
                            skipped_channel += 1; _mark_seen(aid, h); return
                    try:
                        ok, err2, tag, ent_new = await asyncio.wait_for(_try_join(cli, lk), timeout=30)
                        if ok:
                            _mark_seen(aid, h)
                            if ent_new is not None and _is_group_or_channel(ent_new):
                                if _is_broadcast_channel(ent_new):
                                    try: await _lefter_leave_one(cli, {"entity": ent_new, "kind": "channel"})
                                    except Exception: pass
                                    skipped_channel += 1
                                    return
                                active, reason = await _is_group_active(cli, ent_new)
                                if not active:
                                    rejected_inactive += 1
                                    _mark_banned(aid, h, f"inactive:{reason}")
                                    if tag != "already":
                                        try: await _lefter_leave_one(cli, {"entity": ent_new, "kind": "group"})
                                        except Exception: pass
                                    return
                            joined += 1
                        else:
                            failed += 1; add_error("join", err2, lk, name)
                            if err2 and ("BANNED" in err2.upper() or "KICKED" in err2.upper() or
                                          "CHANNEL_PRIVATE" in err2.upper()):
                                _mark_banned(aid, h, err2[:80])
                            if err2 == "is_broadcast_channel":
                                skipped_channel += 1
                            _mark_seen(aid, h)
                    except Exception as e:
                        failed += 1; add_error("join", _fmt_error(e), lk, name)
                        try: _mark_seen(aid, h)
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
            await _set_phase(f"wave {wave_num}: {joined} joined / {failed} failed")
    except asyncio.CancelledError: await _finish("cancelled"); raise
    except Exception as e:
        flog(f"[joiner] FATAL: {traceback.format_exc()}", "error")
        await _finish(f"✗ {type(e).__name__}")
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
    op["progress"] = {"joined": 0, "failed": 0, "total": 0, "phase": "start",
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


# ═══════════════ Sender worker ═══════════════
async def _send_worker(aid, acc, op_id, cfg, stop, log):
    name = acc.get("name") or acc.get("phone") or aid
    op = _get_op(op_id)
    if not op: return
    lock = _get_op_lock(op_id); sent = 0; failed = 0; blocked = 0
    delay = float(op.get("delay", 1.5)); payload = op.get("payload") or {"text": "hi"}
    text = payload.get("text") or "hi"
    auto_left = bool(op.get("auto_left", False))
    groups_only = bool(op.get("groups_only", True))
    attach_file = op.get("attach_file") or ""
    infinite_loop = bool(op.get("infinite_loop", False))
    loop_delay = float(op.get("loop_delay", 3.0))
    rescan_targets = bool(op.get("rescan_targets", True))
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
        await _set_phase("connecting")
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
        if cli is None:
            async with lock:
                op2 = _get_op(op_id)
                if op2: op2["progress"]["phase"] = f"✗ connect: {err}"; op2["status"] = "done"; _save_op(op2)
            return
        await _set_phase("collecting targets")
        own_ids = get_own_channel_ids(aid)
        targets = await _collect_targets(cli, op.get("target", "both"), exclude_ids=own_ids, groups_only=groups_only)
        if not targets and not infinite_loop:
            async with lock:
                op2 = _get_op(op_id)
                if op2: op2["progress"]["phase"] = "no targets"; op2["status"] = "done"; _save_op(op2)
            return
        max_send = int(op.get("max", 0) or 0)
        if max_send and len(targets) > max_send: targets = targets[:max_send]
        snd_cfg = {
            "edit_delay_enabled": bool(op.get("edit_delay_enabled", False)),
            "edit_delay_seconds": float(op.get("edit_delay_seconds", 3.0)),
            "edit_delay_random": bool(op.get("edit_delay_random", False)),
            "edit_delay_min": float(op.get("edit_delay_min", 2.0)),
            "edit_delay_max": float(op.get("edit_delay_max", 6.0)),
            "placeholder_text": op.get("placeholder_text", "hi"),
            "placeholder_random": bool(op.get("placeholder_random", False)),
            "placeholder_list": op.get("placeholder_list", ""),
            "multi_step_edit": bool(op.get("multi_step_edit", False)),
            "multi_step_middle": op.get("multi_step_middle", "Hi"),
        }
        use_edit = snd_cfg["edit_delay_enabled"]
        loop_round = 0; sent_ids: Set[int] = set()

        while True:
            loop_round += 1
            if infinite_loop:
                await _set_phase(f"loop {loop_round} — {len(targets)} targets")
            else:
                await _set_phase(f"sending to {len(targets)}" + (" (edit)" if use_edit else ""))
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
                _tid = None
                try:
                    _e = t.get("entity")
                    if _e is not None: _tid = getattr(_e, "id", None)
                    if _tid is None: _tid = t.get("target")
                except Exception: pass
                try:
                    ent = t.get("entity") or t["target"]
                    if attach_file and os.path.exists(attach_file):
                        _ok, _err = await _send_file_to_entity(cli, ent, attach_file, text)
                        if not _ok and text:
                            try:
                                _r = cli.send_message(ent, text)
                                if asyncio.iscoroutine(_r): _r = await _r
                                _ok, _err = True, "file_failed_text_sent"
                            except Exception: pass
                    else:
                        _ok, _err = await _send_to_entity(cli, ent, text, snd_cfg, log=log)
                    if _ok:
                        sent += 1
                        if _tid is not None:
                            try: sent_ids.add(int(_tid))
                            except Exception: pass
                    else:
                        if _err and _err.startswith("BLOCKED:"):
                            blocked += 1
                        else:
                            failed += 1
                            add_error("send", _err or "send_failed", t.get("name"), name)
                        if _err and "SUSPENDED" in _err.upper():
                            async with lock:
                                op2 = _get_op(op_id)
                                if op2:
                                    op2["status"] = "failed"
                                    op2["progress"]["phase"] = f"account suspended: {name}"
                                    _save_op(op2)
                            return
                except RuntimeError as re:
                    if "ACCOUNT_SUSPENDED" in str(re):
                        async with lock:
                            op2 = _get_op(op_id)
                            if op2:
                                op2["status"] = "failed"
                                op2["progress"]["phase"] = f"account suspended: {name}"
                                _save_op(op2)
                        return
                    raise
                except FloodWaitError as fe:
                    failed += 1
                    add_error("send", f"Flood {fe.seconds}s", t.get("name"), name)
                    await asyncio.sleep(fe.seconds + 1)
                except Exception as e:
                    failed += 1
                    add_error("send", _fmt_error(e), t.get("name"), name)
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
            if rescan_targets:
                await _set_phase(f"loop {loop_round}: rescanning")
                try:
                    fresh = await _collect_targets(cli, op.get("target", "both"),
                                                    exclude_ids=own_ids, groups_only=groups_only)
                    if max_send and len(fresh) > max_send: fresh = fresh[:max_send]
                    old_ids = set()
                    for t in targets:
                        try:
                            _e = t.get("entity")
                            if _e is not None:
                                _id = getattr(_e, "id", None)
                                if _id is not None: old_ids.add(int(_id))
                        except Exception: pass
                    new_added = 0
                    for t in fresh:
                        try:
                            _e = t.get("entity")
                            _id = getattr(_e, "id", None)
                            if _id is None: continue
                            if int(_id) in old_ids: continue
                            targets.append(t); new_added += 1
                        except Exception: continue
                    await _set_phase(f"loop {loop_round}: +{new_added} new targets")
                except Exception as ee:
                    flog(f"[send] rescan err: {ee}", "warning")
            await _set_phase(f"loop {loop_round} done · wait {loop_delay:.0f}s")
            waited = 0.0
            while waited < loop_delay:
                if stop.is_set(): return
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") == "cancelled": return
                chunk = min(1.0, loop_delay - waited)
                await asyncio.sleep(chunk); waited += chunk

        async with lock:
            op2 = _get_op(op_id)
            if op2:
                op2["progress"]["phase"] = f"sent {sent} · failed {failed}" + (f" · blocked {blocked}" if blocked else "")
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
    op["progress"] = {"sent": 0, "failed": 0, "total": 0, "pending": 0, "in_progress": 0,
                      "phase": "start", "blocked": 0, "round": 0}
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


# ═══════════════ AutoTar worker ═══════════════
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

    # PV apply
    pv_cfg = tpl.get("pv") or {}
    if pv_cfg.get("apply_to_accounts") and pv_cfg.get("items"):
        try:
            cur = _load_pv_account(aid)
            cur.update({
                "enabled": bool(pv_cfg.get("enabled", cur.get("enabled", False))),
                "delay_seconds": int(pv_cfg.get("delay_seconds", cur.get("delay_seconds", 0))),
                "reply_once": bool(pv_cfg.get("reply_once", cur.get("reply_once", True))),
                "max_replies": int(pv_cfg.get("max_replies", cur.get("max_replies", 1))),
                "notify": bool(pv_cfg.get("notify", cur.get("notify", True))),
                "poll_seconds": int(pv_cfg.get("poll_seconds", cur.get("poll_seconds", 3))),
                "items": list(pv_cfg.get("items") or []),
            })
            _save_pv_account(aid, cur)
            flog(f"[autotar] PV applied to {aid}")
        except Exception as e:
            flog(f"[autotar] pv apply err: {e}", "warning")

    live_task = asyncio.create_task(_live())
    try:
        await _phase("connecting")
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
        if cli is None:
            await _finish(f"✗ connect: {err}"); return
        try:
            me = await asyncio.wait_for(cli.get_me(), timeout=25)
            await _phase(f"ok: {me.first_name or aid}")
        except Exception as e:
            try: await cli._disconnect()
            except Exception: pass
            await _finish(f"✗ get_me: {type(e).__name__}"); return

        own_channel_ids: Set[int] = get_own_channel_ids(aid)
        cfg = _load(CFG_FILE, DEFAULT_CFG)
        wait_seconds = int(cfg.get("wait_for_links_sec", 90))
        max_wait_rounds = int(cfg.get("max_wait_rounds", 20))

        ch = tpl.get("channel") or {}
        private_link = ""; private_title = ""
        if ch.get("title"):
            ctype = ch.get("type", "private"); is_pub = ctype == "public"
            title = _substitute(ch["title"], ctx)[:60] or f"channel {ctx['n']}"
            about = _substitute(ch.get("about", ""), ctx)
            await _phase(f"creating channel: {title}")
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
                        _nc = ch_data.get("id"); _nr = ch_data.get("raw_id")
                        if _nc is not None: own_channel_ids.add(int(_nc))
                        if _nr is not None: own_channel_ids.add(int(_nr))
                    except Exception: pass
                    await asyncio.sleep(1.0)
                    try:
                        chs = get_stored_channels(aid)
                        tg = ch_data.get("guid"); ti = ch_data.get("id")
                        for i2, c2 in enumerate(chs):
                            hit = False
                            if tg and c2.get("guid") == tg: hit = True
                            elif ti is not None and c2.get("id") == ti: hit = True
                            if hit:
                                ok2, link = await export_invite_link(aid, i2)
                                if ok2: private_link = link
                                break
                    except Exception: pass
                    if not private_link and ch_data.get("username"):
                        private_link = f"https://splus.ir/{ch_data['username']}"
                    private_title = ch_data.get("title", "") or ""
                    ctx["Link_private"] = private_link
                    ctx["Title_private"] = private_title
                    ctx["Link_channel"] = private_link
                    ctx["Title_channel"] = private_title
                    if ch.get("photo_file") and os.path.exists(ch["photo_file"]):
                        try:
                            ent_ph, _ = await _resolve_channel_entity(cli, ch_data, aid)
                            if ent_ph: await soroosh_set_channel_photo(cli, ent_ph, ch["photo_file"])
                        except Exception: pass
                else:
                    add_error("autotar-channel", msg, title, name)
            except Exception as e:
                add_error("autotar-channel", _fmt_error(e), title, name)

        p = tpl.get("profile") or {}
        if p.get("first_name") or p.get("last_name") or p.get("bio") or p.get("username") or p.get("photo_file"):
            await _phase("updating profile")
            kwargs = {}
            if p.get("first_name"): kwargs["first_name"] = _substitute(p["first_name"], ctx)[:64]
            if p.get("last_name"): kwargs["last_name"] = _substitute(p["last_name"], ctx)[:64]
            if p.get("bio"): kwargs["about"] = _substitute(p["bio"], ctx)[:70]
            if kwargs:
                try:
                    r = cli(UpdateProfileRequest(**kwargs))
                    if asyncio.iscoroutine(r): r = await r
                except Exception as e: add_error("autotar-profile", _fmt_error(e), None, name)
            if p.get("username"):
                try:
                    r = cli(UpdateUsernameRequest(username=_substitute(p["username"], ctx)))
                    if asyncio.iscoroutine(r): r = await r
                except Exception as e: add_error("autotar-username", _fmt_error(e), None, name)
            if p.get("photo_file") and os.path.exists(p["photo_file"]):
                try: await soroosh_set_profile_photo(cli, p["photo_file"])
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
        infinite_loop = bool(snd.get("infinite_loop", False))
        loop_delay = float(snd.get("loop_delay", 3.0))
        rescan_targets = bool(snd.get("rescan_targets", True))

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
                                _extract_from_linkdoni(aid, cli, u, limit=300, log=log, deep_scan=use_deep),
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
                            if _is_seen(aid, h): skipped_seen += 1; continue
                            if _is_banned(aid, h): skipped_banned += 1; continue
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
                if _is_seen(aid, h): return
                if _is_banned(aid, h): return
                if groups_only:
                    kind, _pre = await _check_link_type(cli, lk)
                    if kind == "channel":
                        skipped_channel += 1; _mark_seen(aid, h); return
                tried_count += 1
                try:
                    ok, err2, tag, joined_ent = await asyncio.wait_for(_try_join(cli, lk), timeout=30)
                except Exception as e:
                    ok, err2, tag, joined_ent = False, _fmt_error(e), "exc", None
                if not ok:
                    failed_count += 1
                    if err2 and ("BANNED" in err2.upper() or "KICKED" in err2.upper() or
                                  "CHANNEL_PRIVATE" in err2.upper()):
                        _mark_banned(aid, h, err2[:80])
                    elif err2 and not _is_perm_error(err2):
                        failed_queue.append(lk)
                    else:
                        add_error("autotar-join", err2, lk, name)
                    if err2 == "is_broadcast_channel":
                        skipped_channel += 1
                    _mark_seen(aid, h)
                    await _stat(joined=joined_count, already=already_count,
                                failed=failed_count, tried=tried_count)
                    if join_delay > 0: await asyncio.sleep(join_delay)
                    return
                if tag == "already":
                    already_count += 1; _mark_seen(aid, h)
                else:
                    joined_count += 1; _mark_seen(aid, h)
                ent_for_check = joined_ent
                if ent_for_check is None: ent_for_check = await _find_new_entity()
                if ent_for_check is None and lk.startswith("@"):
                    try: ent_for_check = await cli.get_entity(lk.lstrip("@"))
                    except Exception: pass
                active = True
                if ent_for_check is not None and _is_group_or_channel(ent_for_check):
                    if _is_broadcast_channel(ent_for_check):
                        try: await _lefter_leave_one(cli, {"entity": ent_for_check, "kind": "channel"})
                        except Exception: pass
                        skipped_channel += 1
                        if join_delay > 0: await asyncio.sleep(join_delay)
                        return
                    active, reason = await _is_group_active(cli, ent_for_check)
                    if not active:
                        rejected_inactive += 1
                        _mark_banned(aid, h, f"inactive:{reason}")
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
                            add_error("autotar-send", _err or "send_failed", lk, name)
                            if _err and "SUSPENDED" in _err.upper():
                                await _finish(f"account suspended: {name}"); return
                    except RuntimeError as re:
                        if "ACCOUNT_SUSPENDED" in str(re):
                            await _finish(f"account suspended: {name}"); return
                        raise
                    except Exception as e:
                        failed_count += 1
                        add_error("autotar-send", _fmt_error(e), lk, name)
                await _stat(joined=joined_count, already=already_count, sent=sent_count,
                            failed=failed_count, tried=tried_count, left=left_count,
                            rejected=rejected_inactive)
                if join_delay > 0: await asyncio.sleep(join_delay)

            while joined_count < max_join and wave_num < max_waves:
                if await _is_cancelled(): await _finish("cancelled"); return
                wave_num += 1
                await _stat(wave=wave_num)
                await _phase(f"wave {wave_num} ({joined_count}/{max_join})")
                new_links = await _extract_wave(use_deep=False)
                retry_links = []
                for lk in failed_queue[:]:
                    h = _hash_of(lk)
                    if h and not _is_seen(aid, h) and not _is_banned(aid, h):
                        if lk not in new_links: retry_links.append(lk)
                failed_queue = []
                for lk in retry_links: new_links.append(lk)
                if not new_links and not deep_scan_done:
                    deep_scan_done = True
                    await _phase(f"wave {wave_num}: deep scan")
                    deep_links = await _extract_wave(use_deep=True)
                    for lk in deep_links:
                        if lk not in new_links: new_links.append(lk)
                    for lk in retry_links:
                        if lk not in new_links: new_links.append(lk)
                if not new_links:
                    wait_round += 1
                    if wait_round > max_wait_rounds:
                        await _phase("waves done"); break
                    await _phase(f"waiting {wait_seconds}s ({wait_round}/{max_wait_rounds})")
                    for _ in range(wait_seconds):
                        if await _is_cancelled(): await _finish("cancelled"); return
                        await asyncio.sleep(1)
                    wave_num -= 1; deep_scan_done = False; continue
                else:
                    wait_round = 0
                await _phase(f"wave {wave_num}: {len(new_links)} links")
                sem = asyncio.Semaphore(8)
                async def _limited(lk):
                    async with sem: await _join_one(lk)
                await asyncio.gather(*[asyncio.create_task(_limited(lk)) for lk in new_links],
                                     return_exceptions=True)
                await _phase(f"wave {wave_num} done — {joined_count}/{max_join}")

            if joined_count < max_join and failed_queue:
                if await _is_cancelled(): await _finish("cancelled"); return
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
            loop_round = 0
            while True:
                loop_round += 1
                await _phase(f"sending (loop {loop_round})" if infinite_loop else "sending")
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
                if not targets and not infinite_loop: break
                for i, t in enumerate(targets, 1):
                    if await _is_cancelled(): await _finish("cancelled"); return
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
                                except Exception: pass
                        else:
                            _ok, _err = await _send_to_entity(cli, ent, sender_text, snd, log=log)
                        if _ok:
                            sent_count += 1
                            try:
                                _seid = getattr(ent, "id", None)
                                if _seid is not None: sent_ids.add(int(_seid))
                            except Exception: pass
                        else:
                            failed_count += 1
                            add_error("autotar-send", _err or "send_failed", t.get("name"), name)
                            if _err and "SUSPENDED" in _err.upper():
                                await _finish(f"account suspended: {name}"); return
                    except RuntimeError as re:
                        if "ACCOUNT_SUSPENDED" in str(re):
                            await _finish(f"account suspended: {name}"); return
                        raise
                    except FloodWaitError as fe:
                        failed_count += 1; add_error("autotar-send", f"Flood {fe.seconds}s", t.get("name"), name)
                    except Exception as e:
                        failed_count += 1; add_error("autotar-send", _fmt_error(e), t.get("name"), name)
                    await _stat(sent=sent_count, failed=failed_count, pending=max(0, len(targets) - i))
                    if delay > 0: await asyncio.sleep(delay)
                if not infinite_loop: break
                if await _is_cancelled(): await _finish("cancelled"); return
                await _phase(f"loop {loop_round} done · wait {loop_delay:.0f}s")
                waited = 0.0
                while waited < loop_delay:
                    if await _is_cancelled(): await _finish("cancelled"); return
                    await asyncio.sleep(min(1.0, loop_delay - waited)); waited += 1.0

        lf = tpl.get("lefter") or {}
        if lf.get("leave_mode"):
            ml = lf["leave_mode"]
            await _phase(f"leaving ({ml})")
            for t in await _lefter_collect(cli, ml, exclude_ids=own_channel_ids):
                if await _is_cancelled(): await _finish("cancelled"); return
                try:
                    ok_l, _ = await _lefter_leave_one(cli, t)
                    if ok_l: left_count += 1; await _stat(left=left_count)
                except Exception: pass
                await asyncio.sleep(0.6)

        await _finish(f"joined {joined_count} · sent {sent_count} · left {left_count} · "
                      f"inactive {rejected_inactive} · channel-skip {skipped_channel} · seen {skipped_seen}")
    except asyncio.CancelledError: await _finish("cancelled"); raise
    except Exception as e:
        flog(f"[autotar] FATAL: {traceback.format_exc()}", "error")
        await _finish(f"✗ {type(e).__name__}")
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
        op["status"] = "failed"; op["progress"]["phase"] = "no template"; _save_op(op); return
    op["progress"] = {"joined": 0, "failed": 0, "total": 0, "pending": 0,
                      "in_progress": 0, "phase": "start", "sent": 0, "already": 0,
                      "tried": 0, "wave": 0, "left": 0, "round": 0,
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


# ═══════════════ Listener / Keepalive ═══════════════
LISTENER_TASKS: Dict[str, asyncio.Task] = {}

async def _listener_loop(aid, acc, stop_event):
    name = acc.get("name") or acc.get("phone") or aid
    flog(f"[listener] {name}: started")
    while not stop_event.is_set():
        cli = None
        try:
            cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=3)
            if cli is None:
                await asyncio.sleep(30); continue
            raw = cli.raw
            @raw.on(events.NewMessage(incoming=True))
            async def _on_new(event):
                try:
                    if getattr(event, "is_private", False) and not getattr(event, "out", False):
                        STATE["listener_new_count"] = STATE.get("listener_new_count", 0) + 1
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
        LISTENER_TASKS[aid] = t

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


# ═══════════════ PV Poller ═══════════════
PV_LISTENER_TASKS: Dict[str, asyncio.Task] = {}
_PV_SEEN_MSGS: Dict[str, Dict[str, float]] = {}
_PV_REPLY_TASKS: Dict[str, asyncio.Task] = {}
_PV_STOP_EVENTS: Dict[str, asyncio.Event] = {}


async def _sleep_or_stop(ev, sec):
    try: await asyncio.wait_for(ev.wait(), timeout=sec)
    except asyncio.TimeoutError: pass


async def _pv_send_reply(aid, acc, sender_id, user_info, stop_event, sender_entity=None):
    name = acc.get("name") or aid
    sender_str = str(sender_id); key = f"{aid}:{sender_str}"
    cfg = _load_pv_account(aid)
    cli = None; connected = False; send_ok = True; send_err = None

    def _fail(msg):
        nonlocal send_ok, send_err
        send_ok = False; send_err = str(msg)[:150]

    try:
        for _ in range(int(cfg.get("delay_seconds", 0))):
            if stop_event.is_set():
                _pv_count_add(aid, sender_str, -1); return
            await asyncio.sleep(1)
        cfg = _load_pv_account(aid)
        cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=2, per_timeout=20)
        if cli is None:
            _fail(f"connect: {err}")
        else:
            connected = True
            target = sender_entity
            if target is None:
                try: target = await cli.get_entity(sender_id)
                except Exception: target = sender_id
            for item in cfg.get("items") or []:
                if stop_event.is_set(): break
                kind = item.get("kind", "text")
                try:
                    if kind == "text" and item.get("text"):
                        r = cli.send_message(target, item["text"])
                        if asyncio.iscoroutine(r): await r
                    elif kind == "file":
                        fp = item.get("file_path")
                        if fp and os.path.exists(fp):
                            ok, e2 = await _send_file_to_entity(cli, target, fp, item.get("caption") or "")
                            if not ok: _fail(e2)
                        else: _fail("file missing")
                    elif kind == "fwd_saved":
                        me = await cli.get_me()
                        fm = getattr(cli, "forward_messages", None)
                        if fm:
                            r = fm(target, int(item.get("message_id", 0)), me)
                            if asyncio.iscoroutine(r): await r
                    elif kind == "delay":
                        await asyncio.sleep(int(item.get("seconds", 3))); continue
                    await asyncio.sleep(random.uniform(0.8, 1.8))
                except FloodWaitError as fe:
                    _fail(f"Flood {fe.seconds}s"); await asyncio.sleep(min(fe.seconds + 1, 30))
                except Exception as e:
                    _fail(f"{type(e).__name__}: {str(e)[:100]}")
    except asyncio.CancelledError:
        if not connected: _pv_count_add(aid, sender_str, -1)
        raise
    except Exception as e:
        _fail(f"{type(e).__name__}: {str(e)[:100]}")
    finally:
        if cli:
            try: await cli._disconnect()
            except Exception: pass
        _PV_REPLY_TASKS.pop(key, None)

    if not connected:
        _pv_count_add(aid, sender_str, -1)
    try: _record_pv_reply(aid, sender_str, ok=send_ok, err=send_err)
    except Exception: pass
    if cfg.get("notify", True) and cfg.get("notify_on_reply", True):
        u = user_info.get("first_name") or user_info.get("username") or sender_str
        if send_ok:
            await tg_send(f"{{💬}} reply ok: <b>{esc(u)}</b>")
        else:
            await tg_send(f"{{💬}} reply failed: <b>{esc(u)}</b> — <code>{esc(send_err or '?')}</code>")


async def _pv_handle_new_msg(cli, aid, acc, sender, sender_id, msg):
    cfg = _load_pv_account(aid)
    if not cfg.get("enabled"): return
    uid = str(sender_id); key = f"{aid}:{uid}"
    info = {"first_name": getattr(sender, "first_name", "") or "",
            "last_name": getattr(sender, "last_name", "") or "",
            "username": getattr(sender, "username", "") or ""}
    try: _record_pv_visit(aid, uid, info)
    except Exception: pass
    if _pv_limit_reached(aid, uid, cfg): return
    ex = _PV_REPLY_TASKS.get(key)
    if ex and not ex.done(): return
    _pv_count_add(aid, uid, +1)
    if cfg.get("notify", True) and cfg.get("notify_on_receive", True):
        u = info["first_name"] or info["username"] or uid
        mt = getattr(msg, "text", None) or getattr(msg, "message", "") or "(media)"
        await tg_send(f"{{🔔}} new pv · <b>{esc(u)}</b>\n✉️{TICK}text : <code>{esc(mt[:200])}</code>")
    ev = _PV_STOP_EVENTS.get(aid)
    if ev is None: ev = _PV_STOP_EVENTS[aid] = asyncio.Event()
    _PV_REPLY_TASKS[key] = asyncio.create_task(
        _pv_send_reply(aid, acc, sender_id, info, ev, sender))


async def _pv_poller_worker(aid, acc, stop_event):
    global _PV_WM_DIRTY
    name = acc.get("name") or aid
    cli = None; my_id = None
    flog(f"[pv] {name}: poller started")
    try:
        while not stop_event.is_set():
            cfg = _load_pv_account(aid)
            poll = max(2, int(cfg.get("poll_seconds", 3)))
            if not cfg.get("enabled"):
                await _sleep_or_stop(stop_event, poll); continue
            try:
                if cli is None:
                    cli, err = await _connect_with_retry(aid, acc["session_string"], name=name, tries=1, per_timeout=20)
                    if cli is None:
                        await _sleep_or_stop(stop_event, 10); continue
                    my_id = getattr((await cli.get_me()), "id", None)
                dialogs = await asyncio.wait_for(cli.get_dialogs(limit=60), timeout=30)
                first = not (_wm_load().get(aid) or {}).get("_init")
                for d in dialogs or []:
                    if not getattr(d, "is_user", False) or getattr(d, "is_bot", False): continue
                    uid = getattr(d, "id", None)
                    if not uid or (my_id and uid == my_id): continue
                    sender = getattr(d, "entity", None)
                    if sender is None: continue
                    last = getattr(d, "message", None)
                    if last is None:
                        try:
                            ms = await cli.get_messages(sender, limit=1)
                            last = ms[0] if ms else None
                        except Exception: last = None
                    mid = getattr(last, "id", None)
                    if not mid or int(mid) <= _wm_get(aid, uid): continue
                    _wm_set(aid, uid, mid)
                    if first or getattr(last, "out", False): continue
                    try:
                        dt = getattr(last, "date", None)
                        if dt and time.time() - dt.timestamp() > 3600: continue
                    except Exception: pass
                    try: await _pv_handle_new_msg(cli, aid, acc, sender, uid, last)
                    except Exception as he: flog(f"[pv] handle: {he}", "warning")
                if first:
                    _wm_load().setdefault(aid, {})["_init"] = 1
                    _PV_WM_DIRTY = True
                _wm_flush()
            except asyncio.CancelledError: raise
            except Exception as e:
                flog(f"[pv] {name}: {type(e).__name__}: {e}", "warning")
                if cli:
                    try: await cli._disconnect()
                    except Exception: pass
                    cli = None
                await _sleep_or_stop(stop_event, 8); continue
            await _sleep_or_stop(stop_event, poll)
    finally:
        _wm_flush()
        if cli:
            try: await cli._disconnect()
            except Exception: pass
        flog(f"[pv] {name}: poller stopped")


async def start_pv_responders():
    for aid, acc in list_accounts().items():
        cfg = _load_pv_account(aid)
        if not cfg.get("enabled"): continue
        existing = PV_LISTENER_TASKS.get(aid)
        if existing and not existing.done(): continue
        stop = asyncio.Event(); _PV_STOP_EVENTS[aid] = stop
        t = asyncio.create_task(_pv_poller_worker(aid, acc, stop))
        PV_LISTENER_TASKS[aid] = t

def _stop_all_pv():
    for aid, st in list(_PV_STOP_EVENTS.items()):
        try: st.set()
        except: pass
    for aid, t in list(PV_LISTENER_TASKS.items()):
        if not t.done(): t.cancel()
    for key, t in list(_PV_REPLY_TASKS.items()):
        if not t.done(): t.cancel()
    PV_LISTENER_TASKS.clear(); _PV_REPLY_TASKS.clear()
    _PV_STOP_EVENTS.clear(); _PV_SEEN_MSGS.clear()

async def restart_all_pv():
    _stop_all_pv(); await asyncio.sleep(1); await start_pv_responders()

def _stop_pv_for_account(aid):
    st = _PV_STOP_EVENTS.pop(aid, None)
    if st:
        try: st.set()
        except: pass
    t = PV_LISTENER_TASKS.pop(aid, None)
    if t and not t.done(): t.cancel()
    _PV_SEEN_MSGS.pop(aid, None)

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
                    if cli: await cli.get_me()
                except Exception: pass
                finally:
                    if cli:
                        try: await cli._disconnect()
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
                            except: pass
                    await start_pv_responders()
            await asyncio.sleep(KEEPALIVE_SECONDS)
        except asyncio.CancelledError: raise
        except Exception: await asyncio.sleep(60)


# ═══════════════ Telegram UI ═══════════════
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

def B(label, data): return InlineKeyboardButton(label, callback_data=data)
def SEL(active, label): return ("[✓] " if active else "[ ] ") + label
def kb_(*rows): return InlineKeyboardMarkup([list(r) for r in rows if r])
def grid(btns, cols=2):
    return [btns[i:i+cols] for i in range(0, len(btns), cols)]
def nav(back=None, home=True):
    row = []
    if back: row.append(B(f"« {T('back')}", back))
    if home: row.append(B(T("back_to_panel"), "menu:main"))
    return row

def head(icon, key_or_text, sub=None):
    t = T(key_or_text) if key_or_text in _TR else key_or_text
    s = f"{{{icon}}} {SC(t)}"
    if sub is not None: s += f"  ({sub})"
    return "\n" + s + "\n" + _line() + "\n\n"

def mrow(emoji, key, value, key_width=22):
    k = SC(T(key) if key in _TR else key)
    pad = " " * max(1, key_width - len(k))
    return f"{emoji}{TICK}{k}{pad}  :  {value}"

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
    await panel(body, kb_([B(f"« {T('cancel')}", "conv:cancel")]), page_tag="ask")

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
    for attr in ("photo", "video", "animation", "document", "audio", "voice", "sticker"):
        try:
            v = getattr(msg, attr, None)
            if v:
                if isinstance(v, (list, tuple)) and v: return v[-1]
                return v
        except Exception: continue
    return None

async def _download_tg_file(media_obj, aid: str, prefix: str) -> str:
    if APP is None: raise RuntimeError("APP not ready")
    if media_obj is None: raise RuntimeError("no_media")
    file_id = getattr(media_obj, "file_id", None)
    if not file_id: raise RuntimeError("no_file_id")
    f = await APP.bot.get_file(file_id)
    ext = os.path.splitext(getattr(f, "file_path", "") or "")[1] or ".bin"
    fname = f"{prefix}_{aid}_{int(time.time())}_{secrets.token_hex(3)}{ext}"
    full = os.path.join(UPLOADS_DIR, fname)
    try:
        await f.download_to_drive(full)
    except AttributeError:
        data = await f.download_as_bytearray()
        with open(full, "wb") as fp: fp.write(bytes(data))
    if not os.path.exists(full) or os.path.getsize(full) == 0:
        raise RuntimeError("empty_file")
    return full


# ═══════════════ MAIN PANEL ═══════════════
async def show_main():
    accounts = list_accounts()
    running = [o for o in _load_ops() if _op_effective_status(o) == "running"]
    pv_enabled = sum(1 for aid in accounts if _load_pv_account(aid).get("enabled"))
    txt = head("🌀", "panel", VERSION)
    txt += mrow("👤", "accounts_n", len(accounts)) + "\n"
    txt += mrow("💬", "pv_enabled", pv_enabled) + "\n"
    txt += mrow("📊", "running_ops", (len(running) if running else T("idle"))) + "\n"
    txt += mrow("👂", "listener", sum(1 for t in LISTENER_TASKS.values() if not t.done())) + "\n"
    txt += mrow("💾", "data_dir", f"<code>{esc(DATA_DIR)}</code>")
    rows = []
    if running: rows.append([B(f"{T('running_ops')} ({len(running)})", f"op:view:{running[0]['id']}")])
    rows += [
        [B(T("send"), "send:start"), B(T("joiner"), "jl:start")],
        [B(T("lefter"), "lf:start"), B(T("templates"), "at:menu")],
        [B(T("accounts_n"), "menu:acc"), B(T("pv"), "menu:pv")],
        [B(T("stats"), "menu:stats"), B(T("errors"), "menu:errors"), B(T("cache"), "menu:cache")],
        [B(T("listener"), "menu:listen"), B(T("linkdonies"), "ld:list:jl:back_to_settings")],
        [B(T("settings"), "menu:cfg")],
    ]
    await panel(txt, kb_(*rows), page_tag="main")


# ═══════════════ CACHE ═══════════════
async def show_cache_menu():
    accounts = list_accounts()
    txt = head("🗂", "cache")
    txt += T("select_account") + "\n\n"
    rows = []
    for aid, a in accounts.items():
        sn = _seen_count(aid); bn = _banned_count(aid); ln = len(_load_ldprog(aid))
        rows.append([B(f"{short(a.get('name','?'), 14)} · {T('seen')} {sn} · {T('banned')} {bn} · ld {ln}",
                       f"cache:acc:{aid}")])
    if not accounts: txt += T("empty")
    rows.append([B(T("wipe_all"), "cache:clear_all_accounts")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="cache")

async def show_cache_account(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="cache")
    sn = _seen_count(aid); bn = _banned_count(aid); ln = len(_load_ldprog(aid))
    txt = head("🗂", f"cache · {a.get('name','?')}")
    txt += mrow("🔍", "seen", sn) + "\n"
    txt += mrow("🚫", "banned", bn) + "\n"
    txt += mrow("📡", "ld_progress", ln)
    rows = [
        [B(T("clear_seen"), f"cache:acc:{aid}:clear_seen"),
         B(T("clear_banned"), f"cache:acc:{aid}:clear_banned")],
        [B(T("clear_both"), f"cache:acc:{aid}:clear_all"),
         B(T("reset_ld"), f"cache:acc:{aid}:reset_ld")],
        nav("menu:cache"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"cache:{aid}")


# ═══════════════ PV MENU ═══════════════
async def show_pv_menu():
    accounts = list_accounts()
    txt = head("💬", "pv_auto")
    txt += T("select_account") + "\n\n"
    if not accounts:
        txt += T("pv_no_accounts")
        return await panel(txt, kb_([B(T("add_account"), "acc:add")], nav()), page_tag="pv_menu")
    rows = []
    for aid, a in accounts.items():
        cfg = _load_pv_account(aid)
        en = f"[{T('pv_active') if cfg.get('enabled') else T('pv_inactive')}] "
        items_n = len(cfg.get("items") or [])
        rows.append([B(f"{en}{short(a.get('name','?'), 20)} · {items_n}", f"pv:acc:{aid}")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="pv_menu")

async def show_pv_account_menu(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="pv_menu")
    cfg = _load_pv_account(aid)
    en = bool(cfg.get("enabled"))
    mx = int(cfg.get("max_replies", 1) or 0)
    items = cfg.get("items") or []
    notify_on = bool(cfg.get("notify", True))
    poll_sec = int(cfg.get("poll_seconds", 3))
    delay_sec = int(cfg.get("delay_seconds", 0))
    pv_task = PV_LISTENER_TASKS.get(aid)
    poller_on = bool(pv_task and not pv_task.done())
    has_custom = _has_pv_account(aid)
    txt = head("💬", f"pv · {a.get('name','?')}")
    txt += mrow("📶", "pv_status", (T("pv_active") if en else T("pv_inactive"))) + "\n"
    txt += mrow("🔄", "pv_poller", (T("on") if poller_on else T("off"))) + "\n"
    txt += mrow("👥", "pv_max", (mx if mx else "∞")) + "\n"
    txt += mrow("⏱", "pv_delay", f"{delay_sec}s") + "\n"
    txt += mrow("🔔", "pv_notify", (T("on") if notify_on else T("off"))) + "\n"
    txt += mrow("🔄", "pv_poll", f"{poll_sec}s") + "\n"
    txt += mrow("📨", "pv_items", len(items))
    if has_custom: txt += f"  ({T('pv_custom')})"
    txt += "\n\n"
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"{i}. 💬 <code>{esc(short(it.get('text',''), 40))}</code>\n"
        elif k == "file": txt += f"{i}. 📁 <code>{esc(os.path.basename(it.get('file_path','?')))}</code>\n"
        elif k == "fwd_saved": txt += f"{i}. 📨 mid={it.get('message_id','?')}\n"
        elif k == "delay": txt += f"{i}. ⏸ {it.get('seconds', 3)}s\n"
    rows = [
        [B(T("toggle_off") if en else T("toggle_on"), f"pv:acc:{aid}:toggle")],
        [B(f"{T('pv_max')}: {mx if mx else '∞'}", f"pv:acc:{aid}:cycle_max"),
         B(T("pv_delay"), f"pv:acc:{aid}:set_delay")],
        [B(T("pv_add_text"), f"pv:acc:{aid}:add_text"),
         B(T("pv_add_file"), f"pv:acc:{aid}:add_saved"),
         B(T("pv_add_delay"), f"pv:acc:{aid}:add_delay")],
        [B(T("pv_list"), f"pv:acc:{aid}:list"),
         B(T("pv_report"), f"pv:acc:{aid}:report:0")],
        [B(f"{T('pv_notify')} {'✓' if notify_on else '✗'}", f"pv:acc:{aid}:toggle_notify"),
         B(f"{T('pv_poll')} {poll_sec}s", f"pv:acc:{aid}:set_poll")],
        [B(T("pv_reset_counter"), f"pv:acc:{aid}:clear_replies"),
         B(T("pv_reset_custom"), f"pv:acc:{aid}:reset_to_global")],
        [B(T("pv_restart"), f"pv:acc:{aid}:restart")],
        nav("menu:pv"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"pv_acc:{aid}")

async def show_pv_account_list(aid):
    cfg = _load_pv_account(aid); items = cfg.get("items") or []
    a = get_account(aid)
    txt = head("📋", f"pv · {a.get('name','?') if a else aid}")
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"\n{i}. 💬 <code>{esc(short(it.get('text',''), 60))}</code>"
        elif k == "file": txt += f"\n{i}. 📁 <code>{esc(os.path.basename(it.get('file_path','?')))}</code>"
        elif k == "fwd_saved": txt += f"\n{i}. 📨 <code>{it.get('message_id','?')}</code>"
        elif k == "delay": txt += f"\n{i}. ⏸ {it.get('seconds',3)}s"
    rows = [[B(f"{T('delete')} {i+1}", f"pv:acc:{aid}:del:{i}")] for i in range(len(items))]
    rows.append([B(f"« {T('back')}", f"pv:acc:{aid}")])
    await panel(txt, kb_(*rows), page_tag=f"pv_list:{aid}")

async def show_pv_account_report(aid, page=0):
    rep = _load_pv_report(); users = rep.get(aid) or {}
    rows_data = [{"uid": uid, "first_name": d.get("first_name") or "",
                  "count": d.get("count",1), "replied": d.get("replied",False),
                  "reply_ok": d.get("reply_ok",False), "blocked": d.get("blocked",False),
                  "error": d.get("error"), "last_seen": d.get("last_seen",0)}
                 for uid, d in users.items()]
    rows_data.sort(key=lambda x: x["last_seen"], reverse=True)
    PER = 8; pages = max(1, -(-len(rows_data) // PER)); page = max(0, min(page, pages-1))
    chunk = rows_data[page*PER:(page+1)*PER]
    a = get_account(aid)
    txt = head("📊", f"pv_report · {a.get('name','?') if a else aid}")
    txt += mrow("👥", "pv_total", len(rows_data)) + f"   ·   {T('pv_page')} {page+1}/{pages}\n\n"
    for r in chunk:
        name = r["first_name"] or "?"
        st = "✓" if r["replied"] and r["reply_ok"] else ("✗" if r["replied"] else "·")
        if r["blocked"]: st += "!"
        ago = int(time.time() - r["last_seen"])
        txt += f"{st} <b>{esc(short(name,20))}</b> · x{r['count']} · {_eta(ago)}\n"
        if r.get("error"): txt += f"   <code>{esc(short(r['error'], 50))}</code>\n"
    nav_btns = []
    if pages > 1:
        pr = []
        if page > 0: pr.append(B(T("prev"), f"pv:acc:{aid}:report:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B(T("next"), f"pv:acc:{aid}:report:{page+1}"))
        nav_btns.append(pr)
    nav_btns.append([B(f"« {T('back')}", f"pv:acc:{aid}")])
    await panel(txt, kb_(*nav_btns), page_tag=f"pv_rep:{aid}:{page}")


# ═══════════════ ACCOUNTS ═══════════════
def _accounts_view(page):
    accounts = list_accounts(); items = list(accounts.items())
    pages = max(1, -(-len(items) // PAGE_SIZE)); page = max(0, min(page, pages-1))
    chunk = items[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    rows = []
    for aid, a in chunk:
        cfg = _load_pv_account(aid)
        pv = "✓" if cfg.get("enabled") else "·"
        st = _STATS_CACHE.get(aid, {}).get("data") or {}
        rows.append([B(f"{short(a.get('name','?'), 14)} · pv {pv} · 👥 {st.get('groups','…')}",
                       f"acc:view:{aid}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B(T("prev"), f"acc:page:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B(T("next"), f"acc:page:{page+1}"))
        rows.append(pr)
    rows.append([B(f"+ {T('add_account')}", "acc:add")])
    rows.append(nav())
    txt = head("👤", "accounts_n", len(accounts))
    return txt, kb_(*rows), f"acc_list:{page}", chunk

async def show_accounts(page=0):
    txt, kb, tag, chunk = _accounts_view(page)
    await panel(txt, kb, page_tag=tag)
    if chunk:
        stale = any(aid not in _STATS_CACHE or (time.time() - _STATS_CACHE[aid].get("ts",0)) > 120
                    for aid, _ in chunk)
        if stale: asyncio.create_task(_bg_fetch_stats(page, tag))

async def _bg_fetch_stats(page, tag):
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
    tag = f"acc:{aid}"; a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    t = LISTENER_TASKS.get(aid); on = bool(t and not t.done())
    pvt = PV_LISTENER_TASKS.get(aid); pvon = bool(pvt and not pvt.done())
    pvc = _load_pv_account(aid)
    st = _STATS_CACHE.get(aid, {}).get("data") or {}
    g = lambda k: st.get(k, "…")
    txt = head("👤", a.get("name", "?"))
    txt += mrow("📞", "phone", f"<code>{esc(a.get('phone','—'))}</code>") + "\n"
    txt += mrow("👥", "groups", g('groups')) + "\n"
    txt += mrow("💬", "pvs", g('pvs')) + "\n"
    txt += mrow("📢", "channels", g('channels')) + "\n"
    txt += mrow("✨", "channels_created", len(get_stored_channels(aid))) + "\n"
    txt += mrow("👂", "listener_status", (T("on") if on else T("off"))) + "\n"
    txt += mrow("💬", "pv", (T("on") if pvon else T("off"))) + "\n"
    txt += mrow("🔍", "seen", _seen_count(aid)) + "\n"
    txt += mrow("🚫", "banned", _banned_count(aid))
    rows = grid([
        B(T("auto_tar"), f"acc:at:{aid}"), B(T("channels"), f"ch:menu:{aid}"),
        B(T("profile"), f"prof:menu:{aid}"),
        B((T("toggle_off") if on else T("toggle_on")) + " " + T("listener"), f"listen:toggle:{aid}"),
        B(T("pv"), f"pv:acc:{aid}"), B(T("photo"), f"accphoto:menu:{aid}"),
        B(T("lefter"), f"acc:lf:{aid}"), B(T("cache"), f"cache:acc:{aid}"),
    ])
    rows.append([B(T("delete_account"), f"acc:del:{aid}")])
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


# ═══════════════ PROFILES ═══════════════
async def show_profile_menu(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    rows = grid([
        B(T("name"), f"prof:set:first:{aid}"), B(T("last_name"), f"prof:set:last:{aid}"),
        B(T("bio"), f"prof:set:about:{aid}"), B(T("username"), f"prof:set:username:{aid}"),
        B(T("photo"), f"accphoto:menu:{aid}"),
    ])
    rows.append(nav(f"acc:view:{aid}"))
    txt = head("✏️", "profile", a.get("name","?"))
    txt += mrow("📞", "phone", f"<code>{esc(a.get('phone','—'))}</code>")
    await panel(txt, kb_(*rows), page_tag=f"prof:{aid}")

async def show_acc_photo_menu(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    rows = [
        [B(T("prof_set_photo"), f"accphoto:set:{aid}")],
        [B(T("prof_del_photo"), f"accphoto:del:{aid}")],
        nav(f"acc:view:{aid}"),
    ]
    await panel(head("🖼", "prof_photo_menu", a.get("name","?")), kb_(*rows), page_tag=f"accphoto:{aid}")

async def show_ch_photo_menu(aid, idx):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    chs = get_stored_channels(aid)
    if idx < 0 or idx >= len(chs): return await show_ch_list(aid)
    ch = chs[idx]
    rows = [
        [B(T("prof_set_photo"), f"chphoto:set:{aid}:{idx}")],
        [B(T("prof_del_photo"), f"chphoto:del:{aid}:{idx}")],
        nav(f"ch:view:{aid}:{idx}"),
    ]
    await panel(head("🖼", "ch_photo_menu", ch.get("title","?")), kb_(*rows), page_tag=f"chphoto:{aid}:{idx}")

def _ch_link(ch):
    un = (ch.get("username") or "").lstrip("@")
    return ch.get("join_link") or (f"https://splus.ir/{un}" if un else "")


# ═══════════════ CHANNELS ═══════════════
async def show_ch_menu(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    n = len(get_stored_channels(aid))
    txt = head("📢", "channels", a.get("name","?"))
    txt += mrow("✨", "channels_created", n)
    rows = [[B(f"{T('my_channels')} ({n})", f"chlist:show:{aid}:0")],
            [B(T("create_channel"), f"chnew:start:{aid}")],
            nav(f"acc:view:{aid}")]
    await panel(txt, kb_(*rows), page_tag=f"ch_menu:{aid}")

async def show_ch_list(aid, page=0):
    channels = get_stored_channels(aid); per = 6
    pages = max(1, -(-len(channels) // per)); page = max(0, min(page, pages-1))
    rows = []
    for idx, ch in list(enumerate(channels))[page*per:(page+1)*per]:
        icon = "pub" if (ch.get("type") == "public" or ch.get("username")) else "prv"
        lbl = f"[{icon}] {short(ch.get('title','?'), 24)}"
        if ch.get("username"): lbl += f" · @{ch['username']}"
        rows.append([B(lbl, f"ch:view:{aid}:{idx}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B(T("prev"), f"chlist:show:{aid}:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B(T("next"), f"chlist:show:{aid}:{page+1}"))
        rows.append(pr)
    rows.append([B(T("create_channel"), f"chnew:start:{aid}")])
    rows.append(nav(f"ch:menu:{aid}"))
    txt = head("📋", "my_channels", len(channels))
    if not channels: txt += T("ch_no_channels")
    await panel(txt, kb_(*rows), page_tag=f"chlist:{aid}:{page}")

async def show_channel_view(aid, idx):
    if not get_account(aid): return await panel(T("not_found"), kb_(nav()), page_tag="main")
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return await show_ch_list(aid)
    ch = channels[idx]
    un = ch.get("username") or ""
    is_pub = ch.get("type") == "public" or bool(un)
    link = _ch_link(ch)
    txt = head("📢", ch.get("title") or "?")
    txt += mrow("🔖", "type", (T("public") if is_pub else T("private"))) + "\n"
    if un: txt += mrow("🔤", "username", f"@{esc(un)}") + "\n"
    txt += mrow("🔗", "link", (f"<code>{esc(link)}</code>" if link else "—"))
    rows = grid([
        B(T("send"), f"chsend:start:{aid}:{idx}"), B(T("profile"), f"chprof:show:{aid}:{idx}"),
        B(T("get_link"), f"ch:getlink:{aid}:{idx}"), B(T("set_link"), f"ch:setlink:{aid}:{idx}"),
        B(T("photo"), f"chphoto:menu:{aid}:{idx}"), B(T("file"), f"chfile:start:{aid}:{idx}"),
        B(T("delete"), f"ch:del:{aid}:{idx}"),
    ])
    rows.append(nav(f"chlist:show:{aid}:0"))
    await panel(txt, kb_(*rows), page_tag=f"chview:{aid}:{idx}")

async def show_ch_profile(aid, idx):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    channels = get_stored_channels(aid)
    if idx < 0 or idx >= len(channels): return await show_ch_list(aid)
    ch = channels[idx]
    un = ch.get("username") or ""
    txt = head("✏️", ch.get("title") or "?")
    txt += mrow("🔖", "type", (T("public") if (ch.get("is_public") or un) else T("private"))) + "\n"
    if un: txt += mrow("🔤", "username", f"@{esc(un)}") + "\n"
    link = _ch_link(ch)
    txt += mrow("🔗", "link", (f"<code>{esc(link)}</code>" if link else "—")) + "\n"
    txt += mrow("📖", "description", f"<code>{esc(short(ch.get('description',''), 100) or '—')}</code>")
    rows = [
        [B(T("channel_title"), f"chprof:edit:title:{aid}:{idx}"),
         B(T("description"), f"chprof:edit:desc:{aid}:{idx}")],
        [B(T("username"), f"chprof:edit:user:{aid}:{idx}"),
         B(T("photo"), f"chphoto:menu:{aid}:{idx}")],
        [B(T("get_link"), f"ch:getlink:{aid}:{idx}")],
        nav(f"ch:view:{aid}:{idx}"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"chprof:{aid}:{idx}")

async def show_ch_new_type(aid, title):
    txt = head("🏗", "create_channel") + mrow("📝", "channel_title", title) + "\n\n" + T("ch_new_type")
    await panel(txt, kb_(
        [B(T("public"), f"chnew:pub:{aid}"), B(T("private"), f"chnew:priv:{aid}")],
        [B(f"« {T('cancel')}", f"ch:menu:{aid}")]), page_tag=f"chnew_type:{aid}")


# ═══════════════ LISTENER MENU ═══════════════
async def show_listen_menu():
    accounts = list_accounts()
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    enabled = bool(int(cfg.get("listener", 1)))
    txt = head("👂", "listener")
    txt += mrow("📶", "pv_status", (T("on") if enabled else T("off"))) + "\n\n"
    rows = []
    for aid, a in accounts.items():
        t = LISTENER_TASKS.get(aid); run = t is not None and not t.done()
        rows.append([B(f"[{'✓' if run else ' '}] {short(a.get('name','?'), 14)}",
                       f"listen:toggle:{aid}")])
    rows.append([B(T("listener_restart_all"), "listen:restart")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="listen")


# ═══════════════ LINKDONIES ═══════════════
async def show_linkdonies(back_to="jl:back_to_settings"):
    lst = load_link_donies()
    auto = int(_load(CFG_FILE, DEFAULT_CFG).get("auto_join_linkdoni", 1))
    txt = head("📡", "linkdonies", len(lst))
    txt += mrow("🔁", "ld_auto_join", (T("on") if auto else T("off"))) + "\n"
    txt += T("ld_progress_per_acc") + "\n\n"
    for i, url in enumerate(lst):
        txt += f"{i+1}. <code>{esc(url)}</code>\n"
    rows = grid([B(f"{T('delete')} {i+1}. {short(u.split('/')[-1], 12)}", f"ld:del:{i}:{back_to}")
                 for i, u in enumerate(lst)])
    rows.append([B(T("ld_add"), f"ld:add:{back_to}"),
                 B(T("toggle_off") if auto else T("toggle_on"), f"ld:toggle_autojoin:{back_to}")])
    rows.append([B(T("ld_reset_prog"), f"ld:reset_prog:{back_to}")])
    rows.append([B(T("ld_reset_list"), f"ld:reset:{back_to}")])
    rows.append(nav(back_to, home=False))
    await panel(txt, kb_(*rows), page_tag="linkdonies")


# ═══════════════ OP PANEL ═══════════════
_OP_LAST: Dict[str, float] = {}
def _op_view(op):
    oid = op["id"]; t = op.get("type")
    st = _op_effective_status(op); s = _op_stats(op); p = op.get("progress") or {}
    tot = s["total"] or 0; proc = s["done"] + s["failed"]
    pct = min(100, int(proc * 100 / tot)) if tot else 0
    icon = {"joinlef": "🤝", "lefter": "🚪", "autotar": "🎯", "send": "📤"}.get(t, "⚙️")
    label = {"joinlef": "op_joiner", "lefter": "op_lefter",
             "autotar": "op_autotar", "send": "op_send"}.get(t, "op")
    txt = head(icon, label, oid[-6:])
    txt += f"{T('op_' + st)}\n"
    txt += f"<code>{_bar(pct)} {pct}%</code>\n\n"
    if t in ("joinlef", "autotar"):
        txt += f"🤝 {T('op_joined')}: <b>{s['done']}</b>   ✗ {T('op_failed_c')}: <b>{s['failed']}</b>"
        if op.get("max_join"): txt += f"   🎯 {op['max_join']}"
        if s.get("already"): txt += f"\n♻️ {T('op_already')}: <b>{s['already']}</b>"
        if s.get("sent"):    txt += f"\n📤 {T('op_sent')}: <b>{s['sent']}</b>"
        if s.get("left"):    txt += f"\n🚪 {T('op_left')}: <b>{s['left']}</b>"
        if s.get("tried"):   txt += f"\n🔗 {T('op_tried')}: <b>{s['tried']}</b>"
        if s.get("skipped_seen"):   txt += f"\n🔍 {T('op_skipped_seen')}: <b>{s['skipped_seen']}</b>"
        if s.get("skipped_banned"): txt += f"\n🚫 {T('op_skipped_banned')}: <b>{s['skipped_banned']}</b>"
        if s.get("rejected"): txt += f"\n🟡 {T('op_rejected')}: <b>{s['rejected']}</b>"
        if s.get("wave"):  txt += f"\n🌊 {T('op_wave')}: <b>{s['wave']}</b>"
        if s.get("round"): txt += f"   ·   🔁 {T('op_round')}: <b>{s['round']}</b>"
    elif t == "lefter":
        txt += f"🚪 {T('op_left')}: <b>{s['done']}</b>   ✗ {T('op_failed_c')}: <b>{s['failed']}</b>"
    else:
        txt += f"✓ {T('op_sent')}: <b>{s['done']}</b>   ✗ {T('op_failed_c')}: <b>{s['failed']}</b>   ⏳ {s['pending']}"
        if s.get("blocked"): txt += f"\n🚫 {T('op_blocked')}: {s['blocked']}"
        if s.get("round"):   txt += f"   ·   🔁 {T('op_round')}: {s['round']}"
    txt += f"\n\n{SC(T('op_phase'))} : {p.get('phase','—')}"
    rows = []
    if st == "running": rows.append([B(T("stop"), f"op:stop:{oid}")])
    rows.append([B(f"« {T('stats')}", "menu:stats"), B(T("back_to_panel"), "menu:main")])
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
    if not op: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    cid = STATE.get("owner")
    if cid: STATE.setdefault("op_panel", {})[cid] = oid
    txt, kb = _op_view(op)
    await panel(txt, kb, page_tag=f"op:{oid}")


# ═══════════════ STATS / ERRORS ═══════════════
async def show_stats():
    ops = _load_ops(); ops.sort(key=lambda o: o.get("created", 0), reverse=True)
    errs = _load_errors()
    done = sum(_op_stats(o)["done"] for o in ops)
    failed = sum(_op_stats(o)["failed"] for o in ops)
    running = [o for o in ops if _op_effective_status(o) == "running"]
    txt = head("📊", "stats_title")
    txt += mrow("✓", "stats_done", done) + "\n"
    txt += mrow("✗", "stats_failed", failed) + "\n"
    txt += mrow("⚠️", "stats_errors", len(errs))
    if running:
        txt += f"\n\n{SC(T('stats_running'))}:\n"
        for o in running[:3]:
            s = _op_stats(o)
            txt += f"• {short(o.get('id','?'), 12)}  ✓{s['done']} ✗{s['failed']}\n"
    rows = []
    for o in ops[:8]:
        s = _op_stats(o); prog = f"{s['done']}/{s['total']}" if s["total"] else "—"
        rows.append([B(f"{o.get('type','?')} · {prog}", f"op:view:{o['id']}")])
    rows.append([B(T("errors"), "menu:errors"), B(T("back_to_panel"), "menu:main")])
    await panel(txt, kb_(*rows), page_tag="stats")

async def show_errors(page=0):
    errors = list(reversed(_load_errors()))
    if not errors:
        return await panel(head("⚠️", "errors") + T("errors_none"), kb_(nav()), page_tag="errors")
    PER = 4; pages = max(1, -(-len(errors) // PER)); page = max(0, min(page, pages-1))
    txt = head("⚠️", "errors", len(errors))
    for e in errors[page*PER:(page+1)*PER]:
        t = time.strftime("%m/%d %H:%M", time.localtime(e.get("time", 0)))
        txt += f"\n🕐 <code>{esc(t)}</code> · <b>{esc(e.get('source','?'))}</b>\n"
        txt += f"<code>{esc(str(e.get('error',''))[:220])}</code>\n"
    rows = []
    if pages > 1:
        pr = []
        if page > 0: pr.append(B(T("prev"), f"err:page:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B(T("next"), f"err:page:{page+1}"))
        rows.append(pr)
    rows.append([B(T("clear"), "err:clear"), B(T("back_to_panel"), "menu:main")])
    await panel(txt, kb_(*rows), page_tag=f"errors:{page}")


# ═══════════════ SETTINGS ═══════════════
async def show_cfg():
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    lang = _get_lang()
    txt = head("⚙️", "cfg_title")
    txt += mrow("🌐", "cfg_lang", (T("cfg_lang_fa") if lang == "fa" else T("cfg_lang_en"))) + "\n"
    txt += mrow("⏱", "cfg_join_delay", cfg.get("join_delay", DEFAULT_CFG["join_delay"])) + "\n"
    txt += mrow("🌊", "cfg_wave_size", cfg.get("wave_size", DEFAULT_CFG["wave_size"])) + "\n"
    txt += mrow("📦", "cfg_extract", cfg.get("extract_limit", DEFAULT_CFG["extract_limit"])) + "\n"
    txt += mrow("⏸", "cfg_wait", cfg.get("wait_for_links_sec", DEFAULT_CFG["wait_for_links_sec"])) + "\n"
    auto = int(cfg.get("auto_join_linkdoni", 1))
    txt += mrow("🔁", "cfg_auto_join", (T("on") if auto else T("off"))) + "\n"
    lst = int(cfg.get("listener", 1))
    txt += mrow("👂", "cfg_listener", (T("on") if lst else T("off")))
    rows = [
        [B(f"{T('cfg_lang')}: {'🇮🇷 ' + T('cfg_lang_fa') if lang=='fa' else '🇬🇧 ' + T('cfg_lang_en')}",
           "cfg:lang")],
        [B(T("cfg_join_delay"), "cfg:set:join_delay"),
         B(T("cfg_wave_size"), "cfg:set:wave_size")],
        [B(T("cfg_extract"), "cfg:set:extract_limit"),
         B(T("cfg_wait"), "cfg:set:wait_for_links_sec")],
        [B((T("toggle_off") if auto else T("toggle_on")) + " " + T("cfg_auto_join"), "cfg:toggle_autojoin")],
        [B((T("toggle_off") if lst else T("toggle_on")) + " " + T("cfg_listener"), "cfg:toggle_listener")],
        nav(),
    ]
    await panel(txt, kb_(*rows), page_tag="cfg")


# ═══════════════ SEND WIZARD ═══════════════
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
    if "all" in accs: al = f"{T('all')} ({len(all_a)})"
    elif not accs: al = "—"
    else:
        names = [get_account(i).get("name","?") for i in accs[:2] if get_account(i)]
        al = ", ".join(names) + (f" +{len(accs)-2}" if len(accs) > 2 else "")
    p = s.get("payload")
    tgt = {"pv": T("send_target_pv"), "groups": T("send_target_gr"),
           "both": T("send_target_both")}.get(s.get("target","both"), "?")
    mx = s.get("max", 0) or 0
    ed = T("on") if s.get("edit_delay_enabled") else T("off")
    af = T("yes_short") if s.get("attach_file") else T("no_short")
    inf = T("on") if s.get("infinite_loop") else T("off")
    return ("\n" + mrow("👤", "accounts_n", al) + "\n"
            + mrow("✉️", "text", (f"«{short(p.get('text'), 30)}»" if p else "—")) + "\n"
            + mrow("🎯", "target", tgt) + "\n"
            + mrow("🔢", "max", (mx if mx else "∞")) + "\n"
            + mrow("🎭", "send_edit", ed) + "\n"
            + mrow("📎", "send_attach", af) + "\n"
            + mrow("🔁", "send_infinite", inf))

async def send_step_accounts(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel(T("jl_no_account"), kb_([B(f"+ {T('add_account')}", "acc:add")], nav()), page_tag="send:1")
    sel = set(s.get("accounts") or []); all_sel = "all" in sel
    btns = [B(SEL((all_sel or aid in sel), short(a.get('name','?'), 14)), f"send:acc:{aid}")
            for aid, a in accounts.items()]
    rows = grid(btns)
    rows.append([B(T("all") if not all_sel else T("cancel"), "send:accall"),
                 B(T("next"), "send:accnext")])
    rows.append([B(f"« {T('cancel')}", "send:cancel")])
    txt = head("📤", "send", dots(1, 4)) + T("send_step1") + _send_summary(s)
    await panel(txt, kb_(*rows), page_tag="send:1")

async def send_step_compose(cid, s):
    txt = head("📤", "send", dots(2, 4)) + T("send_step2") + _send_summary(s)
    rows = []
    if s.get("payload"): rows.append([B(T("send_custom"), "send:recompose"), B(T("next"), "send:composenext")])
    rows.append([B(f"« {T('prev')}", "send:prev"), B(T("cancel"), "send:cancel")])
    await panel(txt, kb_(*rows), page_tag="send:2")

async def send_step_target(cid, s):
    t = s.get("target", "both")
    mk = lambda k, l: B(SEL(t == k, l), f"send:tgt:{k}")
    ed_on = bool(s.get("edit_delay_enabled", False))
    ed_sec = s.get("edit_delay_seconds", 3.0)
    grp_only = bool(s.get("groups_only", True))
    inf_on = bool(s.get("infinite_loop", False))
    ld = s.get("loop_delay", 3.0)
    rs = bool(s.get("rescan_targets", True))
    af = s.get("attach_file") or ""
    rows = [[mk("pv", T("send_target_pv")), mk("groups", T("send_target_gr")),
             mk("both", T("send_target_both"))],
            [B(SEL(grp_only, T("send_grp_only")), "send:toggle_groups_only")],
            [B(SEL(inf_on, T("send_infinite")), "send:toggle_infinite")],
            [B(f"{T('send_loop_delay')}: {ld}s", "send:loop_delay")],
            [B(SEL(rs, T("send_rescan")), "send:toggle_rescan")],
            [B(SEL(ed_on, T("send_edit")), "send:toggle_edit")],
            [B(f"{ed_sec}s", "send:edit_sec"),
             B(SEL(s.get("edit_delay_random"), T("send_random")), "send:toggle_edit_rand")],
            [B(f"PH: {short(s.get('placeholder_text','hi'), 10)}", "send:edit_ph"),
             B(SEL(s.get("placeholder_random"), T("send_ph_list")), "send:toggle_ph_rand")],
            [B(SEL(s.get("multi_step_edit"), T("send_multi")), "send:toggle_multi")],
            [B(f"{T('send_attach')}: {short(os.path.basename(af), 15) if af else '—'}", "send:attach")],
            [B(SEL(s.get("auto_left"), T("send_auto_left")), "send:toggle_auto_left")],
            [B(T("next"), "send:tgtnext")],
            [B(f"« {T('back')}", "send:prev"), B(T("cancel"), "send:cancel")]]
    txt = head("📤", "send", dots(3, 4)) + T("send_step3") + _send_summary(s)
    await panel(txt, kb_(*rows), page_tag="send:3")

async def send_step_max(cid, s):
    mx = s.get("max", 0)
    mk = lambda n: B(SEL(mx == n, str(n)), f"send:max:{n}")
    rows = [[mk(50), mk(100), mk(500)],
            [mk(1000), mk(2000), mk(5000)],
            [B(SEL(mx == 0, T("send_unlimited")), "send:max:0"),
             B(T("send_custom"), "send:max:custom")],
            [B(T("next"), "send:maxnext")],
            [B(f"« {T('back')}", "send:prev"), B(T("cancel"), "send:cancel")]]
    txt = head("📤", "send", dots(4, 4)) + T("send_step4") + _send_summary(s)
    await panel(txt, kb_(*rows), page_tag="send:4")

async def send_step_confirm(cid, s):
    accounts = list_accounts(); sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "accounts"; return await panel(T("empty"), kb_(nav()), page_tag="send:1")
    if not s.get("payload"):
        s["step"] = "compose"; return await panel(T("empty"), kb_(nav()), page_tag="send:2")
    extra = ""
    if s.get("infinite_loop"):
        extra = "\n" + mrow("🔁", "send_infinite", f"{T('on')} · {s.get('loop_delay',3)}s")
    txt = head("📤", "confirm") + _send_summary(s) + extra
    await panel(txt, kb_(
        [B(T("start"), "send:go")],
        [B(T("send_custom"), "send:back_edit"), B(T("cancel"), "send:cancel")]),
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
        c["jl"] = {"step":"account", "accounts":[], "max_join":0, "speed":"fast", "groups_only":True}
    return c["jl"]

async def jl_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel(T("jl_no_account"), kb_([B(f"+ {T('add_account')}", "acc:add")], nav()), page_tag="jl:1")
    sel = set(s.get("accounts") or [])
    rows = grid([B(SEL(aid in sel, short(a.get('name','?'), 14)), f"jl:acc:{aid}")
                 for aid, a in accounts.items()])
    rows.append([B(T("next"), "jl:next")])
    rows.append([B(T("back_to_panel"), "menu:main")])
    txt = head("🤝", "jl_title", dots(1, 3)) + mrow("👤", "jl_selected", len(sel))
    await panel(txt, kb_(*rows), page_tag="jl:1")

async def jl_step_settings(cid, s):
    speed = s.get("speed", "fast"); lds = load_link_donies()
    lbl = {"ultra": T("jl_speed_ultra"), "fast": T("jl_speed_fast"),
           "normal": T("jl_speed_normal"), "slow": T("jl_speed_safe")}.get(speed, "—")
    grp = T("on") if s.get("groups_only", True) else T("off")
    txt = head("🤝", "jl_title", dots(2, 3))
    txt += mrow("🚀", "jl_speed", lbl) + "\n"
    txt += mrow("📡", "jl_ld", len(lds)) + "\n"
    txt += mrow("👥", "jl_grp_only", grp)
    rows = grid([B(SEL(speed == k, T(f"jl_speed_{k}")), f"jl:speed:{k}")
                 for k, _, _ in JL_SPEEDS])
    rows.append([B(f"{T('jl_ld')} ({len(lds)})", "jl:linkdonies")])
    rows.append([B(SEL(s.get("groups_only", True), T("jl_grp_only")), "jl:toggle_groups_only")])
    rows.append([B(T("next"), "jl:next")])
    rows.append(nav("jl:back"))
    await panel(txt, kb_(*rows), page_tag="jl:2")

async def jl_step_max(cid, s):
    mx = s.get("max_join", 0)
    mk = lambda n: B(SEL(mx == n, str(n)), f"jl:max:{n}")
    txt = head("🤝", "jl_title", dots(3, 3)) + mrow("🎯", "jl_max", (mx if mx else T("send_unlimited")))
    rows = [[mk(50), mk(100), mk(200)],
            [mk(500), mk(1000), mk(2000)],
            [B(T("send_custom"), "jl:max:custom")]]
    if mx: rows.append([B(T("start"), "jl:go")])
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
    if "lf" not in c: c["lf"] = {"step":"account", "accounts":[], "mode":"all", "delay":0.8}
    return c["lf"]

def _lf_modes():
    return [("all", T("lf_mode_all")), ("groups", T("lf_mode_groups")),
            ("channels", T("lf_mode_channels")), ("closed", T("lf_mode_closed"))]

async def lf_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel(T("jl_no_account"), kb_([B(f"+ {T('add_account')}", "acc:add")], nav()), page_tag="lf:1")
    sel = set(s.get("accounts") or [])
    rows = grid([B(SEL(aid in sel, short(a.get('name','?'), 14)), f"lf:acc:{aid}")
                 for aid, a in accounts.items()])
    rows.append([B(T("next"), "lf:next")])
    rows.append([B(T("back_to_panel"), "menu:main")])
    txt = head("🚪", "lf_title", dots(1, 3)) + mrow("👤", "jl_selected", len(sel))
    await panel(txt, kb_(*rows), page_tag="lf:1")

async def lf_step_mode(cid, s):
    mode = s.get("mode", "all"); modes = _lf_modes()
    btns = [B(SEL(mode == k, l), f"lf:mode:{k}") for k, l in modes]
    rows = [[b] for b in btns]
    rows.append([B(T("next"), "lf:next")])
    rows.append(nav("lf:back"))
    txt = head("🚪", "lf_title", dots(2, 3)) + SC(T("lf_mode"))
    await panel(txt, kb_(*rows), page_tag="lf:2")

async def lf_step_delay(cid, s):
    d = s.get("delay", 0.8)
    mk = lambda n, l: B(SEL(abs(d - n) < 0.01, l), f"lf:delay:{n}")
    txt = head("🚪", "lf_title", dots(3, 3)) + mrow("⏱", "lf_delay", f"{d}s")
    rows = [[mk(0.3, "0.3s"), mk(0.8, "0.8s"), mk(1.5, "1.5s")],
            [mk(3.0, "3s")],
            [B(T("start"), "lf:go")],
            nav("lf:back")]
    await panel(txt, kb_(*rows), page_tag="lf:3")

async def show_lf_step(cid):
    s = _lf_conv(cid)
    if s["step"] == "account": await lf_step_account(cid, s)
    if s["step"] == "mode":    await lf_step_mode(cid, s)
    if s["step"] == "delay":   await lf_step_delay(cid, s)


# ═══════════════ TEMPLATES UI ═══════════════
async def show_at_menu():
    tpls = list_templates()
    txt = head("🎯", "at_title", len(tpls))
    txt += T("at_desc") + "\n"
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
    rows.append([B(T("at_new"), "at:new")])
    rows.append(nav())
    await panel(txt, kb_(*rows), page_tag="at:menu")

async def show_at_view(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    ch = t.get("channel", {}); pr = t.get("profile", {})
    jn = t.get("joiner", {}); sn = t.get("sender", {})
    lf = t.get("lefter", {}); pv = t.get("pv", {})
    def badge(d, key): return T("on") if d.get(key) else T("off")
    def badge_n(d, key): return T("on") if int(d.get(key, 0) or 0) > 0 else T("off")
    txt = head("🎯", t.get("name", "?"))
    txt += mrow("🏗", "at_channel", badge(ch, "title"))
    if ch.get("title"): txt += f" ({esc(short(ch['title'],20))})"
    txt += "\n"
    txt += mrow("✏️", "at_profile",
                (badge(pr, "first_name") if pr.get("first_name")
                 else badge(pr, "bio") if pr.get("bio") else badge(pr, "username"))) + "\n"
    txt += mrow("🤝", "at_joiner", badge_n(jn, "max_join"))
    if int(jn.get("max_join", 0) or 0) > 0: txt += f" ({jn['max_join']})"
    txt += "\n"
    txt += mrow("📤", "at_sender", badge(sn, "text")) + "\n"
    txt += mrow("💬", "at_pv",
                (badge(pv, "enabled") + f" · {len(pv.get('items') or [])}")) + "\n"
    txt += mrow("🚪", "at_lefter", lf.get("leave_mode", "?"))
    rows = grid([
        B(T("at_channel"), f"at:{tid}:ch"), B(T("at_profile"), f"at:{tid}:pr"),
        B(T("at_joiner"), f"at:{tid}:jn"), B(T("at_sender"), f"at:{tid}:sn"),
        B(T("at_pv"), f"at:{tid}:pv"), B(T("at_lefter"), f"at:{tid}:lf"),
        B(T("at_rename"), f"at:{tid}:rename"),
    ])
    rows.append([B(T("at_run"), f"at:{tid}:run")])
    rows.append([B(T("at_delete"), f"at:{tid}:del"), B(T("back_to_panel"), "menu:main")])
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:view")

async def show_at_channel(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    c = t.get("channel", {})
    is_pub = c.get("type", "private") == "public"
    txt = head("🏗", "at_channel", t.get("name", "?"))
    txt += mrow("🔖", "type", (T("public") if is_pub else T("private"))) + "\n"
    txt += mrow("📝", "channel_title", c.get("title") or "—") + "\n"
    if is_pub: txt += mrow("🔤", "username", c.get("username") or "—") + "\n"
    txt += mrow("📖", "about", short(c.get("about", ""), 40) or "—") + "\n"
    txt += mrow("🖼", "photo", os.path.basename(c.get("photo_file", "")) or "—") + "\n"
    txt += "\n" + SC("vars") + ": <code>{n} {rnd} {Link_private}</code>"
    rows = [
        [B(SEL(is_pub, T("public")), f"at:{tid}:chtype:public"),
         B(SEL(not is_pub, T("private")), f"at:{tid}:chtype:private")],
        [B(T("channel_title"), f"at:{tid}:chset:title")],
    ]
    if is_pub: rows.append([B(T("username"), f"at:{tid}:chset:username")])
    rows.append([B(T("about"), f"at:{tid}:chset:about")])
    rows.append([B(T("photo"), f"at:{tid}:chset:photo_file")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:ch")

async def show_at_profile(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    p = t.get("profile", {})
    txt = head("✏️", "at_profile", t.get("name", "?"))
    txt += mrow("👤", "name", p.get("first_name") or "—") + "\n"
    txt += mrow("👤", "last_name", p.get("last_name") or "—") + "\n"
    txt += mrow("🔤", "username", p.get("username") or "—") + "\n"
    txt += mrow("📖", "bio", short(p.get("bio", ""), 60) or "—") + "\n"
    txt += mrow("🖼", "photo", os.path.basename(p.get("photo_file", "")) or "—")
    rows = [
        [B(T("name"), f"at:{tid}:prset:first_name"),
         B(T("last_name"), f"at:{tid}:prset:last_name")],
        [B(T("username"), f"at:{tid}:prset:username"),
         B(T("bio"), f"at:{tid}:prset:bio")],
        [B(T("photo"), f"at:{tid}:prset:photo_file")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:pr")

async def show_at_joiner(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    j = t.get("joiner", {})
    spd = j.get("speed")
    spd_lbl = {"ultra": T("jl_speed_ultra"), "fast": T("jl_speed_fast"),
               "normal": T("jl_speed_normal"), "slow": T("jl_speed_safe")}.get(spd, spd)
    txt = head("🤝", "at_joiner", t.get("name", "?"))
    txt += mrow("🎯", "jl_max", j.get("max_join", 0)) + "\n"
    txt += mrow("🚀", "jl_speed", spd_lbl) + "\n"
    txt += mrow("👥", "jl_grp_only", (T("on") if j.get("groups_only", True) else T("off")))
    rows = [[B(T("jl_max"), f"at:{tid}:jnset:max_join")]]
    rows += grid([B(SEL(spd == k, T(f"jl_speed_{k}")), f"at:{tid}:jnspeed:{k}") for k, _, _ in JL_SPEEDS])
    rows.append([B(SEL(j.get("groups_only", True), T("jl_grp_only")), f"at:{tid}:jntoggle_groups_only")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:jn")

async def show_at_sender(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    s = t.get("sender", {})
    mode_labels = {"send_only": T("at_mode_only"),
                   "join_send": T("at_mode_js"),
                   "join_send_leave": T("at_mode_jsl")}
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
    txt = head("📤", "at_sender", t.get("name", "?"))
    txt += mrow("✉️", "text", short(s.get("text", ""), 50) or "—") + "\n"
    txt += mrow("🎯", "target", s.get("target", "?")) + "\n"
    txt += mrow("🔁", "mode", mode_labels.get(s.get("mode"), s.get("mode"))) + "\n"
    txt += mrow("🔢", "max", s.get("max_send", 0) or "∞") + "\n"
    txt += mrow("⏱", "delay", f"{s.get('delay', 1.5)}s") + "\n"
    txt += mrow("🎭", "send_edit", (T("on") if ed_on else T("off")))
    if ed_on: txt += (" (random)" if ed_rand else f" {ed_sec}s")
    txt += "\n" + mrow("💬", "placeholder", ph) + "\n"
    txt += mrow("🔁", "send_infinite", (T("on") if inf_on else T("off")))
    if inf_on:
        txt += f"  {ld}s\n" + mrow("🔄", "send_rescan", (T("on") if rs else T("off")))
    txt += "\n" + mrow("📎", "send_attach", os.path.basename(af) if af else "—")
    rows = [
        [B(T("text"), f"at:{tid}:snset:text")],
        [B(T("target"), f"at:{tid}:snset:target"), B(T("max"), f"at:{tid}:snset:max_send")],
        [B(T("delay"), f"at:{tid}:snset:delay"), B(T("mode"), f"at:{tid}:snmode")],
        [B(SEL(inf_on, T("send_infinite")), f"at:{tid}:sntoggle_loop"),
         B(f"{T('send_loop_delay')}: {ld}s", f"at:{tid}:snset_loop_delay")],
        [B(SEL(rs, T("send_rescan")), f"at:{tid}:sntoggle_rescan")],
        [B(SEL(ed_on, T("send_edit")), f"at:{tid}:snedit:toggle")],
        [B(f"{ed_sec}s", f"at:{tid}:snedit:sec"), B("PH", f"at:{tid}:snedit:ph")],
        [B(SEL(ph_rand, T("send_ph_list")), f"at:{tid}:snedit:ph_rand"),
         B(SEL(ms_on, T("send_multi")), f"at:{tid}:snedit:multi_toggle")],
        [B(f"{T('send_attach')}: {short(os.path.basename(af), 15) if af else '—'}", f"at:{tid}:snedit:file")],
        [B(T("at_apply_acc"), f"at:{tid}:snedit:toggle_existing")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:sn")

async def show_at_sender_mode(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    cur = t["sender"].get("mode", "send_only")
    opts = [("send_only", T("at_mode_only")), ("join_send", T("at_mode_js")),
            ("join_send_leave", T("at_mode_jsl"))]
    txt = head("🔁", "mode", cur)
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
    txt = head("💬", "at_pv", t.get("name", "?"))
    txt += mrow("📶", "pv_status", (T("pv_active") if en else T("pv_inactive"))) + "\n"
    txt += mrow("👥", "pv_max", (mx if mx else "∞")) + "\n"
    txt += mrow("⏱", "pv_delay", f"{pv.get('delay_seconds', 0)}s") + "\n"
    txt += mrow("🔄", "at_apply_acc", (T("on") if apply_acc else T("off"))) + "\n"
    txt += mrow("📨", "pv_items", len(items)) + "\n\n"
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"{i}. 💬 <code>{esc(short(it.get('text',''), 40))}</code>\n"
        elif k == "file": txt += f"{i}. 📁 <code>{esc(os.path.basename(it.get('file_path','?')))}</code>\n"
        elif k == "delay": txt += f"{i}. ⏸ {it.get('seconds', 3)}s\n"
    rows = [
        [B(T("toggle_off") if en else T("toggle_on"), f"at:{tid}:pv:toggle")],
        [B(f"{T('pv_max')}: {mx if mx else '∞'}", f"at:{tid}:pv:cycle_max"),
         B(T("pv_delay"), f"at:{tid}:pv:set_delay")],
        [B(T("pv_add_text"), f"at:{tid}:pv:add_text"),
         B(T("pv_add_file"), f"at:{tid}:pv:add_saved"),
         B(T("pv_add_delay"), f"at:{tid}:pv:add_delay")],
        [B(SEL(apply_acc, T("at_apply_acc")), f"at:{tid}:pv:toggle_apply")],
        [B(T("pv_list"), f"at:{tid}:pv:list")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:pv")

async def show_at_pv_list(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    items = (t.get("pv") or {}).get("items") or []
    txt = head("📋", "pv_list", len(items))
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"\n{i}. 💬 <code>{esc(short(it.get('text',''), 60))}</code>"
        elif k == "file": txt += f"\n{i}. 📁 <code>{esc(os.path.basename(it.get('file_path','?')))}</code>"
        elif k == "delay": txt += f"\n{i}. ⏸ {it.get('seconds',3)}s"
    rows = [[B(f"{T('delete')} {i+1}", f"at:{tid}:pv:del:{i}")] for i in range(len(items))]
    rows.append([B(f"« {T('back')}", f"at:{tid}:pv")])
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:pv_list")

async def show_at_lefter(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    l = t.get("lefter", {})
    txt = head("🚪", "at_lefter", t.get("name", "?"))
    txt += mrow("🎯", "lf_mode", l.get("leave_mode", "?"))
    rows = []
    for k, lbl in _lf_modes():
        rows.append([B(SEL(l.get("leave_mode") == k, lbl), f"at:{tid}:lfset:{k}")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:lf")

async def show_at_run(tid, page=0):
    t = get_template(tid)
    if not t: return await show_at_menu()
    accounts = list_accounts(); items = list(accounts.items())
    per = 6; pages = max(1, -(-len(items) // per)); page = max(0, min(page, pages-1))
    chunk = items[page*per:(page+1)*per]
    cid = STATE.get("owner"); conv = get_conv(cid) if cid else {}
    selected = set((conv.get("at_run") or {}).get("accounts") or [])
    rows = []
    for aid, a in chunk:
        rows.append([B(SEL(aid in selected, short(a.get('name','?'), 20)), f"at:{tid}:run_acc:{aid}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B(T("prev"), f"at:{tid}:run:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B(T("next"), f"at:{tid}:run:{page+1}"))
        rows.append(pr)
    rows.append([B(T("start"), f"at:{tid}:run_go")])
    rows.append(nav(f"at:{tid}:view"))
    txt = head("🎯", "at_run_title", t.get("name", "?"))
    txt += mrow("👤", "jl_selected", len(selected))
    await panel(txt, kb_(*rows), page_tag=f"at:{tid}:run:{page}")

async def show_acc_at_menu(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    tpls = list_templates()
    txt = head("🎯", "auto_tar", a.get("name", "?"))
    if not tpls:
        return await panel(txt + "\n\n" + T("empty"),
                           kb_([B(T("at_new"), "at:new"), B(T("back_to_panel"), "menu:main")]),
                           page_tag=f"acc:at:{aid}")
    rows = []
    for tid, t in list(tpls.items())[:10]:
        rows.append([B(short(t.get('name','?'), 22), f"acc:at:run:{aid}:{tid}")])
    rows.append(nav(f"acc:view:{aid}"))
    await panel(txt, kb_(*rows), page_tag=f"acc:at:{aid}")

async def show_acc_lf(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
    txt = head("🚪", "lf_title", a.get("name", "?"))
    rows = []
    for k, lbl in _lf_modes():
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
        await panel(T("loading"), page_tag="login_verify")
        try: res = await soroosh_complete_login(phone, code)
        except Exception as e: res = {"ok": False, "status": _fmt_error(e)}
        clear_conv(cid)
        if res.get("ok"):
            await panel(head("✅", f"{res['name']}") + f"🆔 <code>{esc(res['aid'])}</code>",
                        kb_([B(T("back_to_panel"), "menu:main")]), page_tag="main"); return
        if res.get("need_signup"):
            await panel(T("not_found"), kb_([B(T("back_to_panel"), "menu:main")]), page_tag="main"); return
        await panel(f"✗ <code>{esc(str(res.get('status'))[:400])}</code>",
                    kb_([B(T("back_to_panel"), "menu:main")]), page_tag="main"); return

    if conv.get("pv_acc_wait"):
        w = conv.pop("pv_acc_wait"); aid = w.get("aid"); kind = w.get("kind")
        cfg = _load_pv_account(aid); items = cfg.get("items") or []
        if kind == "delay":
            try: cfg["delay_seconds"] = max(0, int(re.sub(r"[^\d]", "", text) or "0"))
            except: cfg["delay_seconds"] = 0
        elif kind == "poll":
            try: cfg["poll_seconds"] = max(2, int(re.sub(r"[^\d]", "", text) or "3"))
            except: cfg["poll_seconds"] = 3
        elif kind == "add_text":
            items.append({"kind": "text", "text": text}); cfg["items"] = items
        elif kind == "add_delay_sec":
            try: sec = max(0, int(re.sub(r"[^\d]", "", text) or "3"))
            except: sec = 3
            items.append({"kind": "delay", "seconds": sec}); cfg["items"] = items
        _save_pv_account(aid, cfg); await tg_send(T("saved"))
        return await show_pv_account_menu(aid)

    if conv.get("pv_acc_save_msg"):
        w = conv.pop("pv_acc_save_msg"); aid = w.get("aid")
        media = _extract_media(msg); caption = text or ""
        if not media and not caption: return await ask(T("enter"))
        local_path = None
        if media:
            try: local_path = await _download_tg_file(media, "pv", "pvitem")
            except Exception: pass
        cfg = _load_pv_account(aid); items = cfg.get("items") or []
        if local_path: items.append({"kind": "file", "file_path": local_path, "caption": caption})
        else: items.append({"kind": "text", "text": caption})
        cfg["items"] = items; _save_pv_account(aid, cfg); await tg_send(T("saved"))
        return await show_pv_account_menu(aid)

    if conv.get("pv_tpl_wait"):
        w = conv.pop("pv_tpl_wait"); tid = w.get("tid"); kind = w.get("kind")
        t = get_template(tid)
        if not t: return await show_at_menu()
        pv = t.setdefault("pv", {}); items = pv.get("items") or []
        if kind == "delay":
            try: pv["delay_seconds"] = max(0, int(re.sub(r"[^\d]", "", text) or "0"))
            except: pv["delay_seconds"] = 0
            update_template(tid, "pv", "delay_seconds", pv["delay_seconds"])
        elif kind == "add_text":
            items.append({"kind": "text", "text": text})
            update_template(tid, "pv", "items", items)
        elif kind == "add_delay_sec":
            try: sec = max(0, int(re.sub(r"[^\d]", "", text) or "3"))
            except: sec = 3
            items.append({"kind": "delay", "seconds": sec})
            update_template(tid, "pv", "items", items)
        await tg_send(T("saved"))
        return await show_at_pv(tid)

    if conv.get("pv_tpl_save_msg"):
        w = conv.pop("pv_tpl_save_msg"); tid = w.get("tid")
        t = get_template(tid)
        if not t: return await show_at_menu()
        media = _extract_media(msg); caption = text or ""
        if not media and not caption: return await ask(T("enter"))
        local_path = None
        if media:
            try: local_path = await _download_tg_file(media, "pvtpl", "pvtpl")
            except Exception: pass
        pv = t.setdefault("pv", {}); items = pv.get("items") or []
        if local_path: items.append({"kind": "file", "file_path": local_path, "caption": caption})
        else: items.append({"kind": "text", "text": caption})
        update_template(tid, "pv", "items", items); await tg_send(T("saved"))
        return await show_at_pv(tid)

    if conv.get("accphoto_upload"):
        info = conv.pop("accphoto_upload"); aid = info["aid"]
        media = _extract_media(msg)
        if not media: return await ask(T("prof_no_photo"))
        try: fpath = await _download_tg_file(media, aid, "accphoto")
        except Exception as e: return await ask(f"✗ {str(e)[:100]}")
        a = get_account(aid)
        if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
        STATE["panel"].pop(cid, None)
        await panel(T("prof_uploading"), page_tag=f"accphoto:{aid}")
        cli = None; ok = False; msg_r = ""
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if cli: ok, msg_r = await soroosh_set_profile_photo(cli, fpath)
            else: msg_r = f"connect: {err}"
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        await tg_send("✓" if ok else f"✗ {msg_r[:150]}")
        return await show_acc_photo_menu(aid)

    if conv.get("chphoto_upload"):
        info = conv.pop("chphoto_upload"); aid = info["aid"]; idx = info["idx"]
        media = _extract_media(msg)
        if not media: return await ask(T("prof_no_photo"))
        try: fpath = await _download_tg_file(media, aid, "chphoto")
        except Exception as e: return await ask(f"✗ {str(e)[:100]}")
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel(T("not_found"), kb_(nav()), page_tag="main")
        ch = chs[idx]
        STATE["panel"].pop(cid, None)
        await panel(T("prof_uploading"), page_tag=f"chphoto:{aid}:{idx}")
        cli = None; ok = False; msg_r = ""
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if cli:
                ent, _ = await _resolve_channel_entity(cli, ch, aid)
                if ent: ok, msg_r = await soroosh_set_channel_photo(cli, ent, fpath)
                else: msg_r = "resolve failed"
            else: msg_r = f"connect: {err}"
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        await tg_send("✓" if ok else f"✗ {msg_r[:150]}")
        return await show_ch_photo_menu(aid, idx)

    if conv.get("chfile_upload") and conv["chfile_upload"].get("step") == "wait_file":
        info = conv["chfile_upload"]; media = _extract_media(msg); fpath = None
        if media:
            try: fpath = await _download_tg_file(media, info["aid"], "chfile")
            except Exception as e: return await ask(f"✗ {str(e)[:100]}")
        elif text and os.path.exists(text.strip()): fpath = text.strip()
        if not fpath: return await ask(T("ch_file_q"))
        info["file_path"] = fpath; info["step"] = "wait_caption"
        conv["chfile_upload"] = info
        return await ask(T("ch_caption_q"))

    if conv.get("chfile_upload") and conv["chfile_upload"].get("step") == "wait_caption":
        info = conv.pop("chfile_upload"); aid = info["aid"]; idx = info["idx"]
        fpath = info.get("file_path"); caption = text.strip()
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel(T("not_found"), kb_(nav()), page_tag="main")
        ch = chs[idx]; STATE["panel"].pop(cid, None)
        await panel(T("loading"), page_tag=f"chview:{aid}:{idx}")
        cli = None; ok = False; msg_r = ""
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if cli:
                ent, _ = await _resolve_channel_entity(cli, ch, aid)
                if ent: ok, msg_r = await _send_file_to_entity(cli, ent, fpath, caption)
                else: msg_r = "resolve failed"
            else: msg_r = f"connect: {err}"
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        await tg_send("✓" if ok else f"✗ {msg_r[:150]}")
        return await show_channel_view(aid, idx)

    if conv.get("at_field_photo"):
        info = conv.pop("at_field_photo")
        tid = info["tid"]; section = info["section"]; field = info["field"]
        media = _extract_media(msg)
        if not media: return await ask(T("prof_no_photo"))
        try: fpath = await _download_tg_file(media, "tpl", "tplfile")
        except Exception as e: return await ask(f"✗ {str(e)[:100]}")
        update_template(tid, section, field, fpath); await tg_send(T("saved"))
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
            elif field == "loop_delay":
                try: value = max(0.5, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
                except: value = 3.0
            update_template(tid, section, field, value); await tg_send(T("saved"))
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
            except: s["edit_delay_seconds"] = 3.0
        elif kind == "ph": s["placeholder_text"] = text or "hi"
        elif kind == "loop_delay":
            try: s["loop_delay"] = max(0.5, float(re.sub(r"[^\d\.]", "", text) or "3.0"))
            except: s["loop_delay"] = 3.0
        return await show_send_step(cid)

    if conv.get("send_file_upload"):
        conv.pop("send_file_upload"); s = _send_conv(cid)
        media = _extract_media(msg)
        if media:
            try: fpath = await _download_tg_file(media, "send", "sendfile")
            except Exception as e: return await ask(f"✗ {str(e)[:100]}")
            s["attach_file"] = fpath
        elif text and os.path.exists(text.strip()): s["attach_file"] = text.strip()
        else: return await ask(T("send_attach_q"))
        await tg_send(T("saved"))
        return await show_send_step(cid)

    if conv.get("cfg_wait"):
        key = conv.pop("cfg_wait")
        cfg = _load(CFG_FILE, DEFAULT_CFG)
        try:
            v = text.strip()
            cfg[key] = float(v) if "." in v else int(v)
            _save(CFG_FILE, cfg); await tg_send(T("saved"))
        except: await tg_send(T("cfg_invalid"))
        return await show_cfg()

    if conv.get("ld_wait") == "url":
        back = conv.pop("ld_back", "jl:back_to_settings")
        url = text.strip()
        if url.startswith("splus.ir"): url = "https://" + url
        if url.startswith("soroush.ir"): url = "https://" + url
        if add_link_doni(url): await tg_send(T("saved"))
        else: await tg_send(T("empty"))
        return await show_linkdonies(back)

    if conv.get("setlink"):
        info = conv.pop("setlink"); aid = info["aid"]; idx = info["idx"]
        url = text.strip()
        if not url: return await ask(T("ch_link_q"))
        if not url.startswith("http"): url = "https://" + url
        update_channel_field(aid, idx, "join_link", url)
        await tg_send(T("saved"))
        return await show_channel_view(aid, idx)

    if conv.get("chsend") and conv["chsend"].get("step") == "compose":
        info = conv.pop("chsend"); aid = info["aid"]; idx = info["idx"]
        STATE["panel"].pop(cid, None)
        await panel(T("loading"), page_tag=f"chview:{aid}:{idx}")
        ok, msg_r = await send_to_channel(aid, idx, text)
        if ok:
            return await panel(head("✅", "send") + f"💬 <code>{esc(text[:100])}</code>",
                               kb_([B(f"« {T('back')}", f"ch:view:{aid}:{idx}")]), page_tag=f"chview:{aid}:{idx}")
        return await panel(f"✗ <code>{esc(str(msg_r)[:400])}</code>",
                           kb_([B(f"« {T('back')}", f"ch:view:{aid}:{idx}")]), page_tag=f"chview:{aid}:{idx}")

    if conv.get("chprof_edit"):
        info = conv.pop("chprof_edit"); aid = info["aid"]; idx = info["idx"]; field = info["field"]
        a = get_account(aid); chs = get_stored_channels(aid)
        if not a or idx >= len(chs): return await panel(T("not_found"), kb_(nav()), page_tag="main")
        ch = chs[idx]; STATE["panel"].pop(cid, None)
        await panel(T("loading"), page_tag=f"chprof:{aid}:{idx}")
        cli = None; ok = False; msg_r = ""
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if not cli:
                ok, msg_r = False, f"connect: {err}"
            else:
                ent, _ = await _resolve_channel_entity(cli, ch, aid)
                if not ent:
                    ok, msg_r = False, "resolve failed"
                else:
                    if field == "title":
                        if EditTitleRequest:
                            r = cli(EditTitleRequest(channel=ent, title=text[:60]))
                            if asyncio.iscoroutine(r): r = await r
                            ok, msg_r = True, "OK"
                            update_channel_field(aid, idx, "title", text[:60])
                    elif field == "desc":
                        try:
                            from splusthon.tl.functions.messages import EditChatAboutRequest as _ECAR
                        except Exception: _ECAR = None
                        if _ECAR:
                            try:
                                r = cli(_ECAR(peer=ent, about=text))
                                if asyncio.iscoroutine(r): r = await r
                                ok, msg_r = True, "OK"
                                update_channel_field(aid, idx, "description", text)
                            except Exception as e: msg_r = _fmt_error(e)
                    elif field == "user":
                        r = cli(UpdateUsernameRequest(channel=ent, username=text.lstrip("@")))
                        if asyncio.iscoroutine(r): r = await r
                        ok, msg_r = True, "OK"
                        update_channel_field(aid, idx, "username", text.lstrip("@"))
                        update_channel_field(aid, idx, "type", "public")
        except Exception as e: msg_r = _fmt_error(e)
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        await tg_send("✓" if ok else f"✗ {msg_r[:150]}")
        return await show_ch_profile(aid, idx)

    if conv.get("chnew"):
        info = conv["chnew"]; step = info.get("step"); aid = info.get("aid")
        a = get_account(aid); STATE["panel"].pop(cid, None)
        if not a:
            conv.pop("chnew", None)
            return await panel(T("not_found"), kb_(nav()), page_tag="main")
        if step == "title":
            title = text.strip()
            if not title: return await ask(T("ch_new_name_q"))
            info["title"] = title[:60]; info["step"] = "type"; conv["chnew"] = info
            return await show_ch_new_type(aid, title)
        if step == "username":
            title = info.get("title"); uname = text.lstrip("@").strip()
            if not uname: return await ask(T("ch_new_user_q"))
            conv.pop("chnew", None)
            await panel(f"{T('ch_creating')} «{esc(title)}»", page_tag="chnew_run")
            cli = None; ok = False; msg_r = ""; ch_obj = None
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
                                except Exception as ue: msg_r = f"username: {_fmt_error(ue)[:100]}"
                        except Exception: pass
                else: ok, msg_r = False, f"connect: {err}"
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
                body = head("✅", "ch_created") + f"📝 {esc(title)}\n🔗 @{esc(uname)}"
                return await panel(body, kb_([B(T("my_channels"), f"chlist:show:{aid}:0")],
                                             [B(f"« {T('back')}", f"ch:menu:{aid}")]),
                                   page_tag=f"ch_menu:{aid}")
            return await panel(f"✗ <code>{esc(str(msg_r)[:300])}</code>",
                               kb_([B(f"« {T('back')}", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")

    if conv.get("prof_field"):
        info = conv.pop("prof_field"); field = info["field"]; aid = info["aid"]
        STATE["panel"].pop(cid, None)
        a = get_account(aid)
        if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
        await panel(T("loading"), page_tag=f"prof:{aid}")
        ok = False; msg_r = ""; cli = None
        try:
            cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
            if cli is None: ok, msg_r = False, f"connect: {err}"
            else:
                if field in ("first", "last", "about"):
                    kwargs = {}
                    if field == "first": kwargs["first_name"] = text
                    elif field == "last": kwargs["last_name"] = text
                    elif field == "about": kwargs["about"] = text
                    ok, msg_r = await soroosh_update_profile(cli, **kwargs)
                elif field == "username":
                    ok, msg_r = await soroosh_update_username(cli, text)
        except Exception as e: ok, msg_r = False, f"{type(e).__name__}: {_fmt_error(e)}"
        finally:
            if cli:
                try: await cli._disconnect()
                except Exception: pass
        if ok:
            return await panel(head("✅", "profile") + f"<code>{esc(str(msg_r)[:200])}</code>",
                               kb_([B(f"« {T('back')}", f"prof:menu:{aid}")]), page_tag=f"prof:{aid}")
        return await panel(f"✗ <code>{esc(str(msg_r)[:300])}</code>",
                           kb_([B(f"« {T('back')}", f"prof:menu:{aid}")]), page_tag=f"prof:{aid}")

    if "jl_wait" in conv:
        conv.pop("jl_wait"); jl = get_conv(cid).get("jl") or {}
        try: jl["max_join"] = max(1, int(re.sub(r"[^\d]", "", text)))
        except: return await ask(T("jl_max_q"))
        get_conv(cid)["jl"] = jl; return await jl_step_max(cid, jl)

    if "send_wait" in conv:
        conv.pop("send_wait"); s = _send_conv(cid)
        try: s["max"] = max(0, int(re.sub(r"[^\d]", "", text)))
        except: return await ask(T("send_max_q"))
        return await show_send_step(cid)

    if "send" in conv:
        s = conv["send"]
        if s.get("step") == "compose":
            STATE["panel"].pop(cid, None)
            if not text: return await ask(T("send_step2"))
            s["payload"] = {"text": text}; s["step"] = "target"
            return await show_send_step(cid)

    if "acc" in conv:
        a = conv["acc"]; step = a.get("step")
        STATE["panel"].pop(cid, None)
        if step == "phone":
            try: ph = normalize_phone(text)
            except Exception as e: return await ask(T("invalid_phone"), note=str(e)[:150])
            a["phone"] = ph
            await panel(f"{T('loading')} — <code>{esc(ph)}</code>", page_tag="login_send")
            try: res = await soroosh_send_code(ph)
            except Exception as e: res = {"ok": False, "status": _fmt_error(e)}
            if not res.get("ok"):
                clear_conv(cid)
                return await panel(f"✗ <code>{esc(str(res.get('status'))[:400])}</code>",
                                   kb_([B(T("add_account"), "acc:add")],
                                       [B(T("back_to_panel"), "menu:main")]), page_tag="main")
            a["step"] = "login_code"; STATE["conv"][cid] = {"acc": a}
            return await panel(f"✓ <code>{esc(ph)}</code>", page_tag="login_code")


_on_message_orig = _on_message_impl

async def on_message(update, context):
    cid = None; had_conv = False; keep = False
    try:
        cid = update.effective_chat.id
        had_conv = bool(STATE["conv"].get(cid)) or (cid in _TMP_EDIT)
        c = STATE["conv"].get(cid) or {}
        if any(c.get(k) for k in ("pv_acc_save_msg", "pv_tpl_save_msg", "accphoto_upload",
                                   "chphoto_upload", "chfile_upload", "at_field_photo",
                                   "send_file_upload")):
            keep = True
    except Exception: pass
    await _on_message_orig(update, context)
    try:
        if had_conv and authorized(update) and update.message and not keep:
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
    if data == "menu:cfg": return await show_cfg()

    # language toggle
    if data == "cfg:lang":
        cur = _get_lang(); new = "en" if cur == "fa" else "fa"
        _set_lang(new)
        await tg_send(("🌐 " + T("cfg_lang_en")) if new == "en" else ("🌐 " + T("cfg_lang_fa")))
        return await show_main()

    # cache
    if h == "cache":
        sub = p[1] if len(p) > 1 else ""
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; act = p[3] if len(p) > 3 else ""
            if not act: return await show_cache_account(aid)
            if act == "clear_seen": _clear_seen(aid); await tg_send(T("cleared")); return await show_cache_account(aid)
            if act == "clear_banned": _clear_banned(aid); await tg_send(T("cleared")); return await show_cache_account(aid)
            if act == "clear_all":
                _clear_seen(aid); _clear_banned(aid); await tg_send(T("cleared"))
                return await show_cache_account(aid)
            if act == "reset_ld": _reset_ld_progress(aid); await tg_send(T("cleared")); return await show_cache_account(aid)
        if sub == "clear_all_accounts":
            _clear_seen(); _clear_banned(); _reset_ld_progress()
            await tg_send(T("cleared")); return await show_cache_menu()

    # pv
    if h == "pv":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu": return await show_pv_menu()
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
                seq = [1, 2, 3, 5, 0]
                cur = int(cfg.get("max_replies", 1) or 0)
                cfg["max_replies"] = seq[(seq.index(cur) + 1) % len(seq)] if cur in seq else 1
                _save_pv_account(aid, cfg); return await show_pv_account_menu(aid)
            if act == "set_delay":
                get_conv(cid)["pv_acc_wait"] = {"aid": aid, "kind": "delay"}
                return await ask(T("pv_delay_q"))
            if act == "set_poll":
                get_conv(cid)["pv_acc_wait"] = {"aid": aid, "kind": "poll"}
                return await ask(T("pv_poll_q"))
            if act == "toggle_notify":
                cfg["notify"] = not bool(cfg.get("notify", True))
                _save_pv_account(aid, cfg); return await show_pv_account_menu(aid)
            if act == "add_text":
                get_conv(cid)["pv_acc_wait"] = {"aid": aid, "kind": "add_text"}
                return await ask(T("pv_text_q"))
            if act == "add_saved":
                get_conv(cid)["pv_acc_save_msg"] = {"aid": aid}
                return await ask(T("pv_file_q"))
            if act == "add_delay":
                get_conv(cid)["pv_acc_wait"] = {"aid": aid, "kind": "add_delay_sec"}
                return await ask(T("pv_delaysec_q"))
            if act == "list": return await show_pv_account_list(aid)
            if act == "del" and len(p) >= 5:
                try: i = int(p[4])
                except: return await show_pv_account_list(aid)
                items = cfg.get("items") or []
                if 0 <= i < len(items): items.pop(i)
                cfg["items"] = items; _save_pv_account(aid, cfg)
                await tg_send(T("deleted")); return await show_pv_account_list(aid)
            if act == "clear_replies":
                try:
                    d = _load(PV_COUNTS_FILE, {}); d.pop(aid, None); _save(PV_COUNTS_FILE, d)
                except Exception: pass
                try:
                    w = _wm_load(); w.pop(aid, None); _wm_flush()
                except Exception: pass
                await tg_send(T("cleared")); return await show_pv_account_menu(aid)
            if act == "reset_to_global":
                _delete_pv_account(aid); await tg_send(T("cleared"))
                return await show_pv_account_menu(aid)
            if act == "restart":
                _stop_pv_for_account(aid); await asyncio.sleep(0.5)
                cfg2 = _load_pv_account(aid)
                if cfg2.get("enabled"):
                    acc = get_account(aid)
                    if acc:
                        stop = asyncio.Event(); _PV_STOP_EVENTS[aid] = stop
                        PV_LISTENER_TASKS[aid] = asyncio.create_task(_pv_poller_worker(aid, acc, stop))
                await tg_send(T("restarted")); return await show_pv_account_menu(aid)
            if act == "report":
                try: pg = int(p[4]) if len(p) > 4 else 0
                except: pg = 0
                return await show_pv_account_report(aid, pg)

    # accounts
    if h == "acc":
        if len(p) >= 5 and p[1] == "at" and p[2] == "run":
            aid = p[3]; tid = p[4]
            op = {"id": "at_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "autotar", "accounts": [aid], "template_id": tid, "status": "running",
                  "progress": {"joined":0,"failed":0,"total":0,"pending":0,"in_progress":0,
                               "phase":"start","sent":0,"already":0,"tried":0,"wave":0,
                               "left":0,"round":0,"skipped_seen":0,"skipped_banned":0,"rejected":0},
                  "errors": []}
            _save_op(op); asyncio.create_task(run_auto_tar(op, log_cb))
            return await show_op_detail(op["id"])
        if len(p) >= 3 and p[1] == "at": return await show_acc_at_menu(p[2])
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_accounts(int(p[2]))
        if sub == "refresh":
            for aid in list(_STATS_CACHE.keys()): _STATS_CACHE.pop(aid, None)
            await tg_send("🔄"); return await show_accounts()
        if sub == "add":
            get_conv(cid)["acc"] = {"step": "phone"}
            return await ask(T("add_account_q"))
        if sub == "view": return await show_account_detail(p[2])
        if sub == "del":
            a = get_account(p[2])
            if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
            return await panel(T("acc_delete_q", n=a.get('name','?')),
                               kb_([B(T("yes"), f"acc:delok:{p[2]}"), B(T("no"), f"acc:view:{p[2]}")]),
                               page_tag=f"acc_del:{p[2]}")
        if sub == "delok":
            _stop_listener_for(p[2])
            try: _stop_pv_for_account(p[2])
            except Exception: pass
            remove_account(p[2]); await tg_send(T("deleted")); return await show_accounts()
        if sub == "lf" and len(p) >= 5 and p[3] == "go":
            aid = p[2]; mode = p[4]
            op = {"id": "lf_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "lefter", "accounts": [aid], "leave_mode": mode, "delay": 0.8,
                  "status": "running",
                  "progress": {"joined":0,"failed":0,"total":0,"phase":"start"}, "errors": []}
            _save_op(op); asyncio.create_task(run_lefter(op, log_cb))
            return await show_op_detail(op["id"])
        if sub == "lf" and len(p) >= 3: return await show_acc_lf(p[2])

    if h == "accphoto":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu" and len(p) >= 3: return await show_acc_photo_menu(p[2])
        if sub == "set" and len(p) >= 3:
            get_conv(cid)["accphoto_upload"] = {"aid": p[2]}; return await ask(T("prof_send_photo"))
        if sub == "del" and len(p) >= 3:
            aid = p[2]; a = get_account(aid)
            if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
            await panel(T("prof_deleting"), page_tag=f"accphoto:{aid}")
            cli = None; ok = False; msg_r = ""
            try:
                cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
                if cli: ok, msg_r = await soroosh_delete_profile_photos(cli)
                else: msg_r = f"connect: {err}"
            finally:
                if cli:
                    try: await cli._disconnect()
                    except Exception: pass
            await tg_send("✓" if ok else f"✗ {msg_r[:150]}")
            return await show_acc_photo_menu(aid)

    if h == "chphoto":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu" and len(p) >= 4: return await show_ch_photo_menu(p[2], int(p[3]))
        if sub == "set" and len(p) >= 4:
            get_conv(cid)["chphoto_upload"] = {"aid": p[2], "idx": int(p[3])}
            return await ask(T("prof_send_photo"))
        if sub == "del" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            a = get_account(aid); chs = get_stored_channels(aid)
            if not a or idx >= len(chs): return await panel(T("not_found"), kb_(nav()), page_tag="main")
            ch = chs[idx]; await panel(T("prof_deleting"), page_tag=f"chphoto:{aid}:{idx}")
            cli = None; ok = False; msg_r = ""
            try:
                cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
                if cli:
                    ent, _ = await _resolve_channel_entity(cli, ch, aid)
                    if ent: ok, msg_r = await soroosh_delete_channel_photos(cli, ent)
                    else: msg_r = "resolve failed"
                else: msg_r = f"connect: {err}"
            finally:
                if cli:
                    try: await cli._disconnect()
                    except Exception: pass
            await tg_send("✓" if ok else f"✗ {msg_r[:150]}")
            return await show_ch_photo_menu(aid, idx)

    if h == "chfile":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start" and len(p) >= 4:
            get_conv(cid)["chfile_upload"] = {"aid": p[2], "idx": int(p[3]), "step": "wait_file"}
            return await ask(T("ch_file_q"))

    if h == "prof":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu": return await show_profile_menu(p[2])
        if sub == "set":
            field = p[2]; aid = p[3]
            get_conv(cid)["prof_field"] = {"field": field, "aid": aid}
            prompts = {"first": T("prof_first_q"), "last": T("prof_last_q"),
                       "about": T("prof_bio_q"), "username": T("prof_user_q")}
            return await ask(prompts.get(field, T("enter")))

    if h == "ch":
        sub = p[1] if len(p) > 1 else ""
        if sub == "menu": return await show_ch_menu(p[2])
        if sub == "view" and len(p) >= 4: return await show_channel_view(p[2], int(p[3]))
        if sub == "getlink" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            await panel(T("ch_link_fetch"), page_tag=f"chview:{aid}:{idx}")
            ok, res = await export_invite_link(aid, idx)
            if ok:
                return await panel(head("🔗", "link") + f"\n\n<code>{esc(res)}</code>",
                                   kb_([B("🔄", f"ch:getlink:{aid}:{idx}")],
                                       [B(T("set_link"), f"ch:setlink:{aid}:{idx}")],
                                       [B(f"« {T('back')}", f"ch:view:{aid}:{idx}")]),
                                   page_tag=f"chview:{aid}:{idx}")
            return await panel(head("⚠️", "error") + f"\n{esc(str(res)[:600])}",
                               kb_([B(T("set_link"), f"ch:setlink:{aid}:{idx}")],
                                   [B(f"« {T('back')}", f"ch:view:{aid}:{idx}")]),
                               page_tag=f"chview:{aid}:{idx}")
        if sub == "setlink" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            get_conv(cid)["setlink"] = {"aid": aid, "idx": idx}
            return await ask(T("ch_link_q"))
        if sub == "diag" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            await panel(T("loading"), page_tag=f"chview:{aid}:{idx}")
            try: dump = await diagnose_channel(aid, idx)
            except Exception as e: dump = f"ERR: {e}"
            return await panel(head("🔍", "debug") + f"\n<pre>{esc(dump[:3500])}</pre>",
                               kb_([B(f"« {T('back')}", f"ch:view:{aid}:{idx}")]), page_tag=f"chview:{aid}:{idx}")
        if sub == "del" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            channels = get_stored_channels(aid)
            if idx >= len(channels): return await show_ch_list(aid)
            return await panel(T("ch_delete_q"),
                               kb_([B(T("yes"), f"ch:delok:{aid}:{idx}"),
                                    B(T("no"), f"ch:view:{aid}:{idx}")]),
                               page_tag=f"chview:{aid}:{idx}")
        if sub == "delok" and len(p) >= 4:
            aid = p[2]; idx = int(p[3])
            remove_channel_from_storage(aid, idx)
            await tg_send(T("deleted"))
            return await show_ch_list(aid)

    if h == "chlist":
        sub = p[1] if len(p) > 1 else ""
        if sub == "show": return await show_ch_list(p[2], int(p[3]) if len(p) > 3 else 0)

    if h == "chsend":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start" and len(p) >= 4:
            get_conv(cid)["chsend"] = {"aid": p[2], "idx": int(p[3]), "step": "compose"}
            return await ask(T("ch_send_q"))

    if h == "chprof":
        sub = p[1] if len(p) > 1 else ""
        if sub == "show" and len(p) >= 4: return await show_ch_profile(p[2], int(p[3]))
        if sub == "edit" and len(p) >= 5:
            field = p[2]; aid = p[3]; idx = int(p[4])
            get_conv(cid)["chprof_edit"] = {"aid": aid, "idx": idx, "field": field}
            prompts = {"title": T("ch_profile_edit_title"),
                       "desc": T("ch_profile_edit_desc"),
                       "user": T("ch_profile_edit_user")}
            return await ask(prompts.get(field, T("enter")))

    if h == "chnew":
        sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            get_conv(cid)["chnew"] = {"aid": p[2], "step": "title"}
            return await ask(T("ch_new_name_q"))
        if sub == "pub":
            aid = p[2]; info = get_conv(cid).get("chnew") or {}; title = info.get("title")
            if not title: return await panel(T("not_found"), kb_(nav(f"ch:menu:{aid}")), page_tag=f"ch_menu:{aid}")
            get_conv(cid)["chnew"] = {"aid": aid, "step": "username", "title": title}
            return await ask(T("ch_new_user_q"))
        if sub == "priv":
            aid = p[2]; info = get_conv(cid).get("chnew") or {}; title = info.get("title")
            if not title: return await panel(T("not_found"), kb_(nav(f"ch:menu:{aid}")), page_tag=f"ch_menu:{aid}")
            get_conv(cid).pop("chnew", None)
            a = get_account(aid); STATE["panel"].pop(cid, None)
            if not a: return await panel(T("not_found"), kb_(nav()), page_tag="main")
            await panel(T("ch_creating"), page_tag="chnew_run")
            cli = None; ok = False; msg_r = ""; ch_obj = None
            try:
                cli, err = await _connect_with_retry(aid, a["session_string"], name=a.get("name"), tries=3)
                if cli: ok, ch_obj, msg_r = await soroosh_create_channel(cli, title)
                else: ok, msg_r = False, f"connect: {err}"
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
                return await panel(head("✅", "ch_created") + f"📝 {esc(title)}",
                                   kb_([B(T("my_channels"), f"chlist:show:{aid}:0")],
                                       [B(f"« {T('back')}", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")
            return await panel(f"✗ <code>{esc(str(msg_r)[:300])}</code>",
                               kb_([B(f"« {T('back')}", f"ch:menu:{aid}")]), page_tag=f"ch_menu:{aid}")

    if h == "listen":
        sub = p[1] if len(p) > 1 else ""
        if sub == "restart":
            await restart_all_listeners(); await tg_send(T("restarted")); return await show_listen_menu()
        if sub == "toggle" and len(p) >= 3:
            aid = p[2]; t = LISTENER_TASKS.get(aid)
            if t and not t.done(): _stop_listener_for(aid); await tg_send(T("off"))
            else: await start_all_listeners(); await tg_send(T("on"))
            await asyncio.sleep(0.3); return await show_listen_menu()

    if h == "ld":
        sub = p[1] if len(p) > 1 else ""
        back = p[3] if len(p) > 3 else (p[2] if len(p) > 2 else "jl:back_to_settings")
        if sub == "list": return await show_linkdonies(back)
        if sub == "add":
            get_conv(cid)["ld_wait"] = "url"; get_conv(cid)["ld_back"] = back
            return await ask(T("ld_add_q"))
        if sub == "del" and len(p) >= 3:
            remove_link_doni(int(p[2])); await tg_send(T("deleted")); return await show_linkdonies(back)
        if sub == "reset":
            save_link_donies(list(DEFAULT_LINK_DONIES)); await tg_send(T("restarted")); return await show_linkdonies(back)
        if sub == "reset_prog":
            _reset_ld_progress(); await tg_send(T("restarted")); return await show_linkdonies(back)
        if sub == "toggle_autojoin":
            cfg = _load(CFG_FILE, DEFAULT_CFG)
            cfg["auto_join_linkdoni"] = 0 if int(cfg.get("auto_join_linkdoni", 1)) else 1
            _save(CFG_FILE, cfg); return await show_linkdonies(back)

    if h == "err":
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_errors(int(p[2]))
        if sub == "clear": clear_errors(); await tg_send(T("cleared")); return await show_errors()

    if h == "listen" and p[1] == "cfg":
        return await show_listen_menu()

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
        if sub == "toggle_rescan": s["rescan_targets"] = not s.get("rescan_targets", True); return await show_send_step(cid)
        if sub == "loop_delay":
            get_conv(cid)["send_edit_wait"] = "loop_delay"; return await ask(T("send_loop_q"))
        if sub == "toggle_edit": s["edit_delay_enabled"] = not s.get("edit_delay_enabled", False); return await show_send_step(cid)
        if sub == "edit_sec":
            get_conv(cid)["send_edit_wait"] = "sec"; return await ask(T("send_edit_q"))
        if sub == "edit_ph":
            get_conv(cid)["send_edit_wait"] = "ph"; return await ask(T("send_ph_q"))
        if sub == "toggle_edit_rand": s["edit_delay_random"] = not s.get("edit_delay_random", False); return await show_send_step(cid)
        if sub == "toggle_ph_rand": s["placeholder_random"] = not s.get("placeholder_random", False); return await show_send_step(cid)
        if sub == "toggle_multi": s["multi_step_edit"] = not s.get("multi_step_edit", False); return await show_send_step(cid)
        if sub == "attach":
            get_conv(cid)["send_file_upload"] = True
            return await ask(T("send_attach_q"))
        if sub == "tgtnext": s["step"] = "max"; return await show_send_step(cid)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["send_wait"] = "max"; return await ask(T("send_max_q"))
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
                  "max": s.get("max", 0) or 0,
                  "payload": s.get("payload") or {"text": "hi"},
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
            asyncio.create_task(run_sender(op, log_cb))
            return await show_op_detail(op["id"])

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
                get_conv(cid)["jl_wait"] = "max"; return await ask(T("jl_max_q"))
            try: s["max_join"] = int(v)
            except: pass
            return await jl_step_max(cid, s)
        if sub == "next":
            if s["step"] == "account":
                if not s.get("accounts"): return await panel(T("empty"), kb_([B(f"« {T('back')}", "jl:back")]), page_tag="jl:1")
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
            if not s.get("max_join"): return await panel(T("empty"), kb_([B(f"« {T('back')}", "jl:back")]), page_tag="jl:3")
            if not s.get("accounts"): return await panel(T("empty"), kb_([B(f"« {T('back')}", "jl:back")]), page_tag="jl:1")
            speed_map = {"ultra": 0.3, "fast": 1.0, "normal": 3.0, "slow": 8.0}
            spd = s.get("speed", "fast"); cfg = _load(CFG_FILE, DEFAULT_CFG)
            op = {"id": "jl_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "joinlef", "accounts": s.get("accounts") or [],
                  "max_join": s.get("max_join", 0), "status": "running", "speed": spd,
                  "join_delay": speed_map.get(spd, 1.0),
                  "groups_only": bool(s.get("groups_only", True)),
                  "wave_size": int(cfg.get("wave_size", 50)),
                  "extract_limit": int(cfg.get("extract_limit", 300)),
                  "link_donies": list(load_link_donies()),
                  "progress": {"joined":0,"failed":0,"total":0,"phase":"start",
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
            except: s["delay"] = 0.8
            return await lf_step_delay(cid, s)
        if sub == "next":
            if s["step"] == "account":
                if not s.get("accounts"): return await panel(T("empty"), kb_([B(f"« {T('back')}", "lf:back")]), page_tag="lf:1")
                s["step"] = "mode"; return await lf_step_mode(cid, s)
            elif s["step"] == "mode":
                s["step"] = "delay"; return await lf_step_delay(cid, s)
        if sub == "back":
            if s["step"] == "mode": s["step"] = "account"
            elif s["step"] == "delay": s["step"] = "mode"
            return await show_lf_step(cid)
        if sub == "cancel": c.pop("lf", None); return await show_main()
        if sub == "go":
            if not s.get("accounts"): return await panel(T("empty"), kb_([B(f"« {T('back')}", "lf:back")]), page_tag="lf:1")
            op = {"id": "lf_" + secrets.token_hex(5), "created": int(time.time()),
                  "type": "lefter", "accounts": s.get("accounts") or [],
                  "leave_mode": s.get("mode", "all"), "delay": s.get("delay", 0.8),
                  "status": "running",
                  "progress": {"joined":0,"failed":0,"total":0,"phase":"start"},
                  "errors": []}
            _save_op(op); c.pop("lf", None)
            asyncio.create_task(run_lefter(op, log_cb))
            return await show_op_detail(op["id"])

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
                return await panel(T("at_delete_q", n=t.get('name','?')),
                                   kb_([B(T("yes"), f"at:{tid}:delok"),
                                        B(T("no"), f"at:{tid}:view")]),
                                   page_tag=f"at:{tid}:view")
            if act == "delok": delete_template(tid); await tg_send(T("deleted")); return await show_at_menu()
            if act == "rename":
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "meta", "field": "name"}
                return await ask(T("at_rename_q"))
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
                    return await ask(T("ch_photo_menu"))
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "channel", "field": field}
                prompts = {"title": T("channel_title"), "username": T("username"), "about": T("about")}
                return await ask(prompts.get(field, T("enter")))
            if act == "prset" and len(p) >= 4:
                field = p[3]
                if field == "photo_file":
                    get_conv(cid)["at_field_photo"] = {"tid": tid, "section": "profile", "field": "photo_file"}
                    return await ask(T("prof_photo_menu"))
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "profile", "field": field}
                prompts = {"first_name": T("prof_first_q"), "last_name": T("prof_last_q"),
                           "username": T("prof_user_q"), "bio": T("prof_bio_q")}
                return await ask(prompts.get(field, T("enter")))
            if act == "jnset" and len(p) >= 4:
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "joiner", "field": p[3]}
                return await ask(T("jl_max"))
            if act == "jnspeed" and len(p) >= 4:
                update_template(tid, "joiner", "speed", p[3]); return await show_at_joiner(tid)
            if act == "jntoggle_groups_only":
                t = get_template(tid)
                if t: update_template(tid, "joiner", "groups_only",
                                       not bool(t.get("joiner", {}).get("groups_only", True)))
                return await show_at_joiner(tid)
            if act == "snset" and len(p) >= 4:
                field = p[3]
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender", "field": field}
                prompts = {"text": T("text"), "target": f"{T('target')} (pv/groups/both)",
                           "max_send": f"{T('max')} (0=∞)", "delay": T("delay")}
                return await ask(prompts.get(field, T("enter")))
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
                _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender", "field": "loop_delay"}
                return await ask(T("send_loop_q"))
            if act == "snedit" and len(p) >= 4:
                sub_act = p[3]
                ts = list_templates(); t2 = ts.get(tid)
                if sub_act in ("toggle", "ph_rand", "multi_toggle", "toggle_existing"):
                    if t2:
                        snd2 = t2.setdefault("sender", {})
                        if sub_act == "toggle": snd2["edit_delay_enabled"] = not bool(snd2.get("edit_delay_enabled", False))
                        elif sub_act == "ph_rand": snd2["placeholder_random"] = not bool(snd2.get("placeholder_random", False))
                        elif sub_act == "multi_toggle": snd2["multi_step_edit"] = not bool(snd2.get("multi_step_edit", False))
                        elif sub_act == "toggle_existing": snd2["send_to_existing"] = not bool(snd2.get("send_to_existing", True))
                        save_templates(ts)
                    return await show_at_sender(tid)
                if sub_act == "sec":
                    _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender_edit", "field": "edit_delay_seconds"}
                    return await ask(T("send_edit_q"))
                if sub_act == "ph":
                    _TMP_EDIT[cid] = {"kind": "at_field", "tid": tid, "section": "sender_edit", "field": "placeholder_text"}
                    return await ask(T("send_ph_q"))
                if sub_act == "file":
                    get_conv(cid)["at_field_photo"] = {"tid": tid, "section": "sender_edit", "field": "attach_file"}
                    return await ask(T("send_attach_q"))
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
                    get_conv(cid)["pv_tpl_wait"] = {"tid": tid, "kind": "delay"}
                    return await ask(T("pv_delay_q"))
                if sub_act == "toggle_apply":
                    update_template(tid, "pv", "apply_to_accounts",
                                    not bool(pv2.get("apply_to_accounts", True)))
                    return await show_at_pv(tid)
                if sub_act == "add_text":
                    get_conv(cid)["pv_tpl_wait"] = {"tid": tid, "kind": "add_text"}
                    return await ask(T("pv_text_q"))
                if sub_act == "add_saved":
                    get_conv(cid)["pv_tpl_save_msg"] = {"tid": tid}
                    return await ask(T("pv_file_q"))
                if sub_act == "add_delay":
                    get_conv(cid)["pv_tpl_wait"] = {"tid": tid, "kind": "add_delay_sec"}
                    return await ask(T("pv_delaysec_q"))
                if sub_act == "list": return await show_at_pv_list(tid)
                if sub_act == "del" and len(p) >= 5:
                    try: i = int(p[4])
                    except: return await show_at_pv_list(tid)
                    if 0 <= i < len(items): items.pop(i)
                    update_template(tid, "pv", "items", items)
                    await tg_send(T("deleted")); return await show_at_pv_list(tid)
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
                if not sel: return await panel(T("empty"), kb_(nav(f"at:{tid}:view")), page_tag=f"at:{tid}:run:0")
                op = {"id": "at_" + secrets.token_hex(5), "created": int(time.time()),
                      "type": "autotar", "accounts": sel, "template_id": tid, "status": "running",
                      "progress": {"joined":0,"failed":0,"total":0,"pending":0,"in_progress":0,
                                   "phase":"start","sent":0,"already":0,"tried":0,"wave":0,
                                   "left":0,"round":0,"skipped_seen":0,"skipped_banned":0,"rejected":0},
                      "errors": []}
                _save_op(op); c.pop("at_run", None)
                asyncio.create_task(run_auto_tar(op, log_cb))
                return await show_op_detail(op["id"])
            if len(p) == 3 and p[2].isdigit(): return await show_at_run(tid, int(p[2]))

    if h == "cfg":
        sub = p[1] if len(p) > 1 else ""
        if sub == "set" and len(p) >= 3:
            key = p[2]; get_conv(cid)["cfg_wait"] = key
            return await ask(T("cfg_value_q", k=key))
        if sub == "toggle_autojoin":
            cfg = _load(CFG_FILE, DEFAULT_CFG)
            cfg["auto_join_linkdoni"] = 0 if int(cfg.get("auto_join_linkdoni", 1)) else 1
            _save(CFG_FILE, cfg); return await show_cfg()
        if sub == "toggle_listener":
            cfg = _load(CFG_FILE, DEFAULT_CFG)
            cfg["listener"] = 0 if int(cfg.get("listener", 1)) else 1
            _save(CFG_FILE, cfg); return await show_cfg()


# ═══════════════ BOOT ═══════════════
async def _post_init(app):
    try:
        await app.bot.set_my_commands([BotCommand("start", "start"), BotCommand("menu", "menu")])
    except Exception: pass
    try: _loop_ref[0] = asyncio.get_running_loop()
    except Exception: pass
    try:
        await start_all_listeners()
        await start_pv_responders()
        asyncio.create_task(keepalive_loop())
    except Exception as e:
        flog(f"[post_init] {type(e).__name__}: {e}", "error")

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
        await tg_send(f"✗ {type(e).__name__}: {str(e)[:200]}")

def main(token=None, owner_id=None):
    global APP, TG_TOKEN, FORCED_OWNER
    if token: TG_TOKEN = token
    else: TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
    if not TG_TOKEN or ":" not in TG_TOKEN: print("[x] TG_TOKEN missing."); return
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
    except KeyboardInterrupt: print("\n[!] stop")