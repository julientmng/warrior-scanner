import asyncio, os
import pandas as pd
import streamlit as st
from live_engine import run_live, discover_symbols_only
from webull_engine import WebullScanner
from news_float import news_for, float_map, get_float
from criteria import evaluate
from stream_monitor import monitor_stream

st.set_page_config(page_title="Warrior Momentum Scanner", page_icon="📈", layout="wide")
st.title("Warrior Momentum Scanner — v6")
st.caption("US + TSX/TSXV • candidate discovery • provider routing • time-of-day RVOL • catalyst review • float provenance")
if "auto_refresh" in st.session_state and st.session_state.get("auto_refresh"):
    try:
        from streamlit_autorefresh import st_autorefresh
        secs = {"15 seconds": 15000, "30 seconds": 30000, "60 seconds": 60000}.get(st.session_state.get("refresh_interval"), 30000)
        st_autorefresh(interval=secs, key="scanner_refresh_timer")
    except Exception:
        st.warning("Install streamlit-autorefresh to enable periodic refresh.")
with st.sidebar:
    st.header("Data provider")
    provider = st.selectbox("Market-data provider", ["IBKR", "Webull", "Automatic"], index=0)
    st.caption("IBKR discovery is available; Webull mode queries user-supplied US symbols via the official SDK.")
    if True:  # IBKR settings are also needed for Webull candidate discovery
        st.subheader("IBKR connection")
        ib_host = st.text_input("Host", value=os.getenv("IBKR_HOST", "127.0.0.1"))
        ib_port = st.number_input("TWS / Gateway port", min_value=1, max_value=65535, value=int(os.getenv("IBKR_PORT", "7497")))
        ib_client = st.number_input("Client ID", min_value=1, max_value=9999, value=int(os.getenv("IBKR_CLIENT_ID", "17")))
    if provider in ("Webull", "Automatic"):
        st.subheader("Webull OpenAPI")
        webull_region = st.selectbox("API region", ["US", "Other / not configured"], index=0)
        webull_key = st.text_input("App Key", value="", type="password")
        webull_secret = st.text_input("App Secret", value="", type="password")
        webull_environment = st.selectbox("Environment", ["Production", "Sandbox"], index=0)
        discovery_mode = st.selectbox("Candidate universe", ["Discover market movers automatically", "Use ticker list"], index=0, help="Automatic discovery uses the IBKR scanner as a discovery source; Webull then fetches its own historical bars for US candidates.")
        webull_symbols = st.text_area("US tickers to query (comma-separated)", value="AAPL, NVDA, TSLA", help="Used only when Candidate universe is set to Use ticker list.")
        st.caption("Webull data requires OpenAPI credentials and the relevant market-data entitlement.")
    st.divider()
    st.header("Scan options")
    markets = st.multiselect("Markets", ["US", "TSX", "TSXV"], default=["US", "TSX", "TSXV"])
    session_filter = st.selectbox("Session", ["All available", "Premarket", "Regular", "After-hours"])
    refresh_interval = st.selectbox("Refresh interval", ["Manual", "15 seconds", "30 seconds", "60 seconds"], index=0, help="Automatic refresh reruns the scan when enabled below.")
    monitor_duration = st.selectbox("Streaming monitor window", ["30 seconds", "60 seconds", "90 seconds", "180 seconds"], index=2)
    sample_interval = st.selectbox("Stream sampling", ["1 second", "2 seconds", "5 seconds"], index=1)
    auto_refresh = st.checkbox("Repeat scan automatically", False, help="This reruns provider requests and may consume API quotas or market-data capacity.")
    st.header("Five criteria")
    min_change=st.number_input("Minimum change (%)",-99.0,500.0,10.0,1.0)
    min_rvol=st.number_input("Minimum time-of-day RVOL (×)",0.0,100.0,5.0,.5)
    min_price=st.number_input("Minimum price",.01,100000.0,2.0,.5)
    max_price=st.number_input("Maximum price",.01,100000.0,20.0,1.0)
    max_float=st.number_input("Maximum float (millions)",.1,10000.0,20.0,1.0)
    news_hours=st.slider("News lookback (hours)",1,168,48)
    require_news=st.checkbox("Require verified catalyst",True)
    require_float=st.checkbox("Require verified float",False)
    max_candidates=st.slider("Candidates to quote",5,50,20,5)

