import os
import pandas as pd
from openpyxl import Workbook, load_workbook
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from fastapi import FastAPI
import uvicorn
import threading

TOKEN = "TOKEN_BOT_KHOD_RO_INJA_VARD_KONI"
ADMIN_CHAT_ID = YOUR_ADMIN_CHAT_ID_NUMERIC

app_fastapi = FastAPI()

@app_fastapi.get("/")
def home():
    return {"status": "DentalBox Bot is running perfectly!"}

def run_fastapi():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app_fastapi, host="0.0.0.0", port=port)

# توابع فایل اکسل برای ذخیره آرا
EXCEL_FILE = "DentalBox_Poll_Results.xlsx"

def init_excel():
    if not os.path.exists(EXCEL_FILE):
        wb = Workbook()
        ws = wb.active
        ws.title = "Poll Results"
        ws.append(["User ID", "Username", "First Name", "Selected Option", "Timestamp"])
        wb.save(EXCEL_FILE)

def save_vote(user_id, username, first_name, option):
    init_excel()
    wb = load_workbook(EXCEL_FILE)
    ws = wb.active
    ws.append([user_id, str(username), str(first_name), str(option), str(pd.Timestamp.now())])
    wb.save(EXCEL_FILE)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات نظرسنجی دنتال‌باکس آماده است. برای شروع نظرسنجی از دستور /newpoll استفاده کنید.")

async def new_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("شما اجازه دسترسی به این دستور را ندارید.")
        return

    keyboard = [
        [InlineKeyboardButton("Bisco All-Bond Universal", callback_data="Bisco")],
        [InlineKeyboardButton("Saremco", callback_data="Saremco")],
        [InlineKeyboardButton("3M Single Bond 2", callback_data="3M")],
        [InlineKeyboardButton("Kuraray Clearfil SE", callback_data="Kuraray")],
        [InlineKeyboardButton("Tokuyama Bond Force", callback_data="Tokuyama")],
        [InlineKeyboardButton("Master-Dent", callback_data="Master-Dent")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🦷 **نظرسنجی تخصصی دنتال‌باکس**\n\nکدام باندینگ بیشترین رضایت را در مطب شما داشته است؟ (رای شما کاملاً محرمانه است):",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    selected_option = query.data

    # ذخیره در اکسل
    save_vote(user.id, user.username, user.first_name, selected_option)

    # پیام پاپ‌آپ تشکر برای دکتر
    await query.answer("✅ رای شما با موفقیت ثبت شد. ممنون از مشارکت شما!", show_alert=True)

    # گزارش آنی به پی‌وی ادمین
    try:
        admin_msg = (
            f"📥 **رای جدید دریافت شد!**\n\n"
            f"👤 نام: {user.first_name or ''} (استاندارد: @{user.username or 'ندارد'})\n"
            f"🆔 آیدی کاربر: `{user.id}`\n"
            f"🎯 گزینه انتخابی: **{selected_option}**"
        )
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Error sending admin notification: {e}")

def main():
    init_excel()
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newpoll", new_poll))
    application.add_handler(CallbackQueryHandler(button_handler))

    # اجرای سرور فست‌آپی در پس‌زمینه برای رندر
    t = threading.Thread(target=run_fastapi)
    t.start()

    print("DentalBox Bot started successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
