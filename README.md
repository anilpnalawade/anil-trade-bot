# Anil Trade Bot

This bot executes a simple SMA crossover trading strategy using Zerodha Kite API.

## Features
- 5-min SMA 20/50 crossover on INFY, TCS, HDFCBANK, LT
- 2% Stop Loss, 4% Target
- Telegram alerts
- Runs every 5 minutes

## Setup

1. Clone repo and install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file:
```
API_KEY=your_kite_api_key
ACCESS_TOKEN=your_daily_access_token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

3. Run the bot:
```bash
python anil_trade_bot.py
```

## Access Token
You must generate a new `ACCESS_TOKEN` daily using the manual login script.