st.session_state["auto_refresh"] = auto_refresh
st.session_state["refresh_interval"] = refresh_interval

c1,c2,c3=st.columns(3)
c1.metric("Selected provider", provider)
c2.metric("Selected markets", ", ".join(markets) if markets else "None")
c3.metric("Connection status", "Not tested")
if provider == "Webull":
    if any(m != "US" for m in markets): st.warning("Webull adapter currently supports US tickers only. Select US only or use IBKR for TSX/TSXV.")
elif provider == "Automatic":
    st.info("Automatic mode uses IBKR for discovery/quotes on US + Canadian listings. Webull mode can use IBKR candidate discovery then Webull historical bars for US candidates.")
else:
    st.info("IBKR requires TWS / IB Gateway and the appropriate market-data permissions.")

if "rows" not in st.session_state: st.session_state.rows=[]
if "error" not in st.session_state: st.session_state.error=""
scan_col, stream_col = st.columns(2)
run_scan = scan_col.button("Run live scan", type="primary", disabled=(not markets or (provider=="Webull" and (set(markets)!={"US"} or not webull_key or not webull_secret))))
run_stream = stream_col.button("Start IBKR streaming monitor", disabled=(not markets or provider=="Webull"))
if run_stream:
    with st.spinner(f"Subscribing to IBKR quotes for {monitor_duration}… keep this page open."):
        os.environ["IBKR_HOST"] = str(ib_host)
        stream_result = asyncio.run(monitor_stream(str(ib_host), int(ib_port), int(ib_client)+1, int(monitor_duration.split()[0]), max_candidates, int(sample_interval.split()[0]), markets))
    if not stream_result.get("ok"):
        st.error("Streaming monitor failed: " + stream_result.get("error", "Unknown error"))
    else:
        st.success(f"Streaming window complete. Subscribed candidate count: {stream_result.get('count', 0)}")
        st.caption(stream_result.get("note", ""))
        if stream_result.get("alerts"):
            st.warning(f"{len(stream_result['alerts'])} threshold-crossing alert(s). These are preliminary alerts, not fully qualified five-criteria signals.")
            st.dataframe(pd.DataFrame(stream_result["alerts"]), use_container_width=True, hide_index=True)
        else:
            st.info("No price-threshold alerts occurred during this monitoring window.")
        if stream_result.get("latest"):
            st.subheader("Latest streaming snapshots")
            st.dataframe(pd.DataFrame(stream_result["latest"]), use_container_width=True, hide_index=True)
        if stream_result.get("snapshots"):
            st.download_button("Download streaming samples CSV", pd.DataFrame(stream_result["snapshots"]).to_csv(index=False), "warrior_stream_samples.csv", "text/csv")
if run_scan or auto_refresh:
    if provider == "Webull":
        try:
            with st.spinner("Connecting to Webull OpenAPI and requesting US market bars…"):
                client=WebullScanner(webull_key, webull_secret, webull_environment)
                client.test_connection()
                if discovery_mode == "Discover market movers automatically":
                    os.environ["IBKR_HOST"] = str(ib_host)
                    os.environ["IBKR_PORT"] = str(int(ib_port))
                    os.environ["IBKR_CLIENT_ID"] = str(int(ib_client))
                    discovery = asyncio.run(discover_symbols_only())
                    if not discovery["ok"]:
                        raise RuntimeError("IBKR candidate discovery failed: " + discovery["error"])
                    symbols = list(dict.fromkeys(r["symbol"] for r in discovery["rows"] if r.get("currency") == "USD"))[:max_candidates]
                    if not symbols:
                        raise RuntimeError("IBKR discovery returned no US candidates. Check IBKR connection and scanner permissions.")
                    result={"ok":True,"count":discovery["count"],"rows":client.scan_symbols(symbols)}
                else:
                    symbols=list(dict.fromkeys(x.strip().upper() for x in webull_symbols.replace("\n",",").split(",") if x.strip()))[:max_candidates]
                    result={"ok":True,"count":len(symbols),"rows":client.scan_symbols(symbols)}
        except Exception as e:
            result={"ok":False,"error":str(e),"rows":[],"count":0}
    else:
        os.environ["IBKR_HOST"] = str(ib_host)
        os.environ["IBKR_PORT"] = str(int(ib_port))
        os.environ["IBKR_CLIENT_ID"] = str(int(ib_client))
        with st.spinner("Connecting to IBKR and requesting candidate bars…"):
            result=asyncio.run(run_live(max_candidates))
    if not result["ok"]:
        st.session_state.error=result["error"]; st.session_state.rows=[]
    else:
        st.session_state.error=""
        floats=float_map(); output=[]
        for row in result["rows"]:
            if "Error" in row: output.append(row); continue
            if session_filter != "All available" and row.get("Session") != session_filter: continue
            news=news_for(row["Ticker"],news_hours); flt=get_float(row["Ticker"],floats)
            score=evaluate(row.get("Change %"),row.get("Time-of-day RVOL"),news.get("verified"), row.get("Price"),flt.get("shares"),min_change,min_rvol,min_price,max_price,int(max_float*1_000_000),require_news,require_float)
            row.pop("_bars",None)
            output.append({**row,"Float (M)":flt["shares"]/1_000_000 if flt.get("shares") is not None else None,"Float verified":flt["verified"],"Float source":flt["source"],"Float date":flt["date"],"Catalyst":news["headline"],"News source":news["source"],"News published UTC":news["published"],"News URL":news["url"],"Catalyst status":news["status"],"Criteria passed":score["passed"],"Unknown criteria":score["unknown"],"All 5 pass":score["all_five"],"Eligible":score["eligible"],**score["pillars"]})
        st.session_state.rows=output; st.session_state.discovered=result["count"]
