import json
import requests
import csv
from io import StringIO

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

def get_scaled_ranking(team_name):
    rank = TEAM_RANKINGS.get(team_name, LOWEST_RANK)
    return rank / LOWEST_RANK

def build_team_id_maps():
    """Queries /get/teams to match direct API keys against standardized naming models"""
    name_to_id = {}
    id_to_standard_name = {}
    
    synonyms = {
        "usa": "united states", "us": "united states",
        "korea": "south korea", "ivory coast": "côte d'ivoire",
        "cote d'ivoire": "côte d'ivoire", "bosnia": "bosnia and herzegovina"
    }
    
    try:
        response = requests.get("https://worldcup26.ir/get/teams", timeout=10)
        if response.status_code == 200:
            teams_list = response.json()
            for team in teams_list:
                if not isinstance(team, dict): 
                    continue
                
                # Dynamic check for string MongoDB hash keys vs numerical team index strings
                team_id = str(team.get("id") or team.get("team_id") or team.get("_id", ""))
                api_name = team.get("name", "").strip()
                if not team_id or not api_name: 
                    continue
                
                matched_key = None
                for official_key in TEAM_RANKINGS.keys():
                    if official_key.lower() == api_name.lower():
                        matched_key = official_key
                        break
                
                if not matched_key:
                    matched_key = api_name.title()
                
                id_to_standard_name[team_id] = matched_key
                name_to_id[matched_key.lower()] = team_id
                name_to_id[api_name.lower()] = team_id
            
            for slang, official_target in synonyms.items():
                if official_target in name_to_id:
                    name_to_id[slang] = name_to_id[official_target]
                    
    except Exception as e:
        print(f"⚠️ Critical Error parsing team directory mappings: {e}")
        
    return name_to_id, id_to_standard_name

def fetch_live_tournament_state():
    """Assembles active standings entirely using direct text key comparisons"""
    state = {
        "winner": "TBD", "runner_up": "TBD",
        "semis": set(), "quarters": set(), "r16": set(), "r32": set(), "group_stage_exit": set()
    }
    
    projected_r32 = set()
    projected_exits = set()
    all_api_ids = set()
    
    # 1. Gather Group Projections
    try:
        group_response = requests.get("https://worldcup26.ir/get/groups", timeout=10)
        if group_response.status_code == 200:
            groups_data = group_response.json()
            for group in groups_data:
                teams = group.get("teams", [])
                for i, team in enumerate(teams):
                    # Check if the team element is an object dictionary or a direct raw string ID
                    if isinstance(team, dict):
                        t_id = str(team.get("id") or team.get("team_id") or team.get("_id", ""))
                    else:
                        t_id = str(team)
                        
                    if not t_id: 
                        continue
                    all_api_ids.add(t_id)
                    if i < 2:
                        projected_r32.add(t_id)
                    else:
                        projected_exits.add(t_id)
    except Exception as e:
        print(f"Group standings fetch skipped: {e}")

    # 2. Extract Match Stage updates safely bypassing attribute checks
    try:
        response = requests.get("https://worldcup26.ir/get/games", timeout=10)
        if response.status_code != 200:
            state["r32"] = projected_r32
            state["group_stage_exit"] = projected_exits
            return state
            
        matches = response.json()
        knockout_attendees = set()
        has_actual_knockouts = False
        
        for match in matches:
            if not isinstance(match, dict): 
                continue
            stage = match.get("stage", "")
            status = match.get("status", "")
            
            # Safe parsing logic: extracts raw ID value directly if the endpoint passed plain strings
            h_data = match.get("home_team")
            a_data = match.get("away_team")
            w_data = match.get("winner_team")
            
            home_id = str(h_data.get("id") or h_data.get("_id") if isinstance(h_data, dict) else h_data or "")
            away_id = str(a_data.get("id") or a_data.get("_id") if isinstance(a_data, dict) else a_data or "")
            winner_id = str(w_data.get("id") or w_data.get("_id") if isinstance(w_data, dict) else w_data or "")
            
            if stage in ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]:
                has_actual_knockouts = True
                if home_id: knockout_attendees.add(home_id)
                if away_id: knockout_attendees.add(away_id)
                
            if stage == "Round of 32":
                if home_id: state["r32"].add(home_id)
                if away_id: state["r32"].add(away_id)
            elif stage == "Round of 16":
                if home_id: state["r16"].add(home_id)
                if away_id: state["r16"].add(away_id)
            elif stage == "Quarter-finals":
                if home_id: state["quarters"].add(home_id)
                if away_id: state["quarters"].add(away_id)
            elif stage == "Semi-finals":
                if home_id: state["semis"].add(home_id)
                if away_id: state["semis"].add(away_id)
            elif stage == "Final" and status == "finished" and winner_id:
                state["winner"] = winner_id
                state["runner_up"] = away_id if winner_id == home_id else home_id

        if has_actual_knockouts:
            state["group_stage_exit"] = all_api_ids - knockout_attendees
        else:
            state["r32"] = projected_r32
            state["group_stage_exit"] = projected_exits
            
    except Exception as e:
        print(f"API Match calculation matrix bypassed: {e}")
        state["r32"] = projected_r32
        state["group_stage_exit"] = projected_exits
        
    return state

