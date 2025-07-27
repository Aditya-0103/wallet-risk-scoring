import pandas as pd
import requests
import os
import time
import json
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------
# CONFIGURATION
# ---------------------------
WALLET_LIST_URL = "https://docs.google.com/spreadsheets/d/1ZzaeMgNYnxvriYYpe8PE7uMEblTI0GV5GIVUnsP-sBs/export?format=csv"
COVALENT_KEY = "cqt_rQJQRT3VmxHkt9T8FtGFcWMMqQKW"  # <-- Replace with your Covalent API key
CHAIN_ID = 1  # Ethereum mainnet
OUTPUT_DIR = "output"
CACHE_DIR = "cache"
MAX_THREADS = 5  # Number of wallets to fetch in parallel

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------
# Requests Session (with Retry)
# ---------------------------
session = requests.Session()
retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

def fetch_api(url, params, cache_file):
    """Fetch data with caching and retry logic."""
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)

    time.sleep(0.25)  # Avoid hitting rate limit (4 requests/sec)
    try:
        resp = session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        with open(cache_file, "w") as f:
            json.dump(data, f)
        return data
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {}

# ---------------------------
# Covalent API Helpers
# ---------------------------
def fetch_transactions(wallet):
    url = f"https://api.covalenthq.com/v1/{CHAIN_ID}/address/{wallet}/transactions_v2/"
    params = {"key": COVALENT_KEY, "page-size": 100}
    cache_file = os.path.join(CACHE_DIR, f"{wallet}_tx.json")
    data = fetch_api(url, params, cache_file)
    return data.get("data", {}).get("items", [])

def fetch_token_balances(wallet):
    url = f"https://api.covalenthq.com/v1/{CHAIN_ID}/address/{wallet}/balances_v2/"
    params = {"key": COVALENT_KEY}
    cache_file = os.path.join(CACHE_DIR, f"{wallet}_balances.json")
    data = fetch_api(url, params, cache_file)
    return data.get("data", {}).get("items", [])

# ---------------------------
# Feature Extraction
# ---------------------------
def compute_wallet_features(wallet):
    txs = fetch_transactions(wallet)
    balances = fetch_token_balances(wallet)

    borrowed, repaid, collateral, liquidations = 0, 0, 0, 0
    timestamps = []

    # Parse transactions
    for tx in txs:
        method = (tx.get("decoded", {}).get("name") or "").lower()
        ts = tx.get("block_signed_at")
        if ts:
            timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))

        if "borrow" in method:
            borrowed += 1
        if "repay" in method:
            repaid += 1
        if "liquidate" in method:
            liquidations += 1

    # Collateral estimation (sum of ERC20 balances)
    for token in balances:
        decimals = token.get("contract_decimals") or 18
        balance = float(token.get("balance", 0)) / (10 ** decimals)
        collateral += balance

    activity_days = (max(timestamps) - min(timestamps)).days if timestamps else 0

    repayment_ratio = repaid / borrowed if borrowed > 0 else 1.0
    borrow_collateral_ratio = borrowed / collateral if collateral > 0 else 0.0

    return {
        "wallet_id": wallet,
        "borrowed": borrowed,
        "repaid": repaid,
        "collateral": collateral,
        "repayment_ratio": repayment_ratio,
        "borrow_collateral_ratio": borrow_collateral_ratio,
        "liquidations": liquidations,
        "activity_days": activity_days
    }

# ---------------------------
# Main Pipeline
# ---------------------------
def main():
    wallets_df = pd.read_csv(WALLET_LIST_URL)
    wallets = [w.lower() for w in wallets_df["wallet_id"].tolist()]

    features = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(compute_wallet_features, w): w for w in wallets}
        for future in as_completed(futures):
            wallet = futures[future]
            try:
                features.append(future.result())
                print(f"Processed {wallet}")
            except Exception as e:
                print(f"Error processing {wallet}: {e}")

    df = pd.DataFrame(features)

    # Normalize features
    scaler = MinMaxScaler()
    df_norm = df.copy()

    df_norm["repayment_ratio"] = scaler.fit_transform(df[["repayment_ratio"]])
    df_norm["activity_days"] = scaler.fit_transform(df[["activity_days"]])
    df_norm["borrow_collateral_ratio"] = 1 - scaler.fit_transform(df[["borrow_collateral_ratio"]])
    df_norm["liquidations"] = 1 - scaler.fit_transform(df[["liquidations"]])

    weights = {
        "repayment_ratio": 0.4,
        "borrow_collateral_ratio": 0.25,
        "liquidations": 0.25,
        "activity_days": 0.1
    }

    df_norm["raw_score"] = (
        df_norm["repayment_ratio"] * weights["repayment_ratio"] +
        df_norm["borrow_collateral_ratio"] * weights["borrow_collateral_ratio"] +
        df_norm["liquidations"] * weights["liquidations"] +
        df_norm["activity_days"] * weights["activity_days"]
    )

    min_val, max_val = df_norm["raw_score"].min(), df_norm["raw_score"].max()
    df_norm["score"] = 500 if max_val == min_val else ((df_norm["raw_score"] - min_val) / (max_val - min_val)) * 1000

    output_file = os.path.join(OUTPUT_DIR, "wallet_risk_scores.csv")
    df_norm[["wallet_id", "score"]].to_csv(output_file, index=False)
    print(f"Saved results to {output_file}")

if __name__ == "__main__":
    main()
