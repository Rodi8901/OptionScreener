import streamlit as st
import pandas as pd
import yfinance as yf
import os, time

# === Seiteneinstellungen ===
st.set_page_config(page_title="S&P 500 Fundamentaldaten Downloader", layout="wide")
st.title("📊 S&P 500 Fundamentaldaten Downloader")

# === Dateipfade ===
base_path = os.path.dirname(__file__)
sp500_path = os.path.join(base_path, "sp500.csv")

# === S&P 500 Liste laden ===
def load_sp500_list():
    if not os.path.exists(sp500_path):
        st.error("❌ Datei 'sp500.csv' fehlt im Projektordner!")
        st.stop()
    df = pd.read_csv(sp500_path)
    df.columns = [c.strip() for c in df.columns]
    return df

sp500_df = load_sp500_list()
tickers = sp500_df["Symbol"].tolist()

# --- Für Tests nur begrenzte Anzahl laden ---
# tickers = tickers[:30]

st.write(f"🔹 {len(tickers)} Aktien in der S&P 500-Liste gefunden.")

# === Funktion: Daten laden ===
def download_yf_data(tickers):
    results = []
    progress = st.progress(0)
    status = st.empty()

    for i, t in enumerate(tickers):
        try:
            ticker_obj = yf.Ticker(t)
            info = ticker_obj.info or {}
            hist = ticker_obj.history(period="1d")

            price = 0
            volume = 0

            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                volume = float(hist["Volume"].iloc[-1])

            if price == 0:
                price = info.get("regularMarketPrice", 0)
            if volume == 0:
                volume = info.get("averageVolume", 0)

            results.append({
                "Symbol": t,
                "Name": info.get("shortName", ""),
                "MarketCap_Mrd": round((info.get("marketCap", 0) / 1e9), 2) if info.get("marketCap") else 0,
                "Price": round(price, 2),
                "Volume_Mio": round(volume / 1e6, 2),
                "PERatio": info.get("trailingPE", 0),
                "Sector": info.get("sector", "")
            })
        except Exception as e:
            print(f"Fehler bei {t}: {e}")

        progress.progress((i + 1) / len(tickers))
        status.text(f"{i+1}/{len(tickers)} Aktien verarbeitet…")
        time.sleep(0.05)

    df = pd.DataFrame(results)
    return df

# === Button: Daten abrufen ===
if st.button("📦 Daten jetzt von Yahoo Finance laden"):
    with st.spinner("Lade Daten von Yahoo Finance..."):
        df = download_yf_data(tickers)
        if not df.empty:
            st.success(f"✅ {len(df)} Datensätze erfolgreich geladen!")
            st.dataframe(df.head())

            # --- CSV speichern ---
            csv_path = os.path.join(base_path, "sp500_data.csv")
            df.to_csv(csv_path, index=False)
            st.info(f"📁 Datei gespeichert unter: {csv_path}")

            # --- Download-Button ---
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Daten als CSV exportieren",
                data=csv,
                file_name="sp500_data.csv",
                mime="text/csv",
            )
        else:
            st.warning("⚠️ Keine Daten erhalten. Bitte erneut versuchen.")

else:
    st.info("Klicke auf den Button oben, um die aktuellen Fundamentaldaten herunterzuladen.")
