import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.set_page_config(page_title="S&P 500 Aktien Screener", layout="wide")
st.title("📊 S&P 500 Aktien Screener")

# === Parameter-Filter (veränderbar durch Benutzer) ===
st.sidebar.header("Filtereinstellungen")
min_marketcap = st.sidebar.number_input("Min. Market Cap (in Mrd $)", 0.5, 1000.0, 2.0, step=0.5)
min_price = st.sidebar.number_input("Min. Preis ($)", 1, 500, 20)
max_price = st.sidebar.number_input("Max. Preis ($)", 1, 1000, 70)
min_volume = st.sidebar.number_input("Min. Ø Volumen (in Mio)", 0.1, 100.0, 1.0, step=0.1)

st.write("🧭 Suche nach Aktien mit:")
st.write(f"- Market Cap > {min_marketcap} Mrd $  \n"
         f"- Preis zwischen {min_price} $ und {max_price} $  \n"
         f"- Ø Volumen > {min_volume} Mio  \n"
         f"- Land = USA  \n"
         f"- Optionable = True  \n"
         f"- KGV > 0")

# === Lade S&P500 Tickers aus lokaler CSV ===
@st.cache_data
def load_sp500_list():
    df = pd.read_csv("SP500.csv")
    return df["Symbol"].tolist(), df

tickers, sp500_df = load_sp500_list()
st.success(f"{len(tickers)} S&P 500 Aktien geladen.")

# === Hole Finanzdaten ===
@st.cache_data(show_spinner=False)
def get_stock_info(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "Ticker": ticker,
            "Name": info.get("shortName"),
            "Country": info.get("country"),
            "MarketCap": info.get("marketCap", 0),
            "MarketCap_Mrd": (info.get("marketCap", 0) / 1e9) if info.get("marketCap") else 0,
            "Price": info.get("regularMarketPrice"),
            "Volume": info.get("averageVolume", 0),
            "Volume_Mio": (info.get("averageVolume", 0) / 1e6) if info.get("averageVolume") else 0,
            "PERatio": info.get("trailingPE", 0),
            "Optionable": info.get("optionable", False),
            "Sector": info.get("sector"),
        }
    except Exception:
        return None

progress = st.progress(0)
data = []
for i, t in enumerate(tickers):
    info = get_stock_info(t)
    if info:
        data.append(info)
    progress.progress((i+1)/len(tickers))
    time.sleep(0.05)  # leicht bremsen, um API-Rate-Limits zu vermeiden

df = pd.DataFrame(data)

# === Filter anwenden ===
filtered = df[
    (df["MarketCap_Mrd"] >= min_marketcap) &
    (df["Price"] >= min_price) &
    (df["Price"] <= max_price) &
    (df["Volume_Mio"] >= min_volume) &
    (df["Country"] == "United States") &
    (df["Optionable"] == True) &
    (df["PERatio"] > 0)
]

# === Ergebnis anzeigen ===
st.subheader(f"✅ Gefundene Aktien: {len(filtered)}")
st.dataframe(
    filtered.sort_values("MarketCap_Mrd", ascending=False)[
        ["Ticker", "Name", "Sector", "Price", "MarketCap_Mrd", "Volume_Mio", "PERatio"]
    ],
    use_container_width=True
)

# === Download-Option ===
csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Ergebnisse als CSV herunterladen",
    data=csv,
    file_name="SP500_filtered.csv",
    mime="text/csv",
)
