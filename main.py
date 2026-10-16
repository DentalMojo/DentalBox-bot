import os
import json
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = 8707572497
CHANNEL_ID = -1004416175631

GET_QUESTION, GET_OPTIONS = range(2)
new_poll_temp = {}
DB_FILE = "polls_data.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ساخت کیبورد با درصد و تعداد آرا
def build_poll_keyboard(poll_id, poll_info):
    options = poll_info["options"]
    votes = poll_info["votes"]
    total_votes = len(votes)

    keyboard = []
    for idx, opt_text in enumerate(options):
        opt_count = sum(1 for v in votes.values() if v == idx)
        percent = int((opt_count / total_votes) * 100) if total_votes > 0 else 0
        btn_label = f"[{percent}% - {opt_count} رأی] {opt_text}"
        callback_data = f"vote_{poll_id}_{idx}"
        keyboard.append([InlineKeyboardButton(btn_label, callback_data=callback_data)])
    
    return InlineKeyboardMarkup(keyboard)

# سرور وب برای پایداری در رندر
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ دسترسی به این پنل فقط برای مدیر مجاز است.")
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 سلام مدیر محترم دنتال‌باکس!\n\n"
        "برای ساخت نظرسنجی جدید و اختصاصی، دستور زیر را ارسال کنید:\n"
        "/newpoll"
    )
    return ConversationHandler.END

async def new_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_CHAT_ID:
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 **مرحله ۱:** لطفاً متن سؤال نظرسنجی را ارسال کنید:\n\n"
        "❌ برای لغو: /cancel"
    )
    return GET_QUESTION

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_poll_temp["question"] = update.message.text
    await update.message.reply_text(
        "🔘 **مرحله ۲:** حالا گزینه‌ها را بفرستید.\n\n"
        "هر گزینه را در یک خط جداگانه قرار دهید:\n"
        "مثال:\n"
        "باندینگ آل‌باند بیسکو\n"
        "باندینگ جی‌سی پرمیو\n"
        "باندینگ سینگل باند تری‌ام"
    )
    return GET_OPTIONS

async def get_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    options = [opt.strip() for opt in text.split("\n") if opt.strip()]

    if len(options) < 2:
        await update.message.reply_text("⚠️ نظرسنجی حداقل باید ۲ گزینه داشته باشد. دوباره بفرستید:")
        return GET_OPTIONS

    question = new_poll_temp.get("question", "نظرسنجی دنتال‌باکس")
    data = load_data()
    poll_id = str(len(data) + 1)

    poll_info = {
        "question": question,
        "options": options,
        "votes": {},       # user_id: option_index
        "voters": {}       # user_id: voter_details
    }

    reply_markup = build_poll_keyboard(poll_id, poll_info)
    msg_text = f"📊 **{question}**\n\nبرای ثبت رأی روی گزینه مورد نظر کلیک کنید:"

    try:
        sent_msg = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=msg_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        poll_info["channel_message_id"] = sent_msg.message_id
        data[poll_id] = poll_info
        save_data(data)

        await update.message.reply_text("🎉 **نظرسنجی با درصد و تعداد زنده به کانال ارسال شد!**")
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ خطا در ارسال به کانال:\n`{str(e)}`")

    return ConversationHandler.END

async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_id = str(user.id)
    data_str = query.data

    if not data_str.startswith("vote_"):
        return

    _, poll_id, opt_idx = data_str.split("_")
    opt_idx = int(opt_idx)

    polls = load_data()
    if poll_id not in polls:
        await query.answer("این نظرسنجی دیگر معتبر نیست.", show_alert=True)
        return

    poll = polls[poll_id]

    # اگر قبلاً رأی داده باشد
    if user_id in poll["votes"]:
        await query.answer("شما قبلاً رأی خود را در این نظرسنجی ثبت کرده‌اید!", show_alert=True)
        return

    # ثبت رأی
    selected_option = poll["options"][opt_idx]
    poll["votes"][user_id] = opt_idx
    voter_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    poll["voters"][user_id] = {
        "name": voter_name,
        "username": f"@{user.username}" if user.username else "ندارد",
        "choice": selected_option
    }
    save_data(polls)

    await query.answer(f"✅ رأی شما به «{selected_option}» با موفقیت ثبت شد.")

    # ۱. به‌روزرسانی درصدهای نمایش‌داده‌شده برای همه در کانال
    new_markup = build_poll_keyboard(poll_id, poll)
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=poll["channel_message_id"],
            reply_markup=new_markup
        )
    except Exception as e:
        logger.error(f"Could not update markup: {e}")

    # ۲. ارسال فوری گزارش رأی به پی‌وی ادمین
    admin_alert = (
        "🔔 **یک رأی جدید در نظرسنجی ثبت شد!**\n\n"
        f"📋 **سؤال:** {poll['question']}\n"
        f"👤 **رأی‌دهنده:** {voter_name}\n"
        f"🆔 **یوزرنیم:** {poll['voters'][user_id]['username']}\n"
        f"🔹 **گزینه انتخابی:** {selected_option}\n"
        f"📊 **مجموع آرا تا این لحظه:** {len(poll['votes'])} رأی"
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_alert,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Could not alert admin: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set.")
        return

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("newpoll", new_poll)],
        states={
            GET_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
            GET_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(handle_vote))

    logger.info("Bot starting with realtime percentage updates...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
