import streamlit as st
import requests
import pandas as pd
import ta
from io import BytesIO
from streamlit_autorefresh import st_autorefresh

# --- 🔁 Auto-refresh every 5 minutes ---
st_autorefresh(interval=300000, key="refresh")

# --- ⚙️ Telegram Config ---
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with your bot token
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"      # Replace with your chat ID

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.warning(f"Telegram error: {str(e)}")

# --- API Setup ---
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
def get_ohlcv(symbol, timeframe='15m', limit=210):
    url = f"{DELTA_API}/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": timeframe,
        "limit": limit
    }
    resp = requests.get(url, params=params).json()
    candles = resp.get("result", [])
    if not candles or len(candles) < 210:
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

def get_trend_status(df):
    if df is None or len(df) < 210:
        return "-"
    df = apply_sma(df)
    latest = df.iloc[-1]
    price = latest['close']
    sma20 = latest.get('sma20')
    sma200 = latest.get('sma200')

    if pd.isna(sma20) or pd.isna(sma200):
        return "-"
    
    # Perfect trends
    if price > sma20 and sma20 > sma200:
        return "Bullish"
    elif price < sma20 and sma20 < sma200:
        return "Bearish"
    # Reversal zones
    elif price > sma20 and sma20 < sma200:
        return "🔁 Bullish Reversal"
    elif price < sma20 and sma20 > sma200:
        return "🔁 Bearish Reversal"
    else:
        return "-"

def multi_tf_scan(symbols, timeframes):
    output = []
    for sym, _ in symbols:
        row = {"Symbol": sym}
        trend_values = []
        for tf in timeframes:
            try:
                df = get_ohlcv(sym, tf)
                trend = get_trend_status(df)
                row[tf] = trend
                trend_values.append(trend)
            except:
                row[tf] = "-"
                trend_values.append("-")

        # Classify
        if all(t == "Bullish" for t in trend_values):
            row["Setup Match"] = "✅ Bullish All Frames"
        elif all(t == "Bearish" for t in trend_values):
            row["Setup Match"] = "🔻 Bearish All Frames"
        elif any("Reversal" in t for t in trend_values):
            row["Setup Match"] = "🔁 Reversal Detected"
        else:
            row["Setup Match"] = "-"
        output.append(row)
    return pd.DataFrame(output)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Scan")
    return output.getvalue()

# --- Streamlit UI ---
st.set_page_config(page_title="Delta SMA Screener", layout="wide")
st.title("📊 Multi-Timeframe Crypto Screener")
st.caption("Source: Delta Exchange India")

timeframes = ["1m", "5m", "15m", "1h"]
filter_type = st.selectbox("🔍 Filter View", ["All", "Only Perfect Bullish", "Only Perfect Bearish", "Only Reversals"])

st.info("Scanning all coins and refreshing every 5 minutes...")

# 🔄 Get data
symbols = get_symbols()
result_df = multi_tf_scan(symbols, timeframes)

# 📩 Send alerts via Telegram
perfect_bullish = result_df[result_df["Setup Match"] == "✅ Bullish All Frames"]
perfect_bearish = result_df[result_df["Setup Match"] == "🔻 Bearish All Frames"]
reversals = result_df[result_df["Setup Match"] == "🔁 Reversal Detected"]

if not perfect_bullish.empty:
    msg = "*🚀 Bullish Setup(s):*\n" + "\n".join(perfect_bullish['Symbol'].tolist())
    send_telegram_message(msg)

if not perfect_bearish.empty:
    msg = "*🔻 Bearish Setup(s):*\n" + "\n".join(perfect_bearish['Symbol'].tolist())
    send_telegram_message(msg)

if not reversals.empty:
    msg = "*🔁 Reversal Detected:*\n" + "\n".join(reversals['Symbol'].tolist())
    send_telegram_message(msg)

# ✅ Apply filter AFTER data is created
if filter_type == "Only Perfect Bullish":
    result_df = result_df[result_df["Setup Match"] == "✅ Bullish All Frames"]
elif filter_type == "Only Perfect Bearish":
    result_df = result_df[result_df["Setup Match"] == "🔻 Bearish All Frames"]
elif filter_type == "Only Reversals":
    result_df = result_df[result_df["Setup Match"] == "🔁 Reversal Detected"]

# 🧾 Show table
st.dataframe(result_df, use_container_width=True)

# 📥 Download
excel_data = to_excel(result_df)
st.download_button(
    label="📥 Download Screener Results (Excel)",
    data=excel_data,
    file_name="delta_screener_results.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
