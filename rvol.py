import pandas as pd

def time_of_day_rvol(bars, session, lookback=10):
    """Bars need date, minute, session, volume; same-session cumulative-volume comparison."""
    if not bars:
        return None
    df = pd.DataFrame(bars)
    if not {"date", "minute", "session", "volume"}.issubset(df.columns):
        return None
    df = df[df["session"] == session]
    dates = sorted(df["date"].dropna().unique())
    if not dates:
        return None
    today = dates[-1]
    current = df[df["date"] == today].sort_values("minute")
    if current.empty:
        return None
    minute = int(current.iloc[-1]["minute"])
    current_cum = float(current.loc[current.minute <= minute, "volume"].fillna(0).sum())
    historical = []
    for day in [d for d in dates if d < today][-lookback:]:
        old = df[(df.date == day) & (df.minute <= minute)]
        if not old.empty:
            historical.append(float(old.volume.fillna(0).sum()))
    if len(historical) < 3:
        return None
    avg = sum(historical) / len(historical)
    return current_cum / avg if avg > 0 else None
