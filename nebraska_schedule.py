import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import base64
from io import BytesIO

# Helper function to convert image URLs to base64
def image_to_base64(image_url):
    try:
        response = requests.get(image_url)
        img = BytesIO(response.content)
        base64_image = base64.b64encode(img.read()).decode('utf-8')
        return f"data:image/png;base64,{base64_image}"
    except Exception as e:
        print(f"Error loading image from {image_url}: {e}")
        return None

# Function to scrape NCAA football rankings from the official site
def scrape_ncaa_rankings():
    url = "https://www.ncaa.com/rankings/football/fbs/associated-press"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')
    rankings = {}

    if table:
        rows = table.find_all('tr')

        # Loop through rows, skipping the first (header row)
        for row in rows[1:26]:  # Only get top 25 teams
            cells = row.find_all('td')
            rank = cells[0].text.strip()
            team_name = re.sub(r'\s\(\d+\)', '', cells[1].text.strip())

            # Handle special cases for teams like USC
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

        # If no data is returned, break the loop
        if not data:
            break
        
        all_data.extend(data)
        page += 1

    return all_data

# Function to filter for 2024 season based on "name": "Football 2024"
def filter_2024_schedule(all_data):
    filtered_data = [event for event in all_data if event['schedule']['name'] == "Football 2024"]
    return filtered_data

# Helper function to format the date as "Aug 31 (Sat)"
def format_date(date_str, opponent_name=None):
    # Hardcoded dates for Illinois and Iowa games
    if opponent_name == "Illinois":
        return "Sep 20 (Fri)"
    elif opponent_name == "Iowa":
        return "Nov 29 (Fri)"
    
    # Normal date formatting for other games
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
    # Check if game time is marked as "TBA"
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
            return "TBA"  # If scores are None, return "TBA"
    else:
        # If no result, check if there's a datetime for an unplayed game
        if event['datetime']:
            return format_time_to_cst(event['datetime'])
        else:
            return "TBD"  # If no datetime is available

# Function to display rankings correctly
def format_ranking(ranking, team_name, ncaa_rankings):
    if ranking and ranking.isdigit():
        return f"#{ranking}"
    elif team_name in ncaa_rankings:
        return ncaa_rankings[team_name]  # Return scraped ranking from NCAA site
    return ""  # Leave blank if no ranking available

# Helper function to get the next upcoming game based on today's date
def get_upcoming_game(schedule_data):
    today = datetime.now(pytz.timezone('America/Chicago')).date()  # Use date only for comparison
    
    # Find the next game on or after today's date
    for event in schedule_data:
        event_date = datetime.strptime(event['datetime'].split('T')[0], "%Y-%m-%d").date()  # Extract date only
        if event_date >= today:
            return event
    
    # If no future game is found, default to the first game (though this shouldn't happen)
    return schedule_data[0]

# Helper function to get Nebraska odds and betting information
def get_nebraska_odds(upcoming_game_date):
    # Send a request to the Fox Sports page
    url = 'https://www.foxsports.com/college-football/nebraska-cornhuskers-team-odds'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    event_container = soup.find('div', class_='event-container desktop-cards')
    if event_container:
        odds_containers = event_container.find_all('li', class_='entity-odds-container')

        for odds_container in odds_containers:
            # Extract the game date from the odds container
            game_date = odds_container.find('div', class_='odds-component-date')
            if game_date:
                game_date_text = game_date.text.strip()  # e.g., "Sat, Oct 5 at 8:00 PM"
                
                # Extract only "Oct 5" from "Sat, Oct 5 at 8:00 PM"
                odds_month_day = re.search(r'[A-Za-z]+ \d+', game_date_text).group()  # "Oct 5"
                odds_month, odds_day = odds_month_day.split()  # Split into "Oct" and "5"
                odds_day = odds_day.lstrip('0')  # Remove leading zero from day
                odds_month_day = odds_month.lower() + odds_day  # Recombine, e.g., "oct5"

                # Extract only "Oct 05" from "Oct 05 (Sat)" and normalize it for comparison
                upcoming_month_day = re.search(r'[A-Za-z]+ \d+', upcoming_game_date).group()  # "Oct 05"
                upcoming_month, upcoming_day = upcoming_month_day.split()  # Split into "Oct" and "05"
                upcoming_day = upcoming_day.lstrip('0')  # Remove leading zero from day
                upcoming_month_day = upcoming_month.lower() + upcoming_day  # Recombine, e.g., "oct5"

                # Compare the normalized month-day strings
                if odds_month_day == upcoming_month_day:
                    # Extract and return spread and bet description if dates match
                    team_names = odds_container.find_all('div', class_='uc fs-30')
                    spreads = odds_container.find_all('span', class_='ff-ff fs-20 cl-blk')
                    
                    nebraska_spread = ""
                    bet_description = ""
                    
                    if len(team_names) == 2 and len(spreads) == 2:
                        team1_name = team_names[0].text.strip()
                        team2_name = team_names[1].text.strip()
                        team1_spread = spreads[0].text.strip()
                        team2_spread = spreads[1].text.strip()

                        # Determine if 'NEB' is team1 or team2
                        if 'NEB' in team1_name:
                            nebraska_spread = team1_spread
                        else:
                            nebraska_spread = team2_spread

                    # Extract bet description
                    bet_description_container = odds_container.find('div', class_='bet-description')
                    if bet_description_container:
                        bet_description = bet_description_container.text.strip()

                    return nebraska_spread, bet_description

    return None, None


