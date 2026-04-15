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

TOKEN = ""
ALLOWED_ADMINS = ["1317787152217673749"]
API_PORT = 35585
PET_VALUES_FILE = "pets.json"
PET_ICONS_FILE = "pet_icons.json"
COINFLIP_CHANNEL_ID = 123
OWNER_USER_ID = "123"
TAX_WEBHOOK_URL = "123"
DEPOSIT_WEBHOOK_URL = "123" # deposit webhook doesnt work yet but it adds the items to inv so dw

DEPOSIT_RATE_LIMIT_SECONDS = 10
deposit_cooldowns = {}

datafile = "data.json"
user_links_file = "user_links.json"
profit_data_file = "profit_data.json"
withdraws_file = "withdraws.json"

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

def load_data():
    try:
        with open(datafile, "r") as f:
            return json.load(f)
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

async def check_linked(interaction):
    user_links = load_user_links()
    for roblox_id, data in user_links.items():
        if data.get("discord_id") == str(interaction.user.id):
            return True
    return False

def linked_only():
    async def predicate(interaction):
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

async def send_tax_log(winner, loser, tax_amount, tax_items, total_pot):
    if not TAX_WEBHOOK_URL:
        return
    embed = discord.Embed(
        title="Tax Collection Log",
        color=0xff0000,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Winner", value=winner.mention, inline=True)
    embed.add_field(name="Loser", value=loser.mention, inline=True)
    embed.add_field(name="Total Pot", value=f"{add_suffix2(total_pot)}", inline=True)
    embed.add_field(name="Tax Collected (10%)", value=f"{add_suffix2(tax_amount)}", inline=True)
    if tax_items:
        tax_summary = summarize_items(tax_items)
        embed.add_field(name="Tax Items", value="\n".join(f"- {item}" for item in tax_summary[:10]), inline=False)
    async with aiohttp.ClientSession() as session:
        await session.post(TAX_WEBHOOK_URL, json={"embeds": [embed.to_dict()]})

async def send_deposit_log(deposit_type, user, roblox_id, roblox_username, items, gems, total_value):
    if not DEPOSIT_WEBHOOK_URL:
        return
    embed = discord.Embed(
        title=f"Deposit Log - {deposit_type}",
        color=0x00ff00 if deposit_type == "Auto" else 0xffaa00,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Discord User", value=user.mention if isinstance(user, discord.User) else f"<@{user}>", inline=True)
    embed.add_field(name="Discord ID", value=user.id if isinstance(user, discord.User) else user, inline=True)
    embed.add_field(name="Roblox ID", value=str(roblox_id), inline=True)
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    if items:
        items_summary = summarize_items(items)
        embed.add_field(name="Pets Deposited", value="\n".join(f"- {item}" for item in items_summary[:15]), inline=False)
    if gems > 0:
        embed.add_field(name="Gems Deposited", value=f"{add_suffix2(gems)}", inline=True)
    embed.add_field(name="Total Value", value=f"{add_suffix2(total_value)}", inline=True)
    async with aiohttp.ClientSession() as session:
        await session.post(DEPOSIT_WEBHOOK_URL, json={"embeds": [embed.to_dict()]})

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

def get_pet_value_from_json(pet_name):
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

def get_item_value(item_name):
    if "Gems" in item_name:
        try:
            amount_str = item_name.split()[0].lower()
            return GEM_PACK_VALUES.get(amount_str.upper(), 0)
        except:
            return 0
    else:
        return get_pet_value_from_json(item_name)

def calculate_total_value(items):
    return sum(get_item_value(item) for item in items)

def add_profit(amount):
    data = load_profit_data()
    data["total_profit"] = data.get("total_profit", 0) + amount
    save_profit_data(data)

async def pet_autocomplete(interaction, current):
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

@bot.tree.command(name="link", description="Link your Roblox account to Discord")
@app_commands.describe(roblox_username="Your Roblox username")
async def link_account(interaction, roblox_username):
    await interaction.response.defer()
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [roblox_username]}
    async with aiohttp.ClientSession() as session:
        try:
            for attempt in range(3):
                try:
                    async with session.post(url, json=payload, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and data.get("data") and len(data["data"]) > 0:
                                user_data = data["data"][0]
                                roblox_id = user_data["id"]
                                user_links = load_user_links()
                                user_links[str(roblox_id)] = {
                                    "discord_id": str(interaction.user.id),
                                    "discord_name": interaction.user.name,
                                    "roblox_username": roblox_username,
                                    "linked_at": datetime.now().isoformat()
                                }
                                save_user_links(user_links)
                                embed = discord.Embed(
                                    title="Account Linked",
                                    description=f"Successfully linked {roblox_username} (ID: {roblox_id}) to your Discord account.",
                                    color=0x00ff00
                                )
                                await interaction.followup.send(embed=embed)
                                return
                            else:
                                await interaction.followup.send(f"Roblox user '{roblox_username}' not found.", ephemeral=True)
                                return
                        else:
                            if attempt < 2:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            else:
                                await interaction.followup.send(f"Roblox API error (status {resp.status}). Please try again later.", ephemeral=True)
                                return
                except asyncio.TimeoutError:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        await interaction.followup.send("Connection to Roblox API timed out. Please try again later.", ephemeral=True)
                        return
                except aiohttp.ClientError as e:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        await interaction.followup.send(f"Network error connecting to Roblox: {str(e)}. Please contact an admin if this persists.", ephemeral=True)
                        return
        except Exception as e:
            await interaction.followup.send(f"Unexpected error: {str(e)}", ephemeral=True)

@bot.tree.command(name="unlink", description="Unlink your Roblox account from Discord")
async def unlink_account(interaction):
    user_links = load_user_links()
    found = False
    for roblox_id, data in list(user_links.items()):
        if data.get("discord_id") == str(interaction.user.id):
            del user_links[roblox_id]
            found = True
            break
    if found:
        save_user_links(user_links)
        embed = discord.Embed(
            title="Account Unlinked",
            description="Your Roblox account has been unlinked from Discord.",
            color=0x00ff00
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("You don't have any linked Roblox account.", ephemeral=True)

api_app = Flask(__name__)

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

@bot.tree.command(name="add-pet", description="Add a pet to a user's inventory")
@app_commands.describe(user="User to add the pet to", pet_name="Name of the pet", amount="How many pets to add")
@app_commands.autocomplete(pet_name=pet_autocomplete)
async def add_pet(interaction, user, pet_name, amount=1):
    if str(interaction.user.id) not in ALLOWED_ADMINS:
        await interaction.response.send_message("You are not allowed to use this command", ephemeral=True)
        return
    if amount < 1:
        await interaction.response.send_message("Amount must be at least 1", ephemeral=True)
        return
    await interaction.response.defer()
    try:
        with open(PET_VALUES_FILE, "r") as f:
            pets = json.load(f)
        pet_data = None
        pet_name_clean = None
        for name, data in pets.items():
            if name.lower() == pet_name.lower():
                pet_data = data
                pet_name_clean = name
                break
        if not pet_data:
            await interaction.followup.send(f"Pet '{pet_name}' not found in database")
            return
        pet_value = pet_data.get("formatted_value", "").upper()
        if pet_value in ["O/C", "N/A"]:
            await interaction.followup.send(f"You can't add this pet because its value is {pet_value}")
            return
        user_id = str(user.id)
        data = load_data()
        user_inventory = data.get(user_id, [])
        user_inventory.extend([pet_name_clean] * amount)
        data[user_id] = user_inventory
        save_data(data)
        embed = discord.Embed(
            title=f"Added {amount}x {pet_name_clean}",
            description=f"Added {amount}x {pet_name_clean} to {user.mention}'s Inventory",
            color=0x0062FF
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="add-gems", description="Add gem packs to a user's inventory")
@app_commands.describe(user="User to give gems to", amount="Amount of gem", quantity="How many gem packs to add")
async def add_gems(interaction, user, amount, quantity=1):
    if str(interaction.user.id) not in ALLOWED_ADMINS:
        await interaction.response.send_message("You are not allowed to use this command", ephemeral=True)
        return
    amount_upper = amount.upper()
    if amount_upper not in GEM_PACK_VALUES:
        allowed = ", ".join(GEM_PACK_VALUES.keys())
        await interaction.response.send_message(f"Invalid gem pack, allowed gem packs: {allowed}", ephemeral=True)
        return
    if quantity < 1:
        await interaction.response.send_message("Quantity must be at least 1", ephemeral=True)
        return
    item_name = f"{amount_upper} Gems"
    total_value = GEM_PACK_VALUES[amount_upper] * quantity
    data = load_data()
    user_id = str(user.id)
    inventory = data.get(user_id, [])
    inventory.extend([item_name] * quantity)
    data[user_id] = inventory
    save_data(data)
    embed = discord.Embed(
        title=f"Added {quantity}x {item_name}", 
        description=f"Added {quantity}x {item_name} (Total: {format_value(total_value)}) to {user.mention}'s Inventory",
        color=0x0062FF
    )
    await interaction.response.send_message(embed=embed)

@add_gems.autocomplete("amount")
async def gem_pack_autocomplete(interaction, current):
    current = current.lower()
    return [
        app_commands.Choice(name=label, value=label)
        for label in GEM_PACK_VALUES.keys()
        if current in label.lower()
    ][:25]

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
            if item_name.endswith("Gems"):
                label = item_name.replace(" Gems", "").lower()
                if label.upper() in GEM_PACK_VALUES:
                    display = f"{label.upper()} - {label.upper()}"
                else:
                    display = f"{item_name} - Unknown Value"
                description_lines.append(f"- {prefix}{display}")
            else:
                value = get_pet_value_from_json(item_name)
                if value > 0:
                    display_name = item_name
                    description_lines.append(f"- {prefix}{display_name} - {format_value(value)}")
                else:
                    description_lines.append(f"- {prefix}{item_name} - Unknown Value")
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
    async def previous(self, interaction, button):
        if interaction.user != self.user:
            await interaction.response.send_message("Not your inventory", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next(self, interaction, button):
        if interaction.user != self.user:
            await interaction.response.send_message("Not your inventory", ephemeral=True)
            return
        if self.page < self.total_pages - 1:
            self.page += 1
            await self.update_message(interaction)

@bot.tree.command(name="inventory", description="View your inventory")
@linked_only()
async def inventory(interaction):
    user_id = str(interaction.user.id)
    data = load_data()
    inventory_items = data.get(user_id, [])
    if not inventory_items:
        await interaction.response.send_message("Your inventory is empty")
        return
    total_value = calculate_total_value(inventory_items)
    view = InventoryView(interaction.user, inventory_items)
    embed = await view.fetch_page_embeds()
    embed.set_footer(text=f"{view.page + 1}/{view.total_pages} Page | Total Value: {add_suffix2(total_value)}")
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="value", description="Get the value of a pet")
@app_commands.describe(pet_name="Enter the pet's name")
@app_commands.autocomplete(pet_name=pet_autocomplete)
async def pet_value(interaction, pet_name):
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
        deposit_value = suffix_to_int2(pet_details["formatted_value"])
        if isinstance(deposit_value, (int, float)) and deposit_value > 0:
            depo_value = deposit_value * 0.9  
            formatted_depo_value = add_suffix2(depo_value)
        else:
            formatted_depo_value = pet_details["formatted_value"]
        embed = discord.Embed(
            title=pet_details["name"],  
            color=0x0062FF
        )
        embed.add_field(name="Value", value=pet_details["formatted_value"], inline=True)
        embed.add_field(name="Demand", value=pet_details["demand"], inline=True)
        embed.add_field(name="Deposit Value", value=formatted_depo_value, inline=True)
        timestamp = get_timestamp(pet_details["last_updated"])
        if timestamp != "Unknown":
            embed.add_field(name="Last Updated", value=f"<t:{timestamp}:R>", inline=False)
        if pet_details["image_url"] != "unknown":
            embed.set_thumbnail(url=pet_details["image_url"])
        embed.set_footer(text="Credits to Cosmic Values")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

class TipPetView(discord.ui.View):
    def __init__(self, sender, receiver, pets):
        super().__init__(timeout=120)
        self.sender = sender
        self.receiver = receiver
        self.original_pets = pets
        self.pet_map = {i: pet for i, pet in enumerate(pets)}
        self.selected = set()
        self.page = 0
        self.per_page = 9
        self.max_page = max(1, math.ceil(len(self.pet_map) / self.per_page))
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = self.page * self.per_page
        end = start + self.per_page
        page_items = list(self.pet_map.items())[start:end]
        for idx, pet_name in page_items:
            selected = idx in self.selected
            style = discord.ButtonStyle.green if selected else discord.ButtonStyle.red
            emoji = "✅" if selected else "❌"
            row = (idx % self.per_page) // 3
            self.add_item(PetButton(label=pet_name[:50], style=style, emoji=emoji, pet_index=idx, row=row))
        self.add_item(NavigationButton("⬅️", -1, row=3))
        self.add_item(SendButton(self.sender, self.receiver, self, row=3))
        self.add_item(NavigationButton("➡️", 1, row=3))

    async def update_view(self, interaction):
        self.update_buttons()
        embed = discord.Embed(
            title=f"Send pets to {self.receiver.display_name}",
            description=f"Selected {len(self.selected)} items\nPage {self.page+1}/{self.max_page}",
            color=0x0062FF
        )
        await interaction.response.edit_message(embed=embed, view=self)

class PetButton(discord.ui.Button):
    def __init__(self, label, style, emoji, pet_index, row):
        super().__init__(label=label, style=style, emoji=emoji, row=row)
        self.pet_index = pet_index

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.sender:
            await interaction.response.send_message("Not your command", ephemeral=True)
            return
        if self.pet_index in view.selected:
            view.selected.remove(self.pet_index)
        else:
            view.selected.add(self.pet_index)
        await view.update_view(interaction)

class NavigationButton(discord.ui.Button):
    def __init__(self, emoji, direction, row):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.blurple, row=row)
        self.direction = direction

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.sender:
            await interaction.response.send_message("Not your command", ephemeral=True)
            return
        view.page = (view.page + self.direction) % view.max_page
        await view.update_view(interaction)

class SendButton(discord.ui.Button):
    def __init__(self, sender, receiver, view, row):
        super().__init__(label="Send", style=discord.ButtonStyle.green, row=row)
        self.sender = sender
        self.receiver = receiver
        self.tip_view = view

    async def callback(self, interaction):
        if interaction.user != self.sender:
            await interaction.response.send_message("Not your command", ephemeral=True)
            return
        if not self.tip_view.selected:
            await interaction.response.send_message("No pets selected to send", ephemeral=True)
            return
        data = load_data()
        sender_id = str(self.sender.id)
        receiver_id = str(self.receiver.id)
        sender_pets = data.get(sender_id, [])
        receiver_pets = data.get(receiver_id, [])
        for index in sorted(self.tip_view.selected, reverse=True):
            receiver_pets.append(sender_pets[index])
            del sender_pets[index]
        data[sender_id] = sender_pets
        data[receiver_id] = receiver_pets
        save_data(data)
        await interaction.response.edit_message(
            content=f"Sent {len(self.tip_view.selected)} item(s) to {self.receiver.mention}",
            embed=None,
            view=None
        )
        self.tip_view.stop()

@bot.tree.command(name="tip", description="Send your pets to another user")
@linked_only()
@app_commands.describe(user="The user to send pets to")
async def tip(interaction, user):
    if user == interaction.user:
        await interaction.response.send_message("You can't tip yourself", ephemeral=True)
        return
    data = load_data()
    user_id = str(interaction.user.id)
    pets = data.get(user_id, [])
    if not pets:
        await interaction.response.send_message("Your inventory is empty", ephemeral=True)
        return
    view = TipPetView(interaction.user, user, pets)
    embed = discord.Embed(
        title=f"Send pets to {user.display_name}",
        description="Click on pets to select/unselect them:",
        color=0x0062FF
    )
    await interaction.response.send_message(embed=embed, view=view)

WITHDRAW_CATEGORY_NAME = "Withdraws"

class WithdrawView(discord.ui.View):
    def __init__(self, user, inventory_items):
        super().__init__(timeout=120)
        self.user = user
        self.original_items = inventory_items
        self.item_map = {i: item for i, item in enumerate(inventory_items)}
        self.selected = set()
        self.page = 0
        self.per_page = 9
        self.max_page = max(1, math.ceil(len(self.item_map) / self.per_page))
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = self.page * self.per_page
        end = start + self.per_page
        page_items = list(self.item_map.items())[start:end]
        for idx, item_name in page_items:
            selected = idx in self.selected
            style = discord.ButtonStyle.green if selected else discord.ButtonStyle.red
            emoji = "✅" if selected else "❌"
            row = (idx % self.per_page) // 3
            self.add_item(WithdrawItemButton(label=item_name[:50], style=style, emoji=emoji, item_index=idx, row=row))
        self.add_item(WithdrawAllButton(self.user, self, row=3))
        self.add_item(WithdrawConfirmButton(self.user, self, row=3))
        self.add_item(WithdrawNavigationButton("⬅️", -1, row=3))
        self.add_item(WithdrawNavigationButton("➡️", 1, row=3))

    async def update_view(self, interaction):
        self.update_buttons()
        embed = discord.Embed(
            title="Withdraw Pets",
            description=f"Selected {len(self.selected)} items\nPage {self.page+1}/{self.max_page}",
            color=0x00ccff
        )
        await interaction.response.edit_message(embed=embed, view=self)

class WithdrawItemButton(discord.ui.Button):
    def __init__(self, label, style, emoji, item_index, row):
        super().__init__(label=label, style=style, emoji=emoji, row=row)
        self.item_index = item_index

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't your withdraw menu.", ephemeral=True)
            return
        if self.item_index in view.selected:
            view.selected.remove(self.item_index)
        else:
            view.selected.add(self.item_index)
        await view.update_view(interaction)

class WithdrawNavigationButton(discord.ui.Button):
    def __init__(self, emoji, direction, row):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.blurple, row=row)
        self.direction = direction

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't your withdraw menu.", ephemeral=True)
            return
        view.page = (view.page + self.direction) % view.max_page
        await view.update_view(interaction)

class WithdrawConfirmButton(discord.ui.Button):
    def __init__(self, user, view, row):
        super().__init__(label="Withdraw", style=discord.ButtonStyle.green, row=row)
        self.user = user
        self.withdraw_view = view

    async def callback(self, interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your withdraw menu.", ephemeral=True)
            return
        if not self.withdraw_view.selected:
            await interaction.response.send_message("You didn't select any items.", ephemeral=True)
            return
        data = load_data()
        withdraws = load_withdraws()
        user_id = str(self.user.id)
        user_inventory = data.get(user_id, [])
        selected_items = [user_inventory[i] for i in sorted(self.withdraw_view.selected)]
        for index in sorted(self.withdraw_view.selected, reverse=True):
            del user_inventory[index]
        save_data(data)
        withdraws.append({
            "user_id": user_id,
            "user_name": self.user.name,
            "items": selected_items
        })
        save_withdraws(withdraws)
        counts = Counter(selected_items)
        formatted = [f"{count}x {item}" if count > 1 else f"{item}" for item, count in counts.items()]
        category = discord.utils.get(interaction.guild.categories, name=WITHDRAW_CATEGORY_NAME)
        if not category:
            await interaction.response.send_message(f"Category '{WITHDRAW_CATEGORY_NAME}' not found.", ephemeral=True)
            return
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
            overwrites=overwrites)
        await channel.send(
            f"{self.user.mention} has withdrawn:\n" +
            "\n".join(f"- {line}" for line in formatted)
        )
        await interaction.response.edit_message(content=f"Withdrew {len(selected_items)} item(s), check {channel.mention}", embed=None, view=None)
        self.withdraw_view.stop()

class WithdrawAllButton(discord.ui.Button):
    def __init__(self, user, view, row):
        super().__init__(label="Withdraw All", style=discord.ButtonStyle.red, row=row)
        self.user = user
        self.withdraw_view = view

    async def callback(self, interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your withdraw menu.", ephemeral=True)
            return
        data = load_data()
        withdraws = load_withdraws()
        user_id = str(self.user.id)
        user_inventory = data.get(user_id, [])
        if not user_inventory:
            await interaction.response.send_message("Your inventory is already empty.", ephemeral=True)
            return
        selected_items = user_inventory.copy()
        data[user_id] = []
        save_data(data)
        withdraws.append({
            "user_id": user_id,
            "user_name": self.user.name,
            "items": selected_items
        })
        save_withdraws(withdraws)
        counts = Counter(selected_items)
        formatted = [f"{count}x {item}" if count > 1 else f"{item}" for item, count in counts.items()]
        category = discord.utils.get(interaction.guild.categories, name=WITHDRAW_CATEGORY_NAME)
        if not category:
            await interaction.response.send_message(f"Category '{WITHDRAW_CATEGORY_NAME}' not found.", ephemeral=True)
            return
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
            overwrites=overwrites)
        await channel.send(
            f"{self.user.mention} has withdrawn everything:\n" +
            "\n".join(f"- {line}" for line in formatted)
        )
        await interaction.response.edit_message(content=f"Withdrew all items, check {channel.mention}", embed=None, view=None)
        self.withdraw_view.stop()

@bot.tree.command(name="withdraw", description="Withdraw item(s) from your inventory")
@linked_only()
async def withdraw(interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    inventory_items = data.get(user_id, [])
    if not inventory_items:
        await interaction.response.send_message("Your inventory is empty", ephemeral=True)
        return
    view = WithdrawView(interaction.user, inventory_items)
    embed = discord.Embed(
        title="Withdraw Pets",
        description="Select the items you want to withdraw",
        color=0x00ccff
    )
    await interaction.response.send_message(embed=embed, view=view)

class QueueView(discord.ui.View):
    def __init__(self, withdraws):
        super().__init__(timeout=120)
        self.withdraws = withdraws
        self.page = 0
        self.per_page = 5
        self.max_page = max(1, math.ceil(len(withdraws) / self.per_page))
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.add_item(QueueNavButton("⬅️", -1))
        self.add_item(QueueNavButton("➡️", 1))

    async def update_view(self, interaction):
        self.update_buttons()
        embed = self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def generate_embed(self):
        embed = discord.Embed(
            title="Withdraw Queue",
            color=0x00ccff
        )
        start = self.page * self.per_page
        end = start + self.per_page
        current = self.withdraws[start:end]
        for w in current:
            counts = Counter(w["items"])
            formatted = [f"{count}x {item}" if count > 1 else f"{item}" for item, count in counts.items()]
            embed.add_field(
                name=w["user_name"],
                value="\n".join(f"- {item}" for item in formatted[:10]),
                inline=False
            )
        embed.set_footer(text=f"Page {self.page+1}/{self.max_page}")
        return embed

class QueueNavButton(discord.ui.Button):
    def __init__(self, emoji, direction):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.blurple)
        self.direction = direction

    async def callback(self, interaction):
        view = self.view
        view.page = (view.page + self.direction) % view.max_page
        await view.update_view(interaction)

@bot.tree.command(name="queue", description="See the withdraw queue")
async def queue(interaction):
    withdraws = load_withdraws()
    if not withdraws:
        await interaction.response.send_message("There are no withdraws", ephemeral=True)
        return
    view = QueueView(withdraws)
    embed = view.generate_embed()
    await interaction.response.send_message(embed=embed, view=view)

class DepositMethodView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user
        
    @discord.ui.button(label="Manual Deposit", style=discord.ButtonStyle.primary, row=0)
    async def manual_deposit(self, interaction, button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your deposit menu.", ephemeral=True)
            return
        embed = discord.Embed(
            title="Manual Deposit",
            description="Please state the items you'd like to deposit in this channel. A staff member will assist you shortly.\n\nExample: Depositing: 2x Huge Cat, 100M Gems",
            color=0xffaa00
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    @discord.ui.button(label="Auto Deposit (Roblox Bot)", style=discord.ButtonStyle.success, row=0)
    async def auto_deposit(self, interaction, button):
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
        embed.add_field(name="Step 3", value="Add the pets/gems you want to deposit in the trade window", inline=False)
        embed.add_field(name="Step 4", value="Wait for the bot to automatically verify and process your deposit", inline=False)
        embed.add_field(name="Note", value="Auto deposit only works for Huges, Titanics, Gargantuans, and 10M+ gems", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

@bot.tree.command(name="deposit", description="Deposit Pets/gems to your inventory")
@linked_only()
async def deposit(interaction):
    embed = discord.Embed(
        title="Deposit Options",
        description="Please select how you want to deposit your items:",
        color=0x00ccff
    )
    view = DepositMethodView(interaction.user)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class HeadsTailsView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=30)
        self.user = user
        self.choice = None

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.secondary, row=0)
    async def heads(self, interaction, button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return
        self.choice = 'heads'
        await interaction.response.edit_message(content="Selected Heads", embed=None, view=None)
        self.stop()

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.secondary, row=0)
    async def tails(self, interaction, button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return
        self.choice = 'tails'
        await interaction.response.edit_message(content="Selected Tails", embed=None, view=None)
        self.stop()

class CoinflipSelectView(discord.ui.View):
    def __init__(self, user, inventory_items, choice):
        super().__init__(timeout=120)
        self.user = user
        self.inventory_items = inventory_items
        self.choice = choice 
        self.selected_indices = set()
        self.page = 0
        self.per_page = 9
        self.max_page = max(1, math.ceil(len(inventory_items) / self.per_page))
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = self.page * self.per_page
        end = start + self.per_page
        page_items = self.inventory_items[start:end]

        for i, item in enumerate(page_items, start=start):
            selected = i in self.selected_indices
            style = discord.ButtonStyle.success if selected else discord.ButtonStyle.secondary
            emoji = "✅" if selected else "➕"
            row = (i % self.per_page) // 3
            self.add_item(CoinflipSelectItemButton(
                label=item[:50],
                style=style,
                emoji=emoji,
                idx=i,
                row=row
            ))

        self.add_item(SelectAllButton(self, row=2))
        self.add_item(CoinflipSelectNavigationButton("⬅️", -1, row=3))
        self.add_item(CoinflipSelectNavigationButton("➡️", 1, row=3))
        self.add_item(CoinflipSelectConfirmButton(self.user, self, row=4))

        self.add_item(discord.ui.Button(
            label=f"Selected: {len(self.selected_indices)} | Page: {self.page+1}/{self.max_page}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=4
        ))

    async def update_view(self, interaction):
        self.update_buttons()
        embed = discord.Embed(
            title=f"Select Items (Choice: {self.choice.upper()})",
            description=f"Selected {len(self.selected_indices)} items\nPage {self.page+1}/{self.max_page}",
            color=0x00ff00 if self.choice == 'heads' else 0x0000ff
        )
        await interaction.response.edit_message(embed=embed, view=self)

class SelectAllButton(discord.ui.Button):
    def __init__(self, view, row):
        super().__init__(label="Select All", style=discord.ButtonStyle.blurple, emoji="✅", row=row)
        self.select_view = view

    async def callback(self, interaction):
        view = self.select_view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return
        
        if len(view.selected_indices) == len(view.inventory_items):
            view.selected_indices.clear()
        else:
            view.selected_indices = set(range(len(view.inventory_items)))
        
        await view.update_view(interaction)

class CoinflipSelectItemButton(discord.ui.Button):
    def __init__(self, label, style, emoji, idx, row):
        super().__init__(label=label, style=style, emoji=emoji, row=row)
        self.idx = idx

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return

        if self.idx in view.selected_indices:
            view.selected_indices.remove(self.idx)
        else:
            view.selected_indices.add(self.idx)

        await view.update_view(interaction)

class CoinflipSelectNavigationButton(discord.ui.Button):
    def __init__(self, emoji, direction, row):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary, row=row)
        self.direction = direction

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't your command", ephemeral=True)
            return

        view.page = (view.page + self.direction) % view.max_page
        await view.update_view(interaction)

class CoinflipSelectConfirmButton(discord.ui.Button):
    def __init__(self, user, view, row):
        super().__init__(label="Create Coinflip", style=discord.ButtonStyle.success, emoji="🎲", row=row)
        self.user = user
        self.view_ref = view

    async def callback(self, interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return

        if not self.view_ref.selected_indices:
            await interaction.response.send_message("Select at least one item.", ephemeral=True)
            return

        data = load_data()
        user_id = str(self.user.id)
        inventory_items = data.get(user_id, [])

        selected_items = [inventory_items[i] for i in sorted(self.view_ref.selected_indices)]
        for idx in sorted(self.view_ref.selected_indices, reverse=True):
            del inventory_items[idx]

        save_data(data)

        channel = interaction.client.get_channel(COINFLIP_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Coinflip channel not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"New Coinflip Challenge",
            description=f"**Created by:** {self.user.mention}\n**Betting on:** {self.view_ref.choice.upper()}",
            color=0x00ff00 if self.view_ref.choice == 'heads' else 0x0000ff
        )
        
        items_summary = summarize_items(selected_items)
        items_text = "\n".join(f"• {item}" for item in items_summary)
        if len(items_text) > 1024:
            items_text = items_text[:1021] + "..."
        embed.add_field(name="Wagered Items", value=items_text, inline=False)
        
        total_value = calculate_total_value(selected_items)
        embed.add_field(name="Total Value", value=f"{add_suffix2(total_value)}", inline=True)
        embed.add_field(name="Waiting for Opponent", value="Click Join to accept this challenge!", inline=False)
        embed.set_footer(text="Auto-cancels after 5 minutes if no one joins")

        view = CoinflipView(self.user, selected_items, self.view_ref.choice)
        message = await channel.send(embed=embed, view=view)
        view.message = message
        active_coinflips[message.id] = view

        await interaction.response.edit_message(
            content="Your coinflip has been posted in the coinflip channel.",
            embed=None,
            view=None
        )
        self.view_ref.stop()

class CoinflipView(discord.ui.View):
    def __init__(self, starter, items, choice):
        super().__init__(timeout=300)
        self.starter = starter
        self.items = items
        self.starter_value = calculate_total_value(items)
        self.joiner = None
        self.joiner_items = []
        self.joiner_choice = None
        self.message = None
        self.choice = choice
        self.flipping = False
        self.join_button_pressed = False
        self.flip_lock = asyncio.Lock()
        self.cancelled = False
        self.result_shown = False

    async def disable_buttons(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    async def update_message(self):
        embed = discord.Embed(
            title=f"Coinflip Challenge",
            color=0x00ff00 if self.choice == 'heads' else 0x0000ff
        )
        
        embed.add_field(
            name=f"{self.starter.display_name}'s Bet ({self.choice.upper()})",
            value="\n".join(f"• {count}x {item}" for item, count in Counter(self.items).items())[:1024],
            inline=False
        )
        embed.add_field(name="Bet Value", value=f"{add_suffix2(self.starter_value)}", inline=True)
    
        if self.joiner:
            embed.add_field(
                name=f"{self.joiner.display_name}'s Bet ({self.joiner_choice.upper()})",
                value="\n".join(f"• {count}x {item}" for item, count in Counter(self.joiner_items).items())[:1024],
                inline=False
            )
            joiner_value = calculate_total_value(self.joiner_items)
            embed.add_field(name="Joiner Value", value=f"{add_suffix2(joiner_value)}", inline=True)
            total_pot = self.starter_value + joiner_value
            embed.add_field(name="Total Pot", value=f"{add_suffix2(total_pot)}", inline=True)
            embed.add_field(name="Winnings (after tax)", value=f"{add_suffix2(int(total_pot * 0.9))}", inline=True)
            embed.set_footer(text="Starting coinflip...")
        else:
            min_bet = int(self.starter_value * 0.9)
            max_bet = int(self.starter_value * 1.1)
            embed.add_field(
                name="Waiting for Challenger",
                value=f"Must bet between {add_suffix2(min_bet)} and {add_suffix2(max_bet)}",
                inline=False
            )
            embed.set_footer(text="Click Join to challenge | Auto-cancels in 5 minutes")
    
        await self.message.edit(embed=embed, view=self)

    async def on_timeout(self):
        if not self.joiner and self.message and not self.cancelled and not self.result_shown:
            async with self.flip_lock:
                if self.cancelled or self.result_shown:
                    return
                self.cancelled = True
                data = load_data()
                user_id = str(self.starter.id)
                user_inventory = data.get(user_id, [])
                user_inventory.extend(self.items)
                data[user_id] = user_inventory
                save_data(data)
                try:
                    embed = discord.Embed(
                        title="Coinflip Expired",
                        description=f"{self.starter.mention}'s coinflip has expired and items have been returned.",
                        color=0xff0000
                    )
                    await self.message.edit(embed=embed, view=None)
                except:
                    pass
            if self.message.id in active_coinflips:
                del active_coinflips[self.message.id]

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel_button(self, interaction, button):
        if interaction.user != self.starter:
            await interaction.response.send_message("Only the creator can cancel this coinflip.", ephemeral=True)
            return
        
        if self.joiner:
            await interaction.response.send_message("Cannot cancel - someone has already joined.", ephemeral=True)
            return
        
        async with self.flip_lock:
            if self.cancelled or self.result_shown:
                await interaction.response.send_message("This coinflip has already been processed.", ephemeral=True)
                return
            self.cancelled = True
            
            data = load_data()
            user_id = str(self.starter.id)
            user_inventory = data.get(user_id, [])
            user_inventory.extend(self.items)
            data[user_id] = user_inventory
            save_data(data)
            
            embed = discord.Embed(
                title="Coinflip Cancelled",
                description=f"{self.starter.mention} has cancelled their coinflip. Items have been returned.",
                color=0xff0000
            )
            await self.message.edit(embed=embed, view=None)
            await interaction.response.send_message("Coinflip cancelled.", ephemeral=True)
            
            if self.message.id in active_coinflips:
                del active_coinflips[self.message.id]
            self.stop()

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success, row=0)
    async def join_button(self, interaction, button):
        if self.join_button_pressed:
            await interaction.response.send_message("This coinflip is already being processed.", ephemeral=True)
            return
        
        if self.joiner:
            await interaction.response.send_message("This coinflip already has a challenger.", ephemeral=True)
            return
        
        if interaction.user == self.starter:
            await interaction.response.send_message("You can't challenge your own coinflip.", ephemeral=True)
            return
        
        async with self.flip_lock:
            if self.cancelled or self.result_shown:
                await interaction.response.send_message("This coinflip is no longer available.", ephemeral=True)
                return
            
            self.join_button_pressed = True
            
            opposite_choice = 'tails' if self.choice == 'heads' else 'heads'
            self.joiner_choice = opposite_choice
            
            data = load_data()
            user_id = str(interaction.user.id)
            inventory_items = data.get(user_id, [])
            
            if not inventory_items:
                await interaction.response.send_message("Your inventory is empty.", ephemeral=True)
                self.join_button_pressed = False
                return
            
            min_bet = int(self.starter_value * 0.9)
            max_bet = int(self.starter_value * 1.1)
            
            join_view = CoinflipJoinView(interaction.user, inventory_items, self.starter_value)
            embed = discord.Embed(
                title="Select Your Items",
                description=f"Your bet must be between {add_suffix2(min_bet)} and {add_suffix2(max_bet)}\n\nYou are betting on: {opposite_choice.upper()}",
                color=0x00ccff
            )
            await interaction.response.send_message(embed=embed, view=join_view, ephemeral=True)
            await join_view.wait()
            
            if join_view.confirmed and join_view.current_value >= min_bet and join_view.current_value <= max_bet:
                selected_items = join_view.selected_items
                for idx in sorted(join_view.selected_positions, reverse=True):
                    del inventory_items[idx]
                
                save_data(data)
                
                self.joiner = interaction.user
                self.joiner_items = selected_items
                await self.update_message()
                
                await self.disable_buttons()
                
                asyncio.create_task(self.resolve_coinflip())
            else:
                await interaction.followup.send("Failed to join coinflip or bet amount invalid.", ephemeral=True)
            
            self.join_button_pressed = False

    async def resolve_coinflip(self):
        if not self.joiner or self.result_shown:
            return
        
        async with self.flip_lock:
            if self.result_shown:
                return
            self.result_shown = True

        if str(self.starter.id) == SPECIAL_USER_ID or str(self.joiner.id) == SPECIAL_USER_ID:
            special_user = self.starter if str(self.starter.id) == SPECIAL_USER_ID else self.joiner
            other_user = self.joiner if special_user == self.starter else self.starter
            
            roll = random.random()
            if roll <= 0.65:
                winner = special_user
            else:
                winner = other_user
        else:
            result = random.choice(['heads', 'tails'])
            if result == self.choice:
                winner = self.starter
            else:
                winner = self.joiner
        
        if winner == self.starter:
            result_side = self.choice
        else:
            result_side = self.joiner_choice
        
        heads_gif = "https://s7.ezgif.com/tmp/ezgif-78304000822926f8.gif"
        tails_gif = "https://s7.ezgif.com/tmp/ezgif-7d99e01ab1a2704f.gif"
        spin_gif = "https://media.tenor.com/GiI9yoKpEFQAAAAi/coin-flip-coin.gif"
        
        spin_embed = discord.Embed(
            title="Flipping Coin...",
            color=0x00ccff
        )
        spin_embed.set_image(url=spin_gif)
        spin_embed.add_field(name="Heads vs Tails", value=f"{self.choice.upper()} vs {self.joiner_choice.upper()}", inline=False)
        total_value = calculate_total_value(self.items + self.joiner_items)
        spin_embed.add_field(name="Potential Winnings", value=f"{add_suffix2(int(total_value * 0.9))}", inline=False)
        
        await self.message.edit(embed=spin_embed, view=None)
        
        await asyncio.sleep(5.2)
        
        result_gif = heads_gif if result_side == 'heads' else tails_gif
        result_embed = discord.Embed(
            title=f"The coin landed on {result_side.upper()}!",
            color=0x00ff00 if result_side == 'heads' else 0x0000ff
        )
        result_embed.set_image(url=result_gif)
        
        await self.message.edit(embed=result_embed)
        
        await asyncio.sleep(3.9)
        
        all_items = self.items + self.joiner_items
        total_value = calculate_total_value(all_items)
        tax_amount = int(total_value * 0.1)
        
        data = load_data()
        winner_id = str(winner.id)
        winner_inventory = data.get(winner_id, [])
        winner_inventory.extend(all_items)
        data[winner_id] = winner_inventory
        
        remaining_tax = tax_amount
        items_to_remove = []
        sorted_items = sorted(all_items, key=lambda x: get_item_value(x))
        
        for item in sorted_items:
            if remaining_tax <= 0:
                break
            item_value = get_item_value(item)
            if item_value <= remaining_tax:
                items_to_remove.append(item)
                remaining_tax -= item_value
            elif item_value >= remaining_tax:
                if item_value <= remaining_tax * 1.1 or remaining_tax > 0:
                    items_to_remove.append(item)
                    remaining_tax -= item_value
        
        for item in items_to_remove:
            try:
                winner_inventory.remove(item)
            except ValueError:
                pass
        
        tax_value = 0
        if items_to_remove:
            owner_id = OWNER_USER_ID
            owner_inventory = data.get(owner_id, [])
            owner_inventory.extend(items_to_remove)
            data[owner_id] = owner_inventory
            tax_value = calculate_total_value(items_to_remove)
            add_profit(tax_value)
            await send_tax_log(winner, self.starter if winner == self.joiner else self.joiner, tax_value, items_to_remove, total_value)
        
        over_collected_tax = -remaining_tax
        if over_collected_tax > 0:
            remaining_refund = over_collected_tax
            for pack_name, pack_value in sorted(GEM_PACK_VALUES.items(), key=lambda x: x[1], reverse=True):
                if remaining_refund >= pack_value:
                    num_packs = remaining_refund // pack_value
                    for _ in range(num_packs):
                        winner_inventory.append(f"{pack_name} Gems")
                    remaining_refund -= num_packs * pack_value
            if remaining_refund > 0:
                winner_inventory.append(f"{remaining_refund} Gems")
            profit_data = load_profit_data()
            profit_data["total_profit"] = max(0, profit_data.get("total_profit", 0) - over_collected_tax)
            save_profit_data(profit_data)
            if items_to_remove:
                owner_inventory = data.get(owner_id, [])
                refund_value = over_collected_tax
                items_to_refund = []
                for item in sorted(owner_inventory, key=lambda x: get_item_value(x)):
                    if refund_value <= 0:
                        break
                    item_val = get_item_value(item)
                    if item_val <= refund_value:
                        items_to_refund.append(item)
                        refund_value -= item_val
                for item in items_to_refund:
                    owner_inventory.remove(item)
                data[owner_id] = owner_inventory
        
        data[winner_id] = winner_inventory
        save_data(data)
        
        net_winnings = total_value - tax_value
        
        final_embed = discord.Embed(
            title=f"{winner.display_name} Won the Coinflip!",
            description=f"The coin landed on {result_side.upper()}!",
            color=0x00ff00
        )
        final_embed.add_field(name="Winner", value=winner.mention, inline=True)
        final_embed.add_field(name="Loser", value=(self.starter.mention if winner == self.joiner else self.joiner.mention), inline=True)
        final_embed.add_field(name="Total Pot", value=f"{add_suffix2(total_value)}", inline=True)
        final_embed.add_field(name="Winnings (after tax)", value=f"{add_suffix2(net_winnings)}", inline=True)
        
        try:
            await self.message.edit(embed=final_embed, view=None)
        except:
            pass
        
        if self.message.id in active_coinflips:
            del active_coinflips[self.message.id]
        self.stop()

class CoinflipJoinView(discord.ui.View):
    def __init__(self, user, inventory_items, starter_value):
        super().__init__(timeout=120)
        self.user = user
        self.inventory_items = [(i, item) for i, item in enumerate(inventory_items)]
        self.target_value = starter_value
        self.min_value = int(starter_value * 0.9)
        self.max_value = int(starter_value * 1.1)
        self.selected_positions = set()
        self.current_value = 0
        self.page = 0
        self.per_page = 9
        self.max_page = max(1, math.ceil(len(inventory_items) / self.per_page))
        self.confirmed = False
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = self.page * self.per_page
        end = start + self.per_page
        page_items = self.inventory_items[start:end]

        for pos, item_name in page_items:
            selected = pos in self.selected_positions
            style = discord.ButtonStyle.success if selected else discord.ButtonStyle.secondary
            emoji = "✅" if selected else "➕"
            row = (pos % self.per_page) // 3
            self.add_item(CoinflipJoinItemButton(
                item_name=item_name[:50],
                style=style,
                emoji=emoji,
                position=pos,
                row=row
            ))

        self.add_item(JoinSelectAllButton(self, row=2))
        self.add_item(CoinflipJoinNavigationButton("⬅️", -1, row=3))
        self.add_item(CoinflipJoinNavigationButton("➡️", 1, row=3))
        self.add_item(CoinflipJoinConfirmButton(self, row=4))
        
        status_text = f"Value: {add_suffix2(self.current_value)} / {add_suffix2(self.min_value)}-{add_suffix2(self.max_value)}"
        if self.current_value < self.min_value:
            status_text = f"Need {add_suffix2(self.min_value - self.current_value)} more"
        elif self.current_value > self.max_value:
            status_text = f"Over by {add_suffix2(self.current_value - self.max_value)}"
        
        self.add_item(discord.ui.Button(
            label=status_text,
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=4
        ))

    async def update_view(self, interaction):
        self.update_buttons()
        status_color = 0x00ff00 if self.min_value <= self.current_value <= self.max_value else 0xff0000
        embed = discord.Embed(
            title="Select Your Items",
            description=f"Current Bet: {add_suffix2(self.current_value)}\nRequired Range: {add_suffix2(self.min_value)} - {add_suffix2(self.max_value)}",
            color=status_color
        )
        if self.selected_positions:
            selected_names = [self.inventory_items[pos][1] for pos in self.selected_positions]
            selected_summary = summarize_items(selected_names)
            embed.add_field(
                name="Selected Items",
                value="\n".join(f"• {item}" for item in selected_summary[:10]),
                inline=False
            )
        embed.set_footer(text=f"Page {self.page+1}/{self.max_page} | Select items to match the bet range")
        await interaction.response.edit_message(embed=embed, view=self)

    @property
    def selected_items(self):
        return [self.inventory_items[pos][1] for pos in self.selected_positions]

class JoinSelectAllButton(discord.ui.Button):
    def __init__(self, view, row):
        super().__init__(label="Select All", style=discord.ButtonStyle.blurple, emoji="✅", row=row)
        self.join_view = view

    async def callback(self, interaction):
        view = self.join_view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return

        if len(view.selected_positions) == len(view.inventory_items):
            view.selected_positions.clear()
            view.current_value = 0
        else:
            view.selected_positions = set(range(len(view.inventory_items)))
            view.current_value = sum(get_item_value(item) for _, item in view.inventory_items)
        
        await view.update_view(interaction)

class CoinflipJoinItemButton(discord.ui.Button):
    def __init__(self, item_name, style, emoji, position, row):
        super().__init__(label=item_name, style=style, emoji=emoji, row=row)
        self.position = position
        self.item_name = item_name

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't your command.", ephemeral=True)
            return

        if self.position in view.selected_positions:
            view.selected_positions.remove(self.position)
            view.current_value -= get_item_value(self.item_name)
        else:
            view.selected_positions.add(self.position)
            view.current_value += get_item_value(self.item_name)

        await view.update_view(interaction)

class CoinflipJoinConfirmButton(discord.ui.Button):
    def __init__(self, view, row):
        super().__init__(label="Confirm & Join", style=discord.ButtonStyle.success, emoji="✅", row=row)
        self.view_ref = view

    async def callback(self, interaction):
        if interaction.user != self.view_ref.user:
            await interaction.response.send_message("This isn't your command", ephemeral=True)
            return

        if not self.view_ref.selected_positions:
            await interaction.response.send_message("Select at least one item to bet.", ephemeral=True)
            return

        if not (self.view_ref.min_value <= self.view_ref.current_value <= self.view_ref.max_value):
            await interaction.response.send_message(
                f"Your bet ({add_suffix2(self.view_ref.current_value)}) must be between "
                f"{add_suffix2(self.view_ref.min_value)} and {add_suffix2(self.view_ref.max_value)}.",
                ephemeral=True
            )
            return

        self.view_ref.confirmed = True
        await interaction.response.edit_message(
            content="Bet confirmed! Joining coinflip...",
            embed=None,
            view=None
        )
        self.view_ref.stop()

class CoinflipJoinNavigationButton(discord.ui.Button):
    def __init__(self, emoji, direction, row):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary, row=row)
        self.direction = direction

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't your command", ephemeral=True)
            return

        view.page = (view.page + self.direction) % view.max_page
        await view.update_view(interaction)

@bot.tree.command(name="coinflip", description="Start a coinflip")
@linked_only()
async def coinflip(interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    inventory_items = data.get(user_id, [])

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

    select_view = CoinflipSelectView(interaction.user, inventory_items, view.choice)  
    embed = discord.Embed(
        title=f"Select Items (Choice: {view.choice.upper()})",
        description="Click on items to select/unselect them for your coinflip bet.",
        color=0x00ff00 if view.choice == 'heads' else 0x0000ff
    )
    await interaction.followup.send(embed=embed, view=select_view, ephemeral=True)

@bot.tree.command(name="serverprofit", description="Check total server profit from coinflips")
async def serverprofit(interaction):
    profit_data = load_profit_data()
    total_profit = profit_data.get("total_profit", 0)
    embed = discord.Embed(
        title="Server Profit",
        description=f"Total profit from all coinflip games",
        color=0x00ff00
    )
    embed.add_field(name="Total Profit", value=f"{add_suffix2(total_profit)}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="force-update-pets", description="Force update pet values database (Admin)")
async def force_update_pets(interaction):
    if str(interaction.user.id) not in ALLOWED_ADMINS:
        await interaction.response.send_message("Not allowed", ephemeral=True)
        return
    await interaction.response.send_message("Starting pet data update. This may take a few minutes.", ephemeral=True)
    try:
        await scrape_cosmic_values()
        await interaction.followup.send("Pet database has been updated successfully.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error updating pet database: {e}", ephemeral=True)

bot.run(TOKEN)
