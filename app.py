import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import os, time
from datetime import datetime
import streamlit.components.v1 as components

# === Seiteneinstellungen ===
st.set_page_config(page_title="Optionsanalyse mit OptionCharts.io", layout="wide")
st.title("📊 S&P 500 Downloader + Optionsanalyse (mit IV & Delta von OptionCharts.io)")

# === Basisdateien ===
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
st.header("📊 Optionsanalyse für ausgewählte Aktien (IV + Delta von OptionCharts.io)")

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

# === Laufzeit-Auswahl ===
st.subheader("2️⃣ Laufzeit")
expiry_input = None
available_expirations = []

if tickers_list:
    first_symbol = tickers_list[0]
    try:
        sample_ticker = yf.Ticker(first_symbol)
        available_expirations = sample_ticker.options
        if available_expirations:
            st.success(f"📅 Verfügbare Laufzeiten für {first_symbol}:")
            expiry_input = st.selectbox(
                "Wähle eine Optionslaufzeit:",
                available_expirations,
                index=min(2, len(available_expirations)-1)
            )
        else:
            expiry_input = st.text_input(
                "Manuelle Eingabe (YYYY-MM-DD):", placeholder="2025-12-19"
            )
    except Exception as e:
        st.warning(f"Fehler beim Abruf: {e}")
else:
    st.info("Bitte gib zuerst deine Ticker ein.")

# === Filter-Einstellungen ===
st.subheader("3️⃣ Filtereinstellungen")
col1, col2 = st.columns(2)
with col1:
    min_rendite = st.number_input("Min. Jahresrendite (%)", 0.0, 100.0, 10.0, step=0.5)
with col2:
    min_sicherheit = st.number_input("Min. Sicherheitsabstand (%)", 0.0, 50.0, 5.0, step=0.5)

# ------------------------------------------------------------
# 🧮 4️⃣ Ergebnisse mit OptionCharts.io
# ------------------------------------------------------------
if tickers_list and expiry_input:
    st.subheader("4️⃣ Ergebnisse")

    expiry_date = datetime.strptime(expiry_input, "%Y-%m-%d").date()

    all_results = []  # Für späteren CSV-Export

    for symbol in tickers_list:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get("regularMarketPrice", None)
            company_name = info.get("shortName", "")

            if not current_price:
                continue

            # --- Daten von OptionCharts.io abrufen ---
            url = f"https://optioncharts.io/api/option_chain?symbol={symbol}&type=put&expiration={expiry_input}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                continue

            data = response.json()
            if not data or not isinstance(data, list):
                continue

            df = pd.DataFrame(data)
            df = df[["strike", "bid", "ask", "impliedVolatility", "delta"]].fillna(0)

            # Kennzahlen berechnen
            df["Sicherheitsabstand_%"] = (current_price - df["strike"]) / current_price * 100
            df["Prämie_$"] = df["bid"] * 100
            df["Resttage"] = (expiry_date - datetime.now().date()).days
            df["Rendite_%_p.a."] = (df["Prämie_$"] / (df["strike"] * 100)) * (365 / df["Resttage"]) * 100

            # Filter & Sortierung
            filtered = df[
                (df["Sicherheitsabstand_%"] >= min_sicherheit) &
                (df["Rendite_%_p.a."] >= min_rendite)
            ].sort_values("strike", ascending=True)

            if filtered.empty:
                continue  # Überspringt leere Ergebnisse

            st.markdown(f"<hr style='border:3px solid #444;margin:20px 0;'>", unsafe_allow_html=True)
            st.markdown(f"### 🟦 {symbol} — {company_name}")
            st.write(f"**Aktueller Kurs:** ${current_price:.2f}")

            # === TradingView Chart ===
            chart_html = f"""
            <div class="tradingview-widget-container" style="height:380px;width:100%;margin-bottom:10px;">
              <div id="tradingview_{symbol.lower()}"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
                new TradingView.widget({{
                  "width": "100%",
                  "height": "380",
                  "symbol": "{symbol}",
                  "interval": "D",
                  "timezone": "Etc/UTC",
                  "theme": "dark",
                  "style": "1",
                  "locale": "en",
                  "hide_side_toolbar": true,
                  "allow_symbol_change": false,
                  "save_image": false,
                  "container_id": "tradingview_{symbol.lower()}"
                }});
              </script>
            </div>
            """
            with st.expander(f"📈 Chart anzeigen ({symbol})", expanded=False):
                components.html(chart_html, height=400)

            # Ausgabe
            filtered["impliedVolatility_%"] = filtered["impliedVolatility"] * 100
            st.dataframe(
                filtered[[
                    "strike", "bid", "ask", "volume" if "volume" in filtered.columns else "bid",
                    "Rendite_%_p.a.", "Sicherheitsabstand_%", "impliedVolatility_%", "delta"
                ]],
                use_container_width=True
            )

            filtered["Symbol"] = symbol
            all_results.append(filtered)

        except Exception as e:
            st.warning(f"Fehler bei {symbol}: {e}")

    # CSV-Export
    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        csv_data = combined.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Gefundene Optionen als CSV exportieren",
            csv_data,
            "filtered_options.csv",
            "text/csv"
        )

else:
    st.info("Bitte gib oben deine Ticker und Laufzeit ein.")
