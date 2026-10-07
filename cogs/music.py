# Copyright (C) 2026 Lixiod Technologies

from __future__ import annotations

import asyncio
import collections
import logging
from urllib.parse import urlparse

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

from utils.checks import error_embed, in_same_voice_channel, info_embed, success_embed

log = logging.getLogger("bot.music")

# Safety limits

MAX_TRACK_SECONDS = 2 * 60 * 60
MAX_QUEUE_SIZE = 50
IDLE_DISCONNECT_SECONDS = 300
ALLOWED_URL_SCHEMES = {"http", "https"}

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


def _looks_like_unsafe_input(query: str) -> bool:
    parsed = urlparse(query)
    return bool(parsed.scheme) and parsed.scheme.lower() not in ALLOWED_URL_SCHEMES


class Track:
    __slots__ = ("title", "url", "webpage_url", "duration", "requester")

    def __init__(self, data: dict, requester: discord.Member):
        self.title = data.get("title", "Unknown title")
        self.url = data["url"]
        self.webpage_url = data.get("webpage_url", data.get("original_url", ""))
        self.duration = data.get("duration") or 0
        self.requester = requester


class GuildMusicState:

    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.queue: collections.deque[Track] = collections.deque()
        self.current: Track | None = None
        self.volume: float = 0.5
        self.text_channel: discord.abc.Messageable | None = None
        self._idle_task: asyncio.Task | None = None

    def voice_client(self) -> discord.VoiceClient | None:
        guild = self.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    def cancel_idle_timer(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()

    def start_idle_timer(self):
        self.cancel_idle_timer()
        self._idle_task = asyncio.create_task(self._idle_disconnect())

    async def _idle_disconnect(self):
        try:
            await asyncio.sleep(IDLE_DISCONNECT_SECONDS)
            vc = self.voice_client()
            if vc and not vc.is_playing() and not vc.is_paused():
                await vc.disconnect()
                if self.text_channel:
                    await self.text_channel.send(
                        embed=info_embed("👋 Left voice channel", "No activity for 5 minutes.")
                    )
                self.queue.clear()
                self.current = None
        except asyncio.CancelledError:
            pass

    def play_next(self):
        vc = self.voice_client()
        if not vc or not vc.is_connected():
            return

        if not self.queue:
            self.current = None
            self.start_idle_timer()
            return

        self.current = self.queue.popleft()
        self.cancel_idle_timer()
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(self.current.url, **FFMPEG_OPTIONS), volume=self.volume
        )

        def _after(error: Exception | None):
            if error:
                log.error("Playback error in guild %s: %s", self.guild_id, error)
            self.bot.loop.call_soon_threadsafe(self.play_next)

        vc.play(source, after=_after)
        if self.text_channel:
            asyncio.create_task(
                self.text_channel.send(embed=success_embed("🎶 Now playing", f"**{self.current.title}**"))
            )


