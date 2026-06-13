import os
import sys
import json

# Ensure parent directory is visible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import structural data and normalization from your live app
from src.api_client import (
    API_TOKEN, HEADERS, TEAM_RANKINGS, LOWEST_RANK,
    clean_string, get_scaled_ranking, build_team_id_maps,
    fetch_live_tournament_state, sync_players_from_google_sheets
)

def format_4sf(value):
    """Formats a float to 4 significant figures."""
    if value == 0: return "0.000"
    return f"{float(value):.4g}"

def diagnostic_score_calculator():
    print("=======================================================")
    print("   🏆 SWEEPSTAKE LIVE POINT CALCULATION DIAGNOSTIC 🏆  ")
    print("=======================================================\n")

    # 1. Fetch live API state
    print("1. Syncing with Football-Data API...")
    try:
        name_to_id, id_to_name = build_team_id_maps()
        live = fetch_live_tournament_state(id_to_name)
    except Exception as e:
        print(f"❌ Failed to reach API: {e}")
        return

    # 2. Fetch User Entries
    all_entries = sync_players_from_google_sheets() or []
    
    # Process unique players exactly like in api_client
    unique_players = []
    seen_names = set()
    for p in all_entries:
        name = p.get('name', '').strip()
        if name and name not in seen_names:
            seen_names.add(name)
            unique_players.append(p)

    print(f"   Calculated {len(unique_players)} participant(s).\n")

    # 3. Process each player
    for player in unique_players:
        score = 0.0
        w_id = name_to_id.get(clean_string(player.get('winners')), "UNKNOWN_ID")
        r_id = name_to_id.get(clean_string(player.get('runnersUp')), "UNKNOWN_ID")
        d_id = name_to_id.get(clean_string(player.get('disappointment')), "UNKNOWN_ID")
        u_id = name_to_id.get(clean_string(player.get('underdogs')), "UNKNOWN_ID")

        d_standard_name = id_to_name.get(d_id, "Unknown")
        u_standard_name = id_to_name.get(u_id, "Unknown")

        d_sr = get_scaled_ranking(d_standard_name)
        u_sr = get_scaled_ranking(u_standard_name)
        u_mult = (1 - u_sr)

        print(f"\n👤 PLAYER: {player.get('name')}")
        
        # Winner Logic
        w_pts = 0.0
        if w_id == live["winner"] and live["winner"] != "TBD": w_pts = 6.0
        elif w_id == live["runner_up"] and live["runner_up"] != "TBD": w_pts = 4.0
        elif w_id in live["semis"]: w_pts = 3.0
        elif w_id in live["quarters"]: w_pts = 2.0
        elif w_id in live["r16"]: w_pts = 1.0
        elif w_id in live["r32"]: w_pts = 0.5
        score += w_pts

        # Runner-Up Logic
        r_pts = 0.0
        if r_id == live["runner_up"] and live["runner_up"] != "TBD": r_pts = 6.0
        elif r_id == live["winner"] and live["winner"] != "TBD": r_pts = 4.0
        elif r_id in live["semis"]: r_pts = 3.0
        elif r_id in live["quarters"]: r_pts = 2.0
        elif r_id in live["r16"]: r_pts = 1.0
        elif r_id in live["r32"]: r_pts = 0.5
        score += r_pts

        # Disappointment Logic
        d_pts = 0.0
        if d_id in live["group_stage_exit"]: d_pts = 6 * d_sr
        elif d_id in live["r32"] and d_id not in live["r16"]: d_pts = 5 * d_sr
        elif d_id in live["r16"] and d_id not in live["quarters"]: d_pts = 4 * d_sr
        elif d_id in live["quarters"] and d_id not in live["semis"]: d_pts = 3 * d_sr
        elif d_id in live["semis"] and d_id != live["runner_up"] and d_id != live["winner"]: d_pts = 2 * d_sr
        elif d_id == live["runner_up"] and live["runner_up"] != "TBD": d_pts = 1 * d_sr
        score += d_pts

        # Underdog Logic
        u_pts = 0.0
        if u_id == live["winner"] and live["winner"] != "TBD": u_pts = 6 * u_mult
        elif u_id == live["runner_up"] and live["runner_up"] != "TBD": u_pts = 4 * u_mult
        elif u_id in live["semis"]: u_pts = 3 * u_mult
        elif u_id in live["quarters"]: u_pts = 2 * u_mult
        elif u_id in live["r16"]: u_pts = 1 * u_mult
        elif u_id in live["r32"]: u_pts = 0.5 * u_mult
        score += u_pts

        print(f"  ↳ Winner ({w_pts}) + Runner ({r_pts}) + Disapp ({format_4sf(d_pts)}) + Underdog ({format_4sf(u_pts)})")
        print(f"  ⭐ TOTAL: {format_4sf(score)}")

if __name__ == "__main__":
    diagnostic_score_calculator()