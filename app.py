import os
import asyncio
import threading
import discord
from discord.ext import commands
from discord import ui
from flask import Flask, render_template, request, redirect

# Создаём Flask-приложение
app = Flask(__name__)

# Словарь для сохранения каналов по категориям (будет заполняться при on_ready)
channels_by_category = {}

# Маршрут главной страницы — здесь можно отобразить форму для отправки сообщений
@app.route("/")
def index():
    # Передаем информацию о каналах, собранную из Discord
    return render_template("index.html", channels=channels_by_category)

# Маршрут для отправки сообщений в Discord
@app.route("/send", methods=["POST"])
def send():
    channel_id = int(request.form["channel"])
    message_text = request.form["message"]
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

        await channel.send(content=message_text, embed=embed, view=view)

    # Запускаем корутину в потоке, используя цикл событий бота
    asyncio.run_coroutine_threadsafe(send_discord_message(), bot.loop)
    return redirect("/")

# Функция для запуска Flask-сервера в отдельном потоке
def run_flask():
    app.run(host="0.0.0.0", port=5000)

# Объединяем intents для всех нужных событий
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True
intents.messages = True
intents.guild_messages = True

# Инициализируем бота
bot = commands.Bot(command_prefix="!", intents=intents)

# Временное хранилище для связок реакций и ролей
bot.data = {
    "reaction_roles": {}
}

# Модальное окно для настройки реакционных ролей
class ReactionRoleModal(ui.Modal, title="Настройка реакционной роли"):
    message_id = ui.TextInput(label="ID сообщения")
    emoji = ui.TextInput(label="Эмодзи")
    role_id = ui.TextInput(label="ID роли")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            msg_id = int(self.message_id.value)
            emoji_val = self.emoji.value
            role_id_val = int(self.role_id.value)

            channel = interaction.channel
            message = await channel.fetch_message(msg_id)
            await message.add_reaction(emoji_val)

            # Сохраняем связку (ID сообщения, эмодзи) -> роль
            bot.data["reaction_roles"][(msg_id, emoji_val)] = role_id_val

            await interaction.response.send_message("Реакционная роль настроена!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

# Команда для вызова формы настройки реакционной роли (только для администраторов)
@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrole(ctx):
    await ctx.send_modal(ReactionRoleModal())

# Обработка события добавления реакции — выдача роли указанному участнику
@bot.event
async def on_raw_reaction_add(payload):
    key = (payload.message_id, str(payload.emoji))
    if key in bot.data["reaction_roles"]:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(bot.data["reaction_roles"][key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.add_roles(role)

# Обработка события удаления реакции — убираем роль у пользователя
@bot.event
async def on_raw_reaction_remove(payload):
    key = (payload.message_id, str(payload.emoji))
    if key in bot.data["reaction_roles"]:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(bot.data["reaction_roles"][key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.remove_roles(role)

# При запуске бота заполняем словарь каналов по категориям,
# используя ID сервера, полученный из переменной окружения
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
    else:
        print("DISCORD_GUILD_ID не задан")

# Запуск приложения: Flask-сервер в отдельном потоке и бот Discord.
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN is None:
        print("❌ Переменная окружения DISCORD_TOKEN не задана.")
    else:
        threading.Thread(target=run_flask).start()
        asyncio.run(bot.start(TOKEN))
