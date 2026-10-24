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


## Version 3 provider settings

The webpage has a provider dropdown (IBKR / Webull / Automatic), conditional IBKR and Webull fields, market/session selectors, and status indicators. IBKR is the only live scanner adapter in this build. The Webull UI is present, but authenticated Webull OpenAPI market-data calls have not been integrated or runtime-tested. Webull selection will not run a scan; Automatic currently routes to IBKR only. This is explicit rather than pretending the Webull connection works.

Official Webull OpenAPI: https://www.webull.com/open-api and API access guidance: https://www.webull.com/help/faq/10512. Confirm the API key has appropriate data entitlements.

## v4 Webull adapter

The Webull provider now uses the official `webull-openapi-python-sdk` for authenticated historical US-stock bars. In the sidebar, choose **Webull**, select **US** only, enter App Key/App Secret, choose Production or Sandbox, and provide a comma-separated list of US symbols. The app performs a small AAPL history request as a connection/entitlement test, then queries the requested symbols.

Important limitations: this is not yet an exchange-wide Webull scanner and does not implement MQTT streaming quotes. Price/change are derived from returned bars and are labeled accordingly; do not treat them as a tick-by-tick quote. If the SDK's installed version or account entitlement differs, the UI reports the API error rather than fabricating data. Webull OpenAPI documentation: https://developer.webull.com/apis/docs/market-data-api/getting-started/ . Webull market-data access may require a separate OpenAPI data subscription. The adapter is US-stock only; use IBKR for TSX/TSXV and exchange-wide candidate discovery.


## v6 improvements

- **Candidate discovery for Webull mode:** choose “Discover market movers automatically” to use IBKR scanner results as the candidate funnel, then request historical bars from Webull for US-dollar candidates. IBKR TWS/Gateway must be connected even when Webull is selected. The scanner remains capped by the configured candidate limit and IBKR scanner results; this is not an exhaustive market-wide ranking.
- **Repeat scans:** choose 15, 30 or 60 seconds and enable Repeat scan automatically. Each rerun makes new provider requests. Use caution with API quotas, IBKR pacing, Webull entitlements and rate limits. Manual mode remains the default.
- **Market routing:** IBKR remains the supported route for TSX/TSXV. Webull data mode is US-only.
- **No tick-by-tick claim:** Webull results are based on returned historical bars; streaming quote subscriptions are not implemented in this build. The UI labels the quote type accordingly.
- **Testing:** Python syntax was checked. No live broker/API credentials were available for integration tests. Do not treat the software as production-validated or use it to place trades.


## v6: bounded IBKR streaming monitor

The UI adds **Start IBKR streaming monitor**. It discovers candidates with the IBKR scanner, requests historical 1-minute bars, subscribes to IBKR market-data updates, and samples quotes during a selected 30–180 second window. It produces a latest-snapshot table, downloadable samples, and preliminary alerts when observed price change is at least +10% and price is $2–$20.

Important: this is a bounded monitor, not a permanent background daemon. The Streamlit page waits while the monitoring window runs. Alerts are preliminary and do not mean all five criteria pass. Historical RVOL can be unknown or stale depending on bar availability; news and float still require separate verification. Confirm live-data entitlements and quotes in TWS/IB Gateway. Use a client ID that does not conflict with another running IBKR session. No orders are submitted.
