"""
Voice Control System for Igris AI
Handles automatic voice processing and command execution
"""

import asyncio
import json
import logging
from typing import Dict, Any, Callable, List
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class VoiceCommandHandler:
    def __init__(self):
        self.command_registry: Dict[str, Callable] = {}
        self.voice_log = []
        self.auto_mode = True  # Auto execute commands
        self.command_confidence_threshold = 0.7

    def register_command(self, command_pattern: str, handler: Callable, description: str = "") -> None:
        """
        Register a voice command pattern
        
        Args:
            command_pattern: Regex pattern for command matching
            handler: Async function to handle the command
            description: Description of what the command does
        """
        self.command_registry[command_pattern] = {
            "handler": handler,
            "description": description,
            "created_at": datetime.now().isoformat()
        }
        logger.info(f"Registered voice command: {command_pattern}")

    async def process_voice_command(self, transcript: str, language: str = "ur-PK") -> Dict[str, Any]:
        """
        Process incoming voice command with auto execution
        
        Args:
            transcript: Voice transcript
            language: Language code
            
        Returns:
            Command processing result
        """
        try:
            # Parse command intent
            intent = self._parse_intent(transcript)
            
            if not intent:
                return {
                    "status": "no_match",
                    "message": "Could not understand command",
                    "transcript": transcript
                }
            
            command_name = intent.get("command")
            parameters = intent.get("parameters", {})
            confidence = intent.get("confidence", 0.0)
            
            # Check confidence threshold
            if confidence < self.command_confidence_threshold:
                return {
                    "status": "low_confidence",
                    "message": f"Confidence too low ({confidence:.2%})",
                    "transcript": transcript,
                    "command": command_name
                }
            
            # Find matching command pattern
            handler = None
            for pattern, cmd_info in self.command_registry.items():
                if re.match(pattern, command_name, re.IGNORECASE):
                    handler = cmd_info["handler"]
                    break
            
            if not handler:
                return {
                    "status": "unknown_command",
                    "message": f"Unknown command: {command_name}",
                    "transcript": transcript
                }
            
            # Auto execute if enabled
            if self.auto_mode:
                try:
                    result = await handler(parameters)
                    
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "transcript": transcript,
                        "command": command_name,
                        "parameters": parameters,
                        "confidence": confidence,
                        "status": "executed",
                        "result": result
                    }
                    self.voice_log.append(log_entry)
                    
                    return {
                        "status": "success",
                        "command": command_name,
                        "message": f"Executed: {command_name}",
                        "result": result,
                        "confidence": confidence
                    }
                except Exception as e:
                    return {
                        "status": "execution_error",
                        "command": command_name,
                        "message": f"Error executing command: {str(e)}",
                        "error": str(e)
                    }
            else:
                return {
                    "status": "pending_confirmation",
                    "command": command_name,
                    "message": f"Ready to execute: {command_name}",
                    "parameters": parameters,
                    "confidence": confidence
                }
            
        except Exception as e:
            logger.error(f"Voice command processing error: {str(e)}")
            return {
                "status": "error",
                "message": f"Processing error: {str(e)}",
                "error": str(e)
            }

    def _parse_intent(self, transcript: str) -> Dict[str, Any]:
        """
        Parse voice transcript to extract intent and parameters
        
        Args:
            transcript: Voice transcript
            
        Returns:
            Parsed intent with confidence score
        """
        # Urdu/English command patterns
        command_patterns = [
            # AI Self-Modification Commands
            {
                "patterns": [
                    r"(?:اپنے آپ کو|خود کو|yourself).*(?:تبدیل|modify|improve|update|بہتر\s*بن)",
                    r"modify\s+(yourself|itself|your\s*code|your\s*logic)|change\s+yourself|update\s+yourself"
                ],
                "command": "modify_self",
                "confidence": 0.9
            },
            # Voice Control Auto Commands
            {
                "patterns": [
                    r"خودکار mode|automatic|خود کار|auto.*mode",
                    r"turn on auto|enable auto"
                ],
                "command": "enable_auto_mode",
                "confidence": 0.85
            },
            {
                "patterns": [
                    r"manual mode|دستی mode|یدی|متوقف|stop.*auto",
                    r"turn off auto|disable auto"
                ],
                "command": "disable_auto_mode",
                "confidence": 0.85
            },
            # Execute Commands
            {
                "patterns": [
                    r"یہ کریں|execute that|اس کو کریں|run that",
                    r"confirm|ہاں|جی|yes|proceed"
                ],
                "command": "execute_pending",
                "confidence": 0.8
            },
            # System Status
            {
                "patterns": [
                    r"status|حالت|کیا ہو رہا ہے|what.*happening",
                    r"رپورٹ|خبر|updates|system\s+status|(?:^|\s)status\s*report"
                ],
                "command": "get_status",
                "confidence": 0.85
            },
            # Learning / training (before add_capability to win "سیکھو…" phrases)
            {
                "patterns": [
                    r"\btraining\s+mode\b|enter\s+training(\s+mode)?|learning\s+mode|"
                    r"تربیت|سیکھو اور|سیکھو\s+اور|enter\s+training"
                ],
                "command": "learning_mode",
                "confidence": 0.8
            },
            # Content generation
            {
                "patterns": [
                    r"\bgenerate\b|\bcreate\b|لکھو|تخلیق|بناو|write\s+a|draft\s+a"
                ],
                "command": "generate_content",
                "confidence": 0.8
            },
            {
                "patterns": [
                    r"(?:مختصر|مکمل|standard)?\s*(?:مضمون|content|essay|story|report)"
                ],
                "command": "generate_content",
                "confidence": 0.78
            },
            # Q&A
            {
                "patterns": [
                    r"\bwhat is\b|\bwhat are\b|\bwho is\b|\bwhy is\b|"
                    r"\bhow (?:do|does|is|are)\b",
                    r"کیا|کون|کہاں|کیوں|بتاؤ|tell me|explain|وضاحت|machine learning|deep learning"
                ],
                "command": "answer_question",
                "confidence": 0.82
            },
            # Capability Addition (kept specific — do not use bare "سیکھو" here)
            {
                "patterns": [
                    r"نیا صلاحیت|new capability|add.*feature|نیا feature",
                    r"میں تمہیں.*سیکھاتا ہوں|teach.*you"
                ],
                "command": "add_capability",
                "confidence": 0.8
            },
        ]
        
        # Normalize transcript
        normalized = transcript.lower().strip()
        
        # Match against patterns
        best_match = None
        best_confidence = 0.0
        
        for pattern_info in command_patterns:
            for pattern in pattern_info["patterns"]:
                if re.search(pattern, normalized, re.IGNORECASE | re.UNICODE):
                    if pattern_info["confidence"] > best_confidence:
                        best_match = pattern_info
                        best_confidence = pattern_info["confidence"]
        
        if not best_match:
            return None
        
        # Extract parameters
        parameters = self._extract_parameters(transcript, best_match["command"])
        
        return {
            "command": best_match["command"],
            "confidence": best_confidence,
            "parameters": parameters,
            "transcript": transcript,
            "timestamp": datetime.now().isoformat()
        }

    def _extract_parameters(self, transcript: str, command: str) -> Dict[str, Any]:
        """Extract parameters from transcript based on command type"""
        params = {}
        
        # Common parameter extraction patterns
        # Extract numbers
        numbers = re.findall(r'\d+', transcript)
        if numbers:
            params["numbers"] = [int(n) for n in numbers]
        
        # Extract quoted text
        quoted = re.findall(r'["\']([^"\']+)["\']', transcript)
        if quoted:
            params["quoted_text"] = quoted
        
        # Extract language
        if "اردو" in transcript or "urdu" in transcript.lower():
            params["language"] = "urdu"
        elif "انگلش" in transcript or "english" in transcript.lower():
            params["language"] = "english"
        
        # Command-specific parameters
        if command == "generate_content":
            if "مخت صر" in transcript or "short" in transcript.lower():
                params["length"] = "short"
            elif "مکمل" in transcript or "full" in transcript.lower():
                params["length"] = "full"
        
        if command == "modify_self":
            # Extract what to modify
            if "function" in transcript or "فنکشن" in transcript:
                params["type"] = "function"
            elif "parameter" in transcript or "پیرامیٹر" in transcript:
                params["type"] = "parameter"
            elif "capability" in transcript or "صلاحیت" in transcript:
                params["type"] = "capability"
        
        return params

    async def handle_auto_execution(self, command: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle automatic execution of commands
        """
        # This will be overridden by actual command handlers
        return {
            "status": "pending",
            "command": command,
            "parameters": parameters
        }

    def get_voice_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get voice command log"""
        return self.voice_log[-limit:]

    def set_auto_mode(self, enabled: bool) -> Dict[str, Any]:
        """Enable or disable auto mode"""
        self.auto_mode = enabled
        return {
            "auto_mode": self.auto_mode,
            "status": "updated",
            "message": f"Auto mode {'enabled' if enabled else 'disabled'}"
        }

    def get_registered_commands(self) -> Dict[str, Any]:
        """Get list of registered commands"""
        commands = {}
        for pattern, info in self.command_registry.items():
            commands[pattern] = {
                "description": info.get("description", ""),
                "created_at": info.get("created_at")
            }
        return commands


# Initialize global instance
voice_command_handler = VoiceCommandHandler()
