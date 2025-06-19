
import psycopg2

def connect_db():
    return psycopg2.connect(
        host="localhost",
        database="is_guvenligi",
        user="postgres",
        password="123456"
    )

def delete_record(table_name, record_id):
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {table_name} WHERE id = %s", (record_id,))
        conn.commit()
        print(f" {table_name} tablosundan ID={record_id} başarıyla silindi.")
    except Exception as e:
        print(f"Hata ({table_name} silme):", e)
    finally:
        cur.close()
        conn.close()

def delete_employee_with_dependencies(employee_id):
    try:
        conn = connect_db()
        cur = conn.cursor()

        # Bağımlı kayıtları sil
        cur.execute("DELETE FROM ppe_violations WHERE employee_id = %s", (employee_id,))
        cur.execute("DELETE FROM user_logins WHERE employee_id = %s", (employee_id,))
        cur.execute("DELETE FROM incidents WHERE employee_id = %s", (employee_id,))

        # Ana çalışan kaydını sil
        cur.execute("DELETE FROM employees WHERE id = %s", (employee_id,))

        conn.commit()
        print(f"Çalışan ve ilişkili kayıtlar (ID={employee_id}) başarıyla silindi.")
    except Exception as e:
        print("Hata (employees silme):", e)
    finally:
        cur.close()
        conn.close()

def menu():
    print("""
======= VERİ SİLME MENÜSÜ =======

1. Çalışan (employees - ilişkili kayıtlarla birlikte)
2. Kamera (cameras)
3. Ekipman İhlali (ppe_violations)
4. Olay (incidents)
5. Rol (roles)
6. Güvenlik Kuralı (safety_rules)
7. Giriş Kaydı (user_logins)
0. Çıkış
""")
    return input("Silmek istediğiniz tabloyu seçin (0-7): ")

def get_id():
    return int(input("Silinecek kaydın ID numarasını girin: "))

if __name__ == "__main__":
    while True:
        choice = menu()
        if choice == "1":
            delete_employee_with_dependencies(get_id())
        elif choice == "2":
            delete_record("cameras", get_id())
        elif choice == "3":
            delete_record("ppe_violations", get_id())
        elif choice == "4":
            delete_record("incidents", get_id())
        elif choice == "5":
            delete_record("roles", get_id())
        elif choice == "6":
            delete_record("safety_rules", get_id())
        elif choice == "7":
            delete_record("user_logins", get_id())
        elif choice == "0":
            print("Çıkılıyor...")
            break
        else:
            print("Geçersiz seçim! Lütfen tekrar deneyin.")
