# Copyright (C) 2026 Lixiod Technologies

from __future__ import annotations

import discord

ERROR_COLOR = discord.Color.red()
SUCCESS_COLOR = discord.Color.green()
INFO_COLOR = discord.Color.blurple()


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=description, color=ERROR_COLOR)


def success_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"✅ {title}", description=description, color=SUCCESS_COLOR)


def info_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=INFO_COLOR)


class HierarchyError(Exception):


def ensure_can_moderate(
    guild: discord.Guild,
    actor: discord.Member,
    target: discord.Member,
) -> None:
    if target.id == actor.id:
        raise HierarchyError("You can't use this action on yourself.")

    if target.id == guild.me.id:
        raise HierarchyError("I can't use this action on myself.")

    if target.id == guild.owner_id:
        raise HierarchyError("You can't moderate the server owner.")

    if actor.id != guild.owner_id and target.top_role >= actor.top_role:
        raise HierarchyError(
            "You can't moderate someone with a role equal to or higher than yours."
        )

    if target.top_role >= guild.me.top_role:
        raise HierarchyError(
            "I can't moderate this member — their highest role is above or equal to mine. "
            "Move my role higher in Server Settings → Roles."
        )


async def in_same_voice_channel(interaction: discord.Interaction) -> bool:
    vc = interaction.guild.voice_client
    user_voice = interaction.user.voice
    if vc is None or user_voice is None:
        return False
    return vc.channel.id == user_voice.channel.id
