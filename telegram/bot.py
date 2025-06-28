import os
import json
import logging
import aiohttp
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, CallbackContext, ConversationHandler
)
from telegram.constants import ParseMode

# --- Constants ---
API_URL = 'https://bestsmmprovider.com/api/v2'
API_KEY = '6531b4d73b0d5c6ade83e71ee1a0cb88'
BOT_TOKEN = '7755256026:AAEEoaJwOaP1gkff_yVWoW4VFFOWPZ4HKDk'
ADMIN_ID = 1108165567
USER_DB_FILE = "users_db.json"
MAINTENANCE_FILE = "maintenance_mode.flag"

if os.path.exists(USER_DB_FILE):
    with open(USER_DB_FILE, 'r') as f:
        users = json.load(f)
else:
    users = {}

application = ApplicationBuilder().token(BOT_TOKEN).build()
logging.basicConfig(level=logging.INFO)

def save_users():
    with open(USER_DB_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def get_user_level(user_id):
    return users.get(str(user_id), {}).get("level", "regular")

def is_banned(user_id):
    return users.get(str(user_id), {}).get("banned", False)

def is_maintenance():
    return os.path.exists(MAINTENANCE_FILE)

SERVICES = {
    "like": "1192",
    "view": "2235",
    "tiktok_view": "3099",
    "tiktok_like": "2736"
}

async def place_order_async(service_id, link, quantity):
    data = {
        "key": API_KEY,
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, data=data, timeout=10) as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}

ASK_LINK = range(1)
user_order_context = {}

def get_successful_orders_count(user_id):
    user = users.get(str(user_id), {})
    orders = user.get("orders_per_day", {})
    return sum(orders.values())

def get_service_keyboard(user_id=None):
    buttons = [
        [InlineKeyboardButton("🔺 طلب لايكات", callback_data="order_likes")],
        [InlineKeyboardButton("👁️ طلب مشاهدات", callback_data="order_views")],
        [InlineKeyboardButton("🎬 مشاهدات تيك توك", callback_data="order_tiktok_view")],
        [InlineKeyboardButton("❤️ لايكات تيك توك", callback_data="order_tiktok_like")],
        [InlineKeyboardButton("💸 خدمات مدفوعة", callback_data="paid_services")]
    ]
    if user_id:
        buttons.append([InlineKeyboardButton("🚀 Grodd الترقية إلى", callback_data="upgrade_grodd_progress")])
    buttons.append([InlineKeyboardButton("🆘 الدعم", callback_data="support")])
    return InlineKeyboardMarkup(buttons)

