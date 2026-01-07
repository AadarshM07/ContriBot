import discord
from discord.ext import commands, tasks
import os
import requests
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv() 

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

TARGET_CHANNEL_ID = os.getenv("channel_id")

ORGANIZATIONS = [
    "learningequality"
]

POLL_INTERVAL_MINUTES = 30
STATE_FILE = "state.json"

GITHUB_SEARCH_URL = "https://api.github.com/search/issues"
HEADERS = {
    "Accept": "application/vnd.github+json"
}

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"last_checked": None}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

state = load_state()


def fetch_new_issues(org_name, since_time):
    query = f'label:"help wanted" org:{org_name} is:issue created:>{since_time}'

    params = {
        "q": query,
        "sort": "created",
        "order": "asc"
    }

    response = requests.get(GITHUB_SEARCH_URL, headers=HEADERS, params=params)

    if response.status_code != 200:
        print(f"GitHub API error for {org_name}: {response.status_code}")
        return []

    return response.json().get("items", [])

@tasks.loop(minutes=POLL_INTERVAL_MINUTES)
async def check_github():
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        print("Channel not found.")
        return

    since = state["last_checked"] or datetime.now(timezone.utc).isoformat()
    all_issues = []

    for org in ORGANIZATIONS:
        issues = fetch_new_issues(org, since)
        all_issues.extend(issues)

    if not all_issues:
        return 

    all_issues.sort(key=lambda x: x["created_at"])

    for issue in all_issues:
        title = issue["title"]
        url = issue["html_url"]
        repo = issue["repository_url"].split("/")[-1]
        org_name = issue["repository_url"].split("/")[-2]

        message = (
            f"New Help Wanted Issue\n"
            f"Org: {org_name}\n"
            f"Repo: {repo}\n"
            f"Title: {title}\n"
            f"{url}"
        )

        await channel.send(message)

    state["last_checked"] = all_issues[-1]["created_at"]
    save_state(state)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not check_github.is_running():
        check_github.start()


bot.run(DISCORD_TOKEN)
