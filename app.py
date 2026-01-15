import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Optionsanalyse", layout="wide")
st.title("📊 Aktien- & Optionsanalyse Dashboard")

# Eingabefelder
ticker_symbol = st.text_input("Bitte Ticker eingeben (z. B. INTC, AAPL, TSLA):", "INTC")
fee_per_trade = st.number_input("Gebühr pro Handel ($):", min_value=0.0, value=3.5, step=0.5)

# Zustand speichern, um die Laufzeit-Auswahl beizubehalten
if "selected_exp_date" not in st.session_state:
    st.session_state.selected_exp_date = None

if ticker_symbol:
    try:
        ticker = yf.Ticker(ticker_symbol)
        stock_info = ticker.info
        current_price = stock_info.get("currentPrice", None)

        st.subheader("Optionsdaten")

        if current_price:
            company_name = stock_info.get("longName", ticker_symbol.upper())
            pe_ratio = stock_info.get("trailingPE", None)
            day_change = stock_info.get("regularMarketChangePercent", None)
            earnings_date = stock_info.get("earningsDate", None)
            
            # --- NEU: Market Cap abrufen ---
            market_cap = stock_info.get("marketCap", None)

            # Formatierung für Anzeige
            pe_display = f"{pe_ratio:.2f}" if pe_ratio else "—"
            day_change_display = f"{day_change:.2f}%" if day_change else "—"
            if day_change and day_change > 0:
                day_change_display = f"🟢 +{day_change_display}"
            elif day_change and day_change < 0:
                day_change_display = f"🔴 {day_change_display}"

            if isinstance(earnings_date, list) and len(earnings_date) > 0:
                earnings_date_display = earnings_date[0].strftime("%Y-%m-%d")
            elif isinstance(earnings_date, pd.Timestamp):
                earnings_date_display = earnings_date.strftime("%Y-%m-%d")
            else:
                earnings_date_display = "—"

            # --- NEU: Market Cap Formatierung (Mio/Mrd/Bio) ---
            if market_cap:
                if market_cap >= 1e12:
                    market_cap_display = f"{market_cap / 1e12:.2f} Bio. USD"
                elif market_cap >= 1e9:
                    market_cap_display = f"{market_cap / 1e9:.2f} Mrd. USD"
                elif market_cap >= 1e6:
                    market_cap_display = f"{market_cap / 1e6:.2f} Mio. USD"
                else:
                    market_cap_display = f"{market_cap:,.0f} USD"
            else:
                market_cap_display = "—"

            # --- Anzeige erweitert um Market Cap ---
            st.markdown(
                f"""
                **Unternehmen:** {company_name}  
                **Basiswert:** {ticker_symbol.upper()} | **Aktueller Kurs:** {current_price:.2f} USD | **Market Cap:** {market_cap_display}  
                **KGV:** {pe_display} | **Tägliche Veränderung:** {day_change_display} | **Earnings Date:** {earnings_date_display}
                """
            )

        # Ablaufdaten laden
        expirations = ticker.options
        if not expirations:
            st.warning("Keine Optionsdaten für diesen Ticker gefunden.")
        else:
            # Wochen-/Monatsoptionen erkennen
            def classify_option(exp_date):
                d = datetime.strptime(exp_date, "%Y-%m-%d")
                return "📅 Monatsoption" if d.day >= 15 else "🗓️ Wochenoption"

            exp_labels = [f"{exp} ({classify_option(exp)})" for exp in expirations]

            # Falls vorherige Laufzeit verfügbar ist, diese voreinstellen
            default_index = 0
            if st.session_state.selected_exp_date in expirations:
                default_index = expirations.index(st.session_state.selected_exp_date)

            exp_date_label = st.selectbox(
                "Bitte ein Ablaufdatum wählen:",
                exp_labels,
                index=default_index
            )
            exp_date = exp_date_label.split(" ")[0]
            st.session_state.selected_exp_date = exp_date  # Speichern für nächste Auswahl

            # === OptionCharts-Link unterhalb der Auswahl ===
            optioncharts_url = f"https://optioncharts.io/options/{ticker_symbol.upper()}/option-chain?option_type=put&expiration_dates={exp_date}:m&view=list&strike_range=all"
            st.markdown(
                f"🔗 **Direkter Link zur Option Chain:** [OptionCharts.io für {ticker_symbol.upper()} – {exp_date}]({optioncharts_url})",
                unsafe_allow_html=True
            )

            opt_chain = ticker.option_chain(exp_date)
            puts = opt_chain.puts.copy()

            # --- Unnötige Spalten entfernen ---
            cols_to_drop = ["change", "percentChange", "contractSize", "currency", "lastTradeDate"]
            puts = puts.drop(columns=[c for c in cols_to_drop if c in puts.columns])

            # --- Fallback falls kein Bid vorhanden ---
            puts["bid"] = puts["bid"].fillna(puts["lastPrice"])

            # --- Neue Berechnungen (auf Basis Bid-Kurs) ---
            exp_date_obj = datetime.strptime(exp_date, "%Y-%m-%d")
            today = datetime.now()

            puts["Haltedauer (Tage)"] = (exp_date_obj - today).days
            puts["Prämie ($)"] = puts["bid"] * 100
            puts["Nettoprämie ($)"] = puts["Prämie ($)"] - fee_per_trade
            puts["Rendite (%)"] = (puts["Nettoprämie ($)"] / (puts["strike"] * 100 - puts["Prämie ($)"])) * 100
            puts["Jahresrendite (%)"] = (puts["Rendite (%)"] / puts["Haltedauer (Tage)"]) * 365
            puts["Sicherheitspolster (%)"] = ((current_price - puts["strike"]) / current_price) * 100

            # --- Datentypen korrigieren & runden ---
            for col in puts.columns:
                puts[col] = pd.to_numeric(puts[col], errors="ignore")

            numeric_cols = puts.select_dtypes(include=["float", "int"]).columns
            puts[numeric_cols] = puts[numeric_cols].apply(pd.to_numeric, errors="coerce").round(2)

            # --- Farb- und Schrift-Hervorhebung ---
            def highlight_and_style(row):
                if row["strike"] > current_price:
                    bg = "#ffe5e5"  # im Geld
                else:
                    bg = "#e5ffe5"  # aus dem Geld

                styles = []
                for col in puts.columns:
                    base_style = f"background-color: {bg};"
                    if col in ["bid", "Jahresrendite (%)"]:
                        color_style = "color: #b30000; font-size: 1.1em;"
                        if col == "Jahresrendite (%)" and row.get("Jahresrendite (%)", 0) > 10:
                            styles.append(f"{base_style} {color_style} font-weight: bold;")
                        else:
                            styles.append(f"{base_style} {color_style}")
                    else:
                        if row.get("Jahresrendite (%)", 0) > 10:
                            styles.append(f"{base_style} font-weight: bold;")
                        else:
                            styles.append(base_style)
                return styles

            # --- Sortieren nach Strike ---
            puts = puts.sort_values(by="strike", ascending=True)
            styled_df = puts.style.apply(highlight_and_style, axis=1).format(precision=2)

            # --- Tabelle anzeigen ---
            st.subheader(f"📉 Put-Optionen ({exp_date}) – basierend auf BID-Preisen")
            st.dataframe(styled_df, use_container_width=True, height=800)
            st.caption("🟩 Aus dem Geld | 🟥 Im Geld — **fett = >10 % Jahresrendite** | 🔴 Rot = Bid & Rendite")

            # --- Strike-Analyse ---
            st.markdown("---")
            st.subheader("🔍 Strike-Analyse über Laufzeiten")

            target_strike = st.number_input(
                "Strike-Wert für Analyse eingeben:",
                min_value=0.0,
                step=1.0,
                value=0.0,
                format="%.2f"
            )

            if target_strike > 0:
                strike_data = []
                for exp in expirations:
                    try:
                        opt_chain = ticker.option_chain(exp)
                        puts_exp = opt_chain.puts
                        puts_exp["bid"] = puts_exp["bid"].fillna(puts_exp["lastPrice"])
                        exp_date_obj = datetime.strptime(exp, "%Y-%m-%d")
                        days = (exp_date_obj - today).days
                        row = puts_exp.loc[puts_exp["strike"] == target_strike]
                        if not row.empty:
                            bid = row["bid"].values[0]
                            volume = row["volume"].values[0]
                            oi = row["openInterest"].values[0]
                            prem = bid * 100
                            rendite = (prem / (target_strike * 100 - prem)) * 100
                            jahresrendite = (rendite / days) * 365 if days > 0 else 0
                            strike_data.append({
                                "Laufzeit": exp,
                                "Bid": bid,
                                "Jahresrendite (%)": jahresrendite,
                                "Volumen": volume,
                                "Open Interest": oi
                            })
                    except Exception:
                        continue

                if strike_data:
                    df_strike = pd.DataFrame(strike_data).round(2)
                    st.write(f"📅 Renditeübersicht für Strike {target_strike}")
                    st.dataframe(df_strike.set_index("Laufzeit").T, use_container_width=True)
                    st.subheader("📈 Jahresrendite über Laufzeiten")
                    st.line_chart(df_strike.set_index("Laufzeit")["Jahresrendite (%)"])
                else:
                    st.info("Keine passenden Daten für diesen Strike gefunden.")
            else:
                st.caption("Bitte einen Strike-Wert eingeben, um die Analyse zu starten.")

            # ------------------------------------------------
            # 🔹 TradingView Chart Widget (untere Sektion)
            # ------------------------------------------------
            st.markdown("---")
            st.subheader("📊 TradingView Chart")

            # Versuchen, die Börse herauszufinden (z. B. NYSE, NASDAQ)
            exchange = stock_info.get("exchange", "")
            tv_symbol = ticker_symbol.upper()

            # Einige mögliche Fälle abfangen
            if exchange and exchange.upper() in ["NASDAQ", "NYSE", "AMEX"]:
                tv_full_symbol = f"{exchange.upper()}:{tv_symbol}"
            else:
                tv_full_symbol = tv_symbol  # ohne Präfix, damit TradingView selbst entscheidet

            tradingview_html = f"""
            <div class="tradingview-widget-container" style="position:relative; width:100%; min-height:900px; overflow:hidden;">
              <div class="tradingview-widget-container__widget" style="height:100%; width:100%;"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
              {{
              "width": "100%",
              "height": "900",
              "allow_symbol_change": true,
              "calendar": false,
              "details": false,
              "hide_side_toolbar": false,
              "hide_top_toolbar": false,
              "hide_legend": false,
              "hide_volume": false,
              "interval": "D",
              "locale": "en",
              "save_image": true,
              "style": "1",
              "symbol": "{tv_full_symbol}",
              "theme": "light",
              "timezone": "Etc/UTC",
              "backgroundColor": "#ffffff",
              "gridColor": "rgba(46, 46, 46, 0.06)",
              "withdateranges": false,
              "autosize": true
              }}
              </script>
            </div>
            """
            components.html(tradingview_html, height=1000)

            # --- Nach oben springen Button ---
            st.markdown(
                """
                <div style='text-align:center; margin-top:20px;'>
                    <a href='#' style='
                        display:inline-block;
                        background-color:#007bff;
                        color:white;
                        padding:10px 20px;
                        border-radius:8px;
                        text-decoration:none;
                        font-weight:600;
                    '>⬆️ Nach oben</a>
                </div>
                """,
                unsafe_allow_html=True
            )

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
