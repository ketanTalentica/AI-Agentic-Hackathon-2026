"""
LangGraph-based Agent System
Base classes and event-driven communication
"""
import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from pydantic import BaseModel
from enum import Enum

class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"

class EventType(Enum):
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    DATA_AVAILABLE = "data_available"
    WORKFLOW_COMPLETE = "workflow_complete"

@dataclass
class AgentEvent:
    event_type: EventType
    agent_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""

class EventBus:
    """Centralized event bus for agent communication"""
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self.event_history: List[AgentEvent] = []
        
    def subscribe(self, event_type: EventType, callback: Callable):
        """Subscribe to events of a specific type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        
    def publish(self, event: AgentEvent):
        """Publish an event to all subscribers"""
        self.event_history.append(event)
        
        if event.event_type in self.subscribers:
            for callback in self.subscribers[event.event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(event))
                    else:
                        callback(event)
                except Exception as e:
                    print(f"[EventBus] Error in callback: {e}")

class StateStore:
    """Centralized state management"""
    
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        
    async def set(self, key: str, value: Any):
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
            
        async with self.locks[key]:
            self.data[key] = value
            
    async def get(self, key: str, default=None):
        return self.data.get(key, default)
        
    async def wait_for(self, key: str, timeout: float = 30.0):
        """Wait for a key to become available"""
        start_time = time.time()
        while key not in self.data:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Timeout waiting for key: {key}")
            await asyncio.sleep(0.1)
        return self.data[key]
        
    def has_key(self, key: str) -> bool:
        return key in self.data
        
    def get_all(self) -> Dict[str, Any]:
        return self.data.copy()

class BaseAgent(ABC):
    """Base class for all LangGraph agents"""
    
    def __init__(self, agent_id: str, event_bus: EventBus, state_store: StateStore, debug: bool = False):
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.state_store = state_store
        self.debug = debug
        self.status = AgentStatus.IDLE
        self.dependencies: List[str] = []
        self.output_keys: List[str] = []
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventType.DATA_AVAILABLE, self._on_data_available)
        
    async def _on_data_available(self, event: AgentEvent):
        """Handle data availability events"""
        if self.status == AgentStatus.WAITING:
            # Check if all dependencies are met
            dependencies_met = await self._check_dependencies()
            if dependencies_met:
                await self.execute_async()
                
    async def _check_dependencies(self) -> bool:
        """Check if all dependencies are satisfied"""
        for dep in self.dependencies:
            if not self.state_store.has_key(f"{dep}_output"):
                return False
        return True
        
    async def execute_async(self):
        """Async execution wrapper"""
        try:
            self.status = AgentStatus.RUNNING
            self._publish_event(EventType.AGENT_STARTED)
            
            if self.debug:
                print(f"[{self.agent_id}] Starting execution...")
                
            # Execute the agent logic
            result = await self._execute_impl()
            
            # Store output in state
            await self.state_store.set(f"{self.agent_id}_output", result)
            
            # Update status and notify
            self.status = AgentStatus.COMPLETED
            self._publish_event(EventType.AGENT_COMPLETED, {"result": result})
            self._publish_event(EventType.DATA_AVAILABLE, {"agent": self.agent_id})
            
            if self.debug:
                print(f"[{self.agent_id}] Completed successfully")
                
        except Exception as e:
            self.status = AgentStatus.FAILED
            self._publish_event(EventType.AGENT_FAILED, {"error": str(e)})
            if self.debug:
                print(f"[{self.agent_id}] Failed: {e}")
            raise
            
    @abstractmethod
    async def _execute_impl(self) -> Dict[str, Any]:
        """Implement agent-specific logic"""
        pass
        
    def _publish_event(self, event_type: EventType, data: Dict[str, Any] = None):
        """Publish an event"""
        event = AgentEvent(
            event_type=event_type,
            agent_id=self.agent_id,
            data=data or {}
        )
        self.event_bus.publish(event)
        
    async def wait_for_completion(self, timeout: float = 60.0):
        """Wait for agent to complete"""
        start_time = time.time()
        while self.status not in [AgentStatus.COMPLETED, AgentStatus.FAILED]:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Agent {self.agent_id} timeout")
            await asyncio.sleep(0.1)
            
        if self.status == AgentStatus.FAILED:
            raise RuntimeError(f"Agent {self.agent_id} failed")
            
        return await self.state_store.get(f"{self.agent_id}_output")

class WorkflowMonitor:
    """Monitors workflow execution and provides insights"""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.metrics = {
            "agents_started": 0,
            "agents_completed": 0,
            "agents_failed": 0,
            "total_execution_time": 0,
            "agent_timings": {}
        }
        
        # Subscribe to all events for monitoring
        self.event_bus.subscribe(EventType.AGENT_STARTED, self._on_agent_started)
        self.event_bus.subscribe(EventType.AGENT_COMPLETED, self._on_agent_completed)
        self.event_bus.subscribe(EventType.AGENT_FAILED, self._on_agent_failed)
        
    async def _on_agent_started(self, event: AgentEvent):
        self.metrics["agents_started"] += 1
        self.metrics["agent_timings"][event.agent_id] = {"start": event.timestamp}
        
    async def _on_agent_completed(self, event: AgentEvent):
        self.metrics["agents_completed"] += 1
        if event.agent_id in self.metrics["agent_timings"]:
            start_time = self.metrics["agent_timings"][event.agent_id]["start"]
            duration = event.timestamp - start_time
            self.metrics["agent_timings"][event.agent_id]["duration"] = duration
            
    async def _on_agent_failed(self, event: AgentEvent):
        self.metrics["agents_failed"] += 1
        
    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.copy()
        
    def print_summary(self):
        print("\\n=== Workflow Execution Summary ===")
        print(f"Agents Started: {self.metrics['agents_started']}")
        print(f"Agents Completed: {self.metrics['agents_completed']}")
        print(f"Agents Failed: {self.metrics['agents_failed']}")
        
        if self.metrics["agent_timings"]:
            print("\\nAgent Execution Times:")
            for agent_id, timing in self.metrics["agent_timings"].items():
                if "duration" in timing:
                    print(f"  {agent_id}: {timing['duration']:.2f}s")