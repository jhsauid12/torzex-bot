import os
import json
import discord
from discord.ext import commands
from discord import ui
from flask import Flask, render_template, request, redirect
import threading
import asyncio
import aiohttp

# Инициализация Flask
app = Flask(__name__)

# Настройка Discord бота
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Хранилище данных
bot.reaction_roles = {}
channels_by_category = {}
bot.settings = {
    "auto_role": None,
    "log_channel": None
}

DATA_FILE = "reaction_roles.json"
SETTINGS_FILE = "bot_settings.json"

# Загрузка настроек и реакций из файлов
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        bot.reaction_roles = json.load(f)
        bot.reaction_roles = {(int(k.split("|", 1)[0]), k.split("|", 1)[1]): v for k, v in bot.reaction_roles.items()}

if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        bot.settings.update(json.load(f))

# Сохранение реакций
def save_reaction_roles():
    with open(DATA_FILE, "w") as f:
        json.dump({f"{k[0]}|{k[1]}": v for k, v in bot.reaction_roles.items()}, f)

# Сохранение настроек
def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(bot.settings, f)

# События бота
@bot.event
async def on_ready():
    print(f"Бот {bot.user} готов к работе!")
    try:
        await bot.tree.sync()
        print("Слеш-команды синхронизированы")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")

    # Загрузка каналов для веб-интерфейса
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if guild_id:
        guild = bot.get_guild(int(guild_id))
        if guild:
            for category in guild.categories:
                channels_by_category[category.name] = [channel for channel in category.text_channels]

# Префиксная команда
@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrole(ctx, message_id: int, emoji: str, role: discord.Role):
    try:
        message = await ctx.channel.fetch_message(message_id)
        await message.add_reaction(emoji)
        bot.reaction_roles[(message_id, str(emoji))] = role.id
        save_reaction_roles()
        await ctx.send(f"✅ Настроено! Реакция {emoji} теперь выдает роль {role.name}")
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")

# Модалка
class ReactionRoleModal(ui.Modal, title="Настройка реакционной роли"):
    message_id = ui.TextInput(label="ID сообщения")
    emoji = ui.TextInput(label="Эмодзи")
    role_id = ui.TextInput(label="ID роли")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            message_id = int(self.message_id.value)
            emoji = self.emoji.value
            role_id = int(self.role_id.value)

            message = await interaction.channel.fetch_message(message_id)
            await message.add_reaction(emoji)

            bot.reaction_roles[(message_id, emoji)] = role_id
            save_reaction_roles()

            await interaction.response.send_message(
                f"✅ Настроено\nСообщение: {message_id}\nЭмодзи: {emoji}\nРоль: <@&{role_id}>",
                ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)

@bot.tree.command(name="reactionrole", description="Настройка реакционных ролей")
@discord.app_commands.default_permissions(administrator=True)
async def reactionrole_slash(interaction: discord.Interaction):
    await interaction.response.send_modal(ReactionRoleModal())

# Авто-роли при входе
@bot.event
async def on_member_join(member):
    role_id = bot.settings.get("auto_role")
    if role_id:
        role = member.guild.get_role(int(role_id))
        if role:
            await member.add_roles(role)

# Обработка реакций
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    key = (payload.message_id, str(payload.emoji))
    if key in bot.reaction_roles:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(bot.reaction_roles[key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    key = (payload.message_id, str(payload.emoji))
    if key in bot.reaction_roles:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(bot.reaction_roles[key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.remove_roles(role)

# Логи сообщений
@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author.bot:
        return
    log_id = bot.settings.get("log_channel")
    if log_id:
        log_channel = message.guild.get_channel(int(log_id))
        if log_channel:
            await log_channel.send(f"[{message.author}] #{message.channel}: {message.content}")

# Установка авто-роли и логов
@bot.command()
@commands.has_permissions(administrator=True)
async def setautorole(ctx, role: discord.Role):
    bot.settings["auto_role"] = role.id
    save_settings()
    await ctx.send(f"✅ Авто-роль установлена: {role.name}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel):
    bot.settings["log_channel"] = channel.id
    save_settings()
    await ctx.send(f"✅ Лог-канал установлен: {channel.mention}")

# Погода
@bot.tree.command(name="weather", description="Узнать погоду в городе")
async def weather(interaction: discord.Interaction, city: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1") as geo:
                geo_data = await geo.json()
                if not geo_data.get("results"):
                    return await interaction.response.send_message("❌ Город не найден")
                loc = geo_data["results"][0]
                lat, lon = loc["latitude"], loc["longitude"]

            async with session.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true") as weather:
                w_data = await weather.json()
                temp = w_data["current_weather"]["temperature"]
                wind = w_data["current_weather"]["windspeed"]
                await interaction.response.send_message(f"🌡️ {city.title()}: {temp}°C, 💨 {wind} km/h")
    except:
        await interaction.response.send_message("❌ Ошибка при получении данных")

# Веб-интерфейс
@app.route("/")
def index():
    return render_template("index.html", channels=channels_by_category)

@app.route("/send", methods=["POST"])
def send_message():
    try:
        channel_id = int(request.form["channel"])
        message = request.form["message"]
        image_url = request.form.get("image_url", "")
        button_label = request.form.get("button_label", "")
        button_url = request.form.get("button_url", "")

        async def send_discord_message():
            channel = bot.get_channel(channel_id)
            if not channel:
                return
            embed = discord.Embed() if image_url else None
            if embed:
                embed.set_image(url=image_url)

            view = discord.ui.View()
            if button_label and button_url:
                view.add_item(discord.ui.Button(label=button_label, url=button_url))

            await channel.send(content=message, embed=embed, view=view if view.children else None)

        asyncio.run_coroutine_threadsafe(send_discord_message(), bot.loop)
        return redirect("/")
    except Exception as e:
        return f"Ошибка: {e}", 500

# Запуск

def run_flask():
    app.run(host="0.0.0.0", port=5000)

def run_bot():
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Токен Discord не найден!")
        return
    bot.run(TOKEN)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()
