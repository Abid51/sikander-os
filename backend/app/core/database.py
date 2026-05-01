"""
Advanced Database Layer for Igris
SQLite with ORM capabilities
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Advanced database management system"""
    
    def __init__(self, db_path: str = "igris.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Voice Commands Log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS voice_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transcript TEXT NOT NULL,
                    intent TEXT,
                    confidence REAL,
                    language TEXT,
                    user_id INTEGER,
                    status TEXT,
                    response TEXT,
                    execution_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Users
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT,
                    api_key TEXT UNIQUE,
                    role TEXT DEFAULT 'user',
                    settings JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Modifications Log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS modifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    module_name TEXT,
                    modification_type TEXT,
                    description TEXT,
                    backup_file TEXT,
                    status TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Tasks/Jobs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    task_type TEXT,
                    command TEXT,
                    parameters JSON,
                    status TEXT,
                    priority INTEGER DEFAULT 5,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    result TEXT,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # System Events
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    module TEXT,
                    details JSON,
                    severity TEXT,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Performance Metrics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value REAL,
                    unit TEXT,
                    tags JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # API Access Log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    endpoint TEXT,
                    method TEXT,
                    status_code INTEGER,
                    response_time_ms INTEGER,
                    request_size INTEGER,
                    response_size INTEGER,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Plugins/Extensions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    version TEXT,
                    author TEXT,
                    description TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    config JSON,
                    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Cache Store
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    ttl INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Chat sessions (integration tests)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id)')
            
            # Create indices for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_commands(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_voice_created ON voice_commands(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_ttl ON cache(ttl)')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def create_user(self, username: str, email: str, password_hash: str, api_key: str) -> Dict[str, Any]:
        """Create new user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, api_key, role, settings)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, email, password_hash, api_key, 'user', json.dumps({})))
                
                user_id = cursor.lastrowid
                return {"id": user_id, "username": username, "status": "created"}
        except sqlite3.IntegrityError:
            return {"error": "User already exists", "status": "failed"}

    def update_user_api_key(self, user_id: int, api_key: str) -> bool:
        """Update API key for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET api_key = ? WHERE id = ?",
                (api_key, user_id),
            )
            return cursor.rowcount > 0
    
    def log_voice_command(self, transcript: str, intent: str, confidence: float, 
                         language: str, user_id: Optional[int] = None) -> int:
        """Log voice command"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO voice_commands (transcript, intent, confidence, language, user_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (transcript, intent, confidence, language, user_id, 'pending'))
            
            return cursor.lastrowid
    
    def log_modification(self, user_id: int, module_name: str, mod_type: str, 
                        description: str, backup_file: str, status: str) -> int:
        """Log system modification"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO modifications (user_id, module_name, modification_type, description, backup_file, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, module_name, mod_type, description, backup_file, status))
            
            return cursor.lastrowid
    
    def create_task(self, user_id: int, task_type: str, command: str, 
                   parameters: Dict[str, Any], priority: int = 5) -> int:
        """Create background task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tasks (user_id, task_type, command, parameters, status, priority)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, task_type, command, json.dumps(parameters), 'queued', priority))
            
            return cursor.lastrowid
    
    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending tasks for processing"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tasks 
                WHERE status = 'queued' 
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def update_task(self, task_id: int, status: str, result: str = None, error: str = None) -> bool:
        """Update task status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE tasks 
                SET status = ?, result = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, result, error, task_id))
            
            return cursor.rowcount > 0
    
    def log_system_event(
        self,
        event_type: str,
        second: str,
        details: Any = None,
        *,
        severity: str = "INFO",
        level: str = None,
        metadata: Dict[str, Any] = None,
    ) -> int:
        """
        Log a system event.

        * ``(event_type, module, details_dict, *, severity=...)`` — full form
        * ``(event_type, message, *, level=...)`` — short form (integration tests)
        """
        sev = (level or severity or "INFO").upper()
        if details is not None and isinstance(details, dict):
            module, det = second, details
        else:
            module, det = "igris", {"message": second}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_events (event_type, module, details, severity, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (event_type, module, json.dumps(det), sev, json.dumps(metadata or {})))
            return cursor.lastrowid

    def store_conversation(self, session_id: str, role: str, content: str) -> int:
        """Append a turn to a chat session."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO conversations (session_id, role, content)
                VALUES (?, ?, ?)
                ''',
                (session_id, role, content),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_conversation_history(
        self, session_id: str, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Return ordered messages for a session."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT role, content, created_at
                FROM conversations
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?
                ''',
                (session_id, limit),
            )
            rows = cursor.fetchall()
        return [
            {"role": r[0], "content": r[1], "created_at": r[2]}
            for r in rows
        ]
    
    def log_metric(self, metric_name: str, metric_value: float, unit: str = "", 
                  tags: Dict[str, str] = None) -> int:
        """Log performance metric"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO metrics (metric_name, metric_value, unit, tags)
                VALUES (?, ?, ?, ?)
            ''', (metric_name, metric_value, unit, json.dumps(tags or {})))
            
            return cursor.lastrowid
    
    def log_api_access(self, user_id: Optional[int], endpoint: str, method: str, 
                      status_code: int, response_time_ms: int, ip_address: str, 
                      user_agent: str, req_size: int = 0, res_size: int = 0) -> int:
        """Log API access"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO api_logs (user_id, endpoint, method, status_code, response_time_ms, 
                                     request_size, response_size, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, endpoint, method, status_code, response_time_ms, 
                  req_size, res_size, ip_address, user_agent))
            
            return cursor.lastrowid
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user record by username."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, password_hash, api_key, role, settings, created_at "
                "FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a user record by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, password_hash, api_key, role, settings, created_at "
                "FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user record by API key."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, password_hash, api_key, role, settings, created_at "
                "FROM users WHERE api_key = ?",
                (api_key,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_user_password(self, user_id: int, new_hash: str) -> bool:
        """Update a user's password hash."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_hash, user_id)
            )
            return cursor.rowcount > 0

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Count records
            for table in ['voice_commands', 'users', 'tasks', 'modifications', 'plugins']:
                cursor.execute(f'SELECT COUNT(*) as count FROM {table}')
                stats[f'{table}_count'] = cursor.fetchone()['count']
            
            return stats
    
    def cache_set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set cache value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO cache (key, value, ttl, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (key, value, ttl))
            
            return cursor.rowcount > 0
    
    def cache_get(self, key: str) -> Optional[str]:
        """Get cache value (if not expired)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT value FROM cache 
                WHERE key = ? AND (
                    ttl = 0 OR (strftime('%s', 'now') - strftime('%s', created_at)) < ttl
                )
            ''', (key,))
            
            result = cursor.fetchone()
            return result['value'] if result else None
    
    def install_plugin(self, name: str, version: str, author: str, 
                      description: str, config: Dict[str, Any]) -> bool:
        """Register plugin"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO plugins (name, version, author, description, config)
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, version, author, description, json.dumps(config)))
                
                return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False
    
    def get_plugins(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """Get installed plugins"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM plugins'
            if enabled_only:
                query += ' WHERE enabled = 1'
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]


# Initialize global database instance
db = DatabaseManager(os.path.join(os.path.dirname(__file__), "..", "..", "igris.db"))
