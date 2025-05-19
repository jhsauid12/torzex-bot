import os
import discord
from discord.ext import commands
from discord import ui
from flask import Flask, render_template, request, redirect
import threading
import asyncio

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

# Префиксная команда (рабочий вариант)
@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrole(ctx, message_id: int, emoji: str, role: discord.Role):
    """Настройка реакционной роли: !reactionrole <message_id> <emoji> <role>"""
    try:
        message = await ctx.channel.fetch_message(message_id)
        await message.add_reaction(emoji)
        bot.reaction_roles[(message_id, str(emoji))] = role.id
        await ctx.send(f"✅ Настроено! Реакция {emoji} теперь выдает роль {role.name}")
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")

# Класс для модального окна (только для слеш-команд)
class ReactionRoleModal(ui.Modal, title="Настройка реакционной роли"):
    message_id = ui.TextInput(label="ID сообщения", placeholder="123456789012345678")
    emoji = ui.TextInput(label="Эмодзи", placeholder="🎉 или :thumbsup:")
    role_id = ui.TextInput(label="ID роли", placeholder="123456789012345678")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            message_id = int(self.message_id.value)
            emoji = self.emoji.value
            role_id = int(self.role_id.value)
            
            channel = interaction.channel
            message = await channel.fetch_message(message_id)
            await message.add_reaction(emoji)
            
            bot.reaction_roles[(message_id, emoji)] = role_id
            await interaction.response.send_message(
                f"✅ Реакционная роль настроена!\n"
                f"Сообщение: {message_id}\n"
                f"Эмодзи: {emoji}\n"
                f"Роль: <@&{role_id}>",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)

# Слеш-команда с модальным окном
@bot.tree.command(name="reactionrole", description="Настройка реакционных ролей")
@discord.app_commands.default_permissions(administrator=True)
async def reactionrole_slash(interaction: discord.Interaction):
    await interaction.response.send_modal(ReactionRoleModal())

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
            
            embed = None
            if image_url:
                embed = discord.Embed()
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