import logging
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
 
# for docker image uncoment 3 line below and delete 2 lines above
# import os
# TOKEN = os.getenv("BOT_TOKEN")
# NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")


logging.basicConfig(level=logging.INFO)
user_profiles = {}
user_states = {}  # user_id: {"step": ..., "amount": ...}

# Top 10 major coins (NOWPayments codes, lowercase) except BTC
TOP_COINS = [
    "btc", "eth", "usdttrc20", "usdc", "bnbbsc", "sol", "xrp", "doge", "ton", "ada", "trx", "shib", "trump"
]

def get_supported_currencies():
    url = "https://api.nowpayments.io/v1/currencies"
    headers = {"x-api-key": NOWPAYMENTS_API_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()
    # Handle both NOWPayments string-list and dict-list
    if isinstance(data, dict) and "currencies" in data:
        currencies = set(c.lower() for c in data["currencies"])
    else:
        currencies = set(c.lower() for c in data)
    # Only keep those in TOP_COINS
    available = [coin for coin in TOP_COINS if coin in currencies]
    return available

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if user_id not in user_profiles:
        user_profiles[user_id] = {
            "user_id": user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "registered_at": datetime.utcnow().isoformat()
        }
    await update.message.reply_text(
        f"Hello, {user.first_name}! Your profile has been created.\nType /pay to make a payment."
    )

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"step": "awaiting_amount"}
    await update.message.reply_text("Please enter the amount in USD you want to pay (using . ex: 10.0 for 10 or 100.0 for 100):")

async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_states and user_states[user_id].get("step") == "awaiting_amount":
        try:
            amount = float(update.message.text)
            if amount < 1:
                await update.message.reply_text("Minimum payment is $1. Please enter a higher amount.")
                return
            user_states[user_id]["amount"] = amount
            user_states[user_id]["step"] = "awaiting_currency"
            currencies = get_supported_currencies()
            if not currencies:
                await update.message.reply_text("No major cryptocurrencies available at the moment.")
                return
            # Arrange buttons in rows of 2
            def chunked(lst, n): return [lst[i:i+n] for i in range(0, len(lst), n)]
            keyboard = [
                [InlineKeyboardButton(currency.upper(), callback_data=f"pay_{currency}")]
                for currency in currencies
            ]
            reply_markup = InlineKeyboardMarkup(chunked([btn[0] for btn in keyboard], 2))
            await update.message.reply_text(
                "Choose your preferred cryptocurrency for payment:", reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")

async def pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id, {})
    amount = state.get("amount")
    if not amount:
        await query.edit_message_text("Please use /pay to start a new payment.")
        return
    data = query.data
    if data.startswith("pay_"):
        currency = data[4:]
        payment = create_nowpayments_invoice(amount, currency)
        if payment and "invoice_url" in payment:
            keyboard = [
                [InlineKeyboardButton("Pay Now", url=payment["invoice_url"])]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"Pay ${amount} in {currency.upper()} using the button below:",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                f"Error generating payment invoice for {currency.upper()}."
            )
        # Clear user state
        user_states.pop(user_id, None)

def create_nowpayments_invoice(amount_usd, currency):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "price_amount": amount_usd,
        "price_currency": "usd",
        "pay_currency": currency,
        "order_id": "telegram_order_123",
        "order_description": f"Telegram Crypto Payment in {currency.upper()}",
        "is_fixed_rate": True,
        "is_fee_paid_by_user": False
    }
    response = requests.post(url, json=data, headers=headers)
    logging.info(f"NOWPayments response: {response.status_code} {response.text}")
    if response.status_code == 200:
        return response.json()
    return None

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler('start', start))
app.add_handler(CommandHandler('pay', pay))
app.add_handler(CallbackQueryHandler(pay_callback, pattern="^pay_"))
# Handler for numeric input after /pay
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), amount_handler))

if __name__ == '__main__':
    app.run_polling()