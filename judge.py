import requests
import operator
import re
from pyquery import PyQuery
from collections import defaultdict

SCHEDULE_URL = 'http://www.nhl.com/ice/schedulebyseason.htm?season=20122013&gameType=2&team=&network=&venue='
STANDINGS_URL = 'http://www.nhl.com/ice/standings.htm?season=20112012&type=CON#?navid=nav-stn-main'


def pull(url):
  """Grab HTML content from the url"""

  resp = requests.get(url)

  if resp.ok:
    return resp.content
  else:
    return None

def find_games():
  """Return a list of (home team, visiting team) pairs for the 2012-2013 season"""

  doc = PyQuery(pull(SCHEDULE_URL))
  rows = doc('.schedTbl tbody tr').items()

  games = []
  for row in rows:
    games.append(tuple(t.text() for t in row.items('td.team')))

  return games

def find_standings():
  """Return a dict of NHL teams and their respective points percentages"""

  points_pct = dict()
  POSSIBLE_POINTS = 164.0

  doc = PyQuery(pull(STANDINGS_URL))

  for row in doc('.Conference tbody tr').items():
    columns = list(row('td').items())
    if len(columns) < 8: continue
    team, points = columns[1].text(), int(columns[7].text())

    # Remove prefixes for the top 8 teams in each conference (e.g. clinched
    # division)
    team = re.sub(r'[a-z] - ', '', team)

    points_pct[team] = points / POSSIBLE_POINTS

  return points_pct

def extract_schedules(games):
  """Given the output of find_games, return a dict of team-schedule pairs"""

  schedules = defaultdict(list)

  for home, visitor in games:
    schedules[home].append(visitor)

  return schedules

def difficulty(opponents, pct):
  """Return the difficulty of a schedule, as determined by the mean of the
  opponents' points percentages"""

  win_pcts = [pct[team] for team in opponents]
  return sum(win_pcts) / len(win_pcts)

def determine_difficulty():
  """Return a dict of team-difficulty pairs"""

  schedules = extract_schedules(find_games())
  points_pct = find_standings()

  return {team: difficulty(schedule, points_pct) for team, schedule in schedules.items()}

if __name__ == '__main__':
  team_diffs = determine_difficulty()

  for team, diff in sorted(team_diffs.items(), key = operator.itemgetter(1)):
    print(team, diff)
