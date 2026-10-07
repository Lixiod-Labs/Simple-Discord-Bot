# Simple Discord Bot

A modular, production-ready Discord bot built with Python.

> **Changelog highlights (this revision)**
> - 🔴 **Fixed a bot-breaking bug**: `cogs/utility.py` had broken indentation and would throw an `IndentationError` on startup, so the entire module (and bot) never loaded.
> - 🔒 **Fixed security/abuse issues**: moderation commands had no role-hierarchy checks (a moderator could kick/ban/warn the server owner or higher-ranked staff), no cooldowns, and no bound on `/clear`'s message count. The bot also requested the privileged `MESSAGE CONTENT` intent despite never using it.
> - 🔒 Music input is now validated (http/https only), track length and queue size are capped, and raw exception text is no longer leaked to users (everything is logged server-side instead).
> - ✨ Added a proper global error handler, rotating file logging, and graceful shutdown.
> - ✨ Added a persistent **warning system**, `timeout`/`untimeout`, `unban`, `slowmode`, `lock`/`unlock`.
> - ✨ Added a real **music queue** (`join`, `pause`, `resume`, `skip`, `queue`, `nowplaying`, `volume`) with idle auto-disconnect and per-channel playback permission checks.
> - ✨ Added `botinfo`, `help`, richer `serverinfo`/`userinfo`, and fun commands `coinflip`, `choose`, `rps`, `poll`.

---

## Modules Included

* `moderation`: `kick`, `ban`, `unban`, `timeout`, `untimeout`, `clear`, `slowmode`, `lock`, `unlock`, `warn`, `warnings`, `clearwarnings`
* `utility`: `ping`, `serverinfo`, `userinfo`, `avatar`, `botinfo`, `help`
* `fun`: `roll`, `8ball`, `coinflip`, `choose`, `rps`, `poll`
* `music`: `join`, `play`, `pause`, `resume`, `skip`, `stop`, `leave`, `queue`, `nowplaying`, `volume`

---

## Project Structure

```text
Simple-Discord-Bot/
├── cogs/
│   ├── fun.py
│   ├── moderation.py
│   ├── music.py
│   └── utility.py
├── utils/
│   ├── checks.py        # hierarchy checks, voice checks, embed helpers
│   └── storage.py        # atomic JSON persistence (warnings, etc.)
├── data/                  # created automatically (warnings.json lives here)
├── logs/                  # created automatically (rotating bot.log)
├── .env.example
├── .gitignore
├── main.py
└── requirements.txt
```

---

## System Requirements

* **Python**: `3.10` or higher
* **FFmpeg**: Must be installed and added to your system `PATH` for the music module to function.

---

## Installation

1. **Clone the repository**:
```bash
git clone https://github.com/Lixiod-Labs/Simple-Discord-Bot.git
cd Simple-Discord-Bot
```

2. **Set up a virtual environment**:
```bash
python -m venv venv
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

---

## Configuration

1. Create a `.env` file in the root directory (copy `.env.example`):
```env
DISCORD_TOKEN=your-real-token-here
COMMAND_PREFIX=!
OWNER_IDS=
```

2. Enable or disable modules in `main.py`:
```python
ENABLED_EXTENSIONS = [
    "cogs.moderation",
    "cogs.utility",
    "cogs.fun",
    "cogs.music",
]
```

3. Ensure the following **Privileged Gateway Intent** is enabled in the [Discord Developer Portal](https://discord.com/developers/applications):
   * `SERVER MEMBERS INTENT`

   `MESSAGE CONTENT INTENT` is **no longer required** — the bot only uses slash commands, so this privileged intent was removed to reduce the bot's permission footprint.

4. Give the bot's role a position **above** any role you want it to be able to moderate (kick/ban/timeout). This is required by Discord's own permission hierarchy, and the bot will now tell you clearly if it can't act instead of crashing.

---

## Usage

Run the bot:

```bash
python main.py
```

Logs are written to both the console and `logs/bot.log` (rotated at 2 MB, 3 backups kept).

---

## Command Reference

### Moderation

| Command | Arguments | Permissions Required | Description |
| --- | --- | --- | --- |
| `/kick` | `member`, `[reason]` | Kick Members | Kicks a member. Blocked if the target outranks you or the bot. |
| `/ban` | `member`, `[reason]`, `[delete_message_days]` | Ban Members | Bans a member. |
| `/unban` | `user_id` | Ban Members | Unbans a user by ID. |
| `/timeout` | `member`, `minutes`, `[reason]` | Moderate Members | Times out a member (1-40320 minutes). |
| `/untimeout` | `member` | Moderate Members | Removes an active timeout. |
| `/clear` | `amount` (1-100) | Manage Messages | Bulk deletes recent messages. |
| `/slowmode` | `seconds` (0-21600) | Manage Channels | Sets channel slowmode. |
| `/lock` / `/unlock` | — | Manage Channels | Blocks/restores @everyone sending messages. |
| `/warn` | `member`, `reason` | Moderate Members | Issues a persistent warning. |
| `/warnings` | `member` | Moderate Members | Lists a member's warnings. |
| `/clearwarnings` | `member` | Manage Guild | Clears a member's warnings. |

### Utility

| Command | Arguments | Description |
| --- | --- | --- |
| `/ping` | None | Shows WebSocket + response latency. |
| `/serverinfo` | None | Server stats (members, boosts, channels, roles...). |
| `/userinfo` | `[member]` | Details about a user, including roles. |
| `/avatar` | `[member]` | Shows a user's avatar. |
| `/botinfo` | None | Bot stats: servers, users, uptime, versions. |
| `/help` | None | Lists every available command. |

### Fun

| Command | Arguments | Description |
| --- | --- | --- |
| `/roll` | `[dice]` | Rolls dice using `NdX` format (1-10 dice, 1-100 sides). |
| `/8ball` | `question` | Ask the Magic 8-Ball a question. |
| `/coinflip` | None | Flips a coin. |
| `/choose` | `options` | Picks one option from a comma-separated list. |
| `/rps` | `choice` | Rock-paper-scissors against the bot. |
| `/poll` | `question` | Posts a 👍/👎 poll. |

### Music

| Command | Arguments | Description |
| --- | --- | --- |
| `/join` | None | Connects the bot to your voice channel. |
| `/play` | `query` | Streams or queues a URL / search term (http/https only, max 2h/track). |
| `/pause` / `/resume` | None | Pauses/resumes playback. |
| `/skip` | None | Skips to the next queued track. |
| `/queue` | None | Shows the current queue. |
| `/nowplaying` | None | Shows the current track. |
| `/volume` | `level` (0-100) | Sets playback volume. |
| `/stop` | None | Stops playback and clears the queue. |
| `/leave` | None | Disconnects the bot (auto-leaves after 5 min idle anyway). |

Playback-control commands require you to be in the same voice channel as the bot (or have Manage Channels).

---

## License

Distributed under the AGPL-3.0 License. See `LICENSE` for details.
