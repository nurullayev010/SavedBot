import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import os
import uuid
import json
import threading
from concurrent.futures import ThreadPoolExecutor

# ================= SOZLAMALAR =================
TOKEN = "8872228670:AAEkgyI0KZ64TDC5S4Z_bOPmSq6bRpYEkZk"
ADMIN_ID = 7322361107  # O'z ID raqamingizni yozing
DB_FILE = "insta_bot_db.json"
bot = telebot.TeleBot(TOKEN)
download_pool = ThreadPoolExecutor(max_workers=20)
user_lang = {}
admin_states = {}
cached_ad_message = {}

# ================= DATABASE =================
def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "channels": [], "groups": [], "subscription": False,
            "users": [], "downloads": 0, "show_users_stat": False
        }
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "channels": [], "groups": [], "subscription": False,
            "users": [], "downloads": 0, "show_users_stat": False
        }

db = load_db()
db_lock = threading.Lock()

def save_db():
    with db_lock:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

def save_user(uid):
    with db_lock:
        if uid not in db["users"]:
            db["users"].append(uid)
            save_db()

# ================= TAVSIFLAR =================
DESCRIPTIONS = {
    "uz": "📥 @insta_soxranit_bot - Сиз бу ботда Instagram'даги расм ва видеоларни тез юклаб олишингиз мумкин. Ботни яқинларингизга улашинг!\n\nSupport: @Kvartio_admin",
    "ru": "📥 @insta_soxranit_bot - В этом боте вы можете быстро скачивать фото и видео из Instagram. Поделитесь ботом с близкими!\n\nSupport: @Kvartio_admin"
}

# ================= MAJBURIY OBUNA FUNKSIYALARI =================
def check_sub(uid):
    if not db.get("subscription", False):
        return True
    all_targets = db.get("channels", []) + db.get("groups", [])
    if not all_targets:
        return True
    for target in all_targets:
        try:
            status = bot.get_chat_member(target, uid).status
            if status in ["left", "kicked", "banned"]:
                return False
        except:
            continue
    return True

def get_sub_keyboard(lang):
    markup = InlineKeyboardMarkup()
    for ch in db.get("channels", []):
        markup.add(InlineKeyboardButton(text="📢 Каналга аъзо бўлиш" if lang=="uz" else "📢 Подписаться на канал", url=f"https://t.me/{ch.replace('@', '')}"))
    for grp in db.get("groups", []):
        markup.add(InlineKeyboardButton(text="👥 Гуруҳга қўшилиш" if lang=="uz" else "👥 Вступить в группу", url=f"https://t.me/{grp.replace('@', '')}"))
    markup.add(InlineKeyboardButton(text="✅ Аъзо бўлдим" if lang=="uz" else "✅ Я подписался", callback_data="check_sub"))
    return markup

# ================= ADMIN PANEL MENYULARI =================
def admin_main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    sub = "🟢 Бор" if db.get("subscription") else "🔴 Йўқ"
    stat = "🟢 Ёниқ" if db.get("show_users_stat") else "🔴 Ўчиқ"
    markup.add(
        InlineKeyboardButton(f"Мажбурий обуна: {sub}", callback_data="adm_toggle_sub"),
        InlineKeyboardButton(f"Статистика: {stat}", callback_data="adm_toggle_stat"),
        InlineKeyboardButton("📢 Каналар", callback_data="adm_channels"),
        InlineKeyboardButton("👥 Гуруҳлар", callback_data="adm_groups"),
        InlineKeyboardButton("📊 Статистика маълумоти", callback_data="adm_stats_info"),
        InlineKeyboardButton("📨 Реклама юбориш", callback_data="adm_ads")
    )
    return markup

def channels_menu():
    markup = InlineKeyboardMarkup()
    for ch in db.get("channels", []):
        markup.add(InlineKeyboardButton(f"❌ Ўчириш: {ch}", callback_data=f"del_ch_{ch}"))
    markup.add(InlineKeyboardButton("➕ Канал қўшиш", callback_data="add_channel"))
    markup.add(InlineKeyboardButton("◀️ Орқага", callback_data="adm_back"))
    return markup

def groups_menu():
    markup = InlineKeyboardMarkup()
    for grp in db.get("groups", []):
        markup.add(InlineKeyboardButton(f"❌ Ўчириш: {grp}", callback_data=f"del_grp_{grp}"))
    markup.add(InlineKeyboardButton("➕ Гуруҳ қўшилиш", callback_data="add_group"))
    markup.add(InlineKeyboardButton("◀️ Орқага", callback_data="adm_back"))
    return markup

