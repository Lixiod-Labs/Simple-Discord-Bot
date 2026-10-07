# Copyright (C) 2026 Lixiod Technologies

from __future__ import annotations

import random
import re

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import error_embed, info_embed

DICE_PATTERN = re.compile(r"^(\d{1,2})d(\d{1,3})$", re.IGNORECASE)


class Fun(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Dice roll

    @app_commands.command(name="roll", description="Rolls dice (e.g., 1d6, 2d20).")
    @app_commands.checks.cooldown(5, 10.0, key=lambda i: i.user.id)
    async def roll(self, interaction: discord.Interaction, dice: str = "1d6"):
        match = DICE_PATTERN.match(dice.strip())
        if not match:
            return await interaction.response.send_message(
                embed=error_embed("Invalid format", "Use the `NdX` format, e.g. `2d6` (1-10 dice, 1-100 sides)."),
                ephemeral=True,
            )

        rolls, limit = int(match.group(1)), int(match.group(2))
        if not (1 <= rolls <= 10) or not (1 <= limit <= 100):
            return await interaction.response.send_message(
                embed=error_embed("Out of range", "Use 1-10 dice and 1-100 sides."), ephemeral=True
            )

        results = [random.randint(1, limit) for _ in range(rolls)]
        await interaction.response.send_message(
            embed=info_embed("🎲 Dice roll", f"**Result:** {results}\n**Total:** {sum(results)}")
        )

    # 8ball

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question.")
    @app_commands.checks.cooldown(5, 10.0, key=lambda i: i.user.id)
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        responses = [
            "It is certain.", "Most likely.", "Without a doubt.",
            "Ask again later.", "Cannot predict now.",
            "Don't count on it.", "My reply is no.", "Very doubtful.",
            "Yes, definitely.", "Outlook good.", "Signs point to yes.",
        ]
        embed = info_embed("🎱 Magic 8-Ball", f"**Question:** {question}\n**Answer:** {random.choice(responses)}")
        await interaction.response.send_message(embed=embed)

    # Coinflip

    @app_commands.command(name="coinflip", description="Flips a coin.")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(embed=info_embed("🪙 Coin flip", f"**{result}!**"))

    # Choose between options

    @app_commands.command(name="choose", description="Picks one option from a comma-separated list.")
    @app_commands.describe(options="Comma-separated list of options, e.g. pizza, sushi, tacos")
    async def choose(self, interaction: discord.Interaction, options: str):
        choices = [o.strip() for o in options.split(",") if o.strip()]
        if len(choices) < 2:
            return await interaction.response.send_message(
                embed=error_embed("Not enough options", "Give me at least 2 options separated by commas."),
                ephemeral=True,
            )
        await interaction.response.send_message(embed=info_embed("🤔 I choose...", f"**{random.choice(choices)}**"))

    # Rock Paper Scissors
    
    @app_commands.command(name="rps", description="Play rock-paper-scissors against the bot.")
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Rock", value="rock"),
            app_commands.Choice(name="Paper", value="paper"),
            app_commands.Choice(name="Scissors", value="scissors"),
        ]
    )
    async def rps(self, interaction: discord.Interaction, choice: app_commands.Choice[str]):
        options = ["rock", "paper", "scissors"]
        bot_choice = random.choice(options)
        user_choice = choice.value

        if user_choice == bot_choice:
            result = "It's a tie!"
        elif (
            (user_choice == "rock" and bot_choice == "scissors")
            or (user_choice == "paper" and bot_choice == "rock")
            or (user_choice == "scissors" and bot_choice == "paper")
        ):
            result = "You win! 🎉"
        else:
            result = "I win! 🤖"

        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        embed = info_embed(
            "✊ Rock Paper Scissors",
            f"You chose {emojis[user_choice]} **{user_choice}**\n"
            f"I chose {emojis[bot_choice]} **{bot_choice}**\n\n**{result}**",
        )
        await interaction.response.send_message(embed=embed)

    # Poll

    @app_commands.command(name="poll", description="Creates a simple yes/no poll.")
    async def poll(self, interaction: discord.Interaction, question: str):
        embed = info_embed("📊 Poll", question)
        embed.set_footer(text=f"Poll started by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("👍")
        await message.add_reaction("👎")


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
