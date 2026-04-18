import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import math
import requests
import re
import random
import asyncio
from datetime import datetime, timedelta
from collections import Counter
import secrets
import string
import cloudscraper
from bs4 import BeautifulSoup
from time import time
from flask import Flask, request, jsonify
import threading
import functools
import hashlib
import hmac
import base64

ALLOWED_ADMINS = ["YOUR_ADMIN_ID_1", "YOUR_ADMIN_ID_2"]
API_PORT = 35585
PET_VALUES_FILE = "pets.json"
PET_ICONS_FILE = "pet_icons.json"
COINFLIP_CHANNEL_ID = 123456789012345678
OWNER_USER_ID = "YOUR_OWNER_ID"
TAX_WEBHOOK_URL = "YOUR_TAX_WEBHOOK_URL"
DEPOSIT_WEBHOOK_URL = "YOUR_DEPOSIT_WEBHOOK_URL"
DEPOSIT_LOG_CHANNEL_ID = 123456789012345678
TICKET_CATEGORY_ID = None

datafile = "data.json"
user_links_file = "user_links.json"
profit_data_file = "profit_data.json"
withdraws_file = "withdraws.json"
leaderboard_file = "leaderboard.json"

GEM_PACK_VALUES = {
    "10B": 10000000000,
    "1B": 1000000000,
    "100M": 100000000,
    "10M": 10000000,
    "1M": 1000000,
    "100K": 100000
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_coinflips = {}
coinflip_locks = {}

def ensure_files_exist():
    default_files = {
        datafile: {},
        user_links_file: {},
        profit_data_file: {"total_profit": 0},
        withdraws_file: [],
        leaderboard_file: {"wagered": {}, "value": {}}
    }
    for file_path, default_content in default_files.items():
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                json.dump(default_content, f, indent=4)
            print(f"Created {file_path}")
    if not os.path.exists(PET_VALUES_FILE):
        with open(PET_VALUES_FILE, "w") as f:
            json.dump({}, f, indent=4)
        print(f"Created {PET_VALUES_FILE}")
    if not os.path.exists(PET_ICONS_FILE):
        with open(PET_ICONS_FILE, "w") as f:
            json.dump({}, f, indent=4)
        print(f"Created {PET_ICONS_FILE}")

def load_data():
    try:
        with open(datafile, "r") as f:
            data = json.load(f)
            migrated = False
            for user_id, value in data.items():
                if isinstance(value, list):
                    data[user_id] = {
                        "inventory": value,
                        "wagered": 0,
                        "wins": 0,
                        "losses": 0,
                        "roblox_id": None,
                        "roblox_username": None
                    }
                    migrated = True
                elif isinstance(value, dict):
                    if "inventory" not in value:
                        value["inventory"] = []
                        migrated = True
                    if "wagered" not in value:
                        value["wagered"] = 0
                        migrated = True
                    if "wins" not in value:
                        value["wins"] = 0
                        migrated = True
                    if "losses" not in value:
                        value["losses"] = 0
                        migrated = True
                    if "roblox_id" not in value:
                        value["roblox_id"] = None
                        migrated = True
                    if "roblox_username" not in value:
                        value["roblox_username"] = None
                        migrated = True
            if migrated:
                save_data(data)
            return data
    except FileNotFoundError:
        return {}

def save_data(data):
    with open(datafile, "w") as f:
        json.dump(data, f, indent=4)

def load_user_links():
    try:
        with open(user_links_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_links(links):
    with open(user_links_file, "w") as f:
        json.dump(links, f, indent=4)

def load_profit_data():
    try:
        with open(profit_data_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"total_profit": 0}

def save_profit_data(data):
    with open(profit_data_file, "w") as f:
        json.dump(data, f, indent=4)

def load_withdraws():
    try:
        with open(withdraws_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_withdraws(data):
    with open(withdraws_file, "w") as f:
        json.dump(data, f, indent=4)

def load_pet_icons():
    try:
        with open(PET_ICONS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_pet_icons(icons):
    with open(PET_ICONS_FILE, "w") as f:
        json.dump(icons, f, indent=4)

def load_leaderboard():
    try:
        with open(leaderboard_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"wagered": {}, "value": {}}

def save_leaderboard(data):
    with open(leaderboard_file, "w") as f:
        json.dump(data, f, indent=4)

def update_wagered(user_id: str, amount: int):
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "inventory": [],
            "wagered": 0,
            "wins": 0,
            "losses": 0,
            "roblox_id": None,
            "roblox_username": None
        }
    data[user_id]["wagered"] = data[user_id].get("wagered", 0) + amount
    save_data(data)
    update_leaderboard_stats(user_id)

def update_wins_losses(user_id: str, won: bool):
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "inventory": [],
            "wagered": 0,
            "wins": 0,
            "losses": 0,
            "roblox_id": None,
            "roblox_username": None
        }
    if won:
        data[user_id]["wins"] = data[user_id].get("wins", 0) + 1
    else:
        data[user_id]["losses"] = data[user_id].get("losses", 0) + 1
    save_data(data)

def update_roblox_info(user_id: str, roblox_id: str, roblox_username: str):
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "inventory": [],
            "wagered": 0,
            "wins": 0,
            "losses": 0,
            "roblox_id": None,
            "roblox_username": None
        }
    data[user_id]["roblox_id"] = roblox_id
    data[user_id]["roblox_username"] = roblox_username
    save_data(data)

def update_leaderboard_stats(user_id: str):
    data = load_data()
    lb = load_leaderboard()
    if user_id in data:
        user_data = data[user_id]
        lb["wagered"][user_id] = user_data.get("wagered", 0)
        inventory = user_data.get("inventory", [])
        total_value = calculate_total_value(inventory)
        lb["value"][user_id] = total_value
    save_leaderboard(lb)

async def check_linked(interaction: discord.Interaction) -> bool:
    user_links = load_user_links()
    for roblox_id, data in user_links.items():
        if data.get("discord_id") == str(interaction.user.id):
            return True
    return False

def linked_only():
    async def predicate(interaction: discord.Interaction):
        if not await check_linked(interaction):
            embed = discord.Embed(
                title="Account Not Linked",
                description="You need to link your Roblox account first. Use /link to link your account.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

def format_value(value):
    if isinstance(value, str):
        return value
    if value >= 1000000000000:
        return f"{value/1000000000000:.1f}T"
    elif value >= 1000000000:
        return f"{value/1000000000:.1f}B"
    elif value >= 1000000:
        return f"{value/1000000:.1f}M"
    elif value >= 1000:
        return f"{value/1000:.1f}K"
    return str(value)

def unformat_value(string):
    if not string or string in ["O/C", "N/A", "unknown"]:
        return 0
    suffixes = {'K': 1000, 'M': 1000000, 'B': 1000000000, 'T': 1000000000000}
    try:
        return int(string)
    except ValueError:
        try:
            if string and string[-1].upper() in suffixes:
                num = float(string[:-1])
                return int(num * suffixes[string[-1].upper()])
            return 0
        except:
            return 0

def to_proper_case(text):
    return ' '.join([word.capitalize() for word in text.split()])

def add_suffix2(value):
    if isinstance(value, str):
        return value
    for suffix, divisor in [("T", 1000000000000), ("B", 1000000000), ("M", 1000000), ("K", 1000)]:
        if value >= divisor:
            return f"{round(value / divisor, 2)}{suffix}"
    return str(value)

def suffix_to_int2(value):
    if value in ["SOON", "N/A", "O/C", "unknown"]:
        return 0
    multipliers = {"K": 1000, "M": 1000000, "B": 1000000000, "T": 1000000000000}
    if any(char.isdigit() for char in value):
        if value[-1].upper() in multipliers:
            num, suffix = float(value[:-1]), value[-1].upper()
            return int(num * multipliers[suffix])
        return int(float(value))
    return 0

def get_timestamp(last_updated):
    try:
        match = re.search(r"(\d+)\s*(hour|hours|day|days|week|weeks|month|months)", last_updated.lower())
        if not match:
            return "Unknown"
        num = int(match.group(1))
        unit = match.group(2)
        now = datetime.utcnow()
        if "month" in unit:
            past_date = now - timedelta(days=30 * num)
        elif "week" in unit:
            past_date = now - timedelta(weeks=num)
        elif "day" in unit:
            past_date = now - timedelta(days=num)
        elif "hour" in unit:
            past_date = now - timedelta(hours=num)
        else:
            return "Unknown"
        return int(past_date.timestamp())
    except Exception:
        return "Unknown"

def summarize_items(items):
    counts = Counter(items)
    return [f"{count}x {item}" if count > 1 else item for item, count in counts.items()]

def get_pet_value_from_json(pet_name: str) -> int:
    try:
        with open(PET_VALUES_FILE, "r") as f:
            pets = json.load(f)
        if pet_name in pets:
            return pets[pet_name].get("value", 0)
        for name, pet in pets.items():
            if name.lower() == pet_name.lower():
                return pet.get("value", 0)
        return 0
    except:
        return 0

def get_item_value(item_name: str) -> int:
    if "Gems" in item_name:
        try:
            amount_str = item_name.split()[0].lower()
            return GEM_PACK_VALUES.get(amount_str.upper(), 0)
        except:
            return 0
    else:
        return get_pet_value_from_json(item_name)

def get_pet_display_name(pet_name: str) -> str:
    value = get_pet_value_from_json(pet_name)
    if value > 0:
        return f"{pet_name} ({add_suffix2(value)})"
    return pet_name

def calculate_total_value(items):
    return sum(get_item_value(item) for item in items)

def add_profit(amount: int):
    data = load_profit_data()
    data["total_profit"] = data.get("total_profit", 0) + amount
    save_profit_data(data)

async def send_tax_log(winner, loser, tax_amount, tax_items, total_pot):
    if not TAX_WEBHOOK_URL:
        print("[Tax] No webhook URL configured")
        return
    embed = discord.Embed(
        title="Tax Collection Log",
        color=0xffaa00,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Winner", value=winner.mention, inline=True)
    embed.add_field(name="Loser", value=loser.mention, inline=True)
    embed.add_field(name="Total Pot", value=f"{add_suffix2(total_pot)}", inline=True)
    embed.add_field(name="Server Profit (10%)", value=f"{add_suffix2(tax_amount)}", inline=True)
    if tax_items:
        tax_summary = summarize_items(tax_items)
        tax_text = "\n".join(f"• {item}" for item in tax_summary[:10])
        if len(tax_text) > 1000:
            tax_text = tax_text[:997] + "..."
        embed.add_field(name="Items Taken as Tax", value=tax_text, inline=False)
    embed.set_footer(text="Tax goes to server owner for operating costs")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(TAX_WEBHOOK_URL, json={"embeds": [embed.to_dict()]}, timeout=10) as resp:
                if resp.status in [200, 204]:
                    print(f"[Tax] Webhook sent successfully (Tax: {add_suffix2(tax_amount)})")
                else:
                    print(f"[Tax] Webhook failed with status {resp.status}")
    except Exception as e:
        print(f"[Tax] Error sending webhook: {e}")

async def send_deposit_log(deposit_type, user, roblox_id, roblox_username, items, gems, total_value):
    items_summary = summarize_items(items)
    items_text = "\n".join(f"• {item}" for item in items_summary[:25])
    if len(items_text) > 1000:
        items_text = items_text[:997] + "..."
    gems_text = ""
    if gems > 0:
        gems_text = f"• {add_suffix2(gems)} Gems"
    embed = discord.Embed(
        title=f"Item Deposit Received - {deposit_type}",
        color=0x00ff00 if deposit_type == "Auto" else 0xffaa00,
        timestamp=datetime.utcnow()
    )
    user_name = user.display_name if isinstance(user, discord.User) else f"User {user}"
    embed.add_field(
        name="User",
        value=f"{user_name}\nRoblox Account: {roblox_username}",
        inline=False
    )
    if items_text:
        embed.add_field(name="Items Deposited", value=items_text, inline=False)
    if gems_text:
        embed.add_field(name="Gems Deposited", value=gems_text, inline=False)
    embed.add_field(name="Total Value", value=f"{add_suffix2(total_value)}", inline=False)
    if DEPOSIT_WEBHOOK_URL:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DEPOSIT_WEBHOOK_URL, json={"embeds": [embed.to_dict()]}, timeout=10) as resp:
                    if resp.status in [200, 204]:
                        print(f"[Deposit] Webhook sent")
                    else:
                        print(f"[Deposit] Webhook failed: {resp.status}")
        except Exception as e:
            print(f"[Deposit] Webhook error: {e}")
    if DEPOSIT_LOG_CHANNEL_ID:
        try:
            channel = bot.get_channel(DEPOSIT_LOG_CHANNEL_ID)
            if channel:
                await channel.send(embed=embed)
                print(f"[Deposit] Sent to log channel")
        except Exception as e:
            print(f"[Deposit] Channel error: {e}")

pending_links = {}

async def verify_roblox_bio(roblox_id: str, expected_code: str) -> bool:
    try:
        url = f"https://www.roblox.com/users/{roblox_id}/profile"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    patterns = [
                        r'<div class="profile-bio"[^>]*>(.*?)</div>',
                        r'"description":"(.*?)"',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html, re.DOTALL)
                        if match:
                            bio = re.sub(r'<[^>]+>', '', match.group(1))
                            if expected_code in bio:
                                return True
                    if expected_code in html:
                        return True
        return False
    except:
        return False

scraper = cloudscraper.create_scraper()

def fetch_all_pets():
    all_pets = []
    base_url = "https://petsimulatorvalues.com/values.php?category=all&page={}&sort=id&order=ASC"
    print("Starting pet data fetch...")
    for page in range(1, 113):
        url = base_url.format(page)
        try:
            response = scraper.get(url, timeout=30)
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            pet_containers = soup.find_all("div", class_="p-1 pl-3 pr-3")
            for pet_container in pet_containers:
                name_element = pet_container.find_previous("h5", class_="item-name")
                pet_name = name_element.text.strip() if name_element else "unknown"
                pet_name = to_proper_case(pet_name)
                value_container = pet_container.find("span", class_="value-container")
                pet_value = "unknown"
                pet_value_raw = 0
                if value_container:
                    value_spans = value_container.find_all("span")
                    if value_spans and len(value_spans) >= 3:
                        pet_value = value_spans[-1].text.strip()
                        pet_value_raw = unformat_value(pet_value)
                demand_label = pet_container.find("span", string="Demand")
                pet_demand = "unknown"
                if demand_label:
                    demand_value = demand_label.find_next_sibling("span")
                    if demand_value:
                        pet_demand = demand_value.text.strip()
                last_updated_element = pet_container.find_previous("div", class_="text-grey")
                last_updated = (
                    last_updated_element.text.replace("Last updated:", "").strip()
                    if last_updated_element else "unknown"
                )
                image_element = pet_container.find_previous("img")
                image_url = image_element["src"].replace(" ", "%20") if image_element else "unknown"
                pet_data = {
                    "name": pet_name,
                    "value": pet_value_raw,
                    "formatted_value": pet_value,
                    "demand": pet_demand,
                    "last_updated": last_updated,
                    "image_url": image_url,
                }
                all_pets.append(pet_data)
            print(f"Fetched page {page} - Found {len(pet_containers)} pets")
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            continue
    pets_dict = {}
    for pet in all_pets:
        pets_dict[pet["name"]] = pet
    with open(PET_VALUES_FILE, "w", encoding="utf-8") as json_file:
        json.dump(pets_dict, json_file, indent=4, ensure_ascii=False)
    print(f"Saved {len(all_pets)} pets to {PET_VALUES_FILE}")
    return pets_dict

async def scrape_cosmic_values():
    print("Starting Cosmic Values scrape...")
    start_time = time()
    result = await asyncio.to_thread(fetch_all_pets)
    end_time = time()
    print(f"Scraped {len(result)} pets in {end_time - start_time:.2f} seconds")
    return result

async def scraper_updater():
    await scrape_cosmic_values()
    while True:
        await asyncio.sleep(24 * 60 * 60)
        await scrape_cosmic_values()

async def pet_autocomplete(interaction: discord.Interaction, current: str):
    try:
        with open(PET_VALUES_FILE, 'r', encoding='utf-8') as f:
            pets = json.load(f)
        pet_names = list(pets.keys())
        filtered_names = []
        if current:
            current_lower = current.lower().strip()
            for name in pet_names:
                if current_lower in name.lower():
                    filtered_names.append(name)
        else:
            filtered_names = pet_names[:25]
        filtered_names = sorted(list(set(filtered_names)))[:25]
        choices = []
        for name in filtered_names[:25]:
            choices.append(app_commands.Choice(name=name[:100], value=name))
        return choices
    except:
        return []

def generate_server_seed():
    return secrets.token_hex(32)

def generate_client_seed():
    return secrets.token_hex(16)

def generate_nonce():
    return secrets.randbits(32)

def calculate_coinflip_result(server_seed: str, client_seed: str, nonce: int) -> str:
    message = f"{client_seed}:{nonce}"
    hmac_hash = hmac.new(
        server_seed.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    result_int = int(hmac_hash[:8], 16)
    return 'heads' if result_int % 2 == 0 else 'tails'

class CoinflipFairnessData:
    def __init__(self, server_seed: str, client_seed: str, nonce: int, choice: str):
        self.server_seed = server_seed
        self.client_seed = client_seed
        self.nonce = nonce
        self.choice = choice
        self.result = None

    def get_reveal_data(self) -> dict:
        return {
            "server_seed": self.server_seed,
            "client_seed": self.client_seed,
            "nonce": self.nonce,
            "choice": self.choice,
            "result": self.result
        }

class FairnessButton(discord.ui.Button):
    def __init__(self, fairness_data):
        super().__init__(label="Verify Fairness", style=discord.ButtonStyle.secondary)
        self.fairness_data = fairness_data

    async def callback(self, interaction: discord.Interaction):
        data = self.fairness_data.get_reveal_data()
        embed = discord.Embed(title="Coinflip Fairness Verification", description="This proves the coinflip was fair.", color=0x00ccff)
        embed.add_field(name="Server Seed", value=f"||{data['server_seed']}||", inline=False)
        embed.add_field(name="Client Seed", value=f"||{data['client_seed']}||", inline=True)
        embed.add_field(name="Nonce", value=f"||{data['nonce']}||", inline=True)
        embed.add_field(name="Your Choice", value=data['choice'].upper(), inline=True)
        embed.add_field(name="Result", value=data['result'].upper(), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PaginatedSelectView(discord.ui.View):
    def __init__(self, user: discord.User, inventory_items: list[str], title: str, description: str, timeout: int = 120, mode: str = "normal", target_value: int = None):
        super().__init__(timeout=timeout)
        self.user = user
        self.original_items = inventory_items.copy()
        self.item_counts = Counter(inventory_items)
        self.item_list = [(item, count) for item, count in self.item_counts.items()]
        self.selected_items = []
        self.confirmed = False
        self.title = title
        self.description = description
        self.mode = mode
        self.target_value = target_value
        self.current_page = 0
        self.items_per_page = 10
        self.total_pages = max(1, (len(self.item_list) + self.items_per_page - 1) // self.items_per_page)
        self.update_dropdown()
        if self.total_pages > 1:
            self.prev_button = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.gray, row=0)
            self.prev_button.callback = self.prev_page_callback
            self.add_item(self.prev_button)
            self.next_button = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.gray, row=0)
            self.next_button.callback = self.next_page_callback
            self.add_item(self.next_button)
        self.select_all_button = discord.ui.Button(label="Select All", style=discord.ButtonStyle.secondary, row=1)
        self.select_all_button.callback = self.select_all_callback
        self.add_item(self.select_all_button)
        self.clear_all_button = discord.ui.Button(label="Clear All", style=discord.ButtonStyle.secondary, row=1)
        self.clear_all_button.callback = self.clear_all_callback
        self.add_item(self.clear_all_button)
        if mode == "coinflip_join" and target_value:
            self.auto_select_button = discord.ui.Button(label="Auto Select", style=discord.ButtonStyle.primary, row=2)
            self.auto_select_button.callback = self.auto_select_callback
            self.add_item(self.auto_select_button)
        self.confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, row=3)
        self.confirm_button.callback = self.confirm_callback
        self.add_item(self.confirm_button)
        self.cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
        self.cancel_button.callback = self.cancel_callback
        self.add_item(self.cancel_button)

    def get_available_counts(self):
        selected_counts = Counter(self.selected_items)
        available = {}
        for item, original_count in self.item_counts.items():
            selected_count = selected_counts.get(item, 0)
            remaining = original_count - selected_count
            if remaining > 0:
                available[item] = remaining
        return available

    def update_dropdown(self):
        for item in self.children[:]:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        available = self.get_available_counts()
        available_list = [(item, count) for item, count in available.items()]
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(available_list))
        page_items = available_list[start_idx:end_idx]
        options = []
        for item, count in page_items:
            value = get_item_value(item)
            display_name = get_pet_display_name(item)
            label = f"{count}x {display_name[:60]}" if len(display_name) > 60 else f"{count}x {display_name}"
            options.append(discord.SelectOption(
                label=label[:100],
                value=f"{item}|{count}",
                description=f"Value: {add_suffix2(value)}"
            ))
        total_pages = max(1, (len(available_list) + self.items_per_page - 1) // self.items_per_page)
        if options:
            self.dropdown = discord.ui.Select(
                placeholder=f"Select items (Page {self.current_page + 1}/{total_pages}) - {len(self.selected_items)} selected",
                options=options[:25],
                row=4
            )
            self.dropdown.callback = self.dropdown_callback
            self.add_item(self.dropdown)

    async def dropdown_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your selection menu.", ephemeral=True)
            return
        selected_value = self.dropdown.values[0]
        item_name, count_str = selected_value.rsplit("|", 1)
        self.selected_items.append(item_name)
        self.update_dropdown()
        total_value = calculate_total_value(self.selected_items)
        selected_summary = summarize_items(self.selected_items)
        selected_text = "\n".join(f"• {s}" for s in selected_summary[:20]) if selected_summary else "None"
        if len(selected_text) > 1500:
            selected_text = selected_text[:1497] + "..."
        embed = discord.Embed(
            title=self.title,
            description=f"{self.description}\n\n**Selected Items ({len(self.selected_items)} items):**\n{selected_text}\n\n**Total Value:** {add_suffix2(total_value)}",
            color=0x00ccff
        )
        if self.mode == "coinflip_join" and self.target_value:
            min_val = int(self.target_value * 0.9)
            max_val = int(self.target_value * 1.1)
            status = "✅" if min_val <= total_value <= max_val else "❌"
            embed.add_field(name="Bet Requirement", value=f"{status} Required: {add_suffix2(min_val)} - {add_suffix2(max_val)}", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def select_all_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your selection menu.", ephemeral=True)
            return
        for item, count in self.item_counts.items():
            for _ in range(count):
                self.selected_items.append(item)
        self.update_dropdown()
        total_value = calculate_total_value(self.selected_items)
        selected_summary = summarize_items(self.selected_items)
        selected_text = "\n".join(f"• {s}" for s in selected_summary[:20])
        if len(selected_text) > 1500:
            selected_text = selected_text[:1497] + "..."
        embed = discord.Embed(
            title=self.title,
            description=f"{self.description}\n\n**Selected Items ({len(self.selected_items)} items):**\n{selected_text}\n\n**Total Value:** {add_suffix2(total_value)}",
            color=0x00ccff
        )
        if self.mode == "coinflip_join" and self.target_value:
            min_val = int(self.target_value * 0.9)
            max_val = int(self.target_value * 1.1)
            status = "✅" if min_val <= total_value <= max_val else "❌"
            embed.add_field(name="Bet Requirement", value=f"{status} Required: {add_suffix2(min_val)} - {add_suffix2(max_val)}", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def clear_all_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your selection menu.", ephemeral=True)
            return
        self.selected_items = []
        self.update_dropdown()
        embed = discord.Embed(
            title=self.title,
            description=f"{self.description}\n\n**Selected Items:** None\n\n**Total Value:** 0",
            color=0x00ccff
        )
        if self.mode == "coinflip_join" and self.target_value:
            min_val = int(self.target_value * 0.9)
            max_val = int(self.target_value * 1.1)
            embed.add_field(name="Bet Requirement", value=f"Required: {add_suffix2(min_val)} - {add_suffix2(max_val)}", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def auto_select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your selection menu.", ephemeral=True)
            return
        if not self.target_value:
            await interaction.response.send_message("Auto-select not available.", ephemeral=True)
            return
        await interaction.response.defer()
        min_target = int(self.target_value * 0.9)
        max_target = int(self.target_value * 1.1)
        all_individual_items = []
        for item, count in self.item_counts.items():
            all_individual_items.extend([item] * count)
        items_with_values = [(item, get_item_value(item)) for item in all_individual_items]
        items_with_values.sort(key=lambda x: x[1])
        selected = []
        current_value = 0
        for item, value in items_with_values:
            if current_value + value <= max_target:
                selected.append(item)
                current_value += value
            if current_value >= min_target:
                break
        if current_value < min_target:
            selected = all_individual_items.copy()
            current_value = calculate_total_value(selected)
        self.selected_items = selected
        self.update_dropdown()
        selected_summary = summarize_items(self.selected_items)
        selected_text = "\n".join(f"• {s}" for s in selected_summary[:20])
        if len(selected_text) > 1500:
            selected_text = selected_text[:1497] + "..."
        status_color = 0x00ff00 if min_target <= current_value <= max_target else 0xffaa00
        embed = discord.Embed(
            title=self.title,
            description=f"{self.description}\n\n**Selected Items ({len(self.selected_items)} items):**\n{selected_text}\n\n**Total Value:** {add_suffix2(current_value)}",
            color=status_color
        )
        min_val = int(self.target_value * 0.9)
        max_val = int(self.target_value * 1.1)
        status = "✅" if min_val <= current_value <= max_val else "⚠️"
        embed.add_field(name="Bet Requirement", value=f"{status} Required: {add_suffix2(min_val)} - {add_suffix2(max_val)}", inline=False)
        await interaction.edit_original_response(embed=embed, view=self)

    async def prev_page_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your selection menu.", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.update_dropdown()
            total_value = calculate_total_value(self.selected_items)
            selected_summary = summarize_items(self.selected_items)
            selected_text = "\n".join(f"• {s}" for s in selected_summary[:20]) if selected_summary else "None"
            if len(selected_text) > 1500:
                selected_text = selected_text[:1497] + "..."
            embed = discord.Embed(
                title=self.title,
                description=f"{self.description}\n\n**Selected Items ({len(self.selected_items)} items):**\n{selected_text}\n\n**Total Value:** {add_suffix2(total_value)}",
                color=0x00ccff
            )
            if self.mode == "coinflip_join" and self.target_value:
                min_val = int(self.target_value * 0.9)
                max_val = int(self.target_value * 1.1)
                status = "✅" if min_val <= total_value <= max_val else "❌"
                embed.add_field(name="Bet Requirement", value=f"{status} Required: {add_suffix2(min_val)} - {add_suffix2(max_val)}", inline=False)
            await interaction.response.edit_message(embed=embed, view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your selection menu.", ephemeral=True)
            return
        available = self.get_available_counts()
        available_list = list(available.items())
        total_pages = max(1, (len(available_list) + self.items_per_page - 1) // self.items_per_page)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_dropdown()
            total_value = calculate_total_value(self.selected_items)
            selected_summary = summarize_items(self.selected_items)
            selected_text = "\n".join(f"• {s}" for s in selected_summary[:20]) if selected_summary else "None"
            if len(selected_text) > 1500:
                selected_text = selected_text[:1497] + "..."
            embed = discord.Embed(
                title=self.title,
                description=f"{self.description}\n\n**Selected Items ({len(self.selected_items)} items):**\n{selected_text}\n\n**Total Value:** {add_suffix2(total_value)}",
                color=0x00ccff
            )
            if self.mode == "coinflip_join" and self.target_value:
                min_val = int(self.target_value * 0.9)
                max_val = int(self.target_value * 1.1)
                status = "✅" if min_val <= total_value <= max_val else "❌"
                embed.add_field(name="Bet Requirement", value=f"{status} Required: {add_suffix2(min_val)} - {add_suffix2(max_val)}", inline=False)
            await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your selection menu.", ephemeral=True)
            return
        if not self.selected_items:
            await interaction.response.send_message("Please select at least one item.", ephemeral=True)
            return
        if self.mode == "coinflip_join" and self.target_value:
            total_value = calculate_total_value(self.selected_items)
            min_val = int(self.target_value * 0.9)
            max_val = int(self.target_value * 1.1)
            if not (min_val <= total_value <= max_val):
                await interaction.response.send_message(
                    f"Your bet ({add_suffix2(total_value)}) must be between "
                    f"{add_suffix2(min_val)} and {add_suffix2(max_val)}.",
                    ephemeral=True
                )
                return
        self.confirmed = True
        self.stop()
        await interaction.response.edit_message(content="Selection confirmed!", embed=None, view=None)

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your selection menu.", ephemeral=True)
            return
        self.confirmed = False
        self.selected_items = []
        self.stop()
        await interaction.response.edit_message(content="Selection cancelled.", embed=None, view=None)

class LinkConfirmView(discord.ui.View):
    def __init__(self, user: discord.User, roblox_id: str, roblox_username: str, code: str):
        super().__init__(timeout=300)
        self.user = user
        self.roblox_id = roblox_id
        self.roblox_username = roblox_username
        self.code = code

    @discord.ui.button(label="Confirm Verification", style=discord.ButtonStyle.success, row=0)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your verification menu.", ephemeral=True)
            return
        await interaction.response.defer()
        pending = pending_links.get(str(self.user.id))
        if not pending or pending.get("code") != self.code:
            await interaction.followup.send("Verification expired or invalid. Please use /link again.", ephemeral=True)
            self.stop()
            return
        if datetime.now() > pending["expires"]:
            await interaction.followup.send("Verification code has expired. Please use /link again.", ephemeral=True)
            del pending_links[str(self.user.id)]
            self.stop()
            return
        await interaction.followup.send("Verifying your Roblox bio... Please wait.", ephemeral=True)
        bio_verified = await verify_roblox_bio(self.roblox_id, self.code)
        if not bio_verified:
            await interaction.followup.send(
                f"Verification failed. The code {self.code} was not found in your Roblox bio.\n\n"
                f"Please add {self.code} to your bio and try again.",
                ephemeral=True
            )
            return
        user_links = load_user_links()
        user_links[str(self.roblox_id)] = {
            "discord_id": str(interaction.user.id),
            "discord_name": interaction.user.name,
            "roblox_username": self.roblox_username,
            "linked_at": datetime.now().isoformat()
        }
        save_user_links(user_links)
        update_roblox_info(str(interaction.user.id), str(self.roblox_id), self.roblox_username)
        if str(self.user.id) in pending_links:
            del pending_links[str(self.user.id)]
        embed = discord.Embed(
            title="Account Linked",
            description=f"Successfully linked {self.roblox_username} (ID: {self.roblox_id}) to your Discord account.",
            color=0x00ff00
        )
        await interaction.followup.send(embed=embed)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your verification menu.", ephemeral=True)
            return
        if str(self.user.id) in pending_links:
            del pending_links[str(self.user.id)]
        await interaction.response.send_message("Verification cancelled.", ephemeral=True)
        self.stop()

@bot.tree.command(name="link", description="Link your Roblox account to Discord")
@app_commands.describe(roblox_username="Your Roblox username")
async def link_account(interaction: discord.Interaction, roblox_username: str):
    await interaction.response.defer()
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [roblox_username]}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and data.get("data") and len(data["data"]) > 0:
                        user_data = data["data"][0]
                        roblox_id = user_data["id"]
                        user_links = load_user_links()
                        if str(roblox_id) in user_links:
                            await interaction.followup.send("This Roblox account is already linked to a Discord account.", ephemeral=True)
                            return
                        for rid, link_data in user_links.items():
                            if link_data.get("discord_id") == str(interaction.user.id):
                                await interaction.followup.send("You already have a Roblox account linked. Use /unlink first.", ephemeral=True)
                                return
                        verification_code = ''.join(secrets.choice(string.digits) for _ in range(6))
                        pending_links[str(interaction.user.id)] = {
                            "roblox_id": str(roblox_id),
                            "roblox_username": roblox_username,
                            "code": verification_code,
                            "expires": datetime.now() + timedelta(minutes=5)
                        }
                        embed = discord.Embed(
                            title="Account Verification Required",
                            description=f"To link your Roblox account {roblox_username}, please follow these steps:",
                            color=0xffaa00
                        )
                        embed.add_field(name="Step 1", value="Go to your Roblox profile and edit your Bio", inline=False)
                        embed.add_field(name="Step 2", value=f"Add this verification code to your bio: {verification_code}", inline=False)
                        embed.add_field(name="Step 3", value="Click the Confirm button below to verify", inline=False)
                        embed.add_field(name="Note", value=f"This code will expire in 5 minutes.", inline=False)
                        view = LinkConfirmView(interaction.user, roblox_id, roblox_username, verification_code)
                        await interaction.followup.send(embed=embed, view=view)
                        return
                    else:
                        await interaction.followup.send(f"Roblox user '{roblox_username}' not found.", ephemeral=True)
                        return
                else:
                    await interaction.followup.send(f"Roblox API error (status {resp.status}). Please try again later.", ephemeral=True)
                    return
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="unlink", description="Unlink your Roblox account from Discord")
async def unlink_account(interaction: discord.Interaction):
    user_links = load_user_links()
    found = False
    for roblox_id, data in list(user_links.items()):
        if data.get("discord_id") == str(interaction.user.id):
            del user_links[roblox_id]
            found = True
            break
    if found:
        save_user_links(user_links)
        data = load_data()
        user_id = str(interaction.user.id)
        if user_id in data:
            data[user_id]["roblox_id"] = None
            data[user_id]["roblox_username"] = None
            save_data(data)
        embed = discord.Embed(
            title="Account Unlinked",
            description="Your Roblox account has been unlinked from Discord.",
            color=0x00ff00
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("You don't have any linked Roblox account.", ephemeral=True)

@bot.tree.command(name="force-link", description="Force link a user (Admin only)")
@app_commands.describe(user="Discord user", roblox_username="Roblox username")
async def force_link(interaction: discord.Interaction, user: discord.User, roblox_username: str):
    if str(interaction.user.id) not in ALLOWED_ADMINS:
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return
    await interaction.response.defer()
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [roblox_username]}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and data.get("data") and len(data["data"]) > 0:
                        user_data = data["data"][0]
                        roblox_id = user_data["id"]
                        actual_username = user_data["name"]
                        user_links = load_user_links()
                        if str(roblox_id) in user_links:
                            existing = user_links[str(roblox_id)].get("discord_id")
                            if existing != str(user.id):
                                await interaction.followup.send(f"Roblox account is already linked to <@{existing}>.", ephemeral=True)
                                return
                        for rid, link_data in user_links.items():
                            if link_data.get("discord_id") == str(user.id) and rid != str(roblox_id):
                                await interaction.followup.send(f"{user.mention} is already linked to another Roblox account.", ephemeral=True)
                                return
                        user_links[str(roblox_id)] = {
                            "discord_id": str(user.id),
                            "discord_name": user.name,
                            "roblox_username": actual_username,
                            "linked_at": datetime.now().isoformat(),
                            "forced_by": str(interaction.user.id)
                        }
                        save_user_links(user_links)
                        update_roblox_info(str(user.id), str(roblox_id), actual_username)
                        update_leaderboard_stats(str(user.id))
                        embed = discord.Embed(
                            title="Account Force Linked",
                            description=f"Successfully linked {user.mention} to Roblox account:",
                            color=0x00ff00
                        )
                        embed.add_field(name="Roblox Username", value=actual_username, inline=True)
                        embed.add_field(name="Roblox ID", value=roblox_id, inline=True)
                        embed.add_field(name="Forced By", value=interaction.user.name, inline=True)
                        await interaction.followup.send(embed=embed)
                        return
                await interaction.followup.send(f"Roblox user '{roblox_username}' not found.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

@bot.tree.command(name="stats", description="View your statistics")
@linked_only()
async def stats(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    if user_id not in data:
        embed = discord.Embed(
            title="Your Statistics",
            description="No stats available yet. Play some games to see your stats.",
            color=0x00ccff
        )
        await interaction.response.send_message(embed=embed)
        return
    user_data = data[user_id]
    roblox_username = user_data.get("roblox_username", "Not linked")
    wagered = user_data.get("wagered", 0)
    wins = user_data.get("wins", 0)
    losses = user_data.get("losses", 0)
    total_games = wins + losses
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    inventory = user_data.get("inventory", [])
    total_value = calculate_total_value(inventory)
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s Statistics",
        color=0x00ccff,
        timestamp=datetime.now()
    )
    embed.add_field(name="Roblox Account", value=roblox_username, inline=False)
    embed.add_field(name="Total Wagered", value=add_suffix2(wagered), inline=True)
    embed.add_field(name="Games Played", value=str(total_games), inline=True)
    embed.add_field(name="Wins", value=str(wins), inline=True)
    embed.add_field(name="Losses", value=str(losses), inline=True)
    embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%", inline=True)
    embed.add_field(name="Inventory Value", value=add_suffix2(total_value), inline=True)
    await interaction.response.send_message(embed=embed)

api_app = Flask(__name__)

DEPOSIT_RATE_LIMIT_SECONDS = 10
deposit_cooldowns = {}

@api_app.route('/api/deposit', methods=['POST', 'OPTIONS'])
def handle_deposit():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        roblox_id = data.get('roblox_id')
        pets = data.get('pets', [])
        gems = data.get('gems', 0)
        print(f"[Deposit] Received from Roblox ID: {roblox_id}")
        if not roblox_id:
            return jsonify({"error": "No roblox_id provided"}), 400
        current_time = time()
        roblox_id_str = str(roblox_id)
        if roblox_id_str in deposit_cooldowns:
            time_since_last = current_time - deposit_cooldowns[roblox_id_str]
            if time_since_last < DEPOSIT_RATE_LIMIT_SECONDS:
                print(f"[Deposit] Rate limited: Roblox ID {roblox_id} tried again after {time_since_last:.1f}s")
                return jsonify({
                    "error": f"Please wait {DEPOSIT_RATE_LIMIT_SECONDS - time_since_last:.1f} seconds before depositing again",
                    "retry_after": DEPOSIT_RATE_LIMIT_SECONDS - time_since_last
                }), 429
        deposit_cooldowns[roblox_id_str] = current_time
        if len(deposit_cooldowns) > 1000:
            old_threshold = current_time - 60
            to_remove = [rid for rid, ts in deposit_cooldowns.items() if ts < old_threshold]
            for rid in to_remove:
                del deposit_cooldowns[rid]
        user_links = load_user_links()
        link_data = user_links.get(roblox_id_str)
        if not link_data:
            print(f"[Deposit] No Discord account linked to Roblox ID {roblox_id}")
            return jsonify({"error": "No Discord account linked to this Roblox account. Please use /link in Discord first."}), 404
        discord_id = link_data.get("discord_id")
        roblox_username = link_data.get("roblox_username")
        data_store = load_data()
        if discord_id not in data_store:
            data_store[discord_id] = {
                "inventory": [],
                "wagered": 0,
                "wins": 0,
                "losses": 0,
                "roblox_id": str(roblox_id),
                "roblox_username": roblox_username
            }
        user_inventory = data_store[discord_id].get("inventory", [])
        added_pets = []
        added_gems = 0
        if gems > 0:
            remaining_gems = gems
            for pack_name, pack_value in sorted(GEM_PACK_VALUES.items(), key=lambda x: x[1], reverse=True):
                if remaining_gems >= pack_value:
                    num_packs = remaining_gems // pack_value
                    for _ in range(num_packs):
                        user_inventory.append(f"{pack_name} Gems")
                        added_gems += pack_value
                    remaining_gems -= num_packs * pack_value
            if remaining_gems > 0:
                user_inventory.append(f"{remaining_gems} Gems")
                added_gems += remaining_gems
        pet_names = []
        for pet in pets:
            user_inventory.append(pet)
            pet_names.append(pet)
            added_pets.append(pet)
        data_store[discord_id]["inventory"] = user_inventory
        save_data(data_store)
        total_value = added_gems + sum(get_pet_value_from_json(p) for p in added_pets)
        user_obj = bot.get_user(int(discord_id))
        if user_obj:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            asyncio.run_coroutine_threadsafe(
                send_deposit_log("Auto", user_obj, roblox_id, roblox_username, pet_names, added_gems, total_value),
                loop
            )
        update_leaderboard_stats(discord_id)
        print(f"[Deposit] Processed {len(pet_names)} pets and {format_value(added_gems)} gems for {roblox_username}")
        return jsonify({
            "success": True,
            "message": f"Added {len(pet_names)} pets and {format_value(added_gems)} gems to your inventory",
            "pets_added": len(pet_names),
            "gems_added": added_gems,
            "total_value": total_value
        }), 200
    except Exception as e:
        print(f"[Deposit] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def run_api_server():
    print(f"Starting API server on port {API_PORT}...")
    api_app.run(host='0.0.0.0', port=API_PORT, debug=False, use_reloader=False)

@bot.event
async def on_ready():
    ensure_files_exist()
    print(f"Logged in as {bot.user}")
    asyncio.create_task(scraper_updater())
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    print(f"API server running on port {API_PORT}")
    try:
        synced = await bot.tree.sync()
        print(f"Loaded {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="add-pet", description="Add a pet to a user's inventory (Admin)")
@app_commands.describe(user="User to add the pet to", pet_name="Name of the pet", amount="How many pets to add")
@app_commands.autocomplete(pet_name=pet_autocomplete)
async def add_pet(interaction: discord.Interaction, user: discord.User, pet_name: str, amount: int = 1):
    if str(interaction.user.id) not in ALLOWED_ADMINS:
        await interaction.response.send_message("You are not allowed to use this command", ephemeral=True)
        return
    await interaction.response.defer()
    try:
        with open(PET_VALUES_FILE, "r") as f:
            pets = json.load(f)
        pet_name_clean = None
        for name in pets:
            if name.lower() == pet_name.lower():
                pet_name_clean = name
                break
        if not pet_name_clean:
            await interaction.followup.send(f"Pet '{pet_name}' not found in database")
            return
        data = load_data()
        user_id = str(user.id)
        if user_id not in data:
            data[user_id] = {
                "inventory": [],
                "wagered": 0,
                "wins": 0,
                "losses": 0,
                "roblox_id": None,
                "roblox_username": None
            }
        inventory = data[user_id].get("inventory", [])
        inventory.extend([pet_name_clean] * amount)
        data[user_id]["inventory"] = inventory
        save_data(data)
        update_leaderboard_stats(user_id)
        embed = discord.Embed(
            title=f"Added {amount}x {pet_name_clean}",
            description=f"Added {amount}x {pet_name_clean} to {user.mention}'s Inventory",
            color=0x00ff00
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="add-gems", description="Add gem packs to a user's inventory (Admin)")
@app_commands.describe(user="User to give gems to", amount="Amount of gem", quantity="How many gem packs to add")
async def add_gems(interaction: discord.Interaction, user: discord.User, amount: str, quantity: int = 1):
    if str(interaction.user.id) not in ALLOWED_ADMINS:
        await interaction.response.send_message("You are not allowed to use this command", ephemeral=True)
        return
    amount_upper = amount.upper()
    if amount_upper not in GEM_PACK_VALUES:
        allowed = ", ".join(GEM_PACK_VALUES.keys())
        await interaction.response.send_message(f"Invalid gem pack, allowed gem packs: {allowed}", ephemeral=True)
        return
    item_name = f"{amount_upper} Gems"
    total_value = GEM_PACK_VALUES[amount_upper] * quantity
    data = load_data()
    user_id = str(user.id)
    if user_id not in data:
        data[user_id] = {
            "inventory": [],
            "wagered": 0,
            "wins": 0,
            "losses": 0,
            "roblox_id": None,
            "roblox_username": None
        }
    inventory = data[user_id].get("inventory", [])
    inventory.extend([item_name] * quantity)
    data[user_id]["inventory"] = inventory
    save_data(data)
    update_leaderboard_stats(user_id)
    embed = discord.Embed(
        title=f"Added {quantity}x {item_name}",
        description=f"Added {quantity}x {item_name} (Total: {format_value(total_value)}) to {user.mention}'s Inventory",
        color=0x00ff00
    )
    await interaction.response.send_message(embed=embed)

@add_gems.autocomplete("amount")
async def gem_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=label, value=label) for label in GEM_PACK_VALUES.keys() if current.upper() in label][:25]

class InventoryView(discord.ui.View):
    def __init__(self, user, inventory_items):
        super().__init__(timeout=60)
        self.user = user
        self.page = 0
        self.item_counter = Counter(inventory_items)
        self.items = list(self.item_counter.items())
        self.total_pages = max(1, math.ceil(len(self.items) / 15))

    async def fetch_page_embeds(self):
        start = self.page * 15
        end = start + 15
        items_on_page = self.items[start:end]
        description_lines = []
        for item_name, count in items_on_page:
            prefix = f"{count}x " if count > 1 else ""
            if "Gems" in item_name:
                description_lines.append(f"- {prefix}{item_name}")
            else:
                value = get_pet_value_from_json(item_name)
                if value > 0:
                    description_lines.append(f"- {prefix}{item_name} ({add_suffix2(value)})")
                else:
                    description_lines.append(f"- {prefix}{item_name}")
        embed = discord.Embed(
            title=f"{self.user.name}'s Inventory",
            description="\n".join(description_lines) or "Inventory empty",
            color=0x0062FF
        )
        embed.set_footer(text=f"Page {self.page + 1} of {self.total_pages}")
        return embed

    async def update_message(self, interaction):
        embed = await self.fetch_page_embeds()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Not your inventory", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Not your inventory", ephemeral=True)
            return
        if self.page < self.total_pages - 1:
            self.page += 1
            await self.update_message(interaction)

@bot.tree.command(name="inventory", description="View your inventory")
@linked_only()
async def inventory(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    inventory_items = data.get(user_id, {}).get("inventory", [])
    if not inventory_items:
        await interaction.response.send_message("Your inventory is empty")
        return
    total_value = calculate_total_value(inventory_items)
    view = InventoryView(interaction.user, inventory_items)
    embed = await view.fetch_page_embeds()
    embed.set_footer(text=f"Total Value: {add_suffix2(total_value)}")
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="value", description="Get the value of a pet")
@app_commands.describe(pet_name="Enter the pet's name")
@app_commands.autocomplete(pet_name=pet_autocomplete)
async def pet_value(interaction: discord.Interaction, pet_name: str):
    try:
        with open(PET_VALUES_FILE, "r") as f:
            pets = json.load(f)
        pet_details = None
        for name, data in pets.items():
            if name.lower() == pet_name.lower():
                pet_details = data
                pet_details["name"] = name
                break
        if pet_details is None:
            await interaction.response.send_message("Pet not found", ephemeral=True)
            return
        embed = discord.Embed(title=pet_details["name"], color=0x0062FF)
        embed.add_field(name="Value", value=pet_details["formatted_value"], inline=True)
        embed.add_field(name="Demand", value=pet_details["demand"], inline=True)
        deposit_value = suffix_to_int2(pet_details["formatted_value"])
        if isinstance(deposit_value, (int, float)) and deposit_value > 0:
            depo_value = deposit_value * 0.9
            embed.add_field(name="Deposit Value", value=add_suffix2(depo_value), inline=True)
        else:
            embed.add_field(name="Deposit Value", value=pet_details["formatted_value"], inline=True)
        timestamp = get_timestamp(pet_details["last_updated"])
        if timestamp != "Unknown":
            embed.add_field(name="Last Updated", value=f"<t:{timestamp}:R>", inline=False)
        if pet_details["image_url"] != "unknown":
            embed.set_thumbnail(url=pet_details["image_url"])
        embed.set_footer(text="Credits to Cosmic Values")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

@bot.tree.command(name="tip", description="Send your pets to another user")
@linked_only()
@app_commands.describe(user="The user to send pets to")
async def tip(interaction: discord.Interaction, user: discord.User):
    if user == interaction.user:
        await interaction.response.send_message("You can't tip yourself", ephemeral=True)
        return
    data = load_data()
    user_id = str(interaction.user.id)
    inventory_items = data.get(user_id, {}).get("inventory", [])
    if not inventory_items:
        await interaction.response.send_message("Your inventory is empty", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"Send items to {user.display_name}",
        description="Select items from the dropdown menu below to send. Each click selects ONE item from the stack.",
        color=0x0062FF
    )
    view = PaginatedSelectView(interaction.user, inventory_items, f"Send to {user.display_name}", "Select items to tip:", mode="tip")
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    await view.wait()
    if view.confirmed and view.selected_items:
        receiver_id = str(user.id)
        sender_id = str(interaction.user.id)
        data = load_data()
        if sender_id not in data:
            data[sender_id] = {"inventory": [], "wagered": 0, "wins": 0, "losses": 0, "roblox_id": None, "roblox_username": None}
        if receiver_id not in data:
            data[receiver_id] = {"inventory": [], "wagered": 0, "wins": 0, "losses": 0, "roblox_id": None, "roblox_username": None}
        sender_inventory = data[sender_id].get("inventory", [])
        receiver_inventory = data[receiver_id].get("inventory", [])
        items_to_remove = view.selected_items.copy()
        new_sender = []
        for item in sender_inventory:
            if items_to_remove and item == items_to_remove[0]:
                items_to_remove.pop(0)
                receiver_inventory.append(item)
            else:
                new_sender.append(item)
        data[sender_id]["inventory"] = new_sender
        data[receiver_id]["inventory"] = receiver_inventory
        save_data(data)
        update_leaderboard_stats(sender_id)
        update_leaderboard_stats(receiver_id)
        total_value = calculate_total_value(view.selected_items)
        items_summary = summarize_items(view.selected_items)
        embed = discord.Embed(
            title="Items Sent",
            description=f"Sent {len(view.selected_items)} item(s) to {user.mention}\n\n**Items:**\n" + "\n".join(f"• {item}" for item in items_summary[:10]) + f"\n\n**Total Value:** {add_suffix2(total_value)}",
            color=0x00ff00
        )
        await interaction.edit_original_response(embed=embed, view=None)

@bot.tree.command(name="withdraw", description="Withdraw item(s) from your inventory")
@linked_only()
async def withdraw(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    inventory_items = data.get(user_id, {}).get("inventory", [])
    if not inventory_items:
        await interaction.response.send_message("Your inventory is empty", ephemeral=True)
        return
    embed = discord.Embed(
        title="Withdraw Items",
        description="Select items from the dropdown menu below to withdraw. Each click selects ONE item from the stack.",
        color=0x00ccff
    )
    view = PaginatedSelectView(interaction.user, inventory_items, "Withdraw Items", "Select items to withdraw:", mode="withdraw")
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    await view.wait()
    if view.confirmed and view.selected_items:
        withdraws = load_withdraws()
        items_to_remove = view.selected_items.copy()
        new_inventory = []
        for item in inventory_items:
            if items_to_remove and item == items_to_remove[0]:
                items_to_remove.pop(0)
            else:
                new_inventory.append(item)
        data[user_id]["inventory"] = new_inventory
        save_data(data)
        update_leaderboard_stats(user_id)
        withdraws.append({
            "user_id": user_id,
            "user_name": interaction.user.name,
            "items": view.selected_items,
            "timestamp": datetime.now().isoformat()
        })
        save_withdraws(withdraws)
        items_summary = summarize_items(view.selected_items)
        category = discord.utils.get(interaction.guild.categories, name="Withdraws")
        if category:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
                interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }
            staff_role = discord.utils.get(interaction.guild.roles, name="Depo / Withdraw Team")
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            channel = await interaction.guild.create_text_channel(
                name=f"{interaction.user.name}-withdraw",
                category=category,
                overwrites=overwrites
            )
            await channel.send(
                f"{interaction.user.mention} has withdrawn:\n" +
                "\n".join(f"- {item}" for item in items_summary)
            )
            await interaction.edit_original_response(content=f"Withdrew {len(view.selected_items)} item(s), check {channel.mention}", embed=None, view=None)
        else:
            await interaction.edit_original_response(content=f"Withdrew {len(view.selected_items)} item(s)", embed=None, view=None)

class DepositMethodView(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=60)
        self.user = user

    @discord.ui.button(label="Manual Deposit (Ticket)", style=discord.ButtonStyle.primary, row=0)
    async def manual_deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your deposit menu.", ephemeral=True)
            return
        await interaction.response.defer()
        category = discord.utils.get(interaction.guild.categories, name="Deposit Tickets")
        if not category and TICKET_CATEGORY_ID:
            category = interaction.guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            category = await interaction.guild.create_category("Deposit Tickets")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
        }
        staff_role = discord.utils.get(interaction.guild.roles, name="Depo / Withdraw Team")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
        ticket_number = len([c for c in category.channels if c.name.startswith("ticket-")]) + 1
        channel = await category.create_text_channel(
            name=f"ticket-{interaction.user.name}-{ticket_number}",
            overwrites=overwrites
        )
        embed = discord.Embed(
            title="Deposit Ticket Created",
            description=f"Please state the items you'd like to deposit in this channel. A staff member will assist you shortly.\n\n**Example:** Depositing: 2x Huge Cat, 100M Gems",
            color=0x00ff00
        )
        embed.add_field(name="User", value=interaction.user.mention, inline=True)
        embed.add_field(name="Ticket", value=channel.mention, inline=True)
        await channel.send(embed=embed)
        await interaction.followup.send(f"Ticket created. Please go to {channel.mention}", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Auto Deposit (Roblox Bot)", style=discord.ButtonStyle.success, row=0)
    async def auto_deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your deposit menu.", ephemeral=True)
            return
        embed = discord.Embed(
            title="Auto Deposit via Roblox Bot",
            description="To use auto deposit, follow these steps:",
            color=0x00ff00
        )
        embed.add_field(name="Step 1", value="Make sure you've linked your Roblox account using /link", inline=False)
        embed.add_field(name="Step 2", value="Join the Roblox game and send a trade request to the deposit bot", inline=False)
        embed.add_field(name="Step 3", value="Add the pets/gems you want to deposit to the trade", inline=False)
        embed.add_field(name="Step 4", value="Wait for the bot to verify and process your deposit", inline=False)
        embed.add_field(name="Note", value="Auto deposit only works for Huges, Titanics, Gargantuans, and 10M+ gems", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

@bot.tree.command(name="deposit", description="Deposit Pets/gems to your inventory")
@linked_only()
async def deposit(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Deposit Options",
        description="Please select how you want to deposit your items:",
        color=0x00ccff
    )
    view = DepositMethodView(interaction.user)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class HeadsTailsView(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=30)
        self.user = user
        self.choice = None

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.secondary, row=0)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return
        self.choice = 'heads'
        await interaction.response.edit_message(content="Selected Heads", view=None)
        self.stop()

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.secondary, row=0)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return
        self.choice = 'tails'
        await interaction.response.edit_message(content="Selected Tails", view=None)
        self.stop()

class CoinflipView(discord.ui.View):
    def __init__(self, starter, items, choice, fairness_data):
        super().__init__(timeout=300)
        self.starter = starter
        self.items = items
        self.starter_value = calculate_total_value(items)
        self.joiner = None
        self.joiner_items = []
        self.joiner_choice = None
        self.message = None
        self.choice = choice
        self.cancelled = False
        self.result_shown = False
        self.fairness_data = fairness_data

    async def update_message(self):
        embed = discord.Embed(title="Coinflip Match", color=0xD3D3D3)
        items_summary = summarize_items(self.items)
        items_text = "\n".join(f"• {item}" for item in items_summary)
        if len(items_text) > 1024:
            items_text = items_text[:1021] + "..."
        embed.add_field(name="Started by", value=self.starter.mention, inline=False)
        embed.add_field(name="Wagered Items", value=f"{items_text}\n**Total: {add_suffix2(self.starter_value)}**", inline=False)
        if self.joiner:
            embed.add_field(name="Sides", value=f"🔴 {self.starter.mention}: **{self.choice.upper()}**\n🔵 {self.joiner.mention}: **{self.joiner_choice.upper()}**", inline=False)
        else:
            embed.add_field(name="Sides", value=f"🔴 {self.starter.mention}: **{self.choice.upper()}**\n🔵 Waiting...", inline=False)
        await self.message.edit(embed=embed, view=self)

    async def on_timeout(self):
        if not self.joiner and not self.cancelled and self.message:
            self.cancelled = True
            data = load_data()
            user_id = str(self.starter.id)
            if user_id not in data:
                data[user_id] = {"inventory": [], "wagered": 0, "wins": 0, "losses": 0, "roblox_id": None, "roblox_username": None}
            data[user_id]["inventory"].extend(self.items)
            save_data(data)
            embed = discord.Embed(title="Coinflip Expired", description=f"{self.starter.mention}'s coinflip has expired and items have been returned.", color=0xff0000)
            await self.message.edit(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.starter:
            await interaction.response.send_message("Only the creator can cancel this coinflip.", ephemeral=True)
            return
        if self.joiner:
            await interaction.response.send_message("Cannot cancel - someone has already joined.", ephemeral=True)
            return
        self.cancelled = True
        data = load_data()
        user_id = str(self.starter.id)
        if user_id not in data:
            data[user_id] = {"inventory": [], "wagered": 0, "wins": 0, "losses": 0, "roblox_id": None, "roblox_username": None}
        data[user_id]["inventory"].extend(self.items)
        save_data(data)
        embed = discord.Embed(title="Coinflip Cancelled", description=f"{self.starter.mention} has cancelled their coinflip. Items have been returned.", color=0xff0000)
        await self.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Coinflip cancelled.", ephemeral=True)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success, row=0)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.joiner:
            await interaction.response.send_message("This coinflip already has a challenger.", ephemeral=True)
            return
        if interaction.user == self.starter:
            await interaction.response.send_message("You can't challenge your own coinflip.", ephemeral=True)
            return
        data = load_data()
        user_id = str(interaction.user.id)
        inventory_items = data.get(user_id, {}).get("inventory", [])
        if not inventory_items:
            await interaction.response.send_message("Your inventory is empty.", ephemeral=True)
            return
        opposite = 'tails' if self.choice == 'heads' else 'heads'
        embed = discord.Embed(
            title=f"Join Coinflip - Betting on {opposite.upper()}",
            description=f"Your bet must be between {add_suffix2(int(self.starter_value * 0.9))} and {add_suffix2(int(self.starter_value * 1.1))}",
            color=0x00ccff
        )
        view = PaginatedSelectView(interaction.user, inventory_items, f"Join Coinflip", f"Target: {add_suffix2(self.starter_value)}", mode="coinflip_join", target_value=self.starter_value)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.confirmed and view.selected_items:
            current_value = calculate_total_value(view.selected_items)
            min_bet = int(self.starter_value * 0.9)
            max_bet = int(self.starter_value * 1.1)
            if min_bet <= current_value <= max_bet:
                items_to_remove = view.selected_items.copy()
                new_inventory = []
                for item in inventory_items:
                    if items_to_remove and item == items_to_remove[0]:
                        items_to_remove.pop(0)
                    else:
                        new_inventory.append(item)
                data[user_id]["inventory"] = new_inventory
                save_data(data)
                self.joiner = interaction.user
                self.joiner_items = view.selected_items
                self.joiner_choice = opposite
                await self.update_message()
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
                await self.resolve()
            else:
                await interaction.followup.send(f"Your bet ({add_suffix2(current_value)}) must be between {add_suffix2(min_bet)} and {add_suffix2(max_bet)}.", ephemeral=True)
                data[user_id]["inventory"] = inventory_items
                save_data(data)

    async def animate_flip(self, winning_side: str):
        flip_gif_url = "https://www.image2url.com/r2/default/gifs/1776004675449-33784738-f7f3-48df-8b62-5195eb064f02.gif"
        flip_embed = discord.Embed(
            title="Flipping the Coin...",
            description=f"**{self.starter.display_name}** chose **{self.choice.upper()}**\n**{self.joiner.display_name}** chose **{self.joiner_choice.upper()}**",
            color=0xD3D3D3
        )
        flip_embed.set_image(url=flip_gif_url)
        flip_embed.set_footer(text="Flipping...")
        await self.message.edit(embed=flip_embed, view=None)
        await asyncio.sleep(4)
        if winning_side == 'heads':
            result_image = "https://media.discordapp.net/attachments/1492180470413266964/1492895436653068308/heads.png"
            result_title = "Heads"
        else:
            result_image = "https://media.discordapp.net/attachments/1492180470413266964/1492895436300882092/trails.png"
            result_title = "Tails"
        result_embed = discord.Embed(
            title=f"The coin landed on {result_title}!",
            description=f"**{self.starter.display_name}** → {self.choice.upper()}\n**{self.joiner.display_name}** → {self.joiner_choice.upper()}",
            color=0xD3D3D3
        )
        result_embed.set_thumbnail(url=result_image)
        return result_embed

    async def resolve(self):
        if not self.joiner or self.result_shown:
            return
        self.result_shown = True
        result = calculate_coinflip_result(self.fairness_data.server_seed, self.fairness_data.client_seed, self.fairness_data.nonce)
        self.fairness_data.result = result
        if result == self.choice:
            winner = self.starter
            loser = self.joiner
            winning_side = self.choice
        else:
            winner = self.joiner
            loser = self.starter
            winning_side = self.joiner_choice
        result_embed = await self.animate_flip(winning_side)
        update_wins_losses(str(winner.id), True)
        update_wins_losses(str(loser.id), False)
        all_items = self.items + self.joiner_items
        total_value = calculate_total_value(all_items)
        server_profit = int(total_value * 0.1)
        starter_wagered = self.starter_value
        joiner_wagered = calculate_total_value(self.joiner_items)
        update_wagered(str(self.starter.id), starter_wagered)
        update_wagered(str(self.joiner.id), joiner_wagered)
        data = load_data()
        winner_id = str(winner.id)
        if winner_id not in data:
            data[winner_id] = {"inventory": [], "wagered": 0, "wins": 0, "losses": 0, "roblox_id": None, "roblox_username": None}
        winner_inventory = data[winner_id].get("inventory", [])
        winner_inventory.extend(all_items)
        data[winner_id]["inventory"] = winner_inventory
        remaining_tax = server_profit
        items_to_remove = []
        tax_items = []
        tax_value = 0
        items_with_values = [(item, get_item_value(item)) for item in all_items]
        items_with_values.sort(key=lambda x: x[1])
        for item, value in items_with_values:
            if remaining_tax <= 0:
                break
            items_to_remove.append(item)
            tax_items.append(item)
            tax_value += value
            remaining_tax -= value
        for item in items_to_remove:
            try:
                winner_inventory.remove(item)
            except ValueError:
                pass
        if tax_items:
            owner_id = OWNER_USER_ID
            if owner_id not in data:
                data[owner_id] = {"inventory": [], "wagered": 0, "wins": 0, "losses": 0, "roblox_id": None, "roblox_username": None}
            data[owner_id]["inventory"].extend(tax_items)
            add_profit(tax_value)
            await send_tax_log(winner, loser, tax_value, tax_items, total_value)
        over_collected = tax_value - server_profit
        if over_collected > 0:
            profit_data = load_profit_data()
            profit_data["total_profit"] = max(0, profit_data.get("total_profit", 0) - over_collected)
            save_profit_data(profit_data)
            remaining_refund = over_collected
            for pack_name, pack_value in sorted(GEM_PACK_VALUES.items(), key=lambda x: x[1], reverse=True):
                if remaining_refund >= pack_value:
                    num_packs = remaining_refund // pack_value
                    for _ in range(num_packs):
                        winner_inventory.append(f"{pack_name} Gems")
                    remaining_refund -= num_packs * pack_value
            if remaining_refund > 0:
                winner_inventory.append(f"{remaining_refund} Gems")
        data[winner_id]["inventory"] = winner_inventory
        save_data(data)
        update_leaderboard_stats(str(self.starter.id))
        update_leaderboard_stats(str(self.joiner.id))
        winnings = total_value - server_profit
        result_embed.add_field(name="Winner", value=winner.mention, inline=True)
        result_embed.add_field(name="Loser", value=loser.mention, inline=True)
        result_embed.add_field(name="Total Pot", value=add_suffix2(total_value), inline=True)
        result_embed.add_field(name="Winnings", value=add_suffix2(winnings), inline=True)
        result_embed.add_field(name="Server Profit (10%)", value=add_suffix2(tax_value), inline=True)
        final_view = discord.ui.View()
        final_view.add_item(FairnessButton(self.fairness_data))
        await self.message.edit(embed=result_embed, view=final_view)

@bot.tree.command(name="coinflip", description="Start a coinflip")
@linked_only()
async def coinflip(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    inventory_items = data.get(user_id, {}).get("inventory", [])
    if not inventory_items:
        await interaction.response.send_message("Your inventory is empty", ephemeral=True)
        return
    view = HeadsTailsView(interaction.user)
    embed = discord.Embed(
        title="Choose Heads or Tails",
        description="Select which side you want to bet on.",
        color=0x00ccff
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    await view.wait()
    if not view.choice:
        await interaction.followup.send("Timeout. Please try again.", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"Select Items (Choice: {view.choice.upper()})",
        description="Select items from the dropdown menu below to bet. Each click selects ONE item from the stack.",
        color=0x00ff00 if view.choice == 'heads' else 0x0000ff
    )
    select_view = PaginatedSelectView(interaction.user, inventory_items, f"Create Coinflip - Betting on {view.choice.upper()}", "Select items to bet:", mode="coinflip_create")
    await interaction.followup.send(embed=embed, view=select_view, ephemeral=True)
    await select_view.wait()
    if select_view.confirmed and select_view.selected_items:
        data = load_data()
        user_id = str(interaction.user.id)
        inventory_items = data.get(user_id, {}).get("inventory", [])
        items_to_remove = select_view.selected_items.copy()
        new_inventory = []
        for item in inventory_items:
            if items_to_remove and item == items_to_remove[0]:
                items_to_remove.pop(0)
            else:
                new_inventory.append(item)
        data[user_id]["inventory"] = new_inventory
        save_data(data)
        channel = bot.get_channel(COINFLIP_CHANNEL_ID)
        if not channel:
            await interaction.edit_original_response(content="Coinflip channel not found.", embed=None, view=None)
            return
        server_seed = generate_server_seed()
        client_seed = generate_client_seed()
        nonce = generate_nonce()
        fairness_data = CoinflipFairnessData(server_seed, client_seed, nonce, view.choice)
        items_summary = summarize_items(select_view.selected_items)
        items_value = calculate_total_value(select_view.selected_items)
        items_text = "\n".join(f"• {item}" for item in items_summary)
        if len(items_text) > 1024:
            items_text = items_text[:1021] + "..."
        embed = discord.Embed(
            title="Coinflip Match",
            color=0xD3D3D3
        )
        embed.add_field(name="Started by", value=interaction.user.mention, inline=False)
        embed.add_field(name="Wagered Items", value=f"{items_text}\n**Total: {add_suffix2(items_value)}**", inline=False)
        embed.add_field(name="Sides", value=f"🔴 {interaction.user.mention}: **{view.choice.upper()}**\n🔵 Waiting...", inline=False)
        coinflip_view = CoinflipView(interaction.user, select_view.selected_items, view.choice, fairness_data)
        message = await channel.send(embed=embed, view=coinflip_view)
        coinflip_view.message = message
        await interaction.edit_original_response(content="Your coinflip has been posted in the coinflip channel.", embed=None, view=None)
    else:
        await interaction.edit_original_response(content="Coinflip creation cancelled.", embed=None, view=None)

@bot.tree.command(name="leaderboard", description="View the leaderboard")
async def leaderboard(interaction: discord.Interaction):
    data = load_data()
    lb = load_leaderboard()
    for user_id, user_data in data.items():
        lb["wagered"][user_id] = user_data.get("wagered", 0)
        lb["value"][user_id] = calculate_total_value(user_data.get("inventory", []))
    save_leaderboard(lb)
    sorted_wagered = sorted(lb["wagered"].items(), key=lambda x: x[1], reverse=True)[:10]
    sorted_value = sorted(lb["value"].items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="Leaderboard", color=0xffd700)
    wagered_text = ""
    for i, (uid, val) in enumerate(sorted_wagered, 1):
        user = bot.get_user(int(uid))
        name = user.display_name if user else "Unknown"
        wagered_text += f"{i}. **{name}** - {add_suffix2(val)}\n"
    value_text = ""
    for i, (uid, val) in enumerate(sorted_value, 1):
        user = bot.get_user(int(uid))
        name = user.display_name if user else "Unknown"
        value_text += f"{i}. **{name}** - {add_suffix2(val)}\n"
    embed.add_field(name="Most Wagered", value=wagered_text or "None", inline=True)
    embed.add_field(name="Most Value", value=value_text or "None", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverprofit", description="Check total server profit from coinflips")
async def serverprofit(interaction: discord.Interaction):
    profit_data = load_profit_data()
    total_profit = profit_data.get("total_profit", 0)
    embed = discord.Embed(
        title="Server Profit",
        description=f"Total profit from all coinflip games",
        color=0x00ff00
    )
    embed.add_field(name="Total Server Profit", value=add_suffix2(total_profit), inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="force-update-pets", description="Force update pet values database (Admin)")
async def force_update_pets(interaction: discord.Interaction):
    if str(interaction.user.id) not in ALLOWED_ADMINS:
        await interaction.response.send_message("Not allowed", ephemeral=True)
        return
    await interaction.response.send_message("Starting pet data update. This may take a few minutes.", ephemeral=True)
    try:
        await scrape_cosmic_values()
        await interaction.followup.send("Pet database has been updated successfully.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error updating pet database: {e}", ephemeral=True)

@bot.tree.command(name="close", description="Close a ticket or withdraw channel")
async def close_channel(interaction: discord.Interaction):
    channel = interaction.channel
    is_ticket = channel.name.startswith("ticket-") or (channel.category and channel.category.name == "Deposit Tickets")
    is_withdraw = channel.name.endswith("-withdraw") or (channel.category and channel.category.name == "Withdraws")
    if not is_ticket and not is_withdraw:
        await interaction.response.send_message("This command can only be used in ticket or withdraw channels.", ephemeral=True)
        return
    allowed = False
    if str(interaction.user.id) in ALLOWED_ADMINS:
        allowed = True
    staff_role = discord.utils.get(interaction.guild.roles, name="Depo / Withdraw Team")
    if staff_role and staff_role in interaction.user.roles:
        allowed = True
    if is_ticket:
        parts = channel.name.split("-")
        if len(parts) >= 2:
            creator_name = parts[1]
            if creator_name.lower() == interaction.user.name.lower():
                allowed = True
    if not allowed:
        await interaction.response.send_message("You don't have permission to close this channel.", ephemeral=True)
        return
    class CloseConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)
        @discord.ui.button(label="Yes, Close Channel", style=discord.ButtonStyle.danger, row=0)
        async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            channel_name = channel.name
            channel_category = channel.category.name if channel.category else "No Category"
            messages = []
            try:
                async for msg in channel.history(limit=50):
                    messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.name}: {msg.content[:100]}")
            except:
                messages = ["Could not fetch message history"]
            transcript_embed = discord.Embed(
                title=f"Channel Closed: {channel_name}",
                description=f"Channel was closed by {interaction.user.mention}",
                color=0xff0000,
                timestamp=datetime.utcnow()
            )
            transcript_embed.add_field(name="Category", value=channel_category, inline=True)
            transcript_embed.add_field(name="Channel Type", value="Ticket" if is_ticket else "Withdraw", inline=True)
            transcript_embed.add_field(name="Closed By", value=f"{interaction.user.name} ({interaction.user.id})", inline=False)
            transcript_text = "\n".join(messages[-20:])
            if transcript_text:
                if len(transcript_text) > 1000:
                    transcript_text = transcript_text[:997] + "..."
                transcript_embed.add_field(name="Recent Messages", value=f"```{transcript_text}```", inline=False)
            if DEPOSIT_LOG_CHANNEL_ID:
                try:
                    log_channel = interaction.guild.get_channel(DEPOSIT_LOG_CHANNEL_ID)
                    if log_channel:
                        await log_channel.send(embed=transcript_embed)
                except:
                    pass
            try:
                dm_embed = discord.Embed(
                    title=f"Channel Closed: {channel_name}",
                    description=f"Your {'ticket' if is_ticket else 'withdraw request'} has been closed.",
                    color=0xffaa00
                )
                await interaction.user.send(embed=dm_embed)
            except:
                pass
            await channel.delete(reason=f"Closed by {interaction.user.name}")
            try:
                await interaction.followup.send(f"Channel `{channel_name}` has been closed and deleted.", ephemeral=True)
            except:
                pass
            self.stop()
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
        async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(content="Channel close cancelled.", view=None)
            self.stop()
    embed = discord.Embed(
        title="Close Channel",
        description=f"Are you sure you want to close this channel?\n\n**Channel:** {channel.mention}\n**Type:** {'Ticket' if is_ticket else 'Withdraw Channel'}\n\nThis action cannot be undone.",
        color=0xff0000
    )
    view = CloseConfirmView()
    await interaction.response.send_message(embed=embed, view=view)

if __name__ == "__main__":
    ensure_files_exist()
    bot.run("YOUR_BOT_TOKEN_HERE")
