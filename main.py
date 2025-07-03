# --- DOSYA: main.py (v42 - NİHAİ TÖVBE / SADECE APISERVISIM) ---
# BÜTÜN DİĞER CHECKER'LAR İMHA EDİLDİ. SADECE apiservisim.store KULLANILIYOR.
# BÜTÜN HATALAR DÜZELTİLDİ. BU SON KOD.

import logging, requests, time, os, re, json, io
from urllib.parse import quote
from datetime import datetime
from flask import Flask
from threading import Thread

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest

# --- BÖLÜM 1: NÖBETÇİ KULÜBESİ ---
app = Flask('')
@app.route('/')
def home(): return "ApiServisim Lord Botu Karargahı ayakta."
def run_flask(): app.run(host='0.0.0.0',port=8080)
def keep_alive(): Thread(target=run_flask).start()

# --- BÖLÜM 2: GİZLİ BİLGİLER ---
try:
    from bot_token import TELEGRAM_TOKEN, ADMIN_ID
except ImportError:
    print("KRİTİK HATA: 'bot_token.py' dosyası bulunamadı!"); exit()

# -----------------------------------------------------------------------------
# 3. BİRİM: İSTİHBARAT & OPERASYON (ApiServisim Özel Harekat)
# -----------------------------------------------------------------------------
class ApiServiceChecker:
    def __init__(self, key):
        self.base_url = "https://apiservisim.store/"
        self.key = key
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
        self.timeout = 30

    def login(self) -> bool:
        try:
            login_url = f"{self.base_url}giris.php"
            payload = {'key': self.key}
            response = self.session.post(login_url, data=payload, allow_redirects=True)
            if response.ok and "index.php" in response.url:
                logging.info("ApiServiceChecker girişi başarılı.")
                return True
            else:
                logging.error(f"ApiServiceChecker giriş başarısız. Son URL: {response.url}")
                return False
        except Exception as e:
            logging.error(f"ApiServiceChecker giriş hatası: {e}"); return False

    def _check(self, gateway_php_file, card):
        try:
            # Gelen bilgilere göre API dosyaları ana dizinde
            endpoint = f"{self.base_url}{gateway_php_file}"
            form_data = {'lista': card} # Key session'da zaten var, tekrar yollamaya gerek yok.
            response = self.session.post(endpoint, data=form_data, timeout=self.timeout)
            return response.text.strip()
        except requests.exceptions.RequestException as e:
            return f"❌ HATA ({gateway_php_file}): {e}"

    def check_paypal1(self, card): return self._check('paypal1dolars.php', card)
    def check_pv1(self, card): return self._check('api1.php', card)
    def check_pv2(self, card): return self._check('xrayefe.php', card)
    def check_exx(self, card): return self._check('exxenapi.php', card)