if st.session_state.error:
    st.error("Provider error: "+st.session_state.error)
    st.write("Check credentials, API environment, market-data entitlements, and connection settings.")
rows=st.session_state.rows
if rows:
    df=pd.DataFrame(rows)
    st.metric("Candidates discovered before quote limit",st.session_state.get("discovered",len(rows)))
    if "Eligible" in df:
        a,b,c=st.columns(3); a.metric("Quoted",len(df)); b.metric("All five pass",int(df["All 5 pass"].fillna(False).sum())); c.metric("Eligible",int(df["Eligible"].fillna(False).sum()))
    if "Criteria passed" in df: df=df.sort_values(["Eligible","Criteria passed","Time-of-day RVOL"],ascending=[False,False,False],na_position="last")
    st.dataframe(df,use_container_width=True,hide_index=True,column_config={"News URL":st.column_config.LinkColumn("News URL")})
    st.download_button("Download CSV",df.to_csv(index=False),"warrior_scan.csv","text/csv")
else: st.info("Choose IBKR or Automatic (currently IBKR-backed), then click Run live scan.")
with st.expander("Setup / limitations",expanded=True):
    st.markdown("""
- **IBKR:** install TWS or IB Gateway, enable socket clients, and subscribe to relevant market data. Confirm the port in TWS/Gateway settings.
- **Webull:** authenticated adapter uses the official SDK for historical US stock bars. In automatic-discovery mode, IBKR supplies a limited market-mover candidate list, then Webull supplies historical bars for US candidates. This is not a pure Webull exchange-wide scanner and is not tick-by-tick streaming.
- **Automatic:** currently routes to IBKR for exchange discovery/quotes; it does not silently fail over between data providers.
- **Repeat scan:** re-runs provider requests on the chosen interval; API quotas, broker pacing limits, data permissions and machine load still apply. Stop it when finished.
- **v6 streaming monitor:** uses IBKR quote subscriptions for a bounded 30–180 second window and samples quotes while connected. It reports price-threshold crossings; this is not a fully qualified alert unless RVOL, verified news and float also pass. Keep this page open while it runs. Use a different client ID from other IBKR sessions.
- Webull API credentials are held in Streamlit session memory for this run and are not written to files by this app.
- Optional news: set `FINNHUB_API_KEY`. Headlines are marked REVIEW REQUIRED, never auto-verified.
- Create `float_reference.csv` with `ticker,public_float_shares,source,source_date,verified`; entries older than 180 days are stale.
- RVOL compares cumulative volume through the current minute with prior same-session cumulative volume; at least three historical sessions are required.
- IBKR discovery is not exhaustive. Some extended-hours data may be sparse or unavailable for Canadian listings. The market selector does not guarantee complete exchange-wide coverage.
- This is a scanner only; it does not submit orders.
""")
