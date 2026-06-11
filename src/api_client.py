import json

def calculate_sweepstake_scores():
    # 1. Read the user predictions currently stored on GitHub
    try:
        with open('data/users.json', 'r') as file:
            players = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print("No users found to score.")
        return

    # 2. Tournament Outcomes 
    # (As the World Cup plays out, we will update these actual result parameters!)
    actual_winner = "TBD"          # e.g., "Argentina"
    actual_runner_up = "TBD"       # e.g., "England"
    
    # Teams that fail to progress past the Group Stage
    group_stage_dropouts = []      # e.g., ["Germany", "France"]
    
    # Lower-tier teams that make it to the Quarter-finals or further
    successful_underdogs = []      # e.g., ["Uzbekistan", "Haiti"]

    # 3. Score calculation logic matrix
    leaderboard = []
    for player in players:
        score = 0
        
        # Rule A: Correct Winner prediction = 10 points
        if player.get('winners') == actual_winner and actual_winner != "TBD":
            score += 10
            
        # Rule B: Correct Runner-Up prediction = 5 points
        if player.get('runnersUp') == actual_runner_up and actual_runner_up != "TBD":
            score += 5
            
        # Rule C: Correct Disappointment selection = 5 points
        if player.get('disappointment') in group_stage_dropouts:
            score += 5
            
        # Rule D: Correct Underdog prediction = 5 points
        if player.get('underdogs') in successful_underdogs:
            score += 5
            
        # Append calculated total scores back onto the user properties map
        leaderboard.append({
            "name": player['name'],
            "winners": player['winners'],
            "runnersUp": player['runnersUp'],
            "disappointment": player['disappointment'],
            "underdogs": player['underdogs'],
            "totalScore": score
        })

    # 4. Sort the players leaderboard: highest score always at the top
    leaderboard = sorted(leaderboard, key=lambda x: x.get('totalScore', 0), reverse=True)

    # 5. Overwrite the file with the updated score assignments
    with open('data/users.json', 'w') as file:
        json.dump(leaderboard, file, indent=2)
        
    print(f"Successfully processed scoring calculations for {len(leaderboard)} players.")

if __name__ == "__main__":
    calculate_sweepstake_scores()