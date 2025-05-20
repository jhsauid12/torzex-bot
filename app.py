import os
import json
import random
import asyncio
import threading
import hmac
import hashlib
import requests

from flask import Flask, request
import discord
from discord.ext import commands
from discord import app_commands, Interaction, Member, Object

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Файл хранения данных
CONFIG_PATH = "data/config.json"
if not os.path.exists("data"):
    os.makedirs("data")

def load_data():
    if not os.path.exists(CONFIG_PATH):
        return {
            "reaction_roles": {}, 
            "auto_role": None,
            "log_channel": None,
            "nsfw_allowed": [],
            "git_webhooks": {}
        }
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_data(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)

bot.data = load_data()

# Auto-role при входе
@bot.event
async def on_member_join(member):
    role_id = bot.data.get("auto_role")
    if role_id:
        role = member.guild.get_role(role_id)
        if role:
            await member.add_roles(role)

# Логирование сообщений
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    log_id = bot.data.get("log_channel")
    if log_id:
        log_channel = message.guild.get_channel(log_id)
        if log_channel:
            await log_channel.send(f"📝 `{message.author}`: {message.content}")
    await bot.process_commands(message)

# Установка авто-роли
@tree.command(name="setautorole", description="Задать авто-роль")
@app_commands.checks.has_permissions(administrator=True)
async def set_autorole(interaction: Interaction, role: discord.Role):
    bot.data["auto_role"] = role.id
    save_data(bot.data)
    await interaction.response.send_message(f"✅ Авто-роль установлена: {role.name}")

# Установка канала логов
@tree.command(name="setlogchannel", description="Задать канал логов")
@app_commands.checks.has_permissions(administrator=True)
async def set_logchannel(interaction: Interaction, channel: discord.TextChannel):
    bot.data["log_channel"] = channel.id
    save_data(bot.data)
    await interaction.response.send_message(f"✅ Канал логов установлен: {channel.name}")

# Модальная форма для реакции-ролей
class ReactionRoleModal(discord.ui.Modal, title="Роль по реакции"):
    message_id = discord.ui.TextInput(label="ID сообщения")
    emoji = discord.ui.TextInput(label="Эмодзи (например, 😀 или <:name:id>)")
    role_id = discord.ui.TextInput(label="ID роли")

    async def on_submit(self, interaction: Interaction):
        try:
            msg_id = int(self.message_id.value)
            role_id = int(self.role_id.value)
            emoji = self.emoji.value
        except ValueError:
            await interaction.response.send_message("❌ Неверные данные.", ephemeral=True)
            return

        bot.data["reaction_roles"].setdefault(str(msg_id), {})[emoji] = role_id
        save_data(bot.data)

        channel = interaction.channel
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.add_reaction(emoji)
            await interaction.response.send_message("✅ Роль по реакции установлена.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Не удалось добавить реакцию.", ephemeral=True)

@tree.command(name="reactionrole", description="Создать роль по реакции")
@app_commands.checks.has_permissions(administrator=True)
async def reactionrole(interaction: Interaction):
    await interaction.response.send_modal(ReactionRoleModal())

@bot.event
async def on_raw_reaction_add(payload):
    if str(payload.message_id) in bot.data["reaction_roles"]:
        emoji = str(payload.emoji)
        role_id = bot.data["reaction_roles"][str(payload.message_id)].get(emoji)
        if role_id:
            guild = bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = guild.get_role(role_id)
            if role:
                await member.add_roles(role)

# Погода
@tree.command(name="weather", description="Показать погоду в городе")
async def weather(interaction: Interaction, city: str):
    url = f"http://wttr.in/{city}?format=3"
    try:
        res = requests.get(url)
        await interaction.response.send_message(f"☁️ Погода: {res.text}")
    except:
        await interaction.response.send_message("❌ Ошибка получения погоды.")

# Мемы
@tree.command(name="meme", description="Показать случайный мем")
async def meme(interaction: Interaction):
    res = requests.get("https://meme-api.com/gimme").json()
    await interaction.response.send_message(res["url"])

