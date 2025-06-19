import psycopg2
from dotenv import load_dotenv
import os

# .env dosyasından DB bilgilerini oku
load_dotenv()

def connect_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )

def get_latest_violations():
    """
    En son PPE ihlallerini alır. Örneğin, son 1 dakika içindekileri.
    """
    conn = connect_db()
    cur = conn.cursor()
    
    query = """
    SELECT pv.id, e.name, e.chat_id, pv.violation_type, pv.timestamp
    FROM ppe_violations pv
    JOIN employees e ON pv.employee_id = e.id
    WHERE pv.notified IS FALSE
    ORDER BY pv.timestamp DESC;
    """
    
    cur.execute(query)
    results = cur.fetchall()

    # Notified alanı True yapılır (tekrar gönderilmesin diye)
    update_query = "UPDATE ppe_violations SET notified = TRUE WHERE id = ANY(%s);"
    ids = [row[0] for row in results]
    if ids:
        cur.execute(update_query, (ids,))
    
    conn.commit()
    cur.close()
    conn.close()

    return results
