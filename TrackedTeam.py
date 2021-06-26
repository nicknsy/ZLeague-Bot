class TrackedTeam:
    def __init__(self):
        self.current_total_points = 0
        self.current_total_games = 0

        self.best_game = 0
        self.second_best_game = 0
        self.is_accurate = True

    def update(self, total_games, total_points):
        if total_points == self.current_total_points:
            self.current_total_games = total_games  # If the game points don't change, no need to do any calculations
        elif self.is_accurate and total_games - self.current_total_games == 1:
            game_points = total_points - self.current_total_points
            self.current_total_games = total_games
            self.current_total_points += game_points

            if game_points > self.best_game:
                self.second_best_game = self.best_game
                self.best_game = game_points
            elif game_points > self.second_best_game:
                self.second_best_game = game_points
        else:
            self.is_accurate = False
