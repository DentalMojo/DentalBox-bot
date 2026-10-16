import os
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# تنظیمات لاگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# اطلاعات اصلی
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = 8707572497
CHANNEL_ID = -1004416175631

# مراحل ساخت نظرسنجی
GET_QUESTION, GET_OPTIONS = range(2)

# متغیر موقت برای ذخیره داده‌های ساخت نظرسنجی
poll_creation_data = {}

# ----------------- وب‌سرور سبک برای Render -----------------
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"DentalBox Survey Bot is running perfectly!")

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    logger.info(f"Server started on port {port}")
    server.serve_forever()

# ----------------- دستور /start ادمین -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ شما به پنل ادمین دنتال‌باکس دسترسی ندارید.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("➕ ایجاد و ارسال نظرسنجی به کانال", callback_data="btn_create_poll")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 سلام مدیر محترم دنتال‌باکس!\n\n"
        "به پنل هوشمند مدیریت نظرسنجی مطب‌ها خوش آمدید.\n"
        "برای طراحی و ارسال نظرسنجی روی دکمه زیر کلیک کنید:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

# ----------------- شروع ساخت نظرسنجی -----------------
async def start_create_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "📝 **مرحله ۱:** لطفاً متن سؤال نظرسنجی را ارسال کنید:\n\n"
        "(مثال: همکاران گرامی، اولویت شما در خرید کدام برند فایل اندو است؟)\n\n"
        "❌ برای لغو در هر مرحله /cancel را ارسال کنید."
    )
    return GET_QUESTION

# دریافت متن سؤال
async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_creation_data["question"] = update.message.text
    
    await update.message.reply_text(
        "✅ سؤال ثبت شد.\n\n"
        "🔘 **مرحله ۲:** حالا گزینه‌ها را بفرستید.\n"
        "نکته: گزینه‌ها را در پیام‌های جداگانه یا با علامت ویرگول (،) از هم جدا کنید:\n\n"
        "مثال:\n"
        "پرونکس اقتصادی\n"
        "پروفا استاندارد\n"
        "جوتا پریمیوم"
    )
    return GET_OPTIONS

# دریافت گزینه‌ها و ارسال نظرسنجی به کانال
async def receive_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text
    
    if "\n" in raw_text:
        options = [opt.strip() for opt in raw_text.split("\n") if opt.strip()]
    elif "،" in raw_text:
        options = [opt.strip() for opt in raw_text.split("،") if opt.strip()]
    elif "," in raw_text:
        options = [opt.strip() for opt in raw_text.split(",") if opt.strip()]
    else:
        options = [raw_text.strip()]

    if len(options) < 2:
        await update.message.reply_text("⚠️ نظرسنجی باید حداقل دارای ۲ گزینه باشد. لطفاً دوباره گزینه‌ها را ارسال کنید:")
        return GET_OPTIONS

    question = poll_creation_data.get("question", "نظرسنجی دنتال‌باکس")
    
    # ساخت دکمه‌های شیشه‌ای نظرسنجی
    keyboard = []
    for idx, opt in enumerate(options):
        # ذخیره متن گزینه در context یا دیتا
        keyboard.append([InlineKeyboardButton(f"▫️ {opt}", callback_data=f"vote_{idx}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # متن نهایی پیام کانال
    channel_post_text = (
        f"📊 **نظرسنجی تأمین دنتال‌باکس**\n\n"
        f"❓ **{question}**\n\n"
        f"لطفاً با لمس گزینه موردنظر، در بهبود سبد توزیع مشارکت کنید 👇"
    )

    try:
        sent_msg = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=channel_post_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        # ذخیره متن گزینه‌ها در bot_data برای گزارش‌گیری
        context.bot_data[f"poll_{sent_msg.message_id}"] = {
            "question": question,
            "options": options
        }

        await update.message.reply_text(
            f"🎉 **نظرسنجی با موفقیت در کانال منتشر شد!**\n\n"
            f"پیام شماره {sent_msg.message_id} به کانال خصوصی ارسال گردید."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال به کانال:\n`{str(e)}`")

    return ConversationHandler.END

# لغو عملیات
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات ساخت نظرسنجی لغو شد.")
    return ConversationHandler.END

# ----------------- هندلر ثبت رأی مشتریان -----------------
async def handle_votes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("vote_"):
        idx = int(data.split("_")[1])
        user = query.from_user
        
        # استخراج نام و جزئیات گزینه
        msg_id = query.message.message_id
        poll_info = context.bot_data.get(f"poll_{msg_id}", {})
        options = poll_info.get("options", [])
        
        option_title = options[idx] if idx < len(options) else f"گزینه {idx + 1}"
        question_title = poll_info.get("question", "نظرسنجی دنتال‌باکس")

        # ۱. پیام تأیید و تشکر برای خود مشتری (روی صفحه به صورت پنجره کوتاه)
        await query.answer("✅ نظر شما با موفقیت ثبت شد. از همراهی شما با دنتال‌باکس سپاسگزاریم! 🦷", show_alert=True)

        # ۲. ارسال فوری گزارش به پیوی ادمین
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        username_str = f"@{user.username}" if user.username else "ندارد"
        
        admin_alert = (
            f"🔔 **ثبت رأی جدید در کانال دنتال‌باکس!**\n\n"
            f"👤 **مشتری / همکار:** {user_name}\n"
            f"🔗 **یوزرنیم:** {username_str}\n"
            f"🆔 **شناسه عددی:** `{user.id}`\n\n"
            f"❓ **سؤال:** {question_title}\n"
            f"🎯 **گزینه انتخابی:** {option_title}"
        )
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_alert,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error alerting admin: {e}")

# ----------------- اجرای اصلی -----------------
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        return

    # اجرای ترد وب‌سرور برای زنده ماندن رندر
    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # مدیریت گفت‌وگوی گام‌به‌گام ساخت نظرسنجی
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create_poll, pattern="^btn_create_poll$")],
        states={
            GET_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question)],
            GET_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_options)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_votes, pattern="^vote_"))

    logger.info("Bot polling is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
