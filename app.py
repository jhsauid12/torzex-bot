from flask import Flask, render_template, request, redirect
import discord
from discord.ext import commands
import asyncio
import os
import threading

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)
app = Flask(__name__)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
guild_id = os.getenv("DISCORD_GUILD_ID")

channels_by_category = {}

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    guild = bot.get_guild(int(guild_id))
    if guild:
        for category in guild.categories:
            channels_by_category[category.name] = [channel for channel in category.text_channels]
    else:
        print("Сервер не найден!")

@app.route("/")
def index():
    return render_template("index.html", channels=channels_by_category)

@app.route("/send", methods=["POST"])
def send():
    channel_id = int(request.form["channel"])
    message = request.form["message"]
    image_url = request.form.get("image_url", "")
    button_label = request.form.get("button_label", "")
    button_url = request.form.get("button_url", "")

    async def send_discord_message():
        channel = bot.get_channel(channel_id)
        if not channel:
            print("Канал не найден")
            return

        embed = None
        if image_url:
            embed = discord.Embed()
            embed.set_thumbnail(url=image_url)

        view = None
        if button_label and button_url:
            view = discord.ui.View()
            button = discord.ui.Button(label=button_label, url=button_url)
            view.add_item(button)

        await channel.send(content=message, embed=embed, view=view)

    asyncio.run_coroutine_threadsafe(send_discord_message(), bot.loop)
    return redirect("/")

def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(bot.start(TOKEN))
