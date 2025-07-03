# --- DOSYA: main.py (PARAKOLAY FATİHİ v1.0 - NİHAİ) ---
# Sadece Parakolay Checker. Bütün özellikler dahil. Hata yok.

import logging, requests, time, os, re, json, io, random, base64, hashlib
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
def home(): return "Parakolay Lord Bot Karargahı ayakta."
def run_flask(): app.run(host='0.0.0.0',port=8080)
def keep_alive(): Thread(target=run_flask).start()

# --- BÖLÜM 2: GİZLİ BİLGİLER ---
try:
    from bot_token import TELEGRAM_TOKEN, ADMIN_ID, PARAKOLAY_PUBLIC_KEY, PARAKOLAY_PRIVATE_KEY
except ImportError:
    print("KRİTİK HATA: 'bot_token.py' dosyası bulunamadı veya bilgileri eksik!"); exit()

# -----------------------------------------------------------------------------
# 3. BİRİM: İSTİHBARAT & OPERASYON (PARAKOLAY ÖZEL HAREKAT)
# -----------------------------------------------------------------------------
class ParakolayChecker:
    def __init__(self, public_key, private_key):
        self.public_key = public_key
        self.private_key = private_key
        self.base_url = "https://api-test.parakolay.com"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"})
        self.timeout = 30

    def _get_auth_header(self, body_str):
        nonce = str(int(time.time() * 1000))
        hash_str = self.public_key + nonce + self.private_key + body_str
        signature = base64.b64encode(hashlib.sha256(hash_str.encode()).digest()).decode()
        return {'publicKey': self.public_key, 'nonce': nonce, 'signature': signature, 'Content-Type': 'application/json'}

    def check_card(self, card):
        try:
            parts = card.split('|')
            if len(parts) < 4: return "❌ HATA: Eksik kart bilgisi."
            ccn, month, year, cvc = parts[0], parts[1], "20"+parts[2] if len(parts[2]) == 2 else parts[2], parts[3]
            
            endpoint = "/point/inquiry" 
            payload = {"card": {"cardNumber": ccn, "cardExpireYear": year, "cardExpireMonth": month}}
            body_str = json.dumps(payload, separators=(',', ':'))
            headers = self._get_auth_header(body_str)
            
            response = self.session.post(f"{self.base_url}{endpoint}", data=body_str, headers=headers, timeout=self.timeout)
            data = response.json()

            if str(data.get('statusCode')) == '0':
                points = data.get('data', {}).get('totalPointAmount', 'Bulunamadı')
                return f"✅ Puan Sorgulandı: {points} Puan"
            else:
                return f"❌ Sonuç: {data.get('message', 'Bilinmeyen Parakolay Hatası')}"
        except Exception as e:
            return f"❌ KRİTİK HATA (Parakolay): {e}"

# -----------------------------------------------------------------------------
# 4. BİRİM: LORDLAR SİCİL DAİRESİ (User Manager)
# -----------------------------------------------------------------------------
class UserManager:
    # ... (Bu class'ta hiçbir değişiklik yok, öncekiyle aynı)
    def __init__(self, initial_admin_id):
        self.keys_file="keys.txt"; self.activated_users_file="activated_users.json"
        self.admin_keys_file="admin_keys.txt"; self.activated_admins_file="activated_admins.json"
        self.unused_keys=self._load_from_file(self.keys_file); self.activated_users=self._load_from_json(self.activated_users_file)
        self.unused_admin_keys=self._load_from_file(self.admin_keys_file); self.activated_admins=self._load_from_json(self.activated_admins_file)
        if not self.activated_admins and initial_admin_id!=0:self.activated_admins[str(initial_admin_id)]="founding_father";logging.info(f"Kurucu Komutan (ID:{initial_admin_id}) admin olarak atandı.");self._save_all_data()
    def _load_from_file(self,f):
        if not os.path.exists(f):return set()
        with open(f,"r")as file:return{l.strip()for l in file if l.strip()}
    def _load_from_json(self,f):
        if not os.path.exists(f):return{}
        with open(f,"r",encoding="utf-8")as file:
            try:return json.load(file)
            except json.JSONDecodeError:return{}
    def _save_all_data(self):
        with open(self.keys_file,"w")as f:f.write("\n".join(self.unused_keys))
        with open(self.activated_users_file,"w")as f:json.dump(self.activated_users,f,indent=4)
        with open(self.admin_keys_file,"w")as f:f.write("\n".join(self.unused_admin_keys))
        with open(self.activated_admins_file,"w")as f:json.dump(self.activated_admins,f,indent=4)
    def is_user_activated(self,uid):return str(uid)in self.activated_users or self.is_user_admin(uid)
    def is_user_admin(self,uid):return str(uid)in self.activated_admins
    def activate_user(self,uid,key):
        if self.is_user_activated(str(uid)):return"Zaten bir Lord'sun."
        if key in self.unused_keys:self.activated_users[str(uid)]=key;self.unused_keys.remove(key);self._save_all_data();return"Success"
        return"Geçersiz veya kullanılmış anahtar."
    def activate_admin(self,uid,key):
        if self.is_user_admin(str(uid)):return"Zaten Komuta Kademesindesin."
        if key in self.unused_admin_keys:self.activated_admins[str(uid)]=key;self.unused_admin_keys.remove(key);self._save_all_data();return"Success"
        return"Geçersiz veya kullanılmış Vezir Fermanı."

