Here's a `README.md` file for your Discord bot and Roblox deposit system:

```markdown
# Deposit Bot System

A complete deposit system with Discord bot and Roblox trade bot integration.

## Requirements

- Python 3.8 or higher
- Discord Bot Token
- Roblox account for the trade bot
- Delta Executor or similar Roblox executor

## Discord Bot Setup

### Installation

1. Install Python dependencies:
```bash
pip install discord.py aiohttp flask cloudscraper beautifulsoup4 requests
```

2. Create a Discord application at https://discord.com/developers/applications
3. Go to the Bot section and copy your bot token
4. Enable these Privileged Gateway Intents:
   - Message Content Intent
   - Server Members Intent

### Configuration

Open the bot file and change these values:

| Variable | What to put |
|----------|-------------|
| `ALLOWED_ADMINS` | Your Discord user ID |
| `COINFLIP_CHANNEL_ID` | Channel ID where coinflips appear |
| `TAX_WEBHOOK_URL` | Webhook URL for tax logs |
| `DEPOSIT_WEBHOOK_URL` | Webhook URL for deposit logs |
| `OWNER_USER_ID` | Your Discord user ID for tax collection |

### Finding IDs

- **User ID**: Enable Developer Mode in Discord settings, right-click your name, copy ID
- **Channel ID**: Right-click a channel, copy ID
- **Webhook URL**: Create webhook in channel settings, copy URL

### Running the Bot

```bash
python bot.py
```

The bot will:
- Start an API server on port 35585
- Scrape pet values every 24 hours
- Sync all slash commands

## Roblox Trade Bot Setup

### Files Needed

The Roblox script needs to be loaded through an executor like Delta Executor.

### Configuration

In the Roblox script, change the website URL:

```lua
local website = "http://us0.techstar.ltd:35585"
```

Change this to your server's IP if running locally:
```lua
local website = "http://localhost:35585"
```

### What the Bot Accepts

- Huges
- Titanics  
- Gargantuans
- 10,000,000+ gems

### Loading the Script

1. Join Pet Simulator 99
2. Open Delta Executor
3. Paste the script
4. Click Execute

The bot will automatically:
- Accept trade requests
- Detect valid pets and gems
- Send ready and confirm
- Forward deposits to your Discord bot API

## How It Works

1. User links Roblox account with `/link` in Discord
2. User sends trade request to the Roblox bot
3. Roblox bot detects items in trade
4. If valid, bot readies and confirms
5. After trade completes, bot sends deposit to API
6. Discord bot adds items to user's inventory
7. Deposit log sent to webhook

## Commands

### User Commands
| Command | Description |
|---------|-------------|
| `/link` | Link Roblox account |
| `/unlink` | Unlink Roblox account |
| `/inventory` | View your items |
| `/deposit` | Start a deposit |
| `/withdraw` | Request withdrawal |
| `/coinflip` | Start a coinflip game |
| `/tip` | Send items to another user |
| `/value` | Check pet value |
| `/leaderboard` | View top players |
| `/stats` | Your statistics |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/add-pet` | Add pet to user |
| `/add-gems` | Add gems to user |
| `/force-update-pets` | Update pet values |
| `/force-link` | Force link account |

## Troubleshooting

### Discord Bot Won't Start
- Check your bot token is correct
- Make sure all dependencies are installed
- Verify the token hasn't been reset

### Deposits Not Received
- Check Python bot is running
- Verify Roblox script has correct website URL
- Check console for error messages
- Make sure user used `/link` before depositing

### Trade Bot Not Responding
- Rejoin the game and reload script
- Check executor is injected properly
- Make sure you're in Pet Simulator 99

### Duplicate Deposits
- The bot has rate limiting (10 seconds between deposits from same user)
- This prevents accidental duplicate processing

## File Structure

```
├── bot.py                 # Discord bot
├── data.json              # User inventories
├── user_links.json        # Roblox to Discord links
├── profit_data.json       # Coinflip profits
├── withdraws.json         # Pending withdrawals
├── pets.json              # Pet values from Cosmic Values
└── pet_icons.json         # Cached pet images
```

## API Endpoints

The bot runs a Flask API on port 35585:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/deposit` | POST | Receive deposits from Roblox |
| `/api/link/check` | GET | Check if Roblox ID is linked |
| `/pet/<asset_id>` | GET | Get pet info by asset ID |

## Notes

- Pet values update automatically every 24 hours
- Coinflip takes 10% tax from total pot
- Users must link accounts before depositing
- Minimum gem deposit is 10,000,000
- Only Huges, Titanics, and Gargantuans are accepted
```

This README gives users everything they need to set up both the Discord bot and the Roblox trade bot without making it look like AI wrote it.