class Music(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, GuildMusicState] = {}

    def get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState(self.bot, guild_id)
        return self.states[guild_id]

    async def ensure_voice(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice:
            await interaction.response.send_message(
                embed=error_embed("Not in a voice channel", "You must be in a voice channel first."),
                ephemeral=True,
            )
            return False

        channel = interaction.user.voice.channel
        permissions = channel.permissions_for(interaction.guild.me)
        if not permissions.connect or not permissions.speak:
            await interaction.response.send_message(
                embed=error_embed("Missing permissions", "I need Connect and Speak permissions in that voice channel."),
                ephemeral=True,
            )
            return False

        if interaction.guild.voice_client is None:
            await channel.connect()
        elif interaction.guild.voice_client.channel != channel:
            await interaction.guild.voice_client.move_to(channel)

        return True

    async def _require_same_channel(self, interaction: discord.Interaction) -> bool:
        if interaction.guild.voice_client is None:
            await interaction.response.send_message(
                embed=error_embed("Not connected", "I'm not in a voice channel."), ephemeral=True
            )
            return False
        if interaction.user.guild_permissions.manage_channels:
            return True
        if not await in_same_voice_channel(interaction):
            await interaction.response.send_message(
                embed=error_embed("Join the voice channel", "You need to be in the same voice channel as me."),
                ephemeral=True,
            )
            return False
        return True

    # Join

    @app_commands.command(name="join", description="Connects the bot to your current voice channel.")
    async def join(self, interaction: discord.Interaction):
        if not await self.ensure_voice(interaction):
            return
        self.get_state(interaction.guild_id).text_channel = interaction.channel
        await interaction.response.send_message(embed=success_embed("Connected", f"Joined **{interaction.user.voice.channel.name}**."))

    # Play

    @app_commands.command(name="play", description="Plays or queues music from a URL or search term.")
    async def play(self, interaction: discord.Interaction, query: str):
        if not await self.ensure_voice(interaction):
            return

        if _looks_like_unsafe_input(query):
            return await interaction.response.send_message(
                embed=error_embed("Unsupported link", "Only http(s) links or search terms are supported."),
                ephemeral=True,
            )

        state = self.get_state(interaction.guild_id)
        state.text_channel = interaction.channel

        if len(state.queue) >= MAX_QUEUE_SIZE:
            return await interaction.response.send_message(
                embed=error_embed("Queue full", f"The queue is limited to {MAX_QUEUE_SIZE} tracks."), ephemeral=True
            )

        await interaction.response.defer()

        try:
            data = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False)),
                timeout=30,
            )
        except asyncio.TimeoutError:
            return await interaction.followup.send(embed=error_embed("Timed out", "That took too long to load. Try again."))
        except yt_dlp.utils.DownloadError:
            log.warning("yt-dlp failed to resolve query %r", query)
            return await interaction.followup.send(embed=error_embed("Not found", "I couldn't find or load that track."))
        except Exception:
            log.exception("Unexpected error resolving query %r", query)
            return await interaction.followup.send(embed=error_embed("Error", "Something went wrong loading that track."))

        if "entries" in data:
            entries = [e for e in data["entries"] if e]
            if not entries:
                return await interaction.followup.send(embed=error_embed("Not found", "No results for that search."))
            data = entries[0]

        duration = data.get("duration") or 0
        if duration > MAX_TRACK_SECONDS:
            return await interaction.followup.send(
                embed=error_embed("Track too long", f"Tracks are limited to {MAX_TRACK_SECONDS // 3600} hour(s).")
            )

        track = Track(data, interaction.user)
        state.queue.append(track)

        vc = interaction.guild.voice_client
        if not vc.is_playing() and not vc.is_paused() and state.current is None:
            state.play_next()
            await interaction.followup.send(embed=success_embed("🎶 Now playing", f"**{track.title}**"))
        else:
            await interaction.followup.send(
                embed=success_embed("➕ Queued", f"**{track.title}** — position {len(state.queue)} in queue.")
            )

    # Pause / Resume / Skip / Stop / Leave

    @app_commands.command(name="pause", description="Pauses the current track.")
    async def pause(self, interaction: discord.Interaction):
        if not await self._require_same_channel(interaction):
            return
        vc = interaction.guild.voice_client
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message(embed=success_embed("⏸️ Paused"))
        else:
            await interaction.response.send_message(embed=error_embed("Nothing playing", "There's nothing to pause."), ephemeral=True)

    @app_commands.command(name="resume", description="Resumes the paused track.")
    async def resume(self, interaction: discord.Interaction):
        if not await self._require_same_channel(interaction):
            return
        vc = interaction.guild.voice_client
        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message(embed=success_embed("▶️ Resumed"))
        else:
            await interaction.response.send_message(embed=error_embed("Not paused", "Playback isn't paused."), ephemeral=True)

    @app_commands.command(name="skip", description="Skips the current track.")
    async def skip(self, interaction: discord.Interaction):
        if not await self._require_same_channel(interaction):
            return
        vc = interaction.guild.voice_client
        if vc.is_playing() or vc.is_paused():
            vc.stop()  # triggers the `after` callback -> plays next automatically
            await interaction.response.send_message(embed=success_embed("⏭️ Skipped"))
        else:
            await interaction.response.send_message(embed=error_embed("Nothing playing", "There's nothing to skip."), ephemeral=True)

    @app_commands.command(name="stop", description="Stops playback and clears the queue.")
    async def stop(self, interaction: discord.Interaction):
        if not await self._require_same_channel(interaction):
            return
        state = self.get_state(interaction.guild_id)
        state.queue.clear()
        state.current = None
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        await interaction.response.send_message(embed=success_embed("⏹️ Stopped", "Queue cleared."))

    @app_commands.command(name="leave", description="Disconnects the bot from the voice channel.")
    async def leave(self, interaction: discord.Interaction):
        if not await self._require_same_channel(interaction):
            return
        state = self.get_state(interaction.guild_id)
        state.cancel_idle_timer()
        state.queue.clear()
        state.current = None
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message(embed=success_embed("👋 Disconnected"))

    # Queue / Now playing / Volume

    @app_commands.command(name="queue", description="Shows the current music queue.")
    async def queue_(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if not state.current and not state.queue:
            return await interaction.response.send_message(embed=info_embed("Queue is empty"), ephemeral=True)

        lines = []
        if state.current:
            lines.append(f"**Now playing:** {state.current.title}")
        for i, track in enumerate(list(state.queue)[:15], start=1):
            lines.append(f"`{i}.` {track.title} — requested by {track.requester.display_name}")
        if len(state.queue) > 15:
            lines.append(f"...and {len(state.queue) - 15} more.")

        await interaction.response.send_message(embed=info_embed("🎶 Queue", "\n".join(lines)))

    @app_commands.command(name="nowplaying", description="Shows the currently playing track.")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if not state.current:
            return await interaction.response.send_message(embed=info_embed("Nothing playing"), ephemeral=True)
        await interaction.response.send_message(
            embed=info_embed("🎶 Now playing", f"**{state.current.title}**\nRequested by {state.current.requester.mention}")
        )

    @app_commands.command(name="volume", description="Sets playback volume (0-100).")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]):
        if not await self._require_same_channel(interaction):
            return
        state = self.get_state(interaction.guild_id)
        state.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = state.volume
        await interaction.response.send_message(embed=success_embed("🔊 Volume set", f"{level}%"))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id != self.bot.user.id:
            return
        if before.channel is not None and after.channel is None:
            state = self.states.get(member.guild.id)
            if state:
                state.cancel_idle_timer()
                state.queue.clear()
                state.current = None


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
