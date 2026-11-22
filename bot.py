from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime
import requests
import time

# ================== Settings ==================
with open("bot_token.txt", "r") as f:
    TOKEN = f.read().strip()

user_data = {}
ASSETS = {
    "EURUSD_otc": "EURUSD",
    "GBPUSD_otc": "GBPUSD",
    "USDJPY_otc": "USDJPY",
    "AUDUSD_otc": "AUDUSD",
    "USDCAD_otc": "USDCAD",
    "EURGBP_otc": "EURGBP",
    "EURJPY_otc": "EURJPY",
    "GBPJPY_otc": "GBPJPY",
    "AUDJPY_otc": "AUDJPY",
    "NZDUSD_otc": "NZDUSD",
    "USDCHF_otc": "USDCHF",
    "EURCHF_otc": "EURCHF",
    "CADJPY_otc": "CADJPY",
    "CHFJPY_otc": "CHFJPY",
    "EURAUD_otc": "EURAUD",
    "EURCAD_otc": "EURCAD",
    "GBPAUD_otc": "GBPAUD",
    "GBPCAD_otc": "GBPCAD",
    "AUDCAD_otc": "AUDCAD",
    "AUDNZD_otc": "AUDNZD",
    "NZDJPY_otc": "NZDJPY",
}

# ================== Indicators ==================
def calculate_ema(prices, period):
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = price * k + ema * (1 - k)
    return ema

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices):
    if len(prices) < 26:
        return None, None
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    if ema12 is None or ema26 is None:
        return None, None
    macd_line = ema12 - ema26
    signal_line = macd_line * 0.18
    return macd_line, signal_line

def analyze_asset(symbol):
    try:
        url = f"https://biquote.io/api/{symbol}/ohlc"
        params = {"interval": "5m", "limit": 70}
        r = requests.get(url, params=params, timeout=12)
        data = r.json()
        bars = data.get("bars", [])
        if len(bars) < 40:
            return None

        closes = [float(b["close"]) for b in reversed(bars)]
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        rsi = calculate_rsi(closes, 14)
        macd_line, signal_line = calculate_macd(closes)

        if None in (ema9, ema21, rsi, macd_line):
            return None

        bullish = 0
        bearish = 0
        strength = abs(ema9 - ema21) / ((ema9 + ema21) / 2) * 10000
        price = closes[-1]

        if ema9 > ema21 and strength > 1.8:
            bullish += 1
        elif ema9 < ema21 and strength > 1.8:
            bearish += 1

        if 55 <= rsi <= 67:
            bullish += 1
        elif 33 <= rsi <= 45:
            bearish += 1

        if macd_line > signal_line and macd_line > 0:
            bullish += 1
        elif macd_line < signal_line and macd_line < 0:
            bearish += 1

        if bullish >= 3:
            return "CONFIRMED CALL", price, rsi, ema9, ema21, strength
        elif bearish >= 3:
            return "CONFIRMED PUT", price, rsi, ema9, ema21, strength
        elif bullish == 2:
            return "WAIT (Bullish)", price, rsi, ema9, ema21, strength
        elif bearish == 2:
            return "WAIT (Bearish)", price, rsi, ema9, ema21, strength
        else:
            return "AVOID", price, rsi, ema9, ema21, strength
    except:
        return None

