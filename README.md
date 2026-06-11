# 🔮 FIFA World Cup 2026 Prediction Sweepstake

An automated, serverless prediction tracking leaderboard for the expanded 48-team **FIFA World Cup 2026**. This project connects a public prediction form directly to a dynamic, self-sorting web dashboard with zero server maintenance costs, utilizing **Google Forms**, **Google Apps Script**, **GitHub Actions** and a **Python Matrix Scoring Engine**.

DO NOT SUBMITT MORE THAN ONCE, IT TAKES A WHILE FOR WEBPAGE TO UPDATE
---

## 🏆 Current Leaderboard & Player Submissions

The main dashboard renders player submissions and real-time calculated points dynamically. The table updates automatically on an hourly cron cycle as matches progress.

| Rank | Pundit Name | 🥇 Winner Pick | 🥈 Runner-Up Pick | 📉 Biggest Disappointment | 🚀 Underdog Sleeper | Total Points |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **1** | *Player 1* | Argentina | Spain | France | Haiti | **0.00 pts** |
| **2** | *Player 2* | Brazil | England | Germany | Canada | **0.00 pts** |
| **3** | *Player 3* | France | Portugal | Mexico | New Zealand | **0.00 pts** |

---

## 🧮 Dynamic Point Matrix Rules

Rather than utilizing flat-rate point values, this system scores predictions using a **Scaled Ranking ($SR$)** metric derived directly from the official pre-tournament FIFA World Rankings. This balances risk and reward: picking heavy underdogs to run deep or powerhouses to face early exits generates significantly higher point payouts.

The scaled ranking is calculated as:
$$\text{Scaled Ranking } (SR) = \frac{\text{Country Tournament Ranking}}{\text{Lowest Ranked Country's Ranking (New Zealand = 85)}}$$

### Point Allocation Breakdown

* **Winner Selection Matrix:** 6 points if your pick wins the tournament. Points scale down if they finish as Runner-Up (4 pts), Semis (3 pts), Quarters (2 pts), Round of 16 (1 pt), or Round of 32 (0.5 pts).
* **Runner-Up Selection Matrix:** 6 points if your pick finishes exactly second. Scales down matching the Winner Matrix path if they finish in adjacent knockout slots.
* **The Biggest Disappointment ($6 \times SR$):** Points scale up the higher a powerhouse team is ranked when they exit early. Choosing a top-3 team like France to drop out in groups yields minimal points ($\frac{3}{85} \times 6 = 0.21$), while a mid-tier team crashing out rewards a much higher multiplier.
* **The Underdogs ($6 \times (1 - SR)$):** Points scale up based on an inverted metric multiplied by how far they advance. Selecting a massive underdog like Haiti (#82) to make a deep knockout run yields a near-maximum multiplier payout ($1 - \frac{82}{85} = 0.965$).

### Points Matrix Table

| Actual Tournament Phase Reached | Winner Guess | Runner-Up Guess | Biggest Disappointment | The Underdogs |
| :--- | :---: | :---: | :---: | :---: |
| **Tournament Winner** | 6 pts | 4 pts | $0 \times SR$ | $6 \times (1 - SR)$ |
| **Runner-Up** | 4 pts | 6 pts | $1 \times SR$ | $4 \times (1 - SR)$ |
| **Semi-Finals** | 3 pts | 3 pts | $2 \times SR$ | $3 \times (1 - SR)$ |
| **Quarter-Finals** | 2 pts | 2 pts | $3 \times SR$ | $2 \times (1 - SR)$ |
| **Round of 16** | 1 pt | 1 pt | $4 \times SR$ | $1 \times (1 - SR)$ |
| **Round of 32** | 0.5 pts | 0.5 pts | $5 \times SR$ | $0.5 \times (1 - SR)$ |
| **Group Stage Exit** | 0 pts | 0 pts | $6 \times SR$ | $0 \times (1 - SR)$ |

---

## 📁 Project Structure

```text
├── .github/workflows/
│   ├── sync_users.yml          # Processes incoming Google Form entries instantly
│   └── calculate_scores.yml    # Cron worker running the scoring engine hourly
├── data/
│   └── users.json              # Main database storing player submissions & real-time scores
├── src/
│   └── api_client.py           # Python scoring engine integrated with the WorldCup2026 API
├── index.html                  # Responsive Tailwind CSS frontend leaderboard
└── README.md                   # Repository documentation
