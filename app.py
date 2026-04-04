import streamlit as st
import pandas as pd
import yfinance as yf
import os, time
from datetime import datetime, timedelta, date
import streamlit.components.v1 as components

# === Seiteneinstellungen ===
st.set_page_config(page_title="S&P 500 Downloader + Optionsanalyse", layout="wide")
st.title("📊 S&P 500 Fundamentaldaten & Optionsanalyse")

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
# 🟩 2️⃣ Bereich: Optionsanalyse & Screening
# ------------------------------------------------------------
st.header("📊 Optionsanalyse für ausgewählte Aktien")

# Initialisiere Session State für die Ergebnisse
if 'options_data' not in st.session_state:
    st.session_state.options_data = None

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

def get_upcoming_fridays(weeks=104):
    today = date.today()
    days_ahead = 4 - today.weekday() 
    if days_ahead < 0:
        days_ahead += 7 
    next_friday = today + timedelta(days=days_ahead)
    return [(next_friday + timedelta(days=7 * i)).strftime("%Y-%m-%d") for i in range(weeks)]

if tickers_list:
    available_expirations = get_upcoming_fridays(104) 
    expiry_input = st.selectbox("Wähle eine Optionslaufzeit (immer Freitags):", available_expirations, index=0)
else:
    st.info("Bitte gib zuerst deine Ticker ein, um verfügbare Laufzeiten zu laden.")
    expiry_input = None

# === Filter-Einstellungen ===
st.subheader("3️⃣ Filtereinstellungen")
col1, col2 = st.columns(2)
with col1:
    min_rendite = st.number_input("Min. Jahresrendite (%)", 0.0, 100.0, 10.0, step=0.5)
with col2:
    min_sicherheit = st.number_input("Min. Sicherheitsabstand (%)", 0.0, 50.0, 5.0, step=0.5)

st.write("") # Abstand
analyze_btn = st.button("🚀 Optionen abrufen & filtern", type="primary", use_container_width=True)

# === Analyse durchführen (Nur bei Button-Klick) ===
if analyze_btn and tickers_list and expiry_input:
    try:
        expiry_date = datetime.strptime(expiry_input, "%Y-%m-%d").date()
    except ValueError:
        st.error("⚠️ Ungültiges Datumsformat.")
        st.stop()

    all_filtered_options = []

    with st.spinner("Lade und berechne Optionsdaten von Yahoo Finance..."):
        for symbol in tickers_list:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                current_price = info.get("regularMarketPrice", None)
                company_name = info.get("shortName", "")
                
                market_cap_raw = info.get("marketCap", 0)
                market_cap_str = f"{market_cap_raw / 1e9:.2f} Mrd. USD" if market_cap_raw else "n/a"

                if not current_price or expiry_input not in ticker.options:
                    continue

                chain = ticker.option_chain(expiry_input)
                puts = chain.puts.copy()
                puts = puts[["strike", "lastPrice", "bid", "ask", "volume", "impliedVolatility"]].fillna(0)

                # Kennzahlen berechnen
                puts["Sicherheitsabstand_%"] = (current_price - puts["strike"]) / current_price * 100
                puts["Prämie_$"] = puts["bid"] * 100
                puts["IV_%"] = puts["impliedVolatility"] * 100  # <--- NEU: IV berechnen
                
                resttage = (expiry_date - datetime.now().date()).days
                resttage_calc = resttage if resttage > 0 else 1

                puts["Rendite_%_p.a."] = ((puts["Prämie_$"] / (puts["strike"] * 100)) * (365 / resttage_calc) * 100)

                # Filtern
                filtered = puts[
                    (puts["Sicherheitsabstand_%"] >= min_sicherheit) &
                    (puts["Rendite_%_p.a."] >= min_rendite)
                ].copy()

                if not filtered.empty:
                    # Metadaten für die Gesamttabelle anhängen
                    filtered.insert(0, "Favorit", False)
                    filtered.insert(1, "Symbol", symbol)
                    filtered.insert(2, "Company", company_name)
                    filtered.insert(3, "Kurs", current_price)
                    filtered.insert(4, "MarketCap", market_cap_str)
                    
                    all_filtered_options.append(filtered.sort_values("strike", ascending=True))

            except Exception as e:
                st.warning(f"Fehler bei {symbol}: {e}")

    # Ergebnisse im Session State speichern
    if all_filtered_options:
        st.session_state.options_data = pd.concat(all_filtered_options, ignore_index=True)
    else:
        st.session_state.options_data = pd.DataFrame()
        st.warning("Keine Optionen gefunden, die deinen Kriterien entsprechen.")


