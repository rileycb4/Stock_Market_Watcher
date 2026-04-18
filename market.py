import sqlite3
import yfinance as yf
import time
from datetime import datetime, time as dtime
import pytz
import os
import pandas as pd

DB_NAME = "market.db"
TICKER_FILE = "tickers.txt"
PULL_INTERVAL_SECONDS = 600  # 10 minutes
EASTERN = pytz.timezone("US/Eastern")


# -----------------------------------
# Load tickers from file
# -----------------------------------
def load_tickers():
    if not os.path.exists(TICKER_FILE):
        raise FileNotFoundError(f"{TICKER_FILE} not found")

    with open(TICKER_FILE, "r") as f:
        tickers = [line.strip().upper() for line in f if line.strip()]

    print(f"Loaded {len(tickers)} tickers.")
    return tickers


# -----------------------------------
# Database setup
# -----------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            symbol TEXT,
            datetime TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            interval TEXT,
            PRIMARY KEY (symbol, datetime, interval)
        )
    """)

    conn.commit()
    conn.close()


# -----------------------------------
# Market hours check
# -----------------------------------
def is_market_open():
    now = datetime.now(EASTERN)
    if now.weekday() >= 5:
        return False

    market_open = dtime(9, 30)
    market_close = dtime(16, 0)
    return market_open <= now.time() <= market_close


# -----------------------------------
# Store data in SQLite
# -----------------------------------
def store_data(df, interval):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # df: MultiIndex for batch downloads
    if isinstance(df.columns, pd.MultiIndex):
        for symbol in df.columns.levels[0]:
            try:
                sub_df = df[symbol].dropna(how="all")
            except KeyError:
                continue
            for dt_index, row in sub_df.iterrows():
                cursor.execute("""
                    INSERT OR IGNORE INTO prices
                    (symbol, datetime, open, high, low, close, volume, interval)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    dt_index.strftime("%Y-%m-%d %H:%M:%S"),
                    row["Open"],
                    row["High"],
                    row["Low"],
                    row["Close"],
                    int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                    interval
                ))
    else:
        # Single ticker fallback
        for dt_index, row in df.iterrows():
            cursor.execute("""
                INSERT OR IGNORE INTO prices
                (symbol, datetime, open, high, low, close, volume, interval)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                df.name if hasattr(df, "name") else "UNKNOWN",
                dt_index.strftime("%Y-%m-%d %H:%M:%S"),
                row["Open"],
                row["High"],
                row["Low"],
                row["Close"],
                int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                interval
            ))

    conn.commit()
    conn.close()


# -----------------------------------
# Fetch data in batch
# -----------------------------------
def fetch_data_batch(tickers, interval):
    try:
        if interval == "5m":
            df = yf.download(
                tickers,
                period="1d",
                interval="5m",
                group_by="ticker",
                threads=True,
                progress=False
            )
        elif interval == "1d":
            df = yf.download(
                tickers,
                period="5d",
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False
            )
        else:
            return None
        return df
    except Exception as e:
        print(f"Error fetching batch: {e}")
        return None


# -----------------------------------
# Update cycle
# -----------------------------------
def update_cycle(tickers):
    open_status = is_market_open()
    print("Market Open:", open_status)
    print("Time:", datetime.now(EASTERN))

    interval = "5m" if open_status else "1d"
    print(f"Fetching {interval} data for {len(tickers)} tickers...")

    df = fetch_data_batch(tickers, interval)
    if df is not None:
        store_data(df, interval)
        print(f"Stored {interval} data for {len(tickers)} tickers.")
    else:
        print("No data fetched.")


# -----------------------------------
# Main loop
# -----------------------------------
if __name__ == "__main__":
    init_db()
    tickers = load_tickers()

    while True:
        update_cycle(tickers)
        print(f"Sleeping {PULL_INTERVAL_SECONDS/60} minutes...\n")
        time.sleep(PULL_INTERVAL_SECONDS)