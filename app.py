import streamlit as st
import pandas as pd
import yfinance as yf
import os, time
from datetime import datetime

# === Seiteneinstellungen ===
st.set_page_config(page_title="S&P 500 Downloader + Optionsanalyse", layout="wide")
st.title("📊 S&P 500 Fundamentaldaten & Optionsanalyse")

# === Basisdatei ===
base_path = os.path.dirname(__file__)
sp500_path = os.path.join(base_path, "sp500.csv")
data_path = os.path.join(base_path, "sp500_data.csv")

# ------------------------------------------------------------
# 🟦 1️⃣ Bereich: Fundamentaldaten-Downloader
# ------------------------------------------------------------
st.header("📥 S&P 500 Fundamentaldaten herunterladen")

def load_sp500_list():
    if not os.path.exists(sp500_path):
        st.error("❌ Datei 'sp500.csv' fehlt im Projektordner!")
        st.stop()
    df = pd.read_csv(sp500_path)
    df.columns = [c.strip() for c in df.columns]
    return df

sp500_df = load_sp500_list()
tickers = sp500_df["Symbol"].tolist()
st.write(f"🔹 {len(tickers)} S&P 500 Aktien gefunden.")

# Testweise begrenzen (optional)
# tickers = tickers[:30]

def download_yf_data(tickers):
    results = []
    progress = st.progress(0)
    status = st.empty()
    for i, t in enumerate(tickers):
        try:
            ticker_obj = yf.Ticker(t)
            info = ticker_obj.info or {}
            hist = ticker_obj.history(period="1d")

            price, volume = 0, 0
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
    return pd.DataFrame(results)

if st.button("📦 Daten jetzt von Yahoo Finance laden"):
    with st.spinner("Lade Fundamentaldaten..."):
        df = download_yf_data(tickers)
        if not df.empty:
            st.success(f"✅ {len(df)} Datensätze geladen!")
            st.dataframe(df.head())
            df.to_csv(data_path, index=False)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Fundamentaldaten als CSV exportieren",
                data=csv,
                file_name="sp500_data.csv",
                mime="text/csv",
            )
        else:
            st.warning("⚠️ Keine Daten erhalten. Bitte erneut versuchen.")

st.markdown("---")

# ------------------------------------------------------------
# 🟩 2️⃣ Bereich: Optionsanalyse
# ------------------------------------------------------------
st.header("📊 Optionsanalyse für ausgewählte Aktien")

# === Eingabe der Ticker ===
st.subheader("1️⃣ Aktienauswahl")
tickers_input = st.text_area(
    "Füge hier deine Ticker ein (jeweils in neuer Zeile, z. B. aus Excel):",
    placeholder="AAPL\nAMD\nMSFT\nGOOGL"
)
if tickers_input.strip():
    tickers_list = [t.strip().upper() for t in tickers_input.splitlines() if t.strip()]
else:
    tickers_list = []

# === Laufzeit ===
st.subheader("2️⃣ Laufzeit")
expiry_input = st.text_input(
    "Gib das gewünschte Ablaufdatum ein (YYYY-MM-DD):",
    placeholder="2025-12-19"
)

# === Filter-Einstellungen ===
st.subheader("3️⃣ Filtereinstellungen")
col1, col2 = st.columns(2)
with col1:
    min_rendite = st.number_input("Min. Jahresrendite (%)", 0.0, 100.0, 10.0, step=0.5)
with col2:
    min_sicherheit = st.number_input("Min. Sicherheitsabstand (%)", 0.0, 50.0, 5.0, step=0.5)

# === Analyse starten ===
if tickers_list and expiry_input:
    st.subheader("4️⃣ Ergebnisse")

    try:
        expiry_date = datetime.strptime(expiry_input, "%Y-%m-%d").date()
    except ValueError:
        st.error("⚠️ Ungültiges Datumsformat. Bitte YYYY-MM-DD verwenden.")
        st.stop()

    for symbol in tickers_list:
        st.markdown(f"<hr style='border:3px solid #444;margin:20px 0;'>", unsafe_allow_html=True)
        st.markdown(f"### 🟦 {symbol}")

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get("regularMarketPrice", None)

            if not current_price:
                st.warning(f"Keine Kursdaten für {symbol} gefunden.")
                continue

            if expiry_input not in ticker.options:
                st.warning(f"{symbol}: Kein Verfall am {expiry_input} verfügbar. Verfügbare Termine: {ticker.options}")
                continue

            chain = ticker.option_chain(expiry_input)
            puts = chain.puts.copy()
            puts = puts[["strike", "lastPrice", "bid", "ask", "volume", "impliedVolatility"]].fillna(0)
            puts["mid"] = (puts["bid"] + puts["ask"]) / 2

            # --- Kennzahlen ---
            puts["Sicherheitsabstand_%"] = (current_price - puts["strike"]) / current_price * 100
            puts["Prämie_$"] = puts["bid"] * 100
            puts["Resttage"] = (expiry_date - datetime.now().date()).days
            puts["Rendite_%_p.a."] = (puts["Prämie_$"] / (puts["strike"] * 100)) * (365 / puts["Resttage"]) * 100

            # --- Filter ---
            filtered = puts[
                (puts["Sicherheitsabstand_%"] >= min_sicherheit) &
                (puts["Rendite_%_p.a."] >= min_rendite)
            ].sort_values("Rendite_%_p.a.", ascending=False)

            if filtered.empty:
                st.info(f"Keine passenden Puts für {symbol} gefunden (nach deinen Kriterien).")
                continue

            st.write(f"**Aktueller Kurs:** ${current_price:.2f}")
            st.dataframe(
                filtered[["strike", "bid", "ask", "volume", "Sicherheitsabstand_%", "Rendite_%_p.a."]],
                use_container_width=True
            )

        except Exception as e:
            st.warning(f"Fehler bei {symbol}: {e}")

else:
    st.info("Bitte gib oben deine Ticker und das Ablaufdatum ein, um die Analyse zu starten.")
