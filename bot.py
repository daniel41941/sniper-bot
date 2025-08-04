import time
import requests
import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator
from ta.volatility import AverageTrueRange
from telegram import Bot
from datetime import datetime

# === CONFIGURATION (HARDCODED) ===
bot_token = "7963033521:AAHSq4KWwS3Yg9ppA0AtwNUvNpYlrVGHYak"
chat_id = "8132192522"
bot = Bot(token=bot_token)

balance = 500.0
RISK_PER_TRADE = 10
REWARD_PER_TRADE = 10

symbols = ['DOGE-USDT', 'DOT-USDT', 'LTC-USDT']
active_trades = {}

bot.send_message(chat_id=chat_id, text="🤖 1-Min Scalping Bot Started!\nPairs: DOGE, DOT, LTC")

def fetch_kucoin_candles(symbol, interval='1min'):
    url = f'https://api.kucoin.com/api/v1/market/candles?type={interval}&symbol={symbol}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        raw_data = response.json()['data']
        if len(raw_data) < 50:
            print(f"⚠️ Skipping {symbol} — not enough data")
            return None
        raw_data.reverse()

        df = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
        df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
        df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
        return df
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return None

def calculate_volatility(df):
    atr = AverageTrueRange(df['high'], df['low'], df['close'], window=7).average_true_range().iloc[-1]
    price = df['close'].iloc[-1]
    return (atr / price) * 100

def check_signals(df):
    try:
        ema = EMAIndicator(df['close'], window=9).ema_indicator()
        atr = AverageTrueRange(df['high'], df['low'], df['close'], window=7).average_true_range()
        adx = ADXIndicator(df['high'], df['low'], df['close'], window=10).adx()

        signals = {}
        c = df['close'].iloc[-1]
        prev_c = df['close'].iloc[-2]
        ema_now = ema.iloc[-1]
        ema_prev = ema.iloc[-2]
        atr_now = atr.iloc[-1]
        adx_now = adx.iloc[-1]

        if adx_now > 20:
            if c < ema_now and prev_c > ema_prev:
                signals['short'] = {'entry': c, 'sl': c + 1.2 * atr_now, 'tp': c - 0.8 * atr_now, 'atr': atr_now}
            elif c > ema_now and prev_c < ema_prev:
                signals['long'] = {'entry': c, 'sl': c - 1.2 * atr_now, 'tp': c + 0.8 * atr_now, 'atr': atr_now}
        return signals
    except Exception as e:
        print(f"⚠️ Strategy error: {e}")
        return {}

def run_bot():
    global balance
    while True:
        print(f"\n🔄 Monitoring... Balance: ${balance:.2f} — {datetime.now().strftime('%H:%M:%S')}")
        best_symbol = None
        highest_volatility = 0
        best_df = None

        for symbol in symbols:
            df = fetch_kucoin_candles(symbol)
            if df is None:
                continue

            vol = calculate_volatility(df)
            if vol > highest_volatility:
                highest_volatility = vol
                best_symbol = symbol
                best_df = df

        if not best_symbol:
            print("⚠️ No valid pair found this round.")
            time.sleep(5)
            continue

        print(f"🔥 Most volatile pair: {best_symbol} | Volatility: {highest_volatility:.2f}%")

        if best_symbol in active_trades:
            trade = active_trades[best_symbol]
            price = best_df['close'].iloc[-1]
            if trade['direction'] == 'short':
                if price <= trade['tp']:
                    balance += REWARD_PER_TRADE
                    bot.send_message(chat_id=chat_id, text=f"✅ TP HIT (SHORT) {best_symbol} @ {price:.4f}\nBalance: ${balance:.2f}")
                    del active_trades[best_symbol]
                elif price >= trade['sl']:
                    balance -= RISK_PER_TRADE
                    bot.send_message(chat_id=chat_id, text=f"❌ SL HIT (SHORT) {best_symbol} @ {price:.4f}\nBalance: ${balance:.2f}")
                    del active_trades[best_symbol]
            elif trade['direction'] == 'long':
                if price >= trade['tp']:
                    balance += REWARD_PER_TRADE
                    bot.send_message(chat_id=chat_id, text=f"✅ TP HIT (LONG) {best_symbol} @ {price:.4f}\nBalance: ${balance:.2f}")
                    del active_trades[best_symbol]
                elif price <= trade['sl']:
                    balance -= RISK_PER_TRADE
                    bot.send_message(chat_id=chat_id, text=f"❌ SL HIT (LONG) {best_symbol} @ {price:.4f}\nBalance: ${balance:.2f}")
                    del active_trades[best_symbol]
            time.sleep(5)
            continue

        signals = check_signals(best_df)
        if 'short' in signals:
            s = signals['short']
            active_trades[best_symbol] = {**s, 'direction': 'short'}
            bot.send_message(chat_id=chat_id, text=f"📉 SHORT SIGNAL: {best_symbol}\nEntry: {s['entry']:.4f}\nTP: {s['tp']:.4f}\nSL: {s['sl']:.4f}")
        elif 'long' in signals:
            s = signals['long']
            active_trades[best_symbol] = {**s, 'direction': 'long'}
            bot.send_message(chat_id=chat_id, text=f"📈 LONG SIGNAL: {best_symbol}\nEntry: {s['entry']:.4f}\nTP: {s['tp']:.4f}\nSL: {s['sl']:.4f}")

        time.sleep(5)

run_bot()
