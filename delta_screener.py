import streamlit as st
import requests
import pandas as pd
import ta

DELTA_API = "https://api.india.delta.exchange"

@st.cache_data
def get_symbols():
    url = f"{DELTA_API}/v2/products"
    res = requests.get(url).json()
    return [(p['symbol'], p['id']) for p in res['result']
            if p['contract_type'] == 'perpetual_futures' and p['quote_currency'] == 'USDT']

@st.cache_data
def get_ohlcv(symbol, timeframe='5m', limit=210):
    url = f"{DELTA_API}/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": timeframe,
        "limit": limit
    }
    res = requests.get(url, params=params).json()
    candles = res.get("result", [])
    if not candles or len(candles) < 200:
        return None
    df = pd.DataFrame(candles)
    df['timestamp'] = pd.to_datetime(df['time'], unit='s')
    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
    return df

def apply_sma(df):
    df['sma20'] = ta.trend.SMAIndicator(df['close'], window=20).sma_indicator()
    df['sma200'] = ta.trend.SMAIndicator(df['close'], window=200).sma_indicator()
    return df

def check_trend(df):
    if df is None or len(df) < 200:
        return "No Data"
    df = apply_sma(df)
    last = df.iloc[-1]
    if pd.isna(last['sma20']) or pd.isna(last['sma200']):
        return "No Data"
    if last['sma20'] > last['sma200']:
        return "Bullish"
    elif last['sma20'] < last['sma200']:
        return "Bearish"
    else:
        return "Flat"

def categorize_assets(symbols, timeframes):
    results = {tf: {"Bullish": [], "Bearish": []} for tf in timeframes}
    for symbol, _ in symbols:
        for tf in timeframes:
            df = get_ohlcv(symbol, tf)
            status = check_trend(df)
            if status == "Bullish":
                results[tf]["Bullish"].append(symbol)
            elif status == "Bearish":
                results[tf]["Bearish"].append(symbol)
    return results

# --- UI ---
st.set_page_config(page_title="Delta SMA Categorizer", layout="wide")
st.title("📈 SMA 20 vs SMA 200 Categorizer")
st.caption("Shows assets under Bullish/Bearish by SMA structure")

all_symbols = get_symbols()
selected = st.multiselect("Select up to 10 assets", [s[0] for s in all_symbols], default=[s[0] for s in all_symbols][:10], max_selections=10)
symbols = [s for s in all_symbols if s[0] in selected]

timeframes = ["5m", "15m"]

if symbols:
    results = categorize_assets(symbols, timeframes)
    for tf in timeframes:
        st.subheader(f"🕒 {tf.upper()} Timeframe")
        st.markdown(f"✅ **Bullish (SMA 20 > SMA 200)**\n- {', '.join(results[tf]['Bullish']) or 'None'}")
        st.markdown(f"🔻 **Bearish (SMA 20 < SMA 200)**\n- {', '.join(results[tf]['Bearish']) or 'None'}")
else:
    st.warning("Please select assets to scan.")
