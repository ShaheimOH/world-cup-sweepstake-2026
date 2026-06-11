import json
import requests
import csv
from io import StringIO

# ... Keep your existing TEAM_RANKINGS, get_scaled_ranking, and fetch_live_tournament_state() exactly the same ...

# Paste your copied spreadsheet ID here
SPREADSHEET_ID = "1xVHTfh8G-EOJK_jTiz0zqQ2Q0t4ySVvcVNza4gPIAH0"

def sync_players_from_google_sheets():
    """Backup function that pulls the entire Google Sheet directly to heal dropped webhooks"""
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
    
    try:
        response = requests.get(csv_url, timeout=15)
        if response.status_code != 200:
            print("Backup sync failed: Could not read Google Sheet.")
            return False
            
        # Parse the downloaded CSV data
        csv_data = StringIO(response.text)
        reader = list(csv_reader := csv.reader(csv_data))
        
        if len(reader) <= 1:
            return False # Sheet is empty or only contains headers
            
        updated_players = []
        # Skip header row (row 0), loop through submissions
        for row in reader[1:]:
            if len(row) < 6: # Ensure row isn't corrupted or empty
                continue
                
            # Maps your columns: Timestamp[0], Name[1], Winner[2], RunnerUp[3], Disappointment[4], Underdog[5]
            updated_players.append({
                "name": row[1].strip(),
                "winners": row[2].strip(),
                "runnersUp": row[3].strip(),
                "disappointment": row[4].strip(),
                "underdogs": row[5].strip(),
                "totalScore": 0.0 # Will be populated by the scoring engine immediately next
            })
            
        # Re-write the users.json file with a fresh, complete snapshot from the sheet
        with open('data/users.json', 'w') as file:
            json.dump(updated_players, file, indent=2)
        print(f"🔄 Backup Sync Successful: Hard-synced {len(updated_players)} players from Google Sheets.")
        return True
        
    except Exception as e:
        print(f"Backup sync encountered an error: {e}")
        return False

def calculate_sweepstake_scores():
    # 1. RUN THE SELF-HEALING BACKUP FIRST
    # This automatically pulls down any player missed by the live webhook!
    sync_players_from_google_sheets()

    try:
        with open('data/users.json', 'r') as file:
            players = json.load(file)
    except:
        print("No users found to parse.")
        return

    # 2. RUN YOUR SCORING CALCULATIONS NEXT
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

        # --- CATEGORY 3: Biggest Disappointment ---
        d_guess = player.get('disappointment')
        d_sr = get_scaled_ranking(d_guess)
        if d_guess in actual_group_stage_exit: score += 6 * d_sr
        elif d_guess in actual_r32 and d_guess not in actual_r16: score += 5 * d_sr
        elif d_guess in actual_r16 and d_guess not in actual_quarters: score += 4 * d_sr
        elif d_guess in actual_quarters and d_guess not in actual_semis: score += 3 * d_sr
        elif d_guess in actual_semis and d_guess != actual_runner_up and d_guess != actual_winner: score += 2 * d_sr
        elif d_guess == actual_runner_up and actual_runner_up != "TBD": score += 1 * d_sr

        # --- CATEGORY 4: Underdogs ---
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
        
    print(f"Calculated 48-team matrix loop successfully for {len(leaderboard)} users.")

if __name__ == "__main__":
    calculate_sweepstake_scores()