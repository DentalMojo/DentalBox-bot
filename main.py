import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from fastapi import FastAPI
import uvicorn
import asyncio
import threading

# تنظیمات لاگ
logging.basicConfig(level=logging.INFO)

# توکن و آیدی ادمین
BOT_TOKEN = "توکن_ربات_اینجا"  # توکن رباتت رو اینجا بذار
ADMIN_CHAT_ID = 8707572497

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "DentalBox Poll Bot is running live!"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! خوش آمدید. برای ایجاد نظرسنجی دستور /poll را ارسال کنید.")

async def send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⭐ عالی و باکیفیت", callback_data="vote_1")],
        [InlineKeyboardButton("👍 خوب و مناسب", callback_data="vote_2")],
        [InlineKeyboardButton("👎 نیاز به بهبود دارد", callback_data="vote_3")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📋 **نظرسنجی کیفیت کالاهای دنتال‌باکس**\n\nلطفاً نظر خود را ثبت کنید:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    vote_text = query.data
    user = query.from_user
    
    # ثبت رای کاربر (ارسال گزارش به ادمین)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"📥 رأی جدید ثبت شد!\nکاربر: {user.full_name} (@{user.username})\nگزینه: {vote_text}"
        )
    except Exception as e:
        print(f"Error sending to admin: {e}")

    await query.edit_message_text(text="✅ رأی شما با موفقیت ثبت شد. سپاس از همراهی شما با دنتال‌باکس 🙏")

def run_fastapi():
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

def main():
    # راه‌اندازی وب‌سرور برای زنده ماندن ربات در رندر
    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("poll", send_poll))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
