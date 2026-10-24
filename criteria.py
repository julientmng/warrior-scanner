def _status(value, predicate):
    if value is None:
        return "UNKNOWN"
    try:
        return "PASS" if predicate(value) else "FAIL"
    except (TypeError, ValueError):
        return "UNKNOWN"

def evaluate(change, rvol, news_verified, price, float_shares, min_change=10, min_rvol=5,
             min_price=2, max_price=20, max_float=20_000_000, require_news=True, require_float=False):
    pillars = {
        "Price change": _status(change, lambda x: float(x) >= min_change),
        "Time-of-day RVOL": _status(rvol, lambda x: float(x) >= min_rvol),
        "News catalyst": "UNKNOWN" if news_verified is None else ("PASS" if news_verified is True else "FAIL"),
        "Price range": _status(price, lambda x: min_price <= float(x) <= max_price),
        "Public float": _status(float_shares, lambda x: int(x) < max_float),
    }
    passed = sum(v == "PASS" for v in pillars.values())
    unknown = sum(v == "UNKNOWN" for v in pillars.values())
    all_five = passed == 5 and unknown == 0
    eligible = all_five and (not require_news or pillars["News catalyst"] == "PASS") and (not require_float or pillars["Public float"] == "PASS")
    return {"pillars": pillars, "passed": passed, "unknown": unknown, "all_five": all_five, "eligible": eligible}
