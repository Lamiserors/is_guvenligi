import psycopg2

try:
    
    connection = psycopg2.connect(
        host="localhost",
        database="is_guvenligi",   
        user="postgres",
        password="123456"          
    )

    print(" Bağlantı başarılı!")


    cursor = connection.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()
    print("PostgreSQL versiyonu:", version)

except Exception as e:
    print("Bağlantı hatası:", e)

finally:
    if connection:
        cursor.close()
        connection.close()
        print("Bağlantı kapatıldı.")
