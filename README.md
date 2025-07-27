# Wallet Risk Scoring (Compound/Aave V2)

This project assigns **risk scores (0–1000)** to 100 wallet addresses based on their historical DeFi activity on the Compound or Aave V2 protocol.

The pipeline:
1. **Fetches on-chain transaction history and balances** for each wallet using the Covalent API.
2. **Extracts key behavioral features** such as borrow and repay counts, collateral, repayment ratios, liquidations, and activity span.
3. **Normalizes and weights features** to generate a final score.
4. **Outputs the results** to `output/wallet_risk_scores.csv`.
---
## Usage

1. Install dependencies:
   ```bash
   pip install pandas requests scikit-learn
   ```
2. Add your Covalent API key in main.py:
   ```
   COVALENT_KEY = "your_api_key_here"
   ```
3. Run the script:
   ```
   python main.py
   ```
4. Check results:
   ```
   output/wallet_risk_scores.csv
   ```
---
## Output Format
The CSV contains:

```
wallet_id,score
0xfaa0768bde629806739c3a4620656c5d26f44ef2,732
...
```
Scores range from 0 (highest risk) to 1000 (lowest risk).
---
## Notes
* API calls are cached in cache/ to avoid redundant requests.
* The script uses retry and threading for faster, reliable data fetching.
* Supports 100+ wallets (scalable).

---
