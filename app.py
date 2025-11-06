import streamlit as st
import pandas as pd
import yfinance as yf
import os, time

# === Seiteneinstellungen ===
st.set_page_config(page_title="S&P 500 Aktien Screener", layout="wide")
st.title("📊 S&P 500 Aktien Screener")

# === Sidebar Filter ===
st.sidebar.header("Filtereinstellungen")
min_marketcap = st.sidebar.number_input("Min. Market Cap (Mrd $)", 0.5, 1000.0, 2.0, step=0.5)
min_price = st.sidebar.number_input("Min. Preis ($)", 1, 500, 20)
max_price = st.sidebar.number_input("Max. Preis ($)", 1, 1000, 70)
min_volume = st.sidebar.number_input("Min. Ø Volumen (Mio)", 0.1, 100.0, 1.0, step=0.1)

# === Dateipfade ===
base_path = os.path.dirname(__file__)
sp500_path = os.path.join(base_path, "sp500.csv")
data_path = os.path.join(base_path, "sp500_data.csv")

# === S&P500-Liste laden ===
def load_sp500_list():
    if not os.path.exists(sp500_path):
        st.error("❌ Datei 'sp500.csv' fehlt im Projektordner!")
        st.stop()
    df = pd.read_csv(sp500_path)
    df.columns = [c.strip() for c in df.columns]
    return df

sp500_df = load_sp500_list()
tickers = sp500_df["Symbol"].tolist()

# Für Tests: Begrenze Anzahl (z. B. 50)
# tickers = tickers[:50]

# === Funktion: Daten-Update von Yahoo Finance ===
def update_sp500_data():
    rows = []
    st.info("⏳ Lade Echtzeitdaten von Yahoo Finance... (dies kann einige Minuten dauern)")
    progress = st.progress(0)

    for i, t in enumerate(tickers):
        try:
            ticker_obj = yf.Ticker(t)
            info = ticker_obj.info or {}
            hist = ticker_obj.history(period="1d")

            price, volume = 0, 0

            # Primäre Quelle: history()
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                volume = float(hist["Volume"].iloc[-1])

            # Fallbacks aus info
            if price == 0:
                price = info.get("regularMarketPrice", 0)
            if volume == 0:
                volume = info.get("averageVolume", 0)

            rows.append({
                "Symbol": t,
                "Price": round(price, 2) if price else 0,
                "MarketCap_Mrd": (info.get("marketCap", 0) / 1e9) if info.get("marketCap") else 0,
                "Volume_Mio": round((volume / 1e6), 2) if volume else 0,
                "PERatio": info.get("trailingPE", 0),
                "Country": info.get("country", ""),
                "Optionable": info.get("optionable", False)
            })

        except Exception as e:
            print(f"Fehler bei {t}: {e}")
        progress.progress((i + 1) / len(tickers))
        time.sleep(0.05)  # kleine Pause, um API-Limit zu schonen

    df = pd.DataFrame(rows)
    df.to_csv(data_path, index=False)
    st.success(f"✅ {len(df)} Aktien-Datensätze erfolgreich gespeichert in 'sp500_data.csv'")
    st.dataframe(df.head())
    return df

# === Button: Daten-Update starten ===
if st.button("📦 Daten aktualisieren"):
    with st.spinner("Aktualisiere Daten..."):
        update_sp500_data()

# === CSV-Daten immer frisch laden (ohne Cache) ===
if not os.path.exists(data_path):
    st.warning("⚠️ Noch keine Datei 'sp500_data.csv' gefunden. Bitte zuerst 'Daten aktualisieren' klicken.")
    st.stop()

try:
    data_df = pd.read_csv(data_path)
except Exception as e:
    st.error(f"❌ Fehler beim Laden der Daten: {e}")
    st.stop()

# === Rohdaten-Vorschau ===
with st.expander("🔍 Rohdaten anzeigen"):
    st.write(data_df.head())

# === Filter anwenden ===
filtered = data_df[
    (data_df["MarketCap_Mrd"] >= min_marketcap) &
    (data_df["Price"] >= min_price) &
    (data_df["Price"] <= max_price) &
    (data_df["Volume_Mio"] >= min_volume) &
    (data_df["PERatio"] > 0) &
    (data_df["Country"].isin(["United States", "USA", "US"])) &
    (data_df["Optionable"] == True)
]

# === Ergebnis anzeigen ===
st.subheader(f"✅ Gefundene Aktien: {len(filtered)}")

if len(filtered) > 0:
    st.dataframe(
        filtered.sort_values("MarketCap_Mrd", ascending=False)[
            ["Symbol", "Price", "MarketCap_Mrd", "Volume_Mio", "PERatio", "Country"]
        ],
        use_container_width=True
    )
else:
    st.info("Keine Aktien erfüllen aktuell die Filterbedingungen.")

# === Download-Button ===
if len(filtered) > 0:
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Ergebnisse als CSV herunterladen",
        data=csv,
        file_name="sp500_filtered.csv",
        mime="text/csv",
    )
