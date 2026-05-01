"""
SMART HOME INTEGRATION
Control everything - Lights, Temperature, Security, Appliances

IoT Hub for total home automation
"""

import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import uuid


class DeviceType(Enum):
    LIGHT = "light"
    THERMOSTAT = "thermostat"
    CAMERA = "camera"
    LOCK = "lock"
    SPEAKER = "speaker"
    PLUG = "plug"
    SENSOR = "sensor"
    SWITCH = "switch"


class DeviceStatus(Enum):
    ON = "on"
    OFF = "off"
    IDLE = "idle"
    ACTIVE = "active"


class SmartDevice:
    """Individual smart device representation"""
    
    def __init__(self, device_id: str, name: str, device_type: DeviceType):
        self.device_id = device_id
        self.name = name
        self.device_type = device_type
        self.status = DeviceStatus.OFF
        self.properties = {}
        self.last_updated = datetime.now()
    
    async def toggle(self) -> Dict:
        """Toggle device on/off"""
        self.status = DeviceStatus.ON if self.status == DeviceStatus.OFF else DeviceStatus.OFF
        self.last_updated = datetime.now()
        
        return {
            "device_id": self.device_id,
            "name": self.name,
            "status": self.status.value,
            "updated_at": self.last_updated.isoformat()
        }
    
    async def set_property(self, property_name: str, value: any) -> Dict:
        """Set device property"""
        self.properties[property_name] = value
        self.last_updated = datetime.now()
        
        return {
            "device_id": self.device_id,
            "property": property_name,
            "value": value,
            "status": "success"
        }
    
    async def get_state(self) -> Dict:
        """Get device state"""
        return {
            "device_id": self.device_id,
            "name": self.name,
            "type": self.device_type.value,
            "status": self.status.value,
            "properties": self.properties,
            "last_updated": self.last_updated.isoformat()
        }