# ================== Continuous job ==================
async def continuous_scan(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    mode = user_data.get(chat_id, {}).get("mode", "demo")

    found = []
    for asset, symbol in ASSETS.items():
        result = analyze_asset(symbol)
        if result and result[0].startswith("CONFIRMED"):
            direction, price, rsi, ema9, ema21, strength = result
            found.append((asset, direction, price, rsi))
        time.sleep(0.5)

    if found:
        text = f"📡 *Continuous Auto Signal* ({mode.upper()})\n"
        text += f"🕐 {datetime.now().strftime('%H:%M:%S')}\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        for asset, direction, price, rsi in found:
            emoji = "🟢" if "CALL" in direction else "🔴"
            text += f"🔹 `{asset}` → *{direction}* {emoji}\n💰 `{price:.5f}` | RSI: `{rsi:.1f}`\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n✅ Only confirmed signals"
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

# ================== Handlers ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Demo", callback_data="mode_demo"),
            InlineKeyboardButton("Real", callback_data="mode_real")
        ]
    ]
    await update.message.reply_text(
        "🤖 *Trading Assistant Bot*\n\nChoose account type:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    # Demo / Real
    if data in ["mode_demo", "mode_real"]:
        mode = "demo" if data == "mode_demo" else "real"
        user_data[chat_id] = {"mode": mode}

        keyboard = [
            [InlineKeyboardButton("Manual Confirm", callback_data="type_manual")],
            [InlineKeyboardButton("Auto Scan", callback_data="type_auto")],
            [InlineKeyboardButton("📡 Continuous Auto (every 5m)", callback_data="type_continuous")]
        ]
        await query.edit_message_text(
            f"✅ Mode: *{mode.upper()}*\n\nChoose type:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # ===== Manual (unchanged) =====
    if data == "type_manual":
        keyboard = []
        row = []
        for asset in ASSETS.keys():
            row.append(InlineKeyboardButton(asset, callback_data=f"manual_{asset}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        await query.edit_message_text(
            "📊 Select asset for confirmation:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ===== Auto Scan (unchanged) =====
    if data == "type_auto":
        await query.edit_message_text("⏳ Scanning market carefully...\nThis may take 20-40 seconds...")
        mode = user_data.get(chat_id, {}).get("mode", "demo")
        found = []

        for asset, symbol in ASSETS.items():
            result = analyze_asset(symbol)
            if result and result[0].startswith("CONFIRMED"):
                direction, price, rsi, ema9, ema21, strength = result
                found.append((asset, direction, price, rsi, strength))
            time.sleep(0.8)

        if not found:
            await query.edit_message_text("❌ No strong confirmed signals found right now.")
            return

        message = f"📊 *Auto Confirmed Signals* ({mode.upper()})\n━━━━━━━━━━━━━━━━━━━━\n"
        for asset, direction, price, rsi, strength in found:
            emoji = "🟢" if "CALL" in direction else "🔴"
            message += f"🔹 `{asset}` → *{direction}* {emoji}\n💰 `{price:.5f}` | RSI: `{rsi:.1f}`\n\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n✅ Only strong confirmed setups shown"
        await query.edit_message_text(message, parse_mode="Markdown")
        return

    # ===== Continuous Auto (NEW) =====
    if data == "type_continuous":
        # Remove old job if exists
        current_jobs = context.job_queue.get_jobs_by_name(f"cont_{chat_id}")
        for job in current_jobs:
            job.schedule_removal()

        context.job_queue.run_repeating(
            continuous_scan,
            interval=300,          # every 5 minutes
            first=5,               # first run after 5 seconds
            chat_id=chat_id,
            name=f"cont_{chat_id}"
        )

        keyboard = [[InlineKeyboardButton("⏹ Stop Continuous", callback_data="stop_continuous")]]
        await query.edit_message_text(
            "📡 *Continuous Auto started*\n\n"
            "Every 5 minutes the bot will scan and send only confirmed signals.\n"
            "Press Stop when you want to finish.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if data == "stop_continuous":
        current_jobs = context.job_queue.get_jobs_by_name(f"cont_{chat_id}")
        for job in current_jobs:
            job.schedule_removal()
        await query.edit_message_text("⏹ Continuous Auto stopped.")
        return

    # ===== Manual analysis (unchanged) =====
    if data.startswith("manual_"):
        asset = data.replace("manual_", "")
        mode = user_data.get(chat_id, {}).get("mode", "demo")
        symbol = ASSETS.get(asset)

        await query.edit_message_text(f"⏳ Analyzing {asset} carefully...")

        result = analyze_asset(symbol)
        if not result:
            await query.edit_message_text("❌ Could not get reliable data.")
            return

        status, price, rsi, ema9, ema21, strength = result
        now = datetime.now().strftime("%H:%M:%S")

        message = (
            f"📊 *Manual Confirmation*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 Mode: *{mode.upper()}*\n"
            f"🔹 Asset: `{asset}`\n"
            f"⏱ Timeframe: `5 Minutes`\n"
            f"📈 Status: *{status}*\n"
            f"💰 Price: `{price:.5f}`\n"
            f"📉 RSI(14): `{rsi:.1f}`\n"
            f"📊 EMA9: `{ema9:.5f}` | EMA21: `{ema21:.5f}`\n"
            f"💪 Trend Strength: `{strength:.2f}`\n"
            f"🕐 Time: `{now}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Careful multi-factor analysis"
        )
        await query.edit_message_text(message, parse_mode="Markdown")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
