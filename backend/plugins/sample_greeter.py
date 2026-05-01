"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS SAMPLE PLUGIN — System Greeter
  Demonstrates how to build Igris plugins
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

To create your own plugin:
1. Create a new .py file in this directory
2. Import and extend IgrisPlugin
3. Implement any hooks you need
4. Restart or call POST /plugins/load
"""

import time
from app.core.plugin_loader import IgrisPlugin


class SystemGreeterPlugin(IgrisPlugin):
    """Adds a 'greet' command and logs all messages."""

    NAME = "system_greeter"
    VERSION = "1.0.0"
    DESCRIPTION = "Greets the user and logs message counts"
    AUTHOR = "Igris OS"

    def __init__(self):
        self._message_count = 0
        self._loaded_at = None

    def on_load(self):
        self._loaded_at = time.time()
        print(f"[PLUGIN: {self.NAME}] Loaded successfully ✅")

    def on_unload(self):
        print(f"[PLUGIN: {self.NAME}] Unloaded. {self._message_count} messages processed.")

    def on_command(self, command: str, args: dict):
        if command == "greet":
            name = args.get("name", "My Liege")
            return f"Hukum mere Aqa, {name}! Igris is at your eternal service. ⚔️"
        return None

    def on_message(self, user_msg: str, ai_response: str):
        self._message_count += 1
        # Don't modify the response, just track
        return None

    def on_startup(self):
        print(f"[PLUGIN: {self.NAME}] System startup detected.")

    def get_commands(self):
        return [
            {"name": "greet", "args": ["name"], "description": "Greet the user by name"},
        ]

    def get_status(self):
        uptime = time.time() - self._loaded_at if self._loaded_at else 0
        return {
            "status": "active",
            "messages_processed": self._message_count,
            "uptime_secs": round(uptime, 1),
        }
