import os
import time
import datetime
import pandas as pd
import schedule
import requests
from kiteconnect import KiteConnect
from dotenv import load_dotenv

# === Load .env File ===
load_dotenv()

# === Read from .env ===
api_key = os.getenv("API_KEY")
access_token = os.getenv("ACCESS_TOKEN")
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

symbols = ["INFY", "TCS", "HDFCBANK", "LT"]
quantity = 1
sl_pct = 0.02
target_pct = 0.04
traded_today = set()

# === Initialize Kite ===
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# === Telegram Alert ===
def send_alert(message):
    try:
        url = f"https://api.telegram.org/bot7849103865:AAHKIqI1RwsOGE61p2aVK40KQvJ82wnmxMQ/sendMessage"
        payload = {"chat_id": telegram_chat_id, "text": message}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

# === SMA Crossover Check ===
def check_crossover(symbol):
    try:
        ltp_info = kite.ltp(f"NSE:{symbol}")
        instrument = ltp_info[f"NSE:{symbol}"]["instrument_token"]

        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=5)

        data = kite.historical_data(instrument_token=instrument,
                                    from_date=from_date,
                                    to_date=to_date,
                                    interval="5minute")

        df = pd.DataFrame(data)
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=50).mean()

        if len(df) < 51:
            return None, None

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        prev_cross = prev['sma20'] > prev['sma50']
        curr_cross = curr['sma20'] > curr['sma50']

        if not prev_cross and curr_cross:
            return "BUY", curr['close']
        elif prev_cross and not curr_cross:
            return "SELL", curr['close']
        else:
            return None, None

    except Exception as e:
        send_alert(f"❌ Error checking {symbol}: {e}")
        return None, None

# === Core Strategy ===
def run_strategy():
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"📊 Running strategy at {now}")

    for symbol in symbols:
        if symbol in traded_today:
            continue

        signal, price = check_crossover(symbol)

        if signal:
            sl = round(price * (1 - sl_pct), 2) if signal == "BUY" else round(price * (1 + sl_pct), 2)
            target = round(price * (1 + target_pct), 2) if signal == "BUY" else round(price * (1 - target_pct), 2)

            try:
                order_id = kite.place_order(
                    variety="regular",
                    exchange="NSE",
                    tradingsymbol=symbol,
                    transaction_type=signal,
                    quantity=quantity,
                    order_type="MARKET",
                    product="MIS"
                )

                traded_today.add(symbol)
                msg = f"📈 {signal} order placed for {symbol} at ₹{price}\n🎯 Target: ₹{target}, 🛑 SL: ₹{sl}\n🧾 Order ID: {order_id}"
                send_alert(msg)

            except Exception as e:
                send_alert(f"❌ Order failed for {symbol}: {e}")
        else:
            print(f"No signal for {symbol}")

# === Schedule Job ===
schedule.every(5).minutes.do(run_strategy)

print("✅ Anil Trade Bot started.")
while True:
    schedule.run_pending()
    time.sleep(1)
