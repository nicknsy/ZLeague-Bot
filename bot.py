import discord
import time
import requests
import configparser
import imgkit
import sys
import os
import re

from TrackedGame import TrackedGame
from discord.ext import tasks

live_scoring = "https://www.zleague.gg/warzone/live-scoring?tournamentId={0}"  # id
all_standings = "https://zleague-api.herokuapp.com/warzone/tournament/{0}/standings"  # id

config = configparser.ConfigParser()
config.read("config.ini")
config_html = config["HTML"]
config_bot = config["Bot"]

start_content = config_html["StartContent"]
end_content = config_html["EndContent"]

bot_token = config_bot["Token"]
bot_command_prefix = config_bot["CommandPrefix"]
bot_update_interval = int(config_bot["UpdateInterval"])
bot_file_user = config_bot["FileSendUser"]
bot_debug = config_bot.getboolean("DebugMode")

null_stdout = open(os.devnull, "w")
tournament_id_pattern = re.compile("[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")

client = discord.Client()
tracked_games = []


@client.event
async def on_ready():
    print("Bot logged in as {0.user}".format(client))


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if not message.content.startswith(bot_command_prefix):
        return

    if message.content.startswith(bot_command_prefix + "track "):
        parts = message.content.rsplit(" ", 1)
        if len(parts) >= 2:
            await track(parts[0].split(" ", 1)[1], parts[1], message.channel)
    elif message.content.startswith(bot_command_prefix + "tracklist"):
        tracking = ""
        index = 1
        for game in tracked_games:
            tracking += "[{0}] {1} in {2}\n".format(index, game.team_name, game.stats["tournament"]["title"])
            index += 1

        await message.channel.send("```Currently Tracking:\n" + tracking + "```")
    elif message.content.startswith(bot_command_prefix + "stoptrack "):
        parts = message.content.split(" ")
        if len(parts) >= 2:
            if not parts[1].isnumeric():
                await message.channel.send("Index must be numerical!")
                return

            index = int(parts[1])
            if index < 1 or index > len(tracked_games):
                await message.channel.send("Invalid index!")
            else:
                del tracked_games[index - 1]
                await message.channel.send("Successfully removed tracked game #" + parts[1])


@client.event
async def on_reaction_add(reaction, user):
    if user == client.user:
        return

    for game in tracked_games:
        if game.message_id == reaction.message.id:
            team_points = game.teams[game.team_name]
            team_name = game.team_name

            reaction_switch = {
                "1️⃣": 0,
                "2️⃣": 1,
                "3️⃣": 2,
                "4️⃣": 3,
                "5️⃣": 4
            }
            if reaction.emoji in reaction_switch:
                index = reaction_switch[reaction.emoji]
                teams = list(game.teams.values())
                team_points = teams[index]
                team_name = game.stats["standings"][index]["name"]

            if team_points.is_accurate:
                message = "```{0}'s Best Two Games:\n(1) {1} Points\n(2) {2} Points\n\n{3} Total Points```"\
                    .format(team_name,
                            team_points.best_game,
                            team_points.second_best_game,
                            team_points.current_total_points)
            else:
                message = "Could not calculate this team's best two games."

            await reaction.remove(user)
            await reaction.message.channel.send(message)
            break


@tasks.loop(seconds=1)
async def update_scoreboards():
    stop_tracking = []

    # Update games after update interval
    for game in tracked_games:
        if int(time.time()) - game.last_checked >= bot_update_interval:
            game.update()
            continue_track = await send_update_message(game, True)
            if not continue_track:
                stop_tracking.append(game)

    # Remove finished games
    for game in stop_tracking:
        tracked_games.remove(game)


async def track(team_name, url, channel):
    tournament_id = None
    division = None

    # Get tournament ID
    if "www.zleague.gg" in url:
        parts = url.split("=")
        if len(parts) > 2:
            tournament_id = parts[1].split("&")[0]
        elif len(parts) == 2:
            tournament_id = parts[1]
    elif "ct.sendgrid.net" in url:
        redirect = requests.get(url, allow_redirects=False)
        location = redirect.headers["Location"]

        if "www.zleague.gg" in location:
            await track(team_name, location, channel)
            return
    else:
        tournament_id = url

    if tournament_id is None or not tournament_id_pattern.fullmatch(tournament_id):
        await channel.send("Invalid url or tournament ID!")
        return

    # Get division
    standings = requests.get(all_standings.format(tournament_id)).json()
    for team in standings:
        if team["name"] == team_name:
            division = team["division"]
            break

    if division is None:
        await channel.send("Invalid team name!")
        return

    # Start tracking and send message
    game = TrackedGame(tournament_id, division, team_name, channel, None)
    game.update()
    continue_track = await send_update_message(game, False)

    if continue_track:
        tracked_games.append(game)


async def send_update_message(game, edit):
    continue_track = True
    tournament = game.stats["tournament"]
    standings = game.stats["standings"]
    values = "name", "numberOfGames", "totalWins", "bestKills", "bestPlacementPoints", "totalPoints"

    reaction_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    team_marker_emoji = "⭐"
    inner_content = ""
    hit_team = False

    # Add top 5 teams to scoreboard
    for i in range(0, 5):
        team = standings[i]
        if team["name"] == game.team_name:
            inner_content += "<tr class='active-row'>"
            reaction_emojis[i] = team_marker_emoji
            hit_team = True
        else:
            inner_content += "<tr>"
        for value in values:
            inner_content += "<td>" + str(team[value]) + "</td>"

    # If team is not in top 5, add them to the bottom
    if not hit_team:
        for team in standings:
            if team["name"] == game.team_name:
                inner_content += "<tr class='active-row'>"
                reaction_emojis.append(team_marker_emoji)
                for value in values:
                    inner_content += "<td>" + str(team[value]) + "</td>"
                inner_content += "</tr>"

    options = {
        "width": "0",
        "zoom": "1",
        "enable-local-file-access": None
    }
    file_name = "scoreboard-" + str(time.time()) + ".png"
    old_stdout = sys.stdout

    # Create image from HTML, send wkhtmltoimage output to null
    try:
        sys.stdout = null_stdout
        imgkit.from_string(start_content + inner_content + end_content, file_name, options=options)
    finally:
        sys.stdout = old_stdout

    # Stop tracking if tournament is over
    # But don't stop tracking if a finalized tournament is needed for testing
    title = u"\U0001F48E " + tournament["title"]
    if tournament["tournamentStatus"] == "FINALIZED":
        title += " - [FINALIZED]"
        if not bot_debug:
            continue_track = False

    # Create embed
    file = discord.File(file_name, filename=file_name)
    image_url = await file_to_url(file)
    os.remove(file_name)

    embed = discord.Embed(title=title, url=live_scoring.format(tournament["id"]),
                          description="Division " + str(game.division), color=0x9A63B0)
    embed.set_image(url=image_url)
    embed.set_footer(text="Updated " + time.strftime("%H:%M:%S", time.localtime()))

    # Send message
    if edit:
        old_message = await game.channel.fetch_message(game.message_id)
        await old_message.edit(embed=embed)
    else:
        message = await game.channel.send(embed=embed)
        game.message_id = message.id

        for emoji in reaction_emojis:
            await message.add_reaction(emoji)

    return continue_track


async def file_to_url(file, user_id=bot_file_user):
    user = await client.fetch_user(user_id)
    message = await user.send(file=file, delete_after=0.0)
    return message.attachments[0].url

update_scoreboards.start()
client.run(bot_token)