# === Ergebnisse & Interaktive Auswahl anzeigen ===
if st.session_state.options_data is not None and not st.session_state.options_data.empty:
    st.subheader("4️⃣ Ergebnisse & Auswahl")
    st.info("💡 Hake links die Optionen an, die du handeln oder beobachten möchtest. Sie werden unten gesammelt.")

    df_master = st.session_state.options_data
    updated_dfs = []
    symbols_found = df_master['Symbol'].unique()

    for symbol in symbols_found:
        df_sym = df_master[df_master['Symbol'] == symbol].copy()
        company_name = df_sym['Company'].iloc[0]
        current_price = df_sym['Kurs'].iloc[0]
        market_cap_str = df_sym['MarketCap'].iloc[0]

        st.markdown(f"<hr style='border:3px solid #444;margin:20px 0;'>", unsafe_allow_html=True)
        st.markdown(f"### 🟦 {symbol} — {company_name}")

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
              "studies": [
                {{"id": "MASimple@tv-basicstudies", "inputs": {{"length": 50}}}},
                {{"id": "MASimple@tv-basicstudies", "inputs": {{"length": 100}}}},
                {{"id": "MASimple@tv-basicstudies", "inputs": {{"length": 200}}}}
              ],
              "container_id": "tradingview_{symbol.lower()}"
            }});
          </script>
        </div>
        """
        with st.expander(f"📈 Chart anzeigen ({symbol})", expanded=False):
            components.html(chart_html, height=400)

        # OptionCharts Link
        oc_url = f"https://optioncharts.io/options/{symbol}/option-chain?option_type=put&expiration_dates={expiry_input}:m&view=list&strike_range=all"
        
        st.write(f"**Aktueller Kurs:** ${current_price:.2f}  |  **Marktkapitalisierung:** {market_cap_str}")
        st.markdown(f"""
            <a href="{oc_url}" target="_blank" style="
                display: inline-block; padding: 6px 12px; color: white; background-color: #262730;
                border: 1px solid #4e4f55; border-radius: 5px; text-decoration: none;
                font-size: 0.9em; margin-bottom: 10px;">
                🔗 OptionCharts.io Analyse für {symbol} öffnen (für IV-Rank prüfen)
            </a>
        """, unsafe_allow_html=True)

        # === Interaktive Tabelle (Checkbox) ===
        display_cols = ["Favorit", "strike", "bid", "ask", "volume", "IV_%", "Rendite_%_p.a.", "Sicherheitsabstand_%"] # <--- NEU: IV_% hinzugefügt
        
        edited_df = st.data_editor(
            df_sym[display_cols],
            column_config={
                "Favorit": st.column_config.CheckboxColumn("⭐ Auswahl", default=False),
                "strike": st.column_config.NumberColumn("Strike ($)", format="%.2f"),
                "bid": st.column_config.NumberColumn("Bid", format="%.2f"),
                "ask": st.column_config.NumberColumn("Ask", format="%.2f"),
                "IV_%": st.column_config.NumberColumn("IV (%)", format="%.1f"), # <--- NEU: IV Konfiguration
                "Rendite_%_p.a.": st.column_config.NumberColumn("Rendite p.a. (%)", format="%.1f"),
                "Sicherheitsabstand_%": st.column_config.NumberColumn("Sicherheit (%)", format="%.1f"),
            },
            disabled=["strike", "bid", "ask", "volume", "IV_%", "Rendite_%_p.a.", "Sicherheitsabstand_%"],
            hide_index=True,
            key=f"editor_{symbol}",
            use_container_width=True
        )

        # Änderungen in den Datensatz zurückschreiben
        df_sym['Favorit'] = edited_df['Favorit']
        updated_dfs.append(df_sym)

    # Master-Daten aktualisieren
    st.session_state.options_data = pd.concat(updated_dfs, ignore_index=True)

    # ------------------------------------------------------------
    # ⭐ WATCHLIST BEREICH
    # ------------------------------------------------------------
    st.markdown(f"<hr style='border:5px solid #2ecc71;margin:50px 0 20px 0;'>", unsafe_allow_html=True)
    st.header("🎯 Deine selektierten Favoriten")

    favs = st.session_state.options_data[st.session_state.options_data['Favorit'] == True].copy()

    if not favs.empty:
        fav_display = favs[["Symbol", "Company", "strike", "bid", "ask", "IV_%", "Rendite_%_p.a.", "Sicherheitsabstand_%"]] # <--- NEU: IV_% hinzugefügt
        
        st.dataframe(
            fav_display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "strike": st.column_config.NumberColumn("Strike ($)", format="%.2f"),
                "bid": st.column_config.NumberColumn("Bid ($)", format="%.2f"),
                "ask": st.column_config.NumberColumn("Ask ($)", format="%.2f"),
                "IV_%": st.column_config.NumberColumn("IV (%)", format="%.1f"), # <--- NEU: IV Konfiguration
                "Rendite_%_p.a.": st.column_config.NumberColumn("Rendite p.a. (%)", format="%.2f"),
                "Sicherheitsabstand_%": st.column_config.NumberColumn("Sicherheit (%)", format="%.2f"),
            }
        )

        csv_fav = fav_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Watchlist als CSV exportieren",
            data=csv_fav,
            file_name=f"CSP_Watchlist_{expiry_input}.csv",
            mime="text/csv",
            type="primary"
        )
    else:
        st.info("Noch keine Optionen ausgewählt. Setze bei den Ergebnissen oben einen Haken, um sie hier zu sammeln.")
