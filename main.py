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

async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_creation_data["question"] = update.message.text
    
    await update.message.reply_text(
        "✅ سؤال ثبت شد.\n\n"
        "🔘 **مرحله ۲:** حالا گزینه‌ها را بفرستید (با اینتر یا ویرگول جدا کنید):"
    )
    return GET_OPTIONS

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
    
    # ساخت دکمه‌های اولیه (بدون رای)
    keyboard = []
    for idx, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"▫️ {opt} (0 رای - 0%)", callback_data=f"vote_{idx}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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
        
        # ذخیره اطلاعات نظرسنجی و آرا در bot_data
        context.bot_data[f"poll_{sent_msg.message_id}"] = {
            "question": question,
            "options": options,
            "votes": {idx: 0 for idx in range(len(options))}, # تعداد رای هر گزینه
            "user_votes": {} # ثبت اینکه چه کاربری به کدام گزینه رای داده (جلوگیری از رای تکراری)
        }

        await update.message.reply_text(
            f"🎉 **نظرسنجی با موفقیت در کانال منتشر شد!**\n\n"
            f"پیام شماره {sent_msg.message_id} به کانال خصوصی ارسال گردید."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال به کانال:\n`{str(e)}`")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات ساخت نظرسنجی لغو شد.")
    return ConversationHandler.END

# ----------------- هندلر ثبت رأی و آپدیت زنده دکمه‌ها -----------------
async def handle_votes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("vote_"):
        idx = int(data.split("_")[1])
        user = query.from_user
        msg_id = query.message.message_id
        poll_key = f"poll_{msg_id}"
        
        poll_info = context.bot_data.get(poll_key)
        if not poll_info:
            await query.answer("⚠️ اطلاعات این نظرسنجی منقضی شده است.", show_alert=True)
            return

        user_votes = poll_info["user_votes"]
        votes = poll_info["votes"]
        options = poll_info["options"]

        # بررسی رای قبلی کاربر (جلوگیری از تغییر یا ثبت چندباره یا ثبت به عنوان رای جدید)
        user_id_str = str(user.id)
        if user_id_str in user_votes:
            old_idx = user_votes[user_id_str]
            if old_idx == idx:
                await query.answer("شما قبلاً به همین گزینه رای داده‌اید! 🙏", show_alert=True)
                return
            else:
                # اگر نظرش را عوض کرد
                votes[old_idx] = max(0, votes[old_idx] - 1)
        
        # ثبت یا به‌روزرسانی رای جدید
        user_votes[user_id_str] = idx
        votes[idx] += 1

        # محاسبه مجموع آرا و درصدها
        total_votes = sum(votes.values())

        # ساخت مجدد دکمه‌ها با آمار جدید
        keyboard = []
        for i, opt in enumerate(options):
            count = votes[i]
            percent = int((count / total_votes) * 100) if total_votes > 0 else 0
            
            # اگر این گزینه رای کاربر فعلی است، علامت تیک بزنیم
            prefix = "✅ " if user_votes.get(user_id_str) == i else "▫️ "
            btn_text = f"{prefix}{opt} ({count} رای - {percent}%)"
            
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"vote_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        # آپدیت پیام کانال با دکمه‌های جدید دارای آمار
        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error updating inline keyboard: {e}")

        # پیام تایید برای کاربر
        await query.answer("✅ رای شما با موفقیت ثبت شد و آمار کانال به‌روز گردید! 📊", show_alert=True)

        # ارسال گزارش فوری به پیوی ادمین
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        username_str = f"@{user.username}" if user.username else "ندارد"
        option_title = options[idx]
        
        admin_alert = (
            f"🔔 **ثبت رأی جدید در کانال دنتال‌باکس!**\n\n"
            f"👤 **همکار:** {user_name} ({username_str})\n"
            f"🆔 **آیدی:** `{user.id}`\n\n"
            f"❓ **سؤال:** {poll_info['question']}\n"
            f"🎯 **انتخاب:** {option_title}\n"
            f"📈 **مجموع کل آرای این نظرسنجی:** {total_votes} رای"
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

    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

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