# -----------------------------------------------------------------------------
# 4. BİRİM: LORDLAR SİCİL DAİRESİ (User Manager)
# -----------------------------------------------------------------------------
class UserManager:
    def __init__(self, initial_admin_id):
        self.keys_file = "keys.txt"; self.activated_users_file = "activated_users.json"
        self.admin_keys_file = "admin_keys.txt"; self.activated_admins_file = "activated_admins.json"
        self.unused_keys = self._load_from_file(self.keys_file); self.activated_users = self._load_from_json(self.activated_users_file)
        self.unused_admin_keys = self._load_from_file(self.admin_keys_file); self.activated_admins = self._load_from_json(self.activated_admins_file)
        if not self.activated_admins and initial_admin_id != 0:
             self.activated_admins[str(initial_admin_id)] = "founding_father"; logging.info(f"Kurucu Komutan (ID: {initial_admin_id}) admin olarak atandı."); self._save_all_data()
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
    job_data = context.job.data; user_id = job_data['user_id']; user = job_data['user']
    cards = job_data['cards']; progress_message_id = job_data['progress_message_id']
    checker_method_name = job_data['checker_method']
    total_cards = len(cards); site_checker: ApiServiceChecker = context.bot_data['api_service_checker']
    check_function = getattr(site_checker, checker_method_name)
    report_content = ""; last_update_time = time.time()
    try:
        for i, card in enumerate(cards):
            result = check_function(card); log_activity(user, card, result)
            report_content += f"KART: {card}\nSONUÇ: {result}\n\n"; time.sleep(1)
            current_time = time.time()
            if (i + 1) % 10 == 0 or current_time - last_update_time > 3:
                progress = i + 1; progress_percent = int((progress / total_cards) * 10)
                progress_bar = '█' * progress_percent + '─' * (10 - progress_percent)
                progress_text = f"<code>[{progress_bar}]</code>\n\n<b>Taranıyor:</b> {progress} / {total_cards}"
                try:
                    await context.bot.edit_message_text(text=progress_text, chat_id=user_id, message_id=progress_message_id, parse_mode=ParseMode.HTML)
                    last_update_time = current_time
                except BadRequest as e:
                    if "Message is not modified" not in str(e): logging.warning(f"Durum raporu güncellenemedi: {e}")
    except Exception as e:
        logging.error(f"Toplu check sırasında hata: {e}")
        await context.bot.edit_message_text(chat_id=user_id, message_id=progress_message_id, text=f"❌ Komutanım, operasyon sırasında bir hata oluştu: {e}"); return
    await context.bot.edit_message_text(text=f"✅ Tarama bitti! Rapor hazırlanıp yollanıyor...", chat_id=user_id, message_id=progress_message_id)
    report_file = io.BytesIO(report_content.encode('utf-8'))
    await context.bot.send_document(chat_id=user_id, document=report_file, filename="sonuclar.txt", caption=f"Operasyon tamamlandı. {total_cards} kartlık raporun ektedir.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Lordum, emrindeyim! Kullanabileceğin komutlar:\n`/paypal1`\n`/pv1`\n`/pv2`\n`/exx`\n\nSonuçları ayıklamak için: `/ayikla`")
    else:
        await update.message.reply_text("Api Service Checker'a hoşgeldin,\nherhangi bir sorunun olursa Owner: @Farkederli e sorabilirsin.")
        keyboard = [[InlineKeyboardButton("Evet, bir key'im var ✅", callback_data="activate_start"), InlineKeyboardButton("Hayır, bir key'im yok", callback_data="activate_no_key")]]
        await update.message.reply_text("Botu kullanmak için bir key'in var mı?", reply_markup=InlineKeyboardMarkup(keyboard))