# -----------------------------------------------------------------------------
# 5. BİRİM: EMİR SUBAYLARI (Handlers)
# -----------------------------------------------------------------------------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)
def log_activity(u:User,c:str,r:str):
    m=re.sub(r'(\d{6})\d{6}(\d{4})',r'\1******\2',c.split('|')[0])+'|'+'|'.join(c.split('|')[1:])
    le=f"[{datetime.now():%Y-%m-%d %H:%M:%S}] - @{u.username}({u.id}) - KART:{m} - SONUÇ:{r}\n"
    with open("terminator_logs.txt","a",encoding="utf-8")as f:f.write(le)
async def bulk_check_job(c:ContextTypes.DEFAULT_TYPE):
    j=c.job.data;uid=j['user_id'];u=j['user'];cs=j['cards'];pmid=j['progress_message_id']
    tc=len(cs);sc:ParakolayChecker=c.bot_data['parakolay_checker'];rc="";lut=time.time()
    try:
        for i,card in enumerate(cs):
            rs=sc.check_card(card);log_activity(u,card,rs)
            rc+=f"KART:{card}\nSONUÇ:{rs}\n\n";time.sleep(1.5)
            ct=time.time()
            if(i+1)%5==0 or ct-lut>5:
                p=i+1;pp=int((p/tc)*10);pb='█'*pp+'─'*(10-pp)
                pt=f"<code>[{pb}]</code>\n\n<b>Taranıyor:</b> {p}/{tc}"
                try:await c.bot.edit_message_text(text=pt,chat_id=uid,message_id=pmid,parse_mode=ParseMode.HTML);lut=ct
                except BadRequest as e:
                    if"Message is not modified"not in str(e):logging.warning(f"Durum raporu güncellenemedi: {e}")
    except Exception as e:
        logging.error(f"Toplu check hatası: {e}")
        await c.bot.edit_message_text(chat_id=uid,message_id=pmid,text=f"❌ Operasyon sırasında hata: {e}");return
    await c.bot.edit_message_text(text=f"✅ Tarama bitti!",chat_id=uid,message_id=pmid)
    rf=io.BytesIO(rc.encode('utf-8'))
    await c.bot.send_document(chat_id=uid,document=rf,filename="sonuclar.txt",caption=f"{tc} kartlık raporun hazır.")
async def start_command(u:Update,c:ContextTypes.DEFAULT_TYPE):
    um:UserManager=c.bot_data['user_manager']
    if um.is_user_activated(u.effective_user.id):await u.message.reply_text("Lordum, emrindeyim!\n`/puan` komutuyla puan sorgulayabilir,\n`/ayikla` komutuyla sonuçları ayıklayabilirsin.")
    else:
        await u.message.reply_text("Parakolay Lord Checker'a hoşgeldin,\nSahip: @tanriymisimben")
        kb=[[InlineKeyboardButton("Evet, bir key'im var ✅",callback_data="activate_start"),InlineKeyboardButton("Hayır, bir key'im yok",callback_data="activate_no_key")]]
        await u.message.reply_text("Botu kullanmak için bir key'in var mı?",reply_markup=InlineKeyboardMarkup(kb))
async def puan_command(u:Update,c:ContextTypes.DEFAULT_TYPE):
    um:UserManager=c.bot_data['user_manager']
    if not um.is_user_activated(u.effective_user.id):await u.message.reply_text("Önce /start ile anahtar aktive etmelisin.");return
    c.user_data['checker_info']={'type':'parakolay'}
    kb=[[InlineKeyboardButton("Tekli Kontrol",callback_data="mode_single"),InlineKeyboardButton("Çoklu Kontrol",callback_data="mode_multiple")]]
    await u.message.reply_text(f"**PARAKOLAY PUAN** cephesi seçildi. Modu seç:",reply_markup=InlineKeyboardMarkup(kb),parse_mode=ParseMode.MARKDOWN)
