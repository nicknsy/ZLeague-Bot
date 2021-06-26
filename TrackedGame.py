import time
import requests

from TrackedTeam import TrackedTeam


class TrackedGame:
    tourney_api = "https://zleague-api.herokuapp.com/v2/tournament/{0}"  # id
    standings_api = "https://zleague-api.herokuapp.com/warzone/tournament/{0}/standings/{1}"  # id/standings/division

    def __init__(self, tournament_id, division, team_name, channel, message_id):
        self.tournament_id = tournament_id
        self.division = division
        self.team_name = team_name
        self.channel = channel
        self.message_id = message_id

        self.last_checked = None
        self.stats = {}
        self.teams = {}

    def update(self):
        self.last_checked = int(time.time())

        if "tournament" not in self.stats:
            tournament_request = requests.get(self.tourney_api.format(self.tournament_id))
            self.stats["tournament"] = tournament_request.json()

        standings_request = requests.get(self.standings_api.format(self.tournament_id, self.division))
        self.stats["standings"] = standings_request.json()

        # Update team scores
        standings = self.stats["standings"]
        for team in standings:
            team_name = team["name"]
            if team_name not in self.teams:
                self.teams[team_name] = TrackedTeam()

            self.teams[team_name].update(team["numberOfGames"], team["totalPoints"])
