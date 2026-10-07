# Copyright (C) 2026 Lixiod Technologies

from __future__ import annotations

import datetime
import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import HierarchyError, ensure_can_moderate, error_embed, success_embed
from utils.storage import read_json, write_json

log = logging.getLogger("bot.moderation")

WARNINGS_FILE = "warnings"


class Moderation(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Kick

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    @app_commands.describe(member="The member to kick", reason="Why this member is being kicked")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @app_commands.checks.cooldown(3, 10.0, key=lambda i: i.guild_id)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        try:
            ensure_can_moderate(interaction.guild, interaction.user, member)
        except HierarchyError as e:
            return await interaction.response.send_message(embed=error_embed("Can't do that", str(e)), ephemeral=True)

        await self._notify_dm(member, "kicked", interaction.guild, reason)

        try:
            await member.kick(reason=f"{reason} | By {interaction.user} ({interaction.user.id})")
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=error_embed("Failed", "I don't have permission to kick this member."),
                ephemeral=True,
            )

        log.info("%s kicked %s (reason: %s)", interaction.user, member, reason)
        await interaction.response.send_message(
            embed=success_embed("Member kicked", f"**{member}** has been kicked.\n**Reason:** {reason}")
        )

    # Ban / Unban

    @app_commands.command(name="ban", description="Bans a member from the server.")
    @app_commands.describe(
        member="The member to ban",
        reason="Why this member is being banned",
        delete_message_days="Days of their message history to delete (0-7)",
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.checks.cooldown(3, 10.0, key=lambda i: i.guild_id)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
        delete_message_days: app_commands.Range[int, 0, 7] = 0,
    ):
        try:
            ensure_can_moderate(interaction.guild, interaction.user, member)
        except HierarchyError as e:
            return await interaction.response.send_message(embed=error_embed("Can't do that", str(e)), ephemeral=True)

        await self._notify_dm(member, "banned", interaction.guild, reason)

        try:
            await member.ban(
                reason=f"{reason} | By {interaction.user} ({interaction.user.id})",
                delete_message_seconds=delete_message_days * 86400,
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=error_embed("Failed", "I don't have permission to ban this member."),
                ephemeral=True,
            )

        log.info("%s banned %s (reason: %s)", interaction.user, member, reason)
        await interaction.response.send_message(
            embed=success_embed("Member banned", f"**{member}** has been banned.\n**Reason:** {reason}")
        )

    @app_commands.command(name="unban", description="Unbans a user by their ID.")
    @app_commands.describe(user_id="The ID of the user to unban")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        if not user_id.isdigit():
            return await interaction.response.send_message(
                embed=error_embed("Invalid ID", "Please provide a valid numeric user ID."),
                ephemeral=True,
            )

        try:
            user = discord.Object(id=int(user_id))
            await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user}")
        except discord.NotFound:
            return await interaction.response.send_message(
                embed=error_embed("Not found", "That user isn't banned."), ephemeral=True
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=error_embed("Failed", "I don't have permission to unban."), ephemeral=True
            )

        await interaction.response.send_message(embed=success_embed("User unbanned", f"<@{user_id}> has been unbanned."))

    # Timeout

    @app_commands.command(name="timeout", description="Times out a member for a given duration.")
    @app_commands.describe(member="The member to time out", minutes="Duration in minutes (max 40320 = 28 days)", reason="Reason")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str = "No reason provided",
    ):
        try:
            ensure_can_moderate(interaction.guild, interaction.user, member)
        except HierarchyError as e:
            return await interaction.response.send_message(embed=error_embed("Can't do that", str(e)), ephemeral=True)

        duration = datetime.timedelta(minutes=minutes)
        try:
            await member.timeout(duration, reason=f"{reason} | By {interaction.user}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=error_embed("Failed", "I don't have permission to time out this member."),
                ephemeral=True,
            )

        await interaction.response.send_message(
            embed=success_embed("Member timed out", f"**{member}** has been timed out for **{minutes} minute(s)**.\n**Reason:** {reason}")
        )

    @app_commands.command(name="untimeout", description="Removes an active timeout from a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.timeout(None, reason=f"Timeout removed by {interaction.user}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=error_embed("Failed", "I don't have permission to do that."), ephemeral=True
            )
        await interaction.response.send_message(embed=success_embed("Timeout removed", f"**{member}** can speak again."))

    # Clear / purge

    @app_commands.command(name="clear", description="Deletes a number of recent messages (max 100).")
    @app_commands.describe(amount="How many messages to delete (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.checks.cooldown(2, 15.0, key=lambda i: i.channel_id)
    async def clear(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
        except discord.Forbidden:
            return await interaction.followup.send(embed=error_embed("Failed", "I don't have permission to delete messages here."))
        await interaction.followup.send(embed=success_embed("Messages deleted", f"Deleted {len(deleted)} message(s)."))

    # Slowmode / lock / unlock

    @app_commands.command(name="slowmode", description="Sets slowmode delay for this channel.")
    @app_commands.describe(seconds="Delay in seconds (0 to disable, max 21600)")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await interaction.response.send_message(embed=success_embed("Slowmode disabled"))
        else:
            await interaction.response.send_message(embed=success_embed("Slowmode set", f"Members must now wait **{seconds}s** between messages."))

    @app_commands.command(name="lock", description="Prevents @everyone from sending messages in this channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=success_embed("Channel locked", "🔒 @everyone can no longer send messages here."))

    @app_commands.command(name="unlock", description="Restores @everyone's ability to send messages in this channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=success_embed("Channel unlocked", "🔓 @everyone can send messages again."))

    # Warning system

    @app_commands.command(name="warn", description="Issues a warning to a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        try:
            ensure_can_moderate(interaction.guild, interaction.user, member)
        except HierarchyError as e:
            return await interaction.response.send_message(embed=error_embed("Can't do that", str(e)), ephemeral=True)

        data = await read_json(WARNINGS_FILE, default={})
        guild_warns = data.setdefault(str(interaction.guild_id), {})
        member_warns = guild_warns.setdefault(str(member.id), [])
        member_warns.append(
            {
                "moderator_id": interaction.user.id,
                "reason": reason,
                "timestamp": discord.utils.utcnow().isoformat(),
            }
        )
        await write_json(WARNINGS_FILE, data)

        await self._notify_dm(member, "warned", interaction.guild, reason)
        await interaction.response.send_message(
            embed=success_embed("Member warned", f"**{member}** now has **{len(member_warns)}** warning(s).\n**Reason:** {reason}")
        )

    @app_commands.command(name="warnings", description="Lists a member's warnings.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_(self, interaction: discord.Interaction, member: discord.Member):
        data = await read_json(WARNINGS_FILE, default={})
        member_warns = data.get(str(interaction.guild_id), {}).get(str(member.id), [])

        if not member_warns:
            return await interaction.response.send_message(
                embed=success_embed("No warnings", f"**{member}** has no warnings."), ephemeral=True
            )

        embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.orange())
        for i, w in enumerate(member_warns[-25:], start=1):
            mod = interaction.guild.get_member(w["moderator_id"])
            embed.add_field(
                name=f"#{i} — {discord.utils.format_dt(discord.utils.parse_time(w['timestamp']), 'R')}",
                value=f"By {mod.mention if mod else w['moderator_id']}: {w['reason']}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Clears all warnings for a member.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        data = await read_json(WARNINGS_FILE, default={})
        guild_warns = data.get(str(interaction.guild_id), {})
        guild_warns.pop(str(member.id), None)
        await write_json(WARNINGS_FILE, data)
        await interaction.response.send_message(embed=success_embed("Warnings cleared", f"All warnings for **{member}** have been cleared."))

    # Helpers

    @staticmethod
    async def _notify_dm(member: discord.Member, action: str, guild: discord.Guild, reason: str) -> None:
        try:
            await member.send(
                embed=discord.Embed(
                    title=f"You have been {action} in {guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.orange(),
                )
            )
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
