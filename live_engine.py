import asyncio, os
from datetime import datetime
from zoneinfo import ZoneInfo
from ib_async import IB, ScannerSubscription
from rvol import time_of_day_rvol

ET = ZoneInfo("America/New_York")

def session_name(dt):
    dt = dt.astimezone(ET)
    m = dt.hour * 60 + dt.minute
    if 240 <= m < 570: return "Premarket"
    if 570 <= m < 960: return "Regular"
    if 960 <= m < 1200: return "After-hours"
    return "Closed"

class LiveScanner:
    def __init__(self):
        self.ib = IB()
    async def connect(self):
        await self.ib.connectAsync(os.getenv("IBKR_HOST","127.0.0.1"),
            int(os.getenv("IBKR_PORT","7497")), clientId=int(os.getenv("IBKR_CLIENT_ID","17")), timeout=8)
    async def close(self):
        if self.ib.isConnected(): self.ib.disconnect()
    async def _scan(self, location, code):
        sub = ScannerSubscription(instrument="STK", locationCode=location, scanCode=code, numberOfRows=50)
        try: results = await self.ib.reqScannerDataAsync(sub)
        except Exception: return []
        out=[]
        for item in results:
            c=item.contractDetails.contract
            out.append({"symbol":c.symbol,"conId":c.conId,"exchange":c.primaryExchange or c.exchange or "",
                        "currency":c.currency or "", "contract":c, "scan":code})
        return out
    async def discover(self):
        tasks=[self._scan(loc, code) for loc in ("STK.US.MAJOR","STK.US.MINOR","STK.CA")
               for code in ("TOP_PERC_GAIN","HOT_BY_VOLUME","MOST_ACTIVE")]
        results=await asyncio.gather(*tasks, return_exceptions=True)
        unique={}
        for result in results:
            if isinstance(result,list):
                for r in result: unique[r["conId"] or (r["symbol"],r["exchange"])]=r
        return list(unique.values())
    async def quote(self, row):
        contract=row["contract"]
        try:
            qualified=await self.ib.qualifyContractsAsync(contract)
            if not qualified: return {"Ticker":row["symbol"],"Error":"Contract qualification failed"}
            contract=qualified[0]
            ticker=self.ib.reqMktData(contract,"",False,False)
            await asyncio.sleep(1)
            hist=await self.ib.reqHistoricalDataAsync(contract,endDateTime="",durationStr="10 D",
                barSizeSetting="1 min",whatToShow="TRADES",useRTH=False,formatDate=2,keepUpToDate=False)
            daily=await self.ib.reqHistoricalDataAsync(contract,endDateTime="",durationStr="5 D",
                barSizeSetting="1 day",whatToShow="TRADES",useRTH=True,formatDate=2,keepUpToDate=False)
            bars=[]
            for b in hist or []:
                dt=b.date
                if not isinstance(dt,datetime): continue
                if dt.tzinfo is None: dt=dt.replace(tzinfo=ET)
                local=dt.astimezone(ET)
                bars.append({"date":local.date().isoformat(),"minute":local.hour*60+local.minute,
                    "session":session_name(local),"volume":float(b.volume or 0),"close":float(b.close or 0)})
            now=datetime.now(ET); sess=session_name(now)
            price=ticker.last if ticker.last and ticker.last>0 else ticker.close
            previous=float(daily[-2].close) if daily and len(daily)>=2 else None
            change=((float(price)/previous)-1)*100 if price and previous else None
            bid=ticker.bid if ticker.bid and ticker.bid>0 else None
            ask=ticker.ask if ticker.ask and ticker.ask>0 else None
            spread=((ask-bid)/((ask+bid)/2)*100) if bid and ask and ask>=bid else None
            rvol=time_of_day_rvol(bars,sess)
            today=now.date().isoformat()
            dollars=sum(x["close"]*x["volume"] for x in bars if x["date"]==today and x["session"]==sess)
            self.ib.cancelMktData(contract)
            return {"Ticker":row["symbol"],"Exchange":row["exchange"],"Currency":row["currency"],"Session":sess,
                "Price":float(price) if price else None,"Change %":change,"Time-of-day RVOL":rvol,
                "Spread %":spread,"Session $ volume":dollars,"_bars":bars}
        except Exception as e:
            try: self.ib.cancelMktData(contract)
            except Exception: pass
            return {"Ticker":row["symbol"],"Error":str(e)[:180]}

async def run_live(max_candidates=20):
    s=LiveScanner()
    try:
        await s.connect()
        discovered=await s.discover()
        rows=[]
        for r in discovered[:max_candidates]:
            rows.append(await s.quote(r))
            await asyncio.sleep(.2)
        return {"ok":True,"count":len(discovered),"rows":rows}
    except Exception as e: return {"ok":False,"error":str(e),"rows":[],"count":0}
    finally: await s.close()
