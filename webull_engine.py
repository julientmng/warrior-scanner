"""Webull OpenAPI market-data adapter (US stocks only).
Uses the official webull-openapi-python-sdk. Does not place orders.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

class WebullScanner:
    def __init__(self, app_key, app_secret, environment="Production"):
        if not app_key or not app_secret:
            raise ValueError("Enter your Webull App Key and App Secret.")
        try:
            from webull.core.client import ApiClient
            from webull.data.data_client import DataClient
        except Exception as e:
            raise RuntimeError("Webull SDK is not installed. Install requirements.txt again.") from e
        self.client = ApiClient(app_key, app_secret, "us")
        base = "https://api.webull.com" if environment == "Production" else "https://api.sandbox.webull.com"
        self.client.add_endpoint("us", base)
        self.data = DataClient(self.client)

    def test_connection(self):
        # Small, read-only request. A 403 usually means data entitlement is missing.
        result = self.data.market_data.get_history_bar("AAPL", "US_STOCK", "M1")
        code = getattr(result, "status_code", None)
        if code != 200:
            body = getattr(result, "text", "") or str(getattr(result, "json", lambda: {})())
            raise RuntimeError(f"Webull API returned HTTP {code}: {body[:250]}. Check credentials, environment and OpenAPI data subscription.")
        return True

    @staticmethod
    def _payload(resp):
        try: return resp.json()
        except Exception: return {}

    def fetch_bars(self, symbol, count=500):
        resp = self.data.market_data.get_history_bar(symbol, "US_STOCK", "M1")
        if getattr(resp, "status_code", None) != 200:
            raise RuntimeError(f"History request for {symbol} returned HTTP {getattr(resp,'status_code',None)}")
        payload = self._payload(resp)
        # SDK versions may wrap the result differently; normalize known response shapes.
        items = payload.get("data", payload.get("bars", payload.get("result", []))) if isinstance(payload, dict) else []
        if isinstance(items, dict): items = items.get("items", items.get("bars", []))
        out=[]
        for b in items or []:
            ts = b.get("time") or b.get("timestamp") or b.get("date")
            if not ts: continue
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                dt = dt.astimezone(ET)
            except Exception: continue
            minute = dt.hour*60+dt.minute
            session = "Premarket" if 240 <= minute < 570 else "Regular" if 570 <= minute < 960 else "After-hours" if 960 <= minute < 1200 else "Closed"
            out.append({"date":dt.date().isoformat(),"minute":minute,"session":session,"volume":float(b.get("volume",0) or 0),"close":float(b.get("close",0) or 0)})
        return out

    def quote_row(self, symbol, bars):
        # Derive price/change from recent bars if no snapshot endpoint is available in the SDK response.
        # Explicitly label this as bar-derived rather than pretending it is a streaming quote.
        if not bars:
            return {"Ticker":symbol,"Error":"Webull returned no usable historical bars"}
        today = datetime.now(ET).date().isoformat()
        current = [b for b in bars if b["date"] == today and b["close"] > 0]
        previous_days = sorted({b["date"] for b in bars if b["date"] < today})
        price = current[-1]["close"] if current else bars[-1]["close"]
        prior = [b for b in bars if previous_days and b["date"] == previous_days[-1] and b["close"] > 0]
        previous_close = prior[-1]["close"] if prior else None
        change = (price/previous_close-1)*100 if previous_close else None
        now = datetime.now(ET); m=now.hour*60+now.minute
        session = "Premarket" if 240 <= m < 570 else "Regular" if 570 <= m < 960 else "After-hours" if 960 <= m < 1200 else "Closed"
        from rvol import time_of_day_rvol
        rvol=time_of_day_rvol(bars, session)
        dollars=sum(b["close"]*b["volume"] for b in current if b["session"]==session)
        return {"Ticker":symbol,"Exchange":"US (Webull)","Currency":"USD","Session":session,"Price":price,"Change %":change,
                "Time-of-day RVOL":rvol,"Spread %":None,"Session $ volume":dollars,"Quote type":"Latest historical bar (not streaming snapshot)"}

    def scan_symbols(self, symbols):
        rows=[]
        for symbol in symbols:
            try: rows.append(self.quote_row(symbol, self.fetch_bars(symbol)))
            except Exception as e: rows.append({"Ticker":symbol,"Error":str(e)[:180]})
        return rows
