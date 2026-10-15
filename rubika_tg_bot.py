# rubika_tg_bot.py — v74 (merged: Rubika + Soroosh features · bilingual fa/en · colored buttons)
# Railway-ready · token/owner from app.py or env
import os, sys, ssl, json, socket, asyncio, time, glob, re, threading, secrets, queue
import logging, traceback, concurrent.futures, inspect, random, hashlib
import html as _html
import builtins

VERSION = "v74"

# ══════════════════════════════════════════════════════════════
# DATA DIR
# ══════════════════════════════════════════════════════════════
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
print(f"[+] VERSION: {VERSION}")
print(f"[+] DATA_DIR: {DATA_DIR}")

# ══════════════════════════════════════════════════════════════
# signal patch
# ══════════════════════════════════════════════════════════════
try:
    import asyncio.unix_events as _ue
    _orig_add_signal = _ue._UnixSelectorEventLoop.add_signal_handler
    def _safe_add_signal(self, sig, callback, *args):
        try: return _orig_add_signal(self, sig, callback, *args)
        except (RuntimeError, ValueError, NotImplementedError, AttributeError):
            return None
    _ue._UnixSelectorEventLoop.add_signal_handler = _safe_add_signal
except Exception: pass

# ══════════════════════════════════════════════════════════════
# logging
# ══════════════════════════════════════════════════════════════
_rl = logging.getLogger("rubpy"); _rl.setLevel(logging.WARNING)
_h = logging.StreamHandler(sys.stderr)
_h.setFormatter(logging.Formatter('[rubpy] %(message)s'))
_rl.addHandler(_h); _rl.propagate = False
for _n in ("urllib3","urllib3.connectionpool","requests","httpx","httpcore",
           "telegram.ext.Updater","telegram.request"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)
    logging.getLogger(_n).propagate = False

# ══════════════════════════════════════════════════════════════
# certifi / DoH
# ══════════════════════════════════════════════════════════════
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
    for u in ("https://1.1.1.1/dns-query","https://8.8.8.8/resolve"):
        try:
            r = SESSION_REQ.get(u, params={"name":h,"type":"A"},
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

# ══════════════════════════════════════════════════════════════
# i18n + colored buttons (ported from Soroosh)
# ══════════════════════════════════════════════════════════════
LANG_FILE = os.path.join(DATA_DIR, "lang.json")
_LANG = {"v": None}
def _get_lang():
    if _LANG["v"]: return _LANG["v"]
    try:
        if os.path.exists(LANG_FILE):
            _LANG["v"] = json.load(open(LANG_FILE, encoding="utf-8")).get("v","fa")
        else: _LANG["v"] = "fa"
    except Exception: _LANG["v"] = "fa"
    return _LANG["v"]
def _set_lang(v):
    _LANG["v"] = v
    try:
        with open(LANG_FILE, "w", encoding="utf-8") as f:
            json.dump({"v": v}, f, ensure_ascii=False)
    except Exception: pass
def is_en(): return _get_lang() == "en"

_SC = str.maketrans({"a":"ᴀ","b":"ʙ","c":"ᴄ","d":"ᴅ","e":"ᴇ","f":"ꜰ","g":"ɢ","h":"ʜ","i":"ɪ","j":"ᴊ","k":"ᴋ","l":"ʟ","m":"ᴍ","n":"ɴ","o":"ᴏ","p":"ᴘ","q":"ǫ","r":"ʀ","s":"ꜱ","t":"ᴛ","u":"ᴜ","v":"ᴠ","w":"ᴡ","x":"x","y":"ʏ","z":"ᴢ","A":"ᴀ","B":"ʙ","C":"ᴄ","D":"ᴅ","E":"ᴇ","F":"ꜰ","G":"ɢ","H":"ʜ","I":"ɪ","J":"ᴊ","K":"ᴋ","L":"ʟ","M":"ᴍ","N":"ɴ","O":"ᴏ","P":"ᴘ","Q":"ǫ","R":"ʀ","S":"ꜱ","T":"ᴛ","U":"ᴜ","V":"ᴠ","W":"ᴡ","X":"x","Y":"ʏ","Z":"ᴢ"})
def SC(s): return str(s).translate(_SC) if is_en() else str(s)

_TR = {
 "panel":{"fa":"پنل","en":"panel"},"accounts_n":{"fa":"اکانت‌ها","en":"accounts"},
 "send":{"fa":"ارسال","en":"send"},"joiner":{"fa":"جوینر","en":"joiner"},
 "lefter":{"fa":"لفتر","en":"lefter"},"templates":{"fa":"قالب‌ها","en":"templates"},
 "pv":{"fa":"پیوی","en":"pv"},"stats":{"fa":"آمار","en":"stats"},
 "errors":{"fa":"خطاها","en":"errors"},"cache":{"fa":"کش","en":"cache"},
 "linkdonies":{"fa":"لینک‌دونی","en":"linkdonies"},"settings":{"fa":"تنظیمات","en":"settings"},
 "back_to_panel":{"fa":"بازگشت به پنل","en":"back to panel"},"back":{"fa":"بازگشت","en":"back"},
 "cancel":{"fa":"لغو","en":"cancel"},"next":{"fa":"بعدی »","en":"next »"},
 "prev":{"fa":"« قبلی","en":"« prev"},"yes":{"fa":"بله","en":"yes"},"no":{"fa":"خیر","en":"no"},
 "confirm":{"fa":"تایید","en":"confirm"},"start":{"fa":"شروع","en":"start"},
 "stop":{"fa":"توقف","en":"stop"},"add":{"fa":"افزودن","en":"add"},
 "delete":{"fa":"حذف","en":"delete"},"clear":{"fa":"پاک","en":"clear"},
 "toggle_on":{"fa":"روشن کن","en":"turn on"},"toggle_off":{"fa":"خاموش کن","en":"turn off"},
 "on":{"fa":"روشن","en":"on"},"off":{"fa":"خاموش","en":"off"},
 "all":{"fa":"همه","en":"all"},"empty":{"fa":"خالی","en":"empty"},
 "loading":{"fa":"در حال بارگذاری...","en":"loading..."},"not_found":{"fa":"پیدا نشد.","en":"not found."},
 "saved":{"fa":"ذخیره شد","en":"saved"},"deleted":{"fa":"حذف شد","en":"deleted"},
 "cleared":{"fa":"پاک شد","en":"cleared"},"restarted":{"fa":"ری‌استارت شد","en":"restarted"},
 "enter":{"fa":"بفرست","en":"send"},"phone":{"fa":"شماره","en":"phone"},"id":{"fa":"شناسه","en":"id"},
 "name":{"fa":"نام","en":"name"},"last_name":{"fa":"فامیل","en":"last name"},
 "username":{"fa":"یوزرنیم","en":"username"},"bio":{"fa":"بیو","en":"bio"},
 "about":{"fa":"درباره","en":"about"},"photo":{"fa":"عکس","en":"photo"},
 "profile":{"fa":"پروفایل","en":"profile"},"channels":{"fa":"کانال‌ها","en":"channels"},
 "create_channel":{"fa":"ساخت کانال","en":"create channel"},"channel_title":{"fa":"عنوان","en":"title"},
 "description":{"fa":"توضیحات","en":"description"},"public":{"fa":"عمومی","en":"public"},
 "private":{"fa":"خصوصی","en":"private"},"type":{"fa":"نوع","en":"type"},
 "link":{"fa":"لینک","en":"link"},"get_link":{"fa":"دریافت لینک","en":"get link"},
 "set_link":{"fa":"ثبت لینک","en":"set link"},"seen":{"fa":"دیده‌شده","en":"seen"},
 "banned":{"fa":"بلاک‌شده","en":"banned"},"ld_progress":{"fa":"پیشرفت لینک‌دونی","en":"linkdoni progress"},
 "clear_seen":{"fa":"پاک دیده‌شده","en":"clear seen"},"clear_banned":{"fa":"پاک بلاک‌شده","en":"clear banned"},
 "clear_both":{"fa":"پاک هر دو","en":"clear both"},"reset_ld":{"fa":"ریست پیشرفت","en":"reset ld progress"},
 "wipe_all":{"fa":"پاک کردن همه","en":"wipe all"},"select_account":{"fa":"یک اکانت انتخاب کن","en":"select an account"},
 "pv_auto":{"fa":"پاسخ خودکار پیوی","en":"auto-reply pv"},"pv_status":{"fa":"وضعیت","en":"status"},
 "pv_active":{"fa":"فعال","en":"on"},"pv_inactive":{"fa":"خاموش","en":"off"},
 "pv_poller":{"fa":"پولر","en":"poller"},"pv_max":{"fa":"سقف/کاربر","en":"max/user"},
 "pv_delay":{"fa":"تایمر","en":"delay"},"pv_notify":{"fa":"اعلان","en":"notify"},
 "pv_poll":{"fa":"هر چند ثانیه","en":"poll"},"pv_items":{"fa":"پیام‌ها","en":"items"},
 "pv_custom":{"fa":"سفارشی","en":"custom"},"pv_add_text":{"fa":"افزودن متن","en":"+ text"},
 "pv_add_file":{"fa":"افزودن فایل","en":"+ file"},"pv_add_delay":{"fa":"افزودن تاخیر","en":"+ delay"},
 "pv_list":{"fa":"لیست پیام‌ها","en":"items"},"pv_report":{"fa":"گزارش","en":"report"},
 "pv_reset_counter":{"fa":"ریست شمارنده","en":"reset counter"},"pv_reset_custom":{"fa":"حذف سفارشی","en":"reset custom"},
 "pv_restart":{"fa":"ری‌استارت","en":"restart"},"pv_delay_q":{"fa":"تایمر (0=آنی):","en":"delay (0=instant):"},
 "pv_poll_q":{"fa":"هر چند ثانیه؟ (حداقل 2):","en":"poll seconds (>=2):"},
 "pv_text_q":{"fa":"متن:","en":"text:"},"pv_file_q":{"fa":"پیام/عکس/فایل:","en":"send msg/photo/file:"},
 "pv_delaysec_q":{"fa":"ثانیه:","en":"seconds:"},"pv_report_title":{"fa":"گزارش پیوی","en":"pv report"},
 "pv_total":{"fa":"کل","en":"total"},"pv_page":{"fa":"صفحه","en":"page"},
 "pv_no_accounts":{"fa":"هیچ اکانتی نداری.","en":"no accounts yet."},
 "add_account":{"fa":"افزودن اکانت","en":"add account"},"groups":{"fa":"گروه‌ها","en":"groups"},
 "pvs":{"fa":"پیوی","en":"pvs"},"bots":{"fa":"ربات‌ها","en":"bots"},
 "channels_created":{"fa":"کانال ساخته","en":"channels created"},
 "listener_status":{"fa":"لیسنر","en":"listener"},"delete_account":{"fa":"حذف اکانت","en":"delete account"},
 "refresh_stats":{"fa":"بروزرسانی آمار","en":"refresh stats"},"refresh_all":{"fa":"بروزرسانی همه","en":"refresh all"},
 "auto_tar":{"fa":"اتو تار","en":"auto-tar"},"listen":{"fa":"لیسنر","en":"listener"},
 "prof_first_q":{"fa":"نام:","en":"first name:"},"prof_last_q":{"fa":"فامیل:","en":"last name:"},
 "prof_bio_q":{"fa":"بیو:","en":"bio:"},"prof_user_q":{"fa":"یوزرنیم:","en":"username:"},
 "prof_set_photo":{"fa":"تنظیم عکس جدید","en":"set new photo"},"prof_del_photo":{"fa":"حذف عکس‌ها","en":"delete photos"},
 "prof_send_photo":{"fa":"عکس رو بفرست:","en":"send photo:"},"prof_no_photo":{"fa":"عکس نبود.","en":"no photo."},
 "prof_deleting":{"fa":"در حال حذف...","en":"deleting..."},"prof_uploading":{"fa":"در حال آپلود...","en":"uploading..."},
 "ch_new_type":{"fa":"نوع کانال:","en":"channel type:"},"ch_new_name_q":{"fa":"اسم کانال:","en":"channel name:"},
 "ch_new_user_q":{"fa":"یوزرنیم:","en":"username:"},"ch_creating":{"fa":"در حال ساخت...","en":"creating..."},
 "ch_created":{"fa":"ساخته شد","en":"created"},"ch_no_channels":{"fa":"هنوز کانالی نساختی.","en":"no channels yet."},
 "ch_created_list":{"fa":"کانال‌های من","en":"my channels"},"ld_auto_join":{"fa":"جوین خودکار","en":"auto-join"},
 "ld_progress_per_acc":{"fa":"پیشرفت برای هر اکانت جداست","en":"progress per account"},
 "ld_add_q":{"fa":"لینک:","en":"link:"},"ld_reset_prog":{"fa":"بازنشانی پیشرفت همه","en":"reset all progress"},
 "ld_reset_list":{"fa":"بازنشانی لیست","en":"reset list"},"ld_add":{"fa":"افزودن","en":"+ add"},
 "op_joiner":{"fa":"جوینر","en":"joiner"},"op_lefter":{"fa":"لفتر","en":"lefter"},
 "op_autotar":{"fa":"اتو تار","en":"auto-tar"},"op_send":{"fa":"ارسال","en":"send"},
 "op_running":{"fa":"در حال اجرا","en":"running"},"op_paused":{"fa":"متوقف","en":"paused"},
 "op_queued":{"fa":"در صف","en":"queued"},"op_done":{"fa":"تکمیل","en":"done"},
 "op_failed":{"fa":"خطا","en":"failed"},"op_cancelled":{"fa":"لغو شده","en":"cancelled"},
 "op_empty":{"fa":"خالی","en":"empty"},"op_draft":{"fa":"پیش‌نویس","en":"draft"},
 "op_joined":{"fa":"جوین","en":"joined"},"op_sent":{"fa":"ارسال","en":"sent"},
 "op_left":{"fa":"ترک","en":"left"},"op_failed_c":{"fa":"خطا","en":"failed"},
 "op_tried":{"fa":"تلاش","en":"tried"},"op_wave":{"fa":"موج","en":"wave"},
 "op_round":{"fa":"دور","en":"round"},"op_phase":{"fa":"مرحله","en":"phase"},
 "op_limit":{"fa":"سقف","en":"limit"},"op_already":{"fa":"قبلا عضو","en":"already"},
 "op_blocked":{"fa":"بلاک","en":"blocked"},"op_skipped_seen":{"fa":"دیده‌شده","en":"seen"},
 "op_skipped_banned":{"fa":"بلاک‌شده","en":"banned"},"op_rejected":{"fa":"غیرفعال","en":"inactive"},
 "stats_title":{"fa":"آمار","en":"stats"},"stats_done":{"fa":"موفق","en":"done"},
 "stats_failed":{"fa":"ناموفق","en":"failed"},"stats_errors":{"fa":"خطاها","en":"errors"},
 "stats_running":{"fa":"در حال اجرا","en":"running now"},"errors_none":{"fa":"خالی","en":"empty"},
 "cfg_title":{"fa":"تنظیمات","en":"settings"},"cfg_lang":{"fa":"زبان","en":"language"},
 "cfg_lang_fa":{"fa":"فارسی","en":"persian"},"cfg_lang_en":{"fa":"انگلیسی","en":"english"},
 "cfg_value_q":{"fa":"مقدار جدید برای {k}:","en":"new value for {k}:"},
 "mode":{"fa":"حالت","en":"mode"},"max":{"fa":"سقف","en":"max"},"text":{"fa":"متن","en":"text"},
 "target":{"fa":"مقصد","en":"target"},"delay":{"fa":"تاخیر","en":"delay"},"file":{"fa":"فایل","en":"file"},
 "vars":{"fa":"متغیرها","en":"vars"},"chat":{"fa":"چت","en":"chat"},
 "sender":{"fa":"فرستنده","en":"sender"},"from":{"fa":"از","en":"from"},
 "debug":{"fa":"عیب‌یابی","en":"debug"},"link_sent":{"fa":"لینک","en":"link"},"failed":{"fa":"ناموفق","en":"failed"},
 "lf_title":{"fa":"لفتر","en":"lefter"},"lf_mode":{"fa":"حالت ترک","en":"leave mode"},
 "lf_mode_all":{"fa":"همه گروه‌ها و کانال‌ها","en":"all chats"},
 "lf_mode_groups":{"fa":"فقط گروه‌ها","en":"groups only"},
 "lf_mode_channels":{"fa":"فقط کانال‌ها","en":"channels only"},
 "lf_mode_closed":{"fa":"فقط گروه‌های بسته","en":"closed groups"},
 "lf_delay":{"fa":"تاخیر","en":"delay"},
 "at_title":{"fa":"قالب‌ها","en":"templates"},"at_desc":{"fa":"قالب = ست کامل از تنظیمات","en":"template = full config set"},
 "at_new":{"fa":"ساخت قالب","en":"+ new template"},"at_channel":{"fa":"کانال","en":"channel"},
 "at_profile":{"fa":"پروفایل","en":"profile"},"at_joiner":{"fa":"جوین","en":"joiner"},
 "at_sender":{"fa":"ارسال","en":"sender"},"at_pv":{"fa":"پیوی","en":"pv"},
 "at_lefter":{"fa":"ترک","en":"lefter"},"at_rename":{"fa":"تغییر نام","en":"rename"},
 "at_run":{"fa":"اجرا روی اکانت","en":"run on accounts"},"at_delete":{"fa":"حذف","en":"delete"},
 "at_mode_only":{"fa":"فقط ارسال","en":"send only"},"at_mode_js":{"fa":"جوین + ارسال","en":"join + send"},
 "at_mode_jsl":{"fa":"جوین + ارسال + ترک","en":"join + send + leave"},
 "at_apply_acc":{"fa":"اعمال روی اکانت‌ها","en":"apply to accounts"},
 "at_run_title":{"fa":"اجرای قالب","en":"run template"},"at_rename_q":{"fa":"نام:","en":"name:"},
 "at_delete_q":{"fa":"حذف <b>{n}</b>؟","en":"delete <b>{n}</b>?"},
 "jl_title":{"fa":"جوینر","en":"joiner"},"jl_select":{"fa":"کدام اکانت؟","en":"select accounts"},
 "jl_selected":{"fa":"انتخاب‌شده","en":"selected"},"jl_speed":{"fa":"سرعت","en":"speed"},
 "jl_grp_only":{"fa":"فقط گروه‌ها","en":"groups only"},"jl_max":{"fa":"سقف","en":"max join"},
 "jl_speed_ultra":{"fa":"فوق‌سریع","en":"ultra"},"jl_speed_fast":{"fa":"سریع","en":"fast"},
 "jl_speed_normal":{"fa":"عادی","en":"normal"},"jl_speed_safe":{"fa":"امن","en":"safe"},
 "jl_ld":{"fa":"لینک‌دونی","en":"linkdonies"},"jl_max_q":{"fa":"عدد:","en":"number:"},
 "jl_no_account":{"fa":"اول اکانت اضافه کن.","en":"add an account first."},
 "send_step1":{"fa":"اکانت(ها)","en":"accounts"},"send_step2":{"fa":"متن را بفرست","en":"send text"},
 "send_step3":{"fa":"مقصد؟","en":"target"},"send_step4":{"fa":"حداکثر؟","en":"max"},
 "send_target_pv":{"fa":"پیوی","en":"pv only"},"send_target_gr":{"fa":"گروه‌ها","en":"groups only"},
 "send_target_both":{"fa":"هر دو","en":"both"},"send_grp_only":{"fa":"فقط گروه واقعی","en":"real groups only"},
 "send_infinite":{"fa":"لوپ بی‌نهایت","en":"infinite loop"},"send_loop_delay":{"fa":"بین دورها","en":"loop delay"},
 "send_rescan":{"fa":"اسکن مجدد","en":"rescan each round"},"send_edit":{"fa":"تاخیر ویرایش","en":"edit delay"},
 "send_random":{"fa":"تصادفی","en":"random"},"send_ph_list":{"fa":"لیست جانشین","en":"placeholder list"},
 "send_multi":{"fa":"چند مرحله‌ای","en":"multi-step"},"send_attach":{"fa":"پیوست فایل","en":"attach file"},
 "send_auto_left":{"fa":"ترک خودکار","en":"auto leave"},
 "ph_start":{"fa":"شروع","en":"start"},"ph_connect":{"fa":"اتصال","en":"connecting"},
 "ph_connected":{"fa":"متصل شد: {n}","en":"connected: {n}"},"ph_connect_fail":{"fa":"اتصال ناموفق: {n}","en":"connect failed: {n}"},
 "ph_auto_join":{"fa":"جوین خودکار {i}/{t}","en":"auto-join {i}/{t}"},
 "ph_extract":{"fa":"موج {n}: استخراج","en":"wave {n}: extracting"},
 "ph_deep":{"fa":"موج {n}: اسکن عمیق","en":"wave {n}: deep scan"},
 "ph_wait":{"fa":"انتظار {s}ث ({i}/{t})","en":"wait {s}s ({i}/{t})"},
 "ph_links":{"fa":"موج {n}: {c} لینک","en":"wave {n}: {c} links"},
 "ph_wave_done":{"fa":"موج {n} تمام","en":"wave {n} done"},"ph_no_links":{"fa":"لینک جدید نیامد","en":"no new links"},
 "ph_limit":{"fa":"به سقف رسید","en":"limit reached"},"ph_collecting":{"fa":"جمع‌آوری مخاطبین","en":"collecting targets"},
 "ph_sending":{"fa":"ارسال به {n}","en":"sending to {n}"},"ph_loop":{"fa":"دور {n}","en":"loop {n}"},
 "ph_send_final":{"fa":"ارسال نهایی","en":"send final"},"ph_update_prof":{"fa":"بروزرسانی پروفایل","en":"updating profile"},
 "ph_create_ch":{"fa":"ساخت کانال: {n}","en":"creating channel: {n}"},
 "ph_leaving":{"fa":"ترک کردن ({m})","en":"leaving ({m})"},"ph_no_targets":{"fa":"مخاطبی نیست","en":"no targets"},
 "ph_nothing":{"fa":"چیزی نیست","en":"nothing"},"ph_done":{"fa":"پایان","en":"done"},
 "ph_cancelled":{"fa":"لغو شد","en":"cancelled"},"ph_error":{"fa":"خطا: {n}","en":"error: {n}"},
 "ph_progress":{"fa":"پیشرفت {a}/{b}","en":"progress {a}/{b}"},
 "ph_acc_suspend":{"fa":"اکانت {n} معلق شده","en":"account {n} suspended"},
 "ph_new_pv":{"fa":"پیام خصوصی جدید از {u}","en":"new pv from {u}"},
 "ph_reply_ok":{"fa":"پاسخ موفق به {u}","en":"reply ok: {u}"},
 "ph_reply_fail":{"fa":"پاسخ ناموفق به {u}: {e}","en":"reply failed: {u}: {e}"},
}
def T(k, **kw):
    e = _TR.get(k)
    if not e: return str(k)
    lang = _get_lang(); s = e.get(lang) or e.get("en") or str(k)
    for a, b in kw.items(): s = s.replace("{"+a+"}", str(b))
    return s

def _style_for(data):
    d = str(data or "").lower()
    if ":delok" in d or d.endswith(":go") or ":run_go" in d or ":run_acc" in d: return "success"
    if d.startswith("acc:add") or d.startswith("chnew:start") or d == "at:new": return "success"
    if ":add_text" in d or ":add_saved" in d or ":add_delay" in d: return "success"
    if ":restart" in d or ":refresh" in d: return "success"
    if any(k in d for k in (":accnext",":maxnext",":tgtnext",":composenext",":confirm")): return "success"
    if d.endswith(":del") or ":del:" in d or d.startswith("ld:del:"): return "danger"
    if "cancel" in d: return "danger"
    if d.startswith("op:stop:"): return "danger"
    if d == "err:clear" or "clear_all" in d or "wipe" in d: return "danger"
    if ":clear_seen" in d or ":clear_banned" in d: return "danger"
    if ":reset_ld" in d or ":reset_prog" in d or d.startswith("ld:reset:"): return "danger"
    if d and d != "noop": return "primary"
    return None

def B(l, d, style=None):
    if style is None:
        try: style = _style_for(d)
        except Exception: style = None
    try:
        if style:
            try: return InlineKeyboardButton(l, callback_data=d, style=style)
            except TypeError:
                try: return InlineKeyboardButton(l, callback_data=d, api_kwargs={"style": style})
                except Exception: pass
        return InlineKeyboardButton(l, callback_data=d)
    except Exception:
        return InlineKeyboardButton(l, callback_data=d)

def SEL(active, label): return ("[✓] " if active else "[ ] ") + label
def grid(btns, cols=2): return [btns[i:i+cols] for i in range(0, len(btns), cols)]
def nav(back=None, home=True):
    row = []
    if back: row.append(B(f"« {T('back')}", back))
    if home: row.append(B(T("back_to_panel"), "menu:main"))
    return row
def _line(): return "━" * 32
def head(icon, key, sub=None):
    t = T(key) if key in _TR else str(key)
    if is_en(): t = SC(t)
    s = f"{icon} {t}"
    if sub is not None: s += f"  ({sub})"
    return "\n" + s + "\n" + _line() + "\n\n"
def mrow(emoji, key, value):
    k = T(key) if key in _TR else str(key)
    if is_en(): k = SC(k)
    return f"{emoji} : {k} : {value}"

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
# SafeClient
# ══════════════════════════════════════════════════════════════
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
        old_input = builtins.input
        builtins.input = _no_prompt
        try: await super().start(phone_number=phone_number)
        finally: builtins.input = old_input
        try:
            me = await self.get_me(); self.guid = me.user.user_guid
        except Exception as e:
            raise RuntimeError(f"NO_SESSION: get_me failed — {e}")
        return self
    async def __aexit__(self, *args, **kwargs):
        try: return await super().__aexit__(*args, **kwargs)
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
        if s and ("ERROR" in s or "INVALID" in s or "FAIL" in s or "NOT_" in s): return False
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

# ══════════════════════════════════════════════════════════════
# PATHS / CONSTANTS
# ══════════════════════════════════════════════════════════════
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
KEEPALIVE_SECONDS = 15 * 60

JOINER_CONFIG = {"extract_max_rounds": 20, "join_per_batch": 100, "batch_pause": 2,
    "rate_limit_pause": 20*60, "max_join_per_hour": 500, "join_delay": 0.5}

JL_SPEEDS = [("ultra","jl_speed_ultra",0.3),("fast","jl_speed_fast",1.0),
             ("normal","jl_speed_normal",3.0),("slow","jl_speed_safe",8.0)]

_OP_LOCKS = {}
def _get_op_lock(oid):
    if oid not in _OP_LOCKS: _OP_LOCKS[oid] = asyncio.Lock()
    return _OP_LOCKS[oid]

DEFAULT_CFG = {"delay":8.0,"cooldown":180,"max_parallel":2,"batch_per_account":2,
    "max_attempts":3,"max_channels_per_account":3,"listener":1,
    "listener_service_only":1,"auto_join_linkdoni":1,
    "channels":["@linkdony_rubikas","@lovo_lovoo0"]}

TG_TOKEN = ""
FORCED_OWNER = 0
STATE = {"owner":None,"cancel":None,"job":None,"conv":{},"panel":{},
         "rate_limit_until":0,"listener_seeded":set(),
         "listener_stops":{},"listener_new_count":0}
APP = None
_last_log = [0.0]
_loop_ref = [None]
pending = {}

# ══════════════════════════════════════════════════════════════
# CACHES: seen / banned / ld-progress
# ══════════════════════════════════════════════════════════════
SEEN_FILE = os.path.join(DATA_DIR, "seen_links.json")
BANNED_FILE = os.path.join(DATA_DIR, "banned_groups.json")
LDPROG_FILE = os.path.join(DATA_DIR, "linkdoni_progress.json")
LINK_DONIES_FILE = os.path.join(DATA_DIR, "linkdonies.json")
_SEEN_CACHE, _BANNED_CACHE, _LDPROG_CACHE = {}, {}, {}

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
            all_d = _load(SEEN_FILE, {}); all_d.pop(aid, None); _save(SEEN_FILE, all_d)
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
            all_d = _load(BANNED_FILE, {}); all_d.pop(aid, None); _save(BANNED_FILE, all_d)
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
def _get_ld_last(aid, url):
    try: return int(_load_ldprog(aid).get(url, 0))
    except Exception: return 0
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
            all_d = _load(LDPROG_FILE, {}); all_d.pop(aid, None); _save(LDPROG_FILE, all_d)
        except Exception: pass
    else:
        _LDPROG_CACHE.clear()
        try: _save(LDPROG_FILE, {})
        except Exception: pass

DEFAULT_LINK_DONIES = ["@linkdony_rubikas","@lovo_lovoo0",
                       "@CBkJCCFE1IZHOEMRXTHDONBZMQLEJJGK"]
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
                it.setdefault("status", "pending"); it.setdefault("attempts", 0)
                it.setdefault("last_error", None); it.setdefault("assigned_to", None)
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
                t["attempts"] = t.get("attempts", 0) + 1
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
        for t in self.tasks: s[t["status"]] = s.get(t["status"], 0) + 1
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
    if a:
        sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        for f in glob.glob(sess + "*"):
            try: os.remove(f)
            except Exception: pass
    try: _delete_pv_account(aid)
    except Exception: pass
    try: _clear_seen(aid); _clear_banned(aid); _reset_ld_progress(aid)
    except Exception: pass
def add_account(aid, phone, name, user_guid):
    accounts = list_accounts()
    sess = os.path.join(SESSIONS_DIR, aid)
    accounts[aid] = {"phone": phone, "name": name, "user_guid": user_guid,
        "session_name": sess, "created": int(time.time()), "channels": []}
    save_accounts(accounts); return sess
def remove_channel_from_storage(aid, idx):
    accounts = list_accounts()
    if aid not in accounts: return None
    chans = accounts[aid].get("channels", [])
    if idx < 0 or idx >= len(chans): return None
    removed = chans.pop(idx); accounts[aid]["channels"] = chans
    save_accounts(accounts); return removed
def add_channel_to_storage(aid, ch_data):
    accounts = list_accounts()
    if aid in accounts:
        accounts[aid].setdefault("channels", []).append(ch_data)
        save_accounts(accounts)
def update_channel_field(aid, idx, key, value):
    accounts = list_accounts()
    if aid in accounts and idx < len(accounts[aid].get("channels", [])):
        accounts[aid]["channels"][idx][key] = value
        save_accounts(accounts)
def get_stored_channels(aid):
    a = get_account(aid); return list(a.get("channels") or []) if a else []
def get_own_channel_ids(aid):
    out = set()
    try:
        for ch in get_stored_channels(aid):
            for k in ("id","raw_id","guid"):
                cid = ch.get(k)
                if cid is not None:
                    try: out.add(str(cid))
                    except Exception: pass
    except Exception: pass
    return out

# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════
async def interactive_login_via_rubpy(admin_id, phone):
    loop = asyncio.get_running_loop()
    q = queue.Queue()
    pending[admin_id] = {"step":"login","q": q}
    def fake_input(prompt=""):
        msg = str(prompt).strip() or "مقدار بعدی رو بفرست:"
        asyncio.run_coroutine_threadsafe(tg_send(f"📨 {msg}", parse_mode="HTML"), loop)
        return q.get(timeout=300)
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
        finally: builtins.input = old
    async def job():
        try:
            me = await asyncio.to_thread(worker)
            u = getattr(me, "user", me)
            name = getattr(u, "first_name", None) or phone
            guid = getattr(u, "user_guid", None) or getattr(u, "guid", None)
            add_account(aid, phone, name, guid)
            _spawn_listener_for(aid)
            try: await start_pv_responders()
            except Exception: pass
            await tg_send(f"✅ وارد شد: {name}\n🆔 <code>{aid}</code>\n💾 {sess_path}.rp")
        except Exception as e:
            try: traceback.print_exc()
            except Exception: pass
            for f in glob.glob(sess_path + "*"):
                try: os.remove(f)
                except Exception: pass
            await tg_send(f"❌ لاگین ناموفق: {str(e)[:200]}")
        finally: pending.pop(admin_id, None)
    asyncio.create_task(job())

# ══════════════════════════════════════════════════════════════
# PROFILE / CHANNELS
# ══════════════════════════════════════════════════════════════
async def rubika_set_name(bot, first_name, last_name=None):
    variants = [dict(first_name=first_name, last_name=last_name or ""),
                dict(first_name=first_name)]
    ok, info, err = await _try_methods(bot, ("update_profile","updateProfile",
                                             "set_profile","setProfile"), variants)
    return (True, info) if ok else (False, err)
async def rubika_set_bio(bot, bio):
    variants = [dict(bio=bio), dict(bio=bio, first_name=None, last_name=None)]
    ok, info, err = await _try_methods(bot, ("update_profile","updateProfile",
                                             "set_bio","setBio","update_bio","updateBio"), variants)
    return (True, info) if ok else (False, err)
async def rubika_set_username(bot, username):
    if username and not username.startswith("@"): username = "@" + username
    variants = [dict(username=username), dict(username=username.lstrip("@"))]
    ok, info, err = await _try_methods(bot, ("update_username","set_username","setUsername"), variants)
    return (True, info) if ok else (False, err)
async def rubika_set_photo(bot, my_guid, image_path):
    variants = [dict(object_guid=my_guid, image=image_path, thumbnail_file_id=None),
                dict(object_guid=my_guid, image=image_path)]
    ok, info, err = await _try_methods(bot, ("upload_avatar","uploadAvatar",
                                             "set_avatar","setAvatar"), variants)
    return (True, info) if ok else (False, err)
async def rubika_delete_my_photos(bot, my_guid):
    try:
        fn = getattr(bot, "delete_avatar", None) or getattr(bot, "remove_avatar", None)
        if fn:
            r = fn(object_guid=my_guid)
            if asyncio.iscoroutine(r): r = await r
            return True, "deleted"
        return False, "no-method"
    except Exception as e:
        return False, _fmt_error(e)
async def rubika_get_my_profile(bot):
    out = {"first_name":"","last_name":"","bio":"","username":"","phone":"","user_guid":""}
    try:
        me = await bot.get_me()
        u = getattr(me, "user", me)
        for k in ("first_name","last_name","bio","username","phone","user_guid"):
            v = getattr(u, k, None)
            if v is not None: out[k] = v
    except Exception as e: out["error"] = str(e)[:200]
    return out
async def rubika_check_channel_username(bot, username):
    uname = username.lstrip("@")
    try:
        r = bot.check_channel_username(username=uname)
        if asyncio.iscoroutine(r): r = await r
        status = str(_g(r, "status") or "").upper()
        if "OK" in status and "ERROR" not in status: return True, "آزاد"
        return True, f"status={status}"
    except Exception as e:
        err = _fmt_error(e)
        if _is_username_limit(err): return False, "__LIMIT__"
        if "TAKEN" in err.upper() or "NOT_AVAILABLE" in err.upper():
            return False, f"@{uname} گرفته شده"
        return None, f"خطا: {err}"
async def rubika_set_chat_username(bot, chat_guid, username):
    uname = username.lstrip("@") if username else ""
    if not uname: return False, "یوزرنیم خالی"
    try:
        avail, info_chk = await rubika_check_channel_username(bot, uname)
        if avail is False: return False, info_chk
    except Exception: pass
    errors = []
    for variant in (uname, "@" + uname):
        try:
            r = bot.update_channel_username(channel_guid=chat_guid, username=variant)
            if asyncio.iscoroutine(r): r = await r
            return True, "update_channel_username"
        except Exception as e: errors.append(_fmt_error(e))
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
    ok, info, err = await _try_methods(bot, ("upload_avatar","uploadAvatar",
                                             "set_chat_photo","update_channel_photo"), variants)
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
        for val in ("Private","private"):
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
        variants = [dict(object_guid=guid, request_needed=False),
                    dict(object_guid=guid, request_needed=False, usage_limit=0),
                    dict(object_guid=guid, request_needed=False, expire_time=None),
                    dict(object_guid=guid), dict(chat_id=guid), dict(channel_guid=guid)]
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
            for base in ({"object_guid":guid},{"channel_guid":guid},{"chat_id":guid}):
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
        for name, kw in (("get_info",{"username":bare}),("get_object_by_username",{"username":bare})):
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
                        kind = {"u":"User","c":"Channel","g":"Group"}.get(g[0].lower())
                        return g, kind
            except Exception: continue
    return None, None

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
                        "title": _g(a, "first_name","firstName","title","name","display_name","displayName") or
                                 _g(c, "first_name","firstName","title","name") or "",
                        "username": _g(a, "username","user_name","userName") or "",
                        "is_blocked": bool(_g(a, "is_blocked") or _g(c, "is_blocked")),
                        "raw": _to_plain(c)})
        return out
    except Exception:
        return []

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
            for c in chats if c["type"]=="User" and c["guid"] != my and not c["is_blocked"]]

