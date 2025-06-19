from telegram.ext import ApplicationBuilder, CommandHandler
import os

# Token buraya manuel yazılmalı çünkü .env kullanmıyoruz
BOT_TOKEN = "8169151245:AAEED2Z40XIhWbxydUaeS2yxh36pEoc72Ds"

async def get_id(update, context):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"📌 Chat ID'iniz: {chat_id}")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("getid", get_id))
app.run_polling()