# ================= START & TIL =================
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    save_user(uid)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🇺🇿 O'zbek (Kiril)", callback_data="lang_uz"),
               InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
    bot.send_message(m.chat.id, "Тилни танланг / Выберите язык:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_lang(call):
    lang = call.data.split("_")[1]
    user_lang[call.from_user.id] = lang
    
    if not check_sub(call.from_user.id):
        text = "Ботдан фойдаланиш учун қуйидаги канал ва гуруҳларга аъзо бўлинг:" if lang == "uz" else "Для использования бота подпишитесь на каналы и группы:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_sub_keyboard(lang))
        return
    
    send_main_interface(call.message.chat.id, call.from_user.id, lang, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def verify_sub(call):
    uid = call.from_user.id
    lang = user_lang.get(uid, "uz")
    if check_sub(uid):
        send_main_interface(call.message.chat.id, uid, lang, call.message.message_id)
    else:
        text = "Сиз ҳали ҳамма жойга аъзо бўлмадингиз!" if lang == "uz" else "Вы подписались не на все каналы/группы!"
        bot.answer_callback_query(call.id, text, show_alert=True)

def send_main_interface(chat_id, uid, lang, message_id=None):
    msg_text = "Салом! Instagram ҳаволани менга юборинг." if lang == "uz" else "Привет! Отправь мне ссылку из Instagram."
    if db.get("show_users_stat"):
        users_count = len(db["users"])
        stat_append = f"\n\n👥 Фойдаланувчилар сони: {users_count}" if lang == "uz" else f"\n\n👥 Количество пользователей: {users_count}"
        msg_text += stat_append
        
    if message_id:
        try:
            bot.edit_message_text(msg_text, chat_id, message_id)
        except:
            bot.send_message(chat_id, msg_text)
    else:
        bot.send_message(chat_id, msg_text)

# ================= ADMIN PANEL HANDLERLARI =================
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if m.from_user.id != ADMIN_ID: return
    bot.send_message(m.chat.id, "🛠 **Админ панель:**", reply_markup=admin_main_menu(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_") or call.data in ["add_channel", "add_group", "adm_back"] or call.data.startswith("del_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID: return
    chat_id = call.message.chat.id
    data = call.data
    
    if data == "adm_toggle_sub":
        db["subscription"] = not db.get("subscription", False)
        save_db()
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=admin_main_menu())
    elif data == "adm_toggle_stat":
        db["show_users_stat"] = not db.get("show_users_stat", False)
        save_db()
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=admin_main_menu())
    elif data == "adm_channels":
        bot.edit_message_text("📢 **Каналларни бошқариш:**", chat_id, call.message.message_id, reply_markup=channels_menu(), parse_mode="Markdown")
    elif data == "adm_groups":
        bot.edit_message_text("👥 **Груҳларни бошқариш:**", chat_id, call.message.message_id, reply_markup=groups_menu(), parse_mode="Markdown")
    elif data == "adm_stats_info":
        bot.answer_callback_query(call.id, f"Фойдаланувчилар: {len(db['users'])}\nЮкламалар сони: {db['downloads']}", show_alert=True)
    elif data == "adm_ads":
        admin_states[ADMIN_ID] = "waiting_for_ad"
        bot.send_message(chat_id, "📨 Реклама учун пост (расм, видео ёки матн) юборинг:")
    elif data == "add_channel":
        admin_states[ADMIN_ID] = "waiting_for_channel"
        bot.send_message(chat_id, "Канал username'сини юборинг (масалан: @kanal_nomi):")
    elif data == "add_group":
        admin_states[ADMIN_ID] = "waiting_for_group"
        bot.send_message(chat_id, "Груҳ username'сини юборинг (масалан: @guruh_nomi):")
    elif data.startswith("del_ch_"):
        ch_name = data.replace("del_ch_", "")
        if ch_name in db["channels"]:
            db["channels"].remove(ch_name)
            save_db()
        bot.edit_message_text("📢 **Каналларни бошқариш:**", chat_id, call.message.message_id, reply_markup=channels_menu(), parse_mode="Markdown")
    elif data.startswith("del_grp_"):
        grp_name = data.replace("del_grp_", "")
        if grp_name in db["groups"]:
            db["groups"].remove(grp_name)
            save_db()
        bot.edit_message_text("👥 **Груҳларни бошқариш:**", chat_id, call.message.message_id, reply_markup=groups_menu(), parse_mode="Markdown")
    elif data == "adm_back":
        bot.edit_message_text("🛠 **Админ панель:**", chat_id, call.message.message_id, reply_markup=admin_main_menu(), parse_mode="Markdown")

# ================= REKLAMA VA QO'SHISH MATNLARI =================
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and ADMIN_ID in admin_states and admin_states[ADMIN_ID] is not None, content_types=['text', 'photo', 'video'])
def admin_text_handler(m):
    state = admin_states[ADMIN_ID]
    if state == "waiting_for_channel":
        ch = m.text.strip()
        if not ch.startswith("@"): ch = "@" + ch
        if ch not in db["channels"]:
            db["channels"].append(ch)
            save_db()
        bot.send_message(m.chat.id, f"Канал қўшилди: {ch}", reply_markup=admin_main_menu())
        admin_states[ADMIN_ID] = None
    elif state == "waiting_for_group":
        grp = m.text.strip()
        if not grp.startswith("@"): grp = "@" + grp
        if grp not in db["groups"]:
            db["groups"].append(grp)
            save_db()
        bot.send_message(m.chat.id, f"Груҳ қўшилди: {grp}", reply_markup=admin_main_menu())
        admin_states[ADMIN_ID] = None
    elif state == "waiting_for_ad":
        cached_ad_message[ADMIN_ID] = m
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🧪 Тест қилиб кўриш", callback_data="ad_test"),
            InlineKeyboardButton("🚀 Юбориш", callback_data="ad_send")
        )
        bot.send_message(m.chat.id, "Реклама қабул қилинди. Нима қиламиз?", reply_markup=markup)
        admin_states[ADMIN_ID] = None

