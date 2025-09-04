# -*- coding: utf-8 -*-
import cloudscraper
import os
import random
import time
import json
from datetime import datetime, timedelta, timezone

# Files
ACCOUNTS_FILE = "token.txt"          # JWT tokens, one per line
USERAGENT_FILE = "user_agents.txt"   # User-Agent strings, one per line
STREAK_TOKENS_FILE = "streak_tokens.txt"  # Long-lived streak tokens, one per line
ACCOUNT_UA_FILE = "account_user_agents.json"  # New file to store account-to-User-Agent mapping

# Cloudflare bypass session
scraper = cloudscraper.create_scraper()

# ===================== Helpers =====================
def load_lines(file_path):
    if not os.path.exists(file_path):
        print(f"[!] {file_path} not found")
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_account_user_agents():
    if not os.path.exists(ACCOUNT_UA_FILE):
        return {}
    with open(ACCOUNT_UA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_account_user_agents(account_ua_map):
    with open(ACCOUNT_UA_FILE, "w", encoding="utf-8") as f:
        json.dump(account_ua_map, f, indent=4)

def assign_user_agent(auth_query, user_agents, account_ua_map):
    # If account already has a User-Agent, return it
    if auth_query in account_ua_map:
        return account_ua_map[auth_query]
    # Assign a new random User-Agent and save it
    user_agent = random.choice(user_agents)
    account_ua_map[auth_query] = user_agent
    save_account_user_agents(account_ua_map)
    return user_agent

def build_headers(auth_query, user_agent):
    return {
        "Authorization": f"Bearer {auth_query}",
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://web.xrocket.tg/",
        "Origin": "https://web.xrocket.tg",
        "Connection": "keep-alive"
    }

# ===================== API Calls =====================
def get_profile(auth_query, user_agent):
    url = "https://xjourney.xrocket.tg/api/v1/xjourney/profile"
    headers = build_headers(auth_query, user_agent)
    try:
        r = scraper.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            print(f"   Username: {data.get('username', 'N/A')}")
            print(f"   Balance: {data.get('balance', 'N/A')}")
            return data
        else:
            print(f"   [x] Failed to fetch profile ({r.status_code}) | {r.text}")
            return None
    except Exception as e:
        print(f"   [x] Error fetching profile: {e}")
        return None

def get_streak_info(auth_query, user_agent):
    url = "https://xjourney.xrocket.tg/api/v1/xjourney/daily-streak"
    headers = build_headers(auth_query, user_agent)
    try:
        r = scraper.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            current_streak = data.get("currentStreak", 0)
            next_claim_time = data.get("nextClaimTime", None)
            print(f"   Current Streak: {current_streak}")
            print(f"   Next Claim Time: {next_claim_time}")
            return current_streak, next_claim_time
        else:
            print(f"   [x] Failed to fetch streak info ({r.status_code}) | {r.text}")
            return None, None
    except Exception as e:
        print(f"   [x] Error fetching streak info: {e}")
        return None, None

def claim_once(auth_query, user_agent, streak_token=None):
    url = "https://xjourney.xrocket.tg/api/v1/xjourney/daily-streak"
    headers = build_headers(auth_query, user_agent)

    # Require streak token
    if not streak_token:
        print("   [x] No streak token found for this account. Skipping...")
        return

    # Fetch profile
    profile = get_profile(auth_query, user_agent)
    if not profile:
        return

    # Fetch streak info
    current_streak, next_claim_time = get_streak_info(auth_query, user_agent)
    if current_streak is None:
        return

    # Check if claim is allowed
    if next_claim_time:
        try:
            next_claim_dt = datetime.fromisoformat(next_claim_time.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < next_claim_dt:
                print(f"   [!] Claim not allowed yet until {next_claim_time}")
                return
        except Exception as e:
            print(f"   [x] Error parsing nextClaimTime: {e}")
            return

    # Next day
    next_day = current_streak + 1
    print(f"   Attempting to claim day {next_day}")
    print("   Using streak_tokens.txt token")

    # POST request
    payload = {"day": next_day, "token": streak_token}
    try:
        r = scraper.post(url, headers=headers, json=payload)
        if r.status_code in [200, 201]:
            data = r.json()
            print(f"   ? Check-in successful! Day {data.get('day')} reward: {data.get('amount')}\n")
        else:
            print(f"   ? Failed ({r.status_code}) | {r.text}")
    except Exception as e:
        print(f"   [x] Error during claim: {e}\n")

# ===================== Runner =====================
def run_all_accounts(accounts, user_agents, streak_tokens):
    account_ua_map = load_account_user_agents()  # Load User-Agent mappings
    for idx, auth_query in enumerate(accounts, 1):
        streak_token = streak_tokens[idx - 1] if idx <= len(streak_tokens) else None
        user_agent = assign_user_agent(auth_query, user_agents, account_ua_map)  # Assign or retrieve User-Agent
        print(f"\n=== Account {idx} ===")
        print(f"Using User-Agent: {user_agent}")
        claim_once(auth_query, user_agent, streak_token)
        time.sleep(random.randint(5, 15))

def main_loop():
    accounts = load_lines(ACCOUNTS_FILE)
    user_agents = load_lines(USERAGENT_FILE)
    streak_tokens = load_lines(STREAK_TOKENS_FILE)

    print("=" * 50)
    print(f"Loaded {len(accounts)} accounts | {len(user_agents)} user-agents | {len(streak_tokens)} streak tokens")
    print("=" * 50)

    while True:
        print("\n?? Starting claim cycle...")
        run_all_accounts(accounts, user_agents, streak_tokens)

        wait_seconds = 24 * 3600  # run once per day
        next_dt = datetime.now(timezone.utc) + timedelta(seconds=wait_seconds)
        print("[*] Sleeping for 24h before next cycle...")
        print(f"Next cycle at: {next_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        time.sleep(wait_seconds)

if __name__ == "__main__":
    main_loop()
