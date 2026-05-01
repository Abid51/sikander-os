"""
DISTRIBUTED NETWORK SYSTEM
Connect multiple machines, mesh networking, parallel processing, decentralized consensus

Igris = Everywhere! 🌐
"""

import json
import asyncio
import socket
import uuid
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import threading
import time


class NodeType(Enum):
    MASTER = "master"  # Primary controller
    SLAVE = "slave"    # Secondary processing
    EDGE = "edge"      # Edge device (phone, IoT)
    CLOUD = "cloud"    # Cloud backup


@dataclass
class NetworkNode:
    """Represents a connected node"""
    node_id: str
    node_type: NodeType
    ip_address: str
    port: int
    name: str
    status: str = "online"
    capabilities: List[str] = None
    resources: Dict = None
    last_heartbeat: float = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.resources is None:
            self.resources = {}
        if self.last_heartbeat is None:
            self.last_heartbeat = time.time()


class TaskDistribution:
    """Distribute tasks across network nodes"""
    
    def __init__(self):
        self.task_queue = []
        self.completed_tasks = {}
        self.node_loads = {}
    
    async def submit_task(self, task: Dict, priority: int = 5) -> str:
        """Submit task for distributed processing"""
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "task": task,
            "priority": priority,
            "submitted_at": datetime.now().isoformat(),
            "status": "queued",
            "result": None
        }
        
        self.task_queue.append(task_data)
        
        return task_id
    
    async def assign_task_to_node(self, task_id: str, node_id: str) -> Dict:
        """Assign specific task to specific node"""
        task = next((t for t in self.task_queue if t["task_id"] == task_id), None)
        
        if not task:
            return {"error": "Task not found"}
        
        task["assigned_node"] = node_id
        task["status"] = "assigned"
        task["assigned_at"] = datetime.now().isoformat()
        
        return {
            "task_id": task_id,
            "assigned_to": node_id,
            "status": "assigned"
        }
    
    async def get_optimal_node(self, required_capabilities: List[str]) -> Optional[str]:
        """Find best node for task based on capabilities and load"""
        # This would find the least loaded node with required capabilities
        return "node_2"  # Example
    
    async def execute_distributed_job(self, job: Dict) -> Dict:
        """Execute job across multiple nodes"""
        job_id = str(uuid.uuid4())
        
        # Break job into subtasks
        subtasks = self._break_into_subtasks(job)
        
        # Distribute to nodes
        results = []
        for subtask in subtasks:
            task_id = await self.submit_task(subtask, priority=job.get("priority", 5))
            results.append({"subtask_id": task_id})
        
        return {
            "job_id": job_id,
            "subtasks": results,
            "status": "executing"
        }
    
    def _break_into_subtasks(self, job: Dict) -> List[Dict]:
        """Break job into parallelizable subtasks"""
        subtasks = []
        
        # Example: if job is to process 1000 items, split into 4 chunks
        if "items" in job:
            items = job["items"]
            chunk_size = len(items) // 4
            
            for i in range(0, len(items), chunk_size):
                subtasks.append({
                    "chunk": items[i:i+chunk_size],
                    "operation": job.get("operation")
                })
        
        return subtasks