async def collect_groups(bot):
    chats = await get_all_chats_raw(bot)
    return [{"type":"group","target":c["guid"],"name":c["title"] or c["guid"][:15],
             "raw":c.get("raw")} for c in chats if _is_true_group(c)]

async def _call_get_messages(bot, guid, anchor, limit, sort):
    combos = [((guid,str(anchor),str(limit),sort),{}),((guid,anchor,limit,sort),{}),
              ((guid,str(anchor),limit,sort),{}),((guid,anchor,str(limit),sort),{})]
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
    mid = _g(m, "message_id") or _g(m, "messageId") or _g(m, "id") or ""
    sender = str(_g(m, "sender_id") or _g(m, "author_object_guid") or _g(m, "sender") or "")
    is_mine_raw = _g(m, "is_mine")
    if is_mine_raw is None: is_mine = bool(my_guid) and (sender == str(my_guid))
    else: is_mine = bool(is_mine_raw)
    reply = _g(m, "reply_to_message_id") or _g(m, "reply_to_id") or _g(m, "reply_to") or ""
    typ = _g(m, "type") or "Text"
    if isinstance(typ, int): typ = "Text"
    txt = _g(m, "text") or ""
    if not txt:
        f = _g(m, "file") or _g(m, "photo") or _g(m, "sticker") or _g(m, "voice")
        if isinstance(f, dict): txt = f.get("name") or f.get("file_name") or ""
        elif isinstance(f, str): txt = f
    t = _g(m, "time") or _g(m, "timestamp") or _g(m, "date") or ""
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
    msgs = _g(r, "messages") or []
    if not isinstance(msgs, list): msgs = [msgs] if msgs else []
    return [normalize_message(m, my_guid) for m in msgs if m]

# ══════════════════════════════════════════════════════════════
# SEND HELPERS
# ══════════════════════════════════════════════════════════════
KIND_ICON = {"text":"💬","photo":"🖼","video":"🎬","voice":"🎙","audio":"🎵","document":"📄"}
SEND_METHODS = {"photo":("send_photo","send_image","send_document","send_file"),
    "video":("send_video","send_document","send_file"),
    "voice":("send_voice","send_document","send_file"),
    "audio":("send_music","send_audio","send_document","send_file"),
    "document":("send_document","send_file")}
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
        for kw in ({"object_guid":target,"text":text},{"chat_id":target,"text":text},
                   {"object_guid":target,"message":text}):
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

# ══════════════════════════════════════════════════════════════
# OPS
# ══════════════════════════════════════════════════════════════
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
        return {"done":joined,"failed":failed,"pending":pending,"in_progress":in_prog,"total":total}
    q = TaskQueue(QUEUE_FILE); ids = set(op.get("task_ids") or [])
    s = {"done":0,"failed":0,"pending":0,"in_progress":0,"total":0}
    for t in q.tasks:
        if t.get("id") in ids:
            st = t.get("status", "pending")
            if st in s: s[st] += 1
            s["total"] += 1
    return s
def _op_effective_status(op):
    st = op.get("status", "draft")
    if op.get("type") == "joinlef":
        if st in ("done","failed","cancelled","paused"): return st
        return "running"
    if st == "scheduled":
        if op.get("scheduled_at", 0) > time.time(): return "scheduled"
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
def _op_status_icon(st):
    return {"running":"🟢","paused":"⏸","queued":"⏳","done":"✅","failed":"❌",
            "cancelled":"⛔","scheduled":"⏰","empty":"⚪","draft":"📝"}.get(st, "⚪")
def _op_status_label(st):
    return {"running":"در حال اجرا","paused":"متوقف","queued":"در صف","done":"تکمیل",
            "failed":"با خطا","cancelled":"لغو شده","scheduled":"زمان‌بندی شده",
            "empty":"خالی","draft":"پیش‌نویس"}.get(st, "?")
