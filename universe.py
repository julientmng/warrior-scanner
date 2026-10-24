from io import StringIO
from pathlib import Path
import requests, pandas as pd

US_DIRS={"NASDAQ":"https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
         "OTHER_US":"https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"}

def fetch_us_directories():
    rows=[]
    for group,url in US_DIRS.items():
        r=requests.get(url,timeout=20,headers={"User-Agent":"MomentumCatalystScanner/2.0"})
        r.raise_for_status()
        lines=[x for x in r.text.splitlines() if x.strip() and not x.startswith("File Creation Time")]
        df=pd.read_csv(StringIO("\n".join(lines)),sep="|",dtype=str)
        sym="Symbol" if group=="NASDAQ" else "ACT Symbol"
        if "Test Issue" in df: df=df[df["Test Issue"].fillna("N").eq("N")]
        name="Security Name"
        df["ticker"]=df[sym].astype(str).str.strip(); df["name"]=df[name].astype(str).str.strip()
        df["market_group"]=group; df["currency"]="USD"
        df["Exchange"]="NASDAQ" if group=="NASDAQ" else df.get("Exchange","OTHER_US")
        rows.append(df[["ticker","name","Exchange","currency","market_group"]])
    return pd.concat(rows,ignore_index=True).drop_duplicates(["ticker","Exchange"])

def import_tmx_file(path):
    p=Path(path); df=pd.read_excel(p,dtype=str) if p.suffix.lower() in {".xlsx",".xls"} else pd.read_csv(p,dtype=str)
    cols={str(c).strip().lower():c for c in df.columns}
    sym=next((cols[x] for x in ("symbol","ticker","stock symbol") if x in cols),None)
    if not sym: raise ValueError(f"No symbol column found: {list(df.columns)}")
    name=next((cols[x] for x in ("company name","issuer name","name") if x in cols),None)
    return pd.DataFrame({"ticker":df[sym].astype(str).str.strip(),
        "name":df[name].astype(str).str.strip() if name else "",
        "market_group":"TMX","currency":"CAD"})
