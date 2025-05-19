import os
import discord
from discord.ext import commands
from discord import ui
from flask import Flask, render_template, request, redirect
import threading
import asyncio

# Инициализация Flask приложения
app = Flask(__name__)

# Настройка Discord бота
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Общие данные
bot.data = {
    "reaction_roles": {}
}
channels_by_category = {}

# Discord события и команды
@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if guild_id:
        guild = bot.get_guild(int(guild_id))
        if guild:
            for category in guild.categories:
                channels_by_category[category.name] = [channel for channel in category.text_channels]
        else:
            print("Сервер не найден!")

# Модальное окно для реакционных ролей
class ReactionRoleModal(ui.Modal, title="Настройка реакционной роли"):
    message_id = ui.TextInput(label="ID сообщения")
    emoji = ui.TextInput(label="Эмодзи")
    role_id = ui.TextInput(label="ID роли")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            message_id = int(self.message_id.value)
            emoji = self.emoji.value
            role_id = int(self.role_id.value)
            channel = interaction.channel
            message = await channel.fetch_message(message_id)
            await message.add_reaction(emoji)
            bot.data["reaction_roles"][(message_id, emoji)] = role_id
            await interaction.response.send_message("Реакционная роль настроена!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrole(ctx):
    await ctx.send_modal(ReactionRoleModal())

@bot.event
async def on_raw_reaction_add(payload):
    key = (payload.message_id, str(payload.emoji))
    if key in bot.data["reaction_roles"]:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(bot.data["reaction_roles"][key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    key = (payload.message_id, str(payload.emoji))
    if key in bot.data["reaction_roles"]:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(bot.data["reaction_roles"][key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.remove_roles(role)

# Flask маршруты
@app.route("/")
def index():
    return render_template("index.html", channels=channels_by_category)

@app.route("/send", methods=["POST"])
def send():
    try:
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
            
            embed = discord.Embed() if image_url else None
            if image_url:
                embed.set_image(url=image_url)
            
            view = None
            if button_label and button_url:
                view = discord.ui.View()
                view.add_item(discord.ui.Button(label=button_label, url=button_url))
            
            await channel.send(content=message, embed=embed, view=view)

        asyncio.run_coroutine_threadsafe(send_discord_message(), bot.loop)
        return redirect("/")
    except Exception as e:
        return f"Ошибка: {e}", 500

# Функции запуска
def run_flask():
    app.run(host="0.0.0.0", port=5000)

def run_bot():
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Переменная окружения DISCORD_TOKEN не задана.")
        return
    bot.run(TOKEN)

if __name__ == "__main__":
    # Запуск Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True  # Делаем поток демоном, чтобы он завершался с основным
    flask_thread.start()
    
    # Запуск бота в основном потоке
    run_bot()