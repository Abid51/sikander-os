"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS EMAIL AGENT
  Send, read, draft, organize emails via SMTP/IMAP
  Supports: Gmail, Outlook, any SMTP server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import email
import email.header
import imaplib
import logging
import os
import smtplib
import time
from dataclasses import dataclass, field, asdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EmailConfig:
    email_address: str
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    password: str            # App password (not account password)
    use_tls: bool = True

    @classmethod
    def gmail(cls, email_address: str, app_password: str) -> "EmailConfig":
        return cls(
            email_address=email_address,
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            imap_host="imap.gmail.com",
            imap_port=993,
            password=app_password,
        )

    @classmethod
    def outlook(cls, email_address: str, app_password: str) -> "EmailConfig":
        return cls(
            email_address=email_address,
            smtp_host="smtp.office365.com",
            smtp_port=587,
            imap_host="outlook.office365.com",
            imap_port=993,
            password=app_password,
        )

    @classmethod
    def from_env(cls) -> Optional["EmailConfig"]:
        """Load config from environment variables."""
        addr = os.getenv("EMAIL_ADDRESS", "")
        pwd = os.getenv("EMAIL_APP_PASSWORD", "")
        if not addr or not pwd:
            return None
        provider = os.getenv("EMAIL_PROVIDER", "gmail").lower()
        if provider == "gmail":
            return cls.gmail(addr, pwd)
        elif provider == "outlook":
            return cls.outlook(addr, pwd)
        else:
            return cls(
                email_address=addr,
                smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
                smtp_port=int(os.getenv("SMTP_PORT", "587")),
                imap_host=os.getenv("IMAP_HOST", "imap.gmail.com"),
                imap_port=int(os.getenv("IMAP_PORT", "993")),
                password=pwd,
            )


@dataclass
class EmailMessage:
    subject: str
    sender: str
    recipients: List[str]
    body: str
    html_body: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    uid: Optional[str] = None
    read: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SendResult:
    success: bool
    to: List[str]
    subject: str
    message_id: Optional[str]
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


# ─────────────────────────────────────────────────────────────────────────────
#  EMAIL AGENT
# ─────────────────────────────────────────────────────────────────────────────