def _op_progress_bar(op):
    s = _op_stats(op); done = s["done"] + s["failed"]; tot = s["total"] or 0
    if tot == 0:
        if s["in_progress"]: return "▰" * 8 + "▱" * 8 + " در حال آماده‌سازی…", 0
        return "▱" * 16 + " 0%", 0
    pct = int(done * 100 / tot); fill = int(done * 16 / tot)
    return "▰" * fill + "▱" * (16 - fill) + f" {pct}%", pct

# ══════════════════════════════════════════════════════════════
# SENDER WORKER
# ══════════════════════════════════════════════════════════════
class AState:
    def __init__(self, aid): self.aid = aid; self.cd = 0.0; self.n = 0; self.f = 0
    def ready(self): return time.time() >= self.cd
    def cooldown(self, s): self.cd = time.time() + s
    def remaining(self): return max(0, int(self.cd - time.time()))

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
                    if not tasks:
                        await asyncio.sleep(3); continue
                    batch_rl = False
                    for idx, t in enumerate(tasks):
                        if stop.is_set(): break
                        if time.time() < STATE.get("rate_limit_until", 0):
                            await queue_obj.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                            batch_rl = True; break
                        try:
                            payload = t.get("payload") or {"kind":"text","text":cfg.get("message","سلام")}
                            op_id = t.get("op_id", "_")
                            use_forward = t.get("use_forward", True)
                            akey = (aid, op_id)
                            ids = ANCHORS.get(akey)
                            if use_forward and ids is None:
                                try: ids = await send_anchor(bot, my_guid, payload)
                                except Exception as e:
                                    if _is_rate_limit(e):
                                        await queue_obj.requeue_no_attempt([x["id"] for x in tasks[idx:]])
                                        batch_rl = True; break
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
                                batch_rl = True; break
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
                    if batch_rl: continue
        except RuntimeError as e:
            if _is_auth_dead(e):
                add_error("احراز هویت", str(e)[:200], None, nm)
                log(f"❌ {nm}: NO_SESSION — worker stopped"); return
            log(f"⚠️ {aid}: {str(e)[:100]}")
            await queue_obj.requeue_account(aid); st.cooldown(30)
            await asyncio.sleep(10)
        except Exception as e:
            if _is_transient(e):
                log(f"⚠️ {aid} transient: {str(e)[:80]} — cooldown 60s")
                await queue_obj.requeue_account(aid); st.cooldown(60)
                await asyncio.sleep(15)
            else:
                log(f"⚠️ {aid}: {type(e).__name__}")
                await queue_obj.requeue_account(aid); st.cooldown(30)
                await asyncio.sleep(10)

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
            if s["pending"] + s["in_progress"] == 0:
                stop.set(); break
    s_task = asyncio.create_task(status_loop())
    try: await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        s_task.cancel()
        try: await s_task
        except Exception: pass
        await q.clear("in_progress")
    s = q.stats()
    log(f"🎯 تمام! ✅{s['done']} ❌{s['failed']}")

# ══════════════════════════════════════════════════════════════
# JOINER
# ══════════════════════════════════════════════════════════════
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
                        _find_keys(d, ("object_guid","chat_guid","group_guid","channel_guid","guid"), found)
                        guid = (found.get("object_guid") or found.get("chat_guid") or
                                found.get("group_guid") or found.get("channel_guid") or found.get("guid"))
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

JOIN_DEFAULTS = ["@linkdony_rubikas","@lovo_lovoo0","@CBkJCCFE1IZHOEMRXTHDONBZMQLEJJGK"]

async def _joiner_worker_for_account(aid, acc, op_id, join_delay, max_join, auto_msg_text, log):
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
                        op["progress"]["extracted"] = len(ordered); _save_op(op)
            except Exception as e: add_error("استخراج", _fmt_error(e), guid, acc_name)
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
                        except Exception as e: add_error("msg-after-join", _fmt_error(e), res, acc_name)
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
        async with cli as bot: await job(bot)
    except asyncio.CancelledError: raise
    except Exception as e:
        async with lock:
            op = _get_op(op_id)
            if op:
                op["errors"] = op.get("errors") or []
                op["errors"].append(f"{acc_name}: {type(e).__name__}")
                _save_op(op)