@bot.callback_query_handler(func=lambda call: call.data in ["ad_test", "ad_send"])
def ad_actions(call):
    if call.from_user.id != ADMIN_ID: return
    if call.data == "ad_test":
        msg = cached_ad_message.get(ADMIN_ID)
        if msg:
            bot.copy_message(ADMIN_ID, msg.chat.id, msg.message_id)
            bot.answer_callback_query(call.id, "Тест кўриниш юборилди!")
    elif call.data == "ad_send":
        msg = cached_ad_message.get(ADMIN_ID)
        if msg:
            success, fail = 0, 0
            for uid in db["users"]:
                try:
                    bot.copy_message(uid, msg.chat.id, msg.message_id)
                    success += 1
                except:
                    fail += 1
            bot.answer_callback_query(call.id, f"Юборилди: {success}, Хато: {fail}", show_alert=True)

# ================= INSTAGRAM YUKLASH =================
@bot.message_handler(func=lambda m: m.text and "instagram.com" in m.text)
def handle_link(m):
    uid = m.from_user.id
    save_user(uid)
    lang = user_lang.get(uid, "uz")
    
    if not check_sub(uid):
        text = "Ботдан фойдаланиш учун канал ва гуруҳларга аъзо бўлинг!" if lang=="uz" else "Подпишитесь на каналы и группы!"
        bot.reply_to(m, text, reply_markup=get_sub_keyboard(lang))
        return
    
    msg = bot.reply_to(m, "⏳ Юкланмоқда..." if lang == "uz" else "⏳ Загрузка...")
    
    def process():
        try:
            fname = f"{uuid.uuid4()}.mp4"
            with yt_dlp.YoutubeDL({'format': 'best', 'outtmpl': fname, 'quiet': True}) as ydl:
                ydl.download([m.text])
            bot.send_video(m.chat.id, open(fname, 'rb'), caption=DESCRIPTIONS[lang])
            bot.delete_message(m.chat.id, msg.message_id)
            os.remove(fname)
            with db_lock:
                db["downloads"] += 1
                save_db()
        except:
            bot.edit_message_text("Хатолик ю берди! Мурожаат: @Kvartio_admin", m.chat.id, msg.message_id)
            
    download_pool.submit(process)

bot.infinity_polling()

from flask import Flask
from threading import Thread

app = Flask('')


@app.route('/')
def home():
  I am alive!


def run():
  app.run(host='0.0.0.0', port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# Buni eng pastga bot.infinity_polling() dan oldin yozasiz
keep_alive()