def can_order_today(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    user = users.get(user_id, {})
    orders = user.get("orders_per_day", {})
    return orders.get(today, 0) < 10

def register_order(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    user = users.setdefault(user_id, {})
    orders = user.setdefault("orders_per_day", {})
    orders[today] = orders.get(today, 0) + 1
    save_users()

SERVICE_QUANTITIES = {
    "like": {"regular": 100, "grodd": 200},
    "view": {"regular": 1000, "grodd": 2000},
    "tiktok_view": {"regular": 5000, "grodd": 10000},
    "tiktok_like": {"regular": 100, "grodd": 200},
}

# --- Start Command ---
async def start(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username

    if user_id not in users:
        users[user_id] = {
            "username": username,
            "level": "regular",
            "banned": False,
            "last_order": None
        }
    else:
        users[user_id]["username"] = username
    save_users()

    if is_banned(user_id):
        await update.message.reply_text("🚫 تم حظرك من استخدام هذا البوت.")
        return

    user_level = get_user_level(user_id)
    likes_per_hour = 1000 if user_level == "grodd" else 500
    views_per_hour = 2000 if user_level == "grodd" else 1000

    if user_level == "grodd":
        welcome_msg = (
            f"🎉 أهلاً بك أيها العضو الذهبي @{username} في Infinity Network!\n"
            f"🔥 لديك مزايا ضعف الكمية والدعم المميز.\n"
            f"❤️ لايكات كل ساعة: {likes_per_hour}\n"
            f"👁️ مشاهدات كل ساعة: {views_per_hour}"
        )
    else:
        welcome_msg = (
            f"أهلاً بك في بوت Infinity Network 💜\n"
            f"👤 المستخدم: @{username}\n"
            f"🔹 المستوى: {user_level}\n"
            f"❤️ لايكات كل 3 ساعات: {likes_per_hour}\n"
            f"👁️ مشاهدات كل 3 ساعات: {views_per_hour}\n"
            f"\n"
            f"🚀 يمكنك الترقية لمستوى Grodd الذهبي للحصول على ضعف الكمية!"
        )

    await update.message.reply_text(welcome_msg, parse_mode="Markdown")
    await update.message.reply_text(
        "إختر الخدمة اللي بغيتي:",
        reply_markup=get_service_keyboard(user_id)
    )

# --- Help Command ---
async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "🟣 **مساعدة Infinity Network**\n\n"
        "يمكنك استخدام هذا البوت لطلب لايكات أو مشاهدات لمنشورات وفيديوهات انستغرام وتيك توك مجاناً حسب مستواك.\n\n"
        "الأوامر:\n"
        "• `/start` - بدء البوت وعرض الخيارات\n"
        "• `/status` - معرفة مستواك ووقت الطلب القادم\n"
        "• `/points` - معرفة نقاطك وسجل الحركات\n"
        "• `/help` - عرض هذه الرسالة\n\n"
        "🔺 **طريقة الاستخدام:**\n"
        "1. اضغط على زر الخدمة (لايكات أو مشاهدات).\n"
        "2. أرسل رابط المنشور أو الفيديو.\n"
        "3. انتظر تنفيذ الطلب (يمكنك طلب خدمة كل 3 ساعات).\n\n"
        "🟢 **المستويات:**\n"
        "- المستخدم العادي: 500 لايك أو 1000 مشاهدة انستغرام، 100 لايك أو 5000 مشاهدة تيك توك كل ساعة\n"
        "- مستخدم Grodd: 1000 لايك أو 2000 مشاهدة انستغرام، 200 لايك أو 10000 مشاهدة تيك توك كل ساعة\n\n"
        "للاستفسار أو الترقية تواصل مع: @darraziprime"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- Service selection callback ---
async def service_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    if is_banned(user_id):
        await query.edit_message_text("🚫 تم حظرك من استخدام هذا البوت.")
        return ConversationHandler.END

    user_data = users.get(user_id, {})
    last_order_time_str = user_data.get("last_order")
    if last_order_time_str:
        last_order_time = datetime.strptime(last_order_time_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last_order_time < timedelta(hours=3):
            await query.edit_message_text("⏳ يجب الانتظار 3 ساعات بين كل طلب.")
            return ConversationHandler.END

    if query.data == "order_likes":
        user_order_context[user_id] = "like"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_services")]
        ])
        await query.edit_message_text(
            "🔗 أرسل رابط منشور الانستغرام الذي تريد زيادة اللايكات عليه:",
            reply_markup=kb
        )
        return ASK_LINK
    elif query.data == "order_views":
        user_order_context[user_id] = "view"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_services")]
        ])
        await query.edit_message_text(
            "🔗 أرسل رابط فيديو الانستغرام الذي تريد زيادة المشاهدات عليه:",
            reply_markup=kb
        )
        return ASK_LINK
    elif query.data == "order_tiktok_view":
        user_order_context[user_id] = "tiktok_view"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_services")]
        ])
        await query.edit_message_text(
            "🔗 أرسل رابط فيديو تيك توك الذي تريد زيادة المشاهدات عليه:",
            reply_markup=kb
        )
        return ASK_LINK
    elif query.data == "order_tiktok_like":
        user_order_context[user_id] = "tiktok_like"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_services")]
        ])
        await query.edit_message_text(
            "🔗 أرسل رابط فيديو تيك توك الذي تريد زيادة اللايكات عليه:",
            reply_markup=kb
        )
        return ASK_LINK
    elif query.data == "paid_services":
        await query.edit_message_text(
            "💸 <b>الخدمات المدفوعة قادمة قريباً!</b>\n\n"
            "ترقبوا عروضاً وخدمات مميزة قريباً جداً على Infinity Network.\n"
            "شكراً لثقتكم ودعمكم الدائم 💜",
            parse_mode="HTML",
            reply_markup=get_service_keyboard(user_id)
        )
        return ConversationHandler.END
    elif query.data == "support":
        await query.edit_message_text(
            "🆘 أرسل رسالتك أو استفسارك هنا وسيتم الرد عليك من الإدارة.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_services")]
            ])
        )
        context.user_data["support_mode"] = True
        return ASK_LINK
    elif query.data == "upgrade_grodd_progress":
        count = get_successful_orders_count(user_id)
        if count >= 100:
            msg = (
                f"🎉 لقد أكملت <b>{count}</b> من 100 طلب ناجح!\n\n"
                "يمكنك الآن الترقية مجاناً إلى مستوى Grodd.\n"
                "يرجى إرسال تذكرة دعم مع لقطة شاشة تثبت عدد الطلبات."
            )
        else:
            msg = (
                f"🚀 الترقية إلى Grodd مجاناً!\n\n"
                f"لقد أكملت <b>{count}</b> من 100 طلب ناجح.\n"
                f"عند إكمال 100 طلب، يمكنك الترقية مجاناً عبر إرسال تذكرة دعم مع لقطة شاشة."
            )
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=get_service_keyboard(user_id)
        )
        return ConversationHandler.END
    elif query.data == "back_to_services":
        await query.edit_message_text(
            "إختر الخدمة اللي بغيتي:",
            reply_markup=get_service_keyboard(user_id)
        )
        return ConversationHandler.END

    return ConversationHandler.END

