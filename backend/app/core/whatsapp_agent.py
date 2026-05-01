"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS WHATSAPP INTEGRATION
  Send/receive WhatsApp messages via Twilio API
  Features: send text, receive webhooks, auto-respond, media support
  Setup: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ── Optional: Twilio SDK ─────────────────────────────────────────────────────
try:
    from twilio.rest import Client as TwilioClient
    _TWILIO = True
except ImportError:
    _TWILIO = False
    logger.info("[WHATSAPP] twilio not installed. Run: pip install twilio")


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WhatsAppMessage:
    to: str
    body: str
    media_url: Optional[str] = None
    direction: str = "outgoing"    # "outgoing" | "incoming"
    status: str = "queued"
    sid: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SendResult:
    success: bool
    to: str
    body: str
    sid: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


# ─────────────────────────────────────────────────────────────────────────────
#  WHATSAPP AGENT
# ─────────────────────────────────────────────────────────────────────────────

class IgrisWhatsAppAgent:
    """
    WhatsApp integration for Igris via Twilio.

    Setup (in .env):
    ────────────────
    TWILIO_ACCOUNT_SID=ACxxxxxx
    TWILIO_AUTH_TOKEN=xxxxxxxx
    TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

    Usage:
    ──────
    result = await agent.send("+923001234567", "Hello from Igris!")
    agent.set_auto_responder(my_callback)  # for webhook processing
    """

    def __init__(self) -> None:
        self._account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self._auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self._from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self._client: Optional[TwilioClient] = None
        self._message_log: List[WhatsAppMessage] = []
        self._auto_responder: Optional[Callable] = None

        if self._account_sid and self._auth_token and _TWILIO:
            try:
                self._client = TwilioClient(self._account_sid, self._auth_token)
                logger.info("[WHATSAPP] Twilio client initialized.")
            except Exception as e:
                logger.error(f"[WHATSAPP] Twilio init failed: {e}")

    @property
    def available(self) -> bool:
        return self._client is not None

    def set_auto_responder(self, callback: Callable) -> None:
        """Set a callback for auto-responding to incoming messages."""
        self._auto_responder = callback

    # ── Send Messages ─────────────────────────────────────────────────────────

    async def send(
        self,
        to: str,
        body: str,
        media_url: Optional[str] = None,
    ) -> SendResult:
        """Send a WhatsApp message."""
        if not self._client:
            return SendResult(
                success=False, to=to, body=body,
                error="WhatsApp not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and pip install twilio.",
            )

        # Normalize phone number
        to_number = to.strip()
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        if not to_number.startswith("whatsapp:+"):
            to_number = to_number.replace("whatsapp:", "whatsapp:+")

        try:
            kwargs = {
                "from_": self._from_number,
                "to": to_number,
                "body": body[:1600],  # WhatsApp limit
            }
            if media_url:
                kwargs["media_url"] = [media_url]

            message = await asyncio.to_thread(
                self._client.messages.create, **kwargs
            )

            msg_record = WhatsAppMessage(
                to=to_number, body=body[:1600],
                media_url=media_url, sid=message.sid,
                status=message.status,
            )
            self._message_log.append(msg_record)

            logger.info(f"[WHATSAPP] Sent to {to_number}: {body[:50]}...")
            return SendResult(
                success=True, to=to_number, body=body[:1600],
                sid=message.sid,
            )

        except Exception as e:
            logger.error(f"[WHATSAPP] Send failed: {e}")
            return SendResult(
                success=False, to=to_number, body=body,
                error=str(e),
            )

    async def send_template(self, to: str, template_name: str, **params) -> SendResult:
        """Send a WhatsApp template message (for business-initiated conversations)."""
        # Build template body
        body = f"[Template: {template_name}]"
        if params:
            body += " " + ", ".join(f"{k}={v}" for k, v in params.items())
        return await self.send(to, body)

    # ── Receive / Webhook Processing ──────────────────────────────────────────

    async def process_incoming(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming WhatsApp message (from Twilio webhook).
        Call this from your webhook endpoint.

        Expected fields: Body, From, To, MessageSid, NumMedia
        """
        body = webhook_data.get("Body", "")
        from_number = webhook_data.get("From", "")
        to_number = webhook_data.get("To", "")
        sid = webhook_data.get("MessageSid", "")

        # Log incoming message
        msg = WhatsAppMessage(
            to=to_number, body=body, direction="incoming",
            status="received", sid=sid,
        )
        self._message_log.append(msg)
        logger.info(f"[WHATSAPP] Received from {from_number}: {body[:50]}")

        # Auto-respond if callback is set
        response_text = ""
        if self._auto_responder:
            try:
                result = self._auto_responder(body, from_number)
                if asyncio.iscoroutine(result):
                    result = await result
                response_text = str(result)
            except Exception as e:
                logger.error(f"[WHATSAPP] Auto-responder error: {e}")
                response_text = "⚡ Igris received your message but encountered an error."
        else:
            # Default: use LLM
            try:
                from app.core.llm_manager import universal_llm
                response_text = await universal_llm.generate_response(
                    system_prompt=(
                        "You are Igris, an AI assistant responding via WhatsApp. "
                        "Be concise (max 1600 chars). Use emojis appropriately."
                    ),
                    user_prompt=body,
                    max_tokens=400,
                )
            except Exception:
                response_text = "⚡ Igris is here. How can I help?"

        # Send reply
        if response_text and from_number:
            await self.send(from_number, response_text)

        return {
            "received": body,
            "from": from_number,
            "response": response_text,
            "sid": sid,
        }

    # ── Bulk Messaging ────────────────────────────────────────────────────────

    async def broadcast(self, numbers: List[str], message: str) -> List[SendResult]:
        """Send the same message to multiple numbers."""
        results = []
        for num in numbers:
            r = await self.send(num, message)
            results.append(r)
            await asyncio.sleep(0.5)  # Rate limiting
        return results

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "twilio_sdk_available": _TWILIO,
            "configured": self.available,
            "from_number": self._from_number if self.available else None,
            "messages_sent": sum(1 for m in self._message_log if m.direction == "outgoing"),
            "messages_received": sum(1 for m in self._message_log if m.direction == "incoming"),
            "auto_responder_set": self._auto_responder is not None,
        }

    def get_message_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self._message_log[-limit:]]


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisWhatsAppAgent] = None


def get_whatsapp_agent() -> IgrisWhatsAppAgent:
    global _instance
    if _instance is None:
        _instance = IgrisWhatsAppAgent()
    return _instance
