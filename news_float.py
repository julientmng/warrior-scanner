import os, requests
import pandas as pd
from datetime import datetime, timedelta, timezone

def news_for(symbol, hours=48):
    token=os.getenv("FINNHUB_API_KEY","").strip()
    if not token: return {"headline":"","url":"","source":"","published":"","status":"NOT CONFIGURED","verified":None}
    now=datetime.now(timezone.utc); start=now-timedelta(hours=hours)
    try:
        r=requests.get("https://finnhub.io/api/v1/company-news",params={"symbol":symbol,"from":start.date().isoformat(),"to":now.date().isoformat(),"token":token},timeout=10)
        r.raise_for_status()
        items=sorted(r.json(),key=lambda x:x.get("datetime",0),reverse=True)
        for x in items:
            ts=x.get("datetime",0)
            if ts and ts<start.timestamp(): continue
            if x.get("headline") and x.get("url"):
                return {"headline":x["headline"],"url":x["url"],"source":x.get("source",""),
                    "published":datetime.fromtimestamp(ts,timezone.utc).isoformat() if ts else "",
                    "status":"REVIEW REQUIRED","verified":None}
        return {"headline":"","url":"","source":"","published":"","status":"NO RECENT ITEM","verified":False}
    except Exception as e:
        return {"headline":"","url":"","source":"","published":"","status":str(e)[:80],"verified":None}

def float_map(path="float_reference.csv"):
    try:
        df=pd.read_csv(path)
        needed={"ticker","public_float_shares","source","source_date","verified"}
        if not needed.issubset(df.columns): return {}
        df["ticker"]=df.ticker.astype(str).str.upper().str.strip()
        return {r["ticker"]:r.to_dict() for _,r in df.iterrows()}
    except Exception: return {}

def get_float(symbol, data):
    r=data.get(symbol.upper().strip())
    if not r: return {"shares":None,"source":"","date":"","verified":None}
    date=pd.to_datetime(r.get("source_date"),utc=True,errors="coerce")
    age=(pd.Timestamp.now(tz="UTC")-date).days if pd.notna(date) else 99999
    shares=pd.to_numeric(r.get("public_float_shares"),errors="coerce")
    flag=str(r.get("verified","")).lower() in {"true","1","yes","y"}
    return {"shares":int(shares) if pd.notna(shares) else None,"source":str(r.get("source","")),
        "date":str(r.get("source_date","")),"verified":bool(flag and age<=180 and pd.notna(shares)) if pd.notna(shares) else None}
