import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import pytz
import os
import json

# Helper functions for caching
def get_cached_data(file_path, max_age_hours):
    if os.path.exists(file_path):
        file_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        if datetime.now() - file_modified_time < timedelta(hours=max_age_hours):
            with open(file_path, 'r') as file:
                return json.load(file)
    return None

def save_cache_data(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file)

# Function to scrape NCAA football rankings from the official site
def scrape_ncaa_rankings():
    url = "https://www.ncaa.com/rankings/football/fbs/associated-press"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')
    rankings = {}

    if table:
        rows = table.find_all('tr')

        for row in rows[1:26]:  # Only get top 25 teams
            cells = row.find_all('td')
            rank = cells[0].text.strip()
            team_name = re.sub(r'\s\(\d+\)', '', cells[1].text.strip())

            if "Southern Cal" in team_name or "Southern California" in team_name:
                team_name = "USC"

            rankings[team_name] = f"#{rank}"
    
    return rankings

# Function to fetch football schedule across multiple pages
def fetch_schedule():
    all_data = []
    page = 1
    while True:
        url = f"https://huskers.com/website-api/schedule-events?filter%5Bschedule.sport_id%5D=5&per_page=100&sort=datetime&include=opponent.officialLogo,opponent.customLogo,opponentLogo,schedule.sport,scheduleEventLinks.icon,scheduleEventResult,secondOpponent.officialLogo,secondOpponent.customLogo,secondOpponentLogo,postEventArticle&neutral_event=false&page={page}"
        response = requests.get(url)
        data = response.json()['data']

        if not data:
            break
        
        all_data.extend(data)
        page += 1

    return all_data

# Function to filter for 2024 season based on "name": "Football 2024"
def filter_2024_schedule(all_data):
    return [event for event in all_data if event['schedule']['name'] == "Football 2024"]

# Helper function to format the date as "Aug 31 (Sat)"
def format_date(date_str, opponent_name=None):
    if opponent_name == "Illinois":
        return "Sep 20 (Fri)"
    elif opponent_name == "Iowa":
        return "Nov 29 (Fri)"
    
    date_obj = datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
    return date_obj.strftime("%b %d (%a)")

# Helper function to convert UTC to CST and format the game time
def format_time_to_cst(utc_time_str):
    cst = pytz.timezone('America/Chicago')
    utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    cst_time = utc_time.replace(tzinfo=pytz.utc).astimezone(cst)
    return cst_time.strftime("%I:%M %p CST")

# Helper function to handle result and score display
def format_result(event):
    if 'tba' in event and event['tba'] == "time_tba":
        return "TBA"
    
    if 'schedule_event_result' in event and event['schedule_event_result']['result']:
        result_data = event['schedule_event_result']
        winning_score = result_data['winning_score']
        losing_score = result_data['losing_score']

        if winning_score is not None and losing_score is not None:
            winning_score = int(float(winning_score))
            losing_score = int(float(losing_score))

            if result_data['result'] == 'win':
                return f"W {winning_score}-{losing_score}"
            else:
                return f"L {losing_score}-{winning_score}"
        else:
            return "TBA"
    else:
        if event['datetime']:
            return format_time_to_cst(event['datetime'])
        else:
            return "TBD"

# Function to display rankings correctly
def format_ranking(ranking, team_name, ncaa_rankings):
    if ranking and ranking.isdigit():
        return f"#{ranking}"
    elif team_name in ncaa_rankings:
        return ncaa_rankings[team_name]
    return ""

# Helper function to get the next upcoming game based on today's date
def get_upcoming_game(schedule_data):
    today = datetime.now(pytz.timezone('America/Chicago')).date()
    
    for event in schedule_data:
        event_date = datetime.strptime(event['datetime'].split('T')[0], "%Y-%m-%d").date()
        if event_date >= today:
            return event
    
    return schedule_data[0]

