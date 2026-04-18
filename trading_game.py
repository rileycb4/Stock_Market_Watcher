import pandas as pd
import tkinter as tk
from datetime import datetime
import threading
import time

# ----------------------------
# Load CSV
# ----------------------------
CSV_FILE = "output.csv"
df = pd.read_csv(CSV_FILE, parse_dates=["Datetime"])
df.sort_values("Datetime", inplace=True)
df.reset_index(drop=True, inplace=True)

timestamps = df["Datetime"].sort_values().unique()

# ----------------------------
# Helper indicators
# ----------------------------
def compute_sma(series, period):
    return series.rolling(period).mean()

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ----------------------------
# Strategy class
# ----------------------------
class Strategy:
    def __init__(self, name):
        self.name = name
        self.cash = 100.0
        self.invested = 0.0
        self.holdings = {}  # ticker -> shares
        self.history = []

    def total_value(self, current_prices):
        invested_val = sum(current_prices[ticker]*shares for ticker, shares in self.holdings.items() if ticker in current_prices)
        return self.cash + invested_val

# Initialize strategies
strategies = {
    "Method 1 (SMA)": Strategy("Method 1 (SMA)"),
    "Method 2 (RSI)": Strategy("Method 2 (RSI)"),
    "Method 3 (Buy & Hold)": Strategy("Method 3 (Buy & Hold)")
}

# ----------------------------
# Prepare indicator data
# ----------------------------
sma_short = 5
sma_long = 20
rsi_period = 14

tickers = df["Symbol"].unique()
price_data = {}
for t in tickers:
    tdf = df[df["Symbol"]==t].copy()
    tdf.set_index("Datetime", inplace=True)
    tdf.sort_index(inplace=True)
    tdf["SMA5"] = compute_sma(tdf["Close"], sma_short)
    tdf["SMA20"] = compute_sma(tdf["Close"], sma_long)
    tdf["RSI14"] = compute_rsi(tdf["Close"], rsi_period)
    price_data[t] = tdf

# ----------------------------
# Simulation per timestamp
# ----------------------------
def update_strategies(index):
    timestamp = timestamps[index]
    current_prices = {}
    for t in tickers:
        if timestamp in price_data[t].index:
            current_prices[t] = price_data[t].loc[timestamp, "Close"]

    for name, strat in strategies.items():
        # Method 3: Buy & Hold
        if name == "Method 3 (Buy & Hold)" and not strat.holdings:
            tickers_to_buy = list(current_prices.keys())
            if tickers_to_buy:
                allocation = strat.cash / len(tickers_to_buy)
                for t in tickers_to_buy:
                    shares = allocation / current_prices[t]
                    strat.holdings[t] = shares
                strat.cash = 0.0

        # Method 1: SMA Crossover
        if name == "Method 1 (SMA)":
            for t, price in current_prices.items():
                row = price_data[t].loc[timestamp]
                sma5 = row["SMA5"]
                sma20 = row["SMA20"]
                if pd.isna(sma5) or pd.isna(sma20):
                    continue
                # Buy signal
                if sma5 > sma20 and strat.cash >= price:
                    shares = strat.cash // price
                    if shares > 0:
                        strat.holdings[t] = strat.holdings.get(t,0) + shares
                        strat.cash -= shares*price
                # Sell signal
                elif sma5 < sma20 and t in strat.holdings:
                    strat.cash += strat.holdings[t]*price
                    del strat.holdings[t]

        # Method 2: RSI
        if name == "Method 2 (RSI)":
            for t, price in current_prices.items():
                row = price_data[t].loc[timestamp]
                rsi = row["RSI14"]
                if pd.isna(rsi):
                    continue
                # Buy if oversold
                if rsi < 30 and strat.cash >= price:
                    shares = strat.cash // price
                    if shares>0:
                        strat.holdings[t] = strat.holdings.get(t,0) + shares
                        strat.cash -= shares*price
                # Sell if overbought
                elif rsi > 70 and t in strat.holdings:
                    strat.cash += strat.holdings[t]*price
                    del strat.holdings[t]

        # Update invested and record history
        strat.invested = sum(current_prices[t]*s for t,s in strat.holdings.items() if t in current_prices)
        total_val = strat.cash + strat.invested
        strat.history.append((timestamp, strat.cash, strat.invested, total_val))

# ----------------------------
# Pre-run simulation for all timestamps
# ----------------------------
for i in range(len(timestamps)):
    update_strategies(i)

# ----------------------------
# GUI
# ----------------------------
class SimulationGUI:
    def __init__(self, master):
        self.master = master
        master.title("Trading Simulation")
        self.playing = False
        self.speed = 10
        self.index = 0

        # Controls
        self.play_button = tk.Button(master, text="Play", command=self.toggle_play)
        self.play_button.pack()
        self.speed_label = tk.Label(master, text="Step Speed (sec):")
        self.speed_label.pack()
        self.speed_slider = tk.Scale(master, from_=1, to=30, orient=tk.HORIZONTAL, command=self.update_speed)
        self.speed_slider.set(self.speed)
        self.speed_slider.pack()
        self.time_slider = tk.Scale(master, from_=0, to=len(timestamps)-1, orient=tk.HORIZONTAL, length=500, command=self.jump_to)
        self.time_slider.pack()

        # Scoreboards
        self.score_frames = {}
        for name in strategies.keys():
            frame = tk.LabelFrame(master, text=name)
            frame.pack(fill="x")
            cash_label = tk.Label(frame, text="Cash: $0")
            cash_label.pack()
            invest_label = tk.Label(frame, text="Invested: $0")
            invest_label.pack()
            total_label = tk.Label(frame, text="Total Value: $0")
            total_label.pack()
            holdings_label = tk.Label(frame, text="Holdings: None")
            holdings_label.pack()
            self.score_frames[name] = {
                "cash": cash_label,
                "invested": invest_label,
                "total": total_label,
                "holdings": holdings_label
            }

        self.update_gui()

        self.thread = threading.Thread(target=self.run_loop)
        self.thread.daemon = True
        self.thread.start()

    def toggle_play(self):
        self.playing = not self.playing
        self.play_button.config(text="Pause" if self.playing else "Play")

    def update_speed(self, val):
        self.speed = int(val)

    def jump_to(self, val):
        self.index = int(val)
        self.update_gui()

    def update_gui(self):
        for name, strat in strategies.items():
            if strat.history:
                timestamp, cash, invested, total = strat.history[self.index]
                self.score_frames[name]["cash"].config(text=f"Cash: ${cash:.2f}")
                self.score_frames[name]["invested"].config(text=f"Invested: ${invested:.2f}")
                self.score_frames[name]["total"].config(text=f"Total Value: ${total:.2f}")
                holdings_text = ", ".join([f"{t}:{s:.2f}" for t,s in strat.holdings.items()]) if strat.holdings else "None"
                self.score_frames[name]["holdings"].config(text=f"Holdings: {holdings_text}")
        self.time_slider.set(self.index)

    def run_loop(self):
        while True:
            if self.playing:
                if self.index < len(timestamps)-1:
                    self.index += 1
                    self.update_gui()
            time.sleep(self.speed)

# ----------------------------
# Run GUI
# ----------------------------
root = tk.Tk()
gui = SimulationGUI(root)
root.mainloop()