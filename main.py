import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = 8707572497

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! به دنتال‌باکس خوش آمدید.\nبرای ارسال نظرسنجی دستور /poll را بزنید.")

async def send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⭐ عالی و باکیفیت", callback_data="عالی")],
        [InlineKeyboardButton("👍 خوب و مناسب", callback_data="خوب")],
        [InlineKeyboardButton("👎 نیاز به بهبود دارد", callback_data="نیاز به بهبود")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📋 **نظرسنجی کیفیت کالاهای دنتال‌باکس**\n\nلطفاً سطح رضایت خود را انتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_option = query.data
    user = query.from_user
    username = f"@{user.username}" if user.username else "ندارد"
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"📥 **ثبت رأی جدید در دنتال‌باکس:**\n👤 کاربر: {user.full_name} ({username})\n📊 نظر: {selected_option}"
        )
    except Exception as e:
        print(f"Error sending to admin: {e}")

    await query.edit_message_text(text="✅ نظر شما با موفقیت ثبت شد.\nاز همراهی و اعتمادتان به دنتال‌باکس سپاسگزاریم 🙏")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("poll", send_poll))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is polling and ready...")
    application.run_polling()

if __name__ == "__main__":
    main()
