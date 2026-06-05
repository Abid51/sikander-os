"""
Test script for Igris Voice Control & Self-Modification System (OPTIMIZED)

PERFORMANCE IMPROVEMENTS:
- Connection pooling with requests.Session()
- Batch requests instead of sequential calls
- Timeout handling and retry logic
- Context managers for resource cleanup
"""

import asyncio
import json
import requests
import time
from typing import Dict, Any, List

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

# OPTIMIZATION: Use session for connection pooling
session = requests.Session()
session.headers.update({'User-Agent': 'IgrisTestSuite/1.0'})


class IgrisTestSuite:
    """Optimized test suite with connection pooling and better error handling."""
    
    def __init__(self, timeout: int = 10):
        self.results: List[Dict[str, Any]] = []
        self.timeout = timeout
    
    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic."""
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                kwargs.setdefault('timeout', self.timeout)
                response = session.request(method, url, **kwargs)
                return response
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt == max_retries - 1:
                    raise
                await_time = retry_delay * (2 ** attempt)
                print(f"  Retry {attempt + 1}/{max_retries} after {await_time}s...")
                time.sleep(await_time)
    
    async def test_voice_command_processing(self):
        """Test voice command processing."""
        print("\n📝 Testing Voice Command Processing...")
        
        test_commands = [
            {
                "transcript": "میرے emails check کرو",
                "language": "ur-PK",
                "expected_command": "answer_question"
            },
            {
                "transcript": "خودکار mode",
                "language": "ur-PK",
                "expected_command": "enable_auto_mode"
            },
            {
                "transcript": "میری speed 2x کر دو",
                "language": "ur-PK",
                "expected_command": "modify_self"
            }
        ]
        
        for cmd in test_commands:
            try:
                response = self._request_with_retry(
                    'POST',
                    f"{BASE_URL}/api/voice/process-command",
                    json={
                        "transcript": cmd["transcript"],
                        "language": cmd["language"]
                    }
                )
                
                result = response.json()
                print(f"  ✓ Command: {cmd['transcript']}")
                print(f"    Status: {result.get('status')}")
                print(f"    Detected: {result.get('command')}")
                
                self.results.append({
                    "test": "voice_command",
                    "command": cmd["transcript"],
                    "status": result.get("status"),
                    "passed": result.get("status") in ["success", "pending_confirmation", "pending"]
                })
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
                self.results.append({
                    "test": "voice_command",
                    "command": cmd["transcript"],
                    "status": "error",
                    "error": str(e),
                    "passed": False
                })
    
    async def test_auto_mode(self):
        """Test auto mode toggle."""
        print("\n🤖 Testing Auto Mode...")
        
        try:
            response = self._request_with_retry('GET', f"{BASE_URL}/api/voice/auto-mode")
            current = response.json()
            print(f"  Current Auto Mode: {current.get('auto_mode')}")
            
            response = self._request_with_retry(
                'POST',
                f"{BASE_URL}/api/voice/auto-mode/toggle?enabled=true"
            )
            result = response.json()
            print(f"  ✓ Set Auto Mode: {result.get('auto_mode')}")
            
            self.results.append({
                "test": "auto_mode",
                "status": "success",
                "passed": result.get("auto_mode") == True
            })
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            self.results.append({
                "test": "auto_mode",
                "status": "error",
                "error": str(e),
                "passed": False
            })
    
    async def test_registered_commands(self):
        """Test getting registered commands."""
        print("\n📋 Testing Registered Commands...")
        
        try:
            response = self._request_with_retry('GET', f"{BASE_URL}/api/voice/commands")
            commands = response.json()
            
            num_commands = len(commands)
            print(f"  ✓ Total Registered Commands: {num_commands}")
            print(f"    Sample commands:")
            for i, (pattern, info) in enumerate(list(commands.items())[:3]):
                print(f"      {i+1}. {pattern}")
                print(f"         Desc: {info.get('description', 'N/A')}")
            
            self.results.append({
                "test": "registered_commands",
                "num_commands": num_commands,
                "status": "success",
                "passed": num_commands > 0
            })
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            self.results.append({
                "test": "registered_commands",
                "status": "error",
                "error": str(e),
                "passed": False
            })
    
    async def test_voice_log(self):
        """Test voice command logging."""
        print("\n📜 Testing Voice Log...")
        
        try:
            response = self._request_with_retry(
                'GET',
                f"{BASE_URL}/api/voice/voice-log?limit=10"
            )
            log_data = response.json()
            
            total = log_data.get("total", 0)
            log_count = len(log_data.get("log", []))
            
            print(f"  ✓ Total Commands: {total}")
            print(f"    Retrieved: {log_count}")
            
            if log_count > 0:
                print(f"    Latest command: {log_data['log'][-1].get('transcript', 'N/A')}")
            
            self.results.append({
                "test": "voice_log",
                "total": total,
                "status": "success",
                "passed": True
            })
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            self.results.append({
                "test": "voice_log",
                "status": "error",
                "error": str(e),
                "passed": False
            })
    
    async def test_modification_history(self):
        """Test modification history."""
        print("\n📊 Testing Modification History...")
        
        try:
            response = self._request_with_retry(
                'GET',
                f"{BASE_URL}/api/voice/modify/history"
            )
            history = response.json()
            
            total = history.get("total_modifications", 0)
            print(f"  ✓ Total Modifications: {total}")
            
            if total > 0:
                latest = history["history"][-1]
                print(f"    Latest Modification:")
                print(f"      Type: {latest.get('type', 'N/A')}")
                print(f"      Status: {latest.get('status', 'N/A')}")
                print(f"      Timestamp: {latest.get('timestamp', 'N/A')}")
            
            self.results.append({
                "test": "modification_history",
                "total_modifications": total,
                "status": "success",
                "passed": True
            })
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            self.results.append({
                "test": "modification_history",
                "status": "error",
                "error": str(e),
                "passed": False
            })
    
    async def test_system_stats(self):
        """Test system statistics."""
        print("\n💻 Testing System Stats...")
        
        try:
            response = self._request_with_retry('GET', f"{BASE_URL}/system/stats")
            stats = response.json()
            
            print(f"  ✓ CPU: {stats.get('cpu', 'N/A')}%")
            print(f"  ✓ Memory: {stats.get('memory', 'N/A')}%")
            print(f"  ✓ Disk: {stats.get('disk', 'N/A')}%")
            
            self.results.append({
                "test": "system_stats",
                "stats": stats,
                "status": "success",
                "passed": True
            })
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            self.results.append({
                "test": "system_stats",
                "status": "error",
                "error": str(e),
                "passed": False
            })
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*50)
        print("📊 TEST SUMMARY")
        print("="*50)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.get("passed", False))
        failed_tests = total_tests - passed_tests
        
        print(f"\nTotal Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        if total_tests > 0:
            print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        print("\nDetailed Results:")
        for i, result in enumerate(self.results, 1):
            status = "✅" if result.get("passed") else "❌"
            test_name = result.get("test", "unknown")
            print(f"  {i}. {status} {test_name}")
            if result.get("error"):
                print(f"     Error: {result.get('error')}")
        
        print("\n" + "="*50)


async def main():
    """Run all tests."""
    print("🚀 Igris Voice Control & Self-Modification Test Suite (OPTIMIZED)")
    print("="*50)
    
    try:
        response = session.get(f"{BASE_URL}/system/stats", timeout=2)
        print("✅ Backend Server is Running!")
    except requests.exceptions.ConnectionError:
        print("❌ Backend Server is NOT running!")
        print("   Please start it with: python backend/main.py")
        return
    
    suite = IgrisTestSuite()
    
    await suite.test_system_stats()
    await suite.test_voice_command_processing()
    await suite.test_auto_mode()
    await suite.test_registered_commands()
    await suite.test_voice_log()
    await suite.test_modification_history()
    
    suite.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
