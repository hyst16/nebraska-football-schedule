import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz

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
    filtered_data = [event for event in all_data if event['schedule']['name'] == "Football 2024"]
    return filtered_data

# Helper function to format the date as "Aug 31 (Sat)"
def format_date(date_str, opponent_name=None):
    if opponent_name == "Illinois":
        return "Sep 20 (Fri)"
    elif opponent_name == "Iowa":
        return "Nov 29 (Fri)"
    
    date_obj = datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
    return date_obj.strftime("%b %d (%a)")

# Helper function to convert UTC to CST and format the game time without leading zeros
def format_time_to_cst(utc_time_str):
    cst = pytz.timezone('America/Chicago')
    utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    cst_time = utc_time.replace(tzinfo=pytz.utc).astimezone(cst)
    return cst_time.strftime("%I:%M %p CST").lstrip('0')  # Remove leading zero

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

# Function to get football rankings from NCAA website
def get_football_rankings():
    url = "https://www.ncaa.com/rankings/football/fbs/associated-press"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')
    rankings = {}
    rows = table.find_all('tr')

    for row in rows[1:26]:
        cells = row.find_all('td')
        rank = cells[0].text.strip()
        team_name = re.sub(r'\s\(\d+\)', '', cells[1].text.strip())

        # Normalize USC variations
        if team_name in ["Southern California", "Southern Cal"]:
            team_name = "USC"

        rankings[team_name] = f"#{rank}"

    return rankings

# Generate HTML schedule from filtered data
def generate_html(schedule_data, rankings):
    html_content = '''
    <html>
    <head>
        <title>Nebraska Football Schedule 2024</title>
        <style>
            body {
                font-family: Arial, sans-serif;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            table, th, td {
                border: 1px solid black;
            }
            th, td {
                padding: 10px;
                text-align: left;
            }
            .logo {
                height: 50px;
            }
            .tv-logo {
                height: 30px;
            }
        </style>
    </head>
    <body>
    <h1>Nebraska Football Schedule 2024</h1>
    <table>
        <tr>
            <th>Date</th>
            <th>Opponent</th>
            <th>Opponent Logo</th>
            <th>Location</th>
            <th>Ranking</th>
            <th>Result</th>
            <th>TV Network</th>
        </tr>
    '''
    
    for event in schedule_data:
        opponent = event['opponent_name']
        date = format_date(event['datetime'], opponent_name=opponent)
        opponent_logo_url = event['opponent']['official_logo']['url'] if 'official_logo' in event['opponent'] else ''
        location = event['location']
        result = format_result(event)

        # Check if opponent is ranked from the NCAA rankings or the event API
        if result == "TBA" and opponent in rankings:
            ranking = rankings[opponent]
        else:
            ranking = f"#{event['opponent_ranking']}" if event.get('opponent_ranking') else ""

        # Extracting TV network logo URL, leave blank if no TV logo
        tv_network_logo = ''
        if event['schedule_event_links']:
            for link in event['schedule_event_links']:
                if link['icon'] and 'url' in link['icon']:
                    tv_network_logo = link['icon']['url']
                    break

        html_content += f'''
        <tr>
            <td>{date}</td>
            <td>{opponent}</td>
            <td><img src="{opponent_logo_url}" class="logo" alt="{opponent} logo"></td>
            <td>{location}</td>
            <td>{ranking}</td>
            <td>{result}</td>
            <td>{f'<img src="{tv_network_logo}" class="tv-logo" alt="TV Network Logo">' if tv_network_logo else ''}</td>
        </tr>
        '''
    
    html_content += '''
    </table>
    </body>
    </html>
    '''
    
    with open("index.html", "w") as file:
        file.write(html_content)
    
    print("Schedule HTML generated!")

if __name__ == "__main__":
    all_data = fetch_schedule()
    filtered_data = filter_2024_schedule(all_data)
    rankings = get_football_rankings()
    generate_html(filtered_data, rankings)
