"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS DISCORD BOT
  Full Igris AI inside Discord — chat, tools, voice, image analysis
  Uses discord.py or HTTP webhook fallback
  Setup: DISCORD_BOT_TOKEN in .env
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ── Optional: discord.py ─────────────────────────────────────────────────────
try:
    import discord
    from discord.ext import commands
    _DISCORD = True
except ImportError:
    _DISCORD = False
    logger.warning("[DISCORD] discord.py not installed. Run: pip install discord.py")


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DiscordMessage:
    content: str
    author: str
    channel: str
    guild: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
#  DISCORD BOT
# ─────────────────────────────────────────────────────────────────────────────

class IgrisDiscordBot:
    """
    Discord bot that connects Igris AI to Discord servers.

    Setup:
    ──────
    1. Create bot at https://discord.com/developers
    2. Add DISCORD_BOT_TOKEN to .env
    3. Invite bot to your server with message + slash command permissions
    4. Start via await bot.start_bot()

    Commands:
    ─────────
    !igris <message>  — Chat with Igris
    !status           — System status
    !search <query>   — Web search
    !tools            — List available tools
    """

    def __init__(self) -> None:
        self._token = os.getenv("DISCORD_BOT_TOKEN", "")
        self._webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")
        self._bot: Optional[Any] = None
        self._running = False
        self._message_history: List[DiscordMessage] = []
        self._on_message_callback: Optional[Callable] = None

        if not self._token and not self._webhook_url:
            logger.info("[DISCORD] No token/webhook set. Add DISCORD_BOT_TOKEN to .env")

    @property
    def available(self) -> bool:
        return _DISCORD and bool(self._token)

    def set_message_handler(self, callback: Callable) -> None:
        """Set callback for processing incoming messages."""
        self._on_message_callback = callback

    async def start_bot(self) -> None:
        """Start the Discord bot (blocking — run in background task)."""
        if not _DISCORD:
            logger.error("[DISCORD] discord.py not installed")
            return
        if not self._token:
            logger.error("[DISCORD] No bot token. Set DISCORD_BOT_TOKEN in .env")
            return

        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix="!", intents=intents)
        self._bot = bot

        @bot.event
        async def on_ready():
            logger.info(f"[DISCORD] ⚡ Bot online as {bot.user}")
            self._running = True
            # Set status
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="over Sikander-OS"
                )
            )

        @bot.command(name="igris")
        async def igris_chat(ctx, *, message: str):
            """Chat with Igris AI."""
            self._message_history.append(DiscordMessage(
                content=message,
                author=str(ctx.author),
                channel=str(ctx.channel),
                guild=str(ctx.guild) if ctx.guild else "DM",
            ))

            async with ctx.typing():
                response = await self._process_message(message, str(ctx.author))

            # Discord message limit: 2000 chars
            if len(response) > 1900:
                chunks = [response[i:i + 1900] for i in range(0, len(response), 1900)]
                for chunk in chunks:
                    await ctx.reply(chunk)
            else:
                await ctx.reply(response)

        @bot.command(name="status")
        async def system_status(ctx):
            """Show Igris system status."""
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.5)
                mem = psutil.virtual_memory()
                status = (
                    f"⚡ **Igris System Status**\n"
                    f"```\n"
                    f"CPU:    {cpu}%\n"
                    f"RAM:    {mem.percent}% ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)\n"
                    f"Status: Online\n"
                    f"```"
                )
            except Exception:
                status = "⚡ Igris is online."
            await ctx.reply(status)

        @bot.command(name="search")
        async def web_search(ctx, *, query: str):
            """Search the web via Igris."""
            async with ctx.typing():
                try:
                    from app.tools.igris_tools import get_tool_registry
                    registry = get_tool_registry()
                    result = registry.run("web_search", query=query)
                    if isinstance(result, dict):
                        text = result.get("summary", json.dumps(result, indent=2)[:1500])
                    else:
                        text = str(result)[:1500]
                    await ctx.reply(f"🔍 **Search: {query}**\n{text}")
                except Exception as e:
                    await ctx.reply(f"Search error: {e}")

        @bot.command(name="tools")
        async def list_tools(ctx):
            """List available Igris tools."""
            try:
                from app.tools.igris_tools import get_tool_registry
                registry = get_tool_registry()
                tools = registry.available_tools()
                tool_list = "\n".join(f"• `{t['name']}` — {t['desc']}" for t in tools)
                await ctx.reply(f"🛠️ **Available Tools:**\n{tool_list}")
            except Exception:
                await ctx.reply("Tools: web_search, calculator, python_sandbox, file_manager, system_info")

        @bot.event
        async def on_message(message):
            if message.author == bot.user:
                return
            # Process commands first
            await bot.process_commands(message)
            # Handle DMs or @mentions
            if isinstance(message.channel, discord.DMChannel) or bot.user.mentioned_in(message):
                clean = message.content.replace(f"<@{bot.user.id}>", "").strip()
                if clean and not message.content.startswith("!"):
                    self._message_history.append(DiscordMessage(
                        content=clean,
                        author=str(message.author),
                        channel=str(message.channel),
                        guild=str(message.guild) if message.guild else "DM",
                    ))
                    async with message.channel.typing():
                        response = await self._process_message(clean, str(message.author))
                    if len(response) > 1900:
                        for i in range(0, len(response), 1900):
                            await message.reply(response[i:i + 1900])
                    else:
                        await message.reply(response)

        try:
            await bot.start(self._token)
        except Exception as e:
            logger.error(f"[DISCORD] Bot error: {e}")
            self._running = False

    async def stop_bot(self) -> None:
        """Stop the Discord bot."""
        if self._bot:
            await self._bot.close()
            self._running = False
            logger.info("[DISCORD] Bot stopped.")

    async def _process_message(self, message: str, author: str) -> str:
        """Process a message through Igris brain."""
        # Use callback if set
        if self._on_message_callback:
            try:
                result = self._on_message_callback(message, author)
                if asyncio.iscoroutine(result):
                    result = await result
                return str(result)
            except Exception as e:
                logger.error(f"[DISCORD] Message handler error: {e}")

        # Default: use LLM directly
        try:
            from app.core.llm_manager import universal_llm
            response = await universal_llm.generate_response(
                system_prompt=(
                    "You are Igris, a powerful AI assistant in a Discord server. "
                    "Be helpful, concise, and use Discord formatting (bold, code blocks). "
                    f"You're chatting with {author}."
                ),
                user_prompt=message,
                max_tokens=500,
            )
            return response
        except Exception as e:
            return f"❌ Error: {e}"

    # ── Webhook (no bot required) ─────────────────────────────────────────────

    async def send_webhook(self, content: str, username: str = "Igris AI") -> bool:
        """Send a message via Discord webhook (no bot needed)."""
        if not self._webhook_url:
            return False
        try:
            payload = {"content": content[:2000], "username": username}
            resp = await asyncio.to_thread(
                requests.post, self._webhook_url, json=payload, timeout=10,
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"[DISCORD] Webhook error: {e}")
            return False

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "discord_py_available": _DISCORD,
            "bot_token_set": bool(self._token),
            "webhook_set": bool(self._webhook_url),
            "bot_running": self._running,
            "bot_user": str(self._bot.user) if self._bot and hasattr(self._bot, 'user') and self._bot.user else None,
            "messages_processed": len(self._message_history),
        }

    def get_message_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self._message_history[-limit:]]


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisDiscordBot] = None


def get_discord_bot() -> IgrisDiscordBot:
    global _instance
    if _instance is None:
        _instance = IgrisDiscordBot()
    return _instance
