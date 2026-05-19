import os
import time
import threading
from flask import Flask, render_template, jsonify
from web3 import Web3
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

app = Flask(__name__)
RPC_URL = os.getenv("RPC_URL")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

data = {
    "blocks": [],
    "gas_history": [],
    "tx_type_counts": defaultdict(int),
    "total_eth_moved": 0,
    "total_txs": 0,
    "latest_block": 0
}

def classify_tx(tx):
    raw = tx["input"]
    d = raw.hex() if isinstance(raw, bytes) else raw
    if tx["value"] > 0 and d == "0x":
        return "ETH Transfer"
    elif d.startswith("0xa9059cbb"):
        return "Token Transfer"
    elif d.startswith("0x095ea7b3"):
        return "Approve"
    elif d.startswith("0x38ed1739") or d.startswith("0x7ff36ab5"):
        return "Swap"
    else:
        return "Contract Call"

def monitor():
    last_block = w3.eth.block_number
    while True:
        try:
            current = w3.eth.block_number
            if current > last_block:
                block = w3.eth.get_block(current, full_transactions=True)
                gas_price = w3.from_wei(block["baseFeePerGas"], "gwei") if "baseFeePerGas" in block else 0
                block_eth = sum(float(w3.from_wei(tx["value"], "ether")) for tx in block.transactions)

                data["latest_block"] = current
                data["total_eth_moved"] += block_eth
                data["total_txs"] += len(block.transactions)

                data["blocks"].insert(0, {
                    "number": current,
                    "tx_count": len(block.transactions),
                    "eth_moved": round(block_eth, 4),
                    "gas_price": float(gas_price)
                })
                if len(data["blocks"]) > 20:
                    data["blocks"].pop()

                data["gas_history"].insert(0, {
                    "block": current,
                    "gwei": float(gas_price)
                })
                if len(data["gas_history"]) > 20:
                    data["gas_history"].pop()

                for tx in block.transactions:
                    tx_type = classify_tx(tx)
                    data["tx_type_counts"][tx_type] += 1

                last_block = current
            time.sleep(12)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(12)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return jsonify({
        "latest_block": data["latest_block"],
        "total_txs": data["total_txs"],
        "total_eth_moved": round(data["total_eth_moved"], 4),
        "blocks": data["blocks"][:10],
        "gas_history": data["gas_history"],
        "tx_types": [{"type": k, "count": v} for k, v in data["tx_type_counts"].items()]
    })

if __name__ == "__main__":
    t = threading.Thread(target=monitor, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5003, debug=False)
