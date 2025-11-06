import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# === Seiteneinstellungen ===
st.set_page_config(page_title="Optionsanalyse", layout="wide")
st.title("📊 Optionsanalyse ausgewählter Aktien (Puts)")

# === Eingabe der Ticker ===
st.subheader("1️⃣ Aktienauswahl")
tickers_input = st.text_area(
    "Füge hier deine Ticker ein (z. B. aus Excel kopiert, jeweils in einer neuen Zeile):",
    placeholder="AAPL\nAMD\nMSFT\nGOOGL"
)

if tickers_input.strip():
    tickers = [t.strip().upper() for t in tickers_input.splitlines() if t.strip()]
else:
    tickers = []

# === Auswahl der Laufzeit ===
st.subheader("2️⃣ Laufzeit")
expiry_input = st.text_input(
    "Gib das gewünschte Ablaufdatum ein (Format: YYYY-MM-DD, z. B. 2025-12-19):",
    placeholder="2025-12-19"
)

if tickers and expiry_input:
    st.subheader("3️⃣ Ergebnisse")

    try:
        expiry_date = datetime.strptime(expiry_input, "%Y-%m-%d").date()
    except ValueError:
        st.error("⚠️ Ungültiges Datumsformat. Bitte YYYY-MM-DD verwenden.")
        st.stop()

    # === Für jede Aktie die Option Chain abrufen ===
    for symbol in tickers:
        st.markdown(f"<hr style='border:3px solid #333; margin:20px 0;'>", unsafe_allow_html=True)
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

            # === Kennzahlen berechnen ===
            puts["Sicherheitsabstand_%"] = (current_price - puts["strike"]) / current_price * 100
            puts["Prämie_$"] = puts["bid"] * 100
            puts["Resttage"] = (expiry_date - datetime.now().date()).days
            puts["Rendite_%_p.a."] = (puts["Prämie_$"] / (puts["strike"] * 100)) * (365 / puts["Resttage"]) * 100

            # === Filter: nur attraktive Puts ===
            filtered = puts[
                (puts["Sicherheitsabstand_%"] >= 5) &
                (puts["Rendite_%_p.a."] >= 10)
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
    st.info("Bitte gib oben deine Ticker und ein Ablaufdatum ein, um die Analyse zu starten.")
