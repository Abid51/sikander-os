"""
Plugin: Email Notification System
Migrated to IgrisPlugin base class
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from app.core.plugin_loader import IgrisPlugin

logger = logging.getLogger(__name__)


class EmailNotificationPlugin(IgrisPlugin):
    """Email notification plugin for Igris"""

    NAME = "email_notifications"
    VERSION = "1.0.0"
    AUTHOR = "Igris Team"
    DESCRIPTION = "Send email notifications for important events"

    def __init__(self):
        self.enabled = False
        self.config = {}
        self._message_count = 0

    def on_load(self):
        self.enabled = True
        logger.info(f"[PLUGIN: {self.NAME}] Email notification plugin loaded ✅")

    def on_unload(self):
        self.enabled = False
        logger.info(f"[PLUGIN: {self.NAME}] Unloaded. {self._message_count} emails queued.")

    def on_command(self, command: str, args: dict) -> Optional[Any]:
        if command == "send_email":
            return self._send_email(args)
        elif command == "send_notification":
            return self._send_notification(args)
        return None

    def _send_email(self, args: dict) -> dict:
        recipient = args.get("recipient", "")
        subject = args.get("subject", "")
        body = args.get("body", "")

        if not all([recipient, subject, body]):
            return {"error": "Missing required parameters: recipient, subject, body"}

        # Simulate sending email
        self._message_count += 1
        logger.info(f"[EMAIL] Sent to {recipient}: {subject}")

        return {
            "status": "sent",
            "recipient": recipient,
            "subject": subject,
            "timestamp": datetime.now().isoformat(),
        }

    def _send_notification(self, args: dict) -> dict:
        recipients = args.get("recipients", [])
        subject = args.get("subject", "Notification")
        body = args.get("body", "")

        if not recipients:
            return {"error": "No recipients specified"}

        sent = 0
        for r in recipients:
            result = self._send_email({"recipient": r, "subject": subject, "body": body})
            if result.get("status") == "sent":
                sent += 1

        return {"status": "completed", "total": len(recipients), "sent": sent, "failed": len(recipients) - sent}

    def get_commands(self) -> list:
        return [
            {"name": "send_email", "args": ["recipient", "subject", "body"], "description": "Send an email"},
            {"name": "send_notification", "args": ["recipients", "subject", "body"], "description": "Bulk notification"},
        ]

    def get_status(self) -> dict:
        return {"status": "active" if self.enabled else "inactive", "emails_queued": self._message_count}