def checker_command_factory(method_name, display_name):
    async def command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_manager: UserManager = context.bot_data['user_manager']
        if not user_manager.is_user_activated(update.effective_user.id):
            await update.message.reply_text("Bu komutu kullanmak için önce /start yazarak bir anahtar aktive etmelisin."); return
        context.user_data['checker_method'] = method_name
        keyboard = [[InlineKeyboardButton("Tekli Kontrol", callback_data="mode_single"), InlineKeyboardButton("Çoklu Kontrol", callback_data="mode_multiple")]]
        await update.message.reply_text(f"**{display_name}** cephesi seçildi. Tarama modunu seç Lord'um:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return command_handler

async def ayikla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmak için önce /start yazarak bir anahtar aktive etmelisin."); return
    context.user_data['awaiting_sort_file'] = True
    await update.message.reply_text("Ganimet ayıklama emri alındı.\nİçinde karışık sonuçların olduğu `.txt` dosyasını gönder.")

async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']; key = context.args[0] if context.args else None
    if not key: await update.message.reply_text("Kullanım: `/addadmin <admin-anahtarı>`"); return
    result = user_manager.activate_admin(update.effective_user.id, key)
    if result == "Success": await update.message.reply_text("✅ Ferman kabul edildi! Artık Komuta Kademesindesin.")
    else: await update.message.reply_text(f"❌ {result}")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_admin(update.effective_user.id): await update.message.reply_text("Bu emri sadece Komuta Kademesi verebilir."); return
    if os.path.exists("terminator_logs.txt"): await update.message.reply_document(document=open("terminator_logs.txt", 'rb'), caption="İstihbarat raporu.")
    else: await update.message.reply_text("Henüz toplanmış bir istihbarat yok.")

async def duyuru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_admin(update.effective_user.id): await update.message.reply_text("Bu emri sadece Komuta Kademesi verebilir."); return
    if not context.args: await update.message.reply_text("Kullanım: `/duyuru Mesajınız`"); return
    duyuru_mesaji = " ".join(context.args); all_user_ids = set(user_manager.activated_users.keys()) | set(user_manager.activated_admins.keys())
    if not all_user_ids: await update.message.reply_text("Duyuru gönderilecek kimse bulunamadı."); return
    await update.message.reply_text(f"Ferman hazırlanıyor... {len(all_user_ids)} kişiye gönderilecek.")
    success, fail = 0, 0
    for user_id in all_user_ids:
        try: await context.bot.send_message(chat_id=int(user_id), text=f"📣 **Komuta Kademesinden Ferman Var:**\n\n{duyuru_mesaji}"); success += 1
        except Exception: fail += 1; time.sleep(0.1)
    await update.message.reply_text(f"✅ Ferman operasyonu tamamlandı!\nBaşarıyla gönderildi: {success}\nBaşarısız: {fail}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); action = query.data; new_text = None
    if action == "activate_start": context.user_data['awaiting_key'] = True; new_text = "🔑 Lütfen sana verilen anahtarı şimdi gönder."
    elif action == "activate_no_key": new_text = "Key almak için @Farkederli e başvurabilirsin."
    elif action.startswith("mode_"):
        mode = action.split('_')[1]; context.user_data['mode'] = mode
        if mode == 'single': new_text = "✅ **Tekli Mod** seçildi.\nŞimdi bir adet kart yolla."
        elif mode == 'multiple':
            context.user_data['awaiting_bulk_file'] = True; new_text = "✅ **Çoklu Mod** seçildi.\nŞimdi içinde kartların olduğu `.txt` dosyasını gönder."
    if new_text:
        try: await query.edit_message_text(text=new_text, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            if "Message is not modified" not in str(e): logging.warning(f"Button callback hatası: {e}")

async def main_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if context.user_data.get('awaiting_key', False):
        key = update.message.text.strip(); result = user_manager.activate_user(update.effective_user.id, key)
        if result == "Success": await update.message.reply_text("✅ Anahtar kabul edildi!\n\nLord ailesine hoşgeldiniz.")
        else: await update.message.reply_text(f"❌ {result}")
        context.user_data['awaiting_key'] = False; return
    if not user_manager.is_user_activated(update.effective_user.id): await update.message.reply_text("Botu kullanmak için /start yazarak başla."); return
    if 'mode' not in context.user_data or 'checker_method' not in context.user_data:
        await update.message.reply_text("Önce bir checker komutuyla (`/paypal1` vs.) cephe ve mod seçmelisin."); return
    if context.user_data.get('mode') == 'single':
        cards = re.findall(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', update.message.text)
        if not cards: return
        card = cards[0]; await update.message.reply_text(f"Tekli modda kart taranıyor...")
        site_checker: ApiServiceChecker = context.bot_data['api_service_checker']
        checker_method_name = context.user_data['checker_method']
        check_function = getattr(site_checker, checker_method_name)
        result = check_function(card); log_activity(update.effective_user, card, result)
        await update.message.reply_text(f"KART: {card}\nSONUÇ: {result}")
        context.user_data.pop('mode', None); context.user_data.pop('checker_method', None)

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_activated(update.effective_user.id): return
    if context.user_data.get('awaiting_sort_file'):
        await update.message.reply_text("Sonuç dosyası alındı, ayıklanıyor...");
        try:
            file = await context.bot.get_file(update.message.document); file_content_bytes = await file.download_as_bytearray()
            file_content = file_content_bytes.decode('utf-8')
        except Exception as e: await update.message.reply_text(f"Dosyayı okurken bir hata oldu: {e}"); return
        approved_kartlar_text = ""; mevcut_kart = ""
        for line in file_content.splitlines():
            if line.strip().startswith("KART:"): mevcut_kart = line.strip()
            elif line.strip().startswith("SONUÇ:") and ("Approved" in line or "✅" in line or "Live" in line):
                if mevcut_kart: full_entry = f"{mevcut_kart}\n{line.strip()}\n\n"; approved_kartlar_text += full_entry; mevcut_kart = ""
            elif not line.strip(): mevcut_kart = ""
        context.user_data.pop('awaiting_sort_file', None)
        if not approved_kartlar_text:
            await update.message.reply_text("ℹ️ Yolladığın dosyada 'Approved' sonuçlu kart bulunamadı."); return
        report_file = io.BytesIO(approved_kartlar_text.encode('utf-8'))
        await context.bot.send_document(chat_id=update.effective_user.id, document=report_file, filename="approved_sonuclar.txt", caption="İşte ayıklanmış canlı kartların listesi."); return
    if context.user_data.get('awaiting_bulk_file'):
        progress_message = await update.message.reply_text("Dosya alındı... Hedefler kilitleniyor...")
        try:
            file = await context.bot.get_file(update.message.document); file_content_bytes = await file.download_as_bytearray()
            file_content = file_content_bytes.decode('utf-8')
        except Exception as e: await progress_message.edit_text(f"Dosyayı okurken bir hata oldu: {e}"); return
        cards = [];
        for line in file_content.splitlines():
            if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', line.strip()): cards.append(line.strip())
        if not cards: await progress_message.edit_text("Dosyanın içinde geçerli formatta kart bulamadım."); return
        is_admin = user_manager.is_user_admin(update.effective_user.id); limit = 5000 if is_admin else 120
        if len(cards) > limit:
            await progress_message.edit_text(f"DUR! Dosyadaki kart sayısı ({len(cards)}) limitini aşıyor. Senin limitin: {limit} kart."); return
        job_data = {'user_id': update.effective_user.id, 'user': update.effective_user, 'cards': cards, 'checker_method': context.user_data['checker_method'], 'progress_message_id': progress_message.message_id}
        context.job_queue.run_once(bulk_check_job, 1, data=job_data, name=f"check_{update.effective_user.id}")
        await progress_message.edit_text("✅ Emir alındı! Operasyon Çavuşu görevi devraldı. Canlı telsiz bağlantısı kuruldu.")
        context.user_data.pop('awaiting_bulk_file', None); context.user_data.pop('mode', None); context.user_data.pop('checker_method', None)

# -----------------------------------------------------------------------------
# 6. BİRİM: ANA KOMUTA MERKEZİ (main)
# -----------------------------------------------------------------------------
def main():
    if not TELEGRAM_TOKEN or "BURAYA" in TELEGRAM_TOKEN or not ADMIN_ID:
        print("KRİTİK HATA: 'bot_token.py' dosyasını doldurmadın!"); return
    keep_alive()
    api_service_checker = ApiServiceChecker(key="19d0c0f6f50a75b45df50b216b9b9fb8")
    if not api_service_checker.login(): print("UYARI: ApiServiceChecker'a giriş yapılamadı!")
    else: print("ApiServiceChecker birimi aktif.")
    user_manager_instance = UserManager(initial_admin_id=ADMIN_ID)
    print("Lordlar Kulübü (v41 - Nihai Tövbe) aktif...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.bot_data['api_service_checker'] = api_service_checker
    application.bot_data['user_manager'] = user_manager_instance
    
    # Bütün komutları ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("paypal1", checker_command_factory('check_paypal1', 'PayPal 1$')))
    application.add_handler(CommandHandler("pv1", checker_command_factory('check_pv1', 'Puan V1')))
    application.add_handler(CommandHandler("pv2", checker_command_factory('check_pv2', 'Puan V2')))
    application.add_handler(CommandHandler("exx", checker_command_factory('check_exx', 'Exxen')))
    application.add_handler(CommandHandler("ayikla", ayikla_command))
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("duyuru", duyuru_command))
    
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler))
    application.add_handler(MessageHandler(filters.Document.TXT, document_handler))
    
    application.run_polling()

if __name__ == '__main__':
    main()