class IgrisEmailAgent:
    """
    Email agent for Igris — real SMTP/IMAP operations.

    Setup (in .env):
    ────────────────
    EMAIL_ADDRESS=your@gmail.com
    EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx  (Gmail App Password)
    EMAIL_PROVIDER=gmail

    Usage:
    ──────
    await agent.send("to@email.com", "Subject", "Body text")
    emails = await agent.read_inbox(limit=10)
    draft = await agent.ai_draft("Write apology email to client about delay")
    """

    def __init__(self, config: Optional[EmailConfig] = None) -> None:
        self._config = config or EmailConfig.from_env()
        self._sent_log: List[SendResult] = []
        if self._config:
            logger.info(f"[EMAIL] Agent configured for: {self._config.email_address}")
        else:
            logger.warning("[EMAIL] No email config found. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env")

    @property
    def available(self) -> bool:
        return self._config is not None

    # ── SMTP (Send) ───────────────────────────────────────────────────────────

    async def send(
        self,
        to: str | List[str],
        subject: str,
        body: str,
        html: Optional[str] = None,
        cc: Optional[List[str]] = None,
    ) -> SendResult:
        """Send an email."""
        if not self._config:
            return SendResult(success=False, to=[], subject=subject, message_id=None,
                              error="Email not configured. Add EMAIL_ADDRESS and EMAIL_APP_PASSWORD to .env")

        recipients = [to] if isinstance(to, str) else to
        result = await asyncio.to_thread(self._send_sync, recipients, subject, body, html, cc or [])
        self._sent_log.append(result)
        return result

    def _send_sync(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html: Optional[str],
        cc: List[str],
    ) -> SendResult:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._config.email_address
            msg["To"] = ", ".join(recipients)
            if cc:
                msg["Cc"] = ", ".join(cc)

            msg.attach(MIMEText(body, "plain", "utf-8"))
            if html:
                msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port, timeout=30) as server:
                if self._config.use_tls:
                    server.starttls()
                server.login(self._config.email_address, self._config.password)
                all_recipients = recipients + cc
                server.sendmail(self._config.email_address, all_recipients, msg.as_string())

            logger.info(f"[EMAIL] ✉️  Sent to {recipients}: {subject}")
            return SendResult(
                success=True, to=recipients, subject=subject,
                message_id=msg.get("Message-ID"),
            )
        except Exception as e:
            logger.error(f"[EMAIL] Send failed: {e}")
            return SendResult(success=False, to=recipients, subject=subject,
                              message_id=None, error=str(e))

    # ── IMAP (Read) ───────────────────────────────────────────────────────────

    async def read_inbox(
        self,
        limit: int = 10,
        folder: str = "INBOX",
        unread_only: bool = False,
    ) -> List[EmailMessage]:
        """Read emails from inbox."""
        if not self._config:
            return []
        return await asyncio.to_thread(self._read_sync, limit, folder, unread_only)

    def _read_sync(self, limit: int, folder: str, unread_only: bool) -> List[EmailMessage]:
        messages = []
        try:
            imap = imaplib.IMAP4_SSL(self._config.imap_host, self._config.imap_port)
            imap.login(self._config.email_address, self._config.password)
            imap.select(folder)

            search_criteria = "UNSEEN" if unread_only else "ALL"
            _, msg_ids = imap.search(None, search_criteria)
            msg_id_list = msg_ids[0].split()
            recent_ids = msg_id_list[-limit:] if msg_id_list else []

            for uid in reversed(recent_ids):
                try:
                    _, msg_data = imap.fetch(uid, "(RFC822)")
                    raw = msg_data[0][1]
                    parsed = email.message_from_bytes(raw)

                    # Decode subject
                    subj_parts = email.header.decode_header(parsed.get("Subject", ""))
                    subject = ""
                    for part, encoding in subj_parts:
                        if isinstance(part, bytes):
                            subject += part.decode(encoding or "utf-8", errors="replace")
                        else:
                            subject += part

                    # Get body
                    body = ""
                    if parsed.is_multipart():
                        for p in parsed.walk():
                            if p.get_content_type() == "text/plain":
                                body = p.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]
                                break
                    else:
                        body = parsed.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]

                    messages.append(EmailMessage(
                        subject=subject.strip(),
                        sender=parsed.get("From", ""),
                        recipients=[parsed.get("To", "")],
                        body=body.strip(),
                        uid=uid.decode(),
                        read=False,
                    ))
                except Exception as e:
                    logger.warning(f"[EMAIL] Could not parse message {uid}: {e}")

            imap.logout()
        except Exception as e:
            logger.error(f"[EMAIL] IMAP error: {e}")
        return messages

    # ── AI-Powered Email Drafting ─────────────────────────────────────────────

    async def ai_draft(
        self,
        instruction: str,
        context: Optional[str] = None,
        tone: str = "professional",
    ) -> str:
        """Use LLM to draft an email from natural language instruction."""
        try:
            from app.core.llm_manager import universal_llm
            prompt = f"Write a {tone} email. Instruction: {instruction}"
            if context:
                prompt += f"\n\nContext: {context}"
            draft = await universal_llm.generate_response(
                system_prompt=(
                    "You are an expert email writer for Igris AI. "
                    "Write clear, professional emails. "
                    "Format: Subject: <subject>\n\n<body>"
                ),
                user_prompt=prompt,
                max_tokens=500,
            )
            return draft.strip()
        except Exception as e:
            return f"Draft failed: {e}"

    async def ai_reply(self, original_email: EmailMessage, instruction: str) -> str:
        """Draft a reply to an email."""
        context = f"Original email from {original_email.sender}:\nSubject: {original_email.subject}\n{original_email.body[:500]}"
        return await self.ai_draft(instruction, context=context)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": bool(self._config),
            "email_address": self._config.email_address if self._config else None,
            "provider": self._config.smtp_host if self._config else None,
            "emails_sent": len(self._sent_log),
            "recent_sent": [
                {"to": r.to, "subject": r.subject, "success": r.success}
                for r in self._sent_log[-5:]
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisEmailAgent] = None


def get_email_agent() -> IgrisEmailAgent:
    global _instance
    if _instance is None:
        _instance = IgrisEmailAgent()
    return _instance
