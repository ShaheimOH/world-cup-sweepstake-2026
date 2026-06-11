import json
import requests

# Official Pre-Tournament FIFA World Rankings for all 48 qualified teams (June 2026 Update)
TEAM_RANKINGS = {
    "Mexico": 14, "South Korea": 25, "Czechia": 39, "South Africa": 60,
    "Switzerland": 19, "Canada": 31, "Qatar": 55, "Bosnia and Herzegovina": 64,
    "Brazil": 6, "Morocco": 7, "Scotland": 43, "Haiti": 82,
    "United States": 16, "Türkiye": 22, "Australia": 27, "Paraguay": 40,
    "Germany": 10, "Ecuador": 24, "Côte d'Ivoire": 33, "Curaçao": 83,
    "Netherlands": 8, "Japan": 18, "Sweden": 38, "Tunisia": 46,
    "Belgium": 9, "IR Iran": 20, "Egypt": 29, "New Zealand": 85,
    "Spain": 2, "Uruguay": 17, "Saudi Arabia": 61, "Cabo Verde": 68,
    "France": 3, "Senegal": 15, "Norway": 31, "Iraq": 56,
    "Argentina": 1, "Austria": 23, "Algeria": 28, "Jordan": 63,
    "Portugal": 5, "Colombia": 13, "Congo DR": 45, "Uzbekistan": 50,
    "England": 4, "Croatia": 11, "Panama": 34, "Ghana": 73
}

LOWEST_RANK = max(TEAM_RANKINGS.values()) 

def get_scaled_ranking(team_name):
    rank = TEAM_RANKINGS.get(team_name, LOWEST_RANK)
    return rank / LOWEST_RANK

def fetch_live_tournament_state():
    """Fetches real-time match data from WorldCup2026 API to track team progression & exits"""
    state = {
        "winner": "TBD", "runner_up": "TBD",
        "semis": [], "quarters": [], "r16": [], "r32": [], "group_stage_exit": []
    }
    
    try:
        response = requests.get("https://worldcup26.ir/get/games", timeout=10)
        if response.status_code != 200:
            return state
        
        matches = response.json()
        
        all_teams_started = set(TEAM_RANKINGS.keys())
        knockout_attendees = set()
        
        for match in matches:
            stage = match.get("stage", "")
            status = match.get("status", "")
            home = match.get("home_team")
            away = match.get("away_team")
            winner = match.get("winner_team")
            
            # Record any team that made it past the initial 12 groups into the knockouts
            if stage in ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]:
                if home: knockout_attendees.add(home)
                if away: knockout_attendees.add(away)
                
            # Populate our evaluation arrays
            if stage == "Round of 32":
                if home: state["r32"].append(home)
                if away: state["r32"].append(away)
            elif stage == "Round of 16":
                if home: state["r16"].append(home)
                if away: state["r16"].append(away)
            elif stage == "Quarter-finals":
                if home: state["quarters"].append(home)
                if away: state["quarters"].append(away)
            elif stage == "Semi-finals":
                if home: state["semis"].append(home)
                if away: state["semis"].append(away)
            elif stage == "Final" and status == "finished" and winner:
                state["winner"] = winner
                state["runner_up"] = away if winner == home else home

        # Eliminated entirely in the primary group phase
        state["group_stage_exit"] = list(all_teams_started - knockout_attendees)
        
    except Exception as e:
        print(f"API Fetch failed: {e}")
        
    return state

def calculate_sweepstake_scores():
    try:
        with open('data/users.json', 'r') as file:
            players = json.load(file)
    except:
        print("No users found to parse.")
        return

    live = fetch_live_tournament_state()

    actual_winner = live["winner"]
    actual_runner_up = live["runner_up"]
    actual_semis = live["semis"]
    actual_quarters = live["quarters"]
    actual_r16 = live["r16"]
    actual_r32 = live["r32"]
    actual_group_stage_exit = live["group_stage_exit"]

    leaderboard = []

    for player in players:
        score = 0.0
        
        # --- CATEGORY 1: Winner Selection ---
        w_guess = player.get('winners')
        if w_guess == actual_winner and actual_winner != "TBD": score += 6
        elif w_guess == actual_runner_up and actual_runner_up != "TBD": score += 4
        elif w_guess in actual_semis: score += 3
        elif w_guess in actual_quarters: score += 2
        elif w_guess in actual_r16: score += 1
        elif w_guess in actual_r32: score += 0.5
        
        # --- CATEGORY 2: Runner-Up Selection ---
        r_guess = player.get('runnersUp')
        if r_guess == actual_runner_up and actual_runner_up != "TBD": score += 6
        elif r_guess == actual_winner and actual_winner != "TBD": score += 4
        elif r_guess in actual_semis: score += 3
        elif r_guess in actual_quarters: score += 2
        elif r_guess in actual_r16: score += 1
        elif r_guess in actual_r32: score += 0.5

        # --- CATEGORY 3: Biggest Disappointment (Weighed by Scaled Ranking) ---
        d_guess = player.get('disappointment')
        d_sr = get_scaled_ranking(d_guess)
        
        if d_guess in actual_group_stage_exit: score += 6 * d_sr
        elif d_guess in actual_r32 and d_guess not in actual_r16: score += 5 * d_sr     # Lost in Round of 32
        elif d_guess in actual_r16 and d_guess not in actual_quarters: score += 4 * d_sr # Lost in Round of 16
        elif d_guess in actual_quarters and d_guess not in actual_semis: score += 3 * d_sr
        elif d_guess in actual_semis and d_guess != actual_runner_up and d_guess != actual_winner: score += 2 * d_sr
        elif d_guess == actual_runner_up and actual_runner_up != "TBD": score += 1 * d_sr

        # --- CATEGORY 4: Underdogs (Weighed by Inverted Scaled Ranking) ---
        u_guess = player.get('underdogs')
        u_sr = get_scaled_ranking(u_guess)
        u_multiplier = (1 - u_sr)
        
        if u_guess == actual_winner and actual_winner != "TBD": score += 6 * u_multiplier
        elif u_guess == actual_runner_up and actual_runner_up != "TBD": score += 4 * u_multiplier
        elif u_guess in actual_semis: score += 3 * u_multiplier
        elif u_guess in actual_quarters: score += 2 * u_multiplier
        elif u_guess in actual_r16: score += 1 * u_multiplier
        elif u_guess in actual_r32: score += 0.5 * u_multiplier

        leaderboard.append({
            "name": player['name'],
            "winners": player['winners'],
            "runnersUp": player['runnersUp'],
            "disappointment": player['disappointment'],
            "underdogs": player['underdogs'],
            "totalScore": round(score, 2)
        })

    leaderboard = sorted(leaderboard, key=lambda x: x.get('totalScore', 0), reverse=True)

    with open('data/users.json', 'w') as file:
        json.dump(leaderboard, file, indent=2)
        
    print(f"Calculated 48-team matrix loop successfully.")

if __name__ == "__main__":
    calculate_sweepstake_scores()