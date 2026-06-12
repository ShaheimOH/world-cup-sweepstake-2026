import os
import sys
import requests
import json

# Ensure parent directory is visible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import structural data and normalization from your live app
from src.api_client import (
    API_TOKEN, HEADERS, TEAM_RANKINGS, LOWEST_RANK,
    clean_string, get_scaled_ranking, build_team_id_maps,
    fetch_live_tournament_state, sync_players_from_google_sheets
)

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
        print(f"❌ Failed to reach API or parse matrix: {e}")
        return

    # Extract live pools
    actual_winner = live["winner"]
    actual_runner = live["runner_up"]
    actual_semis = live["semis"]
    actual_quarters = live["quarters"]
    actual_r16 = live["r16"]
    actual_r32 = live["r32"]
    actual_exits = live["group_stage_exit"]

    # 2. Fetch User Entries
    print("\n2. Fetching User Submissions...")
    players = sync_players_from_google_sheets() or []
    
    webhook_players = []
    try:
        with open('data/raw_submissions.json', 'r') as file:
            webhook_players = json.load(file)
            if not isinstance(webhook_players, list):
                webhook_players = [webhook_players]
    except:
        pass

    all_entries = players + webhook_players
    seen_names = set()
    unique_players = []
    
    for p in all_entries:
        name = p.get('name', '').strip()
        if name and name not in seen_names:
            seen_names.add(name)
            unique_players.append(p)

    print(f"   Found {len(unique_players)} unique participant(s) to calculate.\n")
    print("=" * 70)

    # 3. Process each player with explicit terminal breakdown
    for player in unique_players:
        p_name = player.get('name')
        p_winner = player.get('winners')
        p_runner = player.get('runnersUp')
        p_disapp = player.get('disappointment')
        p_underdog = player.get('underdogs')

        print(f"\n👤 PLAYER: {p_name.upper()}")
        print("-" * 40)

        # Resolve IDs
        w_id = name_to_id.get(clean_string(p_winner), "UNKNOWN")
        r_id = name_to_id.get(clean_string(p_runner), "UNKNOWN")
        d_id = name_to_id.get(clean_string(p_disapp), "UNKNOWN")
        u_id = name_to_id.get(clean_string(p_underdog), "UNKNOWN")

        total_score = 0.0

        # --- Winner Calculation ---
        w_pts = 0.0
        if w_id != "UNKNOWN":
            if w_id == actual_winner and actual_winner != "TBD": w_pts = 6.0
            elif w_id == actual_runner and actual_runner != "TBD": w_pts = 4.0
            elif w_id in actual_semis: w_pts = 3.0
            elif w_id in actual_quarters: w_pts = 2.0
            elif w_id in actual_r16: w_pts = 1.0
            elif w_id in actual_r32: w_pts = 0.5
        total_score += w_pts
        print(f"  ↳ Winner Pick: [{p_winner:<15}] -> Map Status: {'OK' if w_id != 'UNKNOWN' else '❌ UNKNOWN'} | Points: {w_pts}")

        # --- Runner-Up Calculation ---
        r_pts = 0.0
        if r_id != "UNKNOWN":
            if r_id == actual_runner and actual_runner != "TBD": r_pts = 6.0
            elif r_id == actual_winner and actual_winner != "TBD": r_pts = 4.0
            elif r_id in actual_semis: r_pts = 3.0
            elif r_id in actual_quarters: r_pts = 2.0
            elif r_id in actual_r16: r_pts = 1.0
            elif r_id in actual_r32: r_pts = 0.5
        total_score += r_pts
        print(f"  ↳ Runner Pick: [{p_runner:<15}] -> Map Status: {'OK' if r_id != 'UNKNOWN' else '❌ UNKNOWN'} | Points: {r_pts}")

        # --- Disappointment Calculation ---
        d_pts = 0.0
        if d_id != "UNKNOWN":
            d_name = id_to_name.get(d_id, "Unknown")
            d_sr = get_scaled_ranking(d_name)
            
            if d_id in actual_exits: base = 6
            elif d_id in actual_r32 and d_id not in actual_r16: base = 5
            elif d_id in actual_r16 and d_id not in actual_quarters: base = 4
            elif d_id in actual_quarters and d_id not in actual_semis: base = 3
            elif d_id in actual_semis and d_id != actual_runner and d_id != actual_winner: base = 2
            elif d_id == actual_runner and actual_runner != "TBD": base = 1
            else: base = 0
            
            d_pts = round(base * d_sr, 2)
            print(f"  ↳ Disapp Pick: [{p_disapp:<15}] -> Weight multiplier (Rank {TEAM_RANKINGS.get(d_name, 73)}/73): {d_sr:.2f} | Points: {d_pts}")
        else:
            print(f"  ↳ Disapp Pick: [{p_disapp:<15}] -> Map Status: ❌ UNKNOWN | Points: 0.0")

        # --- Underdog Calculation ---
        u_pts = 0.0
        if u_id != "UNKNOWN":
            u_name = id_to_name.get(u_id, "Unknown")
            u_sr = get_scaled_ranking(u_name)
            u_mult = round(1 - u_sr, 2)
            
            if u_id == actual_winner and actual_winner != "TBD": base = 6
            elif u_id == actual_runner and actual_runner != "TBD": base = 4
            elif u_id in actual_semis: base = 3
            elif u_id in actual_quarters: base = 2
            elif u_id in actual_r16: base = 1
            elif u_id in actual_r32: base = 0.5
            else: base = 0
            
            u_pts = round(base * u_mult, 2)
            print(f"  ↳ Underdg Pick: [{p_underdog:<15}] -> Weight multiplier (Rank {TEAM_RANKINGS.get(u_name, 73)}/73): {u_mult:.2f} | Points: {u_pts}")
        else:
            print(f"  ↳ Underdg Pick: [{p_underdog:<15}] -> Map Status: ❌ UNKNOWN | Points: 0.0")

        print(f"  ⭐ TOTAL CALCULATED SCORE: {round(total_score, 2)}")
        print("-" * 40)

    print("\n=======================================================")
    print("             DIAGNOSTIC RUN COMPLETED                  ")
    print("=======================================================")

if __name__ == "__main__":
    diagnostic_score_calculator()