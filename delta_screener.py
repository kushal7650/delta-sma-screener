import streamlit as st
import requests
import pandas as pd
import ta

# Delta Exchange India API
DELTA_API = "https://api.india.delta.exchange"

@st.cache_data(show_spinner=False)
def get_symbols():
    products_url = f"{DELTA_API}/v2/products"
    response = requests.get(products_url)
    products = response.json().get('result', [])

    symbols = []
    for p in products:
        contract_type = p.get('contract_type')
        quote_currency = p.get('quote_currency')
        symbol = p.get('symbol')
        product_id = p.get('id')

        if contract_type == 'perpetual_futures' and quote_currency == 'USDT' and symbol:
            # Confirm mark price exists
            mark_url = f"{DELTA_API}/v2/market-data/mark-price"
            mark_resp = requests.get(mark_url, params={"symbol": symbol})
            if mark_resp.status_code == 200 and "result" in mark_resp.json():
                symbols.append((symbol, product_id))

    return symbols

@st.cache_data(show_spinner=False)
def get_ohlcv(symbol, timeframe='15m', limit=200):
    url = f"{DELTA_API}/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": timeframe,
        "limit": limit
    }
    resp = requests.get(url, params=params).json()
    candles = resp.get("result", [])
    if not candles:
        return None
    df = pd.DataFrame(candles)
    df['timestamp'] = pd.to_datetime(df['time'], unit='s')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df

def apply_sma(df):
    df['sma20'] = ta.trend.SMAIndicator(df['close'], window=20).sma_indicator()
    df['sma200'] = ta.trend.SMAIndicator(df['close'], window=200).sma_indicator()
    return df

def screen_symbols(pairs, timeframe):
    bullish, bearish, neutral = [], [], []
    for sym, _ in pairs:
        try:
            df = get_ohlcv(sym, timeframe)
            if df is None or df.empty:
                st.warning(f"No data for {sym}")
                continue
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
            st.error(f"Error processing {sym}: {str(e)}")
    return bullish, bearish, neutral

# --- Streamlit UI ---
st.set_page_config(page_title="Delta SMA Screener", layout="centered")
st.title("📊 Delta Exchange SMA Screener")

symbols = get_symbols()
timeframe = st.selectbox("Select Time Frame", ["15m", "1h", "4h"])
bullish, bearish, neutral = screen_symbols(symbols, timeframe)

st.subheader("📈 Bullish (SMA20 > SMA200)")
for sym, price, dist in bullish:
    st.write(f"{sym} - Price: {price:.2f}, Dist from SMA20: {dist:.2f}%")

st.subheader("📉 Bearish (SMA20 < SMA200)")
for sym, price, dist in bearish:
    st.write(f"{sym} - Price: {price:.2f}, Dist from SMA20: {dist:.2f}%")

st.subheader("⚖️ Neutral (SMA20 ≈ SMA200)")
for sym, price, dist in neutral:
    st.write(f"{sym} - Price: {price:.2f}, Dist from SMA20: {dist:.2f}%")