def sync_players_from_google_sheets():
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
    try:
        response = requests.get(csv_url, timeout=15)
        if response.status_code != 200: return False
        csv_data = StringIO(response.text)
        reader = list(csv.reader(csv_data))
        if len(reader) <= 1: return False
        
        updated_players = []
        headers = [h.strip().lower() for h in reader[0]]
        name_idx, winner_idx, runner_idx, disapp_idx, underdog_idx = 1, 2, 3, 4, 5
        for i, h in enumerate(headers):
            if "name" in h or "username" in h: name_idx = i
            elif "winner" in h: winner_idx = i
            elif "runner" in h: runner_idx = i
            elif "disappointment" in h: disapp_idx = i
            elif "underdog" in h: underdog_idx = i

        for row in reader[1:]:
            if not row or all(cell.strip() == "" for cell in row): continue
            while len(row) < len(headers): row.append("")
            player_name = row[name_idx].strip()
            if not player_name: continue

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
        return True
    except:
        return False

def calculate_sweepstake_scores():
    sync_players_from_google_sheets()
    
    try:
        with open('data/users.json', 'r') as file:
            players = json.load(file)
    except:
        print("No users found to parse.")
        return

    name_to_id, id_to_name = build_team_id_maps()
    live = fetch_live_tournament_state()

    actual_winner_id = live["winner"]
    actual_runner_id = live["runner_up"]
    
    actual_semis = live["semis"]
    actual_quarters = live["quarters"]
    actual_r16 = live["r16"]
    actual_r32 = live["r32"]
    actual_group_stage_exit = live["group_stage_exit"]

    leaderboard = []

    for player in players:
        score = 0.0
        
        w_id = name_to_id.get(player.get('winners', '').strip().lower(), "UNKNOWN_ID")
        r_id = name_to_id.get(player.get('runnersUp', '').strip().lower(), "UNKNOWN_ID")
        d_id = name_to_id.get(player.get('disappointment', '').strip().lower(), "UNKNOWN_ID")
        u_id = name_to_id.get(player.get('underdogs', '').strip().lower(), "UNKNOWN_ID")

        d_standard_name = id_to_name.get(d_id, "Unknown")
        u_standard_name = id_to_name.get(u_id, "Unknown")

        d_sr = get_scaled_ranking(d_standard_name)
        u_sr = get_scaled_ranking(u_standard_name)
        u_multiplier = (1 - u_sr)

        # --- CATEGORY 1: Winner Selection ---
        if w_id == actual_winner_id and actual_winner_id != "TBD": score += 6
        elif w_id == actual_runner_id and actual_runner_id != "TBD": score += 4
        elif w_id in actual_semis: score += 3
        elif w_id in actual_quarters: score += 2
        elif w_id in actual_r16: score += 1
        elif w_id in actual_r32: score += 0.5
        
        # --- CATEGORY 2: Runner-Up Selection ---
        if r_id == actual_runner_id and actual_runner_id != "TBD": score += 6
        elif r_id == actual_winner_id and actual_winner_id != "TBD": score += 4
        elif r_id in actual_semis: score += 3
        elif r_id in actual_quarters: score += 2
        elif r_id in actual_r16: score += 1
        elif r_id in actual_r32: score += 0.5

        # --- CATEGORY 3: Biggest Disappointment ---
        if d_id in actual_group_stage_exit: score += 6 * d_sr
        elif d_id in actual_r32 and d_id not in actual_r16: score += 5 * d_sr
        elif d_id in actual_r16 and d_id not in actual_quarters: score += 4 * d_sr
        elif d_id in actual_quarters and d_id not in actual_semis: score += 3 * d_sr
        elif d_id in actual_semis and d_id != actual_runner_id and d_id != actual_winner_id: score += 2 * d_sr
        elif d_id == actual_runner_id and actual_runner_id != "TBD": score += 1 * d_sr

        # --- CATEGORY 4: Underdogs ---
        if u_id == actual_winner_id and actual_winner_id != "TBD": score += 6 * u_multiplier
        elif u_id == actual_runner_id and actual_runner_id != "TBD": score += 4 * u_multiplier
        elif u_id in actual_semis: score += 3 * u_multiplier
        elif u_id in actual_quarters: score += 2 * u_multiplier
        elif u_id in actual_r16: score += 1 * u_multiplier
        elif u_id in actual_r32: score += 0.5 * u_multiplier

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
        
    print(f"🚀 Fixed ID Engine Sync Successful! Processed {len(leaderboard)} users smoothly.")

if __name__ == "__main__":
    calculate_sweepstake_scores()