class SmartHome:
    """Smart home hub - controls all devices"""
    
    def __init__(self):
        self.devices: Dict[str, SmartDevice] = {}
        self.rooms = {}
        self.automation_rules = {}
        self.energy_usage = 0
        print("[SMART HOME] System Online - Automation Ready!")
    
    async def add_device(self, name: str, device_type: DeviceType, room: str = "general") -> Dict:
        """Add new device to smart home"""
        device_id = str(uuid.uuid4())
        device = SmartDevice(device_id, name, device_type)
        
        self.devices[device_id] = device
        
        if room not in self.rooms:
            self.rooms[room] = []
        
        self.rooms[room].append(device_id)
        
        return {
            "device_id": device_id,
            "name": name,
            "device_type": device_type.value,
            "room": room,
            "status": "added"
        }
    
    async def control_light(self, light_id: str, brightness: int = 100, color: str = "white") -> Dict:
        """Control smart light"""
        if light_id not in self.devices:
            return {"error": "Device not found"}
        
        device = self.devices[light_id]
        await device.set_property("brightness", brightness)
        await device.set_property("color", color)
        await device.toggle()
        
        return {
            "light_id": light_id,
            "brightness": brightness,
            "color": color,
            "status": "controlled"
        }
    
    async def set_temperature(self, thermostat_id: str, target_temp: float, mode: str = "heat") -> Dict:
        """Set thermostat temperature"""
        if thermostat_id not in self.devices:
            return {"error": "Device not found"}
        
        device = self.devices[thermostat_id]
        await device.set_property("target_temperature", target_temp)
        await device.set_property("mode", mode)
        
        return {
            "thermostat_id": thermostat_id,
            "target_temperature": target_temp,
            "mode": mode,
            "current_temperature": 22.5,  # Simulated
            "status": "set"
        }
    
    async def unlock_door(self, lock_id: str, method: str = "fingerprint") -> Dict:
        """Unlock smart lock"""
        if lock_id not in self.devices:
            return {"error": "Device not found"}
        
        device = self.devices[lock_id]
        await device.toggle()
        
        return {
            "lock_id": lock_id,
            "unlock_method": method,
            "timestamp": datetime.now().isoformat(),
            "status": "unlocked"
        }
    
    async def lock_all_doors(self) -> Dict:
        """Lock all doors in home"""
        locked_count = 0
        
        for device in self.devices.values():
            if device.device_type == DeviceType.LOCK:
                await device.toggle()
                locked_count += 1
        
        return {
            "locks_engaged": locked_count,
            "timestamp": datetime.now().isoformat(),
            "duration": "2 seconds",
            "status": "all_locked"
        }
    
    async def view_camera(self, camera_id: str) -> Dict:
        """View camera feed"""
        if camera_id not in self.devices:
            return {"error": "Device not found"}
        
        return {
            "camera_id": camera_id,
            "feed_url": f"rtsp://localhost:8554/camera_{camera_id}",
            "resolution": "1920x1080",
            "fps": 30,
            "status": "streaming",
            "motion_detected": False
        }
    
    async def create_automation(
        self,
        name: str,
        trigger: Dict,
        action: Dict,
        enabled: bool = True
    ) -> Dict:
        """Create automation rule"""
        rule_id = str(uuid.uuid4())
        
        self.automation_rules[rule_id] = {
            "name": name,
            "trigger": trigger,
            "action": action,
            "enabled": enabled,
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "rule_id": rule_id,
            "name": name,
            "trigger": trigger,
            "action": action,
            "status": "created"
        }
    
    async def get_automation_examples(self) -> Dict:
        """Get example automation scenarios"""
        return {
            "examples": [
                {
                    "name": "Morning Routine",
                    "trigger": "time == 06:30",
                    "actions": [
                        "turn_on lights",
                        "set_temperature 22",
                        "brew_coffee"
                    ]
                },
                {
                    "name": "Movie Time",
                    "trigger": "mode == movie",
                    "actions": [
                        "dim_lights 20%",
                        "close_blinds",
                        "disable_notifications"
                    ]
                },
                {
                    "name": "Leaving Home",
                    "trigger": "all_occupants_away",
                    "actions": [
                        "turn_off all lights",
                        "lock all doors",
                        "set thermostat 18"
                    ]
                },
                {
                    "name": "coming Home",
                    "trigger": "first_occupant_arrives",
                    "actions": [
                        "turn_on entrance light",
                        "unlock front door",
                        "start HVAC"
                    ]
                },
                {
                    "name": "Security",
                    "trigger": "motion_detected && all_away",
                    "actions": [
                        "alert owner",
                        "record cameras",
                        "enable sirens"
                    ]
                }
            ]
        }
    
    async def get_energy_report(self) -> Dict:
        """Get energy consumption report"""
        device_usage = {}
        
        for device_id, device in self.devices.items():
            if device.status == DeviceStatus.ON:
                # Simulate energy usage
                power_usage = {
                    DeviceType.LIGHT: 10,
                    DeviceType.THERMOSTAT: 2000,
                    DeviceType.SPEAKER: 5,
                    DeviceType.PLUG: 50
                }
                device_usage[device.name] = power_usage.get(device.device_type, 10)
        
        total_watts = sum(device_usage.values())
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_power_usage_watts": total_watts,
            "estimated_daily_kwh": round((total_watts * 24) / 1000, 2),
            "device_breakdown": device_usage,
            "cost_per_hour": round((total_watts / 1000) * 0.12, 2),  # $0.12 per kWh estimate
            "savings_potential": "23%",
            "recommendations": [
                "Upgrade to LED bulbs",
                "Install programmable thermostat",
                "Use power strips for phantom loads"
            ]
        }
    
    async def get_all_devices(self) -> List[Dict]:
        """Get all devices status"""
        devices = []
        
        for device in self.devices.values():
            state = await device.get_state()
            devices.append(state)
        
        return devices
    
    async def get_room_status(self, room_name: str) -> Dict:
        """Get status of all devices in a room"""
        if room_name not in self.rooms:
            return {"error": "Room not found"}
        
        devices = []
        for device_id in self.rooms[room_name]:
            device = self.devices[device_id]
            state = await device.get_state()
            devices.append(state)
        
        return {
            "room": room_name,
            "device_count": len(devices),
            "devices": devices
        }
    
    async def control_all_lights(self, brightness: int = 100) -> Dict:
        """Control all lights in home"""
        controlled = 0
        
        for device in self.devices.values():
            if device.device_type == DeviceType.LIGHT:
                await device.set_property("brightness", brightness)
                controlled += 1
        
        return {
            "lights_controlled": controlled,
            "brightness": brightness,
            "status": "complete"
        }
    
    async def emergency_shutdown(self) -> Dict:
        """Emergency shutdown - turn off all devices"""
        shutdown_count = 0
        
        for device in self.devices.values():
            if device.status == DeviceStatus.ON:
                await device.toggle()
                shutdown_count += 1
        
        return {
            "devices_shut_down": shutdown_count,
            "timestamp": datetime.now().isoformat(),
            "status": "emergency_shutdown_complete"
        }
    
    async def get_security_status(self) -> Dict:
        """Get security system status"""
        all_locked = all(
            device.status == DeviceStatus.OFF
            for device in self.devices.values()
            if device.device_type == DeviceType.LOCK
        )
        
        cameras_active = sum(
            1 for device in self.devices.values()
            if device.device_type == DeviceType.CAMERA and device.status == DeviceStatus.ON
        )
        
        return {
            "all_doors_locked": all_locked,
            "active_cameras": cameras_active,
            "motion_alerts": 0,
            "breach_attempts": 0,
            "last_alert": None,
            "security_level": "armed"
        }


# Initialize
smart_home = SmartHome()

if __name__ == "__main__":
    async def test():
        # Add devices
        light = await smart_home.add_device("Living Room Light", DeviceType.LIGHT, "living_room")
        print("Added Light:", json.dumps(light, indent=2))
        
        # Control light
        controlled = await smart_home.control_light(light["device_id"], 80, "warm")
        print("Controlled Light:", json.dumps(controlled, indent=2))
        
        # Get all devices
        devices = await smart_home.get_all_devices()
        print("All Devices:", json.dumps(devices, indent=2))
    
    asyncio.run(test())
