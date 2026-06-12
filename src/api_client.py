import json
import requests
import csv
from io import StringIO

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
SPREADSHEET_ID = "1xVHTfh8G-EOJK_jTiz0zqQ2Q0t4ySVvcVNza4gPIAH0"

def get_scaled_ranking(team_name):
    rank = TEAM_RANKINGS.get(team_name, LOWEST_RANK)
    return rank / LOWEST_RANK

def fetch_live_tournament_state():
    """Tracks progression via live matches AND infers predictions using real-time group standings"""
    state = {
        "winner": "TBD", "runner_up": "TBD",
        "semis": [], "quarters": [], "r16": [], "r32": [], "group_stage_exit": []
    }
    
    # 1. Fetch group standings for live "interim" tracking calculations
    projected_r32 = set()
    projected_exits = set()
    
    try:
        group_response = requests.get("https://worldcup26.ir/get/groups", timeout=10)
        if group_response.status_code == 200:
            groups_data = group_response.json()
            for group in groups_data:
                teams = group.get("teams", [])  # Teams come pre-sorted by points/GD
                for i, team in enumerate(teams):
                    team_name = team.get("name")
                    if not team_name: 
                        continue
                    # In 2026, Top 2 teams from the 12 groups advance directly to the Round of 32
                    if i < 2:
                        projected_r32.add(team_name)
                    else:
                        projected_exits.add(team_name)
    except Exception as e:
        print(f"Group standings fallback fetch skipped or unavailable: {e}")

    # 2. Fetch official match brackets history
    try:
        response = requests.get("https://worldcup26.ir/get/games", timeout=10)
        if response.status_code != 200:
            # Drop back to live group standing math if the games endpoint stalls
            state["r32"] = list(projected_r32)
            state["group_stage_exit"] = list(projected_exits)
            return state
        
        matches = response.json()
        all_teams_started = set(TEAM_RANKINGS.keys())
        knockout_attendees = set()
        has_actual_knockouts = False
        
        for match in matches:
            stage = match.get("stage", "")
            status = match.get("status", "")
            home = match.get("home_team")
            away = match.get("away_team")
            winner = match.get("winner_team")
            
            if stage in ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]:
                has_actual_knockouts = True
                if home: knockout_attendees.add(home)
                if away: knockout_attendees.add(away)
                
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

        if has_actual_knockouts:
            state["group_stage_exit"] = list(all_teams_started - knockout_attendees)
        else:
            # If the tournament is live in groups and no knockouts are written yet, use projections
            state["r32"] = list(projected_r32)
            state["group_stage_exit"] = list(projected_exits)
        
    except Exception as e:
        print(f"API Match processing failed fallback: {e}")
        state["r32"] = list(projected_r32)
        state["group_stage_exit"] = list(projected_exits)
        
    return state

def sync_players_from_google_sheets():
    """Backup function that pulls the entire Google Sheet directly to heal dropped webhooks"""
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
    
    try:
        response = requests.get(csv_url, timeout=15)
        if response.status_code != 200:
            print("Backup sync failed: Could not read Google Sheet.")
            return False
            
        csv_data = StringIO(response.text)
        reader = list(csv.reader(csv_data))
        
        if len(reader) <= 1:
            return False
            
        updated_players = []
        headers = [h.strip().lower() for h in reader[0]]
        
        # Default fallback indices
        name_idx, winner_idx, runner_idx, disapp_idx, underdog_idx = 1, 2, 3, 4, 5
        
        # Map indices dynamically based on actual header text
        for i, h in enumerate(headers):
            if "name" in h or "username" in h: name_idx = i
            elif "winner" in h: winner_idx = i
            elif "runner" in h: runner_idx = i
            elif "disappointment" in h: disapp_idx = i
            elif "underdog" in h: underdog_idx = i

        for row in reader[1:]:
            if not row or all(cell.strip() == "" for cell in row): 
                continue
            while len(row) < len(headers): 
                row.append("")
                
            player_name = row[name_idx].strip()
            if not player_name: 
                continue

            updated_players.append({
                "name": player_name,
                "winners": row[winner_idx].strip(),
                "runnersUp": row[runner_idx].strip(),
                "disappointment": row[disapp_idx].strip(),
                "underdogs": row[underdog_idx].strip(),
                "totalScore": 0.0
            })
            
        with open('data/users.json', 'w') as file:
            json.dump(updated_players, file, indent=2)
        print(f"🔄 Backup Sync Successful: Hard-synced {len(updated_players)} players from Google Sheets.")
        return True
    except Exception as e:
        print(f"Backup sync encountered an error: {e}")
        return False

def calculate_sweepstake_scores():
    # 1. Gather up-to-date form users from Google Sheet snapshot
    sync_players_from_google_sheets()
    
    try:
        with open('data/users.json', 'r') as file:
            players = json.load(file)
    except:
        print("No users found to parse.")
        return

    # 2. Get the blended (projections + actuals) live state from tournament data endpoints
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
        elif d_guess in actual_r32 and d_guess not in actual_r16: score += 5 * d_sr
        elif d_guess in actual_r16 and d_guess not in actual_quarters: score += 4 * d_sr
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

    # Sort leaderboard globally by descending score values
    leaderboard = sorted(leaderboard, key=lambda x: x.get('totalScore', 0), reverse=True)

    with open('data/users.json', 'w') as file:
        json.dump(leaderboard, file, indent=2)
        
    print(f"Calculated projection standings loop successfully for {len(leaderboard)} users.")

if __name__ == "__main__":
    calculate_sweepstake_scores()