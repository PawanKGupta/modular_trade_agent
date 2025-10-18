# save as nse_rsi_ema_scan_grouped.py
import os
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
from tqdm import tqdm

# ---------- User settings ----------
EQUITY_CSV = "EQUITY_L.csv"  # NSE symbol list from official site
DAYS_LOOKBACK = 260  # fetch enough data for EMA200
BATCH_SIZE = 50  # number of tickers to request per batch
OUTPUT_CSV = "nse_rsi10_lt30_gt_ema200_by_date.csv"


# -----------------------------------

def get_ticker_list(equity_csv):
    if equity_csv and os.path.exists(equity_csv):
        df = pd.read_csv(equity_csv)
        col = 'SYMBOL' if 'SYMBOL' in df.columns else 'symbol'
        symbols = df[col].dropna().astype(str).str.strip().tolist()
        symbols = [s for s in symbols if s]  # remove blanks
        return symbols
    else:
        raise FileNotFoundError("Please download NSE 'EQUITY_L.csv' and set path in EQUITY_CSV.")


def compute_rsi(series, period=10):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rsi = pd.Series(np.nan, index=series.index)
    first_valid = avg_gain.first_valid_index()
    if first_valid is None:
        return rsi
    idx = series.index.get_loc(first_valid)
    prev_gain, prev_loss = avg_gain.iloc[idx], avg_loss.iloc[idx]
    for i in range(idx, len(series)):
        g, l = gain.iloc[i], loss.iloc[i]
        prev_gain = (prev_gain * (period - 1) + g) / period
        prev_loss = (prev_loss * (period - 1) + l) / period
        rs = prev_gain / prev_loss if prev_loss != 0 else np.inf
        rsi.iloc[i] = 100 - (100 / (1 + rs))
    return rsi


def compute_ema(series, span=200):
    return series.ewm(span=span, adjust=False).mean()


def process_batch(tickers, start, end):
    data = yf.download(tickers, start=start, end=end, progress=False, threads=True, group_by='ticker')
    matches = []
    for tick in tickers:
        try:
            df = data[tick].dropna(subset=['Close']).copy()
            df['RSI10'] = compute_rsi(df['Close'], 10)
            df['EMA200'] = compute_ema(df['Close'], 200)
            cond = (df['RSI10'] < 30) & (df['Close'] > df['EMA200'])
            filt = df.loc[cond, ['Close', 'RSI10', 'EMA200']].copy()
            if not filt.empty:
                filt.reset_index(inplace=True)
                filt['Ticker'] = tick
                matches.append(filt[['Date', 'Ticker']])
        except Exception as e:
            print(f"Error processing {tick}: {e}")
    if matches:
        return pd.concat(matches, ignore_index=True)
    else:
        return pd.DataFrame(columns=['Date', 'Ticker'])


def main():
    end = datetime.now().date() + timedelta(days=1)
    start = datetime.now().date() - timedelta(days=DAYS_LOOKBACK)
    print(f"Fetching data from {start} to {end}")

    symbols = get_ticker_list(EQUITY_CSV)
    tickers = [s + ".NS" for s in symbols]
    print(f"Total tickers: {len(tickers)}")

    all_matches = []
    for i in tqdm(range(0, len(tickers), BATCH_SIZE), desc="Processing"):
        batch = tickers[i:i + BATCH_SIZE]
        df = process_batch(batch, start.isoformat(), end.isoformat())
        if not df.empty:
            all_matches.append(df)
        time.sleep(1.2)  # rate-limit safety

    if not all_matches:
        print("No matches found.")
        return

    df_all = pd.concat(all_matches, ignore_index=True)
    df_all['Date'] = pd.to_datetime(df_all['Date']).dt.date

    # group by date
    grouped = (df_all.groupby('Date')['Ticker']
               .apply(lambda x: '|'.join(sorted(set(x))))
               .reset_index()
               .sort_values('Date'))

    grouped.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Saved grouped results to {OUTPUT_CSV}")
    print(grouped.tail())


if __name__ == "__main__":
    main()