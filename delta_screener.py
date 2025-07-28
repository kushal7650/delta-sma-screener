import streamlit as st
import requests
import pandas as pd
import ta
from io import BytesIO
from streamlit_autorefresh import st_autorefresh
import matplotlib.pyplot as plt

# --- 🔁 Auto-refresh every 5 minutes ---
st_autorefresh(interval=300000, key="refresh")

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
    
    if price > sma20 and sma20 > sma200:
        return "Bullish"
    elif price < sma20 and sma20 < sma200:
        return "Bearish"
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

def plot_price_chart(symbol, timeframe='1h'):
    df = get_ohlcv(symbol, timeframe)
    if df is None or df.empty:
        st.warning(f"{symbol}: No data.")
        return

    fig, ax = plt.subplots(figsize=(6, 2))
    ax.plot(df['timestamp'], df['close'], label="Price", linewidth=1.5)
    ax.set_title(f"{symbol} - {timeframe} Chart", fontsize=10)
    ax.set_ylabel("Price", fontsize=8)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(True, linestyle="--", alpha=0.3)
    st.pyplot(fig)

# --- Streamlit UI ---
st.set_page_config(page_title="Delta SMA Screener", layout="wide")
st.title("📊 Multi-Timeframe Crypto Screener")
st.caption("Source: Delta Exchange India")

timeframes = ["1m", "5m", "15m", "1h"]
filter_type = st.selectbox("🔍 Filter View", ["All", "Only Perfect Bullish", "Only Perfect Bearish", "Only Reversals"])

# 🔄 Get all tradable symbols
all_symbols = get_symbols()
all_symbol_names = [s[0] for s in all_symbols]

st.markdown("### Select up to 6 assets to scan:")
selected = st.multiselect("Assets", all_symbol_names, default=all_symbol_names[:10], max_selections=6)

# Filter symbols based on selection
symbols = [s for s in all_symbols if s[0] in selected]

st.write("✅ Total selected symbols:", len(symbols))

# Run scanner
if symbols:
    result_df = multi_tf_scan(symbols, timeframes)

    if "Setup Match" in result_df.columns:
        if filter_type == "Only Perfect Bullish":
            result_df = result_df[result_df["Setup Match"] == "✅ Bullish All Frames"]
        elif filter_type == "Only Perfect Bearish":
            result_df = result_df[result_df["Setup Match"] == "🔻 Bearish All Frames"]
        elif filter_type == "Only Reversals":
            result_df = result_df[result_df["Setup Match"] == "🔁 Reversal Detected"]

    if result_df.empty:
        st.warning("⚠️ No matching results found for selected symbols and filter.")
    else:
        st.dataframe(result_df, use_container_width=True)
        excel_data = to_excel(result_df)
        st.download_button(
            label="📥 Download Screener Results (Excel)",
            data=excel_data,
            file_name="delta_screener_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.markdown("### 📈 Price Charts (1H Timeframe)")
        for sym in result_df["Symbol"]:
            plot_price_chart(sym, timeframe='1h')
else:
    st.warning("⚠️ Please select at least 1 asset to scan.")
