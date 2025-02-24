import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, InlineQueryHandler, ChosenInlineResultHandler
from datetime import datetime
from decouple import config
import threading
import os
from http.server import SimpleHTTPRequestHandler
import socketserver

# 模拟用户余额存储
user_balances = {}

# 红包存储
hongbaos = {}

# 管理员 ID
ADMIN_USER_ID = 7318904072

# 固定菜单按钮
FIXED_MENU_BUTTONS = ["充值", "提币", "红包", "首页", "把鸡鸡塞微微逼里看看", "青年大学习", "巨龙撞击！"]

# 主页内容生成函数
async def get_home_message(update: Update):
    user = update.effective_user
    nickname = user.full_name
    user_id = user.id
    balances = user_balances.get(user_id, {"usdt": 0, "cny": 0, "trx": 0})
    return (
        f"💰 昵称: {nickname}\n"
        f"💰 ID: {user_id}\n\n"
        f"💰 USDT: {balances['usdt']}\n"
        f"💰 CNY: {balances['cny']}\n"
        f"💰 TRX: {balances['trx']}"
    )

# 发送主页消息（新增文字消息召唤固定菜单）
async def send_home_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    home_text = await get_home_message(update)
    inline_keyboard = [
        [InlineKeyboardButton("充值", callback_data="deposit"), InlineKeyboardButton("提币", callback_data="withdraw")],
        [InlineKeyboardButton("红包", callback_data="redpacket"), InlineKeyboardButton("首页", callback_data="home")],
        [InlineKeyboardButton("把鸡鸡塞微微逼里看看", callback_data="send_voice")],
        [InlineKeyboardButton("青年大学习", callback_data="send_voice_youth"), InlineKeyboardButton("巨龙撞击！", callback_data="send_voice_dragon")]
    ]
    inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)
    reply_keyboard = [
        ["充值", "提币"],
        ["红包", "首页"],
        ["把鸡鸡塞微微逼里看看"],
        ["青年大学习", "巨龙撞击！"]
    ]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)

    # 发送主页消息（带内联键盘）
    try:
        with open("3.jpg", "rb") as photo:
            if update.message:
                await update.message.reply_photo(
                    photo=photo,
                    caption=home_text,
                    reply_markup=inline_reply_markup
                )
            elif update.callback_query:
                await update.callback_query.message.reply_photo(
                    photo=photo,
                    caption=home_text,
                    reply_markup=inline_reply_markup
                )
    except FileNotFoundError:
        if update.message:
            await update.message.reply_text(home_text + "\n❌ 图片 3.jpg 未找到！", reply_markup=inline_reply_markup)
        elif update.callback_query:
            await update.callback_query.message.reply_text(home_text + "\n❌ 图片 3.jpg 未找到！", reply_markup=inline_reply_markup)

    # 发送文字消息召唤固定菜单
    if update.message:
        await update.message.reply_text("请选择功能：", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text("请选择功能：", reply_markup=reply_markup)

# /start 命令
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_home_message(update, context)

# 管理员加钱命令 /addmoney <user_id> <usdt_amount>
async def add_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ 仅管理员可用！")
        return
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("用法：/addmoney <user_id> <usdt_amount>")
            return
        target_user_id = int(args[0])
        amount = float(args[1])
        if amount <= 0:
            await update.message.reply_text("❌ 金额必须大于 0！")
            return
        balances = user_balances.setdefault(target_user_id, {"usdt": 0, "cny": 0, "trx": 0})
        balances["usdt"] += amount
        await update.message.reply_text(f"✅ 已为用户 {target_user_id} 添加 {amount} USDT")
    except ValueError:
        await update.message.reply_text("❌ 参数无效，请输入数字！")

# 处理红包金额输入
async def handle_redpacket_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        amount = float(update.message.text)
        if not (0 <= amount <= 999):
            await update.message.reply_text("❌ 金额必须在 0 到 999 之间！")
            return
        if user_balances.get(user_id, {}).get("usdt", 0) < amount:
            await update.message.reply_text("❌ USDT 余额不足，无法发送红包！")
            return
        keyboard = [[InlineKeyboardButton("支付", callback_data=f"pay_{amount}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"您输入的红包金额为 {amount} USDT，点击支付确认：", reply_markup=reply_markup)
    except ValueError:
        await update.message.reply_text("❌ 请输入有效的数字！")

# 处理红包支付并生成发送按钮
async def handle_redpacket_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = float(query.data.split("_")[1])
    user_id = update.effective_user.id
    nickname = update.effective_user.full_name

    balances = user_balances.setdefault(user_id, {"usdt": 0, "cny": 0, "trx": 0})
    balances["usdt"] -= amount

    hongbao_id = str(random.randint(10000, 99999))
    hongbaos[hongbao_id] = {
        "sender_id": user_id,
        "sender_name": nickname,
        "total_amount": amount,
        "remaining_amount": amount,
        "remaining_count": 10,
        "receivers": [],
        "inline_message_id": None
    }

    keyboard = [[InlineKeyboardButton("发送红包", switch_inline_query=f"hongbao {hongbao_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="✅ 红包创建成功！点击下方按钮选择群组发送红包：",
        reply_markup=reply_markup
    )

# 处理内联查询
async def inlinequery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    user_id = update.inline_query.from_user.id
    nickname = update.inline_query.from_user.full_name

    if query.startswith("hongbao ") and len(query.split()) == 2:
        hongbao_id = query.split()[1]
        if hongbao_id in hongbaos and hongbaos[hongbao_id]["sender_id"] == user_id:
            hongbao = hongbaos[hongbao_id]
            message_text = f"{nickname} 发送了一个红包\n🧧 {nickname} 发送了一个红包\n💵总金额: {hongbao['total_amount']} USDT💰 剩余: 10/10"
            results = [
                InlineQueryResultArticle(
                    id=hongbao_id,
                    title="发送红包",
                    input_message_content=InputTextMessageContent(message_text),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("领取红包", callback_data=f"receive_{hongbao_id}")]])
                )
            ]
            await update.inline_query.answer(results)
        else:
            await update.inline_query.answer([])
    else:
        await update.inline_query.answer([])

# 处理内联消息发送后
async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chosen_inline_result
    hongbao_id = result.result_id
    if hongbao_id in hongbaos:
        hongbao = hongbaos[hongbao_id]
        hongbao["inline_message_id"] = result.inline_message_id
        message_text = f"{hongbao['sender_name']} 发送了一个红包\n🧧 {hongbao['sender_name']} 发送了一个红包\n💵总金额: {hongbao['total_amount']} USDT💰 剩余: 10/10"
        keyboard = [[InlineKeyboardButton("领取红包", callback_data=f"receive_{hongbao_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            with open("2.jpg", "rb") as photo:
                await context.bot.edit_message_media(
                    inline_message_id=hongbao["inline_message_id"],
                    media=InputMediaPhoto(media=photo, caption=message_text),
                    reply_markup=reply_markup
                )
        except FileNotFoundError:
            await context.bot.send_message(chat_id=result.from_user.id, text="❌ 图片 2.jpg 未找到，请确保文件存在！")
        except Exception as e:
            await context.bot.send_message(chat_id=result.from_user.id, text=f"初次消息编辑失败：{str(e)}")

# 处理红包领取
async def handle_hongbao_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hongbao_id = query.data.split("_")[1]
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name

    if hongbao_id not in hongbaos:
        await query.edit_message_caption("❌ 红包已过期或不存在！")
        return

    hongbao = hongbaos[hongbao_id]
    if hongbao["inline_message_id"] is None:
        await context.bot.send_message(chat_id=query.message.chat_id, text="红包消息未正确初始化，请重试！")
        return

    if user_id in [r["user_id"] for r in hongbao["receivers"]]:
        received_amount = next(r["amount"] for r in hongbao["receivers"] if r["user_id"] == user_id)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"您已经领取过 {received_amount} USDT了！"
        )
        return

    if hongbao["remaining_count"] <= 0:
        await context.bot.send_message(chat_id=query.message.chat_id, text="红包已被领完！")
        return

    remaining_amount = hongbao["remaining_amount"]
    amount = round(random.uniform(0.01, remaining_amount / hongbao["remaining_count"]), 2)
    hongbao["remaining_amount"] -= amount
    hongbao["remaining_count"] -= 1
    hongbao["receivers"].append({
        "user_id": user_id,
        "user_name": user_name,
        "amount": amount,
        "time": datetime.now().strftime("%H:%M:%S")
    })

    balances = user_balances.setdefault(user_id, {"usdt": 0, "cny": 0, "trx": 0})
    balances["usdt"] += amount

    receivers_text = "\n".join(
        f"🥇 {r['amount']} USDT💰 ({r['time']}) - {r['user_name']}"
        for r in hongbao["receivers"]
    )
    message_text = (
        f"{hongbao['sender_name']} 发送了一个红包\n"
        f"🧧 {hongbao['sender_name']} 发送了一个红包\n"
        f"💵总金额: {hongbao['total_amount']} USDT💰 剩余: {hongbao['remaining_count']}/10\n"
        f"{receivers_text}"
    )

    try:
        with open("2.jpg", "rb") as photo:
            if hongbao["remaining_count"] > 0:
                keyboard = [[InlineKeyboardButton("领取红包", callback_data=f"receive_{hongbao_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.edit_message_media(
                    inline_message_id=hongbao["inline_message_id"],
                    media=InputMediaPhoto(media=photo, caption=message_text),
                    reply_markup=reply_markup
                )
            else:
                keyboard = [[InlineKeyboardButton("点击查看", url="https://t.me/qianbaoo_bot")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.edit_message_media(
                    inline_message_id=hongbao["inline_message_id"],
                    media=InputMediaPhoto(media=photo, caption=message_text),
                    reply_markup=reply_markup
                )
    except FileNotFoundError:
        await context.bot.send_message(chat_id=query.message.chat_id, text="❌ 图片 2.jpg 未找到，无法更新消息！")
        return
    except Exception as e:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"消息更新失败：{str(e)}")
        return

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"您领取了 {amount} USDT！"
    )

# 处理按钮点击
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        message = query.message
        user_id = query.from_user.id
    elif update.message:
        data = update.message.text
        message = update.message
        user_id = message.from_user.id
    else:
        return

    if data == "deposit" or data == "充值":
        keyboard = [[InlineKeyboardButton("返回", callback_data="home")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            with open("4.jpg", "rb") as photo:
                caption = (
                    "👩‍💼 您正在使用 TRC20 付款\n\n"
                    "付款金额：\n"
                    "至少 1 USDT\n\n"
                    "支持货币: TRX💰, USDT💰\n\n"
                    "收款地址(TRC20):\n"
                    "`TFajYLudHAV2JyXsBtSA55412zKqAoWG7u`\n\n"
                    "👆 点击复制钱包地址，可重复充值!\n\n"
                    "提示：\n"
                    "- 对上述地址👆充值后, 经过3次网络确认, 充值成功!\n"
                    "- 请耐心等待, 充值成功后 Bot 会通知您!"
                )
                await message.reply_photo(photo=photo, caption=caption, reply_markup=reply_markup, parse_mode="Markdown")
        except FileNotFoundError:
            await message.reply_text("❌ 充值图片未找到！", reply_markup=reply_markup)
    elif data == "withdraw" or data == "提币":
        await message.reply_text("邀请五个人即可提现😅 https://t.me/qianbaoo_bot")
    elif data == "redpacket" or data == "红包":
        keyboard = [[InlineKeyboardButton("取消", callback_data="home")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text("请输入红包金额（0-999）：", reply_markup=reply_markup)
        context.user_data["awaiting_redpacket_amount"] = True
    elif data == "home" or data == "首页":
        await send_home_message(update, context)
    elif data == "send_voice" or data == "把鸡鸡塞微微逼里看看":
        balances = user_balances.setdefault(user_id, {"usdt": 0, "cny": 0, "trx": 0})
        balances["usdt"] += 100
        try:
            with open("666.ogg", "rb") as voice:
                if update.callback_query:
                    await context.bot.send_voice(chat_id=query.message.chat_id, voice=voice)
                    await context.bot.send_message(chat_id=query.message.chat_id, text="余额 +100 USDT")
                elif update.message:
                    await context.bot.send_voice(chat_id=message.chat_id, voice=voice)
                    await context.bot.send_message(chat_id=message.chat_id, text="余额 +100 USDT")
        except FileNotFoundError:
            if update.callback_query:
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ 语音文件 666.ogg 未找到！")
            elif update.message:
                await context.bot.send_message(chat_id=message.chat_id, text="❌ 语音文件 666.ogg 未找到！")
    elif data == "send_voice_youth" or data == "青年大学习":
        balances = user_balances.setdefault(user_id, {"usdt": 0, "cny": 0, "trx": 0})
        balances["usdt"] += 100
        try:
            with open("111.ogg", "rb") as voice:
                if update.callback_query:
                    await context.bot.send_voice(chat_id=query.message.chat_id, voice=voice)
                    await context.bot.send_message(chat_id=query.message.chat_id, text="余额 +100 USDT")
                elif update.message:
                    await context.bot.send_voice(chat_id=message.chat_id, voice=voice)
                    await context.bot.send_message(chat_id=message.chat_id, text="余额 +100 USDT")
        except FileNotFoundError:
            if update.callback_query:
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ 语音文件 111.ogg 未找到！")
            elif update.message:
                await context.bot.send_message(chat_id=message.chat_id, text="❌ 语音文件 111.ogg 未找到！")
    elif data == "send_voice_dragon" or data == "巨龙撞击！":
        balances = user_balances.setdefault(user_id, {"usdt": 0, "cny": 0, "trx": 0})
        balances["usdt"] += 100
        try:
            with open("222.ogg", "rb") as voice:
                if update.callback_query:
                    await context.bot.send_voice(chat_id=query.message.chat_id, voice=voice)
                    await context.bot.send_message(chat_id=query.message.chat_id, text="余额 +100 USDT")
                elif update.message:
                    await context.bot.send_voice(chat_id=message.chat_id, voice=voice)
                    await context.bot.send_message(chat_id=message.chat_id, text="余额 +100 USDT")
        except FileNotFoundError:
            if update.callback_query:
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ 语音文件 222.ogg 未找到！")
            elif update.message:
                await context.bot.send_message(chat_id=message.chat_id, text="❌ 语音文件 222.ogg 未找到！")
    elif data.startswith("pay_"):
        await handle_redpacket_payment(update, context)
    elif data.startswith("receive_"):
        await handle_hongbao_receive(update, context)

# 处理任意消息
async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if message_text in FIXED_MENU_BUTTONS:
        await handle_button(update, context)
    elif context.user_data.get("awaiting_redpacket_amount"):
        await handle_redpacket_amount(update, context)
        context.user_data["awaiting_redpacket_amount"] = False
    else:
        await send_home_message(update, context)

# 启动 HTTP 服务器（适配 Render 的 PORT 环境变量）
def run_http_server():
    PORT = int(os.getenv("PORT", 8080))  # Render 会提供 PORT，默认 8080 作为后备
    Handler = SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"HTTP server running on port {PORT}")
        httpd.serve_forever()

# 主程序
def main():
    TOKEN = config("BOT_TOKEN")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addmoney", add_money))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(InlineQueryHandler(inlinequery))
    application.add_handler(ChosenInlineResultHandler(chosen_inline_result))

    # 启动 HTTP 服务器线程
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    print("钱包机器人启动中...")
    application.run_polling()

if __name__ == "__main__":
    main()