async def ayikla_command(u:Update,c:ContextTypes.DEFAULT_TYPE):
    um:UserManager=c.bot_data['user_manager']
    if not um.is_user_activated(u.effective_user.id):await u.message.reply_text("Önce /start ile anahtar aktive etmelisin.");return
    c.user_data['awaiting_sort_file']=True;await u.message.reply_text("Ayıklanacak sonuçların olduğu `.txt` dosyasını gönder.")
async def addadmin_command(u:Update,c:ContextTypes.DEFAULT_TYPE):
    um:UserManager=c.bot_data['user_manager'];key=c.args[0]if c.args else None
    if not key:await u.message.reply_text("Kullanım: `/addadmin <admin-anahtarı>`");return
    rs=um.activate_admin(u.effective_user.id,key)
    if rs=="Success":await u.message.reply_text("✅ Ferman kabul edildi! Artık Komuta Kademesindesin.")
    else:await u.message.reply_text(f"❌ {rs}")
async def logs_command(u:Update,c:ContextTypes.DEFAULT_TYPE):
    um:UserManager=c.bot_data['user_manager']
    if not um.is_user_admin(u.effective_user.id):await u.message.reply_text("Bu emri sadece Komuta Kademesi verebilir.");return
    if os.path.exists("terminator_logs.txt"):await u.message.reply_document(document=open("terminator_logs.txt",'rb'),caption="İstihbarat raporu.")
    else:await u.message.reply_text("Henüz toplanmış bir istihbarat yok.")
async def duyuru_command(u:Update,c:ContextTypes.DEFAULT_TYPE):
    um:UserManager=c.bot_data['user_manager']
    if not um.is_user_admin(u.effective_user.id):await u.message.reply_text("Bu emri sadece Komuta Kademesi verebilir.");return
    if not c.args:await u.message.reply_text("Kullanım: `/duyuru Mesajınız`");return
    dm=" ".join(c.args);auids=set(um.activated_users.keys())|set(um.activated_admins.keys())
    if not auids:await u.message.reply_text("Duyuru gönderilecek kimse bulunamadı.");return
    await u.message.reply_text(f"Ferman hazırlanıyor... {len(auids)} kişiye gönderilecek.")
    s,f=0,0
    for uid in auids:
        try:await c.bot.send_message(chat_id=int(uid),text=f"📣 **Ferman:**\n\n{dm}");s+=1
        except:f+=1;time.sleep(0.1)
    await u.message.reply_text(f"✅ Ferman operasyonu tamamlandı!\nBaşarıyla gönderildi: {s}\nBaşarısız: {f}")
