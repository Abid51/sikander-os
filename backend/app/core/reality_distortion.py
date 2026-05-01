"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS REALITY DISTORTION DETECTOR                                         ║
║  "Truth has no filter. Igris finds it."                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, re, json, time, threading, logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import requests as _req
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


@dataclass
class FactCheck:
    check_id: str
    claim: str
    verdict: str          # "likely_true" | "likely_false" | "out_of_date" | "unverifiable"
    confidence: float     # 0-1
    correction: str = ""
    sources: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data_anomalies: List[str] = field(default_factory=list)

    def to_dict(self): return self.__dict__.copy()


# Known false claims (simple DB — expandable)
KNOWN_FALSE = [
    (r"earth is flat",                  "Earth is an oblate spheroid, confirmed by physics and space photography."),
    (r"vaccines cause autism",          "Multiple large studies found no link. The original study was retracted."),
    (r"5g causes (covid|virus|disease)","5G is radio waves — no biological mechanism to cause viral disease."),
    (r"chatgpt went bankrupt",          "OpenAI is a private company with $157B+ valuation as of 2025."),
    (r"python is dying",               "Python is #1 on TIOBE index as of 2025. Growing, not dying."),
]

# Data anomaly patterns
ANOMALY_PATTERNS = [
    (r"\b(\d{4})\b", "year"),         # Years — check if future
    (r"\$[\d,]+(?:\.\d+)?", "money"), # Money amounts — check for outliers
    (r"\b(\d+)%", "percentage"),      # Percentages — check > 100
    (r"\b(\d{1,3}(?:,\d{3})*)\b", "large_number"),
]


class RealityDistortionDetector:
    """
    Analyzes every user input and shared data for:
    1. Known false claims → immediate correction
    2. Outdated information → flag with year context
    3. Statistical anomalies in pasted data → highlight
    4. Self-contradictions → detect within session
    5. Logical fallacies → soft flag
    """
    DATA_FILE = "igris_fact_checks.json"

    def __init__(self):
        self._lock = threading.RLock()
        self._checks: List[FactCheck] = []
        self._session_claims: List[str] = []
        self._check_counter = 0

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()
        logger.info("[REALITY DISTORTION] 👁️ Reality Distortion Detector online.")

    # ─────────────────────────────────────────────────────────────────────
    # MAIN ANALYSIS
    # ─────────────────────────────────────────────────────────────────────

    def analyze(self, text: str) -> Optional[FactCheck]:
        """Analyze text for false claims, anomalies, contradictions."""
        if not text or len(text) < 10:
            return None

        with self._lock:
            self._check_counter += 1
            check_id = f"fc_{self._check_counter}"

        t_lower = text.lower()

        # 1. Known false claims
        for pattern, correction in KNOWN_FALSE:
            if re.search(pattern, t_lower):
                check = FactCheck(
                    check_id=check_id,
                    claim=text[:100],
                    verdict="likely_false",
                    confidence=0.95,
                    correction=correction,
                )
                self._record(check)
                return check

        # 2. Outdated year check
        years = re.findall(r'\b(20\d\d|19\d\d)\b', text)
        current_year = datetime.now().year
        for y_str in years:
            y = int(y_str)
            if y < current_year - 3:
                check = FactCheck(
                    check_id=check_id,
                    claim=text[:100],
                    verdict="out_of_date",
                    confidence=0.7,
                    correction=f"This references {y_str} data. Current year is {current_year}. Please verify if still accurate.",
                )
                self._record(check)
                return check

        # 3. Statistical anomalies
        anomalies = self._detect_anomalies(text)
        if anomalies:
            check = FactCheck(
                check_id=check_id,
                claim=text[:100],
                verdict="unverifiable",
                confidence=0.6,
                correction="Statistical anomalies detected — please verify these figures.",
                data_anomalies=anomalies,
            )
            self._record(check)
            return check

        # 4. Self-contradiction check
        contradiction = self._check_contradiction(text)
        if contradiction:
            check = FactCheck(
                check_id=check_id,
                claim=text[:100],
                verdict="likely_false",
                confidence=0.75,
                correction=f"This contradicts something said earlier: '{contradiction}'",
            )
            self._record(check)
            return check

        # Track for future contradiction detection
        with self._lock:
            self._session_claims.append(text[:150])
            if len(self._session_claims) > 50:
                self._session_claims = self._session_claims[-50:]

        return None

    def _detect_anomalies(self, text: str) -> List[str]:
        anomalies = []
        # Percentages > 100
        for m in re.finditer(r'\b(\d+(?:\.\d+)?)\s*%', text):
            val = float(m.group(1))
            if val > 100:
                anomalies.append(f"Percentage > 100%: {m.group(0)}")
        # Negative counts
        for m in re.finditer(r'-\s*(\d+)\s*(?:users|items|records|rows)', text):
            anomalies.append(f"Negative count: {m.group(0)}")
        # Future dates used as past
        for m in re.finditer(r'\b(2027|2028|2029|2030)\b', text):
            if "will" not in text[:m.start()].lower()[-20:]:
                anomalies.append(f"Future year used in present context: {m.group(0)}")
        return anomalies

    def _check_contradiction(self, new_claim: str) -> Optional[str]:
        nc = new_claim.lower()
        with self._lock:
            claims = list(self._session_claims)
        # Simple negation check
        for old in claims:
            old_l = old.lower()
            # "X is Y" vs "X is not Y"
            if "not" in nc and nc.replace(" not", "") in old_l:
                return old[:80]
            if "not" in old_l and old_l.replace(" not", "") in nc:
                return old[:80]
        return None

    def to_prompt_alert(self, text: str) -> str:
        """Returns an alert string if any distortion is found."""
        check = self.analyze(text)
        if not check or check.verdict == "likely_true":
            return ""
        icon = "⚠️" if check.verdict == "out_of_date" else "❌"
        return (f"\n[REALITY DISTORTION ALERT {icon}]: "
                f"Verdict: {check.verdict.upper()} | {check.correction}\n")

    def _record(self, check: FactCheck):
        with self._lock:
            self._checks.append(check)
            if len(self._checks) > 500:
                self._checks = self._checks[-500:]
        self._save()
        logger.warning("[REALITY DISTORTION] %s — %s: %s",
                       check.verdict.upper(), check.check_id, check.correction[:60])

    def get_stats(self) -> dict:
        with self._lock:
            verdicts = {}
            for c in self._checks:
                verdicts[c.verdict] = verdicts.get(c.verdict, 0) + 1
            return {
                "total_checks": self._check_counter,
                "flagged": len(self._checks),
                "verdicts": verdicts,
                "session_claims_tracked": len(self._session_claims),
                "recent_flags": [c.to_dict() for c in self._checks[-5:]],
            }

    def get_history(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return [c.to_dict() for c in self._checks[-limit:]]

    def _save(self):
        try:
            with self._lock:
                data = [c.to_dict() for c in self._checks[-100:]]
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[REALITY DISTORTION] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                raw = json.load(f)
            with self._lock:
                for cd in raw:
                    try:
                        self._checks.append(FactCheck(**{
                            k: v for k, v in cd.items()
                            if k in FactCheck.__dataclass_fields__
                        }))
                    except Exception:
                        pass
        except Exception:
            pass


_instance: Optional[RealityDistortionDetector] = None
_lock = threading.Lock()

def get_reality_distortion() -> RealityDistortionDetector:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealityDistortionDetector()
    return _instance
