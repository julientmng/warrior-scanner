# Warrior Momentum Scanner v2

## Recommended provider
Start with IBKR TWS API / IB Gateway if you already use IBKR. IBKR's official pricing page currently lists Canadian Exchange Group (TSX/TSXV) Level 1 at USD 20/month for non-professionals and separate TSX/TSXV Level 1 products at CAD 9/month each. US data requirements depend on the bundle and entitlements. Fees and eligibility can change; confirm directly at https://www.interactivebrokers.com/en/pricing/market-data-pricing.php.

IBKR scanner API returns contracts, not quotes, and is capped at 50 results per scan and 10 active scans. This app combines several scanner codes and then requests data for a bounded set; it is not an exhaustive security master. See https://www.interactivebrokers.com/docs/tws-api/doc/market-scanner/introduction.

## Run on Windows
1. Install Python 3.11+ and IBKR TWS or IB Gateway. Start in paper mode.
2. Extract ZIP and open PowerShell in the folder:
   ```
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   $env:IBKR_HOST="127.0.0.1"
   $env:IBKR_PORT="7497"
   $env:IBKR_CLIENT_ID="17"
   streamlit run app.py
   ```
   Port is an example; use your configured TWS/Gateway API port.
3. Enable socket clients and activate relevant exchange data subscriptions.
4. Optional news enrichment: set `$env:FINNHUB_API_KEY="YOUR_KEY"` before launching. Returned news is not automatically considered a verified material catalyst.
5. Add reviewed float records to `float_reference.csv`.

## Five criteria
Price change, time-of-day RVOL, verified news catalyst, price range, public float. Unknown values are never counted as passing.

## Limitations
The app has a working IBKR scanner/quote path but does not run a continuous all-symbol feed. `universe.py` fetches US symbol directories and can import a TMX file, but TMX ingestion is not wired into the live candidate loop yet. Catalyst materiality requires review, and a reviewed float source is required. Robust production deployment still needs a persistent scheduler, database, alerts, exchange calendar/halts handling, corporate-action handling and tested ticker mapping.
