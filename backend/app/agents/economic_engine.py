"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS ECONOMIC ENGINE — Autonomous Income Intelligence                    ║
║  "While you sleep, I grow your wealth."                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import threading
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)

try:
    import requests as _req
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import ccxt
    CCXT_OK = True
except ImportError:
    CCXT_OK = False
    logger.info("[ECONOMIC ENGINE] ccxt not installed. Trading disabled. Run: pip install ccxt")


@dataclass
class TradeRecord:
    trade_id: str
    symbol: str
    side: str               # buy | sell
    amount: float
    price: float
    pnl: float
    strategy: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "executed"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class IncomeStream:
    name: str
    stream_type: str        # crypto | content | freelance | defi
    active: bool = False
    total_earned: float = 0.0
    last_run: Optional[str] = None
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RevenueRecord:
    record_id: str
    stream_name: str
    stream_type: str
    amount_usd: float
    source: str = ""
    notes: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class EconomicEngine:
    """
    Igris Autonomous Economic Intelligence Engine.

    Income Streams:
    ───────────────
    1. Crypto Price Monitoring  → RSI + momentum signals (paper/live)
    2. Arbitrage Scanner        → Detect price differences across exchanges
    3. DeFi Yield Tracker       → Monitor best APY rates
    4. Market Sentiment         → Fear & Greed index + social signals
    5. Revenue Dashboard        → Track all earnings in one place

    Safety:
    • Paper trading by default (LIVE_MODE=False)
    • Risk limits enforced (max_trade_pct of portfolio)
    • All trades logged with full audit trail
    """

    DATA_FILE = "igris_economy.json"

    def __init__(self, live_mode: bool = False):
        self.live_mode = live_mode
        self._lock = threading.RLock()
        self._trade_history: deque = deque(maxlen=1000)
        self._portfolio: Dict[str, float] = {"USD": 1000.0}  # Paper portfolio
        self._income_streams: Dict[str, IncomeStream] = {}
        self._revenue_history: deque = deque(maxlen=2000)
        self._price_cache: Dict[str, List[float]] = {}       # symbol → recent prices
        self._total_pnl: float = 0.0
        self._max_trade_pct: float = 0.05                    # Max 5% of portfolio per trade

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base_dir, "..", "..", self.DATA_FILE))
        self._load()
        self._register_default_streams()

        threading.Thread(target=self._market_monitor_loop, daemon=True).start()
        logger.info("[ECONOMIC ENGINE] 💹 Economic Intelligence active. Mode: %s",
                    "LIVE" if live_mode else "PAPER")

    # ──────────────────────────────────────────────────────────────────
    # STREAM REGISTRATION
    # ──────────────────────────────────────────────────────────────────

    def _register_default_streams(self):
        streams = [
            IncomeStream("Crypto Momentum", "crypto",    False, config={"symbols": ["BTC/USDT", "ETH/USDT"]}),
            IncomeStream("Arbitrage Scanner", "crypto",  False, config={"min_spread_pct": 0.5}),
            IncomeStream("DeFi Yield Tracker", "defi",  False, config={"min_apy": 5.0}),
            IncomeStream("Market Sentiment", "data",     True,  config={"interval_min": 60}),
            IncomeStream("Social Media Creator", "social_media", False, config={"platforms": ["YouTube", "TikTok", "Instagram"]}),
            IncomeStream("Freelance Services", "freelance", False, config={"platforms": ["Upwork", "Fiverr"], "hourly_rate_usd": 25}),
            IncomeStream("Affiliate Marketing", "affiliate", False, config={"channels": ["blog", "social"], "default_commission_pct": 10}),
            IncomeStream("Digital Products", "content", False, config={"channels": ["gumroad", "etsy"]}),
        ]
        for s in streams:
            if s.name not in self._income_streams:
                self._income_streams[s.name] = s

    def activate_stream(self, name: str) -> str:
        with self._lock:
            if name in self._income_streams:
                self._income_streams[name].active = True
                self._save()
                return f"Stream '{name}' activated."
        return f"Stream '{name}' not found."

    def deactivate_stream(self, name: str) -> str:
        with self._lock:
            if name in self._income_streams:
                self._income_streams[name].active = False
                self._save()
                return f"Stream '{name}' deactivated."
        return f"Stream '{name}' not found."

    def list_streams(self) -> Dict[str, dict]:
        """Return current income stream states for dashboards/APIs."""
        with self._lock:
            return {name: stream.to_dict() for name, stream in self._income_streams.items()}

    def record_income(
        self,
        stream_name: str,
        amount_usd: float,
        source: str = "",
        notes: str = "",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Record non-trading income (social, freelance, affiliate, etc.)."""
        stream_name = str(stream_name or "").strip()
        if not stream_name:
            return {"error": "stream_name is required"}
        if amount_usd <= 0:
            return {"error": "amount_usd must be greater than zero."}
        metadata = metadata or {}

        with self._lock:
            stream = self._income_streams.get(stream_name)
            if not stream:
                return {"error": f"Stream '{stream_name}' not found."}

            stream.total_earned = round(float(stream.total_earned) + float(amount_usd), 2)
            stream.last_run = datetime.now().isoformat()

            rec = RevenueRecord(
                record_id=f"R{int(time.time() * 1000) % 99999999}",
                stream_name=stream.name,
                stream_type=stream.stream_type,
                amount_usd=round(float(amount_usd), 2),
                source=str(source or ""),
                notes=str(notes or ""),
                metadata=metadata,
            )
            self._revenue_history.append(rec)
            self._portfolio["USD"] = round(self._portfolio.get("USD", 0.0) + rec.amount_usd, 2)
            self._save()

        return {"status": "recorded", "record": rec.to_dict(), "usd_balance": self._portfolio.get("USD", 0.0)}

    def get_income_history(self, limit: int = 20, stream_name: Optional[str] = None) -> List[dict]:
        with self._lock:
            records = list(self._revenue_history)
            if stream_name:
                name = stream_name.strip().lower()
                records = [r for r in records if r.stream_name.lower() == name]
            return [r.to_dict() for r in records[-max(1, limit):]]

    def get_income_summary(self) -> dict:
        with self._lock:
            by_stream: Dict[str, float] = {}
            by_type: Dict[str, float] = {}
            total = 0.0
            for rec in self._revenue_history:
                total += rec.amount_usd
                by_stream[rec.stream_name] = round(by_stream.get(rec.stream_name, 0.0) + rec.amount_usd, 2)
                by_type[rec.stream_type] = round(by_type.get(rec.stream_type, 0.0) + rec.amount_usd, 2)
            return {
                "total_income_usd": round(total, 2),
                "records_count": len(self._revenue_history),
                "by_stream": by_stream,
                "by_type": by_type,
            }

    # ──────────────────────────────────────────────────────────────────
    # MARKET DATA
    # ──────────────────────────────────────────────────────────────────

    def fetch_crypto_price(self, symbol: str = "BTC/USDT") -> Optional[float]:
        """Fetch price from CoinGecko public API (no key required)."""
        if not REQUESTS_OK:
            return None
        try:
            coin_map = {
                "BTC/USDT": "bitcoin", "ETH/USDT": "ethereum",
                "SOL/USDT": "solana",  "BNB/USDT": "binancecoin",
            }
            coin_id = coin_map.get(symbol, symbol.split("/")[0].lower())
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            r = _req.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                price = data.get(coin_id, {}).get("usd")
                if price:
                    with self._lock:
                        if symbol not in self._price_cache:
                            self._price_cache[symbol] = []
                        self._price_cache[symbol].append(float(price))
                        if len(self._price_cache[symbol]) > 200:
                            self._price_cache[symbol] = self._price_cache[symbol][-200:]
                    return float(price)
        except Exception as e:
            logger.debug("[ECONOMIC ENGINE] Price fetch error: %s", e)
        return None

    def get_fear_greed_index(self) -> Optional[dict]:
        """Fetch Crypto Fear & Greed Index."""
        if not REQUESTS_OK:
            return None
        try:
            r = _req.get("https://api.alternative.me/fng/?limit=1", timeout=8)
            if r.status_code == 200:
                data = r.json()["data"][0]
                return {"value": int(data["value"]), "classification": data["value_classification"]}
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────────────────────────
    # TECHNICAL ANALYSIS
    # ──────────────────────────────────────────────────────────────────

    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """RSI calculation — no external deps."""
        if len(prices) < period + 1:
            return None
        gains, losses = [], []
        for i in range(1, period + 1):
            diff = prices[-i] - prices[-(i + 1)]
            (gains if diff > 0 else losses).append(abs(diff))
        avg_gain = sum(gains) / period if gains else 0.0
        avg_loss = sum(losses) / period if losses else 0.0001
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    def generate_signal(self, symbol: str) -> dict:
        """Generate a buy/sell/hold signal using RSI + momentum."""
        with self._lock:
            prices = list(self._price_cache.get(symbol, []))

        if len(prices) < 5:
            return {"symbol": symbol, "signal": "NO_DATA", "reason": "Insufficient price history"}

        rsi   = self.calculate_rsi(prices)
        price = prices[-1]
        short_ma = sum(prices[-3:]) / 3
        long_ma  = sum(prices[-10:]) / min(10, len(prices))
        momentum = (short_ma - long_ma) / long_ma * 100

        signal = "HOLD"
        reason = ""
        confidence = 0.5

        if rsi and rsi < 30 and momentum > -2:
            signal = "BUY"
            reason = f"RSI oversold ({rsi:.1f}) + stabilizing momentum ({momentum:+.2f}%)"
            confidence = 0.7
        elif rsi and rsi > 70 and momentum < 2:
            signal = "SELL"
            reason = f"RSI overbought ({rsi:.1f}) + weakening momentum ({momentum:+.2f}%)"
            confidence = 0.7
        elif momentum > 3:
            signal = "BUY"
            reason = f"Strong bullish momentum ({momentum:+.2f}%)"
            confidence = 0.55
        elif momentum < -3:
            signal = "SELL"
            reason = f"Strong bearish momentum ({momentum:+.2f}%)"
            confidence = 0.55
        else:
            rsi_display = f"{rsi:.1f}" if rsi is not None else "N/A"
            reason = f"RSI={rsi_display}, Momentum={momentum:+.2f}%"

        return {
            "symbol": symbol, "signal": signal, "price": price,
            "rsi": rsi, "momentum": round(momentum, 2),
            "reason": reason, "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        }

    # ──────────────────────────────────────────────────────────────────
    # PAPER TRADING
    # ──────────────────────────────────────────────────────────────────

    def paper_trade(self, symbol: str, side: str, amount_usd: float) -> dict:
        """Execute a paper trade."""
        side = str(side or "").strip().lower()
        symbol = str(symbol or "").strip().upper().replace("-", "/")
        if side not in {"buy", "sell"}:
            return {"error": "Invalid side. Use 'buy' or 'sell'."}
        if amount_usd <= 0:
            return {"error": "amount_usd must be greater than zero."}
        if "/" not in symbol:
            return {"error": "Invalid symbol format. Use e.g. BTC/USDT."}

        with self._lock:
            prices = self._price_cache.get(symbol, [])
        if not prices:
            return {"error": "No price data for " + symbol}

        price       = prices[-1]
        max_trade   = self._portfolio.get("USD", 0) * self._max_trade_pct
        trade_usd   = min(amount_usd, max_trade)
        base_asset  = symbol.split("/")[0]
        units       = trade_usd / price

        with self._lock:
            if side == "buy":
                if self._portfolio.get("USD", 0) < trade_usd:
                    return {"error": "Insufficient paper USD balance"}
                self._portfolio["USD"] = self._portfolio.get("USD", 0) - trade_usd
                self._portfolio[base_asset] = self._portfolio.get(base_asset, 0) + units
            elif side == "sell":
                if self._portfolio.get(base_asset, 0) < units:
                    return {"error": f"Insufficient {base_asset} balance"}
                self._portfolio["USD"] = self._portfolio.get("USD", 0) + trade_usd
                self._portfolio[base_asset] = max(0.0, self._portfolio.get(base_asset, 0) - units)

            record = TradeRecord(
                trade_id=f"P{int(time.time()*1000) % 999999}",
                symbol=symbol, side=side, amount=units,
                price=price, pnl=0.0, strategy="manual",
            )
            self._trade_history.append(record)
            self._save()

        return {
            "trade_id": record.trade_id,
            "symbol": symbol, "side": side,
            "units": round(units, 6), "price": price,
            "cost_usd": round(trade_usd, 2),
            "portfolio": dict(self._portfolio),
        }

    def get_portfolio_value(self) -> dict:
        """Calculate total portfolio value in USD."""
        with self._lock:
            total = self._portfolio.get("USD", 0.0)
            details = {"USD": total}
            for asset, qty in self._portfolio.items():
                if asset == "USD" or qty <= 0:
                    continue
                sym = f"{asset}/USDT"
                prices = self._price_cache.get(sym, [])
                if prices:
                    val = qty * prices[-1]
                    details[asset] = {"qty": qty, "price": prices[-1], "value_usd": round(val, 2)}
                    total += val
            return {"total_usd": round(total, 2), "breakdown": details}

    # ──────────────────────────────────────────────────────────────────
    # BACKGROUND MONITOR
    # ──────────────────────────────────────────────────────────────────

    def _market_monitor_loop(self):
        symbols = ["BTC/USDT", "ETH/USDT"]
        while True:
            try:
                for sym in symbols:
                    self.fetch_crypto_price(sym)

                with self._lock:
                    active_streams = [s for s in self._income_streams.values()
                                      if s.active and s.stream_type == "crypto"]

                for stream in active_streams:
                    for sym in stream.config.get("symbols", symbols):
                        sig = self.generate_signal(sym)
                        if sig["signal"] in ("BUY", "SELL") and sig["confidence"] >= 0.65:
                            logger.info("[ECONOMIC ENGINE] 📊 Signal: %s %s — %s (conf=%.0f%%)",
                                        sig["signal"], sym, sig["reason"], sig["confidence"] * 100)

                # Fear & Greed
                fg = self.get_fear_greed_index()
                if fg:
                    logger.debug("[ECONOMIC ENGINE] 😱 Fear & Greed: %s (%d)", fg["classification"], fg["value"])

            except Exception as e:
                logger.debug("[ECONOMIC ENGINE] Monitor error: %s", e)
            time.sleep(300)   # 5-min update cycle

    # ──────────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ──────────────────────────────────────────────────────────────────

    def _save(self):
        try:
            data = {
                "portfolio":     self._portfolio,
                "total_pnl":     self._total_pnl,
                "income_streams": {k: v.to_dict() for k, v in self._income_streams.items()},
                "income_history": [r.to_dict() for r in self._revenue_history],
                "trade_count":   len(self._trade_history),
            }
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[ECONOMIC ENGINE] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file) as f:
                data = json.load(f)
            self._portfolio  = data.get("portfolio", {"USD": 1000.0})
            self._total_pnl  = data.get("total_pnl", 0.0)
            raw_streams = data.get("income_streams", {})
            if raw_streams:
                self._income_streams = {
                    name: IncomeStream(
                        name=payload.get("name", name),
                        stream_type=payload.get("stream_type", "other"),
                        active=bool(payload.get("active", False)),
                        total_earned=float(payload.get("total_earned", 0.0)),
                        last_run=payload.get("last_run"),
                        config=payload.get("config", {}),
                    )
                    for name, payload in raw_streams.items()
                }
            raw_income = data.get("income_history", [])
            if raw_income:
                self._revenue_history = deque(
                    (
                        RevenueRecord(
                            record_id=str(row.get("record_id", f"R{idx}")),
                            stream_name=str(row.get("stream_name", "unknown")),
                            stream_type=str(row.get("stream_type", "other")),
                            amount_usd=float(row.get("amount_usd", 0.0)),
                            source=str(row.get("source", "")),
                            notes=str(row.get("notes", "")),
                            metadata=row.get("metadata", {}) or {},
                            timestamp=str(row.get("timestamp", datetime.now().isoformat())),
                        )
                        for idx, row in enumerate(raw_income)
                    ),
                    maxlen=2000,
                )
        except Exception as e:
            logger.debug("[ECONOMIC ENGINE] Load error: %s", e)

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        portfolio_val = self.get_portfolio_value()
        signals = {}
        for sym in ["BTC/USDT", "ETH/USDT"]:
            with self._lock:
                if self._price_cache.get(sym):
                    signals[sym] = self.generate_signal(sym)
        return {
            "mode":            "LIVE" if self.live_mode else "PAPER",
            "portfolio":       portfolio_val,
            "total_trades":    len(self._trade_history),
            "income_streams":  {k: v.to_dict() for k, v in self._income_streams.items()},
            "income_summary":  self.get_income_summary(),
            "current_signals": signals,
            "fear_greed":      self.get_fear_greed_index(),
        }

    def get_trade_history(self, limit: int = 20) -> List[dict]:
        with self._lock:
            return [t.to_dict() for t in list(self._trade_history)[-limit:]]


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[EconomicEngine] = None
_lock = threading.Lock()

def get_economic_engine(live_mode: bool = False) -> EconomicEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EconomicEngine(live_mode=live_mode)
    return _instance
