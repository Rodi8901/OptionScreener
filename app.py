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

# === Laufzeit-Auswahl ===
st.subheader("2️⃣ Laufzeit")

available_expirations = []
if tickers_list:
    # Hole die Expirations vom ersten Ticker (alle haben meist gleiche Standarddaten)
    try:
        sample_ticker = yf.Ticker(tickers_list[0])
        available_expirations = sample_ticker.options
    except Exception as e:
        st.warning(f"Konnte keine Laufzeiten abrufen: {e}")

if available_expirations:
    expiry_input = st.selectbox("Wähle eine Laufzeit:", available_expirations, index=min(2, len(available_expirations)-1))
else:
    expiry_input = st.text_input("Kein automatisches Datum verfügbar – manuell eingeben (YYYY-MM-DD):", placeholder="2025-12-19")

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

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get("regularMarketPrice", None)
            company_name = info.get("shortName", "")

            st.markdown(f"### 🟦 {symbol} — {company_name}")

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
