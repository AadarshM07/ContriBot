import discord
from discord.ext import commands, tasks
import os
import requests
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

TARGET_CHANNEL_ID = os.getenv("CHANNEL_ID")

ORGANIZATIONS = [
    ""  #add target organizations here
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
        print("[STATE] No state file found. Starting fresh.")
        return {"last_checked": None}
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
        print(f"[STATE] Loaded last_checked = {state.get('last_checked')}")
        return state

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    print(f"[STATE] Saved last_checked = {state.get('last_checked')}")

state = load_state()


def fetch_new_issues(org_name, since_time):
    query = f'label:"help wanted" org:{org_name} is:issue created:>{since_time}'

    params = {
        "q": query,
        "sort": "created",
        "order": "asc"
    }

    print(f"[GITHUB] Searching org: {org_name}")
    print(f"[GITHUB] Query: {query}")

    response = requests.get(GITHUB_SEARCH_URL, headers=HEADERS, params=params)

    if response.status_code != 200:
        print(f"[ERROR] GitHub API error for {org_name}: {response.status_code}")
        print(response.text)
        return []

    items = response.json().get("items", [])
    print(f"[GITHUB] Found {len(items)} issues for {org_name}")

    return items

@tasks.loop(minutes=POLL_INTERVAL_MINUTES)
async def check_github():
    print("\n[CHECK] Running GitHub check...")

    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        print("[ERROR] Channel not found.")
        return

    if state["last_checked"]:
        since = state["last_checked"]
    else:
        since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        print(f"[CHECK] First run. Using since = {since}")

    all_issues = []

    for org in ORGANIZATIONS:
        issues = fetch_new_issues(org, since)
        all_issues.extend(issues)

    if not all_issues:
        print("[CHECK] No new help-wanted issues found.")
        return

    all_issues.sort(key=lambda x: x["created_at"])

    print(f"[CHECK] Sending {len(all_issues)} new issues to Discord...")

    for issue in all_issues:
        title = issue["title"]
        url = issue["html_url"]
        repo = issue["repository_url"].split("/")[-1]
        org_name = issue["repository_url"].split("/")[-2]

        message = (
            f"**New Help Wanted Issue**\n"
            f"**Org:** {org_name}\n"
            f"**Repo:** {repo}\n"
            f"**Title:** {title}\n"
            f"{url}"
        )

        print(f"[SEND] {org_name}/{repo} - {title}")
        await channel.send(message)

    state["last_checked"] = all_issues[-1]["created_at"]
    save_state(state)


@bot.event
async def on_ready():
    print(f"[BOT] Logged in as {bot.user}")
    if not check_github.is_running():
        check_github.start()


bot.run(DISCORD_TOKEN)
