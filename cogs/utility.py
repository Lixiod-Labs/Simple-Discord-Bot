# Copyright (C) 2026 Lixiod Technologies

from __future__ import annotations

import platform
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import info_embed


class Utility(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Ping

    @app_commands.command(name="ping", description="Displays the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        start = time.perf_counter()
        await interaction.response.send_message("Pinging...")
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        ws_latency = round(self.bot.latency * 1000)
        await interaction.edit_original_response(
            content=None,
            embed=info_embed("🏓 Pong!", f"**WebSocket:** {ws_latency} ms\n**Response time:** {elapsed_ms} ms"),
        )

    # Server info

    @app_commands.command(name="serverinfo", description="Displays server details.")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=f"Info — {guild.name}", color=discord.Color.blue())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        humans = sum(1 for m in guild.members if not m.bot)
        bots = guild.member_count - humans

        embed.add_field(name="Members", value=f"{guild.member_count} ({humans} humans, {bots} bots)", inline=True)
        embed.add_field(name="Boosts", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        embed.add_field(name="Created on", value=discord.utils.format_dt(guild.created_at, "D"), inline=True)
        embed.add_field(name="Owner", value=str(guild.owner) if guild.owner else f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="Text channels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="Voice channels", value=str(len(guild.voice_channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.set_footer(text=f"Server ID: {guild.id}")

        await interaction.response.send_message(embed=embed)

    # User info

    @app_commands.command(name="userinfo", description="Displays information about a user.")
    @app_commands.guild_only()
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        embed = discord.Embed(title=f"Profile of {target.display_name}", color=target.color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="ID", value=str(target.id), inline=False)

        joined = discord.utils.format_dt(target.joined_at, "D") if target.joined_at else "Unknown"
        created = discord.utils.format_dt(target.created_at, "D") if target.created_at else "Unknown"
        embed.add_field(name="Joined server on", value=joined, inline=True)
        embed.add_field(name="Account created on", value=created, inline=True)

        roles = [r.mention for r in reversed(target.roles) if r.name != "@everyone"]
        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join(roles[:15]) + (" ..." if len(roles) > 15 else "") if roles else "None",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    # Avatar

    @app_commands.command(name="avatar", description="Displays a user's avatar.")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        embed = discord.Embed(title=f"Avatar of {target.display_name}", color=target.color)
        embed.set_image(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # Bot info / uptime

    @app_commands.command(name="botinfo", description="Displays information about the bot.")
    async def botinfo(self, interaction: discord.Interaction):
        bot = self.bot
        uptime = discord.utils.utcnow() - bot.launch_time if bot.launch_time else None
        embed = discord.Embed(title=f"{bot.user.name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Users", value=str(sum(g.member_count for g in bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)} ms", inline=True)
        if uptime:
            embed.add_field(name="Uptime", value=str(uptime).split(".")[0], inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        await interaction.response.send_message(embed=embed)

    # Help

    @app_commands.command(name="help", description="Lists all available commands.")
    async def help_(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📖 Command list", color=discord.Color.blurple())
        for cog_name, cog in self.bot.cogs.items():
            commands_list = cog.get_app_commands()
            if not commands_list:
                continue
            value = "\n".join(f"`/{c.name}` — {c.description}" for c in commands_list)
            embed.add_field(name=cog_name, value=value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
