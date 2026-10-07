# Copyright (C) 2026 Lixiod Technologies

import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
OWNER_IDS = {
    int(uid) for uid in os.getenv("OWNER_IDS", "").replace(" ", "").split(",") if uid.isdigit()
}

# Logging setup
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")

file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "bot.log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)
logging.getLogger("discord").setLevel(logging.WARNING)

log = logging.getLogger("bot")

# Intent configuration
intents = discord.Intents.default()
intents.members = True
intents.message_content = False
intents.voice_states = True


class SimpleBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
        self.launch_time: discord.utils.utcnow = None

    async def setup_hook(self) -> None:
        await self.load_extensions()
        try:
            synced = await self.tree.sync()
            log.info("Synchronized %d slash command(s).", len(synced))
        except discord.HTTPException as e:
            log.error("Slash command sync failed: %s", e)

    async def load_extensions(self) -> None:
        for ext in ENABLED_EXTENSIONS:
            try:
                await self.load_extension(ext)
                log.info("Loaded cog: %s", ext)
            except Exception:
                log.exception("Failed to load cog '%s'", ext)

    async def is_owner(self, user: discord.abc.User, /) -> bool:
        if user.id in OWNER_IDS:
            return True
        return await super().is_owner(user)


bot = SimpleBot()

# COGS CONFIGURATION
ENABLED_EXTENSIONS = [
    "cogs.moderation",
    "cogs.utility",
    "cogs.fun",
    "cogs.music",
]


@bot.event
async def on_ready():
    bot.launch_time = discord.utils.utcnow()
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    log.info("Connected to %d guild(s).", len(bot.guilds))
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="/help")
    )


# Global error handling
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "You don't have the required permissions to use this command."
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = "I don't have the required permissions to do that. Check my role's permissions."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"This command is on cooldown. Try again in {error.retry_after:.1f}s."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "You can't use this command right now."
    else:
        log.exception(
            "Unhandled app command error in /%s",
            interaction.command.qualified_name if interaction.command else "?",
            exc_info=error,
        )
        msg = "Something went wrong while running that command."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


async def main():
    if not TOKEN:
        log.critical(
            "No Discord token found. Copy .env.example to .env and set DISCORD_TOKEN."
        )
        raise SystemExit(1)

    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown requested, exiting.")
