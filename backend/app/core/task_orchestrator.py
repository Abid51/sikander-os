"""
Advanced Task Orchestration & Job Queue System
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Callable, Optional
from datetime import datetime, timedelta
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """Task status enumeration"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class Task:
    """Individual task representation"""
    
    def __init__(self, task_type: str, command: str, parameters: Dict[str, Any],
                 user_id: Optional[int] = None, priority: int = 5):
        self.id = str(uuid.uuid4())
        self.task_type = task_type
        self.command = command
        self.parameters = parameters
        self.user_id = user_id
        self.priority = priority
        self.status = TaskStatus.QUEUED
        self.retry_count = 0
        self.max_retries = 3
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.dependencies: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "id": self.id,
            "task_type": self.task_type,
            "command": self.command,
            "parameters": self.parameters,
            "user_id": self.user_id,
            "priority": self.priority,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class TaskOrchestrator:
    """Advanced task orchestration and job queue system"""
    
    def __init__(self, max_workers: int = 5):
        self.task_queue: Dict[str, Task] = {}
        self.running_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.max_workers = max_workers
        self.handlers: Dict[str, Callable] = {}
        self.is_running = False
    
    def register_handler(self, task_type: str, handler: Callable) -> None:
        """Register task type handler"""
        self.handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")
    
    async def submit_task(self, task_type: str, command: str, parameters: Dict[str, Any],
                         user_id: Optional[int] = None, priority: int = 5,
                         dependencies: List[str] = None) -> str:
        """Submit new task to queue"""
        task = Task(task_type, command, parameters, user_id, priority)
        
        if dependencies:
            task.dependencies = dependencies
        
        self.task_queue[task.id] = task
        logger.info(f"Task submitted: {task.id} ({task_type})")
        
        return task.id
    
    async def start_orchestration(self) -> None:
        """Start the orchestration engine"""
        self.is_running = True
        logger.info("Task orchestrator started")
        
        # Run worker tasks
        workers = [
            asyncio.create_task(self._worker())
            for _ in range(self.max_workers)
        ]
        
        await asyncio.gather(*workers)
    
    async def stop_orchestration(self) -> None:
        """Stop the orchestration engine"""
        self.is_running = False
        logger.info("Task orchestrator stopped")
    
    async def _worker(self) -> None:
        """Worker coroutine processing tasks"""
        while self.is_running:
            try:
                # Get next task with highest priority
                task = self._get_next_task()
                
                if not task:
                    await asyncio.sleep(1)
                    continue
                
                # Process task
                await self._process_task(task)
                
            except Exception as e:
                logger.error(f"Worker error: {str(e)}")
                await asyncio.sleep(1)
    
    def _get_next_task(self) -> Optional[Task]:
        """Get next task from queue (sorted by priority)"""
        if not self.task_queue:
            return None
        
        # Sort by priority (highest first) and creation time
        sorted_tasks = sorted(
            self.task_queue.values(),
            key=lambda t: (-t.priority, t.created_at)
        )
        
        if len(self.running_tasks) < self.max_workers:
            for task in sorted_tasks:
                deps_ready = all(dep_id in self.completed_tasks for dep_id in task.dependencies)
                if not deps_ready:
                    continue
                del self.task_queue[task.id]
                self.running_tasks[task.id] = task
                return task
        
        return None
    
    async def _check_dependencies(self, task: Task) -> bool:
        """Check if task dependencies are met"""
        if not task.dependencies:
            return True
        
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                return False
        
        return True
    
    async def _process_task(self, task: Task) -> None:
        """Process individual task"""
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.now()
        
        try:
            # Get handler for task type
            handler = self.handlers.get(task.task_type)
            
            if not handler:
                raise ValueError(f"No handler for task type: {task.task_type}")
            
            # Execute handler
            result = await handler(task.command, task.parameters)
            
            # Mark as completed
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # Move to completed
            del self.running_tasks[task.id]
            self.completed_tasks[task.id] = task
            
            logger.info(f"Task completed: {task.id}")
            
        except Exception as e:
            logger.error(f"Task failed: {task.id} - {str(e)}")
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                task.error = str(e)
                
                # Re-queue task
                del self.running_tasks[task.id]
                self.task_queue[task.id] = task
                
                logger.info(f"Task requeued: {task.id} (attempt {task.retry_count})")
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now()
                
                # Move to completed
                del self.running_tasks[task.id]
                self.completed_tasks[task.id] = task
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel pending task"""
        if task_id in self.task_queue:
            task = self.task_queue[task_id]
            task.status = TaskStatus.CANCELLED
            del self.task_queue[task_id]
            self.completed_tasks[task_id] = task
            return True
        
        return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        # Check all locations
        for task_dict in [self.task_queue, self.running_tasks, self.completed_tasks]:
            if task_id in task_dict:
                return task_dict[task_id].to_dict()
        
        return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            "queued_tasks": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "total_tasks": len(self.task_queue) + len(self.running_tasks) + len(self.completed_tasks),
            "max_workers": self.max_workers
        }
    
    def get_recent_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent completed tasks"""
        tasks = sorted(
            self.completed_tasks.values(),
            key=lambda t: t.completed_at or t.created_at,
            reverse=True
        )
        
        return [task.to_dict() for task in tasks[:limit]]


# Initialize global orchestrator
task_orchestrator = TaskOrchestrator(max_workers=10)
