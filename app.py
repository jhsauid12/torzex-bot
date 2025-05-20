import os
import discord
import json
import random
import asyncio
import aiohttp
from discord.ext import commands
from discord import app_commands
from flask import Flask, request
import threading
import hmac
import hashlib
from datetime import datetime

# Инициализация Flask
app = Flask(__name__)

# Настройка Discord бота
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Конфигурация
CONFIG_FILE = "data/config.json"

def load_data():
    try:
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "reaction_roles": {},
                    "auto_roles": [],
                    "nsfw_channels": [],
                    "notification_channels": {},
                    "git_webhooks": {}
                }, f)
        
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config: {e}")
        return {
            "reaction_roles": {},
            "auto_roles": [],
            "nsfw_channels": [],
            "notification_channels": {},
            "git_webhooks": {}
        }

def save_data(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

bot.data = load_data()

# События
@bot.event
async def on_ready():
    print(f"Bot {bot.user} is ready!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="/help"))
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Help Command
@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 Bot Commands", color=0x00ff00)
    
    embed.add_field(
        name="🎭 Reaction Roles",
        value="`/reaction_role` - Set up role reactions",
        inline=False
    )
    
    embed.add_field(
        name="🌤 Weather",
        value="`/weather [city]` - Get current weather",
        inline=False
    )
    
    embed.add_field(
        name="😂 Fun",
        value="`/meme` - Random meme\n"
              "`/coinflip` - Flip a coin\n"
              "`/cat` - Random cat\n"
              "`/dog` - Random dog",
        inline=False
    )
    
    embed.add_field(
        name="🔞 NSFW (18+)",
        value="`/nsfw_setup` - Enable NSFW in this channel\n"
              "`/nsfw [category]` - NSFW content",
        inline=False
    )
    
    embed.add_field(
        name="👥 Auto Roles",
        value="`/autorole_add` - Add auto role\n"
              "`/autorole_remove` - Remove auto role",
        inline=False
    )
    
    embed.add_field(
        name="🔔 Notifications",
        value="`/git_setup` - Setup Git notifications\n"
              "`/git_webhook` - Create repo webhook",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

# Weather Command
@bot.tree.command(name="weather", description="Get weather for a city")
@app_commands.describe(city="City name")
async def weather(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en"
            ) as resp:
                geo_data = await resp.json()
                
            if not geo_data.get("results"):
                return await interaction.followup.send(f"❌ City not found: {city}")
            
            location = geo_data["results"][0]
            lat, lon = location["latitude"], location["longitude"]
            
            async with session.get(
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&current_weather=true&hourly=temperature_2m&daily=weathercode,temperature_2m_max,temperature_2m_min"
                f"&timezone=auto&windspeed_unit=ms"
            ) as resp:
                weather_data = await resp.json()
        
        current = weather_data["current_weather"]
        daily = weather_data["daily"]
        
        weather_codes = {
            0: "Clear ☀️", 1: "Mainly clear 🌤", 2: "Partly cloudy ⛅",
            3: "Overcast ☁️", 45: "Fog 🌫", 48: "Depositing rime fog 🌫",
            51: "Light drizzle 🌧", 53: "Moderate drizzle 🌧", 55: "Dense drizzle 🌧",
            61: "Slight rain 🌧", 63: "Moderate rain 🌧", 65: "Heavy rain 🌧",
            71: "Slight snow ❄️", 73: "Moderate snow ❄️", 75: "Heavy snow ❄️",
            80: "Light showers 🌧", 81: "Moderate showers 🌧", 82: "Violent showers 🌧",
            85: "Slight snow showers ❄️", 86: "Heavy snow showers ❄️", 95: "Thunderstorm ⚡"
        }
        
        embed = discord.Embed(
            title=f"🌤 Weather in {location['name']}, {location.get('admin1', '')}",
            color=0x00ffff
        )
        embed.add_field(name="🌡️ Temperature", value=f"{current['temperature']}°C", inline=True)
        embed.add_field(name="💨 Wind", value=f"{current['windspeed']} m/s", inline=True)
        embed.add_field(name="☁️ Condition", value=weather_codes.get(current['weathercode'], "Unknown"), inline=True)
        embed.add_field(name="⬆️ High", value=f"{daily['temperature_2m_max'][0]}°C", inline=True)
        embed.add_field(name="⬇️ Low", value=f"{daily['temperature_2m_min'][0]}°C", inline=True)
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# Reaction Roles
class RoleModal(discord.ui.Modal, title="Reaction Role Setup"):
    message_id = discord.ui.TextInput(label="Message ID")
    emoji = discord.ui.TextInput(label="Emoji")
    role = discord.ui.TextInput(label="Role ID")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            message = await interaction.channel.fetch_message(int(self.message_id.value))
            await message.add_reaction(self.emoji.value)
            bot.data["reaction_roles"][f"{self.message_id.value}-{self.emoji.value}"] = int(self.role.value)
            save_data(bot.data)
            
            await interaction.response.send_message(
                f"✅ Reaction role setup complete!\n"
                f"Message: {self.message_id.value}\n"
                f"Emoji: {self.emoji.value}\n"
                f"Role: <@&{self.role.value}>",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="reaction_role", description="Setup reaction roles")
@app_commands.default_permissions(administrator=True)
async def reaction_role(interaction: discord.Interaction):
    await interaction.response.send_modal(RoleModal())

# Reaction Handling
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    
    key = f"{payload.message_id}-{payload.emoji}"
    if key in bot.data["reaction_roles"]:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(bot.data["reaction_roles"][key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    key = f"{payload.message_id}-{payload.emoji}"
    if key in bot.data["reaction_roles"]:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(bot.data["reaction_roles"][key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.remove_roles(role)

# Fun Commands
@bot.tree.command(name="meme", description="Get a random meme")
@app_commands.describe(category="Meme category")
@app_commands.choices(category=[
    app_commands.Choice(name="Random", value="random"),
    app_commands.Choice(name="Funny", value="funny"),
    app_commands.Choice(name="Dank", value="dank"),
    app_commands.Choice(name="Wholesome", value="wholesome")
])
async def meme(interaction: discord.Interaction, category: app_commands.Choice[str]):
    await interaction.response.defer()
    try:
        url = f"https://meme-api.com/gimme/{category.value}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        
        embed = discord.Embed(title=data["title"], color=0xff9900)
        embed.set_image(url=data["url"])
        embed.set_footer(text=f"👍 {data['ups']} | r/{data['subreddit']}")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 {random.choice(['Heads', 'Tails'])}!")

@bot.tree.command(name="cat", description="Get a random cat picture")
async def cat(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
                data = await resp.json()
        await interaction.followup.send(data[0]["url"])
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="dog", description="Get a random dog picture")
async def dog(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                data = await resp.json()
        await interaction.followup.send(data["message"])
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# Auto Roles
@bot.tree.command(name="autorole_add", description="Add an auto role")
@app_commands.describe(role="Role to add")
@app_commands.default_permissions(administrator=True)
async def add_autorole(interaction: discord.Interaction, role: discord.Role):
    if role.id not in bot.data["auto_roles"]:
        bot.data["auto_roles"].append(role.id)
        save_data(bot.data)
        await interaction.response.send_message(f"✅ Auto role added: {role.mention}")
    else:
        await interaction.response.send_message(f"ℹ Role is already an auto role: {role.mention}")

@bot.tree.command(name="autorole_remove", description="Remove an auto role")
@app_commands.describe(role="Role to remove")
@app_commands.default_permissions(administrator=True)
async def remove_autorole(interaction: discord.Interaction, role: discord.Role):
    if role.id in bot.data["auto_roles"]:
        bot.data["auto_roles"].remove(role.id)
        save_data(bot.data)
        await interaction.response.send_message(f"✅ Auto role removed: {role.mention}")
    else:
        await interaction.response.send_message(f"ℹ Role is not an auto role: {role.mention}")

@bot.event
async def on_member_join(member):
    for role_id in bot.data["auto_roles"]:
        role = member.guild.get_role(role_id)
        if role:
            await member.add_roles(role)

# NSFW Commands
@bot.tree.command(name="nsfw_setup", description="Setup current channel as NSFW")
@app_commands.default_permissions(administrator=True)
async def setup_nsfw(interaction: discord.Interaction):
    if interaction.channel.id not in bot.data["nsfw_channels"]:
        bot.data["nsfw_channels"].append(interaction.channel.id)
        save_data(bot.data)
        await interaction.response.send_message("✅ Channel set as NSFW")
    else:
        await interaction.response.send_message("ℹ This channel is already NSFW")

@bot.tree.command(name="nsfw", description="NSFW content (18+)")
@app_commands.describe(category="Content category")
@app_commands.choices(category=[
    app_commands.Choice(name="Neko", value="neko"),
    app_commands.Choice(name="Hentai", value="hentai"),
    app_commands.Choice(name="Boobs", value="boobs")
])
async def nsfw_content(interaction: discord.Interaction, category: app_commands.Choice[str]):
    if interaction.channel.id not in bot.data["nsfw_channels"]:
        return await interaction.response.send_message("❌ This is not an NSFW channel!", ephemeral=True)
    
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.waifu.pics/nsfw/{category.value}") as resp:
                data = await resp.json()
        
        embed = discord.Embed(color=0xff69b4)
        embed.set_image(url=data["url"])
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# Git Notifications
@bot.tree.command(name="git_setup", description="Setup Git notifications channel")
@app_commands.describe(channel="Notification channel")
@app_commands.default_permissions(administrator=True)
async def setup_git(interaction: discord.Interaction, channel: discord.TextChannel):
    bot.data["notification_channels"]["git"] = channel.id
    save_data(bot.data)
    await interaction.response.send_message(f"✅ Git notifications channel set to: {channel.mention}")

@bot.tree.command(name="git_webhook", description="Create a webhook for repository")
@app_commands.describe(repo="Repository name (owner/repo)")
@app_commands.default_permissions(administrator=True)
async def create_webhook(interaction: discord.Interaction, repo: str):
    if "git" not in bot.data["notification_channels"]:
        return await interaction.response.send_message(
            "❌ First setup a channel with /git_setup",
            ephemeral=True
        )
    
    secret = os.urandom(16).hex()
    bot.data["git_webhooks"][repo] = {
        "secret": secret,
        "channel_id": bot.data["notification_channels"]["git"]
    }
    save_data(bot.data)
    
    embed = discord.Embed(title="🔔 Git Webhook", color=0x7289da)
    embed.add_field(name="Repository", value=repo, inline=False)
    embed.add_field(name="Secret", value=f"`{secret}`", inline=False)
    embed.add_field(
        name="Webhook URL", 
        value=f"`{os.getenv('WEBHOOK_URL', 'https://your-render-url.onrender.com')}/webhook/git`", 
        inline=False
    )
    embed.add_field(
        name="Instructions", 
        value="1. Go to repository Settings\n"
              "2. Open Webhooks section\n"
              "3. Add new webhook with provided URL and Secret\n"
              "4. Select events: Push, Pull Request, Releases",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Git Webhook Handler
@app.route('/webhook/git', methods=['POST'])
def handle_git_webhook():
    try:
        signature = request.headers.get('X-Hub-Signature-256', '')
        if not signature:
            return "No signature", 400
        
        repo = request.json['repository']['full_name']
        if repo not in bot.data["git_webhooks"]:
            return "Repository not configured", 404
        
        secret = bot.data["git_webhooks"][repo]["secret"]
        channel_id = bot.data["git_webhooks"][repo]["channel_id"]
        
        # Verify signature
        body = request.data
        hash_object = hmac.new(secret.encode(), body, hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return "Invalid signature", 403
        
        event = request.headers.get('X-GitHub-Event', '')
        data = request.json
        
        # Format message
        message = None
        if event == "push":
            commits = data['commits']
            if commits:
                message = (
                    f"🔨 **New push to {repo}**\n"
                    f"Author: {data['pusher']['name']}\n"
                    f"Branch: {data['ref'].split('/')[-1]}\n"
                    f"Commits: {len(commits)}\n"
                    f"Last: {commits[-1]['message']}\n"
                    f"[View changes]({data['compare']})"
                )
        
        elif event == "pull_request":
            pr = data['pull_request']
            action = data['action']
            message = (
                f"🔄 **PR {action} in {repo}**\n"
                f"Title: {pr['title']}\n"
                f"Author: {pr['user']['login']}\n"
                f"Branches: {pr['head']['ref']} → {pr['base']['ref']}\n"
                f"[View PR]({pr['html_url']})"
            )
        
        elif event == "release":
            release = data['release']
            message = (
                f"🎉 **New release {release['tag_name']} in {repo}**\n"
                f"Name: {release['name']}\n"
                f"Author: {release['author']['login']}\n"
                f"[Download]({release['html_url']})"
            )
        
        if message:
            async def send_notification():
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(message)
            
            asyncio.run_coroutine_threadsafe(send_notification(), bot.loop)
        
        return "OK", 200
    except Exception as e:
        print(f"Git webhook error: {e}")
        return "Error", 500

# Flask Routes
@app.route('/')
def home():
    return "Bot is running!"

# Startup
def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("data", exist_ok=True)
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start the bot
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Discord token not found in environment variables!")
    else:
        bot.run(TOKEN)