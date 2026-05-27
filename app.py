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

# === persistenten Speicher für manuelle Eingaben initialisieren ===
if 'raw_options_data' not in st.session_state:
    st.session_state.raw_options_data = None
if 'storage_favoriten' not in st.session_state:
    st.session_state.storage_favoriten = {}
if 'storage_delta' not in st.session_state:
    st.session_state.storage_delta = {}
if 'storage_charts' not in st.session_state:
    st.session_state.storage_charts = {}

# ------------------------------------------------------------
# 🛠️ HILFSFUNKTION: Robuster Earnings-Datum Parser
# ------------------------------------------------------------
def get_robust_earnings_date(ticker_obj, info_dict):
    """Sucht extrem aggressiv über 3 verschiedene Wege nach dem Earnings-Datum."""
    today = date.today()
    
    for key in ['earningsTimestamp', 'earningsTimestampStart']:
        if key in info_dict and info_dict[key]:
            try:
                ts = int(info_dict[key])
                dt = datetime.fromtimestamp(ts).date()
                return dt
            except Exception:
                continue

    try:
        cal = ticker_obj.calendar
        if isinstance(cal, dict) and 'Earnings Date' in cal:
            val = cal['Earnings Date']
            if isinstance(val, list) and len(val) > 0:
                return pd.to_datetime(val[0]).date()
            elif val:
                return pd.to_datetime(val).date()
        elif isinstance(cal, pd.DataFrame) and not cal.empty and 'Earnings Date' in cal.index:
            val = cal.loc['Earnings Date'].iloc[0]
            if isinstance(val, list) and len(val) > 0:
                return pd.to_datetime(val[0]).date()
            else:
                return pd.to_datetime(val).date()
    except Exception:
        pass
        
    return None

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
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    min_rendite = st.number_input("Min. Rendite p.a. (%)", 0.0, 500.0, 12.0, step=0.5)
with col2:
    max_rendite = st.number_input("Max. Rendite p.a. (%)", 0.0, 500.0, 40.0, step=0.5)
with col3:
    min_sicherheit = st.number_input("Min. Sicherheit (%)", 0.0, 100.0, 7.0, step=0.5)
with col4:
    min_strike = st.number_input("Min. Strike ($)", min_value=0.0, value=None, step=5.0, placeholder="Leer = aus")
with col5:
    max_strike = st.number_input("Max. Strike ($)", min_value=0.0, value=None, step=5.0, placeholder="Leer = aus")

st.write("") 
analyze_btn = st.button("🚀 Optionen abrufen & filtern", type="primary", use_container_width=True)

# === SCHRITT A: REINE DATENBESCHAFFUNG (Nur bei Button-Klick) ===
if analyze_btn and tickers_list and expiry_input:
    try:
        expiry_date = datetime.strptime(expiry_input, "%Y-%m-%d").date()
    except ValueError:
        st.error("⚠️ Ungültiges Datumsformat.")
        st.stop()

    if min_rendite > max_rendite:
        st.error("⚠️ Die minimale Rendite kann nicht größer sein als die maximale Rendite.")
        st.stop()
        
    if min_strike is not None and max_strike is not None and min_strike > max_strike:
        st.error("⚠️ Der minimale Strike kann nicht größer sein als der maximale Strike.")
        st.stop()

    all_raw_options = []

    with st.spinner("Lade Optionsdaten von Yahoo Finance..."):
        for symbol in tickers_list:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                current_price = info.get("regularMarketPrice", None)
                company_name = info.get("shortName", "")
                
                market_cap_raw = info.get("marketCap", 0)
                market_cap_str = f"{market_cap_raw / 1e9:.2f} Mrd. USD" if market_cap_raw else "n/a"

                sector = info.get("sector", "N/A")
                industry = info.get("industry", "N/A")
                
                div_rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0
                div_yield_str = f"{(div_rate / current_price) * 100:.2f}%" if (div_rate > 0 and current_price and current_price > 0) else "0.00%"

                earnings_date_val = get_robust_earnings_date(ticker, info)
                earnings_date_str = earnings_date_val.strftime("%Y-%m-%d") if earnings_date_val else "Unbekannt"

                if not current_price or expiry_input not in ticker.options:
                    continue

                chain = ticker.option_chain(expiry_input)
                puts = chain.puts.copy()
                puts = puts[["strike", "lastPrice", "bid", "ask", "volume", "impliedVolatility"]].fillna(0)

                puts["Sicherheitsabstand_%"] = (current_price - puts["strike"]) / current_price * 100
                puts["Prämie_$"] = puts["bid"] * 100
                puts["IV_%"] = puts["impliedVolatility"] * 100 
                
                resttage = (expiry_date - datetime.now().date()).days
                resttage_calc = resttage if resttage > 0 else 1
                puts["Rendite_%_p.a."] = ((puts["Prämie_$"] / (puts["strike"] * 100)) * (365 / resttage_calc) * 100)

                # Strukturierte Rohdaten erstellen
                puts.insert(0, "Symbol", symbol)
                puts.insert(1, "Company", company_name)
                puts.insert(2, "Kurs", current_price)
                puts.insert(3, "MarketCap", market_cap_str)
                puts.insert(4, "Sector", sector)
                puts.insert(5, "Industry", industry)
                puts.insert(6, "DivYield", div_yield_str)
                puts.insert(7, "EarningsDate", earnings_date_str)
                
                all_raw_options.append(puts)

            except Exception as e:
                st.warning(f"Fehler bei {symbol}: {e}")

    if all_raw_options:
        st.session_state.raw_options_data = pd.concat(all_raw_options, ignore_index=True)
    else:
        st.session_state.raw_options_data = pd.DataFrame()
        st.warning("Keine Optionen gefunden, die deinen Kriterien entsprechen.")