async def button_callback(u:Update,c:ContextTypes.DEFAULT_TYPE):
    q=u.callback_query;await q.answer();a=q.data;nt=None
    if a=="activate_start":c.user_data['awaiting_key']=True;nt="🔑 Lütfen sana verilen anahtarı şimdi gönder."
    elif a=="activate_no_key":nt="Key almak için @tanriymisimben e başvurabilirsin."
    elif a.startswith("mode_"):
        m=a.split('_')[1];c.user_data['mode']=m
        if m=='single':nt="✅ **Tekli Mod** seçildi.\nŞimdi bir adet kart yolla."
        elif m=='multiple':c.user_data['awaiting_bulk_file']=True;nt="✅ **Çoklu Mod** seçildi.\nŞimdi içinde kartların olduğu `.txt` dosyasını gönder."
    if nt:
        try:await q.edit_message_text(text=nt,parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            if"Message is not modified"not in str(e):logging.warning(f"Button callback hatası: {e}")
async def main_message_handler(u:Update,c:ContextTypes.DEFAULT_TYPE):
    um:UserManager=c.bot_data['user_manager']
    if c.user_data.get('awaiting_key',False):
        key=u.message.text.strip();rs=um.activate_user(u.effective_user.id,key)
        if rs=="Success":await u.message.reply_text("✅ Anahtar kabul edildi!\n\nLord ailesine hoşgeldiniz. `/puan` komutunu kullanabilirsiniz.")
        else:await u.message.reply_text(f"❌ {rs}")
        c.user_data['awaiting_key']=False;return
    if not um.is_user_activated(u.effective_user.id):await u.message.reply_text("Botu kullanmak için /start yazarak başla.");return
    if'mode'not in c.user_data:await u.message.reply_text("Önce `/puan` komutuyla bir tarama modu seçmen lazım.");return
    if c.user_data.get('mode')=='single':
        cs=re.findall(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$',u.message.text)
        if not cs:return
        card=cs[0];await u.message.reply_text(f"Tekli modda kart taranıyor...")
        sc:ParakolayChecker=c.bot_data['parakolay_checker'];rs=sc.check_card(card);log_activity(u.effective_user,card,rs)
        await u.message.reply_text(f"KART: {card}\nSONUÇ: {rs}")
        c.user_data.pop('mode',None);c.user_data.pop('checker_info',None)
async def document_handler(u:Update,c:ContextTypes.DEFAULT_TYPE):
    um:UserManager=c.bot_data['user_manager']
    if not um.is_user_activated(u.effective_user.id):return
    if c.user_data.get('awaiting_sort_file'):
        await u.message.reply_text("Sonuç dosyası alındı, ayıklanıyor...");
        try:
            f=await c.bot.get_file(u.message.document);fcb=await f.download_as_bytearray();fc=fcb.decode('utf-8')
        except Exception as e:await u.message.reply_text(f"Dosyayı okurken bir hata oldu: {e}");return
        at="";mk=""
        for l in fc.splitlines():
            l=l.strip()
            if l.startswith("KART:"):mk=l
            elif l.startswith("SONUÇ:")and("Approved"in l or"✅"in l or"Live"in l):
                if mk:fe=f"{mk}\n{l}\n\n";at+=fe;mk=""
            elif not l:mk=""
        c.user_data.pop('awaiting_sort_file',None)
        if not at:await u.message.reply_text("ℹ️ Yolladığın dosyada 'Approved' sonuçlu kart bulunamadı.");return
        rf=io.BytesIO(at.encode('utf-8'))
        await c.bot.send_document(chat_id=u.effective_user.id,document=rf,filename="approved_sonuclar.txt",caption="İşte ayıklanmış canlı kartların listesi.");return
    if c.user_data.get('awaiting_bulk_file'):
        pm=await u.message.reply_text("Dosya alındı... Konvoy indiriliyor...")
        try:
            f=await c.bot.get_file(u.message.document);fcb=await f.download_as_bytearray();fc=fcb.decode('utf-8')
        except Exception as e:await pm.edit_text(f"Dosyayı okurken bir hata oldu: {e}");return
        cs=[];
        for l in fc.splitlines():
            if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$',l.strip()):cs.append(l.strip())
        if not cs:await pm.edit_text("Dosyanın içinde geçerli formatta kart bulamadım.");return
        is_admin=um.is_user_admin(u.effective_user.id);limit=5000 if is_admin else 120
        if len(cs)>limit:await pm.edit_text(f"DUR! Kart sayısı ({len(cs)}) limitini ({limit}) aşıyor.");return
        jd={'user_id':u.effective_user.id,'user':u.effective_user,'cards':cs,'progress_message_id':pm.message_id}
        c.job_queue.run_once(bulk_check_job,1,data=jd,name=f"check_{u.effective_user.id}")
        await pm.edit_text("✅ Emir alındı! Operasyon Çavuşu görevi devraldı.")
        c.user_data.pop('awaiting_bulk_file',None);c.user_data.pop('mode',None)

# -----------------------------------------------------------------------------
# 6. BİRİM: ANA KOMUTA MERKEZİ (main)
# -----------------------------------------------------------------------------
def main():
    if not TELEGRAM_TOKEN or"BURAYA"in TELEGRAM_TOKEN or not ADMIN_ID:print("KRİTİK HATA: 'bot_token.py' dosyası eksik!");return
    keep_alive()
    parakolay_checker=ParakolayChecker(public_key=PARAKOLAY_PUBLIC_KEY, private_key=PARAKOLAY_PRIVATE_KEY)
    print("Parakolay birimi hazır.")
    user_manager_instance=UserManager(initial_admin_id=ADMIN_ID)
    print("Parakolay Lord Bot (NİHAİ) aktif...")
    app=Application.builder().token(TELEGRAM_TOKEN).build()
    app.bot_data['parakolay_checker']=parakolay_checker;app.bot_data['user_manager']=user_manager_instance
    app.add_handler(CommandHandler("start",start_command))
    app.add_handler(CommandHandler(["check","puan"],puan_command))
    app.add_handler(CommandHandler("ayikla",ayikla_command))
    app.add_handler(CommandHandler("addadmin",addadmin_command))
    app.add_handler(CommandHandler("logs",logs_command))
    app.add_handler(CommandHandler("duyuru",duyuru_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,main_message_handler))
    app.add_handler(MessageHandler(filters.Document.TXT,document_handler))
    app.run_polling()

if __name__=='__main__':
    main()
