from database.storage import load_json, save_json
from config import STATS_FILE

def update_stats(user, action: str):
    stats = load_json(STATS_FILE, {})
    uid = str(user.id)
    if uid not in stats:
        stats[uid] = {"username": user.username, "name": user.full_name, "actions": {}}
    if "actions" not in stats[uid]:
        stats[uid]["actions"] = {}
    stats[uid]["username"] = user.username
    current = stats[uid]["actions"].get(action, 0)
    stats[uid]["actions"][action] = current + 1
    save_json(STATS_FILE, stats)