# === SCHRITT B: LOKALE DYNAMISCHE FILTERUNG & UI ===
if st.session_state.raw_options_data is not None and not st.session_state.raw_options_data.empty:
    
    df_working = st.session_state.raw_options_data.copy()
    
    # Standard-Filter anwenden
    df_filtered = df_working[
        (df_working["Sicherheitsabstand_%"] >= min_sicherheit) &
        (df_working["Rendite_%_p.a."] >= min_rendite) &
        (df_working["Rendite_%_p.a."] <= max_rendite)
    ]
    
    # Strike-Filter optional anwenden
    if min_strike is not None:
        df_filtered = df_filtered[df_filtered["strike"] >= min_strike]
    if max_strike is not None:
        df_filtered = df_filtered[df_filtered["strike"] <= max_strike]

    if not df_filtered.empty:
        symbols_found = df_filtered['Symbol'].unique()
        anzahl_aktien = len(symbols_found)
        anzahl_optionen = len(df_filtered)

        # Dynamische Überschrift mit KPIs
        st.subheader(f"4️⃣ Ergebnisse & Auswahl ({anzahl_aktien} Aktien, {anzahl_optionen} Optionen gefunden)")
        st.info("💡 Hake links die Optionen an, trag optional ein Delta ein und hinterlege deine Chart-Notizen. Alles wird unten gesammelt.")

        final_processed_dfs = []

        for symbol in symbols_found:
            df_sym = df_filtered[df_filtered['Symbol'] == symbol].copy().sort_values("strike", ascending=True)
            
            company_name = df_sym['Company'].iloc[0]
            current_price = df_sym['Kurs'].iloc[0]
            market_cap_str = df_sym['MarketCap'].iloc[0]
            sector = df_sym['Sector'].iloc[0]
            industry = df_sym['Industry'].iloc[0]
            div_yield = df_sym['DivYield'].iloc[0]
            earnings_date_str = df_sym['EarningsDate'].iloc[0]

            st.markdown(f"<hr style='border:3px solid #444;margin:20px 0;'>", unsafe_allow_html=True)
            st.markdown(f"### 🟦 {symbol} — {company_name}")

            oc_url = f"https://optioncharts.io/options/{symbol}/option-chain?option_type=put&expiration_dates={expiry_input}:m&view=list&strike_range=all"

            # --- HTML Info-Tabelle ---
            info_html = f"""
            <div style="display: flex; flex-wrap: wrap; gap: 10px; background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #d1d5db; margin-bottom: 15px; font-size: 0.95em; text-align: center; color: #111827; align-items: center;">
                <div style="flex: 1; min-width: 100px;">
                    <span style="color: #6b7280; font-size: 0.85em;">Kurs</span><br>
                    <b>${current_price:.2f}</b>
                </div>
                <div style="flex: 1; min-width: 120px;">
                    <span style="color: #6b7280; font-size: 0.85em;">Market Cap</span><br>
                    <b>{market_cap_str}</b>
                </div>
                <div style="flex: 1; min-width: 160px;">
                    <span style="color: #6b7280; font-size: 0.85em;">Sektor / Branche</span><br>
                    <b>{sector}</b><br><span style="font-size: 0.8em; color: #4b5563;">{industry}</span>
                </div>
                <div style="flex: 1; min-width: 100px;">
                    <span style="color: #6b7280; font-size: 0.85em;">Dividende</span><br>
                    <b>{div_yield}</b>
                </div>
                <div style="flex: 1; min-width: 120px;">
                    <span style="color: #6b7280; font-size: 0.85em;">Nächste Earnings</span><br>
                    <b>{earnings_date_str}</b>
                </div>
                <div style="flex: 1; min-width: 180px;">
                    <a href="{oc_url}" target="_blank" style="display: inline-block; padding: 8px 12px; color: white; background-color: #1f2937; border-radius: 5px; text-decoration: none; font-size: 0.85em; width: 100%; box-sizing: border-box; transition: 0.2s;">
                        🔗 IV-Rank prüfen (OptionCharts)
                    </a>
                </div>
            </div>
            """
            st.markdown(info_html, unsafe_allow_html=True)

            # --- TradingView Chart ---
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
                
            # Chartbewertung aus Session State laden / speichern
            current_chart_val = st.session_state.storage_charts.get(symbol, "")
            chart_bewertung = st.text_input(
                f"✍️ Chartanalyse Bewertung für {symbol}:",
                value=current_chart_val,
                key=f"chart_bewertung_{symbol}",
                placeholder="Z.B. Aufwärtstrend intakt, prallt am SMA50 ab..."
            )
            st.session_state.storage_charts[symbol] = chart_bewertung
            df_sym['Chartbewertung'] = chart_bewertung

            # Vorhandene Zustände für Favorit & Delta aus dem persistenten Speicher mappen
            df_sym['Favorit'] = df_sym.apply(lambda r: st.session_state.storage_favoriten.get(f"{symbol}_{r['strike']}", False), axis=1)
            df_sym['Delta'] = df_sym.apply(lambda r: st.session_state.storage_delta.get(f"{symbol}_{r['strike']}", 0.00), axis=1)

            display_cols = ["Favorit", "strike", "bid", "ask", "volume", "IV_%", "Rendite_%_p.a.", "Sicherheitsabstand_%", "Delta"] 
            
            edited_df = st.data_editor(
                df_sym[display_cols],
                column_config={
                    "Favorit": st.column_config.CheckboxColumn("⭐ Auswahl", default=False),
                    "strike": st.column_config.NumberColumn("Strike ($)", format="%.2f"),
                    "bid": st.column_config.NumberColumn("Bid", format="%.2f"),
                    "ask": st.column_config.NumberColumn("Ask", format="%.2f"),
                    "IV_%": st.column_config.NumberColumn("IV (%)", format="%.1f"), 
                    "Rendite_%_p.a.": st.column_config.NumberColumn("Rendite p.a. (%)", format="%.1f"),
                    "Sicherheitsabstand_%": st.column_config.NumberColumn("Sicherheit (%)", format="%.1f"),
                    "Delta": st.column_config.NumberColumn("Delta", format="%.2f", step=0.01),
                },
                disabled=["strike", "bid", "ask", "volume", "IV_%", "Rendite_%_p.a.", "Sicherheitsabstand_%"],
                hide_index=True,
                key=f"editor_{symbol}",
                use_container_width=True
            )

            # Eingaben zeilenweise zurück in den permanenten Speicher schreiben
            for i in range(len(df_sym)):
                strike_val = df_sym.iloc[i]['strike']
                fav_val = edited_df.iloc[i]['Favorit']
                delta_val = edited_df.iloc[i]['Delta']
                
                st.session_state.storage_favoriten[f"{symbol}_{strike_val}"] = fav_val
                st.session_state.storage_delta[f"{symbol}_{strike_val}"] = delta_val

            df_sym['Favorit'] = edited_df['Favorit'].values
            df_sym['Delta'] = edited_df['Delta'].values
            
            final_processed_dfs.append(df_sym)

        # Zusammenfassung aller modifizierten DataFrames
        st.session_state.options_data = pd.concat(final_processed_dfs, ignore_index=True)
    else:
        st.warning("Keine Optionen entsprechen deinen aktuellen Filtereinstellungen. Passe die Regler an.")