async def run_joiner_lefter(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    max_join = op.get("max_join", 0) or 0
    join_delay = float(op.get("join_delay", 0.5))
    auto_msg_text = (op.get("auto_msg") or "").strip()
    op["progress"] = {"joined":0,"failed":0,"total":0,"phase":"شروع","extracted":0,
                      "msg_sent":0,"msg_fail":0,"linkdoni_ok":[],"linkdoni_fail":[],"link_errors":[]}
    op["status"] = "running"; op["errors"] = []
    _save_op(op)
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        t = asyncio.create_task(_joiner_worker_for_account(aid, a, op["id"], join_delay, max_join, auto_msg_text, log))
        tasks.append(t)
    if tasks:
        try: log(f"🚀 Joiner: {len(tasks)} اکانت همزمان (delay={join_delay}s)")
        except Exception: pass
        await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") != "cancelled":
        op2["status"] = "done"; op2["progress"]["phase"] = "تمام"
        op2["finished_at"] = int(time.time()); _save_op(op2)
    _OP_LOCKS.pop(op["id"], None)

# ══════════════════════════════════════════════════════════════
# LEFTER
# ══════════════════════════════════════════════════════════════
async def _lefter_collect(bot, mode="all", exclude_ids=None):
    exclude_ids = exclude_ids or set()
    out = []
    try: chats = await get_all_chats_raw(bot)
    except Exception: return out
    for c in chats or []:
        try:
            ctype = (c.get("type") or "").strip()
            guid = c.get("guid")
            if not guid: continue
            if guid in exclude_ids: continue
            kind = None
            if ctype == "Group": kind = "group"
            elif ctype == "Channel": kind = "channel"
            else: continue
            if mode == "groups" and kind != "group": continue
            if mode == "channels" and kind != "channel": continue
            out.append({"guid":guid,"name":c.get("title") or guid[:15],"kind":kind})
        except Exception: continue
    return out

async def _lefter_leave_one(bot, target):
    guid = target.get("guid"); kind = target.get("kind")
    try:
        if kind == "channel" or (guid and guid[0].lower() == "c"):
            fn = getattr(bot, "join_channel_action", None)
            if fn:
                r = fn(channel_guid=guid, action="Leave")
                if asyncio.iscoroutine(r): r = await r
                return True, None
        fn = getattr(bot, "leave_chat", None) or getattr(bot, "leave_group", None)
        if fn:
            r = fn(chat=guid)
            if asyncio.iscoroutine(r): r = await r
            return True, None
        return False, "no-leave-method"
    except Exception as e:
        msg = str(e).upper()
        if "NOT_MEMBER" in msg or "ALREADY" in msg: return True, "already_left"
        return False, _fmt_error(e)

async def _lefter_worker(aid, acc, op_id, mode, delay, log):
    nm = acc.get("name") or aid
    op = _get_op(op_id)
    if not op: return
    lock = _get_op_lock(op_id); left = 0; failed = 0
    async def _phase(ph):
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["progress"]["phase"] = ph; _save_op(op2)
    try:
        sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        cli = SafeClient(name=sess, _aid=aid)
        async with cli as bot:
            await _phase(T("ph_collecting"))
            own_ids = get_own_channel_ids(aid)
            targets = await _lefter_collect(bot, mode, exclude_ids=own_ids)
            if not targets: await _phase(T("ph_nothing")); return
            async with lock:
                op2 = _get_op(op_id)
                if op2: op2["progress"]["total"] = len(targets); _save_op(op2)
            for t in targets:
                async with lock:
                    op2 = _get_op(op_id)
                    if not op2 or op2.get("status") == "cancelled": return
                ok, err2 = await _lefter_leave_one(bot, t)
                if ok: left += 1
                else: failed += 1; add_error("lefter", err2, t.get("name"), nm)
                async with lock:
                    op2 = _get_op(op_id)
                    if op2:
                        op2["progress"]["joined"] = left
                        op2["progress"]["failed"] = failed
                        op2["progress"]["phase"] = T("ph_progress", a=left, b=len(targets))
                        _save_op(op2)
                if delay > 0: await asyncio.sleep(delay)
            await _phase(f"✓ {left} · ✗ {failed}")
    except asyncio.CancelledError: raise
    except Exception as e: add_error("lefter", _fmt_error(e), None, nm)

async def run_lefter(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    op["progress"] = {"joined":0,"failed":0,"total":0,"phase":T("ph_start")}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(_lefter_worker(aid, a, op["id"],
                     op.get("leave_mode","all"), float(op.get("delay",0.8)), log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled","done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)
    _OP_LOCKS.pop(op["id"], None)

# ══════════════════════════════════════════════════════════════
# TEMPLATES
# ══════════════════════════════════════════════════════════════
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")
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
    else: t.setdefault(section, {})[field] = value
    save_templates(ts)
def new_template(name="قالب جدید"):
    return {
        "id": "tp_" + secrets.token_hex(4), "name": name, "created": int(time.time()),
        "channel": {"type":"private","title":"","username":"","about":"","photo_file":""},
        "profile": {"first_name":"","last_name":"","username":"","bio":"","photo_file":""},
        "joiner": {"max_join":0,"speed":"fast","groups_only":True},
        "sender": {"text":"","target":"groups","mode":"send_only","max_send":0,"delay":1.5,
                   "edit_delay_enabled":False,"edit_delay_seconds":3.0,
                   "edit_delay_random":False,"edit_delay_min":2.0,"edit_delay_max":6.0,
                   "placeholder_text":"سلام","placeholder_random":False,
                   "placeholder_list":"سلام,درود","multi_step_edit":False,
                   "multi_step_middle":"Hi","send_to_existing":True,
                   "attach_file":"","attach_caption":"",
                   "infinite_loop":False,"loop_delay":3.0,"rescan_targets":True},
        "pv": {"enabled":False,"delay_seconds":0,"max_replies":1,
               "notify":True,"notify_on_receive":True,"notify_on_reply":True,
               "poll_seconds":3,"items":[{"kind":"text","text":"سلام 👋"}],
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
            "Link_channel":"", "Username_channel":"", "Title_channel":"",
            "Link_private":"", "Title_private":"",
            "Link_public":"", "Username_public":"", "Title_public":""}

# ══════════════════════════════════════════════════════════════
# PV AUTO-RESPONDER
# ══════════════════════════════════════════════════════════════
PV_ITEMS_FILE = os.path.join(DATA_DIR, "pv_items.json")
PV_COUNTS_FILE = os.path.join(DATA_DIR, "pv_counts.json")
PV_REPORT_FILE = os.path.join(DATA_DIR, "pv_report.json")
PV_ACCOUNT_FILE = os.path.join(DATA_DIR, "pv_per_account.json")
PV_WM_FILE = os.path.join(DATA_DIR, "pv_wm.json")

DEFAULT_PV_ITEMS = {"enabled":False,"delay_seconds":0,"max_replies":1,
    "notify":True,"notify_on_receive":True,"notify_on_reply":True,
    "poll_seconds":3,"items":[{"kind":"text","text":"سلام 👋"}]}
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
    per[aid] = {k: cfg.get(k) for k in ("enabled","delay_seconds","max_replies",
        "notify","notify_on_receive","notify_on_reply","poll_seconds","items")}
    _save(PV_ACCOUNT_FILE, per)
def _has_pv_account(aid):
    per = _load(PV_ACCOUNT_FILE, {})
    return isinstance(per, dict) and aid in per
def _delete_pv_account(aid):
    per = _load(PV_ACCOUNT_FILE, {})
    if isinstance(per, dict): per.pop(aid, None); _save(PV_ACCOUNT_FILE, per)
def _pv_count(aid, uid):
    d = _load(PV_COUNTS_FILE, {}); return int((d.get(aid) or {}).get(str(uid), 0))
def _pv_count_add(aid, uid, delta):
    d = _load(PV_COUNTS_FILE, {}); acc = d.setdefault(aid, {})
    acc[str(uid)] = max(0, int(acc.get(str(uid), 0)) + delta); _save(PV_COUNTS_FILE, d)
def _pv_limit_reached(aid, uid, cfg):
    mx = int(cfg.get("max_replies", 1) or 0)
    return mx > 0 and _pv_count(aid, uid) >= mx

_PV_WM = None; _PV_WM_DIRTY = False
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
        e = {"first_seen":now,"last_seen":now,"count":1,
             "replied":False,"reply_ok":False,"error":None,"blocked":False}
        if info: e.update({k: v for k, v in info.items() if v is not None})
        acc[uid] = e
    _save_pv_report(rep)
def _record_pv_reply(aid, uid, ok, err=None):
    rep = _load_pv_report(); acc = rep.setdefault(aid, {}); uid = str(uid)
    if uid not in acc:
        acc[uid] = {"first_seen":int(time.time()),"last_seen":int(time.time()),
                    "count":1,"replied":False,"reply_ok":False}
    acc[uid]["replied"] = True; acc[uid]["replied_at"] = int(time.time())
    acc[uid]["reply_ok"] = bool(ok)
    if err:
        acc[uid]["error"] = str(err)[:200]
        acc[uid]["blocked"] = "FORBIDDEN" in str(err).upper()
    else: acc[uid]["error"] = None; acc[uid]["blocked"] = False
    _save_pv_report(rep)

PV_LISTENER_TASKS = {}
_PV_REPLY_TASKS = {}
_PV_STOP_EVENTS = {}

async def _sleep_or_stop(ev, sec):
    try: await asyncio.wait_for(ev.wait(), timeout=sec)
    except asyncio.TimeoutError: pass

async def _pv_send_reply(aid, acc, sender_id, user_info, stop_event):
    name = acc.get("name") or aid
    sender_str = str(sender_id); key = f"{aid}:{sender_str}"
    cfg = _load_pv_account(aid)
    cli = None; connected = False; send_ok = True; send_err = None
    def _fail(msg):
        nonlocal send_ok, send_err
        send_ok = False; send_err = str(msg)[:150]
    try:
        for _ in range(int(cfg.get("delay_seconds", 0))):
            if stop_event.is_set(): _pv_count_add(aid, sender_str, -1); return
            await asyncio.sleep(1)
        cfg = _load_pv_account(aid)
        sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        try:
            cli = SafeClient(name=sess, _aid=aid)
            await cli.__aenter__()
            connected = True
        except Exception as e: _fail(f"connect: {_fmt_error(e)}")
        if cli and connected:
            target = sender_id
            for item in cfg.get("items") or []:
                if stop_event.is_set(): break
                kind = item.get("kind", "text")
                try:
                    if kind == "text" and item.get("text"):
                        await send_text_only(cli, target, item["text"])
                    elif kind == "file":
                        fp = item.get("file_path")
                        if fp and os.path.exists(fp):
                            await send_media(cli, target,
                                {"kind":"document","file":fp,"text":item.get("caption") or ""})
                        else: _fail("file")
                    elif kind == "delay":
                        await asyncio.sleep(int(item.get("seconds", 3))); continue
                    await asyncio.sleep(random.uniform(0.8, 1.8))
                except Exception as e:
                    if _is_rate_limit(e): _fail(f"Flood")
                    else: _fail(f"{type(e).__name__}")
    except asyncio.CancelledError:
        if not connected: _pv_count_add(aid, sender_str, -1)
        raise
    except Exception as e: _fail(f"{type(e).__name__}")
    finally:
        if cli:
            try: await cli.__aexit__(None, None, None)
            except Exception: pass
        _PV_REPLY_TASKS.pop(key, None)
    if not connected: _pv_count_add(aid, sender_str, -1)
    try: _record_pv_reply(aid, sender_str, ok=send_ok, err=send_err)
    except Exception: pass
    if cfg.get("notify", True) and cfg.get("notify_on_reply", True):
        u = user_info.get("first_name") or user_info.get("username") or sender_str
        if send_ok: await tg_send(f"✅ {T('ph_reply_ok', u=esc(u))}")
        else: await tg_send(f"❌ {T('ph_reply_fail', u=esc(u), e=esc(send_err or '?'))}")

async def _pv_handle_new_msg(cli, aid, acc, sender_guid, msg):
    cfg = _load_pv_account(aid)
    if not cfg.get("enabled"): return
    uid = str(sender_guid); key = f"{aid}:{uid}"
    info = {"first_name":"","username":""}
    try: _record_pv_visit(aid, uid, info)
    except Exception: pass
    if _pv_limit_reached(aid, uid, cfg): return
    ex = _PV_REPLY_TASKS.get(key)
    if ex and not ex.done(): return
    _pv_count_add(aid, uid, +1)
    if cfg.get("notify", True) and cfg.get("notify_on_receive", True):
        mt = msg.get("text") if isinstance(msg, dict) else ""
        await tg_send(f"🔔 <b>{esc(uid[:20])}</b>: <code>{esc((mt or '📎')[:120])}</code>")
    ev = _PV_STOP_EVENTS.get(aid)
    if ev is None: ev = _PV_STOP_EVENTS[aid] = asyncio.Event()
    _PV_REPLY_TASKS[key] = asyncio.create_task(_pv_send_reply(aid, acc, sender_guid, info, ev))

async def _pv_poller_worker(aid, acc, stop_event):
    global _PV_WM_DIRTY
    name = acc.get("name") or aid
    cli = None; my_guid = None
    print(f"[pv] {name}: poller started")
    try:
        while not stop_event.is_set():
            cfg = _load_pv_account(aid)
            poll = max(2, int(cfg.get("poll_seconds", 3)))
            if not cfg.get("enabled"):
                await _sleep_or_stop(stop_event, poll); continue
            try:
                if cli is None:
                    sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
                    cli = SafeClient(name=sess, _aid=aid)
                    await cli.__aenter__()
                    me = await cli.get_me(); my_guid = me.user.user_guid
                chats = await get_all_chats_raw(cli)
                first = not (_wm_load().get(aid) or {}).get("_init")
                for c in chats or []:
                    if c.get("type") != "User": continue
                    if c.get("is_blocked"): continue
                    uid = c.get("guid")
                    if not uid or uid == my_guid: continue
                    try: msgs = await fetch_messages(cli, uid, limit=1, my_guid=my_guid)
                    except Exception: continue
                    if not msgs: continue
                    last = msgs[0]; mid = last.get("id")
                    if not mid: continue
                    try:
                        if int(mid) <= _wm_get(aid, uid): continue
                    except Exception: continue
                    _wm_set(aid, uid, mid)
                    if first: continue
                    if last.get("is_mine"): continue
                    await _pv_handle_new_msg(cli, aid, acc, uid, last)
                if first:
                    _wm_load().setdefault(aid, {})["_init"] = 1
                    _PV_WM_DIRTY = True
                _wm_flush()
            except asyncio.CancelledError: raise
            except Exception as e:
                print(f"[pv] {name}: {type(e).__name__}")
                if cli:
                    try: await cli.__aexit__(None, None, None)
                    except Exception: pass
                    cli = None
                await _sleep_or_stop(stop_event, 8); continue
            await _sleep_or_stop(stop_event, poll)
    finally:
        _wm_flush()
        if cli:
            try: await cli.__aexit__(None, None, None)
            except Exception: pass
        print(f"[pv] {name}: poller stopped")

async def start_pv_responders():
    for aid, acc in list_accounts().items():
        cfg = _load_pv_account(aid)
        if not cfg.get("enabled"): continue
        existing = PV_LISTENER_TASKS.get(aid)
        if existing and not existing.done(): continue
        stop = asyncio.Event()
        _PV_STOP_EVENTS[aid] = stop
        t = asyncio.create_task(_pv_poller_worker(aid, acc, stop))
        PV_LISTENER_TASKS[aid] = t

def _stop_pv_for_account(aid):
    st = _PV_STOP_EVENTS.pop(aid, None)
    if st:
        try: st.set()
        except Exception: pass
    t = PV_LISTENER_TASKS.pop(aid, None)
    if t and not t.done(): t.cancel()

# ══════════════════════════════════════════════════════════════
# LISTENER (پیام‌های سرویس ورود روبیکا)
# ══════════════════════════════════════════════════════════════
LISTENER_SEEN = {}
LISTENER_SEEN_LOCK = threading.Lock()
LISTENER_MAX_SEEN = 8000
LISTENER_TASKS = {}

def is_login_service_message(chat_title, text):
    title = (chat_title or ""); txt = (text or "")
    tl = title.lower(); xl = txt.lower()
    if "اعلان" in title or "ورود" in title: return True
    if "login" in tl or "login" in xl: return True
    if "کد روبیکا" in txt or "code " in xl or "code:" in xl: return True
    return False
def _listener_should_show(chat_type):
    t = (chat_type or "").strip().lower()
    if t in ("group","channel"): return False
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
        except asyncio.CancelledError: raise
        except RuntimeError as e:
            if _is_auth_dead(e):
                print(f"[listener] {nm}: NO_SESSION — stopped"); return
            await asyncio.sleep(20)
        except Exception: await asyncio.sleep(20)
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
    cfg["listener"] = 0 if int(cfg.get("listener", 1)) else 1
    _save(CFG_FILE, cfg); return int(cfg["listener"])
async def toggle_service_only_cfg():
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    cfg["listener_service_only"] = 0 if int(cfg.get("listener_service_only", 1)) else 1
    _save(CFG_FILE, cfg); return int(cfg["listener_service_only"])

# ══════════════════════════════════════════════════════════════
# KEEPALIVE
# ══════════════════════════════════════════════════════════════
async def keepalive_loop():
    print(f"[keepalive] started (interval={KEEPALIVE_SECONDS}s)")
    await asyncio.sleep(60)
    while True:
        try:
            accounts = list_accounts()
            if not accounts:
                await asyncio.sleep(60); continue
            print(f"[keepalive] tick — {len(accounts)} accounts")
            for aid, acc in accounts.items():
                sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
                if not os.path.exists(sess + ".rp"): continue
                try:
                    cli = SafeClient(name=sess, _aid=aid)
                    async with cli as bot:
                        me = await bot.get_me()
                        nm = getattr(getattr(me, "user", me), "first_name", aid)
                        print(f"[keepalive] {aid}: ok ({nm})")
                except RuntimeError as e:
                    if _is_auth_dead(e):
                        print(f"[keepalive] {aid}: SESSION DEAD")
                        try:
                            await tg_send(f"⚠️ <b>سشن مرده</b>\n📱 {esc(acc.get('name',aid))}\n<code>{esc(str(e)[:150])}</code>")
                        except Exception: pass
                except Exception as e:
                    print(f"[keepalive] {aid}: {type(e).__name__}: {e}")
                await asyncio.sleep(random.uniform(3, 8))
            await asyncio.sleep(KEEPALIVE_SECONDS)
        except asyncio.CancelledError: raise
        except Exception: await asyncio.sleep(60)

# ══════════════════════════════════════════════════════════════
# TELEGRAM UI
# ══════════════════════════════════════════════════════════════
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters as tg_filters)
from telegram.request import HTTPXRequest

HR = "━━━━━━━━━━━━"
PAGE_SIZE = 6
_TMP_EDIT = {}

def esc(s): return _html.escape(str(s if s is not None else ""))
def short(s, n=40):
    s = str(s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n-1] + "…"

def authorized(update):
    try: return update.effective_chat.id == FORCED_OWNER
    except Exception: return False

def load_owner(): return FORCED_OWNER
def save_owner(cid):
    _save(OWNER_FILE, {"owner": FORCED_OWNER})

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
            if "parse entities" in str(e) and parse_mode:
                parse_mode = None; continue
            await asyncio.sleep(1.5 * (attempt + 1))
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
                parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            STATE["panel"][cid] = m.message_id; return
        except Exception:
            await asyncio.sleep(1.5 * (attempt + 1))

async def ask(text, note=None):
    body = (f"⚠️ {esc(note)}\n\n" if note else "") + text
    await panel(body, kb_([B("❌ "+T("cancel"), "conv:cancel")]))

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

# ─── menus ───
def main_kb():
    rows = [[{"text": f"📱 {p}", "callback_data": f"acc:{p}"}] for p in list_accounts().keys()]
    rows.append([{"text": "➕ افزودن اکانت", "callback_data": "add"}])
    return rows
def acc_kb(phone):
    return [[{"text": "🎲 اسم رندوم", "callback_data": f"rn:{phone}"}],
            [{"text": "📊 وضعیت", "callback_data": f"st:{phone}"}],
            [{"text": "🗑 حذف سشن", "callback_data": f"ds:{phone}"},
             {"text": "⚠️ حذف اکانت", "callback_data": f"da:{phone}"}],
            [{"text": "⬅️ برگشت", "callback_data": "home"}]]

async def show_main():
    accounts = list_accounts()
    ops = _load_ops()
    running_ops = [o for o in ops if _op_effective_status(o) == "running"]
    listening = sum(1 for t in LISTENER_TASKS.values() if not t.done())
    txt = head("🤖", "panel", VERSION)
    txt += mrow("📱", "accounts_n", len(accounts)) + "\n"
    txt += mrow("📊", "stats", len(ops)) + "\n"
    if running_ops: txt += mrow("🟢", "op_running", len(running_ops)) + "\n"
    txt += mrow("👂", "listen", listening) + "\n"
    txt += mrow("🔄", "keepalive", f"{KEEPALIVE_SECONDS//60}m") + "\n"
    txt += mrow("👤", "owner", f"<code>{FORCED_OWNER}</code>") + "\n"
    txt += f"\n💾 <code>{esc(DATA_DIR)}</code>"
    await panel(txt, kb_(
        [B("📤 "+T("send"), "send:start"), B("🤝 "+T("joiner"), "send:jl")],
        [B("🚪 "+T("lefter"), "lf:start"), B("🎯 "+T("templates"), "at:menu")],
        [B("📱 "+T("accounts_n"), "menu:acc"), B("💬 "+T("pv"), "menu:pv")],
        [B("📡 "+T("linkdonies"), "ld:list:jl:back_to_settings"), B("🗂 "+T("cache"), "menu:cache")],
        [B("👂 "+T("listen"), "menu:listen"), B("⚙️ "+T("settings"), "menu:cfg")],
        [B("📊 "+T("stats"), "menu:stats"), B("⚠️ "+T("errors"), "menu:errors")],
        [B("🌐 "+("English" if not is_en() else "فارسی"), "cfg:lang")],
    ))

async def show_listen_menu():
    accounts = list_accounts()
    enabled = _listener_cfg_enabled(); service_only = _listener_cfg_service_only()
    txt = head("👂", "listen")
    txt += f"{T('pv_status')}: <b>{'🟢 '+T('on') if enabled else '🔴 '+T('off')}</b>\n"
    txt += f"service only: <b>{'🟢' if service_only else '🔴'}</b>\n\n"
    rows = []
    for aid, a in accounts.items():
        t = LISTENER_TASKS.get(aid); running = t is not None and not t.done()
        icon = "🟢" if running else "⚪"
        rows.append([B(f"{icon} {short(a.get('name','?'),24)}", f"listen:toggle:{aid}")])
    rows.append([B("🔄 "+T("restarted"), "listen:restart")])
    rows.append([B("🔍 service only", "cfg:toggle_service_only")])
    rows.append(nav())
    await panel(txt, kb_(*rows))

async def show_accounts(page=0):
    accounts = list_accounts(); items = list(accounts.items())
    pages = max(1, -(-len(items) // PAGE_SIZE)); page = max(0, min(page, pages-1))
    chunk = items[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    rows = []
    for aid, a in chunk:
        n_ch = len(a.get("channels", []))
        label = f"📱 {short(a.get('name','?'),18)} · {a.get('phone','?')}"
        if n_ch: label += f" · {n_ch}📢"
        rows.append([B(label, f"acc:view:{aid}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"acc:page:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B("▶️", f"acc:page:{page+1}"))
        rows.append(pr)
    rows.append([B("➕ "+T("add_account"), "acc:add")])
    rows.append([B("🏠 "+T("back_to_panel"), "menu:main")])
    txt = head("📱", "accounts_n", len(accounts))
    if not accounts: txt += T("empty")
    await panel(txt, kb_(*rows))

async def show_account_detail(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()))
    n_ch = len(a.get("channels", []))
    t = LISTENER_TASKS.get(aid); ls = "🟢" if (t and not t.done()) else "⚪"
    pv_cfg = _load_pv_account(aid); pv_on = "🟢" if pv_cfg.get("enabled") else "⚪"
    sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
    rp_exists = os.path.exists(sess + ".rp")
    rp_size = os.path.getsize(sess + ".rp") if rp_exists else 0
    txt = head("📱", a.get("name", "?"))
    txt += f"📞 <code>{esc(a.get('phone','—'))}</code>\n"
    txt += f"🆔 <code>{esc(aid)}</code>\n"
    txt += f"📢 {T('channels')}: <b>{n_ch}</b>\n"
    txt += f"👂 {T('listen')}: <b>{ls}</b>   ·   💬 {T('pv')}: <b>{pv_on}</b>\n"
    txt += f"🔍 {T('seen')}: <b>{_seen_count(aid)}</b>  ·  🚫 {T('banned')}: <b>{_banned_count(aid)}</b>\n"
    txt += f"💾 session.rp: <b>{'✅' if rp_exists else '❌'}</b> ({rp_size}B)"
    await panel(txt, kb_(
        [B("📝 "+T("profile"), f"prof:menu:{aid}")],
        [B("📢 "+T("create_channel"), f"chan:new:{aid}"), B("📋 "+T("channels"), f"chan:list:{aid}")],
        [B("💬 "+T("pv"), f"pv:acc:{aid}"), B("👂 "+T("listen"), f"listen:toggle:{aid}")],
        [B("🗂 "+T("cache"), f"cache:acc:{aid}"), B("🎯 "+T("auto_tar"), f"acc:at:{aid}")],
        [B("🚪 "+T("lefter"), f"acc:lf:{aid}")],
        [B("🗑 "+T("delete_account"), f"acc:del:{aid}")],
        [B("⬅️ "+T("accounts_n"), "menu:acc"), B("🏠 "+T("back_to_panel"), "menu:main")]))

async def show_profile_menu(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()))
    await panel(head("📝", "profile", a.get("name","?")),
        kb_([B("👤 "+T("name"), f"prof:set:name:{aid}"), B("📖 "+T("bio"), f"prof:set:bio:{aid}")],
            [B("🔤 "+T("username"), f"prof:set:user:{aid}"), B("🖼 "+T("photo"), f"prof:set:photo:{aid}")],
            [B("🗑 "+T("prof_del_photo"), f"accphoto:del:{aid}")],
            [B("⬅️", f"acc:view:{aid}")]))

async def show_channel_new(aid):
    if not get_account(aid): return await panel(T("not_found"), kb_(nav()))
    await panel(head("📢", "create_channel") + f"🌐 {T('public')} · 🔒 {T('private')}",
        kb_([B("🌐 "+T("public"), f"chan:new_pub:{aid}"),
             B("🔒 "+T("private"), f"chan:new_priv:{aid}")],
            [B("⬅️", f"acc:view:{aid}")]))

async def show_channel_list(aid, page=0):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()))
    chans = list(enumerate(a.get("channels", [])))
    if not chans:
        return await panel(head("📋", "channels") + T("ch_no_channels"),
            kb_([B("➕ "+T("create_channel"), f"chan:new:{aid}")], [B("⬅️", f"acc:view:{aid}")]))
    pages = max(1, -(-len(chans) // PAGE_SIZE)); page = max(0, min(page, pages-1))
    chunk = chans[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    rows = [[B(f"{'🌐' if c.get('is_public') else '🔒'} {short(c.get('title','?'),28)}", f"chan:view:{aid}:{i}")]
            for i, c in chunk]
    if pages > 1:
        pr = []
        if page > 0: pr.append(B("◀️", f"chan:page:{aid}:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B("▶️", f"chan:page:{aid}:{page+1}"))
        rows.append(pr)
    rows.append([B("➕ "+T("add"), f"chan:new:{aid}")])
    rows.append([B("⬅️", f"acc:view:{aid}")])
    await panel(head("📋", "ch_created_list", len(chans)), kb_(*rows))

async def show_channel_view(aid, idx):
    a = get_account(aid); chans = (a or {}).get("channels", [])
    if not a or idx >= len(chans): return await panel(T("not_found"), kb_(nav()))
    ch = chans[idx]
    link = ("@"+ch["username"]) if ch.get("username") else (ch.get("join_link") or "—")
    txt = head("⚙️", ch.get("title", "—"))
    txt += f"{'🌐 '+T('public') if ch.get('is_public') else '🔒 '+T('private')}\n🔗 {esc(link)}"
    await panel(txt, kb_(
        [B("📤 "+T("send"), f"chan:send:{aid}:{idx}")],
        [B("✏️ "+T("name"), f"chan:edit:title:{aid}:{idx}"),
         B("📖 "+T("bio"), f"chan:edit:desc:{aid}:{idx}")],
        [B("🔗 "+T("username"), f"chan:edit:user:{aid}:{idx}"),
         B("🖼 "+T("photo"), f"chan:edit:photo:{aid}:{idx}")],
        [B("🔁 "+T("get_link"), f"chan:mklink:{aid}:{idx}"),
         B("🗑 "+T("delete"), f"chan:del:{aid}:{idx}")],
        [B("⬅️", f"chan:list:{aid}")]))

# ─── Send wizard ───
SCHEDULE_OPTIONS = [("0","⚡️ آنی",0),("1h","۱ ساعت بعد",3600),
                    ("3h","۳ ساعت بعد",3*3600),("12h","۱۲ ساعت بعد",12*3600),
                    ("24h","۲۴ ساعت بعد",24*3600)]
MAX_OPTIONS = [50, 100, 500, 1000]

def _send_conv(cid):
    c = get_conv(cid)
    if "send" not in c:
        c["send"] = {"step":"accounts","accounts":[],"payload":None,
                     "target":"both","max":0,"schedule":0}
    return c["send"]

async def show_send_step(cid):
    s = _send_conv(cid); step = s["step"]
    if step == "accounts": await send_step_accounts(cid, s)
    elif step == "compose": await send_step_compose(cid, s)
    elif step == "target": await send_step_target(cid, s)
    elif step == "max": await send_step_max(cid, s)
    elif step == "schedule": await send_step_schedule(cid, s)
    elif step == "confirm": await send_step_confirm(cid, s)

def _send_summary(s):
    accs = s.get("accounts") or []
    all_a = list_accounts()
    if "all" in accs: acc_label = f"{T('all')} ({len(all_a)})"
    elif not accs: acc_label = "—"
    elif len(accs) == 1:
        a = get_account(accs[0]); acc_label = a.get("name", "?") if a else "?"
    else:
        names = [get_account(aid).get("name","?") for aid in accs[:3] if get_account(aid)]
        acc_label = "، ".join(names) + (f" +{len(accs)-3}" if len(accs) > 3 else "")
    p = s.get("payload")
    if not p: msg_label = "—"
    elif p.get("file"):
        msg_label = f"{KIND_ICON.get(p.get('kind'),'📎')} {p.get('file_name','file')}"
        if p.get("text"): msg_label += f" + «{short(p.get('text'),20)}»"
    else: msg_label = f"💬 «{short(p.get('text'),30)}»"
    tgt = {"pv":T("send_target_pv"),"groups":T("send_target_gr"),
           "both":T("send_target_both")}.get(s.get("target","both"),"?")
    mx = s.get("max", 0) or 0
    mx_label = f"{mx}" if mx else "∞"
    sch = s.get("schedule", 0); sch_label = "آنی"
    if sch > 0:
        for code, label, secs in SCHEDULE_OPTIONS:
            if secs == sch: sch_label = label; break
        else: sch_label = _fmt_time(sch)
    return (f"\n👤 {esc(acc_label)}\n✉️ {esc(msg_label)}\n"
            f"🎯 {esc(tgt)}\n🔢 {esc(mx_label)}\n⏰ {esc(sch_label)}")

async def send_step_accounts(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel(T("jl_no_account"), kb_([B("➕ "+T("add_account"), "acc:add")], nav()))
    sel = set(s.get("accounts") or [])
    rows = []
    for aid, a in accounts.items():
        check = "☑" if (aid in sel or "all" in sel) else "☐"
        rows.append([B(f"{check} {short(a.get('name','?'),22)} · {a.get('phone','?')}", f"send:acc:{aid}")])
    all_sel = ("all" in sel) or (len(sel) >= len(accounts) and accounts)
    rows.append([B("✅ لغو همه" if all_sel else "☑ "+T("all"), "send:accall")])
    rows.append([B("▶️ "+T("next"), "send:accnext")])
    rows.append([B("🏠 "+T("back_to_panel"), "menu:main")])
    txt = head("📤", "send", dots(1,4)) + T("send_step1") + "\n" + _send_summary(s)
    await panel(txt, kb_(*rows))

def dots(cur, total): return "".join("●" if i <= cur else "○" for i in range(1, total+1)) + f"  {cur}/{total}"

async def send_step_compose(cid, s):
    txt = head("📤", "send", dots(2,4)) + T("send_step2") + _send_summary(s)
    rows = []
    if s.get("payload"):
        rows.append([B("✏️", "send:recompose"), B("▶️ "+T("next"), "send:composenext")])
    rows.append([B("⬅️", "send:back"), B("🏠", "menu:main")])
    await panel(txt, kb_(*rows))

async def send_step_target(cid, s):
    tgt = s.get("target", "both")
    rows = [
        [B(("✅ " if tgt=="pv" else "")+"👤 "+T("send_target_pv"), "send:tgt:pv")],
        [B(("✅ " if tgt=="groups" else "")+"👥 "+T("send_target_gr"), "send:tgt:groups")],
        [B(("✅ " if tgt=="both" else "")+"📨 "+T("send_target_both"), "send:tgt:both")],
        [B("▶️ "+T("next"), "send:tgtnext")],
        [B("⬅️", "send:prev"), B("🏠", "menu:main")],
    ]
    await panel(head("📤", "send", dots(3,4)) + T("send_step3") + _send_summary(s), kb_(*rows))

async def send_step_max(cid, s):
    mx = s.get("max", 0); rows = []
    row = [B(("✅ " if mx == n else "") + f"{n}", f"send:max:{n}") for n in MAX_OPTIONS[:3]]
    rows.append(row)
    row2 = [B(("✅ " if mx == n else "") + f"{n}", f"send:max:{n}") for n in MAX_OPTIONS[3:]]
    if row2: rows.append(row2)
    rows.append([B(("✅ " if mx==0 else "")+"♾ ∞", "send:max:0")])
    rows.append([B("✏️", "send:max:custom")])
    rows.append([B("▶️ "+T("next"), "send:maxnext")])
    rows.append([B("⬅️", "send:prev"), B("🏠", "menu:main")])
    await panel(head("📤", "send", dots(4,4)) + T("send_step4") + _send_summary(s), kb_(*rows))

async def send_step_schedule(cid, s):
    sch = s.get("schedule", 0)
    rows = [[B(("✅ " if sch == 0 else "")+"⚡️ آنی", "send:sch:0")]]
    row = [B(("✅ " if sch == secs else "")+label, f"send:sch:{code}")
           for code, label, secs in SCHEDULE_OPTIONS[1:3]]
    if row: rows.append(row)
    row = [B(("✅ " if sch == secs else "")+label, f"send:sch:{code}")
           for code, label, secs in SCHEDULE_OPTIONS[3:]]
    if row: rows.append(row)
    rows.append([B("▶️ "+T("confirm"), "send:schedulenext")])
    rows.append([B("⬅️", "send:prev"), B("🏠", "menu:main")])
    await panel(head("📤", "send", "5/5") + _send_summary(s), kb_(*rows))

async def send_step_confirm(cid, s):
    await panel("⏳ ...")
    accounts = list_accounts(); sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "accounts"; return await panel(T("empty"), kb_(nav()))
    tgt = s.get("target", "both")
    total_targets = []; errors = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        try:
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot:
                pv = await collect_pv(bot) if tgt in ("pv","both") else []
                gr = await collect_groups(bot) if tgt in ("groups","both") else []
            for it in pv:
                it["owner_account"] = aid
                it["payload"] = s.get("payload") or {"kind":"text","text":"سلام"}
                total_targets.append(it)
            for it in gr:
                it["owner_account"] = aid
                it["payload"] = s.get("payload") or {"kind":"text","text":"سلام"}
                total_targets.append(it)
        except Exception as e: errors.append(f"{a.get('name','?')}: {type(e).__name__}")
    mx = s.get("max", 0) or 0
    if mx and len(total_targets) > mx: total_targets = total_targets[:mx]
    s["_targets"] = total_targets; s["_analysis_errors"] = errors
    txt = head("📊", "confirm") + f"📦 {len(total_targets)}\n"
    if errors: txt += f"⚠️ {len(errors)}\n"
    txt += _send_summary(s)
    rows = []
    if total_targets: rows.append([B("✅ "+T("confirm"), "send:go")])
    rows.append([B("⚠️ "+T("errors"), "menu:errors")])
    rows.append([B("✏️", "send:back_edit")])
    rows.append([B("❌ "+T("cancel"), "send:cancel")])
    await panel(txt, kb_(*rows))

# ─── Joiner wizard ───
def _jl_conv(cid):
    c = get_conv(cid)
    if "jl" not in c:
        c["jl"] = {"step":"account","accounts":[],"max_join":0,"speed":"fast","auto_msg":""}
    return c["jl"]

async def show_jl_step(cid):
    s = _jl_conv(cid)
    if s["step"] == "account": await jl_step_account(cid, s)
    if s["step"] == "settings": await jl_step_settings(cid, s)
    if s["step"] == "max": await jl_step_max(cid, s)
    if s["step"] == "confirm": await jl_step_confirm(cid, s)

async def jl_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel(T("jl_no_account"), kb_([B("➕ "+T("add_account"), "acc:add")], nav()))
    sel = set(s.get("accounts") or [])
    rows = []
    for aid, a in accounts.items():
        check = "☑" if aid in sel else "☐"
        rows.append([B(f"{check} {short(a.get('name','?'),22)} · {a.get('phone','?')}", f"jl:acc:{aid}")])
    rows.append([B("▶️ "+T("next"), "jl:next")])
    rows.append([B("🏠", "menu:main")])
    await panel(head("🤝", "joiner", "1/4") + T("jl_select"), kb_(*rows))

async def jl_step_settings(cid, s):
    speed = s.get("speed", "fast")
    speed_label = next((T(l) for k, l, _ in JL_SPEEDS if k == speed), "—")
    auto = (s.get("auto_msg") or "").strip()
    txt = head("⚙️", "settings") + f"🚀 {T('jl_speed')}: <b>{speed_label}</b>\n"
    txt += f"✉️ {T('text')}: <b>{'🟢' if auto else '🔴'}</b>\n"
    if auto: txt += f"\n💬 <code>{esc(auto[:300])}</code>"
    rows = []; row = []
    for k, label, _ in JL_SPEEDS:
        row.append(B(("✅ " if speed == k else "")+T(label), f"jl:speed:{k}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([B("✏️ "+T("text"), "jl:setauto")])
    if auto: rows.append([B("🗑", "jl:clrauto")])
    rows.append([B("▶️ "+T("next"), "jl:next")])
    rows.append([B("⬅️", "jl:back"), B("🏠", "menu:main")])
    await panel(txt, kb_(*rows))

async def jl_step_max(cid, s):
    mx = s.get("max_join", 0); rows = []
    rows.append([B(("✅ " if mx == n else "") + f"{n}", f"jl:max:{n}") for n in [50,100,200]])
    rows.append([B(("✅ " if mx == n else "") + f"{n}", f"jl:max:{n}") for n in [500,1000,2000]])
    rows.append([B(("✅ " if mx==0 else "")+"♾ ∞", "jl:max:0")])
    rows.append([B("✏️", "jl:max:custom")])
    rows.append([B("▶️ "+T("next"), "jl:next")])
    rows.append([B("⬅️", "jl:back")])
    await panel(head("🤝", "joiner", T("jl_max")), kb_(*rows))

async def jl_step_confirm(cid, s):
    accounts = list_accounts(); sel = s.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    if not sel:
        s["step"] = "account"; return await panel(T("empty"), kb_(nav()))
    speed = s.get("speed", "fast")
    speed_label = next((T(l) for k, l, _ in JL_SPEEDS if k == speed), "—")
    auto = (s.get("auto_msg") or "").strip()
    txt = head("🤝", "confirm")
    txt += f"👤 <b>{len(sel)}</b>\n"
    txt += f"🚀 {T('jl_speed')}: <b>{speed_label}</b>\n"
    txt += f"🔢 {T('jl_max')}: <b>{s.get('max_join',0) or '∞'}</b>\n"
    txt += f"✉️ {T('text')}: <b>{'🟢' if auto else '🔴'}</b>"
    if auto: txt += f"\n💬 <code>{esc(auto[:300])}</code>"
    await panel(txt, kb_(
        [B("🚀 "+T("start"), "jl:go")],
        [B("✏️", "jl:back")],
        [B("❌ "+T("cancel"), "jl:cancel")]))

# ─── Lefter wizard ───
def _lf_conv(cid):
    c = get_conv(cid)
    if "lf" not in c: c["lf"] = {"step":"account","accounts":[],"mode":"all","delay":0.8}
    return c["lf"]
def _lf_modes():
    return [("all","lf_mode_all"),("groups","lf_mode_groups"),
            ("channels","lf_mode_channels"),("closed","lf_mode_closed")]

async def show_lf_step(cid):
    s = _lf_conv(cid)
    if s["step"] == "account": await lf_step_account(cid, s)
    if s["step"] == "mode": await lf_step_mode(cid, s)
    if s["step"] == "delay": await lf_step_delay(cid, s)

async def lf_step_account(cid, s):
    accounts = list_accounts()
    if not accounts:
        return await panel(T("jl_no_account"), kb_([B("➕ "+T("add_account"), "acc:add")], nav()))
    sel = set(s.get("accounts") or [])
    rows = []
    for aid, a in accounts.items():
        check = "☑" if aid in sel else "☐"
        rows.append([B(f"{check} {short(a.get('name','?'),22)}", f"lf:acc:{aid}")])
    rows.append([B("▶️ "+T("next"), "lf:next")])
    rows.append([B("🏠", "menu:main")])
    await panel(head("🚪", "lefter", dots(1,3)) + T("jl_select"), kb_(*rows))

async def lf_step_mode(cid, s):
    mode = s.get("mode", "all")
    btns = [B(SEL(mode == k, T(l)), f"lf:mode:{k}") for k, l in _lf_modes()]
    rows = [[b] for b in btns]
    rows.append([B("▶️ "+T("next"), "lf:next")])
    rows.append([B("⬅️", "lf:back")])
    await panel(head("🚪", "lefter", dots(2,3)) + T("lf_mode"), kb_(*rows))

async def lf_step_delay(cid, s):
    d = s.get("delay", 0.8)
    mk = lambda n, l: B(SEL(abs(d - n) < 0.01, l), f"lf:delay:{n}")
    txt = head("🚪", "lefter", dots(3,3)) + f"⏱ {T('delay')}: <b>{d}s</b>"
    rows = [[mk(0.3,"🚀 0.3s"), mk(0.8,"⚡ 0.8s"), mk(1.5,"🐢 1.5s")],
            [mk(3.0,"🛡 3s")],
            [B("🚀 "+T("start"), "lf:go")],
            [B("⬅️", "lf:back")]]
    await panel(txt, kb_(*rows))

# ─── Templates UI ───
async def show_at_menu():
    tpls = list_templates()
    txt = head("🎯", "at_title", len(tpls))
    txt += f"<i>{T('at_desc')}</i>"
    rows = []
    for tid, t in list(tpls.items())[:8]:
        parts = []
        if t.get("channel", {}).get("title"): parts.append("🌐" if t.get("channel",{}).get("type")=="public" else "🔒")
        if t.get("profile", {}).get("first_name") or t.get("profile", {}).get("bio"): parts.append("📝")
        if int(t.get("joiner", {}).get("max_join", 0) or 0) > 0: parts.append("🤝")
        if t.get("sender", {}).get("text"): parts.append("📤")
        if (t.get("pv") or {}).get("items"): parts.append("💬")
        badge = " ".join(parts) or "∅"
        rows.append([B(f"🎯 {short(t.get('name','?'),16)} · {badge}", f"at:{tid}:view")])
    rows.append([B("➕ "+T("at_new"), "at:new")])
    rows.append(nav())
    await panel(txt, kb_(*rows))

async def show_at_view(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    ch = t.get("channel", {}); pr = t.get("profile", {})
    jn = t.get("joiner", {}); sn = t.get("sender", {})
    lf = t.get("lefter", {}); pv = t.get("pv", {})
    def bd(d, k): return "🟢" if d.get(k) else "⚪"
    def bdn(d, k): return "🟢" if int(d.get(k, 0) or 0) > 0 else "⚪"
    txt = head("🎯", t.get("name", "?"))
    txt += f"🏗 {T('at_channel')}: {bd(ch, 'title')}"
    if ch.get("title"): txt += f" <i>{esc(short(ch['title'],20))}</i>"
    txt += f"\n📝 {T('at_profile')}: {bd(pr,'first_name') or bd(pr,'bio') or bd(pr,'username')}"
    txt += f"\n🤝 {T('at_joiner')}: {bdn(jn,'max_join')}"
    txt += f"\n📤 {T('at_sender')}: {bd(sn,'text')}"
    txt += f"\n💬 {T('at_pv')}: {'🟢' if pv.get('enabled') else '⚪'} · {len(pv.get('items') or [])}"
    txt += f"\n🚪 {T('at_lefter')}: 🟢 <i>{lf.get('leave_mode','?')}</i>"
    rows = grid([
        B(T("at_channel"), f"at:{tid}:ch"), B(T("at_profile"), f"at:{tid}:pr"),
        B(T("at_joiner"), f"at:{tid}:jn"), B(T("at_sender"), f"at:{tid}:sn"),
        B(T("at_pv"), f"at:{tid}:pv"), B(T("at_lefter"), f"at:{tid}:lf"),
        B(T("at_rename"), f"at:{tid}:rename"),
    ])
    rows.append([B(T("at_run"), f"at:{tid}:run")])
    rows.append([B(T("at_delete"), f"at:{tid}:del"), B(T("back_to_panel"), "menu:main")])
    await panel(txt, kb_(*rows))

async def show_at_channel(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    c = t.get("channel", {}); is_pub = c.get("type","private") == "public"
    txt = head("🏗", "at_channel", t.get("name","?"))
    txt += mrow("🔖","type",(T("public") if is_pub else T("private"))) + "\n"
    txt += mrow("📝","channel_title", c.get("title") or "—") + "\n"
    if is_pub: txt += mrow("🔤","username", c.get("username") or "—") + "\n"
    txt += mrow("📖","about", short(c.get("about",""),40) or "—") + "\n"
    txt += mrow("🖼","photo", os.path.basename(c.get("photo_file","")) or "—")
    txt += f"\n\n<b>{T('vars')}</b>: <code>{{n}} {{rnd}} {{Link_private}}</code>"
    rows = [
        [B(SEL(is_pub, T("public")), f"at:{tid}:chtype:public"),
         B(SEL(not is_pub, T("private")), f"at:{tid}:chtype:private")],
        [B(T("channel_title"), f"at:{tid}:chset:title")],
    ]
    if is_pub: rows.append([B(T("username"), f"at:{tid}:chset:username")])
    rows.append([B(T("about"), f"at:{tid}:chset:about")])
    rows.append([B(T("photo"), f"at:{tid}:chset:photo_file")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows))

async def show_at_profile(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    p = t.get("profile", {})
    txt = head("📝","at_profile", t.get("name","?"))
    txt += mrow("👤","name", p.get("first_name") or "—") + "\n"
    txt += mrow("👤","last_name", p.get("last_name") or "—") + "\n"
    txt += mrow("🔤","username", p.get("username") or "—") + "\n"
    txt += mrow("📖","bio", short(p.get("bio",""),60) or "—") + "\n"
    txt += mrow("🖼","photo", os.path.basename(p.get("photo_file","")) or "—")
    rows = [
        [B(T("name"), f"at:{tid}:prset:first_name"), B(T("last_name"), f"at:{tid}:prset:last_name")],
        [B(T("username"), f"at:{tid}:prset:username"), B(T("bio"), f"at:{tid}:prset:bio")],
        [B(T("photo"), f"at:{tid}:prset:photo_file")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows))

async def show_at_joiner(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    j = t.get("joiner", {}); spd = j.get("speed")
    spd_lbl = next((T(l) for k, l, _ in JL_SPEEDS if k == spd), spd)
    txt = head("🤝","at_joiner", t.get("name","?"))
    txt += mrow("🎯","jl_max", j.get("max_join",0)) + "\n"
    txt += mrow("🚀","jl_speed", spd_lbl) + "\n"
    txt += mrow("👥","jl_grp_only", ("🟢" if j.get("groups_only",True) else "⚪"))
    rows = [[B(T("jl_max"), f"at:{tid}:jnset:max_join")]]
    rows += grid([B(SEL(spd == k, T(l)), f"at:{tid}:jnspeed:{k}") for k, l, _ in JL_SPEEDS])
    rows.append([B(SEL(j.get("groups_only",True), T("jl_grp_only")), f"at:{tid}:jntoggle_groups_only")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows))

async def show_at_sender(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    s = t.get("sender", {})
    modes = {"send_only":T("at_mode_only"),"join_send":T("at_mode_js"),"join_send_leave":T("at_mode_jsl")}
    txt = head("📤","at_sender", t.get("name","?"))
    txt += mrow("✉️","text", short(s.get("text",""),50) or "—") + "\n"
    txt += mrow("🎯","target", s.get("target","?")) + "\n"
    txt += mrow("🔁","mode", modes.get(s.get("mode"), s.get("mode"))) + "\n"
    txt += mrow("🔢","max", s.get("max_send",0) or "∞") + "\n"
    txt += mrow("⏱","delay", f"{s.get('delay',1.5)}s")
    rows = [
        [B(T("text"), f"at:{tid}:snset:text")],
        [B(T("target"), f"at:{tid}:snset:target"), B(T("max"), f"at:{tid}:snset:max_send")],
        [B(T("delay"), f"at:{tid}:snset:delay"), B(T("mode"), f"at:{tid}:snmode")],
        nav(f"at:{tid}:view"),
    ]
    await panel(txt, kb_(*rows))

async def show_at_sender_mode(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    cur = t["sender"].get("mode", "send_only")
    opts = [("send_only",T("at_mode_only")),("join_send",T("at_mode_js")),("join_send_leave",T("at_mode_jsl"))]
    rows = grid([B(SEL(cur == k, l), f"at:{tid}:snmode_set:{k}") for k, l in opts])
    rows.append(nav(f"at:{tid}:sn"))
    await panel(head("🔁","mode") + f"<b>{cur}</b>", kb_(*rows))

async def show_at_pv(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    pv = t.get("pv", {}); en = bool(pv.get("enabled"))
    mx = int(pv.get("max_replies",1) or 0); items = pv.get("items") or []
    apply_acc = bool(pv.get("apply_to_accounts", True))
    txt = head("💬","at_pv", t.get("name","?"))
    txt += mrow("📶","pv_status", (T("pv_active") if en else T("pv_inactive"))) + "\n"
    txt += mrow("👥","pv_max", (mx if mx else "∞")) + "\n"
    txt += mrow("⏱","pv_delay", f"{pv.get('delay_seconds',0)}s") + "\n"
    txt += mrow("🔄","at_apply_acc", ("🟢" if apply_acc else "⚪")) + "\n"
    txt += mrow("📨","pv_items", len(items)) + "\n\n"
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"{i}. 💬 <code>{esc(short(it.get('text',''),40))}</code>\n"
        elif k == "file": txt += f"{i}. 📁 <code>{esc(os.path.basename(it.get('file_path','?')))}</code>\n"
        elif k == "delay": txt += f"{i}. ⏸ {it.get('seconds',3)}s\n"
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
    await panel(txt, kb_(*rows))

async def show_at_pv_list(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    items = (t.get("pv") or {}).get("items") or []
    txt = head("📋","pv_list", len(items))
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"\n{i}. 💬 <code>{esc(short(it.get('text',''),60))}</code>"
        elif k == "file": txt += f"\n{i}. 📁 <code>{esc(os.path.basename(it.get('file_path','?')))}</code>"
        elif k == "delay": txt += f"\n{i}. ⏸ {it.get('seconds',3)}s"
    rows = [[B(f"{T('delete')} {i+1}", f"at:{tid}:pv:del:{i}")] for i in range(len(items))]
    rows.append([B(f"« {T('back')}", f"at:{tid}:pv")])
    await panel(txt, kb_(*rows))

async def show_at_lefter(tid):
    t = get_template(tid)
    if not t: return await show_at_menu()
    l = t.get("lefter", {})
    txt = head("🚪","at_lefter", t.get("name","?"))
    txt += f"🎯 {T('lf_mode')}: <b>{l.get('leave_mode','?')}</b>"
    rows = []
    for k, lbl in _lf_modes():
        rows.append([B(SEL(l.get("leave_mode") == k, T(lbl)), f"at:{tid}:lfset:{k}")])
    rows.append(nav(f"at:{tid}:view"))
    await panel(txt, kb_(*rows))

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
        rows.append([B(SEL(aid in selected, short(a.get('name','?'),20)), f"at:{tid}:run_acc:{aid}")])
    if pages > 1:
        pr = []
        if page > 0: pr.append(B(T("prev"), f"at:{tid}:run:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B(T("next"), f"at:{tid}:run:{page+1}"))
        rows.append(pr)
    rows.append([B(T("start"), f"at:{tid}:run_go")])
    rows.append(nav(f"at:{tid}:view"))
    txt = head("🎯","at_run_title", t.get("name","?"))
    txt += f"{T('jl_selected')}: <b>{len(selected)}</b>"
    await panel(txt, kb_(*rows))

async def show_acc_at_menu(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()))
    tpls = list_templates()
    txt = head("🎯","auto_tar", a.get("name","?"))
    if not tpls:
        return await panel(txt + "\n\n" + T("empty"),
            kb_([B("➕ "+T("at_new"), "at:new"), B("🏠", "menu:main")]))
    rows = []
    for tid, t in list(tpls.items())[:10]:
        rows.append([B(f"🎯 {short(t.get('name','?'),22)}", f"acc:at:run:{aid}:{tid}")])
    rows.append(nav(f"acc:view:{aid}"))
    await panel(txt, kb_(*rows))

async def show_acc_lf(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()))
    txt = head("🚪","lefter", a.get("name","?"))
    rows = []
    for k, lbl in _lf_modes():
        rows.append([B(T(lbl), f"acc:lf:go:{aid}:{k}")])
    rows.append(nav(f"acc:view:{aid}"))
    await panel(txt, kb_(*rows))

# ─── Cache ───
async def show_cache_menu():
    accounts = list_accounts()
    txt = head("🗂", "cache")
    txt += T("select_account") + "\n\n"
    rows = []
    for aid, a in accounts.items():
        sn = _seen_count(aid); bn = _banned_count(aid); ln = len(_load_ldprog(aid))
        rows.append([B(f"{short(a.get('name','?'),14)} · {T('seen')} {sn} · {T('banned')} {bn} · {ln}",
                       f"cache:acc:{aid}")])
    if not accounts: txt += T("empty")
    rows.append([B(T("wipe_all"), "cache:clear_all_accounts")])
    rows.append(nav())
    await panel(txt, kb_(*rows))

async def show_cache_account(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()))
    sn = _seen_count(aid); bn = _banned_count(aid); ln = len(_load_ldprog(aid))
    txt = head("🗂", f"{T('cache')} · {a.get('name','?')}")
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
    await panel(txt, kb_(*rows))

# ─── PV panels ───
async def show_pv_menu():
    accounts = list_accounts()
    txt = head("💬", "pv_auto")
    txt += T("select_account") + "\n\n"
    if not accounts:
        txt += T("pv_no_accounts")
        return await panel(txt, kb_([B(T("add_account"), "acc:add")], nav()))
    rows = []
    for aid, a in accounts.items():
        cfg = _load_pv_account(aid)
        en = f"[{T('pv_active') if cfg.get('enabled') else T('pv_inactive')}] "
        n = len(cfg.get("items") or [])
        rows.append([B(f"{en}{short(a.get('name','?'),20)} · {n}", f"pv:acc:{aid}")])
    rows.append(nav())
    await panel(txt, kb_(*rows))

async def show_pv_account_menu(aid):
    a = get_account(aid)
    if not a: return await panel(T("not_found"), kb_(nav()))
    cfg = _load_pv_account(aid)
    en = bool(cfg.get("enabled")); mx = int(cfg.get("max_replies",1) or 0)
    items = cfg.get("items") or []
    notify_on = bool(cfg.get("notify", True))
    poll_sec = int(cfg.get("poll_seconds",3)); delay_sec = int(cfg.get("delay_seconds",0))
    pv_task = PV_LISTENER_TASKS.get(aid); poller_on = bool(pv_task and not pv_task.done())
    has_custom = _has_pv_account(aid)
    txt = head("💬", f"{T('pv')} · {a.get('name','?')}")
    txt += mrow("📶","pv_status", (T("pv_active") if en else T("pv_inactive"))) + "\n"
    txt += mrow("🔄","pv_poller", (T("on") if poller_on else T("off"))) + "\n"
    txt += mrow("👥","pv_max", (mx if mx else "∞")) + "\n"
    txt += mrow("⏱","pv_delay", f"{delay_sec}s") + "\n"
    txt += mrow("🔔","pv_notify", (T("on") if notify_on else T("off"))) + "\n"
    txt += mrow("🔄","pv_poll", f"{poll_sec}s") + "\n"
    txt += mrow("📨","pv_items", len(items))
    if has_custom: txt += f" ({T('pv_custom')})"
    txt += "\n\n"
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"{i}. 💬 <code>{esc(short(it.get('text',''),40))}</code>\n"
        elif k == "file": txt += f"{i}. 📁 <code>{esc(os.path.basename(it.get('file_path','?')))}</code>\n"
        elif k == "delay": txt += f"{i}. ⏸ {it.get('seconds',3)}s\n"
    rows = [
        [B(T("toggle_off") if en else T("toggle_on"), f"pv:acc:{aid}:toggle")],
        [B(f"{T('pv_max')}: {mx if mx else '∞'}", f"pv:acc:{aid}:cycle_max"),
         B(T("pv_delay"), f"pv:acc:{aid}:set_delay")],
        [B(T("pv_add_text"), f"pv:acc:{aid}:add_text"),
         B(T("pv_add_file"), f"pv:acc:{aid}:add_saved"),
         B(T("pv_add_delay"), f"pv:acc:{aid}:add_delay")],
        [B(T("pv_list"), f"pv:acc:{aid}:list"),
         B(T("pv_report"), f"pv:acc:{aid}:report:0")],
        [B(f"{T('pv_notify')}: {'✓' if notify_on else '✗'}", f"pv:acc:{aid}:toggle_notify"),
         B(f"{T('pv_poll')} {poll_sec}s", f"pv:acc:{aid}:set_poll")],
        [B(T("pv_reset_counter"), f"pv:acc:{aid}:clear_replies"),
         B(T("pv_reset_custom"), f"pv:acc:{aid}:reset_to_global")],
        [B(T("pv_restart"), f"pv:acc:{aid}:restart")],
        nav("menu:pv"),
    ]
    await panel(txt, kb_(*rows))

async def show_pv_account_list(aid):
    cfg = _load_pv_account(aid); items = cfg.get("items") or []
    a = get_account(aid)
    txt = head("📋", f"{T('pv_list')} · {a.get('name','?') if a else aid}")
    for i, it in enumerate(items, 1):
        k = it.get("kind", "text")
        if k == "text": txt += f"\n{i}. 💬 <code>{esc(short(it.get('text',''),60))}</code>"
        elif k == "file": txt += f"\n{i}. 📁 <code>{esc(os.path.basename(it.get('file_path','?')))}</code>"
        elif k == "delay": txt += f"\n{i}. ⏸ {it.get('seconds',3)}s"
    rows = [[B(f"{T('delete')} {i+1}", f"pv:acc:{aid}:del:{i}")] for i in range(len(items))]
    rows.append([B(f"« {T('back')}", f"pv:acc:{aid}")])
    await panel(txt, kb_(*rows))

async def show_pv_account_report(aid, page=0):
    rep = _load_pv_report(); users = rep.get(aid) or {}
    data = []
    for uid, d in users.items():
        data.append({"uid":uid,"first_name":d.get("first_name") or "",
                     "count":d.get("count",1),"replied":d.get("replied",False),
                     "reply_ok":d.get("reply_ok",False),"blocked":d.get("blocked",False),
                     "error":d.get("error"),"last_seen":d.get("last_seen",0)})
    data.sort(key=lambda x: x["last_seen"], reverse=True)
    PER = 8; pages = max(1, -(-len(data) // PER)); page = max(0, min(page, pages-1))
    chunk = data[page*PER:(page+1)*PER]
    a = get_account(aid)
    txt = head("📊", f"{T('pv_report')} · {a.get('name','?') if a else aid}")
    txt += f"👥 {T('pv_total')}: <b>{len(data)}</b> · 📄 {T('pv_page')} {page+1}/{pages}\n\n"
    for r in chunk:
        name = r["first_name"] or "?"
        st = "✅" if r["replied"] and r["reply_ok"] else ("❌" if r["replied"] else "⏳")
        if r["blocked"]: st += " 🚫"
        txt += f"{st} <b>{esc(short(name,20))}</b> · 📨×{r['count']}\n"
        if r.get("error"): txt += f"   <code>{esc(short(r['error'],50))}</code>\n"
    nav_btns = []
    if pages > 1:
        pr = []
        if page > 0: pr.append(B(T("prev"), f"pv:acc:{aid}:report:{page-1}"))
        pr.append(B(f"{page+1}/{pages}", "noop"))
        if page < pages-1: pr.append(B(T("next"), f"pv:acc:{aid}:report:{page+1}"))
        nav_btns.append(pr)
    nav_btns.append([B(f"« {T('back')}", f"pv:acc:{aid}")])
    await panel(txt, kb_(*nav_btns))

# ─── Linkdoni ───
async def show_linkdonies(back_to="jl:back_to_settings"):
    lst = load_link_donies()
    auto = int(_load(CFG_FILE, DEFAULT_CFG).get("auto_join_linkdoni", 1))
    txt = head("📡", "linkdonies", len(lst))
    txt += f"🔁 {T('ld_auto_join')}: <b>{'🟢' if auto else '🔴'}</b>\n"
    txt += f"<i>{T('ld_progress_per_acc')}</i>\n\n"
    for i, url in enumerate(lst): txt += f"{i+1}. <code>{esc(url)}</code>\n"
    rows = grid([B(f"🗑 {i+1}. {short(u.split('/')[-1], 12)}", f"ld:del:{i}:{back_to}")
                 for i, u in enumerate(lst)])
    rows.append([B(T("ld_add"), f"ld:add:{back_to}"),
                 B(T("toggle_off") if auto else T("toggle_on"), f"ld:toggle_autojoin:{back_to}")])
    rows.append([B(T("ld_reset_prog"), f"ld:reset_prog:{back_to}")])
    rows.append([B(T("ld_reset_list"), f"ld:reset:{back_to}")])
    rows.append(nav(back_to, home=False))
    await panel(txt, kb_(*rows))

# ─── Stats / Errors / Op detail / Cfg / Help ───
async def show_stats():
    ops = _load_ops()
    ops.sort(key=lambda o: o.get("created", 0), reverse=True)
    total_done = total_failed = 0
    q = TaskQueue(QUEUE_FILE)
    for t in q.tasks:
        if t.get("status") == "done": total_done += 1
        elif t.get("status") == "failed": total_failed += 1
    errs = _load_errors()
    txt = head("📊", "stats_title")
    txt += (f"✅ <b>{total_done}</b>\n"
            f"❌ <b>{total_failed}</b>\n"
            f"⚠️ <b>{len(errs)}</b>\n"
            f"📥 {STATE.get('listener_new_count',0)}\n\n")
    rows = []
    if ops:
        for op in ops[:10]:
            st = _op_effective_status(op); ico = _op_status_icon(st); s = _op_stats(op)
            prog = f"{s['done']+s['failed']}/{s['total']}" if s['total'] else "—"
            rows.append([B(f"{ico} {short(_op_short_title(op,28),32)} · {prog}", f"op:view:{op['id']}")])
    else: txt += T("empty")
    rows.append([B("⚠️ "+T("errors"), "menu:errors")])
    rows.append([B("🏠 "+T("back_to_panel"), "menu:main")])
    await panel(txt, kb_(*rows))

async def show_errors(page=0):
    errors = list(reversed(_load_errors()))
    if not errors:
        return await panel(head("⚠️", "errors") + T("errors_none"), kb_(nav()))
    PER = 5; pages = max(1, -(-len(errors) // PER)); page = max(0, min(page, pages-1))
    chunk = errors[page*PER:(page+1)*PER]
    txt = head("⚠️", "errors", f"{page+1}/{pages}") 
    for e in chunk:
        t = time.strftime('%m/%d %H:%M', time.localtime(e.get("time", 0)))
        txt += f"\n🕐 <code>{esc(t)}</code> · <b>{esc(e.get('source','?'))}</b>\n"
        txt += f"❗️ <code>{esc(str(e.get('error',''))[:220])}</code>\n"
    rows = []; pr = []
    if page > 0: pr.append(B("◀️", f"err:page:{page-1}"))
    pr.append(B(f"{page+1}/{pages}", "noop"))
    if page < pages-1: pr.append(B("▶️", f"err:page:{page+1}"))
    if len(pr) > 1: rows.append(pr)
    rows.append([B("🗑 "+T("clear"), "err:clear")])
    rows.append([B("📊 "+T("stats"), "menu:stats"), B("🏠", "menu:main")])
    await panel(txt, kb_(*rows))

async def show_op_detail(oid):
    op = _get_op(oid)
    if not op: return await panel(T("not_found"), kb_(nav()))
    st = _op_effective_status(op); ico = _op_status_icon(st); ttl = _op_status_label(st)
    s = _op_stats(op); bar, _ = _op_progress_bar(op)
    txt = head("📋", f"{op['id']}")
    txt += f"{ico} <b>{esc(ttl)}</b>\n\n<code>{esc(bar)}</code>\n\n"
    if op.get("type") == "joinlef":
        p = op.get("progress") or {}
        txt += f"📍 {esc(p.get('phase','—'))}\n"
        txt += f"✅ {s['done']} · ❌ {s['failed']}\n"
        ms = p.get("msg_sent",0); mf = p.get("msg_fail",0)
        if ms or mf: txt += f"✉️ {ms} · ❌ {mf}\n"
    else:
        txt += f"✅ {s['done']} · ❌ {s['failed']}\n"
        txt += f"⏳ {s['pending']} · 🔄 {s['in_progress']}\n"
    rows = []
    if st == "running": rows.append([B(T("stop"), f"op:stop:{oid}")])
    rows.append([B("📊 "+T("stats"), "menu:stats"), B("🏠", "menu:main")])
    await panel(txt, kb_(*rows))

CFG_FIELDS = [("delay","⏱",1,0,120),("cooldown","❄️",30,0,3600),
              ("batch_per_account","📦",1,1,20),("max_parallel","🚀",1,1,10),
              ("max_attempts","🔁",1,1,10)]
def _fmt_num(v):
    try:
        v = float(v); return str(int(v)) if v == int(v) else str(round(v, 1))
    except Exception: return str(v)

async def show_cfg():
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    txt = head("⚙️", "cfg_title"); rows = []
    txt += f"🌐 {T('cfg_lang')}: <b>{T('cfg_lang_fa') if not is_en() else T('cfg_lang_en')}</b>\n\n"
    for key, label, step, lo, hi in CFG_FIELDS:
        v = cfg.get(key, DEFAULT_CFG[key]); v_str = _fmt_num(v)
        txt += f"{label} {key}: <b>{esc(v_str)}</b>\n"
        rows.append([B("➖", f"cfg:adj:{key}:-1"), B(v_str, "noop"), B("➕", f"cfg:adj:{key}:1")])
    lv = int(cfg.get("listener", 1)); sv = int(cfg.get("listener_service_only", 1))
    txt += f"\n👂 {T('listen')}: <b>{'🟢' if lv else '🔴'}</b>\n"
    txt += f"🔍 service only: <b>{'🟢' if sv else '🔴'}</b>\n"
    txt += f"\n🔖 {VERSION}\n👤 <code>{FORCED_OWNER}</code>"
    rows.append([B("👂", "cfg:toggle_listener"), B("🔍", "cfg:toggle_service_only")])
    rows.append([B("🌐", "cfg:lang")])
    rows.append([B("🏠", "menu:main")])
    await panel(txt, kb_(*rows))

async def adjust_cfg(key, sign):
    spec = next((f for f in CFG_FIELDS if f[0] == key), None)
    if not spec: return
    _, _, step, lo, hi = spec
    cfg = _load(CFG_FILE, DEFAULT_CFG)
    v = float(cfg.get(key, DEFAULT_CFG[key])) + sign * step
    v = max(lo, min(hi, v))
    cfg[key] = round(v, 1) if key in ("delay","cooldown") else int(v)
    _save(CFG_FILE, cfg); await show_cfg()

async def show_help():
    txt = (head("❓", "panel") + f"🔖 {VERSION}\n\n"
           "📤 ارسال · 📢 کانال‌ها · 🤝 Joiner · 🚪 Lefter\n"
           "💬 پاسخ خودکار PV · 📡 Linkdoni · 🎯 Templates\n"
           f"\n👤 <code>{FORCED_OWNER}</code>\n"
           "🔑 auth در <code>sessions/{aid}.rp</code>")
    await panel(txt, kb_([B("🏠", "menu:main")]))

# ─── commands ───
async def cmd_start(update, context):
    cid = update.effective_chat.id
    if cid != FORCED_OWNER:
        try: await update.message.reply_text("⛔ خصوصی")
        except Exception: pass
        return
    STATE["owner"] = FORCED_OWNER
    try: _save(OWNER_FILE, {"owner": FORCED_OWNER})
    except Exception: pass
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
    txt = f"🔖 <b>{VERSION}</b>\n💾 <code>{DATA_DIR}</code>\n📱 {len(accounts)}\n👤 <code>{FORCED_OWNER}</code>"
    await update.message.reply_text(txt, parse_mode="HTML")
async def cmd_keepalive(update, context):
    if not authorized(update): return
    await update.message.reply_text("⏳ ping...")
    for aid, acc in list_accounts().items():
        sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        try:
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot: await bot.get_me()
            await update.message.reply_text(f"✅ {aid}")
        except Exception as e: await update.message.reply_text(f"❌ {aid}: {str(e)[:120]}")

# ─── media helper ───
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
    full = os.path.join(MEDIA_DIR, fname)
    try: await f.download_to_drive(full)
    except AttributeError:
        data = await f.download_as_bytearray()
        with open(full, "wb") as fp: fp.write(bytes(data))
    if not os.path.exists(full) or os.path.getsize(full) == 0: raise RuntimeError("empty_file")
    return full

# ─── message handler ───
async def on_message(update, context):
    if not authorized(update): return
    msg = update.message
    if msg is None: return
    cid = update.effective_chat.id
    conv = STATE["conv"].get(cid) or {}
    text = (msg.text or "").strip()

    if "acc" in conv and conv["acc"].get("step") == "login_pending":
        q = pending.get(cid, {}).get("q")
        if q:
            try: q.put(text)
            except Exception: pass
        return

    # PV wait states
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
            items.append({"kind":"text","text":text}); cfg["items"] = items
        elif kind == "add_delay_sec":
            try: sec = max(0, int(re.sub(r"[^\d]", "", text) or "3"))
            except: sec = 3
            items.append({"kind":"delay","seconds":sec}); cfg["items"] = items
        _save_pv_account(aid, cfg); await tg_send("✅")
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
        if local_path: items.append({"kind":"file","file_path":local_path,"caption":caption})
        else: items.append({"kind":"text","text":caption})
        cfg["items"] = items; _save_pv_account(aid, cfg); await tg_send("✅")
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
            items.append({"kind":"text","text":text})
            update_template(tid, "pv", "items", items)
        elif kind == "add_delay_sec":
            try: sec = max(0, int(re.sub(r"[^\d]", "", text) or "3"))
            except: sec = 3
            items.append({"kind":"delay","seconds":sec})
            update_template(tid, "pv", "items", items)
        await tg_send("✅"); return await show_at_pv(tid)

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
        if local_path: items.append({"kind":"file","file_path":local_path,"caption":caption})
        else: items.append({"kind":"text","text":caption})
        update_template(tid, "pv", "items", items)
        await tg_send("✅"); return await show_at_pv(tid)

    if conv.get("ld_wait") == "url":
        back = conv.pop("ld_back", "jl:back_to_settings")
        url = text.strip()
        if url.startswith("rubika.ir"): url = "@" + url.split("/")[-1]
        if add_link_doni(url): await tg_send("✅")
        else: await tg_send("ℹ️")
        return await show_linkdonies(back)

    if cid in _TMP_EDIT:
        info = _TMP_EDIT.pop(cid)
        if info["kind"] == "at_field":
            tid = info["tid"]; section = info["section"]; field = info["field"]
            value = text
            if field in ("max_join","max_send","max_replies"):
                try: value = int(re.sub(r"[^\d]", "", text) or "0")
                except: value = 0
            elif field in ("delay","edit_delay_seconds","loop_delay"):
                try: value = float(re.sub(r"[^\d\.]", "", text) or "1.5")
                except: value = 1.5
            update_template(tid, section, field, value); await tg_send("✅")
            if section == "meta": return await show_at_view(tid)
            if section == "channel": return await show_at_channel(tid)
            if section == "profile": return await show_at_profile(tid)
            if section == "joiner": return await show_at_joiner(tid)
            if section == "sender": return await show_at_sender(tid)
            if section == "lefter": return await show_at_lefter(tid)

    # acc photo upload
    if conv.get("accphoto_upload"):
        info = conv.pop("accphoto_upload"); aid = info["aid"]
        media = _extract_media(msg)
        if not media: return await ask(T("prof_no_photo"))
        try: fpath = await _download_tg_file(media, aid, "accphoto")
        except Exception as e: return await ask(f"❌ {str(e)[:100]}")
        a = get_account(aid)
        if not a: return await panel(T("not_found"), kb_(nav()))
        STATE["panel"].pop(cid, None)
        await panel(f"⏳ {T('prof_uploading')}")
        sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        ok = False; msg_r = ""
        try:
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot:
                me = await bot.get_me()
                ok, msg_r = await rubika_set_photo(bot, me.user.user_guid, fpath)
        except Exception as e: msg_r = _fmt_error(e)
        await tg_send("✅" if ok else f"❌ {msg_r[:150]}")
        return await show_profile_menu(aid)

    if "jl_wait" in conv:
        wait_kind = conv.pop("jl_wait")
        jl = get_conv(cid).get("jl") or {}
        if wait_kind == "max":
            try: jl["max_join"] = max(0, int(text))
            except Exception:
                get_conv(cid)["jl_wait"] = "max"
                return await ask(T("jl_max_q"))
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
        except Exception: return await ask(T("send_max_q"))
        return await show_send_step(cid)

    if "send" in conv:
        s = conv["send"]
        if s.get("step") == "compose":
            STATE["panel"].pop(cid, None)
            s["payload"] = {"kind":"text","text":text,"file":None}
            s["step"] = "target"
            return await show_send_step(cid)

    if "acc" in conv:
        a = conv["acc"]; step = a.get("step")
        STATE["panel"].pop(cid, None)
        if step == "phone":
            ph = text.replace("+","").replace(" ","").replace("-","")
            if ph.startswith("0"): ph = "98" + ph[1:]
            if not ph.isdigit() or len(ph) < 10:
                return await ask("📞 invalid")
            await panel(f"⏳ login... {esc(ph)}")
            a["step"] = "login_pending"
            asyncio.create_task(interactive_login_via_rubpy(cid, ph))
            return

    if "prof" in conv:
        pr = conv["prof"]; field = pr.get("field"); aid = pr.get("aid")
        STATE["panel"].pop(cid, None)
        a = get_account(aid)
        if not a:
            STATE["conv"].pop(cid, None)
            return await panel(T("not_found"), kb_(nav()))
        if not text: return await ask(PROF_PROMPT.get(field, T("enter")))
        STATE["conv"].pop(cid, None)
        await panel("⏳ ...")
        sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        try:
            cli = SafeClient(name=sess, _aid=aid)
            async with cli as bot:
                if field == "name": ok, info = await rubika_set_name(bot, text)
                elif field == "bio": ok, info = await rubika_set_bio(bot, text)
                elif field == "user": ok, info = await rubika_set_username(bot, text)
                else: ok, info = False, "?"
        except Exception as e: ok, info = False, _fmt_error(e)
        return await panel(("✅" if ok else f"⚠️ {esc(str(info)[:200])}"),
                           kb_([B("⬅️", f"prof:menu:{aid}")]))

    if "chan_send" in conv:
        cs = conv["chan_send"]
        STATE["panel"].pop(cid, None)
        if cs.get("step") == "compose":
            if not text: return await ask(T("text"))
            payload = {"kind":"text","text":text,"file":None}
            cs["payload"] = payload; cs["step"] = "confirm"
            aid = cs["aid"]; idx = cs["idx"]
            a = get_account(aid); chans = (a or {}).get("channels", [])
            if not a or idx >= len(chans):
                STATE["conv"].pop(cid, None)
                return await panel(T("not_found"), kb_(nav()))
            ch = chans[idx]
            txt = head("📤", "send") + f"📢 <b>{esc(ch.get('title','?'))}</b>\n\n💬 <code>{esc(text[:800])}</code>"
            return await panel(txt, kb_(
                [B("✅ "+T("send"), "chan:sendgo")],
                [B("✏️", "chan:sendredo")],
                [B("❌ "+T("cancel"), f"chan:view:{aid}:{idx}")]))

    if "chan" in conv:
        ch = conv["chan"]; step = ch.get("step")
        STATE["panel"].pop(cid, None)
        if step == "title":
            aid = ch.get("aid"); public = ch.get("public", True)
            STATE["conv"].pop(cid, None)
            if not text: return await show_main()
            a = get_account(aid)
            if not a: return await panel(T("not_found"), kb_(nav()))
            await panel(f"⏳ {T('ch_creating')} <b>{esc(text[:60])}</b>")
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            ctype = "public" if public else "private"
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot:
                    ok, info, guid, link = await rubika_create_channel(bot, text[:60], "", ctype)
            except Exception as e: ok, info, guid, link = False, _fmt_error(e), None, None
            if not ok:
                return await panel(f"⚠️ {esc(str(info)[:300])}", kb_([B("⬅️", f"acc:view:{aid}")]))
            add_channel_to_storage(aid, {"title":text[:60],"description":"","guid":guid,
                "username":None,"is_public":public,"type":ctype,"join_link":link,
                "created":int(time.time())})
            idx = len(get_account(aid).get("channels", [])) - 1
            txt = head("✅", text[:60]) + f"🆔 <code>{esc(guid)}</code>\n"
            txt += ("🌐" if public else "🔒")
            if not public and link: txt += f"\n🔗 <code>{esc(link)}</code>"
            return await panel(txt, kb_([B("⚙️", f"chan:view:{aid}:{idx}")],
                                         [B("📤", f"chan:send:{aid}:{idx}")],
                                         [B("⬅️", f"chan:list:{aid}")]))
        if step == "edit":
            aid = ch.get("aid"); idx = ch.get("idx"); field = ch.get("field")
            STATE["conv"].pop(cid, None)
            a = get_account(aid); chans = (a or {}).get("channels", [])
            if not a or idx >= len(chans): return await panel(T("not_found"), kb_(nav()))
            if not text: return await ask(CHAN_PROMPT.get(field, T("enter")))
            await panel("⏳ ...")
            guid = chans[idx].get("guid")
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot:
                    if field == "title": ok, info = await rubika_set_chat_title(bot, guid, text)
                    elif field == "desc": ok, info = await rubika_set_chat_description(bot, guid, text)
                    elif field == "user": ok, info = await rubika_set_chat_username(bot, guid, text)
                    else: ok, info = False, "?"
            except Exception as e: ok, info = False, _fmt_error(e)
            if ok:
                if field == "title": update_channel_field(aid, idx, "title", text)
                elif field == "desc": update_channel_field(aid, idx, "description", text)
                elif field == "user":
                    update_channel_field(aid, idx, "username", text.lstrip("@"))
                    update_channel_field(aid, idx, "is_public", True)
            return await panel(("✅" if ok else f"⚠️ {esc(str(info)[:200])}"),
                               kb_([B("⬅️", f"chan:view:{aid}:{idx}")]))

PROF_PROMPT = {"name":T("prof_first_q"),"bio":T("prof_bio_q"),
               "user":T("prof_user_q"),"photo":T("prof_send_photo")}
CHAN_PROMPT = {"title":T("channel_title"),"desc":T("about"),
               "user":T("username"),"photo":T("photo")}

# ══════════════════════════════════════════════════════════════
# CALLBACK ROUTER
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
        try: traceback.print_exc()
        except Exception: pass
        await panel(f"❌ {esc(type(e).__name__)}: {esc(str(e)[:200])}", kb_([B("🏠", "menu:main")]))

async def route_cb(cid, data):
    p = data.split(":"); h = p[0]
    if data == "conv:cancel": clear_conv(cid); _TMP_EDIT.pop(cid, None); return await show_main()
    if data == "menu:main": clear_conv(cid); _TMP_EDIT.pop(cid, None); return await show_main()
    if data == "menu:acc": return await show_accounts()
    if data == "menu:stats": return await show_stats()
    if data == "menu:errors": return await show_errors()
    if data == "menu:cfg": return await show_cfg()
    if data == "menu:help": return await show_help()
    if data == "menu:listen": return await show_listen_menu()
    if data == "menu:cache": return await show_cache_menu()
    if data == "menu:pv": return await show_pv_menu()
    if data == "cfg:lang":
        cur = _get_lang(); new = "en" if cur == "fa" else "fa"
        _set_lang(new)
        await tg_send(("🌐 English") if new == "en" else "🌐 فارسی")
        return await show_main()

    if h == "err":
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_errors(int(p[2]))
        if sub == "clear":
            clear_errors(); await tg_send("🗑")
            return await show_errors()

    if h == "listen":
        sub = p[1] if len(p) > 1 else ""
        if sub == "restart":
            await restart_all_listeners()
            await tg_send("🔄")
            return await show_listen_menu()
        if sub == "toggle" and len(p) >= 3:
            aid = p[2]
            t = LISTENER_TASKS.get(aid)
            if t and not t.done():
                _stop_listener_for(aid); await tg_send(f"👂 {aid} off")
            else:
                _spawn_listener_for(aid); await tg_send(f"👂 {aid} on")
            await asyncio.sleep(0.5)
            return await show_listen_menu()

    # cache
    if h == "cache":
        sub = p[1] if len(p) > 1 else ""
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; act = p[3] if len(p) > 3 else ""
            if not act: return await show_cache_account(aid)
            if act == "clear_seen": _clear_seen(aid); await tg_send("🗑"); return await show_cache_account(aid)
            if act == "clear_banned": _clear_banned(aid); await tg_send("🗑"); return await show_cache_account(aid)
            if act == "clear_all": _clear_seen(aid); _clear_banned(aid); await tg_send("🗑"); return await show_cache_account(aid)
            if act == "reset_ld": _reset_ld_progress(aid); await tg_send("🔄"); return await show_cache_account(aid)
        if sub == "clear_all_accounts":
            _clear_seen(); _clear_banned(); _reset_ld_progress()
            await tg_send("🗑"); return await show_cache_menu()

    # pv
    if h == "pv":
        sub = p[1] if len(p) > 1 else ""
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; act = p[3] if len(p) > 3 else ""
            if not act: return await show_pv_account_menu(aid)
            cfg = _load_pv_account(aid)
            if act == "toggle":
                cfg["enabled"] = not bool(cfg.get("enabled"))
                _save_pv_account(aid, cfg)
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
                seq = [1,2,3,5,0]; cur = int(cfg.get("max_replies",1) or 0)
                cfg["max_replies"] = seq[(seq.index(cur)+1) % len(seq)] if cur in seq else 1
                _save_pv_account(aid, cfg); return await show_pv_account_menu(aid)
            if act == "set_delay":
                get_conv(cid)["pv_acc_wait"] = {"aid":aid,"kind":"delay"}
                return await ask(T("pv_delay_q"))
            if act == "set_poll":
                get_conv(cid)["pv_acc_wait"] = {"aid":aid,"kind":"poll"}
                return await ask(T("pv_poll_q"))
            if act == "toggle_notify":
                cfg["notify"] = not bool(cfg.get("notify", True))
                _save_pv_account(aid, cfg); return await show_pv_account_menu(aid)
            if act == "add_text":
                get_conv(cid)["pv_acc_wait"] = {"aid":aid,"kind":"add_text"}
                return await ask(T("pv_text_q"))
            if act == "add_saved":
                get_conv(cid)["pv_acc_save_msg"] = {"aid":aid}
                return await ask(T("pv_file_q"))
            if act == "add_delay":
                get_conv(cid)["pv_acc_wait"] = {"aid":aid,"kind":"add_delay_sec"}
                return await ask(T("pv_delaysec_q"))
            if act == "list": return await show_pv_account_list(aid)
            if act == "del" and len(p) >= 5:
                try: i = int(p[4])
                except: return await show_pv_account_list(aid)
                items = cfg.get("items") or []
                if 0 <= i < len(items): items.pop(i)
                cfg["items"] = items; _save_pv_account(aid, cfg)
                await tg_send("🗑"); return await show_pv_account_list(aid)
            if act == "clear_replies":
                try:
                    d = _load(PV_COUNTS_FILE, {}); d.pop(aid, None); _save(PV_COUNTS_FILE, d)
                except Exception: pass
                try:
                    w = _wm_load(); w.pop(aid, None); _wm_flush()
                except Exception: pass
                await tg_send("🧹"); return await show_pv_account_menu(aid)
            if act == "reset_to_global":
                _delete_pv_account(aid); await tg_send("♻️"); return await show_pv_account_menu(aid)
            if act == "restart":
                _stop_pv_for_account(aid); await asyncio.sleep(0.5)
                cfg2 = _load_pv_account(aid)
                if cfg2.get("enabled"):
                    acc = get_account(aid)
                    if acc:
                        stop = asyncio.Event(); _PV_STOP_EVENTS[aid] = stop
                        PV_LISTENER_TASKS[aid] = asyncio.create_task(_pv_poller_worker(aid, acc, stop))
                await tg_send("🔄"); return await show_pv_account_menu(aid)
            if act == "report":
                try: pg = int(p[4]) if len(p) > 4 else 0
                except: pg = 0
                return await show_pv_account_report(aid, pg)

    # ld
    if h == "ld":
        sub = p[1] if len(p) > 1 else ""
        back = p[3] if len(p) > 3 else (p[2] if len(p) > 2 else "jl:back_to_settings")
        if sub == "list": return await show_linkdonies(back)
        if sub == "add":
            get_conv(cid)["ld_wait"] = "url"; get_conv(cid)["ld_back"] = back
            return await ask(T("ld_add_q"))
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

    # templates
    if data == "at:menu": return await show_at_menu()
    if data == "at:new":
        tpl = new_template("قالب " + secrets.token_hex(2)); add_template(tpl)
        return await show_at_view(tpl["id"])
    if h == "at" and len(p) >= 3 and p[1].startswith("tp_"):
        tid = p[1]; act = p[2]
        if act == "view": return await show_at_view(tid)
        if act == "del":
            t = get_template(tid)
            if not t: return await show_at_menu()
            return await panel(T("at_delete_q", n=esc(t.get('name','?'))),
                kb_([B(T("yes"), f"at:{tid}:delok"), B(T("no"), f"at:{tid}:view")]))
        if act == "delok": delete_template(tid); await tg_send("🗑"); return await show_at_menu()
        if act == "rename":
            _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"meta","field":"name"}
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
            _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"channel","field":p[3]}
            return await ask(T("enter"))
        if act == "prset" and len(p) >= 4:
            _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"profile","field":p[3]}
            return await ask(T("enter"))
        if act == "jnset" and len(p) >= 4:
            _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"joiner","field":p[3]}
            return await ask(T("jl_max"))
        if act == "jnspeed" and len(p) >= 4:
            update_template(tid, "joiner", "speed", p[3]); return await show_at_joiner(tid)
        if act == "jntoggle_groups_only":
            t = get_template(tid)
            if t: update_template(tid, "joiner", "groups_only",
                                  not bool(t.get("joiner",{}).get("groups_only", True)))
            return await show_at_joiner(tid)
        if act == "snset" and len(p) >= 4:
            _TMP_EDIT[cid] = {"kind":"at_field","tid":tid,"section":"sender","field":p[3]}
            return await ask(T("enter"))
        if act == "snmode_set" and len(p) >= 4:
            update_template(tid, "sender", "mode", p[3]); return await show_at_sender(tid)
        if act == "pv" and len(p) >= 4:
            sub_act = p[3]
            t2 = get_template(tid)
            if not t2: return await show_at_menu()
            pv2 = t2.setdefault("pv", {}); items = pv2.get("items") or []
            if sub_act == "toggle":
                pv2["enabled"] = not bool(pv2.get("enabled", False))
                update_template(tid, "pv", "enabled", pv2["enabled"]); return await show_at_pv(tid)
            if sub_act == "cycle_max":
                seq = [1,2,3,5,0]; cur = int(pv2.get("max_replies",1) or 0)
                nv = seq[(seq.index(cur)+1) % len(seq)] if cur in seq else 1
                update_template(tid, "pv", "max_replies", nv); return await show_at_pv(tid)
            if sub_act == "set_delay":
                get_conv(cid)["pv_tpl_wait"] = {"tid":tid,"kind":"delay"}
                return await ask(T("pv_delay_q"))
            if sub_act == "toggle_apply":
                update_template(tid, "pv", "apply_to_accounts",
                                not bool(pv2.get("apply_to_accounts", True)))
                return await show_at_pv(tid)
            if sub_act == "add_text":
                get_conv(cid)["pv_tpl_wait"] = {"tid":tid,"kind":"add_text"}
                return await ask(T("pv_text_q"))
            if sub_act == "add_saved":
                get_conv(cid)["pv_tpl_save_msg"] = {"tid":tid}
                return await ask(T("pv_file_q"))
            if sub_act == "add_delay":
                get_conv(cid)["pv_tpl_wait"] = {"tid":tid,"kind":"add_delay_sec"}
                return await ask(T("pv_delaysec_q"))
            if sub_act == "list": return await show_at_pv_list(tid)
            if sub_act == "del" and len(p) >= 5:
                try: i = int(p[4])
                except: return await show_at_pv_list(tid)
                if 0 <= i < len(items): items.pop(i)
                update_template(tid, "pv", "items", items)
                await tg_send("🗑"); return await show_at_pv_list(tid)
        if act == "lfset" and len(p) >= 4:
            update_template(tid, "lefter", "leave_mode", p[3]); return await show_at_lefter(tid)
        if act == "run": return await show_at_run(tid)
        if act == "run_acc" and len(p) >= 4:
            c2 = get_conv(cid); ar = c2.setdefault("at_run", {"template_id":tid,"accounts":[]})
            sel = ar.setdefault("accounts", [])
            if p[3] in sel: sel.remove(p[3])
            else: sel.append(p[3])
            return await show_at_run(tid)
        if act == "run_go":
            c2 = get_conv(cid); ar = c2.get("at_run") or {}
            sel = ar.get("accounts") or []
            if not sel: return await panel(T("empty"), kb_(nav(f"at:{tid}:view")))
            op = {"id":"at_"+secrets.token_hex(5),"created":int(time.time()),
                  "type":"autotar","accounts":sel,"template_id":tid,"status":"running",
                  "progress":{"joined":0,"failed":0,"total":0,"phase":T("ph_start"),
                              "sent":0,"already":0,"tried":0,"wave":0,"left":0,
                              "skipped_seen":0,"skipped_banned":0,"rejected":0},
                  "errors":[]}
            _save_op(op); c2.pop("at_run", None)
            asyncio.create_task(run_auto_tar(op, log_cb))
            return await show_op_detail(op["id"])
        if len(p) == 3 and p[2].isdigit(): return await show_at_run(tid, int(p[2]))

    # chan
    if h == "chan":
        sub = p[1]
        if sub == "new": return await show_channel_new(p[2])
        if sub == "new_pub":
            get_conv(cid)["chan"] = {"step":"title","aid":p[2],"public":True}
            return await ask(T("ch_new_name_q"))
        if sub == "new_priv":
            get_conv(cid)["chan"] = {"step":"title","aid":p[2],"public":False}
            return await ask(T("ch_new_name_q"))
        if sub == "list": return await show_channel_list(p[2])
        if sub == "page": return await show_channel_list(p[2], int(p[3]))
        if sub == "view": return await show_channel_view(p[2], int(p[3]))
        if sub == "edit":
            get_conv(cid)["chan"] = {"step":"edit","aid":p[3],"idx":int(p[4]),"field":p[2]}
            return await ask(CHAN_PROMPT.get(p[2], T("enter")))
        if sub == "mklink":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels", [])
            if not a or idx >= len(chans): return await panel(T("not_found"), kb_(nav()))
            await panel("⏳ ...")
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
            a = get_account(aid); chans = (a or {}).get("channels", [])
            if not a or idx >= len(chans): return await panel(T("not_found"), kb_(nav()))
            return await panel(f"🗑 <b>{esc(chans[idx].get('title','?'))}</b>?",
                kb_([B("✅ "+T("yes"), f"chan:delok:{aid}:{idx}")],
                    [B("❌ "+T("no"), f"chan:view:{aid}:{idx}")]))
        if sub == "delok":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels", [])
            if not a or idx >= len(chans): return await panel(T("not_found"), kb_(nav()))
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot:
                    ok, info = await rubika_remove_channel(bot, chans[idx]["guid"])
            except Exception as e: ok, info = False, _fmt_error(e)
            if ok: remove_channel_from_storage(aid, idx)
            return await panel(("✅" if ok else f"⚠️ {esc(str(info)[:200])}"),
                               kb_([B("⬅️", f"chan:list:{aid}")]))
        if sub == "send":
            aid, idx = p[2], int(p[3])
            a = get_account(aid); chans = (a or {}).get("channels", [])
            if not a or idx >= len(chans): return await panel(T("not_found"), kb_(nav()))
            get_conv(cid)["chan_send"] = {"aid":aid,"idx":idx,"step":"compose","payload":None}
            return await ask(T("text"))
        if sub == "sendgo":
            cs = get_conv(cid).get("chan_send")
            if not cs: return await show_main()
            aid = cs["aid"]; idx = cs["idx"]; payload = cs["payload"]
            a = get_account(aid); chans = (a or {}).get("channels", [])
            if not a or idx >= len(chans):
                STATE["conv"].pop(cid, None)
                return await panel(T("not_found"), kb_(nav()))
            ch = chans[idx]; guid = ch.get("guid")
            await panel("⏳ ...")
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot:
                    await send_text_only(bot, guid, payload.get("text") or "—")
                ok = True; err = None
            except Exception as e: ok = False; err = _fmt_error(e)
            STATE["conv"].pop(cid, None)
            if ok:
                return await panel(f"✅ <b>{esc(ch.get('title','?'))}</b>",
                    kb_([B("📤", f"chan:send:{aid}:{idx}")], [B("⬅️", f"chan:view:{aid}:{idx}")]))
            return await panel(f"❌ {esc(str(err)[:250])}",
                kb_([B("🔁", f"chan:send:{aid}:{idx}")], [B("⬅️", f"chan:view:{aid}:{idx}")]))
        if sub == "sendredo":
            cs = get_conv(cid).get("chan_send")
            if not cs: return await show_main()
            cs["step"] = "compose"; cs["payload"] = None
            return await ask(T("text"))

    # profile
    if h == "prof":
        sub = p[1]; aid = p[-1]
        if sub == "menu": return await show_profile_menu(aid)
        if sub == "set":
            field = p[2]
            get_conv(cid)["prof"] = {"step":"value","aid":aid,"field":field}
            return await ask(PROF_PROMPT.get(field, T("enter")))

    if h == "accphoto":
        sub = p[1] if len(p) > 1 else ""
        if sub == "set" and len(p) >= 3:
            get_conv(cid)["accphoto_upload"] = {"aid": p[2]}
            return await ask(T("prof_send_photo"))
        if sub == "del" and len(p) >= 3:
            aid = p[2]
            a = get_account(aid)
            if not a: return await panel(T("not_found"), kb_(nav()))
            await panel(f"⏳ {T('prof_deleting')}")
            sess = a.get("session_name") or os.path.join(SESSIONS_DIR, aid)
            try:
                cli = SafeClient(name=sess, _aid=aid)
                async with cli as bot:
                    me = await bot.get_me()
                    ok, info = await rubika_delete_my_photos(bot, me.user.user_guid)
            except Exception as e: ok, info = False, _fmt_error(e)
            await tg_send("✅" if ok else f"❌ {str(info)[:150]}")
            return await show_profile_menu(aid)

    # accounts
    if h == "acc":
        if len(p) >= 5 and p[1] == "at" and p[2] == "run":
            aid = p[3]; tid = p[4]
            op = {"id":"at_"+secrets.token_hex(5),"created":int(time.time()),
                  "type":"autotar","accounts":[aid],"template_id":tid,"status":"running",
                  "progress":{"joined":0,"failed":0,"total":0,"phase":T("ph_start"),
                              "sent":0,"already":0,"tried":0,"wave":0,"left":0,
                              "skipped_seen":0,"skipped_banned":0,"rejected":0},
                  "errors":[]}
            _save_op(op); asyncio.create_task(run_auto_tar(op, log_cb))
            return await show_op_detail(op["id"])
        if len(p) >= 3 and p[1] == "at": return await show_acc_at_menu(p[2])
        sub = p[1] if len(p) > 1 else ""
        if sub == "page": return await show_accounts(int(p[2]))
        if sub == "add":
            get_conv(cid)["acc"] = {"step":"phone"}
            return await ask("📞 <code>989121234567</code>")
        if sub == "view": return await show_account_detail(p[2])
        if sub == "del":
            a = get_account(p[2])
            if not a: return await panel(T("not_found"), kb_(nav()))
            return await panel(f"🗑 <b>{esc(a.get('name','?'))}</b>?",
                kb_([B("✅ "+T("yes"), f"acc:delok:{p[2]}")],
                    [B("❌ "+T("no"), f"acc:view:{p[2]}")]))
        if sub == "delok":
            _stop_listener_for(p[2]); _stop_pv_for_account(p[2])
            remove_account(p[2]); await tg_send("🗑")
            return await show_accounts()
        if sub == "lf" and len(p) >= 5 and p[3] == "go":
            aid = p[2]; mode = p[4]
            op = {"id":"lf_"+secrets.token_hex(5),"created":int(time.time()),
                  "type":"lefter","accounts":[aid],"leave_mode":mode,"delay":0.8,
                  "status":"running","progress":{"joined":0,"failed":0,"total":0,"phase":T("ph_start")},
                  "errors":[]}
            _save_op(op); asyncio.create_task(run_lefter(op, log_cb))
            return await show_op_detail(op["id"])
        if sub == "lf" and len(p) >= 3: return await show_acc_lf(p[2])

    # jl
    if h == "jl":
        c = get_conv(cid)
        s = c.get("jl") or {"step":"account","accounts":[],"max_join":0,"speed":"fast","auto_msg":""}
        c["jl"] = s
        sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            c["jl"] = {"step":"account","accounts":[],"max_join":0,"speed":"fast","auto_msg":""}
            return await jl_step_account(cid, c["jl"])
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await jl_step_account(cid, s)
        if sub == "speed" and len(p) >= 3:
            s["speed"] = p[2]; return await jl_step_settings(cid, s)
        if sub == "setauto":
            get_conv(cid)["jl_wait"] = "auto_msg"
            return await ask(T("text"))
        if sub == "clrauto":
            s["auto_msg"] = ""; return await jl_step_settings(cid, s)
        if sub == "next":
            if s["step"] == "account":
                if not s.get("accounts"): return await panel(T("empty"), kb_(nav()))
                s["step"] = "settings"; return await jl_step_settings(cid, s)
            elif s["step"] == "settings":
                s["step"] = "max"; return await jl_step_max(cid, s)
            elif s["step"] == "max":
                s["step"] = "confirm"; return await jl_step_confirm(cid, s)
        if sub == "back":
            if s["step"] == "settings": s["step"] = "account"
            elif s["step"] == "max": s["step"] = "settings"
            elif s["step"] == "confirm": s["step"] = "max"
            return await show_jl_step(cid)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["jl_wait"] = "max"
                return await ask(T("jl_max_q"))
            try: s["max_join"] = int(v)
            except: pass
            return await jl_step_max(cid, s)
        if sub == "cancel":
            c.pop("jl", None); return await show_main()
        if sub == "go":
            speed_map = {"ultra":0.3,"fast":1.0,"normal":3.0,"slow":8.0}
            spd = s.get("speed", "fast")
            op = {"id":"jl_"+secrets.token_hex(5),"created":int(time.time()),
                  "type":"joinlef","accounts":s.get("accounts") or [],
                  "max_join":s.get("max_join",0) or 0,"status":"running","speed":spd,
                  "join_delay":speed_map.get(spd, 1.0),
                  "auto_msg":(s.get("auto_msg") or "").strip(),
                  "progress":{"joined":0,"failed":0,"total":0,"phase":"شروع","extracted":0,
                              "msg_sent":0,"msg_fail":0,"linkdoni_ok":[],"linkdoni_fail":[],"link_errors":[]},
                  "errors":[]}
            _save_op(op); c.pop("jl", None)
            task = asyncio.create_task(run_joiner_lefter(op, log_cb))
            JL_JOBS[op["id"]] = task
            return await show_op_detail(op["id"])

    # lf
    if h == "lf":
        c = get_conv(cid)
        s = c.get("lf") or {"step":"account","accounts":[],"mode":"all","delay":0.8}
        c["lf"] = s
        sub = p[1] if len(p) > 1 else ""
        if sub == "start":
            c["lf"] = {"step":"account","accounts":[],"mode":"all","delay":0.8}
            return await lf_step_account(cid, c["lf"])
        if sub == "acc" and len(p) >= 3:
            aid = p[2]; sel = s.setdefault("accounts", [])
            if aid in sel: sel.remove(aid)
            else: sel.append(aid)
            return await lf_step_account(cid, s)
        if sub == "mode" and len(p) >= 3:
            s["mode"] = p[2]; return await lf_step_mode(cid, s)
        if sub == "delay" and len(p) >= 3:
            try: s["delay"] = float(p[2])
            except: s["delay"] = 0.8
            return await lf_step_delay(cid, s)
        if sub == "next":
            if s["step"] == "account":
                if not s.get("accounts"): return await panel(T("empty"), kb_(nav()))
                s["step"] = "mode"; return await lf_step_mode(cid, s)
            elif s["step"] == "mode":
                s["step"] = "delay"; return await lf_step_delay(cid, s)
        if sub == "back":
            if s["step"] == "mode": s["step"] = "account"
            elif s["step"] == "delay": s["step"] = "mode"
            return await show_lf_step(cid)
        if sub == "cancel":
            c.pop("lf", None); return await show_main()
        if sub == "go":
            if not s.get("accounts"): return await panel(T("empty"), kb_(nav()))
            op = {"id":"lf_"+secrets.token_hex(5),"created":int(time.time()),
                  "type":"lefter","accounts":s.get("accounts") or [],
                  "leave_mode":s.get("mode", "all"),"delay":s.get("delay", 0.8),
                  "status":"running",
                  "progress":{"joined":0,"failed":0,"total":0,"phase":T("ph_start")},
                  "errors":[]}
            _save_op(op); c.pop("lf", None)
            asyncio.create_task(run_lefter(op, log_cb))
            return await show_op_detail(op["id"])

    # send wizard
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
        if sub == "recompose":
            s["step"] = "compose"; s["payload"] = None
            return await show_send_step(cid)
        if sub == "composenext":
            if not s.get("payload"): return await show_send_step(cid)
            s["step"] = "target"; return await show_send_step(cid)
        if sub == "tgt" and len(p) >= 3:
            s["target"] = p[2]; return await show_send_step(cid)
        if sub == "tgtnext":
            s["step"] = "max"; return await show_send_step(cid)
        if sub == "max" and len(p) >= 3:
            v = p[2]
            if v == "custom":
                get_conv(cid)["send_wait"] = "max"
                return await ask(T("send_max_q"))
            try: s["max"] = int(v)
            except: pass
            return await show_send_step(cid)
        if sub == "maxnext":
            s["step"] = "schedule"; return await show_send_step(cid)
        if sub == "sch" and len(p) >= 3:
            code = p[2]
            for c2, label, secs in SCHEDULE_OPTIONS:
                if c2 == code: s["schedule"] = secs; break
            return await show_send_step(cid)
        if sub == "schedulenext":
            s["step"] = "confirm"; return await show_send_step(cid)
        if sub == "back":
            s["step"] = "accounts"; return await show_send_step(cid)
        if sub == "prev":
            order = ["accounts","compose","target","max","schedule","confirm"]
            i = order.index(s.get("step", "accounts"))
            s["step"] = order[max(0, i-1)]
            return await show_send_step(cid)
        if sub == "back_edit":
            s["step"] = "accounts"; return await show_send_step(cid)
        if sub == "cancel":
            clear_conv(cid); return await show_main()
        if sub == "go":
            accounts = list_accounts(); sel = s.get("accounts") or []
            if "all" in sel: sel = list(accounts.keys())
            payload = s.get("payload") or {"kind":"text","text":"سلام"}
            targets = s.get("_targets") or []
            if not targets:
                return await panel(T("empty"), kb_(nav()))
            op = {"id":"op_"+secrets.token_hex(5),"created":int(time.time()),
                  "scheduled_at":int(time.time()) + s.get("schedule", 0),
                  "payload":payload,"target":s.get("target", "both"),
                  "max":s.get("max", 0) or 0,"accounts":sel,
                  "status":"draft","task_ids":[],"_targets":targets}
            if s.get("schedule", 0) > 0:
                op["status"] = "scheduled"; _save_op(op); clear_conv(cid)
                await panel(head("⏰", "confirm") + f"📦 {len(targets)}",
                            kb_([B("🏠", "menu:main")]))
            else:
                n = await op_start_now(op); clear_conv(cid)
                await panel(head("🚀", "start") + f"📦 {n}",
                            kb_([B("📊", "menu:stats")], [B("🏠", "menu:main")]))
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
                    op["status"] = "cancelled"
                    op["finished_at"] = int(time.time())
                    _save_op(op)
                elif op.get("type") == "autotar":
                    op["status"] = "cancelled"; _save_op(op)
                else:
                    op["status"] = "paused"
                    q = TaskQueue(QUEUE_FILE)
                    for t in q.tasks:
                        if t.get("op_id") == oid and t["status"] in ("pending","in_progress"):
                            t["status"] = "paused"
                    q._save(); _save_op(op)
            return await show_op_detail(oid)

    if h == "cfg":
        sub = p[1] if len(p) > 1 else ""
        if sub == "adj" and len(p) >= 4:
            return await adjust_cfg(p[2], int(p[3]))
        if sub == "toggle_listener":
            new = await toggle_listener_cfg()
            await tg_send(f"👂 {'🟢' if new else '🔴'}")
            return await show_cfg()
        if sub == "toggle_service_only":
            new = await toggle_service_only_cfg()
            await tg_send(f"🔍 {'🟢' if new else '🔴'}")
            return await show_cfg()

# ══════════════════════════════════════════════════════════════
# AutoTar worker
# ══════════════════════════════════════════════════════════════
async def _auto_tar_worker(aid, acc, op_id, tpl, log):
    nm = acc.get("name") or aid
    op = _get_op(op_id)
    if not op: return
    lock = _get_op_lock(op_id); ctx = _build_ctx()
    async def _phase(ph):
        async with lock:
            op2 = _get_op(op_id)
            if op2: op2["progress"]["phase"] = ph; _save_op(op2)
    async def _finish(ph):
        async with lock:
            op2 = _get_op(op_id)
            if op2:
                op2["progress"]["phase"] = ph
                if op2.get("status") == "running":
                    op2["status"] = "done"; op2["finished_at"] = int(time.time())
                _save_op(op2)
    try:
        sess = acc.get("session_name") or os.path.join(SESSIONS_DIR, aid)
        cli = SafeClient(name=sess, _aid=aid)
        async with cli as bot:
            me = await bot.get_me(); my_guid = me.user.user_guid
            await _phase(T("ph_connected", n=me.user.first_name or aid))
            ch = tpl.get("channel") or {}
            if ch.get("title"):
                title = _substitute(ch["title"], ctx)[:60] or f"channel_{ctx['n']}"
                about = _substitute(ch.get("about", ""), ctx)
                await _phase(T("ph_create_ch", n=title))
                try:
                    ctype = ch.get("type", "private")
                    ok, info, guid, link = await rubika_create_channel(bot, title, about, ctype)
                    if ok and guid:
                        add_channel_to_storage(aid, {"title":title,"description":about,
                            "guid":guid,"username":None,"is_public":ctype == "public",
                            "type":ctype,"join_link":link,"created":int(time.time())})
                except Exception as e: add_error("autotar-channel", _fmt_error(e), title, nm)
            p = tpl.get("profile") or {}
            if p.get("first_name") or p.get("last_name") or p.get("bio") or p.get("username"):
                await _phase(T("ph_update_prof"))
                try:
                    if p.get("first_name") or p.get("last_name"):
                        await rubika_set_name(bot,
                            _substitute(p.get("first_name",""), ctx)[:64],
                            _substitute(p.get("last_name",""), ctx)[:64])
                    if p.get("bio"):
                        await rubika_set_bio(bot, _substitute(p["bio"], ctx)[:70])
                    if p.get("username"):
                        await rubika_set_username(bot, _substitute(p["username"], ctx))
                except Exception as e: add_error("autotar-profile", _fmt_error(e), None, nm)
            j = tpl.get("joiner") or {}
            snd = tpl.get("sender") or {}
            mode = snd.get("mode", "send_only")
            sender_text = _substitute(snd.get("text",""), ctx) if snd.get("text") else ""
            max_join = int(j.get("max_join", 0) or 0)
            join_delay = {"ultra":0.3,"fast":1.0,"normal":3.0,"slow":8.0}.get(j.get("speed","fast"), 1.0)
            joined_count = 0; sent_count = 0; left_count = 0; failed_count = 0
            if max_join > 0:
                lds = list(load_link_donies())
                await _phase(T("ph_extract", n=1))
                ordered = {}
                for url in lds:
                    guid_t, kind = await _resolve_target(bot, url)
                    if not guid_t: continue
                    try:
                        found = await _extract_links_from_bot(bot, guid_t, limit=300, log=log)
                        for lk in found:
                            h = _hash_of(lk)
                            if not h: continue
                            if _is_seen(aid, h) or _is_banned(aid, h): continue
                            if lk not in ordered: ordered[lk] = True
                    except Exception: pass
                new_links = list(ordered.keys())
                await _phase(T("ph_links", n=1, c=len(new_links)))
                for lk in new_links:
                    async with lock:
                        op2 = _get_op(op_id)
                        if not op2 or op2.get("status") == "cancelled": return
                    if joined_count >= max_join: break
                    try:
                        ok, guid_j, tag = await _try_join_single(bot, lk)
                        if not ok: failed_count += 1; continue
                        h = _hash_of(lk); _mark_seen(aid, h)
                        if tag != "already": joined_count += 1
                        if mode in ("join_send","join_send_leave") and sender_text and guid_j:
                            try:
                                await send_text_only(bot, guid_j, sender_text)
                                sent_count += 1
                                if mode == "join_send_leave":
                                    ok_l, _ = await _lefter_leave_one(bot, {"guid":guid_j,"kind":"group"})
                                    if ok_l: left_count += 1
                            except Exception: pass
                    except Exception: failed_count += 1
                    async with lock:
                        op2 = _get_op(op_id)
                        if op2:
                            op2["progress"]["joined"] = joined_count
                            op2["progress"]["sent"] = sent_count
                            op2["progress"]["left"] = left_count
                            op2["progress"]["failed"] = failed_count
                            _save_op(op2)
                    if join_delay > 0: await asyncio.sleep(join_delay)
            if sender_text and bool(snd.get("send_to_existing", True)) and mode == "send_only":
                await _phase(T("ph_send_final"))
                target = snd.get("target", "groups")
                chats = await get_all_chats_raw(bot)
                own_guids = set(c.get("guid") for c in get_stored_channels(aid) if c.get("guid"))
                for c in chats:
                    if c.get("guid") in own_guids or c.get("guid") == my_guid: continue
                    if target == "pv" and c.get("type") != "User": continue
                    if target == "groups" and not _is_true_group(c): continue
                    if target == "both" and c.get("type") not in ("User","Group"): continue
                    try:
                        await send_text_only(bot, c.get("guid"), sender_text)
                        sent_count += 1
                    except Exception: failed_count += 1
                    await asyncio.sleep(float(snd.get("delay", 1.5)))
            lf = tpl.get("lefter") or {}
            if lf.get("leave_mode"):
                await _phase(T("ph_leaving", m=lf["leave_mode"]))
                own_guids = set(c.get("guid") for c in get_stored_channels(aid) if c.get("guid"))
                for t in await _lefter_collect(bot, lf["leave_mode"], exclude_ids=own_guids):
                    try:
                        ok_l, _ = await _lefter_leave_one(bot, t)
                        if ok_l: left_count += 1
                    except Exception: pass
                    await asyncio.sleep(0.6)
            await _finish(T("ph_done"))
    except asyncio.CancelledError:
        await _finish(T("ph_cancelled")); raise
    except Exception as e:
        await _finish(T("ph_error", n=type(e).__name__))

async def run_auto_tar(op, log):
    accounts = list_accounts(); sel = op.get("accounts") or []
    if "all" in sel: sel = list(accounts.keys())
    tpl = get_template(op.get("template_id"))
    if not tpl:
        op["status"] = "failed"; op["progress"]["phase"] = T("not_found"); _save_op(op); return
    op["progress"] = {"joined":0,"failed":0,"total":0,"phase":T("ph_start"),
                      "sent":0,"already":0,"tried":0,"wave":0,"left":0,
                      "skipped_seen":0,"skipped_banned":0,"rejected":0}
    op["status"] = "running"; op["errors"] = []; _save_op(op)
    tasks = []
    for aid in sel:
        a = accounts.get(aid)
        if not a: continue
        tasks.append(asyncio.create_task(_auto_tar_worker(aid, a, op["id"], tpl, log)))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    op2 = _get_op(op["id"])
    if op2 and op2.get("status") not in ("cancelled","done"):
        op2["status"] = "done"; op2["finished_at"] = int(time.time()); _save_op(op2)
    _OP_LOCKS.pop(op["id"], None)

# ══════════════════════════════════════════════════════════════
# OPS helpers
# ══════════════════════════════════════════════════════════════
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
    if not targets:
        op["status"] = "empty"; _save_op(op); return
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
# BOOT
# ══════════════════════════════════════════════════════════════
async def _post_init(app):
    try:
        from telegram import BotCommand
        await app.bot.set_my_commands([
            BotCommand("start", "شروع"),
            BotCommand("menu", "منو"),
            BotCommand("version", "نسخه"),
            BotCommand("keepalive", "ping"),
        ])
    except Exception: pass
    try:
        asyncio.create_task(start_all_listeners())
        print("[listener] boot scheduled")
    except Exception as e: print(f"[listener-boot] {e}")
    try:
        asyncio.create_task(start_pv_responders())
        print("[pv] boot scheduled")
    except Exception as e: print(f"[pv-boot] {e}")
    try:
        asyncio.create_task(keepalive_loop())
        print("[keepalive] boot scheduled")
    except Exception as e: print(f"[keepalive-boot] {e}")

async def _on_error(update, context):
    print(f"[!] {type(context.error).__name__}: {context.error}")

def main(token: str = None, owner_id: int = None):
    global APP, TG_TOKEN, FORCED_OWNER
    if token: TG_TOKEN = token
    else: TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
    if not TG_TOKEN or ":" not in TG_TOKEN:
        print("[x] TG_TOKEN نبود."); return
    if owner_id: FORCED_OWNER = int(owner_id)
    else:
        try: FORCED_OWNER = int(os.environ.get("TG_OWNER_ID", "8389746549"))
        except Exception: FORCED_OWNER = 8389746549
    STATE["owner"] = FORCED_OWNER
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        _save(OWNER_FILE, {"owner": FORCED_OWNER})
    except Exception: pass
    print(f"[+] VERSION: {VERSION}")
    print(f"[+] DATA_DIR: {DATA_DIR}")
    print(f"[+] OWNER: {FORCED_OWNER}")

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
    APP.run_polling(allowed_updates=Update.ALL_TYPES,
                    poll_interval=2.0, timeout=30.0)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n[!] قطع")