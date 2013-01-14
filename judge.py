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
POINTS_PER_GAME = 2.0

POINTS_FULL_SEASON = POINTS_PER_GAME * GAMES_FULL_SEASON
POINTS_FULL_SEASON_IN_CONFERENCE = POINTS_PER_GAME * GAMES_FULL_SEASON_IN_CONFERENCE

class Conference(object):
  """Conference enumeration"""
  EAST = 1
  WEST = 2


def url_read(url):
  """Grab HTML content from the url"""

  urlc = UrlCache(url)
  return urlc.read()

def games_in_short_season():
  """Return a list of (home team, visiting team) pairs for the 2012-2013 season"""

  doc = PyQuery(url_read(SCHEDULE_URL))
  rows = doc('.schedTbl tbody tr').items()

  games = []
  for row in rows:
    games.append(tuple(t.text() for t in row.items('td.team')))

  return games

def calc_pp_delta(conf):
  """Return the change in team points percentages resulting from the oss of
  inter-conference games"""

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

      points_pct[team] = (pct_in_conf - pct) / pct

  return points_pct

def calc_metric_from_div_standings(conf, extract_func):
  """Calculate a metric, using extract_func, for a conference"""

  url = VS_EAST_URL if conf == Conference.WEST else VS_WEST_URL
  doc = PyQuery(url_read(url))

  div_tables = list(doc('.Division').items())
  east_t, west_t = (div_tables[:3], div_tables[3:])

  return extract_func(east_t if conf == Conference.EAST else west_t)

def pp_delta_conf_only():
  """Return the change in points percentage for both conferences due to
  loss of inter-conference games"""

  west = calc_metric_from_div_standings(Conference.WEST, calc_pp_delta)
  east = calc_metric_from_div_standings(Conference.EAST, calc_pp_delta)

  return (east, west)

def points_percentages(conf):
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

      pct_in_conf = (points-vs_points) / POINTS_FULL_SEASON_IN_CONFERENCE

      points_pct[team] = pct_in_conf

  return points_pct

def team_schedules(games):
  """Given the output of games_in_short_season, return a dict of team-schedule pairs"""

  schedules = defaultdict(list)

  for home, visitor in games:
    schedules[home].append(visitor)
    schedules[visitor].append(home)

  return schedules

def mopp(opponents, pct):
  """Return the mean opponent's points percentage for a team"""

  win_pcts = [pct[team] for team in opponents]
  return sum(win_pcts) / len(win_pcts)

def divisions_from_conference(conf):
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

def mopp_delta(standings_tables, all_games_2013, points_pct):
  """Return the relative change in the schedule difficulty between the
  2013-2012 and 2012-2011 seasons for teams in a conference"""

  divisions = divisions_from_conference(standings_tables)
  conference = set.union(*divisions)

  games_2012 = list(chain.from_iterable(full_home_schedule(t, divisions) for t in conference))
  scheds_2012 = team_schedules(games_2012)

  games_2013 = [g for g in all_games_2013 if g[0] in conference]
  scheds_2013 = team_schedules(games_2013)

  diff_2013 = {team: mopp(schedule, points_pct) for team, schedule in scheds_2013.items()}
  diff_2012 = {team: mopp(schedule, points_pct) for team, schedule in scheds_2012.items()}

  return {t: (diff_2013[t] - diff_2012[t])/diff_2012[t] for t in conference}

def league_mopp():
  """Return a pair of dictionaries, containing the relative change in the
  mean opponent's point percentage"""

  west = calc_metric_from_div_standings(Conference.WEST, points_percentages)
  east = calc_metric_from_div_standings(Conference.EAST, points_percentages)

  points_pct = dict(list(west.items()) + list(east.items()))

  doc = PyQuery(url_read(STANDINGS_URL))
  div_tables = list(doc('.Division').items())

  east_t, west_t = (div_tables[:3], div_tables[3:])

  all_games_2013 = games_in_short_season()

  return (mopp_delta(east_t, all_games_2013, points_pct),
          mopp_delta(west_t, all_games_2013, points_pct))

def print_results(results):
  """Print a formatted table for the change in schedule difficult for teams
  in a conference"""

  for team, diff in sorted(results.items(), key = operator.itemgetter(1)):
    dp = diff * 100
    ds = '%.3f' % dp if diff < 0 else '+%.3f' % dp
    print('%s %s %%' % (team.ljust(20), ds))


######################################################################
# Main
######################################################################

if __name__ == '__main__':
  east_diff, west_diff = league_mopp()

  header = """\
2012-2013 NHL Schedule Difficulty by Team (easiest to hardest)

Team                 Difficulty
--------------------------------------------------------------"""

  print(header)

  print_results(east_diff)
  print()
  print_results(west_diff)
