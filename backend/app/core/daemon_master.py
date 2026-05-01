"""
KNIGHT COMMANDER IGRIS - DAEMON MASTER CONTROLLER
All 13 Daemon Systems - Fully Integrated & Autonomous

Daemons:
1. Blood Ward - Security & Protection
2. Dominion - System Control & OS
3. Phantom Recon - Network Intelligence
4. Crimson Ledger - Finance & Crypto
5. Shadow Forge - Code Generation
6. Soul Weaver - Memory & Learning
7. Storm Caller - Automation & Scheduling
8. Void Walker - File Management
9. Aether Eye - Vision & OCR
10. Whisper Wind - Voice & Audio
11. Data Drake - Data Analysis
12. Iron Crown - Hardware Control
13. Chronos - Time & Prediction
"""

import asyncio
import threading
import json
import psutil
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DaemonStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class BaseDaemon:
    """Base class for all daemons"""
    
    def __init__(self, name: str, daemon_id: str, description: str):
        self.name = name
        self.daemon_id = daemon_id
        self.description = description
        self.status = DaemonStatus.STOPPED
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.tasks: List[asyncio.Task] = []
        self.stats = {
            "started_at": None,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "last_activity": None
        }
        self.is_running = False
        
    async def start(self):
        """Start the daemon"""
        if self.status == DaemonStatus.RUNNING:
            return {"status": "already_running"}
            
        self.status = DaemonStatus.STARTING
        self.is_running = True
        self.stats["started_at"] = datetime.now().isoformat()
        
        try:
            await self._initialize()
            self.status = DaemonStatus.RUNNING
            asyncio.create_task(self._main_loop())
            return {
                "status": "started",
                "daemon": self.name,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.status = DaemonStatus.ERROR
            logger.error(f"[{self.name}] Failed to start: {e}")
            return {"status": "error", "error": str(e)}
    
    async def stop(self):
        """Stop the daemon"""
        self.is_running = False
        self.status = DaemonStatus.STOPPED
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        await self._cleanup()
        
        return {
            "status": "stopped",
            "daemon": self.name,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _initialize(self):
        """
        Override in subclass.
        Called once before _main_loop begins — use for setup, config loading,
        and connection establishment.
        """

    async def _main_loop(self):
        """
        Override in subclass.
        Primary work loop.  Should run while self.is_running is True
        and call asyncio.sleep() to yield control.
        """

    async def _cleanup(self):
        """
        Override in subclass.
        Called on stop() after is_running is set False.
        Release connections, flush buffers, close files here.
        """
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "daemon_id": self.daemon_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "stats": self.stats,
            "is_running": self.is_running
        }


# ============================================================================
# DAEMON 1: BLOOD WARD - Security & Protection
# ============================================================================
class BloodWardDaemon(BaseDaemon):
    """
    Security daemon that monitors system for threats,
    unauthorized access, and suspicious activities.
    """
    
    def __init__(self):
        super().__init__(
            name="Blood Ward",
            daemon_id="blood_ward_01",
            description="Security & Protection Guardian"
        )
        self.threats_detected = []
        self.security_rules = []
        self.blocked_ips = set()
        self.suspicious_processes = []
        
    async def _initialize(self):
        """Initialize security monitoring"""
        logger.info("[Blood Ward] Initializing security protocols...")
        self._load_security_rules()
        
    def _load_security_rules(self):
        """Load security rules from config"""
        self.security_rules = [
            {"type": "process", "pattern": "malware", "action": "kill"},
            {"type": "network", "pattern": "suspicious_port", "action": "block"},
            {"type": "file", "pattern": "encryptor", "action": "quarantine"},
        ]
        
    async def _main_loop(self):
        """Main security monitoring loop"""
        while self.is_running:
            try:
                # Monitor processes
                await self._scan_processes()
                
                # Monitor network connections
                await self._monitor_network()
                
                # Check file integrity
                await self._check_file_integrity()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"[Blood Ward] Error: {e}")
                self.stats["tasks_failed"] += 1
                await asyncio.sleep(1)
    
    async def _scan_processes(self):
        """Scan for suspicious processes"""
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                # Check for high CPU usage
                if proc.info['cpu_percent'] and proc.info['cpu_percent'] > 80:
                    self.suspicious_processes.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "cpu": proc.info['cpu_percent'],
                        "timestamp": datetime.now().isoformat()
                    })
                    
                # Check against security rules
                for rule in self.security_rules:
                    if rule['type'] == 'process' and rule['pattern'] in proc.info['name'].lower():
                        await self._handle_threat("process", proc.info)
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    async def _monitor_network(self):
        """Monitor network connections"""
        try:
            connections = psutil.net_connections()
            for conn in connections:
                if conn.status == 'ESTABLISHED' and conn.raddr:
                    ip = conn.raddr.ip
                    # Check for suspicious IPs
                    if ip in self.blocked_ips:
                        await self._block_connection(conn)
        except Exception as e:
            logger.warning(f"[Blood Ward] Network monitoring error: {e}")
    
    async def _check_file_integrity(self):
        """Check critical file integrity"""
        import hashlib
        critical_files = []
        if os.name == 'nt': critical_files = ['C:\\Windows\\System32\\hal.dll']
        else: critical_files = ['/etc/passwd']
        
        for file_path in critical_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, "rb") as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                        # Simulated baseline check
                except Exception as e:
                    logger.debug(f"[Blood Ward] Integrity check failed for {file_path}: {e}")
    
    async def _handle_threat(self, threat_type: str, details: Dict):
        """Handle detected threat"""
        threat = {
            "type": threat_type,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "handled": False
        }
        self.threats_detected.append(threat)
        logger.warning(f"[Blood Ward] Threat detected: {threat_type}")
        self.stats["tasks_completed"] += 1
    
    async def _block_connection(self, connection):
        """Block suspicious network connection"""
        logger.info(f"[Blood Ward] Blocking connection to {connection.raddr.ip}")
    
    def get_threats(self) -> List[Dict]:
        return self.threats_detected[-50:]  # Last 50 threats
    
    async def add_blocked_ip(self, ip: str):
        self.blocked_ips.add(ip)
        return {"status": "blocked", "ip": ip}


