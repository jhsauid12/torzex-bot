import os
import discord
from discord.ext import commands
from flask import Flask, render_template, request, redirect, url_for
import threading

TOKEN = "MTM3NDA0ODM5OTk3NTc4MDQ2Mw.Gtk6bd.3eeWjXcKWdAGcmP9vhnhGRQkchXtNO62fgg5-M"
GUILD_ID = 1373993594486259734  # без кавычек, число

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

app = Flask(__name__)
discord_client_ready = threading.Event()

channels_by_category = {}

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    guild = bot.get_guild(GUILD_ID)

    if guild is None:
        print("Сервер не найден.")
        return

    global channels_by_category
    channels_by_category = {}

    for channel in guild.text_channels:
        category = channel.category.name if channel.category else "Без категории"
        if category not in channels_by_category:
            channels_by_category[category] = []
        channels_by_category[category].append(channel)

    discord_client_ready.set()

@app.route("/", methods=["GET"])
def index():
    if not discord_client_ready.is_set():
        return "Бот не готов. Попробуй позже.", 503

    return render_template("index.html", channels=channels_by_category)

@app.route("/send", methods=["POST"])
def send():
    channel_id = int(request.form.get("channel"))
    message = request.form.get("message")
    image_url = request.form.get("image_url")

    async def send_message():
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(description=message, color=discord.Color.blue())
            if image_url:
                embed.set_image(url=image_url)
            await channel.send(embed=embed)
        else:
            print("Канал не найден.")

    bot.loop.create_task(send_message())
    return redirect(url_for("index"))

def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    bot.run(TOKEN)
