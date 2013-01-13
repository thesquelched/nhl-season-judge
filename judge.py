######################################################################
# NOTE: Compare to normal 82 game season, minus interconference games
######################################################################

from cache import UrlCache

import requests
import operator
import re
from itertools import chain, repeat
from pyquery import PyQuery
from collections import defaultdict

# nhl.com urls
SCHEDULE_URL = 'http://www.nhl.com/ice/schedulebyseason.htm?season=20122013&gameType=2&team=&network=&venue='
STANDINGS_URL = 'http://www.nhl.com/ice/standings.htm?season=20112012&type=DIV'

# Constants
POINTS_IN_FULL_SEASON = 164.0

def url_read(url):
  """Grab HTML content from the url"""

  urlc = UrlCache(url)
  return urlc.read()

def find_games():
  """Return a list of (home team, visiting team) pairs for the 2012-2013 season"""

  doc = PyQuery(url_read(SCHEDULE_URL))
  rows = doc('.schedTbl tbody tr').items()

  games = []
  for row in rows:
    games.append(tuple(t.text() for t in row.items('td.team')))

  return games

def extract_standings(conf):
  points_pct = dict()

  for division in conf:
    for row in division('tbody tr').items():
      columns = list(row('td').items())
      if len(columns) < 8: continue
      team, points = columns[1].text(), int(columns[6].text())

      # Remove prefixes for the top 8 teams in each conference (e.g. clinched
      # division)
      team = re.sub(r'[a-z] - ', '', team)

      points_pct[team] = points / POINTS_IN_FULL_SEASON

  return points_pct

def find_standings(*conferences):
  """Return a dict of NHL teams and their respective points percentages"""

  points_pct = dict()

  east, west = map(extract_standings, conferences)
  points_pct = dict(list(east.items()) + list(west.items()))

  return points_pct

def extract_schedules(games):
  """Given the output of find_games, return a dict of team-schedule pairs"""

  schedules = defaultdict(list)

  for home, visitor in games:
    schedules[home].append(visitor)
    schedules[visitor].append(home)

  return schedules

def difficulty(opponents, pct):
  """Return the difficulty of a schedule, as determined by the mean of the
  opponents' points percentages"""

  win_pcts = [pct[team] for team in opponents]
  return sum(win_pcts) / len(win_pcts)

def separate_divisions(conf):
  divisions = []

  for div in conf:
    division = set()

    for team in div('tbody tr td:nth-child(2)').items():
      name = re.sub(r'[a-z] - ', '', team.text())
      division.add(name)

    divisions.append(division)

  return divisions

def full_home_schedule(team, divisions):
  my_div = next(d for d in divisions if team in d)
  conf = set.union(*list(d for d in divisions if team not in d))

  div_matchups = [(team, t) for t in my_div if t != team]
  conf_matchups = [(team, t) for t in conf]

  div_sched = chain.from_iterable(repeat(m, 3) for m in div_matchups)
  conf_sched = chain.from_iterable(repeat(m, 2) for m in conf_matchups)

  return list(div_sched) + list(conf_sched)

def determine_difficulty():
  """Return a dict of team-difficulty pairs"""

  doc = PyQuery(url_read(STANDINGS_URL))

  div_tables = list(doc('.Division').items())
  east_t, west_t = (div_tables[:3], div_tables[3:])

  east_divs, west_divs = map(separate_divisions, (east_t, west_t))
  east, west = tuple(set.union(*d) for d in (east_divs, west_divs))

  east_games_2012 = list(chain.from_iterable(full_home_schedule(t, east_divs) for t in east))
  west_games_2012 = list(chain.from_iterable(full_home_schedule(t, west_divs) for t in west))

  east_scheds_2012 = extract_schedules(east_games_2012)
  west_scheds_2012 = extract_schedules(west_games_2012)

  points_pct = find_standings(east_t, west_t)
  scheds_2013 = extract_schedules(find_games())

  return {team: difficulty(schedule, points_pct) for team, schedule in scheds_2013.items()}

if __name__ == '__main__':
  team_diffs = determine_difficulty()

  header = """\
2012-2013 NHL Schedule Difficulty by Team (easiest to hardest)

Team                 Difficulty
--------------------------------------------------------------"""

  print(header)

  for team, diff in sorted(team_diffs.items(), key = operator.itemgetter(1)):
    print(team.ljust(20), diff)
