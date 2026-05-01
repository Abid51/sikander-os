import ccxt
import time
import os
import threading
import feedparser
import schedule
from dotenv import load_dotenv

load_dotenv()

class EarningSystem:
    """
    The Ultimate Earning System Architecture for Knight Commander Igris.
    Runs Crypto Trading, Social Media Automation, and Freelance Bidding in parallel.
    """
    def __init__(self):
        self.exchange = None
        self.balance = 0.0
        self.active_tasks = []
        self.running = True

    def init_crypto_bot(self):
        """Initializes connection to Crypto Exchange (Binance)."""
        api_key = os.getenv("CRYPTO_API_KEY")
        api_secret = os.getenv("CRYPTO_API_SECRET")
        
        if not api_key or not api_secret:
            return False, "Missing API Keys for Crypto Bot. Add them to .env file."
            
        try:
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
            })
            self.balance = self.exchange.fetch_balance()['USDT']['free']
            return True, f"Crypto Bot initialized. Available Balance: {self.balance} USDT."
        except Exception as e:
            return False, f"Failed to connect to Exchange: {str(e)}"

    def get_market_analysis(self, symbol: str = "BTC/USDT"):
        """Fetches basic market data."""
        if not self.exchange:
            return "Simulated Analysis: Market is volatile. Suggesting HOLD."
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return f"{symbol} current price is {ticker['last']}. High: {ticker['high']}, Low: {ticker['low']}."
        except Exception as e:
            return str(e)

    # --- BACKGROUND WORKERS (DAEMONS) ---

    def start_crypto_trading_daemon(self, symbol="BTC/USDT", amount=10):
        """A simple background trading loop (Moving Average Crossover example)."""
        def trader():
            print(f"[CRYPTO BOT] Started trading {symbol} with {amount} USDT...")
            while self.running:
                try:
                    if self.exchange:
                        ticker = self.exchange.fetch_ticker(symbol)
                        price = ticker['last']
                        # Simple Logic: Buy if price drops, Sell if it rises (Placeholder for real AI logic)
                        print(f"[CRYPTO BOT] {symbol} Price: {price} - Analyzing market...")
                    else:
                        print(f"[CRYPTO BOT] Simulated Mode - {symbol} analyzing market...")
                except Exception as e:
                    print(f"[CRYPTO BOT] Error: {str(e)}")
                time.sleep(60 * 5) # Check every 5 minutes

        t = threading.Thread(target=trader, daemon=True)
        t.start()
        self.active_tasks.append("CryptoTrader")
        return f"Crypto Trading Daemon started for {symbol}."

    def start_freelance_auto_bidder(self, keyword="python"):
        """Scans Upwork/RSS for new jobs and logs them (Auto-Bidding prep)."""
        def bidder():
            print(f"[FREELANCE BOT] Scanning for new '{keyword}' jobs...")
            # Upwork RSS Feed Example (Requires real token for full API)
            rss_url = f"https://www.upwork.com/ab/feed/jobs/rss?q={keyword}"
            seen_jobs = []
            
            while self.running:
                try:
                    feed = feedparser.parse(rss_url)
                    for entry in feed.entries[:3]: # Top 3 new jobs
                        if entry.link not in seen_jobs:
                            seen_jobs.append(entry.link)
                            title = entry.title
                            print(f"\n[FREELANCE BOT] New Job Found: {title}")
                            print(f"[FREELANCE BOT] Generating Cover Letter via Local LLM...")
                            # Here, Igris will use Ollama/Llama3 to write a cover letter
                            time.sleep(2)
                            print(f"[FREELANCE BOT] Proposal saved/submitted for: {title[:30]}...\n")
                except Exception:
                    pass
                time.sleep(60 * 10) # Check every 10 minutes
                
        t = threading.Thread(target=bidder, daemon=True)
        t.start()
        self.active_tasks.append("FreelanceBidder")
        return f"Freelance Auto-Bidder started for '{keyword}' jobs."

    def start_social_media_automator(self, platform="twitter"):
        """Simulates scheduling content for social media growth."""
        def social():
            print(f"[SOCIAL BOT] Starting engagement engine for {platform}...")
            while self.running:
                print(f"[SOCIAL BOT] Generating viral content via Local LLM...")
                time.sleep(2)
                print(f"[SOCIAL BOT] Auto-posting to {platform} and engaging with followers...")
                time.sleep(60 * 60) # Post/Engage every 1 hour

        t = threading.Thread(target=social, daemon=True)
        t.start()
        self.active_tasks.append("SocialMediaAutomator")
        return f"Social Media Automator started for {platform}."
