import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz
import os

TICKER_FILE = "tickers.txt"
EASTERN = pytz.timezone("US/Eastern")
OUTPUT_FILE = "output.csv"


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
# Pull last 7 days of 5-minute data
# -----------------------------------
def pull_last_7_days_5min(tickers):
    df = yf.download(
        tickers,
        period="7d",
        interval="5m",
        group_by="ticker",
        threads=True,
        progress=True
    )

    result = {}

    if isinstance(df.columns, pd.MultiIndex):
        for symbol in df.columns.levels[0]:
            try:
                sub_df = df[symbol].dropna(how="all")
                if sub_df.empty:
                    continue

                # Convert datetime index and sort
                sub_df.index = pd.to_datetime(sub_df.index)
                sub_df = sub_df.sort_index()

                # Convert to Eastern time
                if sub_df.index.tzinfo is None:
                    sub_df = sub_df.tz_localize("UTC").tz_convert(EASTERN)
                else:
                    sub_df = sub_df.tz_convert(EASTERN)

                # Filter market hours
                sub_df = sub_df.between_time("09:30", "16:00")

                result[symbol] = sub_df

            except Exception as e:
                print(f"Skipping {symbol} due to error: {e}")

    else:
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df.tz_localize("UTC").tz_convert(EASTERN)
        df = df.between_time("09:30", "16:00")
        result[df.name] = df

    return result


# -----------------------------------
# Extract value at a specific time (optional)
# -----------------------------------
def extract_time_slot(data_dict, time_slot="10:30"):
    """
    time_slot: string in HH:MM format, Eastern Time
    """
    rows = []
    for symbol, df in data_dict.items():
        # Convert time_slot to datetime.time
        h, m = map(int, time_slot.split(":"))
        try:
            row = df[df.index.time == pd.to_datetime(f"{h}:{m}").time()]
            if not row.empty:
                row = row.copy()
                row["Symbol"] = symbol
                row["TimeSlot"] = time_slot
                rows.append(row)
        except Exception as e:
            print(f"Error extracting time slot for {symbol}: {e}")
    if rows:
        return pd.concat(rows)
    else:
        return pd.DataFrame()


# -----------------------------------
# Main
# -----------------------------------
if __name__ == "__main__":
    tickers = load_tickers()
    data = pull_last_7_days_5min(tickers)

    # Optional: Extract specific time slot, e.g., "10:30"
    # time_slot_df = extract_time_slot(data, "10:30")

    # Or save all 5-min rows
    all_rows = []
    for symbol, df in data.items():
        df_copy = df.copy()
        df_copy["Symbol"] = symbol
        all_rows.append(df_copy)
    final_df = pd.concat(all_rows)

    # Reorder columns for readability
    final_df = final_df[["Symbol", "Open", "High", "Low", "Close", "Volume"]]

    # Save to CSV
    final_df.index = final_df.index.tz_localize(None)
    final_df.to_csv(OUTPUT_FILE, index_label="Datetime")
    print(f"Saved {len(final_df)} rows to {OUTPUT_FILE}")