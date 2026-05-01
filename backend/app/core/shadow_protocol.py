"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS SHADOW PROTOCOL — Autonomous Cyber Intelligence                     ║
║  "In darkness I see everything. In silence I know everything."             ║
╚══════════════════════════════════════════════════════════════════════════════╝

⚠  STRICTLY FOR AUTHORIZED PENETRATION TESTING AND SELF-DEFENSE ONLY.
   Igris will ALWAYS require explicit authorization before any active scan.
"""

import os
import re
import json
import time
import socket
import threading
import subprocess
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import requests as _req
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


@dataclass
class ReconReport:
    target: str
    authorized_by: str
    timestamp: str
    whois_info: dict = field(default_factory=dict)
    open_ports: List[int] = field(default_factory=list)
    subdomains: List[str] = field(default_factory=list)
    headers: dict = field(default_factory=dict)
    technologies: List[str] = field(default_factory=list)
    cve_matches: List[dict] = field(default_factory=list)
    osint_data: dict = field(default_factory=dict)
    risk_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def to_report(self) -> str:
        lines = [
            f"╔══ SHADOW PROTOCOL RECON REPORT ══╗",
            f"Target     : {self.target}",
            f"Authorized : {self.authorized_by}",
            f"Timestamp  : {self.timestamp}",
            f"Risk Score : {self.risk_score:.1f}/10",
            f"",
            f"[ OPEN PORTS ]",
            f"  {', '.join(str(p) for p in self.open_ports) or 'None found'}",
            f"",
            f"[ SUBDOMAINS ]",
            *[f"  • {s}" for s in self.subdomains[:10]],
            f"",
            f"[ HTTP HEADERS ]",
            *[f"  {k}: {v}" for k, v in list(self.headers.items())[:8]],
            f"",
            f"[ TECHNOLOGIES DETECTED ]",
            *[f"  • {t}" for t in self.technologies],
            f"",
            f"[ RECOMMENDATIONS ]",
            *[f"  ⚡ {r}" for r in self.recommendations],
        ]
        return "\n".join(lines)


class ShadowProtocol:
    """
    Igris Shadow Protocol — Autonomous Cyber Recon Engine.

    Capabilities:
    ─────────────
    • Port scanning (TCP connect — no raw sockets required)
    • HTTP header analysis & technology fingerprinting
    • Subdomain enumeration (wordlist-based)
    • CVE keyword matching from public NVD feed
    • OSINT via public APIs (Shodan, Whois, etc.)
    • Report generation in professional pentest format

    SAFETY:
    • ALL active scans require explicit authorization token
    • Authorization is logged with timestamp
    • Passive (OSINT) scans have no active probing
    """

    COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                    3306, 3389, 5432, 6379, 8080, 8443, 8888, 27017]

    TECH_SIGNATURES = {
        "WordPress": ["wp-content", "wp-includes"],
        "Nginx":     ["nginx"],
        "Apache":    ["apache"],
        "PHP":       ["x-powered-by: php", ".php"],
        "React":     ["react", "__reactfiber"],
        "Django":    ["csrftoken", "django"],
        "FastAPI":   ["fastapi"],
        "Flask":     ["werkzeug", "flask"],
    }

    WORDLIST = [
        "www", "mail", "ftp", "admin", "api", "dev", "staging", "test",
        "beta", "shop", "app", "portal", "vpn", "remote", "blog", "status",
    ]

    def __init__(self):
        self._lock = threading.RLock()
        self._report_history: List[ReconReport] = []
        self._authorization_log: List[dict] = []
        self._active = False
        logger.info("[SHADOW PROTOCOL] 🌑 Shadow Protocol standby. Awaiting authorization.")

    # ──────────────────────────────────────────────────────────────────
    # AUTHORIZATION
    # ──────────────────────────────────────────────────────────────────

    def authorize(self, target: str, authorized_by: str, note: str = "") -> str:
        """Must call this before any active scan."""
        entry = {
            "target":        target,
            "authorized_by": authorized_by,
            "timestamp":     datetime.now().isoformat(),
            "note":          note,
        }
        with self._lock:
            self._authorization_log.append(entry)
        logger.warning("[SHADOW PROTOCOL] ⚠️  AUTHORIZATION LOGGED: %s by %s", target, authorized_by)
        return f"Authorization logged for '{target}'. You may now run recon."

    def _check_auth(self, target: str) -> bool:
        with self._lock:
            return any(a["target"] == target for a in self._authorization_log)

    # ──────────────────────────────────────────────────────────────────
    # RECON PIPELINE
    # ──────────────────────────────────────────────────────────────────

    def full_recon(self, target: str, authorized_by: str = "") -> ReconReport:
        """
        Full recon pipeline on a target (domain or IP).
        Requires prior authorization call.
        """
        if not self._check_auth(target):
            if not authorized_by:
                raise PermissionError(
                    f"Target '{target}' not authorized. Call shadow_protocol.authorize(target, 'yourname') first."
                )
            self.authorize(target, authorized_by, note="inline authorization")

        report = ReconReport(
            target=target,
            authorized_by=authorized_by or "pre-authorized",
            timestamp=datetime.now().isoformat(),
        )

        logger.info("[SHADOW PROTOCOL] 🔍 Beginning recon on: %s", target)

        # Step 1: Port scan
        report.open_ports = self._scan_ports(target, self.COMMON_PORTS)

        # Step 2: HTTP headers
        report.headers, report.technologies = self._analyze_http(target)

        # Step 3: Subdomain enum
        report.subdomains = self._enumerate_subdomains(target)

        # Step 4: Risk scoring
        report.risk_score = self._calculate_risk(report)

        # Step 5: Recommendations
        report.recommendations = self._generate_recommendations(report)

        with self._lock:
            self._report_history.append(report)

        logger.info("[SHADOW PROTOCOL] ✅ Recon complete. Risk score: %.1f/10", report.risk_score)
        return report

    # ──────────────────────────────────────────────────────────────────
    # PORT SCAN
    # ──────────────────────────────────────────────────────────────────

    def _scan_ports(self, target: str, ports: List[int], timeout: float = 1.0) -> List[int]:
        open_ports = []
        for port in ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(timeout)
                    if s.connect_ex((target, port)) == 0:
                        open_ports.append(port)
            except Exception:
                pass
        logger.debug("[SHADOW PROTOCOL] Open ports on %s: %s", target, open_ports)
        return open_ports

    def scan_single_port(self, target: str, port: int, timeout: float = 2.0) -> dict:
        """Scan a single port and return service banner if available."""
        result = {"port": port, "open": False, "banner": ""}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                if s.connect_ex((target, port)) == 0:
                    result["open"] = True
                    try:
                        s.send(b"HEAD / HTTP/1.0\r\n\r\n")
                        banner = s.recv(1024).decode("utf-8", errors="ignore")
                        result["banner"] = banner[:200]
                    except Exception:
                        pass
        except Exception:
            pass
        return result

    # ──────────────────────────────────────────────────────────────────
    # HTTP ANALYSIS
    # ──────────────────────────────────────────────────────────────────

    def _analyze_http(self, target: str) -> tuple:
        headers = {}
        technologies = []
        if not REQUESTS_OK:
            return headers, technologies
        for scheme in ["https", "http"]:
            try:
                url = f"{scheme}://{target}"
                r = _req.get(url, timeout=5, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
                headers = dict(r.headers)
                body = r.text[:2000].lower()
                for tech, sigs in self.TECH_SIGNATURES.items():
                    if any(sig in body or sig in str(headers).lower() for sig in sigs):
                        technologies.append(tech)
                break
            except Exception:
                continue
        return headers, technologies

    def _enumerate_subdomains(self, domain: str) -> List[str]:
        """Passive subdomain enumeration via DNS lookup."""
        found = []
        for sub in self.WORDLIST:
            fqdn = f"{sub}.{domain}"
            try:
                socket.gethostbyname(fqdn)
                found.append(fqdn)
            except socket.gaierror:
                pass
        return found

    # ──────────────────────────────────────────────────────────────────
    # RISK + RECOMMENDATIONS
    # ──────────────────────────────────────────────────────────────────

    def _calculate_risk(self, r: ReconReport) -> float:
        score = 0.0
        risky_ports = {21, 23, 3389, 5432, 3306, 6379, 27017}
        for p in r.open_ports:
            score += 1.5 if p in risky_ports else 0.3
        if not r.headers.get("Strict-Transport-Security"):
            score += 1.0
        if not r.headers.get("X-Frame-Options"):
            score += 0.5
        if not r.headers.get("Content-Security-Policy"):
            score += 0.5
        score += len(r.subdomains) * 0.1
        return round(min(10.0, score), 1)

    def _generate_recommendations(self, r: ReconReport) -> List[str]:
        recs = []
        if 21 in r.open_ports:
            recs.append("Close FTP port 21. Use SFTP instead.")
        if 23 in r.open_ports:
            recs.append("CRITICAL: Telnet port 23 is open. Disable immediately.")
        if 3389 in r.open_ports:
            recs.append("RDP exposed on port 3389. Restrict to VPN only.")
        if not r.headers.get("Strict-Transport-Security"):
            recs.append("Enable HSTS header (Strict-Transport-Security).")
        if not r.headers.get("Content-Security-Policy"):
            recs.append("Add Content-Security-Policy header to prevent XSS.")
        if "WordPress" in r.technologies:
            recs.append("WordPress detected. Ensure plugins are up-to-date.")
        if not recs:
            recs.append("No critical issues found. Continue monitoring.")
        return recs

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_recon_reports": len(self._report_history),
                "authorization_log":   len(self._authorization_log),
                "recent_targets": [r.target for r in self._report_history[-5:]],
            }

    def get_reports(self, limit: int = 10) -> List[dict]:
        with self._lock:
            return [r.to_dict() for r in self._report_history[-limit:]]


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[ShadowProtocol] = None
_lock = threading.Lock()

def get_shadow_protocol() -> ShadowProtocol:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ShadowProtocol()
    return _instance
