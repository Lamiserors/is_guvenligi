import asyncio
import sys
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from datetime import datetime
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

# PostgreSQL bağlantı bilgileri
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "is_guvenligi"
DB_USER = "postgres"
DB_PASS = "123456"
BOT_TOKEN = "8169151245:AAEED2Z40XIhWbxydUaeS2yxh36pEoc72Ds"
ADMIN_USERS = [5923574338]  # Admin chat ID'leri

# Connection pool
connection_pool = None

def veritabani_baglan():
    """PostgreSQL bağlantı havuzu oluştur"""
    global connection_pool
    try:
        connection_pool = SimpleConnectionPool(
            1, 20,  # Min 1, Max 20 bağlantı
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        print("✅ PostgreSQL bağlantı havuzu oluşturuldu")
    except Exception as e:
        print(f"❌ PostgreSQL bağlantı hatası: {e}")
        sys.exit(1)

def tabloyu_olustur():
    """Kullanıcılar tablosunu oluştur"""
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        
        # Kullanıcılar tablosu
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bot_kullanicilar (
                chat_id BIGINT PRIMARY KEY,
                ad_soyad VARCHAR(100) NOT NULL,
                mail VARCHAR(100) NOT NULL,
                departman VARCHAR(100) NOT NULL,
                kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                aktif BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Bildirim geçmişi tablosu
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bildirim_gecmisi (
                id SERIAL PRIMARY KEY,
                bildirim_turu VARCHAR(50) NOT NULL,
                hedef_turu VARCHAR(20) NOT NULL,
                hedef_departman VARCHAR(100),
                gonderilen_kullanici_sayisi INTEGER,
                basarili_gonderim INTEGER,
                basarisiz_gonderim INTEGER,
                gonderim_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_chat_id BIGINT
            )
        ''')
        
        conn.commit()
        print("✅ Veritabanı tabloları oluşturuldu")
        
    except Exception as e:
        print(f"❌ Tablo oluşturma hatası: {e}")
    finally:
        if conn:
            connection_pool.putconn(conn)

def tarih_saat_formatla():
    """Türkçe tarih saat formatı"""
    now = datetime.now()
    return now.strftime("%d.%m.%Y %H:%M")

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Conversation states
AD_SOYAD, MAIL, DEPARTMAN = range(3)

# Veritabanı işlemleri
def kullanici_kaydet(chat_id, ad_soyad, mail, departman):
    """Kullanıcı kaydetme"""
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO bot_kullanicilar (chat_id, ad_soyad, mail, departman)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (chat_id) 
            DO UPDATE SET 
                ad_soyad = EXCLUDED.ad_soyad,
                mail = EXCLUDED.mail,
                departman = EXCLUDED.departman,
                kayit_tarihi = CURRENT_TIMESTAMP
        ''', (chat_id, ad_soyad, mail, departman))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Kullanıcı kaydetme hatası: {e}")
        return False
    finally:
        if conn:
            connection_pool.putconn(conn)

def kullanici_var_mi(chat_id):
    """Kullanıcı kontrolü"""
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        
        cur.execute('SELECT chat_id FROM bot_kullanicilar WHERE chat_id = %s AND aktif = TRUE', (chat_id,))
        result = cur.fetchone()
        return result is not None
        
    except Exception as e:
        print(f"❌ Kullanıcı kontrol hatası: {e}")
        return False
    finally:
        if conn:
            connection_pool.putconn(conn)

def tum_kullanicilari_getir():
    """Tüm aktif kullanıcıları getir"""
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        
        cur.execute('SELECT chat_id, ad_soyad, departman FROM bot_kullanicilar WHERE aktif = TRUE')
        users = cur.fetchall()
        return users
        
    except Exception as e:
        print(f"❌ Kullanıcı listesi hatası: {e}")
        return []
    finally:
        if conn:
            connection_pool.putconn(conn)

def departman_kullanicilari_getir(departman):
    """Departman kullanıcılarını getir"""
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        
        cur.execute('SELECT chat_id, ad_soyad FROM bot_kullanicilar WHERE departman = %s AND aktif = TRUE', (departman,))
        users = cur.fetchall()
        return users
        
    except Exception as e:
        print(f"❌ Departman kullanıcıları hatası: {e}")
        return []
    finally:
        if conn:
            connection_pool.putconn(conn)

def kullanici_bilgisi_getir(chat_id):
    """Kullanıcı bilgilerini getir"""
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        
        cur.execute('SELECT * FROM bot_kullanicilar WHERE chat_id = %s', (chat_id,))
        kullanici = cur.fetchone()
        return kullanici
        
    except Exception as e:
        print(f"❌ Kullanıcı bilgisi hatası: {e}")
        return None
    finally:
        if conn:
            connection_pool.putconn(conn)

def bildirim_gecmisi_kaydet(bildirim_turu, hedef_turu, hedef_departman, gonderilen, basarili, basarisiz, admin_chat_id):
    """Bildirim geçmişini kaydet"""
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO bildirim_gecmisi 
            (bildirim_turu, hedef_turu, hedef_departman, gonderilen_kullanici_sayisi, 
             basarili_gonderim, basarisiz_gonderim, admin_chat_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (bildirim_turu, hedef_turu, hedef_departman, gonderilen, basarili, basarisiz, admin_chat_id))
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Bildirim geçmişi kaydetme hatası: {e}")
    finally:
        if conn:
            connection_pool.putconn(conn)

# Başlangıç - Kullanıcı kaydı
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if kullanici_var_mi(chat_id):
        # Kayıtlı kullanıcı ana menü
        keyboard = [
            [InlineKeyboardButton("📊 Bilgilerim", callback_data="profil")],
            [InlineKeyboardButton("ℹ️ Yardım", callback_data="yardim")]
        ]
        
        # Admin ise admin menüsü ekle
        if chat_id in ADMIN_USERS:
            keyboard.append([InlineKeyboardButton("👨‍💼 Admin Panel", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"👋 Hoş geldiniz! İSG Güvenlik Asistanınız hazır.\n📅 {tarih_saat_formatla()}",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "👋 **İSG Güvenlik Asistanı Bot'a hoş geldiniz!**\n\n"
            "Lütfen **ad soyad** bilginizi giriniz:",
            parse_mode='Markdown'
        )
        return AD_SOYAD

# Kullanıcı bilgilerini toplama
async def ad_soyad_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ad_soyad"] = update.message.text
    await update.message.reply_text("📧 E-posta adresinizi giriniz:")
    return MAIL

async def mail_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mail"] = update.message.text
    await update.message.reply_text("🏢 Hangi departmanda çalışıyorsunuz?")
    return DEPARTMAN

async def departman_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["departman"] = update.message.text
    chat_id = update.effective_chat.id
    
    # Kullanıcıyı kaydet
    if kullanici_kaydet(
        chat_id,
        context.user_data["ad_soyad"],
        context.user_data["mail"],
        context.user_data["departman"]
    ):
        # Ana menü
        keyboard = [
            [InlineKeyboardButton("📊 Bilgilerim", callback_data="profil")],
            [InlineKeyboardButton("ℹ️ Yardım", callback_data="yardim")]
        ]
        
        if chat_id in ADMIN_USERS:
            keyboard.append([InlineKeyboardButton("👨‍💼 Admin Panel", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "✅ **Kaydınız başarıyla tamamlandı!**\n\n"
            f"**Ad Soyad:** {context.user_data['ad_soyad']}\n"
            f"**E-posta:** {context.user_data['mail']}\n"
            f"**Departman:** {context.user_data['departman']}\n"
            f"**Chat ID:** {chat_id}\n"
            f"**Kayıt Tarihi:** {tarih_saat_formatla()}\n\n"
            "Artık güvenlik bildirimleri alacaksınız.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ Kayıt sırasında bir hata oluştu. Lütfen tekrar deneyin."
        )
    
    return ConversationHandler.END

# Admin fonksiyonları
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_chat.id not in ADMIN_USERS:
        await query.edit_message_text("❌ Admin yetkisine sahip değilsiniz.")
        return
    
    keyboard = [
        [InlineKeyboardButton("👷 Baret Uyarısı", callback_data="bildirim_baret")],
        [InlineKeyboardButton("🧤 Eldiven Uyarısı", callback_data="bildirim_eldiven")],
        [InlineKeyboardButton("👓 Gözlük Uyarısı", callback_data="bildirim_gozluk")],
        [InlineKeyboardButton("🦺 Yelek Uyarısı", callback_data="bildirim_yelek")],
        [InlineKeyboardButton("📢 Tüm Kullanıcılara", callback_data="herkese_bildirim")],
        [InlineKeyboardButton("🏢 Departmana Özel", callback_data="departman_bildirim")],
        [InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data="kullanici_listesi")],
        [InlineKeyboardButton("📊 İstatistikler", callback_data="istatistikler")],
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="ana_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👨‍💼 **Admin Panel**\n📅 {tarih_saat_formatla()}\n\nHangi işlemi yapmak istersiniz?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Güvenlik bildirimleri
async def guvenlik_bildirimi_gonder(context, bildirim_turu, hedef="tumu", admin_chat_id=None):
    """Güvenlik bildirimi gönder"""
    
    tarih_saat = tarih_saat_formatla()
    
    bildirim_mesajlari = {
        "baret": f"👷 **GÜVENLİK UYARISI!**\n\n🚨 Lütfen baretinizi takınız!\n\nİş güvenliğiniz için baret kullanımı zorunludur.\n\n📅 {tarih_saat}",
        "eldiven": f"🧤 **GÜVENLİK UYARISI!**\n\n🚨 Lütfen eldivenlerinizi takınız!\n\nEl güvenliğiniz için eldiven kullanımı zorunludur.\n\n📅 {tarih_saat}",
        "gozluk": f"👓 **GÜVENLİK UYARISI!**\n\n🚨 Lütfen koruyucu gözlüğünüzü takınız!\n\nGöz güvenliğiniz için koruyucu gözlük kullanımı zorunludur.\n\n📅 {tarih_saat}",
        "yelek": f"🦺 **GÜVENLİK UYARISI!**\n\n🚨 Lütfen güvenlik yeleğinizi giyin!\n\nGörünürlüğünüz için güvenlik yeleği kullanımı zorunludur.\n\n📅 {tarih_saat}",
        "genel": f"⚠️ **GÜVENLİK BİLDİRİMİ**\n\nGenel güvenlik uyarısı!\n\n📅 {tarih_saat}"
    }
    
    mesaj = bildirim_mesajlari.get(bildirim_turu, f"⚠️ Güvenlik uyarısı!\n\n📅 {tarih_saat}")
    
    if hedef == "tumu":
        kullanicilar = tum_kullanicilari_getir()
        hedef_turu = "tumu"
        hedef_departman = None
    else:
        kullanicilar = departman_kullanicilari_getir(hedef)
        hedef_turu = "departman"
        hedef_departman = hedef
    
    basarili = 0
    basarisiz = 0
    gonderilen = len(kullanicilar)
    
    for kullanici in kullanicilar:
        try:
            await context.bot.send_message(
                chat_id=kullanici[0],
                text=mesaj,
                parse_mode='Markdown'
            )
            basarili += 1
            await asyncio.sleep(0.1)  # Rate limiting için
        except Exception as e:
            print(f"❌ Mesaj gönderme hatası (Chat ID: {kullanici[0]}): {e}")
            basarisiz += 1
    
    # Bildirim geçmişini kaydet
    if admin_chat_id:
        bildirim_gecmisi_kaydet(
            bildirim_turu, hedef_turu, hedef_departman, 
            gonderilen, basarili, basarisiz, admin_chat_id
        )
    
    return basarili, basarisiz, gonderilen

# Bildirim callback'leri
async def bildirim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    bildirim_turu = query.data.replace("bildirim_", "")
    admin_chat_id = update.effective_chat.id
    
   # Bildirimi gönder
    basarili, basarisiz, gonderilen = await guvenlik_bildirimi_gonder(
        context, bildirim_turu, "tumu", admin_chat_id
    )
    
    oran = (basarili / gonderilen * 100) if gonderilen > 0 else 0
    await query.edit_message_text(
        f"✅ **{bildirim_turu.title()} Bildirimi Gönderildi**\n\n"
        f"📊 **İstatistikler:**\n"
        f"• Hedeflenen: {gonderilen}\n"
        f"• Başarılı: {basarili}\n"
        f"• Başarısız: {basarisiz}\n"
        f"• Başarı Oranı: %{(basarili/gonderilen*100):.1f if gonderilen > 0 else 0}\n\n"
        f"📅 {tarih_saat_formatla()}",
        parse_mode='Markdown'
    )


# Kullanıcı listesi göster
async def kullanici_listesi_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    kullanicilar = tum_kullanicilari_getir()
    
    if not kullanicilar:
        await query.edit_message_text("📋 Henüz kayıtlı kullanıcı bulunmamaktadır.")
        return
    
    liste_metni = f"👥 **Kayıtlı Kullanıcılar ({len(kullanicilar)}):**\n\n"
    
    # Departmanlara göre grupla
    departmanlar = {}
    for kullanici in kullanicilar:
        dept = kullanici[2]
        if dept not in departmanlar:
            departmanlar[dept] = []
        departmanlar[dept].append(kullanici)
    
    for dept, users in departmanlar.items():
        liste_metni += f"🏢 **{dept}** ({len(users)} kişi):\n"
        for user in users[:10]:  # Her departmandan max 10 kişi göster
            liste_metni += f"   • {user[1]}\n"
        if len(users) > 10:
            liste_metni += f"   ... ve {len(users) - 10} kişi daha\n"
        liste_metni += "\n"
    
    liste_metni += f"📅 {tarih_saat_formatla()}"
    
    keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        liste_metni,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# İstatistikler göster
async def istatistikler_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        
        # Toplam kullanıcı sayısı
        cur.execute('SELECT COUNT(*) FROM bot_kullanicilar WHERE aktif = TRUE')
        toplam_kullanici = cur.fetchone()[0]
        
        # Departman dağılımı
        cur.execute('SELECT departman, COUNT(*) FROM bot_kullanicilar WHERE aktif = TRUE GROUP BY departman')
        departman_dagilimi = cur.fetchall()
        
        # Son 7 günde gönderilen bildirimler
        cur.execute('''
            SELECT bildirim_turu, COUNT(*), SUM(basarili_gonderim), SUM(basarisiz_gonderim)
            FROM bildirim_gecmisi 
            WHERE gonderim_tarihi >= NOW() - INTERVAL '7 days'
            GROUP BY bildirim_turu
        ''')
        bildirim_istatistikleri = cur.fetchall()
        
        istatistik_metni = f"📊 **Sistem İstatistikleri**\n\n"
        istatistik_metni += f"👥 **Toplam Kullanıcı:** {toplam_kullanici}\n\n"
        
        istatistik_metni += "🏢 **Departman Dağılımı:**\n"
        for dept in departman_dagilimi:
            istatistik_metni += f"   • {dept[0]}: {dept[1]} kişi\n"
        
        if bildirim_istatistikleri:
            istatistik_metni += "\n📢 **Son 7 Gün Bildirimler:**\n"
            for stat in bildirim_istatistikleri:
                istatistik_metni += f"   • {stat[0]}: {stat[1]} bildirim, {stat[2]} başarılı\n"
        
        istatistik_metni += f"\n📅 {tarih_saat_formatla()}"
        
    except Exception as e:
        istatistik_metni = f"❌ İstatistik verisi alınamadı: {e}"
    finally:
        if conn:
            connection_pool.putconn(conn)
    
    keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        istatistik_metni,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Profil göster
async def profil_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    kullanici = kullanici_bilgisi_getir(chat_id)
    
    if kullanici:
        kayit_tarihi = kullanici[4].strftime("%d.%m.%Y %H:%M") if kullanici[4] else "Bilinmiyor"
        profil_metni = (
            f"👤 **Profil Bilgileriniz**\n\n"
            f"**Ad Soyad:** {kullanici[1]}\n"
            f"**E-posta:** {kullanici[2]}\n"
            f"**Departman:** {kullanici[3]}\n"
            f"**Chat ID:** {kullanici[0]}\n"
            f"**Kayıt Tarihi:** {kayit_tarihi}\n"
            f"**Durum:** {'✅ Aktif' if kullanici[5] else '❌ Pasif'}\n\n"
            f"📅 {tarih_saat_formatla()}"
        )
    else:
        profil_metni = "❌ Profil bilgileriniz bulunamadı."
    
    keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data="ana_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        profil_metni,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Yardım
async def yardim_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    yardim_metni = (
        "ℹ️ **İSG Güvenlik Asistanı Yardım**\n\n"
        "Bu bot ile:\n"
        "• Anlık güvenlik bildirimlerini alabilirsiniz\n"
        "• Profil bilgilerinizi görüntüleyebilirsiniz\n"
        "• Güvenlik uyarıları tarih/saat bilgisiyle gelir\n\n"
        "**Komutlar:**\n"
        "/start - Botu başlat\n"
        "/admin - Admin panel (sadece adminler)\n\n"
        "**Güvenlik Ekipmanları:**\n"
        "👷 Baret\n"
        "🧤 Eldiven\n"
        "👓 Koruyucu Gözlük\n"
        "🦺 Güvenlik Yeleği\n\n"
        "**Özellikler:**\n"
        "• PostgreSQL veritabanı\n"
        "• Departman bazlı bildirimler\n"
        "• Bildirim geçmişi takibi\n"
        "• Detaylı istatistikler\n\n"
        f"📅 {tarih_saat_formatla()}\n\n"
        "Sorularınız için yönetiminizle iletişime geçin."
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data="ana_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        yardim_metni,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Ana menüye dön
async def ana_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("📊 Bilgilerim", callback_data="profil")],
        [InlineKeyboardButton("ℹ️ Yardım", callback_data="yardim")]
    ]
    
    if chat_id in ADMIN_USERS:
        keyboard.append([InlineKeyboardButton("👨‍💼 Admin Panel", callback_data="admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🏠 **Ana Menü**\n📅 {tarih_saat_formatla()}\n\nNe yapmak istersiniz?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Callback handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.data == "admin":
        await admin_panel(update, context)
    elif query.data.startswith("bildirim_"):
        await bildirim_callback(update, context)
    elif query.data == "kullanici_listesi":
        await kullanici_listesi_goster(update, context)
    elif query.data == "istatistikler":
        await istatistikler_goster(update, context)
    elif query.data == "profil":
        await profil_goster(update, context)
    elif query.data == "yardim":
        await yardim_goster(update, context)
    elif query.data == "ana_menu":
        await ana_menu(update, context)

# İptal
async def iptal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Kayıt işlemi iptal edildi.")
    return ConversationHandler.END

# Admin komut fonksiyonu
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_USERS:
        await update.message.reply_text("❌ Admin yetkisine sahip değilsiniz.")
        return
    
    # Query objesi olmadığı için update.callback_query yerine fake query oluştur
    class FakeQuery:
        def __init__(self):
            self.data = "admin"
        async def answer(self):
            pass
        async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    
    fake_update = type('obj', (object,), {
        'callback_query': FakeQuery(),
        'effective_chat': update.effective_chat
    })
    
    await admin_panel(fake_update, context)

def main():
    """Ana fonksiyon"""
    # Veritabanı bağlantısını kur
    veritabani_baglan()
    tabloyu_olustur()
    # Telegram botu başlat
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AD_SOYAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_soyad_al)],
            MAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, mail_al)],
            DEPARTMAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, departman_al)],
        },
        fallbacks=[CommandHandler("iptal", iptal)],
    )

    # Komut ve callback handler'ları ekle
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot çalışıyor... Telegram'dan /start yazarak test edebilirsin.")
    application.run_polling()

# BU SATIRI EKLE!
if __name__ == "__main__":
    main()
