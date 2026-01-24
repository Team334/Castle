def _generate_test_teams(event_key):
    """Generate test teams based on event key"""
    if str(event_key).endswith("test1"):
        start, end = 1, 6
    elif str(event_key).endswith("test2"):
        start, end = 6, 11
    elif str(event_key).endswith("test3"):
        start, end = 11, 16
    else:
        return []
        
    teams = []
    for i in range(start, end):
        teams.append({
            'key': f'frc{i}',
            'team_number': i,
            'nickname': f'Test Team {i}',
            'name': f'Test Team {i}',
            'city': 'Test City',
            'state_prov': 'Test State',
            'country': 'Test Country'
        })
    return teams

def _generate_test_matches(event_key):
    """Generate test matches for 5 teams"""
    teams = [t['key'] for t in _generate_test_teams(event_key)]
    if not teams:
        return {}
        
    formatted_matches = {}
    
    def get_team_number(index):
        return teams[index % len(teams)]

    for i in range(1, 6):
        # Shift starting position for variety
        start_idx = (i - 1) * 2
        
        red_teams = [
            get_team_number(start_idx),
            get_team_number(start_idx + 1),
            get_team_number(start_idx + 2)
        ]
        blue_teams = [
            get_team_number(start_idx + 3),
            get_team_number(start_idx + 4),
            get_team_number(start_idx + 5)
        ]
        
        match_key = f"Qual {i}"
        formatted_matches[match_key] = {
            'red': red_teams,
            'blue': blue_teams,
            'comp_level': 'qm',
            'match_number': i,
            'set_number': 1
        }

    # Playoffs
    formatted_matches["Semifinal 1"] = {
        'red': [teams[0], teams[1], teams[2]],
        'blue': [teams[3], teams[4], teams[0]], # Reuse team 0 to fill
        'comp_level': 'sf',
        'match_number': 1,
        'set_number': 1
    }
    
    formatted_matches["Final 1"] = {
        'red': [teams[0], teams[1], teams[2]],
        'blue': [teams[3], teams[4], teams[0]], # Reuse team 0 to fill
        'comp_level': 'f',
        'match_number': 1,
        'set_number': 1
    }

    return formatted_matches

def _generate_test_rankings(event_key):
    """Generate test rankings"""
    teams = _generate_test_teams(event_key)
    rankings = []
    
    for i, team in enumerate(teams, 1):
        rankings.append({
            'rank': i,
            'team_key': team['key'],
            'team_number': team['team_number'],
            'ranking_points': 2.0 + (1.0 / i), # Fake RP
            'record': {'wins': 5-i, 'losses': i, 'ties': 0},
            'matches_played': 5
        })
        
    return rankings