import psycopg2
from datetime import datetime

def connect_db():
    return psycopg2.connect(
        host="localhost",
        database="is_guvenligi",
        user="postgres",
        password="123456"
    )

# Tablolara veri ekleme fonksiyonları
def insert_employee():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO employees (name, photo_path, ppe_required, role_id)
            VALUES (%s, %s, %s, %s)
        """, ("Ahmet Yılmaz", "/images/ahmet.jpg", ['baret', 'gözlük'], 1))
        conn.commit()
        print(" Çalışan eklendi.")
    except Exception as e:
        print("Hata (employees):", e)
    finally:
        cur.close()
        conn.close()

def insert_camera():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO cameras (name, ip_address, location, rule_id)
            VALUES (%s, %s, %s, %s)
        """, ("Kamera A", "192.168.1.101", "Depo Girişi", 1))
        conn.commit()
        print("Kamera eklendi.")
    except Exception as e:
        print(" Hata (cameras):", e)
    finally:
        cur.close()
        conn.close()

def insert_incident():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO incidents (employee_id, date, missing_ppe, status)
            VALUES (%s, %s, %s, %s)
        """, (1, datetime.now(), ['baret'], 'uyarıldı'))
        conn.commit()
        print("Olay kaydı eklendi.")
    except Exception as e:
        print(" Hata (incidents):", e)
    finally:
        cur.close()
        conn.close()

def insert_ppe_violation():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ppe_violations (employee_id, camera_id, missing_items, timestamp, alert_sent)
            VALUES (%s, %s, %s, %s, %s)
        """, (1, 1, ['eldiven'], datetime.now(), True))
        conn.commit()
        print(" PPE ihlali eklendi.")
    except Exception as e:
        print(" Hata (ppe_violations):", e)
    finally:
        cur.close()
        conn.close()

def insert_role():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO roles (name)
            VALUES (%s)
        """, ("İnşaat İşçisi",))
        conn.commit()
        print("Rol eklendi.")
    except Exception as e:
        print("Hata (roles):", e)
    finally:
        cur.close()
        conn.close()

def insert_safety_rule():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO safety_rules (zone_name, required_ppe)
            VALUES (%s, %s)
        """, ("İnşaat Alanı", ['baret', 'gözlük']))
        conn.commit()
        print(" Güvenlik kuralı eklendi.")
    except Exception as e:
        print(" Hata (safety_rules):", e)
    finally:
        cur.close()
        conn.close()

def insert_user_login():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_logins (employee_id, login_time, login_status)
            VALUES (%s, %s, %s)
        """, (1, datetime.now(), "başarılı"))
        conn.commit()
        print(" Giriş kaydı eklendi.")
    except Exception as e:
        print("Hata (user_logins):", e)
    finally:
        cur.close()
        conn.close()

# Ana menü
def menu():
    print("\n=== VERİ EKLEME MENÜSÜ ===")
    print("1. Çalışan Ekle")
    print("2. Kamera Ekle")
    print("3. Olay (Incident) Ekle")
    print("4. PPE İhlali Ekle")
    print("5. Rol Ekle")
    print("6. Güvenlik Kuralı Ekle")
    print("7. Kullanıcı Giriş Kaydı Ekle")
    print("0. Çıkış")

    secim = input("Bir seçim yapın: ")
    if secim == "1":
        insert_employee()
    elif secim == "2":
        insert_camera()
    elif secim == "3":
        insert_incident()
    elif secim == "4":
        insert_ppe_violation()
    elif secim == "5":
        insert_role()
    elif secim == "6":
        insert_safety_rule()
    elif secim == "7":
        insert_user_login()
    elif secim == "0":
        print("Çıkılıyor...")
        return
    else:
        print(" Geçersiz seçim")

    menu()  # menüyü tekrar göster

# Ana çalıştırma bloğu
if __name__ == "__main__":
    menu()