# Generate HTML schedule from filtered data
def generate_html(schedule_data, ncaa_rankings):
    upcoming_game = get_upcoming_game(schedule_data)  # Get the next game based on today's date

    # Extract upcoming game info
    upcoming_opponent = upcoming_game['opponent_name']
    upcoming_opponent_logo_url = image_to_base64(upcoming_game['opponent']['official_logo']['url'])
    upcoming_location = upcoming_game['location']
    upcoming_time = format_time_to_cst(upcoming_game['datetime'])
    upcoming_date = format_date(upcoming_game['datetime'], opponent_name=upcoming_opponent)
    upcoming_tv_logo_url = ""
    
    if upcoming_game['schedule_event_links']:
        for link in upcoming_game['schedule_event_links']:
            if link['icon'] and 'url' in link['icon']:
                upcoming_tv_logo_url = image_to_base64(link['icon']['url'])
                break

    # Get Nebraska odds and betting information
    nebraska_spread, bet_description = get_nebraska_odds(upcoming_date)

    # Generate the HTML content
    html_content = f'''
    <html>
    <head>
        <title>Nebraska Football Schedule 2024</title>
        <style>
            @font-face {{
                font-family: "Liberator";
                src: url("Liberator.ttf") format("truetype");
            }}
            body {{
                font-family: "Liberator", Arial, sans-serif;
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
            .left-section img {{
                width: 50%;
                margin-bottom: 15px;
            }}
            .upcoming-game {{
                background-color: rgba(0, 0, 0, 0.8); /* Black background */
                padding: 20px;
                border-radius: 10px;
            }}
            .upcoming-game h2 {{
                font-size: 28px;
                margin-bottom: 10px;
            }}
            .upcoming-game h1 {{
                font-size: 36px; /* Increase the size of the opponent name */
                margin-bottom: 5px;
                display: inline-block;
                vertical-align: middle;
            }}
            .upcoming-game img {{
                width: 100px;
                vertical-align: middle;
                margin-right: 10px;
            }}
            .game-info {{
                font-size: 18px;
                text-align: left;
            }}
            .game-info td {{
                padding: 1px; /* Tighten the padding */
                border: none; /* Remove grid lines */
                text-align: left; /* Left justify the text */
            }}
            .right-section {{
                width: 66%;
                padding: 20px;
            }}
            table {{
                width: 100%;
                margin-top: 20px;
                border-collapse: collapse;
                background-color: rgba(255, 255, 255, 0.9);
                border: none;
                text-align: left;
                color: black;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }}
            th, td {{
                padding: 8px;
                border: 1px solid black; /* Adds grid lines */
                font-size: 20px;
                line-height: 1.1;
            }}
            th {{
                background-color: rgba(255, 255, 255, 0.7);
                font-weight: bold;
            }}
            td img {{
                vertical-align: middle;
                width: 40px;
                margin-right: 8px;
            }}
            .outcome-w {{
                color: green;
                font-weight: bold;
            }}
            .outcome-l {{
                color: red;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="left-section">
            <img src="Nebraska_Cornhuskers_logo.png" alt="Nebraska Logo">
            <div class="upcoming-game">
                <h2>Upcoming Game:</h2>
                <div class="game-info">
                    <img src="{upcoming_opponent_logo_url}" alt="{upcoming_opponent} Logo">
                    <h1>{upcoming_opponent}</h1><br>
                    <table>
                    <tr>
                        <td>Date: {upcoming_date}</td>
                        <td rowspan="3">{f'<img src="{upcoming_tv_logo_url}" alt="TV Network Logo">' if upcoming_tv_logo_url else ''}</td>
                    </tr>
                    <tr>
                        <td>Time: {upcoming_time}</td>
                    </tr>
                    <tr>
                        <td>Location: {upcoming_location}</td>
                    </tr>
                      <tr>
                        <td colspan="2"style="height: 10px;"></td>
                    </tr>
                    <tr>
                        <td colspan="2">Spread: (NEB) {nebraska_spread if nebraska_spread else 'N/A'}</td>
                    </tr>
                    <tr>
                        <td colspan="2">{bet_description if bet_description else 'N/A'}</td>
                    </tr>
                    </table>
                </div>
            </div>
        </div>
        <div class="right-section">
            <table>
                <tr>
                    <th>Date</th>
                    <th>Opponent</th>
                    <th>Location</th>
                    <th>Result</th>
                </tr>
    '''

    for event in schedule_data:
        # Extracting data
        opponent = event['opponent_name']  # Using opponent_name field now
        date = format_date(event['datetime'], opponent_name=opponent)
        opponent_logo_url = image_to_base64(event['opponent']['official_logo']['url']) if 'official_logo' in event['opponent'] else ''
        location = event['location']
        ranking = format_ranking(event.get('opponent_ranking', ''), opponent, ncaa_rankings)  # Correct ranking logic
        result = format_result(event)
        result_class = "outcome-w" if result.startswith("W") else "outcome-l" if result.startswith("L") else ""
        
        # Building HTML row
        html_content += f'''
        <tr>
            <td>{date}</td>
            <td class="left-align"><img src="{opponent_logo_url}" class="logo" alt="{opponent} logo"> {opponent} {ranking}</td>
            <td>{location}</td>
            <td class="{result_class}">{result}</td>
        </tr>
        '''

    # Closing HTML
    html_content += '''
    </table>
    </div>
    </body>
    </html>
    '''

    # Writing to index.html
    with open("index.html", "w") as file:
        file.write(html_content)

# Main code execution
if __name__ == "__main__":
    all_data = fetch_schedule()  # Fetch schedule data
    filtered_data = filter_2024_schedule(all_data)  # Filter for 2024 season
    ncaa_rankings = scrape_ncaa_rankings()  # Scrape the rankings from the NCAA site
    generate_html(filtered_data, ncaa_rankings)