# Helper function to get Nebraska odds and betting information
def get_nebraska_odds(upcoming_game_date):
    url = 'https://www.foxsports.com/college-football/nebraska-cornhuskers-team-odds'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    event_container = soup.find('div', class_='event-container desktop-cards')
    if event_container:
        odds_containers = event_container.find_all('li', class_='entity-odds-container')

        for odds_container in odds_containers:
            game_date = odds_container.find('div', class_='odds-component-date')
            if game_date:
                game_date_text = game_date.text.strip()
                odds_month_day = re.search(r'[A-Za-z]+ \d+', game_date_text).group()
                odds_month, odds_day = odds_month_day.split()
                odds_day = odds_day.lstrip('0')
                odds_month_day = odds_month.lower() + odds_day

                upcoming_month_day = re.search(r'[A-Za-z]+ \d+', upcoming_game_date).group()
                upcoming_month, upcoming_day = upcoming_month_day.split()
                upcoming_day = upcoming_day.lstrip('0')
                upcoming_month_day = upcoming_month.lower() + upcoming_day

                if odds_month_day == upcoming_month_day:
                    team_names = odds_container.find_all('div', class_='uc fs-30')
                    spreads = odds_container.find_all('span', class_='ff-ff fs-20 cl-blk')

                    nebraska_spread = ""
                    bet_description = ""

                    if len(team_names) == 2 and len(spreads) == 2:
                        team1_name = team_names[0].text.strip()
                        team2_name = team_names[1].text.strip()
                        team1_spread = spreads[0].text.strip()
                        team2_spread = spreads[1].text.strip()

                        if 'NEB' in team1_name:
                            nebraska_spread = team1_spread
                        else:
                            nebraska_spread = team2_spread

                    bet_description_container = odds_container.find('div', class_='bet-description')
                    if bet_description_container:
                        bet_description = bet_description_container.text.strip()

                    return nebraska_spread, bet_description

    return None, None

# Generate HTML schedule from filtered data
def generate_html(schedule_data, ncaa_rankings):
    upcoming_game = get_upcoming_game(schedule_data)

    upcoming_opponent = upcoming_game['opponent_name']
    upcoming_opponent_logo_url = upcoming_game['opponent']['official_logo']['url']
    upcoming_location = upcoming_game['location']
    upcoming_time = format_time_to_cst(upcoming_game['datetime'])
    upcoming_date = format_date(upcoming_game['datetime'], opponent_name=upcoming_opponent)
    upcoming_tv_logo_url = ""

    if upcoming_game['schedule_event_links']:
        for link in upcoming_game['schedule_event_links']:
            if link['icon'] and 'url' in link['icon']:
                upcoming_tv_logo_url = link['icon']['url']
                break

    nebraska_spread, bet_description = get_nebraska_odds(upcoming_date)

    html_content = f'''
    <html>
    <head>
        <title>Nebraska Football Schedule 2024</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: url('Memorial Stadium Picture.jpg') no-repeat center center fixed;
                background-size: cover;
                padding: 20px;
                color: white;
                font-size: 24px;
                display: flex;
                justify-content: space-between;
            }}
            .left-section {{
                width: 33%;
                text-align: middle;
                padding: 20px;
            }}
            .upcoming-game {{
                background-color: rgba(0, 0, 0, 0.8);
                padding: 20px;
                border-radius: 10px;
            }}
            .upcoming-game img {{
                width: 100px;
                vertical-align: middle;
                margin-right: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="left-section">
            <img src="Nebraska_Cornhuskers_logo.png" alt="Nebraska Logo">
            <div class="upcoming-game">
                <h2>Upcoming Game</h2>
                <div class="game-info">
                    <img src="{upcoming_opponent_logo_url}" alt="{upcoming_opponent} Logo">
                    <h1>{upcoming_opponent}</h1><br>
                    Date: {upcoming_date}<br>
                    Time: {upcoming_time}<br>
                    Location: {upcoming_location}<br>
                    Spread: (NEB) {nebraska_spread if nebraska_spread else 'N/A'}<br>
                    {bet_description if bet_description else 'N/A'}
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

    with open("index.html", "w") as file:
        file.write(html_content)

# Main code execution with caching

# Cache configuration
rankings_cache_file = "ncaa_rankings_cache.json"
schedule_cache_file = "schedule_cache.json"
odds_cache_file = "odds_cache.json"

rankings_cache = get_cached_data(rankings_cache_file, max_age_hours=24 * 7)  # Cache for one week
schedule_cache = get_cached_data(schedule_cache_file, max_age_hours=24)  # Cache for one day
odds_cache = get_cached_data(odds_cache_file, max_age_hours=1)  # Cache for one hour

# Fetch rankings, schedule, and odds with caching
if rankings_cache:
    ncaa_rankings = rankings_cache
else:
    ncaa_rankings = scrape_ncaa_rankings()
    save_cache_data(rankings_cache_file, ncaa_rankings)

if schedule_cache:
    filtered_data = schedule_cache
else:
    all_data = fetch_schedule()
    filtered_data = filter_2024_schedule(all_data)
    save_cache_data(schedule_cache_file, filtered_data)

# Generate HTML with the latest data
generate_html(filtered_data, ncaa_rankings)
