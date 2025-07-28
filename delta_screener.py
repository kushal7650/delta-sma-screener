import streamlit as st
import requests
import pandas as pd
import ta
from io import BytesIO

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
                continue
            df = apply_sma(df)
            latest = df.iloc[-1]
            if pd.isna(latest['sma20']) or pd.isna(latest['sma200']):
                continue
            price = latest['close']
            dist = abs(price - latest['sma20']) / price * 100
            record = {
                "Symbol": sym,
                "Price": round(price, 2),
                "SMA20": round(latest['sma20'], 2),
                "SMA200": round(latest['sma200'], 2),
                "Distance from SMA20 (%)": round(dist, 2)
            }
            if latest['sma20'] > latest['sma200']:
                bullish.append(record)
            elif latest['sma20'] < latest['sma200']:
                bearish.append(record)
            else:
                neutral.append(record)
        except Exception as e:
            st.error(f"Error processing {sym}: {str(e)}")
    return pd.DataFrame(bullish), pd.DataFrame(bearish), pd.DataFrame(neutral)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- Streamlit UI ---
st.set_page_config(page_title="Delta SMA Screener", layout="centered")
st.title("📊 Delta Exchange SMA Screener")

symbols = get_symbols()
timeframe = st.selectbox("Select Time Frame", ["15m", "1h", "4h"])
bullish_df, bearish_df, neutral_df = screen_symbols(symbols, timeframe)

# ---- Output each section ----
def show_section(title, df, label):
    st.subheader(title)
    if not df.empty:
        st.dataframe(df)
        excel_data = to_excel(df)
        st.download_button(
            label=f"📥 Download {label} as Excel",
            data=excel_data,
            file_name=f"{label.lower()}_{timeframe}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No entries in this category.")

show_section("📈 Bullish (SMA20 > SMA200)", bullish_df, "Bullish")
show_section("📉 Bearish (SMA20 < SMA200)", bearish_df, "Bearish")
show_section("⚖️ Neutral (SMA20 ≈ SMA200)", neutral_df, "Neutral")
