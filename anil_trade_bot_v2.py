
import os
import time
import datetime
import pandas as pd
import requests
from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
access_token = os.getenv("ACCESS_TOKEN")
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

symbols = ["INFY", "TCS", "HDFCBANK", "LT"]
quantity = 1
sl_pct = 0.02
target_pct = 0.04

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

trades = {}

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    with open("trade_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def send_alert(msg):
    try:
        if not telegram_token or not telegram_chat_id:
            return
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        requests.post(url, data={"chat_id": telegram_chat_id, "text": msg})
    except Exception as e:
        log(f"Telegram error: {e}")

def check_crossover(symbol):
    try:
        ltp_info = kite.ltp(f"NSE:{symbol}")
        instrument = ltp_info[f"NSE:{symbol}"]["instrument_token"]

        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=5)

        data = kite.historical_data(instrument, from_date, to_date, "5minute")
        df = pd.DataFrame(data)
        df["sma20"] = df["close"].rolling(20).mean()
        df["sma50"] = df["close"].rolling(50).mean()

        if len(df) < 51:
            return None, None

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        prev_cross = prev["sma20"] > prev["sma50"]
        curr_cross = curr["sma20"] > curr["sma50"]

        if not prev_cross and curr_cross:
            return "BUY", curr["close"]
        elif prev_cross and not curr_cross:
            return "SELL", curr["close"]
        return None, None
    except Exception as e:
        log(f"Error in crossover for {symbol}: {e}")
        return None, None

def place_order(symbol, signal, price):
    try:
        sl = round(price * (1 - sl_pct), 2) if signal == "BUY" else round(price * (1 + sl_pct), 2)
        target = round(price * (1 + target_pct), 2) if signal == "BUY" else round(price * (1 - target_pct), 2)

        order_id = kite.place_order(
            variety="regular",
            exchange="NSE",
            tradingsymbol=symbol,
            transaction_type=signal,
            quantity=quantity,
            order_type="MARKET",
            product="MIS"
        )

        trades[symbol] = {
            "direction": signal,
            "entry": price,
            "sl": sl,
            "target": target,
            "status": "OPEN"
        }

        msg = f"📈 {signal} {symbol} at ₹{price} | 🎯 ₹{target} 🛑 ₹{sl} | Order ID: {order_id}"
        log(msg)
        send_alert(msg)
    except Exception as e:
        log(f"Order failed for {symbol}: {e}")
        send_alert(f"❌ Order failed for {symbol}: {e}")

def check_exit(symbol):
    if symbol not in trades or trades[symbol]["status"] != "OPEN":
        return

    try:
        price = kite.ltp(f"NSE:{symbol}")[f"NSE:{symbol}"]["last_price"]
        trade = trades[symbol]
        if trade["direction"] == "BUY":
            if price >= trade["target"] or price <= trade["sl"]:
                exit_trade(symbol, price)
        else:
            if price <= trade["target"] or price >= trade["sl"]:
                exit_trade(symbol, price)
    except Exception as e:
        log(f"Error checking exit for {symbol}: {e}")

def exit_trade(symbol, exit_price):
    try:
        direction = "SELL" if trades[symbol]["direction"] == "BUY" else "BUY"
        kite.place_order(
            variety="regular",
            exchange="NSE",
            tradingsymbol=symbol,
            transaction_type=direction,
            quantity=quantity,
            order_type="MARKET",
            product="MIS"
        )
        trades[symbol]["status"] = "CLOSED"
        msg = f"✅ Exited {symbol} at ₹{exit_price} (via SL/Target)"
        log(msg)
        send_alert(msg)
    except Exception as e:
        log(f"Error exiting trade for {symbol}: {e}")
        send_alert(f"❌ Error exiting {symbol}: {e}")

def square_off_all():
    try:
        positions = kite.positions()["net"]
        for p in positions:
            if p["product"] == "MIS" and p["quantity"] != 0:
                direction = "SELL" if p["quantity"] > 0 else "BUY"
                kite.place_order(
                    variety="regular",
                    exchange=p["exchange"],
                    tradingsymbol=p["tradingsymbol"],
                    transaction_type=direction,
                    quantity=abs(p["quantity"]),
                    order_type="MARKET",
                    product="MIS"
                )
                msg = f"🔁 Auto square-off {p['tradingsymbol']} at 3:15 PM"
                log(msg)
                send_alert(msg)
    except Exception as e:
        log(f"Square-off error: {e}")
        send_alert(f"❌ Square-off error: {e}")

# === Start ===
log("✅ Anil Trade Bot v2 started.")

entry_done = False

while True:
    now = datetime.datetime.now().strftime("%H:%M")

    if now == "09:15" and not entry_done:
        log("📊 Running strategy for entry...")
        for symbol in symbols:
            signal, price = check_crossover(symbol)
            if signal:
                place_order(symbol, signal, price)
            else:
                log(f"No signal for {symbol}")
        entry_done = True

    if entry_done:
        for symbol in list(trades.keys()):
            check_exit(symbol)

    if now == "15:15":
        square_off_all()
        log("🚪 Exiting bot after square-off.")
        break

    time.sleep(30)
