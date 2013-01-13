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
VS_EAST_URL = 'http://www.nhl.com/ice/standings.htm?season=20112012&type=XVE'
VS_WEST_URL = 'http://www.nhl.com/ice/standings.htm?season=20112012&type=XVW'

# Constants
GAMES_FULL_SEASON = 82
GAMES_FULL_SEASON_IN_CONFERENCE = 64
POINTS_FULL_SEASON = 2.0 * GAMES_FULL_SEASON
POINTS_FULL_SEASON_IN_CONFERENCE = 2.0 * GAMES_FULL_SEASON_IN_CONFERENCE

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

def _extract_vs_standings(conf):
  """Return the points percentage of each team from the 2011-2012 season"""

  points_pct = dict()

  for division in conf:
    for row in division('tbody tr').items():
      columns = list(row('td').items())
      if len(columns) < 8: continue
      team, points, record = columns[1].text(), int(columns[6].text()), columns[8].text()

      # Remove prefixes for the top 8 teams in each conference (e.g. clinched
      # division)
      team = re.sub(r'[a-z] - ', '', team)

      wins, losses, otl = map(int, record.split('-'))
      vs_points = wins*2 + otl

      pct = points / POINTS_FULL_SEASON
      pct_in_conf = (points-vs_points) / POINTS_FULL_SEASON_IN_CONFERENCE

      #print(team, points, vs_points, pct, pct_in_conf)

      points_pct[team] = (pct_in_conf - pct) / pct

  return points_pct

def _versus_standings(url, conf):
  doc = PyQuery(url_read(url))

  div_tables = list(doc('.Division').items())
  east_t, west_t = (div_tables[:3], div_tables[3:])

  if conf == 'east':
    return _extract_vs_standings(east_t)
  else:
    return _extract_vs_standings(west_t)

def find_versus_standings():
  west = _versus_standings(VS_EAST_URL, 'west')
  east = _versus_standings(VS_WEST_URL, 'east')

  return (east, west)

def _extract_standings(conf):
  """Return the points percentage of each team from the 2011-2012 season"""

  points_pct = dict()

  for division in conf:
    for row in division('tbody tr').items():
      columns = list(row('td').items())
      if len(columns) < 8: continue
      team, points = columns[1].text(), int(columns[6].text())

      # Remove prefixes for the top 8 teams in each conference (e.g. clinched
      # division)
      team = re.sub(r'[a-z] - ', '', team)

      points_pct[team] = points / POINTS_FULL_SEASON

  return points_pct

def extract_standings(*conferences):
  """Return a dict of NHL teams and their respective points percentages"""

  points_pct = dict()

  east, west = map(_extract_standings, conferences)
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
  """Return a list of sets, each containing the teams in a division"""

  divisions = []

  for div in conf:
    division = set()

    for team in div('tbody tr td:nth-child(2)').items():
      name = re.sub(r'[a-z] - ', '', team.text())
      division.add(name)

    divisions.append(division)

  return divisions

def full_home_schedule(team, divisions):
  """Calculate the in-conference schedule for a given team in a regular,
  82-game season"""

  my_div = next(d for d in divisions if team in d)
  conf = set.union(*list(d for d in divisions if team not in d))

  div_matchups = [(team, t) for t in my_div if t != team]
  conf_matchups = [(team, t) for t in conf]

  div_sched = chain.from_iterable(repeat(m, 3) for m in div_matchups)
  conf_sched = chain.from_iterable(repeat(m, 2) for m in conf_matchups)

  return list(div_sched) + list(conf_sched)

def conf_difficulties(standings_tables, all_games_2013, points_pct):
  """Return the relative change in the schedule difficulty between the
  2013-2012 and 2012-2011 seasons for teams in a conference"""

  divisions = separate_divisions(standings_tables)
  conference = set.union(*divisions)

  games_2012 = list(chain.from_iterable(full_home_schedule(t, divisions) for t in conference))
  scheds_2012 = extract_schedules(games_2012)

  games_2013 = [g for g in all_games_2013 if g[0] in conference]
  scheds_2013 = extract_schedules(games_2013)

  diff_2013 = {team: difficulty(schedule, points_pct) for team, schedule in scheds_2013.items()}
  diff_2012 = {team: difficulty(schedule, points_pct) for team, schedule in scheds_2012.items()}

  return {t: (diff_2013[t] - diff_2012[t])/diff_2012[t] for t in conference}

def schedule_difficulties(url):
  """Return a dict of team-difficulty pairs"""

  doc = PyQuery(url_read(url))

  div_tables = list(doc('.Division').items())

  east_t, west_t = (div_tables[:3], div_tables[3:])
  points_pct = extract_standings(east_t, west_t)

  all_games_2013 = find_games()

  return (conf_difficulties(east_t, all_games_2013, points_pct),
          conf_difficulties(west_t, all_games_2013, points_pct))

def display_difficulty(diff):
  """Print a formatted table for the change in schedule difficult for teams
  in a conference"""

  for team, diff in sorted(diff.items(), key = operator.itemgetter(1)):
    dp = diff * 100
    ds = '%.3f' % dp if diff < 0 else '+%.3f' % dp
    print('%s %s %%' % (team.ljust(20), ds))


if __name__ == '__main__':
  east_diff, west_diff = schedule_difficulties(STANDINGS_URL)

  header = """\
2012-2013 NHL Schedule Difficulty by Team (easiest to hardest)

Team                 Difficulty
--------------------------------------------------------------"""

  print(header)

  display_difficulty(east_diff)
  print()
  display_difficulty(west_diff)