# --- Receive Link Handler ---
async def receive_link(update: Update, context: CallbackContext):
    if is_maintenance():
        await update.message.reply_text(
            "🚧 **البوت حالياً في وضع الصيانة المؤقتة** 🚧\n\n"
            "نحن نقوم بتحديث وتحسين الخدمات حالياً.\n"
            "يرجى المحاولة لاحقاً، شكراً لتفهمك وصبرك 💜"
        )
        return ConversationHandler.END

    user_id = str(update.message.from_user.id)
    text = update.message.text.strip()

    # Handle support messages
    if context.user_data.get("support_mode"):
        await update.message.forward(chat_id=ADMIN_ID)
        await update.message.reply_text(
            "✅ تم إرسال رسالتك للدعم. سيتم الرد عليك من الإدارة.",
            reply_markup=get_service_keyboard(user_id)
        )
        context.user_data["support_mode"] = False
        return ConversationHandler.END

    # Handle service orders
    if user_id not in user_order_context:
        await update.message.reply_text("❌ يرجى اختيار الخدمة أولاً من القائمة.", reply_markup=get_service_keyboard(user_id))
        return ConversationHandler.END

    if not can_order_today(user_id):
        await update.message.reply_text("🚫 لقد تجاوزت الحد الأقصى للطلبات اليوم (10 طلبات). حاول غداً.", reply_markup=get_service_keyboard(user_id))
        return ConversationHandler.END

    service_type = user_order_context.pop(user_id)
    user_level = get_user_level(user_id)
    quantity = SERVICE_QUANTITIES.get(service_type, {}).get(user_level, 100)
    service_id = SERVICES[service_type]

    result = await place_order_async(service_id, text, quantity)
    if result.get("order"):
        users[user_id]["last_order"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if service_type == "like":
            users[user_id]["total_likes"] = users[user_id].get("total_likes", 0) + quantity
        elif service_type == "view":
            users[user_id]["total_views"] = users[user_id].get("total_views", 0) + quantity
        elif service_type == "tiktok_view":
            users[user_id]["total_tiktok_views"] = users[user_id].get("total_tiktok_views", 0) + quantity
        elif service_type == "tiktok_like":
            users[user_id]["total_tiktok_likes"] = users[user_id].get("total_tiktok_likes", 0) + quantity
        register_order(user_id)
        save_users()
        await update.message.reply_text(
            f"✅ تم إرسال طلبك بنجاح!\n\n🔗 الرابط: {text}\n🔢 العدد: {quantity}\n🆔 رقم الطلب: {result['order']}",
            reply_markup=get_service_keyboard(user_id)
        )
        if get_user_level(user_id) == "regular":
            upgrade_text = (
                "🚀 هل تريد الحصول على ضعف عدد اللايكات والمشاهدات مجاناً؟\n"
                "إنتقل الآن إلى مستوى Grodd الذهبي واستمتع بالمزايا الحصرية!"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 الترقية إلى Grodd", callback_data="upgrade_grodd_progress")]
            ])
            await update.message.reply_text(upgrade_text, reply_markup=kb)
    else:
        await update.message.reply_text(
            f"❌ حدث خطأ أثناء تنفيذ الطلب: {result.get('error', 'خطأ غير معروف')}",
            reply_markup=get_service_keyboard(user_id)
        )

    return ConversationHandler.END

