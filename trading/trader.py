import sys
import math
import random
import time
import requests
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QFrame, QGridLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPixmap
import pyqtgraph as pg

# ================= 1. THE BRAIN (Only Class Remaining) =================
class TradingBrain:
    def __init__(self):
        self.hidden_knobs = [random.uniform(-1.0, 1.0) for _ in range(42)]
        self.action_knobs = [random.uniform(-1.0, 1.0) for _ in range(21)]

    def make_tweaked_clone(self, strength):
        baby = TradingBrain()
        for i in range(len(self.hidden_knobs)):
            baby.hidden_knobs[i] = self.hidden_knobs[i] + random.uniform(-strength, strength)
        for i in range(len(self.action_knobs)):
            baby.action_knobs[i] = self.action_knobs[i] + random.uniform(-strength, strength)
        return baby

    def decide_action(self, inputs):
        hidden_thoughts = [0.0] * 6
        knob_idx = 0
        for h in range(6):
            score = 0
            for i in range(6): 
                score += inputs[i] * self.hidden_knobs[knob_idx]
                knob_idx += 1
            score += self.hidden_knobs[knob_idx] 
            knob_idx += 1
            hidden_thoughts[h] = math.tanh(score)

        action_scores = [0.0] * 3 
        knob_idx = 0
        for a in range(3):
            score = 0
            for h in range(6):
                score += hidden_thoughts[h] * self.action_knobs[knob_idx]
                knob_idx += 1
            score += self.action_knobs[knob_idx] 
            knob_idx += 1
            action_scores[a] = score

        return action_scores, hidden_thoughts

