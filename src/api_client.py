import os
import json
import requests
import csv
from io import StringIO

# 🔑 SECURE: Looks for the GitHub Secret token first, falls back to your token for local testing
API_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "df1cb358fc2a451986970e91883e58b1")
# Ensure the 'data' directory exists locally to avoid FileNotFoundError
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')

# Official Pre-Tournament FIFA World Rankings (June 2026 Update)
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
HEADERS = { "X-Auth-Token": API_TOKEN }

def clean_string(text):
    """Normalizes names to minimize string mismatch issues across external sheets."""
    if not text:
        return ""
    text = str(text).strip().lower()
    # Handle common diacritics / synonyms manually for robust pairing
    replacements = {
        "ô": "o", "é": "e", "ü": "u", "í": "i", "ç": "c",
        "usa": "united states", "us": "united states",
        "korea": "south korea", "ivory coast": "côte d'ivoire",
        "cote d'ivoire": "côte d'ivoire", "bosnia": "bosnia and herzegovina"
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return text.strip()

def get_scaled_ranking(team_name):
    rank = TEAM_RANKINGS.get(team_name, LOWEST_RANK)
    return rank / LOWEST_RANK

def log_rate_limits(response):
    available = response.headers.get("X-RequestsAvailable", "Unknown")
    reset_timer = response.headers.get("X-RequestCounter-Reset", "Unknown")
    print(f"📊 Rate Limits -> Requests Available in Window: {available} | Window Reset: {reset_timer}s")

def build_team_id_maps():
    name_to_id = {}
    id_to_standard_name = {}
    
    url = "https://api.football-data.org/v4/competitions/WC/teams"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        log_rate_limits(response)
        
        if response.status_code == 200:
            data = response.json()
            for team in data.get("teams", []):
                team_id = str(team.get("id", ""))
                api_name = team.get("name", "").strip()
                short_name = team.get("shortName", api_name).strip()
                
                if not team_id: 
                    continue
                
                matched_key = None
                for official_key in TEAM_RANKINGS.keys():
                    if clean_string(official_key) in [clean_string(api_name), clean_string(short_name)]:
                        matched_key = official_key
                        break
                
                if not matched_key: 
                    matched_key = short_name.title()
                
                id_to_standard_name[team_id] = matched_key
                name_to_id[clean_string(api_name)] = team_id
                name_to_id[clean_string(short_name)] = team_id
                name_to_id[clean_string(matched_key)] = team_id
        else:
            print(f"⚠️ Teams API Warning: Server responded with status code {response.status_code}")
    except Exception as e:
        print(f"Error building database translation maps: {e}")
            
    return name_to_id, id_to_standard_name

def fetch_live_tournament_state(id_to_name):
    state = {
        "winner": "TBD", "runner_up": "TBD",
        "semis": set(), "quarters": set(), "r16": set(), "r32": set(), "group_stage_exit": set()
    }
    
    interim_r32 = set()
    interim_exits = set()
    all_known_ids = set(id_to_name.keys())
    
    url_standings = "https://api.football-data.org/v4/competitions/WC/standings"
    try:
        response = requests.get(url_standings, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            standings_data = response.json().get("standings", [])
            for group_block in standings_data:
                table = group_block.get("table", [])
                for idx, row in enumerate(table):
                    t_id = str(row.get("team", {}).get("id", ""))
                    if not t_id: 
                        continue
                    # 🎯 INTERIM MODE: Pulls indices 0 and 1 directly without waiting for games to finish
                    if idx < 2: 
                        interim_r32.add(t_id)
                    else: 
                        interim_exits.add(t_id)
    except Exception as e:
        print(f"Could not parse group standby tables: {e}")

    url_matches = "https://api.football-data.org/v4/competitions/WC/matches"
    try:
        response = requests.get(url_matches, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            matches = response.json().get("matches", [])
            has_actual_knockouts = False
            
            for m in matches:
                stage = m.get("stage", "")
                status = m.get("status", "")
                home_id = str(m.get("homeTeam", {}).get("id", "") or "")
                away_id = str(m.get("awayTeam", {}).get("id", "") or "")
                winner_assignment = str(m.get("score", {}).get("winner", ""))
                
                true_winner_id = ""
                if status == "FINISHED":
                    if winner_assignment == "HOME_TEAM": true_winner_id = home_id
                    elif winner_assignment == "AWAY_TEAM": true_winner_id = away_id
                
                if stage != "GROUP_STAGE": 
                    has_actual_knockouts = True
                    
                if stage == "ROUND_OF_32":
                    if home_id: state["r32"].add(home_id)
                    if away_id: state["r32"].add(away_id)
                elif stage in ["LAST_16", "ROUND_OF_16"]:
                    if home_id: state["r16"].add(home_id)
                    if away_id: state["r16"].add(away_id)
                elif stage == "QUARTER_FINALS":
                    if home_id: state["quarters"].add(home_id)
                    if away_id: state["quarters"].add(away_id)
                elif stage == "SEMI_FINALS":
                    if home_id: state["semis"].add(home_id)
                    if away_id: state["semis"].add(away_id)
                elif stage == "FINAL":
                    if status == "FINISHED" and true_winner_id:
                        state["winner"] = true_winner_id
                        state["runner_up"] = away_id if true_winner_id == home_id else home_id

            if has_actual_knockouts:
                knockout_attendees = state["r32"] | state["r16"] | state["quarters"] | state["semis"]
                state["group_stage_exit"] = all_known_ids - knockout_attendees
            else:
                state["r32"] = interim_r32 if interim_r32 else all_known_ids
                state["group_stage_exit"] = interim_exits
    except Exception as e:
        print(f"Matches processor tracking error: {e}")
        state["r32"] = interim_r32
        state["group_stage_exit"] = interim_exits
        
    return state

def sync_players_from_google_sheets():
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
    try:
        response = requests.get(csv_url, timeout=15)
        if response.status_code != 200: 
            return None
        csv_data = StringIO(response.text)
        reader = list(csv.reader(csv_data))
        if len(reader) <= 1: 
            return None
        
        fresh_players = []
        headers = [h.strip().lower() for h in reader[0]]
        name_idx, winner_idx, runner_idx, disapp_idx, underdog_idx = 1, 2, 3, 4, 5
        
        for i, h in enumerate(headers):
            if h in ["name", "player name", "your name", "username"]: name_idx = i
            elif "winner" in h and "runner" not in h: winner_idx = i
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

            fresh_players.append({
                "name": player_name,
                "winners": row[winner_idx].strip(),
                "runnersUp": row[runner_idx].strip(),
                "disappointment": row[disapp_idx].strip(),
                "underdogs": row[underdog_idx].strip(),
                "totalScore": 0.0
            })
        return fresh_players
    except Exception as e:
        print(f"Sheet sync error: {e}")
        return None

def calculate_sweepstake_scores():
    players = sync_players_from_google_sheets() or []
    
    webhook_players = []
    try:
        with open('data/raw_submissions.json', 'r') as file:
            webhook_players = json.load(file)
            if not isinstance(webhook_players, list): 
                webhook_players = [webhook_players]
    except:
        pass

    all_submitted_entries = players + webhook_players
    seen_names = set()
    unique_players = []
    
    for p in all_submitted_entries:
        p_name = p.get('name', '').strip()
        if p_name and p_name not in seen_names:
            seen_names.add(p_name)
            unique_players.append(p)

    if not unique_players:
        print("⚠️ No user targets discovered.")
        return

    try:
        name_to_id, id_to_name = build_team_id_maps()
        live = fetch_live_tournament_state(id_to_name)
    except Exception as e:
        print(f"❌ API connection failed: {e}. Calculations halted.")
        return

    actual_winner_id = live["winner"]
    actual_runner_id = live["runner_up"]
    actual_semis = live["semis"]
    actual_quarters = live["quarters"]
    actual_r16 = live["r16"]
    actual_r32 = live["r32"]
    actual_group_stage_exit = live["group_stage_exit"]

    leaderboard = []

    for player in unique_players:
        score = 0.0
        w_id = name_to_id.get(clean_string(player.get('winners')), "UNKNOWN_ID")
        r_id = name_to_id.get(clean_string(player.get('runnersUp')), "UNKNOWN_ID")
        d_id = name_to_id.get(clean_string(player.get('disappointment')), "UNKNOWN_ID")
        u_id = name_to_id.get(clean_string(player.get('underdogs')), "UNKNOWN_ID")

        # Fallback tracking printouts for debugging naming mismatches
        if d_id == "UNKNOWN_ID" and player.get('disappointment'):
            print(f"🔍 Notice: Unable to resolve ID for pick string: '{player.get('disappointment')}'")

        d_standard_name = id_to_name.get(d_id, "Unknown")
        u_standard_name = id_to_name.get(u_id, "Unknown")

        d_sr = get_scaled_ranking(d_standard_name)
        u_sr = get_scaled_ranking(u_standard_name)
        u_multiplier = (1 - u_sr)

        # --- Winner Selection ---
        if w_id == actual_winner_id and actual_winner_id != "TBD": score += 6
        elif w_id == actual_runner_id and actual_runner_id != "TBD": score += 4
        elif w_id in actual_semis: score += 3
        elif w_id in actual_quarters: score += 2
        elif w_id in actual_r16: score += 1
        elif w_id in actual_r32: score += 0.5
        
        # --- Runner-Up Selection ---
        if r_id == actual_runner_id and actual_runner_id != "TBD": score += 6
        elif r_id == actual_winner_id and actual_winner_id != "TBD": score += 4
        elif r_id in actual_semis: score += 3
        elif r_id in actual_quarters: score += 2
        elif r_id in actual_r16: score += 1
        elif r_id in actual_r32: score += 0.5

        # --- Biggest Disappointment ---
        if d_id in actual_group_stage_exit: score += 6 * d_sr
        elif d_id in actual_r32 and d_id not in actual_r16: score += 5 * d_sr
        elif d_id in actual_r16 and d_id not in actual_quarters: score += 4 * d_sr
        elif d_id in actual_quarters and d_id not in actual_semis: score += 3 * d_sr
        elif d_id in actual_semis and d_id != actual_runner_id and d_id != actual_winner_id: score += 2 * d_sr
        elif d_id == actual_runner_id and actual_runner_id != "TBD": score += 1 * d_sr

        # --- Underdogs ---
        if u_id == actual_winner_id and actual_winner_id != "TBD": score += 6 * u_multiplier
        elif u_id == actual_runner_id and actual_runner_id != "TBD": score += 4 * u_multiplier
        elif u_id in actual_semis: score += 3 * u_multiplier
        elif u_id in actual_quarters: score += 2 * u_multiplier
        elif u_id in actual_r16: score += 1 * u_multiplier
        elif u_id in actual_r32: score += 0.5 * u_multiplier

        leaderboard.append({
            "name": player.get('name'),
            "winners": player.get('winners'),
            "runnersUp": player.get('runnersUp'),
            "disappointment": player.get('disappointment'),
            "underdogs": player.get('underdogs'),
            "totalScore": round(score, 2)
        })

    leaderboard = sorted(leaderboard, key=lambda x: x.get('totalScore', 0), reverse=True)
    
    if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            
    with open(USERS_FILE, 'w') as file: 
            json.dump(leaderboard, file, indent=2)
            
    print(f"🚀 Success! Processed {len(leaderboard)} sorted users. Saved to {USERS_FILE}")

if __name__ == "__main__":
    calculate_sweepstake_scores()