# --- Upgrade Grodd Callback (old, not used anymore) ---
async def upgrade_grodd_callback(update: Update, context: CallbackContext):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "يرجى استخدام زر الترقية الجديد في القائمة الرئيسية.",
        reply_markup=None
    )

async def handle_screenshot(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    if context.user_data.get("awaiting_screenshot"):
        await update.message.forward(chat_id=ADMIN_ID)
        await update.message.reply_text("✅ تم إرسال لقطة الشاشة للإدارة. سيتم ترقية مستواك بعد المراجعة.")
        context.user_data["awaiting_screenshot"] = False

# --- Admin: List all users ---
async def list_users(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    report = "👥 **لائحة المستخدمين:**\n"
    for uid, data in users.items():
        report += f"ID: {uid} | @{data.get('username')} | مستوى: {data.get('level')} | محظور: {data.get('banned', False)}\n"
    await update.message.reply_text(report)

# --- Admin: Ban user ---
async def ban_user(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    parts = update.message.text.split()
    if len(parts) != 2:
        await update.message.reply_text("🔴 استعمل: /ban USER_ID")
        return
    uid = parts[1]
    if uid in users:
        users[uid]['banned'] = True
        save_users()
        await update.message.reply_text(f"🚫 تم حظر المستخدم {uid}")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود.")

# --- Admin: Unban user ---
async def unban_user(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    parts = update.message.text.split()
    if len(parts) != 2:
        await update.message.reply_text("🔵 استعمل: /unban USER_ID")
        return
    uid = parts[1]
    if uid in users:
        users[uid]['banned'] = False
        save_users()
        await update.message.reply_text(f"✅ تم رفع الحظر على المستخدم {uid}")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود.")

# --- Admin: Upgrade user to Grodd ---
async def upgrade_user(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    if len(context.args) != 1:
        await update.message.reply_text("استعمل: /upgrade USER_ID_OR_USERNAME")
        return
    target = context.args[0]
    user = users.get(target)
    if not user:
        for uid, data in users.items():
            if data.get("username") == target.lstrip("@"):
                user = data
                target = uid
                break
    if user:
        users[target]["level"] = "grodd"
        save_users()
        await update.message.reply_text(f"✅ تم ترقية المستخدم {target} إلى مستوى Grodd.")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود.")

# --- Admin: Downgrade user to regular ---
async def downgrade_user(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    if len(context.args) != 1:
        await update.message.reply_text("استعمل: /downgrade USER_ID_OR_USERNAME")
        return
    target = context.args[0]
    user = users.get(target)
    if not user:
        for uid, data in users.items():
            if data.get("username") == target.lstrip("@"):
                user = data
                target = uid
                break
    if user:
        users[target]["level"] = "regular"
        save_users()
        await update.message.reply_text(f"✅ تم إعادة المستخدم {target} إلى المستوى العادي.")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود.")

# --- Admin: Downgrade all Grodd users to regular ---
async def downgrade_all_grodd(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    count = 0
    for uid, data in users.items():
        if data.get("level") == "grodd":
            data["level"] = "regular"
            count += 1
    save_users()
    await update.message.reply_text(f"✅ تم إعادة {count} مستخدم من مستوى Grodd إلى المستوى العادي.")

# --- Admin: Add points ---
async def addpoints(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    if len(context.args) < 2:
        await update.message.reply_text("استعمل: /addpoints USER_ID_OR_USERNAME AMOUNT [ملاحظة]")
        return
    target, amount, *note = context.args
    note = " ".join(note)
    user = users.get(target)
    if not user:
        for uid, data in users.items():
            if data.get("username") == target.lstrip("@"):
                user = data
                target = uid
                break
    if not user:
        await update.message.reply_text("❌ المستخدم غير موجود.")
        return
    amount = int(amount)
    user["points"] = user.get("points", 0) + amount
    hist = user.setdefault("points_history", [])
    hist.append({
        "action": "إضافة",
        "amount": amount,
        "by": "admin",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": note
    })
    save_users()
    await update.message.reply_text(f"✅ تم إضافة {amount} نقطة للمستخدم {target}.")

# --- Admin: Remove points ---
async def removepoints(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    if len(context.args) < 2:
        await update.message.reply_text("استعمل: /removepoints USER_ID_OR_USERNAME AMOUNT [ملاحظة]")
        return
    target, amount, *note = context.args
    note = " ".join(note)
    user = users.get(target)
    if not user:
        for uid, data in users.items():
            if data.get("username") == target.lstrip("@"):
                user = data
                target = uid
                break
    if not user:
        await update.message.reply_text("❌ المستخدم غير موجود.")
        return
    amount = int(amount)
    user["points"] = max(0, user.get("points", 0) - amount)
    hist = user.setdefault("points_history", [])
    hist.append({
        "action": "سحب",
        "amount": amount,
        "by": "admin",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": note
    })
    save_users()
    await update.message.reply_text(f"✅ تم سحب {amount} نقطة من المستخدم {target}.")

# --- Admin: Broadcast message to all users (text, photo, or document) ---
async def broadcast(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return

    sent = 0
    failed = 0

    if update.message.photo:
        caption = update.message.caption or ""
        photo = update.message.photo[-1].file_id
        for uid in users:
            try:
                await context.bot.send_photo(chat_id=uid, photo=photo, caption=caption)
                sent += 1
            except Exception:
                failed += 1
    elif update.message.document:
        caption = update.message.caption or ""
        document = update.message.document.file_id
        for uid in users:
            try:
                await context.bot.send_document(chat_id=uid, document=document, caption=caption)
                sent += 1
            except Exception:
                failed += 1
    elif update.message.text:
        msg = update.message.text.partition(' ')[2] if update.message.text.startswith('/broadcast') else update.message.text
        if not msg.strip():
            await update.message.reply_text("Send your message after /broadcast or send a photo/document with caption.")
            return
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=msg)
                sent += 1
            except Exception:
                failed += 1
    else:
        await update.message.reply_text("Send a text, photo, or document to broadcast.")
        return

    await update.message.reply_text(f"📢 Sent to {sent} users. Failed: {failed}")

# --- Admin: Send message to any user by ID or username ---
async def send_user_message(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    if len(context.args) < 2:
        await update.message.reply_text("استعمل: /senduser USER_ID_OR_USERNAME رسالتك هنا")
        return
    target = context.args[0]
    msg = " ".join(context.args[1:])
    user = users.get(target)
    if not user:
        for uid, data in users.items():
            if data.get("username") == target.lstrip("@"):
                user = data
                target = uid
                break
    if not user:
        await update.message.reply_text("❌ المستخدم غير موجود.")
        return
    try:
        await context.bot.send_message(chat_id=target, text=msg)
        await update.message.reply_text("✅ تم إرسال الرسالة للمستخدم.")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل إرسال الرسالة: {e}")

# --- Handler for /orderstatus ---
ORDER_STATUS_WAIT_ID = range(1)

async def orderstatus_command(update: Update, context: CallbackContext):
    await update.message.reply_text("📝 أرسل رقم الطلب الذي تريد معرفة حالته:")
    return ORDER_STATUS_WAIT_ID

async def orderstatus_receive_id(update: Update, context: CallbackContext):
    order_id = update.message.text.strip()
    data = {
        "key": API_KEY,
        "action": "status",
        "order": order_id
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, data=data, timeout=10) as resp:
                result = await resp.json()
                msg = (
                    f"📦 <b>حالة الطلب</b>\n"
                    f"رقم الطلب: <code>{order_id}</code>\n"
                    f"الحالة: <b>{result.get('status', 'غير معروف')}</b>\n"
                    f"الكمية عند البدء: {result.get('start_count', '-')}\n"
                    f"المتبقي: {result.get('remains', '-')}\n"
                    f"التكلفة: {result.get('charge', '-')} {result.get('currency', '')}"
                )
        except Exception as e:
            msg = f"❌ حدث خطأ أثناء جلب حالة الطلب: {e}"
    await update.message.reply_text(msg, parse_mode="HTML")
    return ConversationHandler.END

order_status_conv = ConversationHandler(
    entry_points=[CommandHandler("orderstatus", orderstatus_command)],
    states={
        ORDER_STATUS_WAIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, orderstatus_receive_id)]
    },
    fallbacks=[],
)

# --- Admin: Maintenance Mode ---
async def maintenance_on(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    with open(MAINTENANCE_FILE, "w") as f:
        f.write("on")
    await update.message.reply_text("🛠️ تم تفعيل وضع الصيانة. لن يستطيع المستخدمون تنفيذ الطلبات الآن.")

async def maintenance_off(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    if os.path.exists(MAINTENANCE_FILE):
        os.remove(MAINTENANCE_FILE)
    await update.message.reply_text("✅ تم إيقاف وضع الصيانة. البوت يعمل الآن بشكل طبيعي.")

# --- Admin: Show all admin commands with hints ---
async def show_admin_commands(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    msg = (
        "<b>🛡️ All Admin Commands:</b>\n\n"
        "• <code>/users</code> — Show all users\n"
        "• <code>/ban USER_ID</code> — Ban a user\n"
        "• <code>/unban USER_ID</code> — Unban a user\n"
        "• <code>/upgrade USER_ID_OR_USERNAME</code> — Upgrade user to Grodd\n"
        "• <code>/downgrade USER_ID_OR_USERNAME</code> — Downgrade user to regular\n"
        "• <code>/downgradeallgrodd</code> — Downgrade all Grodd users to regular\n"
        "• <code>/addpoints USER_ID_OR_USERNAME AMOUNT [note]</code> — Add points\n"
        "• <code>/removepoints USER_ID_OR_USERNAME AMOUNT [note]</code> — Remove points\n"
        "• <code>/broadcast your message</code> — Broadcast message to all users\n"
        "• <code>/senduser USER_ID_OR_USERNAME your message</code> — Send message to a specific user\n"
        "• <code>/setpaidprice service_key new_price</code> — Change paid service price (e.g. paid_like)\n"
        "• <code>/disablepaid service_key</code> — Disable a paid service (e.g. paid_like)\n"
        "• <code>/enablepaid service_key</code> — Enable a paid service (e.g. paid_like)\n"
        "• <code>/setquantity service_key user_level quantity</code> — Change free service quantity per level\n"
        "• <code>/maintenance_on</code> — Enable maintenance mode\n"
        "• <code>/maintenance_off</code> — Disable maintenance mode\n"
        "\n"
        "<b>🔑 Notes:</b>\n"
        "- service_key: paid_like, paid_view, paid_tiktok_like, paid_tiktok_view, like, view, tiktok_like, tiktok_view\n"
        "- user_level: regular or grodd\n"
        "- All admin commands are available only to the admin."
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def admin_reply(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != str(ADMIN_ID):
        return
    if update.message.reply_to_message and update.message.reply_to_message.forward_from:
        user_id = update.message.reply_to_message.forward_from.id
        await context.bot.send_message(chat_id=user_id, text=f"رد الإدارة:\n{update.message.text}")
        await update.message.reply_text("✅ تم إرسال الرد للمستخدم.")

order_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(service_callback, pattern="^(order_likes|order_views|order_tiktok_view|order_tiktok_like|paid_services|support|upgrade_grodd_progress|back_to_services)$")],
    states={
        ASK_LINK: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link),
            CallbackQueryHandler(service_callback, pattern="^(back_to_services|paid_services|support|upgrade_grodd_progress)$")
        ],
    },
    fallbacks=[],
)

# --- Register Handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("users", list_users))
application.add_handler(CommandHandler("ban", ban_user))
application.add_handler(CommandHandler("unban", unban_user))
application.add_handler(CommandHandler("upgrade", upgrade_user))
application.add_handler(CommandHandler("downgrade", downgrade_user))
application.add_handler(CommandHandler("broadcast", broadcast))
application.add_handler(CommandHandler("removepoints", removepoints))
application.add_handler(CommandHandler("addpoints", addpoints))
application.add_handler(CommandHandler("senduser", send_user_message))
application.add_handler(CommandHandler("maintenance_on", maintenance_on))
application.add_handler(CommandHandler("maintenance_off", maintenance_off))
application.add_handler(CommandHandler("downgradeallgrodd", downgrade_all_grodd))
application.add_handler(order_conv)
application.add_handler(order_status_conv)
application.add_handler(CallbackQueryHandler(upgrade_grodd_callback, pattern="^upgrade_grodd$"))
application.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
application.add_handler(MessageHandler(filters.REPLY & filters.TEXT, admin_reply))

if __name__ == '__main__':
    application.run_polling()