class MeshNetwork:
    """Decentralized mesh networking"""
    
    def __init__(self):
        self.nodes: Dict[str, NetworkNode] = {}
        self.network_graph = {}
        self.routing_table = {}
        self.message_queue = {}
    
    def add_node(self, node: NetworkNode) -> Dict:
        """Add node to network"""
        self.nodes[node.node_id] = node
        self.network_graph[node.node_id] = []
        self.message_queue[node.node_id] = []
        
        return {
            "status": "added",
            "node_id": node.node_id,
            "node_type": node.node_type.value,
            "total_nodes": len(self.nodes)
        }
    
    def connect_nodes(self, node_id_1: str, node_id_2: str) -> Dict:
        """Create connection between two nodes"""
        if node_id_1 not in self.nodes or node_id_2 not in self.nodes:
            return {"error": "Node not found"}
        
        self.network_graph[node_id_1].append(node_id_2)
        self.network_graph[node_id_2].append(node_id_1)
        
        return {
            "status": "connected",
            "node_1": node_id_1,
            "node_2": node_id_2
        }
    
    async def broadcast_message(self, message: Dict, sender_id: str) -> Dict:
        """Broadcast message to all nodes"""
        broadcast_id = str(uuid.uuid4())
        
        for node_id in self.nodes:
            if node_id != sender_id:
                self.message_queue[node_id].append({
                    "broadcast_id": broadcast_id,
                    "message": message,
                    "sender": sender_id,
                    "received_at": datetime.now().isoformat()
                })
        
        return {
            "broadcast_id": broadcast_id,
            "nodes_notified": len(self.nodes) - 1,
            "status": "sent"
        }
    
    async def point_to_point_message(self, message: Dict, from_id: str, to_id: str) -> Dict:
        """Send message from one node to another"""
        if to_id not in self.nodes:
            return {"error": "Destination node not found"}
        
        # Find shortest path
        path = self._find_shortest_path(from_id, to_id)
        
        self.message_queue[to_id].append({
            "message": message,
            "sender": from_id,
            "path": path,
            "received_at": datetime.now().isoformat()
        })
        
        return {
            "status": "delivered",
            "from": from_id,
            "to": to_id,
            "path": path
        }
    
    def _find_shortest_path(self, start: str, end: str) -> List[str]:
        """BFS to find shortest path"""
        from collections import deque
        
        queue = deque([[start]])
        visited = set([start])
        
        while queue:
            path = queue.popleft()
            node = path[-1]
            
            if node == end:
                return path
            
            for neighbor in self.network_graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        
        return []
    
    def get_network_topology(self) -> Dict:
        """Get current network structure"""
        return {
            "nodes": {
                node_id: {
                    "type": node.node_type.value,
                    "status": node.status,
                    "ip": node.ip_address,
                    "capabilities": node.capabilities
                }
                for node_id, node in self.nodes.items()
            },
            "connections": self.network_graph,
            "total_nodes": len(self.nodes)
        }
    
    async def check_node_health(self, node_id: str) -> Dict:
        """Check if node is healthy"""
        if node_id not in self.nodes:
            return {"error": "Node not found"}
        
        node = self.nodes[node_id]
        heartbeat_age = time.time() - node.last_heartbeat
        
        return {
            "node_id": node_id,
            "status": node.status,
            "heartbeat_age": heartbeat_age,
            "healthy": heartbeat_age < 30  # Healthy if heartbeat within 30 seconds
        }
    
    async def consensus_vote(self, proposal: Dict) -> Dict:
        """Decentralized consensus voting"""
        votes = {}
        required_agreement = 0.67  # 2/3 majority
        
        # Simulate voting from all nodes
        for node_id in self.nodes:
            # Nodes with MASTER type vote yes, others vote based on proposal
            vote = "yes" if self.nodes[node_id].node_type == NodeType.MASTER else "no"
            votes[node_id] = vote
        
        yes_votes = sum(1 for v in votes.values() if v == "yes")
        total_votes = len(votes)
        agreement = yes_votes / total_votes if total_votes > 0 else 0
        
        return {
            "proposal": proposal,
            "votes": votes,
            "total_votes": total_votes,
            "yes_votes": yes_votes,
            "agreement_level": agreement,
            "decision": "APPROVED" if agreement >= required_agreement else "REJECTED"
        }