# ============================================================================
# DAEMON 2: DOMINION - System Control & OS
# ============================================================================
class DominionDaemon(BaseDaemon):
    """
    System control daemon that manages OS-level operations,
    process management, and system resources.
    """
    
    def __init__(self):
        super().__init__(
            name="Dominion",
            daemon_id="dominion_02",
            description="System Control & OS Manager"
        )
        self.system_info = {}
        self.processes = {}
        self.commands_queue = []
        
    async def _initialize(self):
        """Initialize system monitoring"""
        logger.info("[Dominion] Initializing system control...")
        self._gather_system_info()
        
    def _gather_system_info(self):
        """Gather system information"""
        self.system_info = {
            "platform": os.name,
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_total": psutil.disk_usage('/').total if os.name != 'nt' else psutil.disk_usage('C:').total,
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }
        
    async def _main_loop(self):
        """Main system control loop"""
        while self.is_running:
            try:
                # Update system stats
                await self._update_system_stats()
                
                # Process commands queue
                await self._process_commands()
                
                # Monitor critical processes
                await self._monitor_critical_processes()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"[Dominion] Error: {e}")
                await asyncio.sleep(1)
    
    async def _update_system_stats(self):
        """Update real-time system statistics"""
        self.system_info.update({
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used": psutil.virtual_memory().used,
            "memory_available": psutil.virtual_memory().available,
            "disk_percent": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _process_commands(self):
        """Process pending system commands"""
        while self.commands_queue:
            command = self.commands_queue.pop(0)
            try:
                result = await self._execute_command(command)
                self.stats["tasks_completed"] += 1
                logger.info(f"[Dominion] Executed: {command['type']}")
            except Exception as e:
                logger.error(f"[Dominion] Command failed: {e}")
                self.stats["tasks_failed"] += 1
    
    async def _execute_command(self, command: Dict) -> Dict:
        """Execute system command"""
        cmd_type = command.get('type')
        
        if cmd_type == 'open_app':
            return await self._open_application(command['app'])
        elif cmd_type == 'close_app':
            return await self._close_application(command['process_name'])
        elif cmd_type == 'system_command':
            return await self._run_system_command(command['command'])
        elif cmd_type == 'kill_process':
            return await self._kill_process(command['pid'])
        elif cmd_type == 'ghost_protocol':
            return await self._execute_ghost_protocol(command)
        
        return {"status": "unknown_command"}
    
    async def _execute_ghost_protocol(self, payload: Dict) -> Dict:
        """GOD TIER PHASE 3: Take control of mouse and keyboard"""
        try:
            import pyautogui
            import time
            action = payload.get('action')
            
            if action == 'type':
                pyautogui.write(payload.get('text', ''), interval=0.05)
            elif action == 'click':
                pyautogui.click(x=payload.get('x'), y=payload.get('y'))
            elif action == 'combo':
                # Example: ['ctrl', 'c']
                pyautogui.hotkey(*payload.get('keys', []))
            
            logger.info(f"[Ghost Protocol] Executed action: {action}")
            return {"status": "executed", "action": action}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _open_application(self, app_name: str) -> Dict:
        """Open an application"""
        import subprocess
        try:
            subprocess.Popen(app_name)
            return {"status": "opened", "app": app_name}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _close_application(self, process_name: str) -> Dict:
        """Close an application"""
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == process_name:
                try:
                    proc.terminate()
                    return {"status": "closed", "process": process_name}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
        return {"status": "not_found"}
    
    async def _run_system_command(self, command: str) -> Dict:
        """Run system command"""
        import subprocess
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return {
                "status": "completed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _kill_process(self, pid: int) -> Dict:
        """Kill a process by PID"""
        try:
            process = psutil.Process(pid)
            process.terminate()
            return {"status": "killed", "pid": pid}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _monitor_critical_processes(self):
        """Monitor critical system processes and log any that are missing."""
        critical = (
            ['explorer.exe', 'svchost.exe', 'csrss.exe']
            if os.name == 'nt'
            else ['systemd', 'init', 'sshd']
        )
        try:
            running_names = {p.name().lower() for p in psutil.process_iter(['name'])}
            for proc_name in critical:
                if proc_name.lower() not in running_names:
                    logger.warning(
                        "[Dominion] Critical process missing: %s", proc_name
                    )
                    self.stats["tasks_failed"] += 1
        except psutil.AccessDenied:
            logger.debug("[Dominion] Access denied reading process list")
    
    def queue_command(self, command: Dict):
        """Queue a command for execution"""
        self.commands_queue.append(command)
        return {"status": "queued"}
    
    def get_system_info(self) -> Dict:
        return self.system_info


# ============================================================================
# DAEMON 3: PHANTOM RECON - Network Intelligence
# ============================================================================
class PhantomReconDaemon(BaseDaemon):
    """
    Network intelligence daemon for scanning, monitoring,
    and analyzing network activity.
    """
    
    def __init__(self):
        super().__init__(
            name="Phantom Recon",
            daemon_id="phantom_recon_03",
            description="Network Intelligence & Scanner"
        )
        self.network_devices = []
        self.network_stats = {}
        self.scans_history = []
        self.ioT_devices = []
        
    async def _initialize(self):
        """Initialize network monitoring"""
        logger.info("[Phantom Recon] Initializing network intelligence...")
        
    async def _main_loop(self):
        """Main network monitoring loop"""
        while self.is_running:
            try:
                # Monitor network stats
                await self._update_network_stats()
                
                # Discover devices
                await self._discover_devices()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"[Phantom Recon] Error: {e}")
                await asyncio.sleep(1)
    
    async def _update_network_stats(self):
        """Update network statistics"""
        try:
            net_io = psutil.net_io_counters()
            self.network_stats = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"[Phantom Recon] Network stats error: {e}")
    
    async def _discover_devices(self):
        """Discover network devices"""
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            self.network_devices.append({"hostname": hostname, "ip": local_ip, "status": "online"})
            # To avoid duplicates logic
            self.network_devices = [dict(t) for t in {tuple(d.items()) for d in self.network_devices}]
        except Exception as e:
            logger.debug(f"[Phantom Recon] Discovery error: {e}")
    
    async def scan_port(self, host: str, port: int) -> Dict:
        """Scan a specific port"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            
            is_open = result == 0
            scan_result = {
                "host": host,
                "port": port,
                "is_open": is_open,
                "timestamp": datetime.now().isoformat()
            }
            self.scans_history.append(scan_result)
            return scan_result
        except Exception as e:
            return {"error": str(e)}
    
    async def network_scan(self, subnet: str) -> Dict:
        """Scan entire network subnet"""
        logger.info(f"[Phantom Recon] Scanning subnet: {subnet}")
        return {
            "subnet": subnet,
            "devices_found": 0,
            "timestamp": datetime.now().isoformat(),
            "status": "completed"
        }
    
    def get_network_info(self) -> Dict:
        return {
            "stats": self.network_stats,
            "devices": self.network_devices,
            "recent_scans": self.scans_history[-10:]
        }


# ============================================================================
# DAEMON 4: CRIMSON LEDGER - Finance & Crypto
# ============================================================================
class CrimsonLedgerDaemon(BaseDaemon):
    """
    Finance and cryptocurrency daemon for portfolio tracking,
    market analysis, and trading operations.
    """
    
    def __init__(self):
        super().__init__(
            name="Crimson Ledger",
            daemon_id="crimson_ledger_04",
            description="Finance & Cryptocurrency Manager"
        )
        self.portfolio = {}
        self.watchlist = []
        self.price_cache = {}
        self.transactions = []
        self.alerts = []
        
    async def _initialize(self):
        """Initialize finance module"""
        logger.info("[Crimson Ledger] Initializing finance systems...")
        try:
            import ccxt
            self.exchange = ccxt.binance()  # Default exchange
        except:
            self.exchange = None
            
    async def _main_loop(self):
        """Main finance monitoring loop"""
        while self.is_running:
            try:
                # Update prices
                await self._update_prices()
                
                # Check alerts
                await self._check_alerts()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                logger.error(f"[Crimson Ledger] Error: {e}")
                await asyncio.sleep(10)
    
    async def _update_prices(self):
        """Update cryptocurrency prices"""
        if self.exchange:
            try:
                for symbol in self.watchlist:
                    ticker = self.exchange.fetch_ticker(symbol)
                    self.price_cache[symbol] = {
                        "price": ticker['last'],
                        "change_24h": ticker['change'],
                        "timestamp": datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"[Crimson Ledger] Price update error: {e}")
    
    async def _check_alerts(self):
        """Check price alerts"""
        for alert in self.alerts:
            symbol = alert['symbol']
            if symbol in self.price_cache:
                current_price = self.price_cache[symbol]['price']
                target = alert['target_price']
                
                if (alert['condition'] == 'above' and current_price >= target) or \
                   (alert['condition'] == 'below' and current_price <= target):
                    alert['triggered'] = True
                    alert['triggered_at'] = datetime.now().isoformat()
                    logger.info(f"[Crimson Ledger] Alert triggered: {symbol}")
    
    def add_to_watchlist(self, symbol: str) -> Dict:
        """Add cryptocurrency to watchlist"""
        if symbol not in self.watchlist:
            self.watchlist.append(symbol)
        return {"status": "added", "symbol": symbol, "watchlist": self.watchlist}
    
    def get_portfolio(self) -> Dict:
        """Get current portfolio"""
        total_value = sum(
            holding['amount'] * self.price_cache.get(symbol, {}).get('price', 0)
            for symbol, holding in self.portfolio.items()
        )
        return {
            "holdings": self.portfolio,
            "total_value": total_value,
            "watchlist": self.watchlist,
            "prices": self.price_cache
        }
    
    async def simulate_trade(self, symbol: str, amount: float, side: str) -> Dict:
        """Simulate a trade"""
        trade = {
            "symbol": symbol,
            "amount": amount,
            "side": side,
            "timestamp": datetime.now().isoformat(),
            "status": "simulated"
        }
        self.transactions.append(trade)
        return trade


# ============================================================================
# DAEMON 5: SHADOW FORGE - Code Generation
# ============================================================================
class ShadowForgeDaemon(BaseDaemon):
    """
    Code generation daemon that can write, analyze, and optimize code
    in multiple programming languages.
    """
    
    def __init__(self):
        super().__init__(
            name="Shadow Forge",
            daemon_id="shadow_forge_05",
            description="Code Generation & Analysis"
        )
        self.code_templates = {}
        self.generated_code = []
        self.analysis_queue = []
        
    async def _initialize(self):
        """Initialize code templates"""
        logger.info("[Shadow Forge] Initializing code forge...")
        self._load_templates()
        
    def _load_templates(self):
        """Load code templates"""
        self.code_templates = {
            "python": {
                "function": "def {name}({params}):\n    \"\"\"{docstring}\"\"\"\n    {body}",
                "class": "class {name}:\n    \"\"\"{docstring}\"\"\"\n    def __init__(self):\n        pass"
            },
            "javascript": {
                "function": "function {name}({params}) {{\n    // {docstring}\n    {body}\n}}",
                "class": "class {name} {{\n    constructor() {{\n        // {docstring}\n    }}\n}}"
            }
        }
        
    async def _main_loop(self):
        """Main code generation loop"""
        while self.is_running:
            try:
                # Process analysis queue
                await self._process_analysis()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"[Shadow Forge] Error: {e}")
                await asyncio.sleep(1)
    
    async def _process_analysis(self):
        """Process pending code analysis requests from the queue."""
        while self.analysis_queue:
            request = self.analysis_queue.pop(0)
            try:
                lang = request.get('language', 'unknown')
                code = request.get('code', '')
                result = await self.analyze_code(code, lang)
                request['result']   = result
                request['analyzed'] = True
                logger.debug("[Shadow Forge] Analyzed %s (%d lines)", lang, result.get('lines', 0))
                self.stats["tasks_completed"] += 1
            except Exception as e:
                logger.error("[Shadow Forge] Analysis failed: %s", e)
                self.stats["tasks_failed"] += 1
    
    async def generate_code(self, language: str, template: str, params: Dict) -> str:
        """Generate code from template"""
        if language in self.code_templates and template in self.code_templates[language]:
            code = self.code_templates[language][template].format(**params)
            self.generated_code.append({
                "language": language,
                "code": code,
                "timestamp": datetime.now().isoformat()
            })
            return code
        return f"# Template not found for {language}/{template}"
    
    async def analyze_code(self, code: str, language: str) -> Dict:
        """Analyze code for issues and improvements"""
        line_list = code.splitlines()
        analysis = {
            "language": language,
            "lines": len(line_list),
            "issues": [],
            "suggestions": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Basic analysis
        if 'TODO' in code:
            analysis["issues"].append("Contains TODO items")
        if len(line_list) > 100:
            analysis["suggestions"].append("Consider splitting into smaller functions")
            
        return analysis
    
    async def optimize_code(self, code: str, language: str) -> Dict:
        """Optimize code for performance"""
        # Basic string-level optimizations for now
        lines = code.split('\n')
        lines = [line.rstrip() for line in lines if line.strip() or not lines]
        optimized_code = '\n'.join(lines)
        return {
            "original": code,
            "optimized": optimized_code,
            "improvements": ["Removed trailing whitespaces and empty lines"],
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# DAEMON 6: SOUL WEAVER - Memory & Learning
# ============================================================================
class SoulWeaverDaemon(BaseDaemon):
    """
    Memory and learning daemon that manages AI memory,
    training data, and knowledge base.
    """
    
    def __init__(self):
        super().__init__(
            name="Soul Weaver",
            daemon_id="soul_weaver_06",
            description="Memory & Learning Systems"
        )
        self.memory = {}
        self.training_data = []
        self.knowledge_base = {}
        self.learning_queue = []
        
    async def _initialize(self):
        """Initialize memory systems"""
        logger.info("[Soul Weaver] Initializing memory systems...")
        await self._load_memory()
        
        # GOD TIER PHASE 4: Neural Deep-Link
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path="./igris_chroma_db")
            self.collection = self.chroma_client.get_or_create_collection(name="igris_neural_link")
            self.vector_enabled = True
            logger.info("[Soul Weaver] God-Tier Phase 4: Neural Deep-Link (VectorDB) Activated")
        except Exception as e:
            self.vector_enabled = False
            logger.error(f"[Soul Weaver] VectorDB init failed: {e}")
        
    async def _load_memory(self):
        """Load persisted memory"""
        try:
            with open('igris_memory.json', 'r') as f:
                self.memory = json.load(f)
        except:
            self.memory = {"conversations": [], "facts": {}, "preferences": {}}
            
    async def _main_loop(self):
        """Main learning loop"""
        while self.is_running:
            try:
                # Process learning queue
                await self._process_learning()
                
                # Periodic memory save
                await self._save_memory()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"[Soul Weaver] Error: {e}")
                await asyncio.sleep(5)
    
    async def _process_learning(self):
        """Process learning tasks"""
        while self.learning_queue:
            task = self.learning_queue.pop(0)
            # Learning logic here
            self.stats["tasks_completed"] += 1
    
    async def _save_memory(self):
        """Save memory to disk"""
        try:
            with open('igris_memory.json', 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logger.error(f"[Soul Weaver] Failed to save memory: {e}")
    
    def store_conversation(self, user_input: str, ai_response: str, context: Dict = None):
        """Store conversation in memory"""
        import time
        conv_id = f"conv_{int(time.time()*1000)}"
        doc = f"User: {user_input}\nIgris: {ai_response}"
        
        self.memory["conversations"].append({
            "id": conv_id,
            "user": user_input,
            "ai": ai_response,
            "context": context,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 1000 conversations
        self.memory["conversations"] = self.memory["conversations"][-1000:]
        
        # Vector insertion
        if getattr(self, 'vector_enabled', False):
            try:
                self.collection.add(
                    documents=[doc],
                    metadatas=[{"type": "conversation", "timestamp": datetime.now().isoformat()}],
                    ids=[conv_id]
                )
            except Exception as e:
                logger.error(f"[Soul Weaver] Vector store error: {e}")
        
    def store_fact(self, key: str, value: Any):
        """Store a fact"""
        self.memory["facts"][key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        
    def recall(self, query: str) -> List[Dict]:
        """Recall relevant memories"""
        # Phase 4 Neural Recall
        if getattr(self, 'vector_enabled', False):
            try:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=5
                )
                if results['documents'] and len(results['documents'][0]) > 0:
                    return [{"source": "neural_link", "content": doc} for doc in results['documents'][0]]
            except Exception as e:
                logger.error(f"[Soul Weaver] Neural recall error: {e}")
                
        # Basic Fallback
        results = []
        for conv in self.memory.get("conversations", []):
            if query.lower() in conv['user'].lower() or query.lower() in conv['ai'].lower():
                results.append(conv)
        return results[-10:]  # Last 10 relevant


# ============================================================================
# DAEMON MASTER CONTROLLER
# ============================================================================
class DaemonMaster:
    """
    Master controller for all 13 daemons.
    Manages daemon lifecycle, coordination, and inter-daemon communication.
    """
    
    def __init__(self):
        self.daemons: Dict[str, BaseDaemon] = {}
        self.initialized = False
        self.event_bus = asyncio.Queue()
        self._init_daemons()
        
    def _init_daemons(self):
        """Initialize all daemon instances"""
        self.daemons = {
            "blood_ward": BloodWardDaemon(),
            "dominion": DominionDaemon(),
            "phantom_recon": PhantomReconDaemon(),
            "crimson_ledger": CrimsonLedgerDaemon(),
            "shadow_forge": ShadowForgeDaemon(),
            "soul_weaver": SoulWeaverDaemon(),
                "storm_caller": StormCallerDaemon(),
            "void_walker": VoidWalkerDaemon(),
            "aether_eye": AetherEyeDaemon(),
            "whisper_wind": WhisperWindDaemon(),
            "data_drake": DataDrakeDaemon(),
            "iron_crown": IronCrownDaemon(),
            "chronos": ChronosDaemon()
        }
        logger.info(f"[Daemon Master] Initialized {len(self.daemons)} daemons")
    
    async def start_all(self) -> Dict:
        """Start all daemons"""
        results = {}
        for name, daemon in self.daemons.items():
            result = await daemon.start()
            results[name] = result
            await asyncio.sleep(0.1)  # Stagger starts
        
        self.initialized = True
        
        # Start event bus
        asyncio.create_task(self._event_bus_loop())
        
        return {
            "status": "started",
            "daemons": results,
            "total": len(results)
        }
    
    async def stop_all(self) -> Dict:
        """Stop all daemons"""
        results = {}
        for name, daemon in self.daemons.items():
            result = await daemon.stop()
            results[name] = result
        
        self.initialized = False
        return {
            "status": "stopped",
            "daemons": results
        }
    
    async def _event_bus_loop(self):
        """Event bus for inter-daemon communication"""
        while self.initialized:
            try:
                event = await asyncio.wait_for(self.event_bus.get(), timeout=1.0)
                # Route event to appropriate daemons
                await self._route_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[Daemon Master] Event bus error: {e}")
    
    async def _route_event(self, event: Dict):
        """Route events to daemons"""
        target = event.get('target')
        if target and target in self.daemons:
            daemon = self.daemons[target]
            command = event.get("command")
            params = event.get("params", {})
            if command and hasattr(daemon, "queue_command"):
                daemon.queue_command({"type": command, **params})
            elif command and hasattr(daemon, command):
                fn = getattr(daemon, command)
                result = fn(**params) if callable(fn) else None
                if asyncio.iscoroutine(result):
                    await result
            else:
                logger.debug(f"[Daemon Master] Event dropped for {target}: unsupported command {command!r}")
        elif target == 'broadcast':
            command = event.get("command")
            params = event.get("params", {})
            for daemon in self.daemons.values():
                try:
                    if command and hasattr(daemon, "queue_command"):
                        daemon.queue_command({"type": command, **params})
                    elif command and hasattr(daemon, command):
                        fn = getattr(daemon, command)
                        result = fn(**params) if callable(fn) else None
                        if asyncio.iscoroutine(result):
                            await result
                except Exception as e:
                    logger.warning(f"[Daemon Master] Broadcast failed for {daemon.name}: {e}")
        else:
            logger.debug(f"[Daemon Master] Event ignored: unknown target={target!r}")

    async def emit_event(self, target: str, command: str, params: Dict = None) -> Dict:
        """Push an event onto the internal bus for daemon routing."""
        event = {
            "target": target,
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat(),
        }
        await self.event_bus.put(event)
        return {"status": "queued", "event": event}
    
    def get_status(self) -> Dict:
        """Get status of all daemons"""
        return {
            "initialized": self.initialized,
            "daemons": {
                name: daemon.get_status()
                for name, daemon in self.daemons.items()
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def get_daemon(self, name: str) -> Optional[BaseDaemon]:
        """Get a specific daemon"""
        return self.daemons.get(name)
    
    async def send_command(self, daemon_name: str, command: str, params: Dict = None) -> Dict:
        """Send command to a specific daemon — routes to daemon methods or queue"""
        daemon = self.get_daemon(daemon_name)
        if not daemon:
            return {"error": f"Daemon '{daemon_name}' not found",
                    "available": list(self.daemons.keys())}
        params = params or {}
        # Try direct async method call first
        method = getattr(daemon, command, None)
        if method and callable(method):
            try:
                result = method(**params)
                if asyncio.iscoroutine(result):
                    result = await result
                return result if isinstance(result, dict) else {"result": result, "status": "ok"}
            except Exception as e:
                return {"error": str(e), "daemon": daemon_name, "command": command}
        # Fallback to queue_command if daemon supports it
        if hasattr(daemon, 'queue_command'):
            return daemon.queue_command({"type": command, **params})
        return {"error": f"Command '{command}' not found on daemon '{daemon_name}'",
                "hint": f"Available methods: {[m for m in dir(daemon) if not m.startswith('_')][:20]}"
                }

    async def create_dynamic_daemon(self, class_name: str, daemon_code: str) -> Dict:
        """Phase 2 God-Tier: Dynamically construct and forge a new daemon at runtime"""
        try:
            # Run code to construct the daemon in current scope
            exec_namespace = globals().copy()
            exec(daemon_code, exec_namespace)
            
            if class_name in exec_namespace:
                DaemonClass = exec_namespace[class_name]
                new_daemon = DaemonClass()
                
                daemon_key = class_name.lower().replace("daemon", "")
                self.daemons[daemon_key] = new_daemon
                
                # Start immediately if system running
                if self.initialized:
                    await self.daemons[daemon_key].start()
                    
                logger.info(f"[Daemon Master] Successfully executed Phase 2 Shadow Clone! Forged daemon: {class_name}")
                return {"status": "forged", "daemon": class_name, "key": daemon_key}
            else:
                return {"status": "error", "error": f"Class {class_name} not found"}
        except Exception as e:
            logger.error(f"[Daemon Master] Failed to forge new daemon: {e}")
            return {"status": "error", "error": str(e)}


# ============================================================================
# DAEMON 7: STORM CALLER - Automation & Scheduling
# ============================================================================
class StormCallerDaemon(BaseDaemon):
    """
    Automation and scheduling daemon for task scheduling,
    recurring jobs, and automated workflows.
    """
    
    def __init__(self):
        super().__init__(
            name="Storm Caller",
            daemon_id="storm_caller_07",
            description="Automation & Scheduling"
        )
        self.scheduled_tasks = []
        self.running_jobs = {}
        self.workflows = {}
        
    async def _initialize(self):
        """Initialize scheduler"""
        logger.info("[Storm Caller] Initializing automation engine...")
        
    async def _main_loop(self):
        """Main scheduling loop"""
        while self.is_running:
            try:
                now = datetime.now()
                
                # Check scheduled tasks
                for task in self.scheduled_tasks:
                    if task['next_run'] <= now and not task['running']:
                        asyncio.create_task(self._execute_task(task))
                
                # Cleanup completed jobs
                self._cleanup_jobs()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"[Storm Caller] Error: {e}")
                await asyncio.sleep(1)
    
    async def _execute_task(self, task: Dict):
        """Execute a scheduled task"""
        task['running'] = True
        try:
            # Execute task logic
            result = await self._run_task_action(task['action'], task['params'])
            task['last_result'] = result
            task['last_run'] = datetime.now().isoformat()
            task['run_count'] = task.get('run_count', 0) + 1
            
            # Schedule next run
            if task['recurring']:
                task['next_run'] = self._calculate_next_run(task['schedule'])
            else:
                task['completed'] = True
                
            self.stats["tasks_completed"] += 1
        except Exception as e:
            task['error'] = str(e)
            self.stats["tasks_failed"] += 1
        finally:
            task['running'] = False
    
    async def _run_task_action(self, action: str, params: Dict) -> Dict:
        """Run task action — supports shell, http_get, file_write, file_delete, notify"""
        import subprocess, aiohttp
        try:
            if action == "shell":
                return {"action": action, "status": "error", "error": "shell action disabled for security"}
            elif action == "http_get":
                url = params.get("url", "")
                if not url:
                    return {"error": "No URL provided"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        text = await resp.text()
                        return {"action": action, "status": "completed", "status_code": resp.status, "body_snippet": text[:500]}
            elif action == "file_write":
                path = params.get("path", "")
                content = params.get("content", "")
                if not path:
                    return {"error": "No path provided"}
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"action": action, "status": "completed", "path": path, "bytes_written": len(content)}
            elif action == "file_delete":
                path = params.get("path", "")
                if not path or not os.path.exists(path):
                    return {"error": "File not found"}
                os.remove(path)
                return {"action": action, "status": "completed", "deleted": path}
            elif action == "notify":
                message = params.get("message", "Storm Caller notification")
                logger.info(f"[Storm Caller] NOTIFY: {message}")
                return {"action": action, "status": "completed", "message": message}
            elif action == "python_eval":
                return {"action": action, "status": "error", "error": "python_eval action disabled for security"}
            else:
                return {"action": action, "status": "completed", "note": "no-op action"}
        except Exception as e:
            return {"action": action, "status": "error", "error": str(e)}

    def _calculate_next_run(self, schedule: Dict) -> datetime:
        """Calculate next run time — supports interval_minutes, interval_hours, cron_hour"""
        from datetime import timedelta
        if "cron_hour" in schedule:
            hour = int(schedule.get("cron_hour", 0))
            minute = int(schedule.get("cron_minute", 0))
            now = datetime.now()
            target = now.replace(hour=max(0, min(hour, 23)), minute=max(0, min(minute, 59)), second=0, microsecond=0)
            if target <= now:
                target = target + timedelta(days=1)
            return target
        if "interval_hours" in schedule:
            return datetime.now() + timedelta(hours=schedule["interval_hours"])
        interval = schedule.get('interval_minutes', 60)
        return datetime.now() + timedelta(minutes=interval)

    def _cleanup_jobs(self):
        """Cleanup completed non-recurring jobs, keep last 200 completed"""
        completed = [t for t in self.scheduled_tasks if t.get('completed')]
        active = [t for t in self.scheduled_tasks if not t.get('completed')]
        # Keep last 100 completed for history
        self.scheduled_tasks = active + completed[-100:]

    def schedule_task(self, name: str, action: str, params: Dict, schedule: Dict, recurring: bool = False) -> Dict:
        """Schedule a new task"""
        if action in {"shell", "python_eval"}:
            return {"status": "error", "error": f"{action} action disabled for security"}
        task = {
            "id": f"{int(datetime.now().timestamp()*1000)}",
            "name": name,
            "action": action,
            "params": params,
            "schedule": schedule,
            "recurring": recurring,
            "next_run": self._calculate_next_run(schedule),
            "running": False,
            "completed": False,
            "run_count": 0,
            "created_at": datetime.now().isoformat()
        }
        self.scheduled_tasks.append(task)
        logger.info(f"[Storm Caller] Scheduled task '{name}' action='{action}' recurring={recurring}")
        return {"status": "scheduled", "task_id": task['id'], "task": task}

    def cancel_task(self, task_id: str) -> Dict:
        """Cancel a scheduled task by ID"""
        before = len(self.scheduled_tasks)
        self.scheduled_tasks = [t for t in self.scheduled_tasks if t['id'] != task_id]
        removed = before - len(self.scheduled_tasks)
        return {"status": "cancelled" if removed else "not_found", "task_id": task_id}

    def get_tasks(self) -> List[Dict]:
        """Get all scheduled tasks (serializable)"""
        result = []
        for t in self.scheduled_tasks:
            row = dict(t)
            # Convert datetime to string for JSON
            if isinstance(row.get('next_run'), datetime):
                row['next_run'] = row['next_run'].isoformat()
            result.append(row)
        return result


# ============================================================================
# DAEMON 8: VOID WALKER - File Management
# ============================================================================
class VoidWalkerDaemon(BaseDaemon):
    """
    File management daemon for file operations, organization,
    and intelligent file handling.
    """
    
    def __init__(self):
        super().__init__(
            name="Void Walker",
            daemon_id="void_walker_08",
            description="File Management & Organization"
        )
        self.file_cache: Dict[str, Any] = {}
        self.organized_dirs: Dict[str, Any] = {}
        self.file_operations: List[Dict] = []
        self.file_operations_log: List[Dict] = []
        
    async def _initialize(self):
        """Initialize file manager"""
        logger.info("[Void Walker] Initializing file systems...")
        
    async def _main_loop(self):
        """Main file monitoring loop"""
        while self.is_running:
            try:
                # Monitor organized directories
                await self._monitor_directories()
                
                # Process file operations queue
                await self._process_operations()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"[Void Walker] Error: {e}")
                await asyncio.sleep(1)
    
    async def _monitor_directories(self):
        """Monitor organized directories"""
        for dir_path, config in self.organized_dirs.items():
            if os.path.exists(dir_path):
                await self._organize_directory(dir_path, config)
    
    async def _organize_directory(self, dir_path: str, config: Dict):
        """Organize files in directory"""
        for filename in os.listdir(dir_path):
            file_path = os.path.join(dir_path, filename)
            if os.path.isfile(file_path):
                ext = os.path.splitext(filename)[1].lower()
                target_folder = config.get(ext, "")
                if target_folder:
                    target_path = os.path.join(dir_path, target_folder)
                    os.makedirs(target_path, exist_ok=True)
                    try:
                        import shutil
                        shutil.move(file_path, os.path.join(target_path, filename))
                        logger.info(f"[Void Walker] Organized {filename} into {target_folder}")
                    except Exception as e:
                        pass
    
    async def _process_operations(self):
        """Process file operations queue"""
        import shutil, zipfile
        while self.file_operations:
            op = self.file_operations.pop(0)
            try:
                op_type = op.get("type")
                src = op.get("src", "")
                dst = op.get("dst", "")
                if op_type == "copy" and os.path.exists(src):
                    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
                    shutil.copy2(src, dst)
                    logger.info(f"[Void Walker] Copied {src} -> {dst}")
                elif op_type == "move" and os.path.exists(src):
                    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
                    shutil.move(src, dst)
                    logger.info(f"[Void Walker] Moved {src} -> {dst}")
                elif op_type == "delete" and os.path.exists(src):
                    if os.path.isdir(src):
                        shutil.rmtree(src)
                    else:
                        os.remove(src)
                    logger.info(f"[Void Walker] Deleted {src}")
                elif op_type == "compress":
                    # src = list of files/dirs, dst = zip path
                    files = op.get("files", [src])
                    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for fp in files:
                            if os.path.isfile(fp):
                                zf.write(fp, os.path.basename(fp))
                            elif os.path.isdir(fp):
                                for root, _, fnames in os.walk(fp):
                                    for fn in fnames:
                                        full = os.path.join(root, fn)
                                        zf.write(full, os.path.relpath(full, os.path.dirname(fp)))
                    logger.info(f"[Void Walker] Compressed -> {dst}")
                self.stats["tasks_completed"] += 1
                self.file_operations_log.append({"op": op, "status": "ok", "timestamp": datetime.now().isoformat()})
            except Exception as e:
                logger.error(f"[Void Walker] Operation failed: {e}")
                self.stats["tasks_failed"] += 1
                self.file_operations_log.append({"op": op, "status": "error", "error": str(e), "timestamp": datetime.now().isoformat()})

    def queue_operation(self, op_type: str, src: str, dst: str = "", files: List[str] = None) -> Dict:
        """Queue a file operation: copy | move | delete | compress"""
        op = {"type": op_type, "src": src, "dst": dst}
        if files:
            op["files"] = files
        self.file_operations.append(op)
        return {"status": "queued", "operation": op}

    def get_operation_log(self, limit: int = 50) -> List[Dict]:
        """Return recent file operation history"""
        return self.file_operations_log[-limit:]

    async def organize_files(self, source_dir: str, rules: List[Dict]) -> Dict:
        """Organize files based on rules: [{pattern, target_dir}]"""
        import shutil
        organized = 0
        errors = []
        if os.path.exists(source_dir):
            for filename in os.listdir(source_dir):
                file_path = os.path.join(source_dir, filename)
                if not os.path.isfile(file_path):
                    continue
                for rule in rules:
                    pattern = rule.get('pattern', '')
                    target_dir = rule.get('target_dir', '')
                    matches = False
                    if pattern.startswith('ext:'):
                        matches = filename.lower().endswith(pattern[4:].lower())
                    else:
                        matches = pattern.lower() in filename.lower()
                    if matches and target_dir:
                        os.makedirs(target_dir, exist_ok=True)
                        try:
                            shutil.move(file_path, os.path.join(target_dir, filename))
                            organized += 1
                        except Exception as e:
                            errors.append(str(e))
                        break
        return {"organized": organized, "source": source_dir, "errors": errors}

    async def search_files(self, directory: str, pattern: str, max_results: int = 200) -> List[Dict]:
        """Search for files by name pattern (case-insensitive), limited depth"""
        results = []
        if not os.path.exists(directory):
            return results
        for root, dirs, files in os.walk(directory):
            # Skip hidden and system dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'__pycache__', 'node_modules', '.git'}]
            for filename in files:
                if pattern.lower() in filename.lower():
                    fp = os.path.join(root, filename)
                    try:
                        stat = os.stat(fp)
                        results.append({
                            "name": filename,
                            "path": fp,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                    except Exception:
                        results.append({"name": filename, "path": fp, "size": 0, "modified": None})
                    if len(results) >= max_results:
                        return results
        return results

    async def get_directory_tree(self, directory: str, depth: int = 2) -> Dict:
        """Return a tree structure of a directory up to given depth"""
        def _tree(path: str, current_depth: int) -> Dict:
            node: Dict[str, Any] = {"name": os.path.basename(path), "path": path}
            if os.path.isdir(path) and current_depth > 0:
                children = []
                try:
                    for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name)):
                        if entry.name.startswith('.'):
                            continue
                        children.append(_tree(entry.path, current_depth - 1))
                except PermissionError:
                    pass
                node["children"] = children
                node["type"] = "directory"
            else:
                node["type"] = "file"
                try:
                    node["size"] = os.path.getsize(path)
                except Exception:
                    node["size"] = 0
            return node
        return _tree(directory, depth)

    async def cleanup_temp_files(self, directory: str, max_age_hours: int = 24) -> Dict:
        """Clean up old files in a directory"""
        import time
        cleaned = 0
        freed_space = 0
        errors = []
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    age = time.time() - os.path.getmtime(file_path)
                    if age > (max_age_hours * 3600):
                        try:
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned += 1
                            freed_space += size
                        except Exception as e:
                            errors.append(str(e))
        return {"cleaned": cleaned, "freed_bytes": freed_space, "freed_mb": round(freed_space / 1_048_576, 2), "errors": errors}


# ============================================================================
# DAEMON 9: AETHER EYE - Vision & OCR
# ============================================================================
class AetherEyeDaemon(BaseDaemon):
    """
    Vision and OCR daemon for image processing, text recognition,
    and computer vision tasks.
    """
    
    def __init__(self):
        super().__init__(
            name="Aether Eye",
            daemon_id="aether_eye_09",
            description="Vision & OCR Systems"
        )
        self.vision_queue = []
        self.processed_images = []
        self.tesseract_available = False
        
    async def _initialize(self):
        """Initialize vision systems"""
        logger.info("[Aether Eye] Initializing vision systems...")
        try:
            import pytesseract
            self.tesseract_available = True
        except:
            logger.warning("[Aether Eye] Tesseract not available")
            
    async def _main_loop(self):
        """Main vision processing loop"""
        import time
        last_capture_time = time.time()
        
        while self.is_running:
            try:
                # Process vision queue
                await self._process_vision_queue()
                
                # GOD TIER PHASE 1: Pre-Cognitive Assistance Loop
                current_time = time.time()
                if current_time - last_capture_time > 15:
                    try:
                        # 15 second loop to capture and analyze screen context invisibly
                        snapshot = await self.capture_screen()
                        if snapshot.get("path"):
                            logger.info(f"[Pre-Cognition] Analyzed context from {snapshot.get('path')}")
                            # In future: send to LLM for proactive suggestions
                            # os.remove(snapshot.get("path")) # Clean up to save space
                        last_capture_time = current_time
                    except Exception as loop_e:
                        logger.debug(f"[Pre-Cognition] Capture skipped: {loop_e}")
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"[Aether Eye] Error: {e}")
                await asyncio.sleep(1)
    
    async def _process_vision_queue(self):
        """Process vision tasks"""
        while self.vision_queue:
            task = self.vision_queue.pop(0)
            try:
                result = await self._process_image(task['image_path'], task['operation'])
                task['callback'](result) if task.get('callback') else None
                self.stats["tasks_completed"] += 1
            except Exception as e:
                logger.error(f"[Aether Eye] Processing error: {e}")
                self.stats["tasks_failed"] += 1
    
    async def _process_image(self, image_path: str, operation: str) -> Dict:
        """Process image"""
        if operation == 'ocr' and self.tesseract_available:
            return await self._perform_ocr(image_path)
        elif operation == 'analyze':
            return await self._analyze_image(image_path)
        return {"error": "Unknown operation or Tesseract not available"}
    
    async def _perform_ocr(self, image_path: str) -> Dict:
        """Perform OCR on image"""
        try:
            import pytesseract
            from PIL import Image
            
            if not os.path.exists(image_path):
                return {"error": "Image not found"}
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            
            return {
                "text": text,
                "confidence": 85,  # Estimated
                "image_path": image_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _analyze_image(self, image_path: str) -> Dict:
        """Analyze image content"""
        try:
            from PIL import Image
            img = Image.open(image_path)
            return {
                "size": img.size,
                "mode": img.mode,
                "format": img.format,
                "file_size": os.path.getsize(image_path),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def queue_vision_task(self, image_path: str, operation: str, callback=None):
        """Queue a vision task"""
        self.vision_queue.append({
            "image_path": image_path,
            "operation": operation,
            "callback": callback,
            "queued_at": datetime.now().isoformat()
        })
        return {"status": "queued"}
    
    async def capture_screen(self, region: Dict = None) -> Dict:
        """Capture screen"""
        try:
            vision_mode = os.getenv("IGRIS_VISION_MODE", "snapshot").strip().lower()
            if vision_mode == "live":
                try:
                    from app.core.live_view import get_live_view
                    lv = get_live_view()
                    latest = lv.get_latest_frame()
                    if latest:
                        return {
                            "source": "live_frame_buffer",
                            "timestamp": latest.get("timestamp"),
                            "format": latest.get("format", "jpeg"),
                            "has_frame": True,
                        }
                except Exception as live_e:
                    logger.debug(f"[Aether Eye] Live frame path unavailable: {live_e}")

            import pyautogui
            screenshot = pyautogui.screenshot(region=region)
            path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            screenshot.save(path)
            return {"path": path, "size": screenshot.size, "source": "snapshot_file"}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# DAEMON 10: WHISPER WIND - Voice & Audio
# ============================================================================
class WhisperWindDaemon(BaseDaemon):
    """
    Voice and audio daemon for speech recognition,
    text-to-speech, and audio processing.
    """
    
    def __init__(self):
        super().__init__(
            name="Whisper Wind",
            daemon_id="whisper_wind_10",
            description="Voice & Audio Systems"
        )
        self.audio_queue = []
        self.speech_engine = None
        self.recognizer = None
        
    async def _initialize(self):
        """Initialize voice systems"""
        logger.info("[Whisper Wind] Initializing voice systems...")
        try:
            import pyttsx3
            self.speech_engine = pyttsx3.init()
        except:
            logger.warning("[Whisper Wind] TTS not available")
        
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
        except:
            logger.warning("[Whisper Wind] Speech recognition not available")
            
    async def _main_loop(self):
        """Main audio processing loop"""
        while self.is_running:
            try:
                # Process audio queue
                await self._process_audio_queue()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"[Whisper Wind] Error: {e}")
                await asyncio.sleep(1)
    
    async def _process_audio_queue(self):
        """Process audio tasks"""
        while self.audio_queue:
            task = self.audio_queue.pop(0)
            try:
                if task['type'] == 'speak':
                    await self._speak(task['text'])
                elif task['type'] == 'transcribe':
                    result = await self._transcribe_audio(task['audio_path'])
                    if task.get('callback'):
                        task['callback'](result)
                self.stats["tasks_completed"] += 1
            except Exception as e:
                logger.error(f"[Whisper Wind] Task error: {e}")
                self.stats["tasks_failed"] += 1
    
    async def _speak(self, text: str):
        """Text to speech"""
        if self.speech_engine:
            self.speech_engine.say(text)
            self.speech_engine.runAndWait()
    
    async def _transcribe_audio(self, audio_path: str) -> Dict:
        """Transcribe audio to text"""
        if not self.recognizer:
            return {"error": "Speech recognition not available"}
        
        try:
            import speech_recognition as sr
            with sr.AudioFile(audio_path) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)
                return {"text": text, "confidence": 90}
        except Exception as e:
            return {"error": str(e)}
    
    def speak(self, text: str) -> Dict:
        """Queue text to speak"""
        self.audio_queue.append({
            "type": "speak",
            "text": text,
            "queued_at": datetime.now().isoformat()
        })
        return {"status": "queued"}
    
    def listen(self, duration: int = 5) -> Dict:
        """Listen for voice input"""
        if not self.recognizer:
            return {"error": "Speech recognition not available"}
        
        try:
            import speech_recognition as sr
            with sr.Microphone() as source:
                print("Listening...")
                audio = self.recognizer.listen(source, timeout=duration)
                text = self.recognizer.recognize_google(audio)
                return {"text": text, "status": "success"}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# DAEMON 11: DATA DRAKE - Data Analysis
# ============================================================================
class DataDrakeDaemon(BaseDaemon):
    """
    Data analysis daemon for processing, analyzing,
    and visualizing data.
    """
    
    def __init__(self):
        super().__init__(
            name="Data Drake",
            daemon_id="data_drake_11",
            description="Data Analysis & Processing"
        )
        self.datasets = {}
        self.analysis_queue = []
        self.visualizations = {}
        
    async def _initialize(self):
        """Initialize data analysis"""
        logger.info("[Data Drake] Initializing data analysis...")
        
    async def _main_loop(self):
        """Main data analysis loop"""
        while self.is_running:
            try:
                # Process analysis queue
                await self._process_analysis_queue()
                
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"[Data Drake] Error: {e}")
                await asyncio.sleep(1)
    
    async def _process_analysis_queue(self):
        """Process analysis tasks"""
        while self.analysis_queue:
            task = self.analysis_queue.pop(0)
            try:
                result = await self._analyze_data(task['data'], task['analysis_type'])
                if task.get('callback'):
                    task['callback'](result)
                self.stats["tasks_completed"] += 1
            except Exception as e:
                logger.error(f"[Data Drake] Analysis error: {e}")
                self.stats["tasks_failed"] += 1
    
    async def _analyze_data(self, data: Any, analysis_type: str) -> Dict:
        """Analyze data"""
        if analysis_type == 'statistics':
            return self._calculate_statistics(data)
        elif analysis_type == 'trends':
            return self._analyze_trends(data)
        return {"error": "Unknown analysis type"}
    
    def _calculate_statistics(self, data: List[float]) -> Dict:
        """Calculate statistics"""
        if not data:
            return {"error": "Empty data"}
        
        import statistics
        return {
            "count": len(data),
            "mean": statistics.mean(data),
            "median": statistics.median(data),
            "stdev": statistics.stdev(data) if len(data) > 1 else 0,
            "min": min(data),
            "max": max(data)
        }
    
    def _analyze_trends(self, data: List) -> Dict:
        """Linear regression trend analysis on numeric list or list of dicts with 'value' key"""
        try:
            values: List[float] = []
            if data and isinstance(data[0], dict):
                values = [float(d.get('value', 0)) for d in data]
            else:
                values = [float(v) for v in data]
            n = len(values)
            if n < 2:
                return {"error": "Need at least 2 data points"}
            # Linear regression: y = mx + b
            x_vals = list(range(n))
            x_mean = sum(x_vals) / n
            y_mean = sum(values) / n
            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
            denominator = sum((x - x_mean) ** 2 for x in x_vals)
            slope = numerator / denominator if denominator != 0 else 0
            intercept = y_mean - slope * x_mean
            # R-squared
            ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, values))
            ss_tot = sum((y - y_mean) ** 2 for y in values)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 1.0
            # Forecast next 5
            forecast = [round(slope * (n + i) + intercept, 4) for i in range(1, 6)]
            direction = "upward" if slope > 0 else "downward" if slope < 0 else "flat"
            return {
                "trend_direction": direction,
                "slope": round(slope, 6),
                "intercept": round(intercept, 6),
                "r_squared": round(r_squared, 4),
                "forecast_next_5": forecast,
                "data_points": n
            }
        except Exception as e:
            return {"error": str(e)}

    async def analyze_csv(self, file_path: str, columns: List[str] = None) -> Dict:
        """Load and analyze a CSV file"""
        import csv
        if not os.path.exists(file_path):
            return {"error": "File not found"}
        rows: List[Dict] = []
        with open(file_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        if not rows:
            return {"error": "Empty CSV"}
        # Analyze requested numeric columns
        report: Dict[str, Any] = {"file": file_path, "total_rows": len(rows), "columns": list(rows[0].keys()), "stats": {}}
        target_cols = columns or list(rows[0].keys())
        for col in target_cols:
            try:
                numeric = [float(r[col]) for r in rows if r.get(col) not in (None, '', 'nan')]
                if numeric:
                    report["stats"][col] = self._calculate_statistics(numeric)
            except Exception:
                pass
        return report

    async def analyze_json(self, file_path: str) -> Dict:
        """Load and analyze a JSON file (list of records expected)"""
        if not os.path.exists(file_path):
            return {"error": "File not found"}
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return {"file": file_path, "records": len(data), "sample": data[:3]}
        elif isinstance(data, dict):
            return {"file": file_path, "keys": list(data.keys()), "type": "object"}
        return {"file": file_path, "type": str(type(data).__name__)}

    def queue_analysis(self, data: Any, analysis_type: str, callback=None) -> Dict:
        """Queue analysis task"""
        self.analysis_queue.append({
            "data": data,
            "analysis_type": analysis_type,
            "callback": callback,
            "queued_at": datetime.now().isoformat()
        })
        return {"status": "queued", "queue_length": len(self.analysis_queue)}

    async def load_dataset(self, name: str, data: Any) -> Dict:
        """Load dataset into memory"""
        self.datasets[name] = data
        return {"status": "loaded", "name": name, "records": len(data) if hasattr(data, '__len__') else 'unknown'}

    def get_dataset_names(self) -> List[str]:
        """List loaded dataset names"""
        return list(self.datasets.keys())


# ============================================================================
# DAEMON 12: IRON CROWN - Hardware Control
# ============================================================================
class IronCrownDaemon(BaseDaemon):
    """
    Hardware control daemon for managing system hardware,
    sensors, and device interfaces.
    """
    
    def __init__(self):
        super().__init__(
            name="Iron Crown",
            daemon_id="iron_crown_12",
            description="Hardware Control & Sensors"
        )
        self.sensors = {}
        self.hardware_info = {}
        self.device_controls = {}
        
    async def _initialize(self):
        """Initialize hardware monitoring"""
        logger.info("[Iron Crown] Initializing hardware control...")
        self._gather_hardware_info()
        
    def _gather_hardware_info(self):
        """Gather hardware information"""
        try:
            import platform
            self.hardware_info = {
                "cpu": {
                    "count": psutil.cpu_count(),
                    "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
                },
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available
                },
                "disk": {
                    "partitions": [p._asdict() for p in psutil.disk_partitions()]
                },
                "platform": platform.platform()
            }
        except Exception as e:
            logger.error(f"[Iron Crown] Hardware info error: {e}")
            
    async def _main_loop(self):
        """Main hardware monitoring loop"""
        while self.is_running:
            try:
                await self._monitor_sensors()
                await self._update_hardware_stats()
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"[Iron Crown] Error: {e}")
                await asyncio.sleep(1)

    async def _monitor_sensors(self):
        """Monitor all available hardware sensors"""
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    self.sensors["temperatures"] = {
                        chip: [{"label": t.label, "current": t.current, "high": t.high, "critical": t.critical}
                               for t in readings]
                        for chip, readings in temps.items()
                    }
        except Exception:
            pass
        try:
            if hasattr(psutil, "sensors_fans"):
                fans = psutil.sensors_fans()
                if fans:
                    self.sensors["fans"] = {
                        chip: [{"label": f.label, "current": f.current} for f in readings]
                        for chip, readings in fans.items()
                    }
        except Exception:
            pass
        try:
            if hasattr(psutil, "sensors_battery"):
                bat = psutil.sensors_battery()
                if bat:
                    self.sensors["battery"] = {
                        "percent": bat.percent,
                        "secsleft": bat.secsleft,
                        "power_plugged": bat.power_plugged
                    }
        except Exception:
            pass
        try:
            net_if = psutil.net_if_stats()
            self.sensors["network_interfaces"] = {
                iface: {"isup": stats.isup, "speed": stats.speed, "mtu": stats.mtu}
                for iface, stats in net_if.items()
            }
        except Exception:
            pass

    async def _update_hardware_stats(self):
        """Update real-time hardware statistics"""
        try:
            self.hardware_info['cpu']['percent'] = psutil.cpu_percent(interval=None)
            self.hardware_info['cpu']['per_core'] = psutil.cpu_percent(percpu=True)
            mem = psutil.virtual_memory()
            self.hardware_info['memory']['percent'] = mem.percent
            self.hardware_info['memory']['used'] = mem.used
            self.hardware_info['memory']['available'] = mem.available
            # Disk usage per partition
            disk_usage = {}
            for p in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    disk_usage[p.mountpoint] = {
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    }
                except Exception:
                    pass
            self.hardware_info['disk_usage'] = disk_usage
            self.hardware_info['timestamp'] = datetime.now().isoformat()
        except Exception as e:
            logger.debug(f"[Iron Crown] Stat update error: {e}")

    def get_hardware_info(self) -> Dict:
        """Get full hardware information including sensors"""
        return {"hardware": self.hardware_info, "sensors": self.sensors}

    async def control_device(self, device_type: str, action: str, params: Dict = None) -> Dict:
        """Control hardware devices — brightness, volume, power"""
        params = params or {}
        try:
            if device_type == "display" and action == "brightness":
                level = params.get("level", 50)  # 0-100
                if os.name == 'nt':
                    import subprocess
                    # Use PowerShell WMI to set brightness on Windows
                    script = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
                    subprocess.run(["powershell", "-Command", script], capture_output=True)
                return {"device": device_type, "action": action, "level": level, "status": "applied"}
            elif device_type == "audio" and action == "volume":
                level = params.get("level", 50)
                if os.name == 'nt':
                    import subprocess
                    script = f"$obj = New-Object -ComObject WScript.Shell; for ($i=0;$i -lt 50;$i++){{$obj.SendKeys([char]174)}}; for ($i=0;$i -lt [math]::Round({level}/2);$i++){{$obj.SendKeys([char]175)}}"
                    subprocess.run(["powershell", "-Command", script], capture_output=True)
                return {"device": device_type, "action": action, "level": level, "status": "applied"}
            elif device_type == "power" and action in ("shutdown", "restart", "sleep"):
                import subprocess
                if action == "shutdown":
                    cmd = "shutdown /s /t 60" if os.name == 'nt' else "shutdown -h +1"
                elif action == "restart":
                    cmd = "shutdown /r /t 60" if os.name == 'nt' else "shutdown -r +1"
                else:  # sleep
                    cmd = "rundll32.exe powrprof.dll,SetSuspendState 0,1,0" if os.name == 'nt' else "systemctl suspend"
                subprocess.Popen(cmd, shell=True)
                return {"device": device_type, "action": action, "status": "initiated", "warning": "Will execute in 60s for shutdown/restart"}
            else:
                return {"device": device_type, "action": action, "status": "unsupported",
                        "supported": ["display/brightness", "audio/volume", "power/shutdown|restart|sleep"]}
        except Exception as e:
            return {"device": device_type, "action": action, "status": "error", "error": str(e)}

    async def get_process_list(self, sort_by: str = "cpu", limit: int = 20) -> List[Dict]:
        """Get top processes sorted by cpu or memory"""
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        key = 'cpu_percent' if sort_by == 'cpu' else 'memory_percent'
        procs.sort(key=lambda x: x.get(key) or 0, reverse=True)
        return procs[:limit]


# ============================================================================
# DAEMON 13: CHRONOS - Time & Prediction
# ============================================================================
class ChronosDaemon(BaseDaemon):
    """
    Time and prediction daemon for scheduling, forecasting,
    and predictive analytics.
    """
    
    def __init__(self):
        super().__init__(
            name="Chronos",
            daemon_id="chronos_13",
            description="Time & Prediction Engine"
        )
        self.time_events = []
        self.predictions = {}
        self.models = {}
        
    async def _initialize(self):
        """Initialize prediction engine and load snapshots"""
        logger.info("[Chronos] Initializing time and prediction systems...")
        self.snapshot_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "igris_snapshots"
        )
        os.makedirs(self.snapshot_dir, exist_ok=True)
        self._load_event_history()

    def _load_event_history(self):
        """Load persisted time events from disk"""
        history_path = os.path.join(self.snapshot_dir, "chronos_events.json")
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r') as f:
                    raw = json.load(f)
                # Restore trigger_time as datetime
                for ev in raw:
                    if isinstance(ev.get('trigger_time'), str):
                        try:
                            ev['trigger_time'] = datetime.fromisoformat(ev['trigger_time'])
                        except Exception:
                            ev['trigger_time'] = datetime.now()
                self.time_events = raw
                logger.info(f"[Chronos] Loaded {len(self.time_events)} events from history")
            except Exception as e:
                logger.warning(f"[Chronos] Could not load event history: {e}")

    def _save_event_history(self):
        """Persist time events to disk"""
        history_path = os.path.join(self.snapshot_dir, "chronos_events.json")
        try:
            serializable = []
            for ev in self.time_events:
                row = dict(ev)
                if isinstance(row.get('trigger_time'), datetime):
                    row['trigger_time'] = row['trigger_time'].isoformat()
                serializable.append(row)
            with open(history_path, 'w') as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            logger.error(f"[Chronos] Could not save event history: {e}")

    async def _main_loop(self):
        """Main time/prediction loop — checks events every second, snapshots hourly"""
        last_snapshot = time.time()
        while self.is_running:
            try:
                now = datetime.now()
                # Fire due events
                for event in self.time_events:
                    trigger = event.get('trigger_time')
                    if isinstance(trigger, str):
                        try:
                            trigger = datetime.fromisoformat(trigger)
                            event['trigger_time'] = trigger
                        except Exception:
                            continue
                    if trigger <= now and not event.get('triggered'):
                        await self._trigger_time_event(event)
                # Hourly auto-snapshot
                if time.time() - last_snapshot >= 3600:
                    await self.take_snapshot(reason="auto_hourly")
                    last_snapshot = time.time()
                await self._update_predictions()
                self.stats["last_activity"] = datetime.now().isoformat()
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"[Chronos] Error: {e}")
                await asyncio.sleep(1)

    async def _trigger_time_event(self, event: Dict):
        """Trigger a time event and optionally execute its action"""
        event['triggered'] = True
        event['triggered_at'] = datetime.now().isoformat()
        logger.info(f"[Chronos] Time event triggered: {event['name']}")
        self.stats["tasks_completed"] = self.stats.get("tasks_completed", 0) + 1
        action = event.get('action', {})
        act_type = action.get('type')
        try:
            if act_type == 'snapshot':
                await self.take_snapshot(reason=event['name'])
            elif act_type == 'shell':
                import subprocess
                subprocess.Popen(action.get('command', ''), shell=True)
            elif act_type == 'log':
                logger.info(f"[Chronos] Event log: {action.get('message', '')}")
        except Exception as e:
            logger.error(f"[Chronos] Event action failed: {e}")
        # Handle recurring events
        if event.get('recurring') and event.get('interval_minutes'):
            from datetime import timedelta
            event['triggered'] = False
            event['trigger_time'] = datetime.now() + timedelta(minutes=event['interval_minutes'])
            self._save_event_history()

    async def _update_predictions(self):
        """Sample CPU/memory into rolling predictions buffer"""
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            ts = datetime.now().isoformat()
            self.predictions.setdefault('cpu_history', []).append({'value': cpu, 'ts': ts})
            self.predictions.setdefault('mem_history', []).append({'value': mem, 'ts': ts})
            # Keep only last 1000 samples
            self.predictions['cpu_history'] = self.predictions['cpu_history'][-1000:]
            self.predictions['mem_history'] = self.predictions['mem_history'][-1000:]
            self.stats["predictions_updated"] = self.stats.get("predictions_updated", 0) + 1
        except Exception:
            pass

    async def take_snapshot(self, reason: str = "manual") -> Dict:
        """Take a real system snapshot (processes + resource state)"""
        try:
            snapshot_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    procs.append(p.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            snapshot = {
                "id": snapshot_id,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory": psutil.virtual_memory()._asdict(),
                "disk": {p.mountpoint: psutil.disk_usage(p.mountpoint)._asdict()
                         for p in psutil.disk_partitions() if p.fstype},
                "process_count": len(procs),
                "top_processes": sorted(procs, key=lambda x: x.get('cpu_percent') or 0, reverse=True)[:10]
            }
            path = os.path.join(self.snapshot_dir, f"snapshot_{snapshot_id}.json")
            with open(path, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)
            logger.info(f"[Chronos] Snapshot saved: {path}")
            return {"status": "saved", "snapshot_id": snapshot_id, "path": path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def list_snapshots(self) -> List[Dict]:
        """List all saved snapshots"""
        if not hasattr(self, 'snapshot_dir') or not os.path.exists(self.snapshot_dir):
            return []
        snapshots = []
        for fn in sorted(os.listdir(self.snapshot_dir)):
            if fn.startswith('snapshot_') and fn.endswith('.json'):
                fp = os.path.join(self.snapshot_dir, fn)
                snapshots.append({
                    "filename": fn,
                    "path": fp,
                    "size_bytes": os.path.getsize(fp),
                    "created": datetime.fromtimestamp(os.path.getctime(fp)).isoformat()
                })
        return snapshots

    def schedule_event(self, name: str, trigger_time: datetime, action: Dict,
                       recurring: bool = False, interval_minutes: int = 60) -> Dict:
        """Schedule a time event with optional recurrence"""
        event = {
            "id": f"{int(datetime.now().timestamp()*1000)}",
            "name": name,
            "trigger_time": trigger_time,
            "action": action,
            "triggered": False,
            "recurring": recurring,
            "interval_minutes": interval_minutes if recurring else None,
            "created_at": datetime.now().isoformat()
        }
        self.time_events.append(event)
        self._save_event_history()
        return {"status": "scheduled", "event_id": event['id'],
                "trigger_at": trigger_time.isoformat() if isinstance(trigger_time, datetime) else trigger_time}

    async def predict_trend(self, data: List[float], periods: int = 5) -> Dict:
        """Linear regression trend prediction"""
        if len(data) < 2:
            return {"error": "Insufficient data — need at least 2 points"}
        n = len(data)
        x_vals = list(range(n))
        x_mean = sum(x_vals) / n
        y_mean = sum(data) / n
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, data))
        den = sum((x - x_mean) ** 2 for x in x_vals)
        slope = num / den if den != 0 else 0
        intercept = y_mean - slope * x_mean
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, data))
        ss_tot = sum((y - y_mean) ** 2 for y in data)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 1.0
        predictions = [round(slope * (n + i) + intercept, 4) for i in range(1, periods + 1)]
        direction = "upward" if slope > 0.001 else "downward" if slope < -0.001 else "flat"
        return {
            "predictions": predictions,
            "slope": round(slope, 6),
            "r_squared": round(r_squared, 4),
            "confidence": round(min(r_squared * 100, 99), 1),
            "direction": direction,
            "periods": periods,
            "timestamp": datetime.now().isoformat()
        }

    def get_system_uptime(self) -> Dict:
        """Get system uptime in readable form"""
        uptime_sec = time.time() - psutil.boot_time()
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        return {
            "uptime_seconds": round(uptime_sec),
            "uptime_formatted": f"{days}d {hours}h {minutes}m",
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }

    def get_resource_forecast(self, resource: str = "cpu", periods: int = 10) -> Dict:
        """Forecast CPU or memory usage based on historical samples"""
        history = self.predictions.get(f"{resource}_history", [])
        if len(history) < 5:
            return {"error": "Not enough history yet — wait for more samples"}
        values = [h['value'] for h in history[-200:]]
        n = len(values)
        x_vals = list(range(n))
        x_mean = sum(x_vals) / n
        y_mean = sum(values) / n
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
        den = sum((x - x_mean) ** 2 for x in x_vals)
        slope = num / den if den != 0 else 0
        intercept = y_mean - slope * x_mean
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, values))
        ss_tot = sum((y - y_mean) ** 2 for y in values)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 1.0
        result = {
            "predictions": [round(slope * (n + i) + intercept, 4) for i in range(1, periods + 1)],
            "slope": round(slope, 6),
            "r_squared": round(r_squared, 4),
            "confidence": round(min(r_squared * 100, 99), 1),
            "direction": "upward" if slope > 0.001 else "downward" if slope < -0.001 else "flat",
            "periods": periods,
            "timestamp": datetime.now().isoformat(),
        }
        result["resource"] = resource
        result["history_samples"] = len(values)
        return result


# Global daemon master instance
daemon_master = DaemonMaster()
