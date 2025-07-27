# Methodology: Wallet Risk Scoring

## 1. Data Collection

- Wallet list sourced from the provided spreadsheet.
- For each wallet:
  - **Transaction history** retrieved via Covalent’s `transactions_v2` endpoint.
  - **Token balances** retrieved via Covalent’s `balances_v2` endpoint.
- API results cached locally in `cache/` for efficiency.

## 2. Feature Selection

Each wallet is characterized by:
- **Borrowed:** Number of borrow transactions.
- **Repaid:** Number of repay transactions.
- **Collateral:** Total estimated ERC20 balance (converted via decimals).
- **Repayment Ratio:** `repaid / borrowed` (defaults to 1 if no borrows).
- **Borrow-to-Collateral Ratio:** `borrowed / collateral` (0 if no collateral).
- **Liquidations:** Count of liquidation-related events.
- **Activity Days:** Days between first and last transaction.

These indicators reflect both **creditworthiness** (repayment behavior) and **risk** (collateralization, liquidations, activity).

## 3. Scoring Method

1. Each feature is **normalized (0–1)** using `MinMaxScaler`.
2. Ratios where **higher values imply higher risk** (e.g., borrow/collateral, liquidations) are inverted (`1 - scaled_value`).
3. Weighted sum:
   ```
   score_raw = (repayment_ratio * 0.4) +
   (borrow_collateral_ratio * 0.25) +
   (1 - liquidations) * 0.25 +
   (activity_days * 0.1)
   ```
4. `score_raw` is rescaled to **0–1000**.

If all scores are identical (no activity), defaults to `500`.

## 4. Output

- Results are saved to `output/wallet_risk_scores.csv`.
- Example:
  ```
  wallet_id,score
  0xfaa0768bde629806739c3a4620656c5d26f44ef2,732
  ```

## 5. Scalability

- API calls are cached.
- Multithreading (`ThreadPoolExecutor`) speeds up fetching.
- Retry with exponential backoff ensures reliability.

## Risk Indicators Justification

- **High repayment ratio** → lower risk (good borrower).
- **High collateral relative to borrow** → lower risk.
- **Few liquidations** → lower risk.
- **Consistent activity** → better history, less likely to default.

Final scores balance these dimensions to estimate overall wallet health.
