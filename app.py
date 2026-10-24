import asyncio, pandas as pd, streamlit as st
from live_engine import run_live
from news_float import news_for, float_map, get_float
from criteria import evaluate

st.set_page_config(page_title="Warrior Momentum Scanner",page_icon="📈",layout="wide")
st.title("Warrior Momentum Scanner — v2")
st.caption("US + TSX/TSXV • IBKR scanner discovery • time-of-day RVOL • catalyst review • float provenance")
with st.sidebar:
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

st.warning("Live connection requires TWS/IB Gateway, API socket access and market-data subscriptions. IBKR scans are candidate discovery, not a complete exchange-wide universe. News requires review; missing float is UNKNOWN.")
if "rows" not in st.session_state: st.session_state.rows=[]
if "error" not in st.session_state: st.session_state.error=""
if st.button("Run live scan",type="primary"):
    with st.spinner("Connecting to IBKR and requesting candidate bars…"):
        result=asyncio.run(run_live(max_candidates))
    if not result["ok"]:
        st.session_state.error=result["error"]; st.session_state.rows=[]
    else:
        st.session_state.error=""
        floats=float_map(); output=[]
        for row in result["rows"]:
            if "Error" in row: output.append(row); continue
            symbol=row["Ticker"]; news=news_for(symbol,news_hours); flt=get_float(symbol,floats)
            score=evaluate(row.get("Change %"),row.get("Time-of-day RVOL"),news.get("verified"),
                row.get("Price"),flt.get("shares"),min_change,min_rvol,min_price,max_price,
                int(max_float*1_000_000),require_news,require_float)
            row.pop("_bars",None)
            output.append({**row,"Float (M)":flt["shares"]/1_000_000 if flt.get("shares") is not None else None,
                "Float verified":flt["verified"],"Float source":flt["source"],"Float date":flt["date"],
                "Catalyst":news["headline"],"News source":news["source"],"News published UTC":news["published"],
                "News URL":news["url"],"Catalyst status":news["status"],"Criteria passed":score["passed"],
                "Unknown criteria":score["unknown"],"All 5 pass":score["all_five"],"Eligible":score["eligible"],**score["pillars"]})
        st.session_state.rows=output; st.session_state.discovered=result["count"]
if st.session_state.error:
    st.error("IBKR error: "+st.session_state.error)
    st.write("Check TWS/Gateway is running, socket clients are enabled, port matches, and exchange data subscriptions are active.")
rows=st.session_state.rows
if rows:
    df=pd.DataFrame(rows)
    st.metric("Candidates discovered before quote limit",st.session_state.get("discovered",len(rows)))
    if "Eligible" in df:
        a,b,c=st.columns(3); a.metric("Quoted",len(df)); b.metric("All five pass",int(df["All 5 pass"].fillna(False).sum())); c.metric("Eligible",int(df["Eligible"].fillna(False).sum()))
    if "Criteria passed" in df: df=df.sort_values(["Eligible","Criteria passed","Time-of-day RVOL"],ascending=[False,False,False],na_position="last")
    st.dataframe(df,use_container_width=True,hide_index=True,column_config={"News URL":st.column_config.LinkColumn("News URL")})
    st.download_button("Download CSV",df.to_csv(index=False),"warrior_scan.csv","text/csv")
else: st.info("Click Run live scan after configuring IBKR.")
with st.expander("Setup / limitations",expanded=True):
    st.markdown("""
1. Install TWS or IB Gateway; start in paper mode.
2. Enable socket clients in API settings. Set `IBKR_HOST`, `IBKR_PORT`, `IBKR_CLIENT_ID` to your configured values.
3. Subscribe to relevant US and Canadian market data.
4. Optional news: set `FINNHUB_API_KEY`. Headlines are marked REVIEW REQUIRED, never auto-verified.
5. Create `float_reference.csv` with `ticker,public_float_shares,source,source_date,verified`; use `verified=true` only after source review. Entries older than 180 days are stale.
6. RVOL compares cumulative volume through the current minute with prior same-session cumulative volume; at least three historical sessions are required.
7. This is not yet a continuous all-symbol service. IBKR scanner API returns at most 50 results per scan and needs separate quote requests. Some extended-hours data may be sparse or unavailable for Canadian listings.
""")