# ================= 2. DATA UTILS =================
def get_binance_data(symbol="BTCUSDT", interval="1d", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        prices, volumes = [], []
        for candle in data:
            prices.append(float(candle[4]))
            volumes.append(float(candle[5]))
        return prices, volumes
    except Exception:
        return [], []

def fit_scale_data(data_list):
    min_val, max_val = min(data_list), max(data_list)
    scaled = [(val - min_val) / (max_val - min_val) if max_val != min_val else 0.5 for val in data_list]
    return scaled, min_val, max_val

def apply_scale(val, min_val, max_val):
    if max_val == min_val: return 0.5
    return (val - min_val) / (max_val - min_val)

# ================= 3. GUI UPDATE FUNCTIONS =================
def run_on_main(func, *args):
    """Safely executes a function on the main GUI thread from a background thread."""
    QTimer.singleShot(0, lambda f=func, a=args: f(*a))

def append_log(ui, text):
    ui['console'].append(text)
    sb = ui['console'].verticalScrollBar()
    sb.setValue(sb.maximum())

def update_graph(ui, prices, bx, by, sx, sy):
    gw = ui['graph']
    gw.clear()
    gw.plot(range(len(prices)), prices, pen=pg.mkPen('#00aaff', width=2))
    if bx: gw.addItem(pg.ScatterPlotItem(x=bx, y=by, symbol='t', size=16, brush='#00ff00', pen='w'))
    if sx: gw.addItem(pg.ScatterPlotItem(x=sx, y=sy, symbol='t1', size=16, brush='#ff0000', pen='w'))

def update_portfolio(ui, status, price, cash, shares, equity):
    ui['lbl_status'].setText(f"STATUS: {status}")
    ui['lbl_price'].setText(f"BTC: ${price:,.2f}")
    ui['lbl_cash'].setText(f"Cash: ${cash:,.2f}")
    ui['lbl_shares'].setText(f"Shares: {shares:.4f} BTC")
    
    color = "#00ff00" if equity >= 100000 else "#ff5555"
    ui['lbl_equity'].setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
    ui['lbl_equity'].setText(f"Total Equity: ${equity:,.2f}")

def draw_neural_net(ui, inputs, hidden, outputs):
    label = ui['nn_label']
    w, h = label.width(), label.height()
    if w < 50 or h < 50: return # Prevent drawing on invalid sizes

    pixmap = QPixmap(w, h)
    pixmap.fill(QColor("#121212"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    layers = [
        {"name": "In", "data": inputs, "x": 30}, 
        {"name": "Hid", "data": hidden, "x": int(w/2)}, 
        {"name": "Out", "data": outputs, "x": w - 80}
    ]

    painter.setPen(QColor("gray"))
    for l in layers: 
        painter.drawText(l["x"] - 10, 20, l["name"])

    for layer in layers:
        data = layer["data"]
        if not data: continue
        spacing = h / (len(data) + 1)
        for i, val in enumerate(data):
            y = int((i + 1) * spacing)
            brightness = min(255, max(0, int(abs(val) * 200) + 55))
            color = QColor(0, brightness, 0) if val > 0 else QColor(brightness, 0, 0)
            
            if layer["name"] == "Out":
                labels = ["BUY", "SELL", "HOLD"]
                painter.setPen(QColor("white"))
                painter.drawText(layer["x"] + 25, y + 5, labels[i])
            
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor("white"), 1))
            painter.drawEllipse(layer["x"], y - 10, 20, 20)

    painter.end()
    label.setPixmap(pixmap)

# ================= 4. BACKGROUND BOT LOGIC =================
def run_bot(ui):
    run_on_main(append_log, ui, "Fetching Historical Data (1000 minutes)...")
    hist_prices, hist_volumes = get_binance_data(interval="1m", limit=1000)
    
    if not hist_prices:
        run_on_main(append_log, ui, "Error fetching data. Check internet connection.")
        return

    scaled_prices, min_p, max_p = fit_scale_data(hist_prices)
    scaled_volumes, min_v, max_v = fit_scale_data(hist_volumes)

    population_size = 30
    population = [TradingBrain() for _ in range(population_size)]
    generations = 30
    best_overall_brain = None

    # --- TRAINING PHASE ---
    for gen in range(generations):
        best_balance = 0
        best_brain = population[0]
        best_bx, best_by, best_sx, best_sy = [], [], [], []
        last_in, last_hid, last_out = [], [], []
        
        for brain in population:
            cash, shares = 100000.0, 0
            bx, by, sx, sy = [], [], [], []
            
            for day in range(2, len(hist_prices)):
                inputs = [
                    scaled_prices[day], scaled_prices[day-1], scaled_prices[day-2],
                    scaled_volumes[day], scaled_volumes[day-1], scaled_volumes[day-2]
                ]
                scores, hidden = brain.decide_action(inputs)
                action = scores.index(max(scores))
                current_price = hist_prices[day]
                
                if action == 0 and cash > 0: # BUY
                    shares += cash / current_price
                    cash = 0
                    bx.append(day); by.append(current_price)
                elif action == 1 and shares > 0: # SELL
                    cash += shares * current_price
                    shares = 0
                    sx.append(day); sy.append(current_price)
                    
                if day == len(hist_prices) - 1:
                    last_in, last_hid, last_out = inputs, hidden, scores

            final_balance = cash + (shares * hist_prices[-1])
            if final_balance == 100000.0: final_balance = 0 
                
            if final_balance > best_balance:
                best_balance = final_balance
                best_brain = brain
                best_bx, best_by, best_sx, best_sy = bx, by, sx, sy

        current_strength = max(0.01, 0.5 * (0.90 ** gen)) 
        population = [best_brain] + [best_brain.make_tweaked_clone(current_strength) for _ in range(population_size - 1)]
        
        # Dispatch UI Updates
        log_msg = f"Gen {gen+1}/{generations} | Best Profit: {((best_balance - 10000) / 10000) * 100:.1f}%"
        run_on_main(append_log, ui, log_msg)
        run_on_main(update_graph, ui, hist_prices, best_bx, best_by, best_sx, best_sy)
        run_on_main(draw_neural_net, ui, last_in, last_hid, last_out)
        run_on_main(update_portfolio, ui, f"TRAINING (Gen {gen+1})", hist_prices[-1], 0.0, 0.0, best_balance)
        time.sleep(0.1) 

    best_overall_brain = best_brain
    run_on_main(append_log, ui, "\n--- SWITCHING TO LIVE TRADING (1-Minute Candles) ---")

    # --- LIVE TRADING PHASE ---
    live_cash, live_shares = 10000.0, 0.0
    live_prices_history = hist_prices[-20:] 
    
    while True:
        live_p, live_v = get_binance_data(interval="1m", limit=3)
        if not live_p:
            time.sleep(5)
            continue
            
        current_price = live_p[-1]
        inputs = [
            apply_scale(live_p[2], min_p, max_p), apply_scale(live_p[1], min_p, max_p), apply_scale(live_p[0], min_p, max_p),
            apply_scale(live_v[2], min_v, max_v), apply_scale(live_v[1], min_v, max_v), apply_scale(live_v[0], min_v, max_v)
        ]
        
        scores, hidden = best_overall_brain.decide_action(inputs)
        action = scores.index(max(scores))
        
        live_prices_history.append(current_price)
        if len(live_prices_history) > 50: live_prices_history.pop(0)

        bx, by, sx, sy = [], [], [], []
        if action == 0 and live_cash > 0:
            live_shares = live_cash / current_price
            live_cash = 0
            run_on_main(append_log, ui, f"BOUGHT BTC at ${current_price:.2f}")
            bx.append(len(live_prices_history)-1); by.append(current_price)
        elif action == 1 and live_shares > 0:
            live_cash = live_shares * current_price
            live_shares = 0
            run_on_main(append_log, ui, f"SOLD BTC at ${current_price:.2f}")
            sx.append(len(live_prices_history)-1); sy.append(current_price)

        total_equity = live_cash + (live_shares * current_price)
        
        run_on_main(draw_neural_net, ui, inputs, hidden, scores)
        run_on_main(update_graph, ui, live_prices_history, bx, by, sx, sy)
        run_on_main(update_portfolio, ui, "🔴 LIVE TRADING", current_price, live_cash, live_shares, total_equity)
        
        time.sleep(5) 

# ================= 5. UI CONSTRUCTION =================
def build_ui():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("AI Algorithmic Trading Terminal")
    window.resize(1100, 700)
    window.setStyleSheet("background-color: #121212; color: white;")

    main_widget = QWidget()
    main_layout = QHBoxLayout()
    left_layout = QVBoxLayout()
    right_layout = QVBoxLayout()

    # Portfolio Setup
    portfolio_frame = QFrame()
    portfolio_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; padding: 10px;")
    port_layout = QGridLayout()
    
    lbl_status = QLabel("STATUS: INACTIVE")
    lbl_status.setStyleSheet("color: #ffaa00; font-weight: bold; font-size: 14px;")
    lbl_price = QLabel("BTC: $0.00")
    lbl_price.setStyleSheet("font-size: 18px; font-weight: bold;")
    lbl_equity = QLabel("Total Equity: $10,000.00")
    lbl_equity.setStyleSheet("color: #00ff00; font-size: 16px; font-weight: bold;")
    lbl_cash = QLabel("Cash: $10,000.00")
    lbl_shares = QLabel("Shares: 0.0000 BTC")

    port_layout.addWidget(lbl_status, 0, 0, 1, 2)
    port_layout.addWidget(lbl_price, 1, 0, 1, 2)
    port_layout.addWidget(lbl_equity, 2, 0)
    port_layout.addWidget(lbl_cash, 3, 0)
    port_layout.addWidget(lbl_shares, 4, 0)
    portfolio_frame.setLayout(port_layout)
    left_layout.addWidget(portfolio_frame, stretch=1)

    # Neural Net Visualizer Label (Replaces Custom QWidget Class)
    nn_label = QLabel()
    nn_label.setMinimumSize(250, 300)
    left_layout.addWidget(nn_label, stretch=2)

    # Log Console
    console = QTextEdit()
    console.setReadOnly(True)
    console.setStyleSheet("background-color: #000000; color: #00ff00; font-family: monospace; border: 1px solid #333;")
    left_layout.addWidget(console, stretch=1)

    # Graph
    pg.setConfigOption('background', '#121212')
    pg.setConfigOption('foreground', 'w')
    graph_widget = pg.PlotWidget(title="Live Market Feed")
    graph_widget.showGrid(x=True, y=True, alpha=0.3)
    right_layout.addWidget(graph_widget)

    main_layout.addLayout(left_layout, stretch=1)
    main_layout.addLayout(right_layout, stretch=3)
    main_widget.setLayout(main_layout)
    window.setCentralWidget(main_widget)

    # Package UI components in a dictionary to pass to functions
    ui_refs = {
        "app": app, "window": window,
        "lbl_status": lbl_status, "lbl_price": lbl_price, 
        "lbl_equity": lbl_equity, "lbl_cash": lbl_cash, 
        "lbl_shares": lbl_shares, "console": console,
        "nn_label": nn_label, "graph": graph_widget
    }

    return app, window, ui_refs

if __name__ == "__main__":
    app, window, ui = build_ui()
    
    # Start bot in a standard background thread rather than QThread class
    bot_thread = threading.Thread(target=run_bot, args=(ui,), daemon=True)
    bot_thread.start()

    window.show()
    sys.exit(app.exec_())