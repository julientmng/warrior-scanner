"""IBKR streaming monitor. Read-only: subscribes to quotes and emits sampled snapshots."""
import asyncio, os, time
from datetime import datetime
from zoneinfo import ZoneInfo
from ib_async import IB, ScannerSubscription
from rvol import time_of_day_rvol

ET = ZoneInfo('America/New_York')

def _session(dt):
    m=dt.astimezone(ET).hour*60+dt.astimezone(ET).minute
    if 240 <= m < 570: return 'Premarket'
    if 570 <= m < 960: return 'Regular'
    if 960 <= m < 1200: return 'After-hours'
    return 'Closed'

async def monitor_stream(host='127.0.0.1', port=7497, client_id=28, duration_seconds=90,
                         max_candidates=20, sample_seconds=2, markets=None):
    """Subscribe to IBKR live quotes for a bounded window and return sampled snapshots.

    RVOL is calculated from historical 1-minute bars when available; it is not fabricated
    from the streaming daily-volume field. This function does not place orders.
    """
    ib=IB(); subscribed=[]; snapshots=[]; alerts=[]; latest={}; hist_by_conid={}
    markets=markets or ['US','TSX','TSXV']
    try:
        await ib.connectAsync(host, int(port), clientId=int(client_id), timeout=10)
        specs=[]
        if 'US' in markets: specs += [('STK.US.MAJOR', c) for c in ('TOP_PERC_GAIN','HOT_BY_VOLUME','MOST_ACTIVE')]
        if 'TSX' in markets or 'TSXV' in markets: specs += [('STK.CA', c) for c in ('TOP_PERC_GAIN','HOT_BY_VOLUME','MOST_ACTIVE')]
        found=[]
        for loc, code in specs:
            try:
                for x in await ib.reqScannerDataAsync(ScannerSubscription(instrument='STK', locationCode=loc, scanCode=code, numberOfRows=50)):
                    c=x.contractDetails.contract
                    if c.conId and c.conId not in {z['contract'].conId for z in found}:
                        if ('US' in markets and c.currency=='USD') or (('TSX' in markets or 'TSXV' in markets) and c.currency=='CAD'):
                            found.append({'contract':c,'symbol':c.symbol,'exchange':c.primaryExchange or c.exchange or '', 'currency':c.currency})
            except Exception:
                continue
        found=found[:max_candidates]
        if not found: return {'ok':False,'error':'IBKR scanner returned no candidates for the selected markets. Check API permissions, scanner availability and market-data subscriptions.','snapshots':[],'alerts':[],'symbols':[]}
        contracts=await ib.qualifyContractsAsync(*[x['contract'] for x in found])
        by_id={c.conId: next(x for x in found if x['contract'].conId==c.conId) for c in contracts}
        # Load historical minute bars before subscribing, so RVOL has a defensible baseline.
        for c in contracts:
            try:
                bars=await ib.reqHistoricalDataAsync(c,endDateTime='',durationStr='10 D',barSizeSetting='1 min',whatToShow='TRADES',useRTH=False,formatDate=2,keepUpToDate=False)
                norm=[]
                for b in bars or []:
                    dt=b.date
                    if not isinstance(dt,datetime): continue
                    if dt.tzinfo is None: dt=dt.replace(tzinfo=ET)
                    dt=dt.astimezone(ET)
                    norm.append({'date':dt.date().isoformat(),'minute':dt.hour*60+dt.minute,'session':_session(dt),'volume':float(b.volume or 0),'close':float(b.close or 0)})
                hist_by_conid[c.conId]=norm
            except Exception: hist_by_conid[c.conId]=[]
        tickers=ib.reqMktData(contracts, '', False, False) if False else [ib.reqMktData(c,'',False,False) for c in contracts]
        subscribed=contracts
        end=time.monotonic()+max(10,int(duration_seconds))
        last_alert_state={}
        while time.monotonic()<end:
            await asyncio.sleep(max(1,int(sample_seconds)))
            now=datetime.now(ET); sess=_session(now); minute=now.hour*60+now.minute
            for c,t in zip(contracts,tickers):
                meta=by_id[c.conId]
                price=t.last if t.last and t.last>0 else (t.marketPrice() if t.marketPrice() and t.marketPrice()>0 else None)
                prev=t.close if t.close and t.close>0 else None
                change=(float(price)/float(prev)-1)*100 if price and prev else None
                bid=t.bid if t.bid and t.bid>0 else None; ask=t.ask if t.ask and t.ask>0 else None
                spread=((ask-bid)/((ask+bid)/2)*100) if bid and ask and ask>=bid else None
                hist=hist_by_conid.get(c.conId,[])
                # Historical bars may not yet include the active minute. Add a provisional current bar
                # using cumulative session volume only when IBKR provides it; otherwise RVOL remains unknown.
                rvol=time_of_day_rvol(hist,sess)
                volume=getattr(t,'volume',None)
                row={'Timestamp ET':now.isoformat(timespec='seconds'),'Ticker':meta['symbol'],'Exchange':meta['exchange'],'Currency':meta['currency'],'Session':sess,
                     'Price':float(price) if price else None,'Change %':change,'Time-of-day RVOL':rvol,'Daily volume':int(volume) if volume is not None and volume>=0 else None,
                     'Spread %':spread,'Quote status':'LIVE subscription; field availability varies by entitlement'}
                snapshots.append(row); latest[meta['symbol']]=row
                # Candidate threshold alert is deliberately limited to observable price/price-change
                # thresholds. RVOL/news/float must still pass the main app's verified criteria.
                hit=bool(change is not None and price is not None and change>=10 and 2<=price<=20)
                key=(meta['symbol'],sess)
                if hit and not last_alert_state.get(key,False):
                    alerts.append({**row,'Alert':'Price >= +10% and within $2-$20; verify RVOL/news/float'})
                last_alert_state[key]=hit
        return {'ok':True,'count':len(found),'symbols':[x['symbol'] for x in found], 'snapshots':snapshots,'latest':list(latest.values()),'alerts':alerts,
                'note':'Streaming quote subscriptions were sampled during this window. RVOL may be UNKNOWN if historical same-session bars are unavailable; verify quote entitlement and data freshness.'}
    except Exception as e:
        return {'ok':False,'error':str(e)[:300],'snapshots':snapshots,'alerts':alerts,'symbols':[]}
    finally:
        for c in subscribed:
            try: ib.cancelMktData(c)
            except Exception: pass
        if ib.isConnected(): ib.disconnect()
