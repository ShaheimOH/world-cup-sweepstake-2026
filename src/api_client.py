import json

# Official Pre-Tournament FIFA World Rankings for all 48 qualified teams (June 2026 Update)
TEAM_RANKINGS = {
    # Group A
    "Mexico": 14, "South Korea": 25, "Czechia": 39, "South Africa": 60,
    # Group B
    "Switzerland": 19, "Canada": 31, "Qatar": 55, "Bosnia and Herzegovina": 64,
    # Group C
    "Brazil": 6, "Morocco": 7, "Scotland": 43, "Haiti": 82,
    # Group D
    "United States": 16, "Türkiye": 22, "Australia": 27, "Paraguay": 40,
    # Group E
    "Germany": 10, "Ecuador": 24, "Côte d'Ivoire": 33, "Curaçao": 83,
    # Group F
    "Netherlands": 8, "Japan": 18, "Sweden": 38, "Tunisia": 46,
    # Group G
    "Belgium": 9, "IR Iran": 20, "Egypt": 29, "New Zealand": 85,
    # Group H
    "Spain": 2, "Uruguay": 17, "Saudi Arabia": 61, "Cabo Verde": 68,
    # Group I
    "France": 3, "Senegal": 15, "Norway": 31, "Iraq": 56,
    # Group J
    "Argentina": 1, "Austria": 23, "Algeria": 28, "Jordan": 63,
    # Group K
    "Portugal": 5, "Colombia": 13, "Congo DR": 45, "Uzbekistan": 50,
    # Group L
    "England": 4, "Croatia": 11, "Panama": 34, "Ghana": 73
}

# The denominator represents the lowest ranked team in the entire tournament (New Zealand = 85)
LOWEST_RANK = max(TEAM_RANKINGS.values()) 

def get_scaled_ranking(team_name):
    """Returns the country's ranking divided by the lowest country ranking (0 to 1 scale)"""
    rank = TEAM_RANKINGS.get(team_name, LOWEST_RANK)
    return rank / LOWEST_RANK

def calculate_sweepstake_scores():
    # 1. Fetch data submitted from the Google Form pipeline
    try:
        with open('data/users.json', 'r') as file:
            players = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print("No users found to parse.")
        return

    # --------------------------------------------------------------------
    # TOURNAMENT CONFIGURATION HUB
    # As the World Cup unfolds, populate these variables with the actual outcomes!
    # --------------------------------------------------------------------
    actual_winner = "TBD"          # e.g., "France"
    actual_runner_up = "TBD"       # e.g., "Spain"
    
    # Add teams here as they reach these respective knockout levels
    actual_semis = []              # Final 4 teams
    actual_quarters = []           # Final 8 teams
    actual_r16 = []                # Final 16 teams
    actual_group_stage_exit = []   # Teams knocked out in groups/round of 32

    leaderboard = []

    for player in players:
        score = 0.0
        
        # --- CATEGORY 1: Winner Selection Matrix ---
        w_guess = player.get('winners')
        if w_guess == actual_winner and actual_winner != "TBD": score += 6
        elif w_guess == actual_runner_up and actual_runner_up != "TBD": score += 4
        elif w_guess in actual_semis: score += 3
        elif w_guess in actual_quarters: score += 2
        elif w_guess in actual_r16: score += 1
        
        # --- CATEGORY 2: Runner-Up Selection Matrix ---
        r_guess = player.get('runnersUp')
        if r_guess == actual_runner_up and actual_runner_up != "TBD": score += 6
        elif r_guess == actual_winner and actual_winner != "TBD": score += 4
        elif r_guess in actual_semis: score += 3
        elif r_guess in actual_quarters: score += 2
        elif r_guess in actual_r16: score += 1

        # --- CATEGORY 3: Biggest Disappointment Matrix (Weighed by Scaled Ranking) ---
        d_guess = player.get('disappointment')
        d_sr = get_scaled_ranking(d_guess)
        
        if d_guess in actual_group_stage_exit: score += 6 * d_sr
        elif d_guess in actual_r16 and d_guess not in actual_quarters: score += 4 * d_sr
        elif d_guess in actual_quarters and d_guess not in actual_semis: score += 3 * d_sr
        elif d_guess in actual_semis and d_guess != actual_runner_up and d_guess != actual_winner: score += 2 * d_sr
        elif d_guess == actual_runner_up and actual_runner_up != "TBD": score += 1 * d_sr

        # --- CATEGORY 4: Underdogs Matrix (Weighed by Inverted Scaled Ranking) ---
        u_guess = player.get('underdogs')
        u_sr = get_scaled_ranking(u_guess)
        u_multiplier = (1 - u_sr)
        
        if u_guess == actual_winner and actual_winner != "TBD": score += 6 * u_multiplier
        elif u_guess == actual_runner_up and actual_runner_up != "TBD": score += 4 * u_multiplier
        elif u_guess in actual_semis: score += 3 * u_multiplier
        elif u_guess in actual_quarters: score += 2 * u_multiplier
        elif u_guess in actual_r16: score += 1 * u_multiplier

        # Append data to the payload, keeping 2 decimals for floating points
        leaderboard.append({
            "name": player['name'],
            "winners": player['winners'],
            "runnersUp": player['runnersUp'],
            "disappointment": player['disappointment'],
            "underdogs": player['underdogs'],
            "totalScore": round(score, 2)
        })

    # Sort the leaderboard array from highest points score to lowest
    leaderboard = sorted(leaderboard, key=lambda x: x.get('totalScore', 0), reverse=True)

    # Save calculated outcomes back to database store
    with open('data/users.json', 'w') as file:
        json.dump(leaderboard, file, indent=2)
        
    print(f"Leaderboard calculations processed for {len(leaderboard)} active users.")

if __name__ == "__main__":
    calculate_sweepstake_scores()