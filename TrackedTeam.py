class TrackedTeam:
    def __init__(self):
        self.current_total_points = 0
        self.current_total_games = 0

        self.best_game = 0
        self.second_best_game = 0
        self.is_accurate = True

    def update(self, total_games, total_points):
        if total_points == self.current_total_points:
            self.current_total_games = total_games
        elif self.is_accurate:
            # Even if a team plays multiple games before a score update occurs,
            # it only matters if the number of points they got in that time
            # is enough to have potentially replaced both the first and second best games.
            # Since getting a score higher than the first best would cause that score to become
            # the second best, a score that is big enough to replace the (current) best game
            # two times over is required before the calculation becomes inaccurate.
            if total_games - self.current_total_games > 1 and total_points >= (self.best_game + 1) * 2:
                self.is_accurate = False
                return

            game_points = total_points - self.best_game
            self.current_total_games = total_games
            self.current_total_points = total_points

            if game_points > self.best_game:
                self.second_best_game = self.best_game
                self.best_game = game_points
            else:
                self.second_best_game = game_points