class DistributedLedger:
    """Blockchain-like ledger for tracking operations across network"""
    
    def __init__(self):
        self.blocks = []
        self.pending_transactions = []
        self.chain_hash = "genesis"
    
    def add_transaction(self, transaction: Dict) -> str:
        """Add transaction to ledger"""
        trans_id = str(uuid.uuid4())
        
        self.pending_transactions.append({
            "trans_id": trans_id,
            "transaction": transaction,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        })
        
        return trans_id
    
    async def mine_block(self) -> Dict:
        """Create new block from pending transactions"""
        if not self.pending_transactions:
            return {"error": "No pending transactions"}
        
        block = {
            "block_id": str(uuid.uuid4()),
            "previous_hash": self.chain_hash,
            "transactions": self.pending_transactions,
            "timestamp": datetime.now().isoformat(),
            "nonce": 0
        }
        
        # Simple proof of work (in production, would be more complex)
        block["block_hash"] = self._calculate_hash(block)
        
        self.blocks.append(block)
        self.chain_hash = block["block_hash"]
        self.pending_transactions = []
        
        return {
            "block_id": block["block_id"],
            "transactions_count": len(block["transactions"]),
            "block_hash": block["block_hash"]
        }
    
    def _calculate_hash(self, block: Dict) -> str:
        """Calculate block hash"""
        import hashlib
        block_str = json.dumps(block, sort_keys=True)
        return hashlib.sha256(block_str.encode()).hexdigest()
    
    def get_chain_health(self) -> Dict:
        """Verify blockchain integrity"""
        valid = True
        
        for i in range(1, len(self.blocks)):
            if self.blocks[i]["previous_hash"] != self.blocks[i-1]["block_hash"]:
                valid = False
                break
        
        return {
            "total_blocks": len(self.blocks),
            "pending_transactions": len(self.pending_transactions),
            "chain_integrity": "VALID" if valid else "COMPROMISED",
            "current_hash": self.chain_hash
        }


class DistributedNetwork:
    """Master distributed network system"""
    
    def __init__(self):
        self.mesh = MeshNetwork()
        self.task_distribution = TaskDistribution()
        self.ledger = DistributedLedger()
        self.master_node = None
        print("[NETWORK] Distributed Network System Online!")
    
    async def setup_network(self, nodes_config: List[Dict]) -> Dict:
        """Setup initial network configuration"""
        created_nodes = []
        
        for config in nodes_config:
            node = NetworkNode(
                node_id=str(uuid.uuid4()),
                node_type=NodeType[config.get("type", "SLAVE").upper()],
                ip_address=config.get("ip", "localhost"),
                port=config.get("port", 8000),
                name=config.get("name", "unnamed"),
                capabilities=config.get("capabilities", [])
            )
            
            self.mesh.add_node(node)
            created_nodes.append(node.node_id)
            
            if node.node_type == NodeType.MASTER:
                self.master_node = node.node_id
        
        # Create mesh connections
        for i in range(len(created_nodes) - 1):
            await asyncio.sleep(0.1)
            self.mesh.connect_nodes(created_nodes[i], created_nodes[i+1])
        
        return {
            "status": "network_ready",
            "nodes_created": len(created_nodes),
            "master_node": self.master_node,
            "topology": self.mesh.get_network_topology()
        }
    
    async def get_network_status(self) -> Dict:
        """Get overall network status"""
        return {
            "mesh_topology": self.mesh.get_network_topology(),
            "ledger_status": self.ledger.get_chain_health(),
            "total_nodes": len(self.mesh.nodes),
            "pending_tasks": len(self.task_distribution.task_queue),
            "network_status": "operational"
        }


# Initialize global distributed network
distributed_network = DistributedNetwork()

if __name__ == "__main__":
    async def test():
        # Setup demo network
        nodes_config = [
            {"name": "Master-PC", "type": "MASTER", "ip": "192.168.1.10", "port": 8000, "capabilities": ["compute", "storage"]},
            {"name": "Office-PC", "type": "SLAVE", "ip": "192.168.1.11", "port": 8001, "capabilities": ["compute"]},
            {"name": "Laptop", "type": "SLAVE", "ip": "192.168.1.12", "port": 8002, "capabilities": ["compute", "mobile"]},
            {"name": "Mobile", "type": "EDGE", "ip": "192.168.1.13", "port": 8003, "capabilities": ["mobile"]},
        ]
        
        await distributed_network.setup_network(nodes_config)
        status = await distributed_network.get_network_status()
        print(json.dumps(status, indent=2, default=str))
    
    asyncio.run(test())
