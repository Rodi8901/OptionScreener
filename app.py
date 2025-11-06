import streamlit as st
import yfinance as yf
import pandas as pd
import os, time

st.set_page_config(page_title="S&P 500 Aktien Screener", layout="wide")
st.title("📊 S&P 500 Aktien Screener")

# --- Sidebar-Filter ---
st.sidebar.header("Filtereinstellungen")
min_marketcap = st.sidebar.number_input("Min. Market Cap (Mrd $)", 0.5, 1000.0, 2.0, step=0.5)
min_price = st.sidebar.number_input("Min. Preis ($)", 1, 500, 20)
max_price = st.sidebar.number_input("Max. Preis ($)", 1, 1000, 70)
min_volume = st.sidebar.number_input("Min. Ø Volumen (Mio)", 0.1, 100.0, 1.0, step=0.1)

# --- Lade S&P500-Liste ---
@st.cache_data
def load_sp500_list():
    file_path = os.path.join(os.path.dirname(__file__), "sp500.csv")
    df = pd.read_csv(file_path)
    return df["Symbol"].tolist(), df

tickers, sp500_df = load_sp500_list()
st.success(f"{len(tickers)} S&P 500 Aktien geladen.")
tickers = tickers[:30]  # testweise begrenzen

# --- Hole Finanzdaten (nur einmal cachen!) ---
@st.cache_data(show_spinner=True)
def load_yf_data(tickers):
    results = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            results.append({
                "Ticker": t,
                "Name": info.get("shortName"),
                "Country": info.get("country") or "",
                "MarketCap": info.get("marketCap", 0),
                "Price": info.get("regularMarketPrice", 0),
                "Volume": info.get("averageVolume", 0),
                "PERatio": info.get("trailingPE", 0),
                "Optionable": info.get("optionable", False),
                "Sector": info.get("sector")
            })
        except Exception:
            pass
    df = pd.DataFrame(results)
    df["MarketCap_Mrd"] = df["MarketCap"] / 1e9
    df["Volume_Mio"] = df["Volume"] / 1e6
    df = df.fillna(0)
    return df

with st.spinner("Lade Daten von Yahoo Finance..."):
    df = load_yf_data(tickers)

# --- Filter anwenden ---
filtered = df[
    (df["MarketCap_Mrd"] >= min_marketcap) &
    (df["Price"] >= min_price) &
    (df["Price"] <= max_price) &
    (df["Volume_Mio"] >= min_volume) &
    (df["PERatio"] > 0) &
    (df["Optionable"] == True) &
    (df["Country"].isin(["United States", "USA", "US"]))
]

st.subheader(f"✅ Gefundene Aktien: {len(filtered)}")
st.dataframe(
    filtered.sort_values("MarketCap_Mrd", ascending=False)[
        ["Ticker", "Name", "Sector", "Price", "MarketCap_Mrd", "Volume_Mio", "PERatio"]
    ],
    use_container_width=True
)