# ------------------------------------------------------------
# ⭐ WATCHLIST BEREICH
# ------------------------------------------------------------
if st.session_state.options_data is not None and not st.session_state.options_data.empty:
    st.markdown(f"<hr style='border:5px solid #2ecc71;margin:50px 0 20px 0;'>", unsafe_allow_html=True)
    st.header("🎯 Deine selektierten Favoriten")

    favs = st.session_state.options_data[st.session_state.options_data['Favorit'] == True].copy()

    if not favs.empty:
        fav_display = favs[["Symbol", "Company", "strike", "bid", "ask", "IV_%", "Rendite_%_p.a.", "Sicherheitsabstand_%", "Delta", "EarningsDate", "DivYield", "Chartbewertung"]] 
        
        st.dataframe(
            fav_display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "strike": st.column_config.NumberColumn("Strike ($)", format="%.2f"),
                "bid": st.column_config.NumberColumn("Bid ($)", format="%.2f"),
                "ask": st.column_config.NumberColumn("Ask ($)", format="%.2f"),
                "IV_%": st.column_config.NumberColumn("IV (%)", format="%.1f"),
                "Rendite_%_p.a.": st.column_config.NumberColumn("Rendite p.a. (%)", format="%.2f"),
                "Sicherheitsabstand_%": st.column_config.NumberColumn("Sicherheit (%)", format="%.2f"),
                "Delta": st.column_config.NumberColumn("Delta", format="%.2f"),
                "EarningsDate": st.column_config.TextColumn("Earnings am"),
                "DivYield": st.column_config.TextColumn("Dividende"),
                "Chartbewertung": st.column_config.TextColumn("Chartbewertung"), 
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