# Кот
@tree.command(name="cat", description="Показать кота")
async def cat(interaction: Interaction):
    res = requests.get("https://api.thecatapi.com/v1/images/search").json()
    await interaction.response.send_message(res[0]["url"])

# Пёс
@tree.command(name="dog", description="Показать собаку")
async def dog(interaction: Interaction):
    res = requests.get("https://dog.ceo/api/breeds/image/random").json()
    await interaction.response.send_message(res["message"])

# Монетка
@tree.command(name="coinflip", description="Подбросить монетку")
async def coinflip(interaction: Interaction):
    await interaction.response.send_message(random.choice(["Орел", "Решка"]))

# NSFW toggle
@tree.command(name="nsfw", description="Разрешить/запретить 18+ в этом канале")
@app_commands.checks.has_permissions(administrator=True)
async def nsfw(interaction: Interaction):
    cid = str(interaction.channel_id)
    if cid in bot.data["nsfw_allowed"]:
        bot.data["nsfw_allowed"].remove(cid)
        await interaction.response.send_message("🔞 NSFW отключен в этом канале.")
    else:
        bot.data["nsfw_allowed"].append(cid)
        await interaction.response.send_message("✅ NSFW включен в этом канале.")
    save_data(bot.data)

# NSFW контент
@tree.command(name="hentai", description="Показать хентай (NSFW)")
async def hentai(interaction: Interaction):
    if str(interaction.channel_id) not in bot.data["nsfw_allowed"]:
        await interaction.response.send_message("❌ NSFW запрещён в этом канале.", ephemeral=True)
        return
    res = requests.get("https://nekos.life/api/v2/img/hentai").json()
    await interaction.response.send_message(res["url"])

# GitHub webhook создание
@tree.command(name="setgitwebhook", description="Создать GitHub webhook")
@app_commands.checks.has_permissions(administrator=True)
async def set_git_webhook(interaction: Interaction, repo: str, secret: str):
    bot.data["git_webhooks"][repo] = {
        "secret": secret,
        "channel_id": interaction.channel_id
    }
    save_data(bot.data)
    url = f"https://<your-domain>/webhook/{repo.replace('/', '_')}"
    await interaction.response.send_message(
        f"✅ Webhook для `{repo}` создан.\n"
        f"🔑 Secret: `{secret}`\n"
        f"🌐 URL: `{url}`", ephemeral=True)

# Flask GitHub webhook обработчик
app = Flask(__name__)

@app.route("/webhook/<repo_name>", methods=["POST"])
def github_webhook(repo_name):
    repo = repo_name.replace("_", "/")
    if repo not in bot.data["git_webhooks"]:
        return "Unknown repo", 404

    data = bot.data["git_webhooks"][repo]
    secret = data["secret"]
    sig_header = request.headers.get("X-Hub-Signature-256")

    if not sig_header:
        return "Forbidden", 403

    sha_name, signature = sig_header.split("=")
    mac = hmac.new(secret.encode(), msg=request.data, digestmod=hashlib.sha256)
    if not hmac.compare_digest(mac.hexdigest(), signature):
        return "Invalid signature", 403

    payload = request.json
    repo_name = payload["repository"]["full_name"]
    pusher = payload["pusher"]["name"]
    commits = payload["commits"]

    commit_text = "\n".join([f"- [{c['id'][:7]}] {c['message']} by {c['author']['name']}" for c in commits])
    text = f"📦 `{repo_name}`: коммиты от **{pusher}**\n{commit_text}"

    asyncio.run_coroutine_threadsafe(
        send_git_message(data["channel_id"], text),
        bot.loop
    )

    return "OK", 200

async def send_git_message(channel_id, message):
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(message)

# Flask запуск
def run_flask():
    app.run(host="0.0.0.0", port=8080)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# Запуск Discord-бота
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN не найден.")
else:
    bot.run(TOKEN)
