import os
from dotenv import load_dotenv

load_dotenv()
print("Şifre:", os.getenv("DB_PASS"))
