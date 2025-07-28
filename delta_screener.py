import streamlit as st
import requests
import pandas as pd
import ta

DELTA_API = "https://api.delta.exchange"

@st.cache_data(show_spinner=False)
def get_symbols():
    url = f"{DELTA_API}/v2/products"
    resp = requests.get(url).json()
    return [(p['symbol'], p['id']) for p in resp['result'] if p['contract_type'] == 'perpetual']

@st.cache_data(show_spinner=False)
def get_ohlcv(product_id, timeframe='15m', limit=200):
    url = f"{DELTA_API}/v2/candles"
    params = {
        "product_id": product_id,
        "interval": timeframe,
        "limit": limit
    }
    resp = requests.get(url, params=params).json()
    candles = resp['result']
    df = pd.DataFrame(candles)
    df['timestamp'] = pd.to_datetime(df['time'], unit='s')
    df = df.sort_values('timestamp')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df

def apply_sma(df):
    df['sma20'] = ta.trend.SMAIndicator(df['close'], window=20).sma_indicator()
    df['sma200'] = ta.trend.SMAIndicator(df['close'], window=200).sma_indicator()
    return df

def screen_symbols(pairs, timeframe):
    bullish, bearish, neutral = [], [], []
    for sym, pid in pairs:
        try:
            df = get_ohlcv(pid, timeframe)
            df = apply_sma(df)
            latest = df.iloc[-1]
            if pd.isna(latest['sma20']) or pd.isna(latest['sma200']):
                continue
            price = latest['close']
            dist = abs(price - latest['sma20']) / price * 100
            if latest['sma20'] > latest['sma200']:
                bullish.append((sym, price, dist))
            elif latest['sma20'] < latest['sma200']:
                bearish.append((sym, price, dist))
            else:
                neutral.append((sym, price, dist))
        except Exception as e:
            print(f"Error processing {sym}: {e}")
    return bullish, bearish, neutral

st.set_page_config(page_title="Delta SMA Screener", layout="centered")
st.title("📊 Delta Exchange SMA Screener")

symbols = get_symbols()
timeframe = st.selectbox("Select Time Frame", ["15m", "1h", "4h"])
bullish, bearish, neutral = screen_symbols(symbols, timeframe)

st.subheader(\"📈 Bullish (SMA20 > SMA200)")
for sym, price, dist in bullish:
    st.write(f\"{sym} - Price: {price:.2f}, Dist from SMA20: {dist:.2f}%\")

st.subheader(\"📉 Bearish (SMA20 < SMA200)")
for sym, price, dist in bearish:
    st.write(f\"{sym} - Price: {price:.2f}, Dist from SMA20: {dist:.2f}%\")

st.subheader(\"⚖️ Neutral (SMA20 ≈ SMA200)")
for sym, price, dist in neutral:
    st.write(f\"{sym} - Price: {price:.2f}, Dist from SMA20: {dist:.2f}%\")
