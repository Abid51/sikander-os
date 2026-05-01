import os
import subprocess
import platform
import webbrowser
import psutil
import shutil
import re
import io
import sys
import contextlib
import shlex

# Optional imports with fallback
try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

try:
    import wmi
except ImportError:
    wmi = None

class SystemController:
    """
    Interface for the OS to perform system-level operations.
    Runs entirely locally without external APIs.
    """
    def execute_python_code(self, code: str):
        """Runs python code locally and returns stdout."""
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(code, {})
            return output.getvalue() or "Code executed successfully with no output."
        except Exception as e:
            return f"Python Execution Error: {str(e)}"

    def __init__(self):
        self.os_type = platform.system()

    def execute_terminal(self, command: str):
        """Executes terminal commands and returns the output."""
        try:
            cmd = (command or "").strip()
            if not cmd:
                return "No command provided."
            if re.search(r"[;&|><`]", cmd):
                return "Command blocked: shell metacharacters are not allowed."

            parts = shlex.split(cmd, posix=(self.os_type != "Windows"))
            if not parts:
                return "No command provided."

            allowed = {"whoami", "hostname", "ipconfig", "ifconfig", "systeminfo", "tasklist", "arp", "ping", "dir", "ls", "pwd"}
            base = parts[0].lower()
            if base not in allowed:
                return f"Command blocked: '{base}' is not in the safe allowlist."

            if self.os_type == "Windows" and base in {"dir", "ls", "pwd"}:
                win_cmd = "dir" if base in {"dir", "ls"} else "cd"
                result = subprocess.run(["cmd", "/c", win_cmd, *parts[1:]], capture_output=True, text=True)
            else:
                result = subprocess.run(parts, capture_output=True, text=True)
            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            if result.returncode == 0:
                if stdout:
                    return f"Command completed successfully.\nOutput: {stdout[:600]}"
                return "Command completed successfully."
            if stderr:
                return f"Command failed (code {result.returncode}). Error: {stderr[:600]}"
            return f"Command failed (code {result.returncode})."
        except Exception as e:
            return f"Error executing terminal: {str(e)}"
            
    def write_file(self, path: str, content: str):
        """Writes any text or code to a file."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
            
    def read_file(self, path: str):
        """Reads content from a local file."""
        try:
            if not os.path.exists(path):
                return f"Error: File {path} not found."
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return content[:2000] # Return first 2000 chars to avoid overflowing LLM
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def list_directory(self, path: str):
        """Lists files and folders in a directory."""
        try:
            if not os.path.exists(path):
                return f"Error: Directory {path} not found."
            items = os.listdir(path)
            return "\n".join(items)
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    def get_system_info(self):
        """Returns deep system information."""
        try:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk_root = os.environ.get("SystemDrive", "C:") + "\\" if self.os_type == "Windows" else "/"
            disk = psutil.disk_usage(disk_root)
            
            info = [
                f"OS: {platform.system()} {platform.release()}",
                f"CPU Usage: {cpu}%",
                f"RAM: {ram.used / (1024**3):.2f}GB / {ram.total / (1024**3):.2f}GB ({ram.percent}%)",
                f"Disk: {disk.used / (1024**3):.2f}GB / {disk.total / (1024**3):.2f}GB ({disk.percent}%)"
            ]
            return "\n".join(info)
        except Exception as e:
            return f"Error getting system info: {str(e)}"

    def open_app(self, app_name: str):
        """Open a local desktop application without API"""
        try:
            if self.os_type == "Windows":
                subprocess.Popen(f"start {app_name}", shell=True)
            elif self.os_type == "Linux":
                subprocess.Popen([app_name])
            elif self.os_type == "Darwin": # Mac
                subprocess.Popen(["open", "-a", app_name])
            return True
        except Exception:
            return False

    def close_app(self, app_name: str):
        """Force close an application locally"""
        try:
            if self.os_type == "Windows":
                subprocess.run(["taskkill", "/IM", f"{app_name}.exe", "/F"], capture_output=True, text=True)
            else:
                subprocess.run(["pkill", "-f", app_name], capture_output=True, text=True)
            return True
        except Exception:
            return False

    def search_browser(self, query: str):
        """Search the default web browser directly"""
        url = f"https://www.google.com/search?q={query}"
        webbrowser.open(url)
        return True

    def search_youtube(self, query: str):
        """Search YouTube directly"""
        url = f"https://www.youtube.com/results?search_query={query}"
        webbrowser.open(url)
        return True

    def connect_phone_wireless(self, ip_address: str):
        """
        Connect to phone via ADB over Wi-Fi without a USB cable.
        """
        try:
            result = subprocess.run(f"adb connect {ip_address}", shell=True, capture_output=True, text=True)
            return True, result.stdout
        except Exception as e:
            return False, str(e)

    def control_phone(self, action: str, *args):
        """
        Control phone locally via ADB (Android Debug Bridge).
        No APIs used.
        """
        try:
            if action == "wake":
                subprocess.run("adb shell input keyevent 26", shell=True) # Power button
            elif action == "home":
                subprocess.run("adb shell input keyevent 3", shell=True) # Home button
            elif action == "tap" and len(args) >= 2:
                subprocess.run(f"adb shell input tap {args[0]} {args[1]}", shell=True)
            elif action == "swipe" and len(args) >= 4:
                subprocess.run(f"adb shell input swipe {args[0]} {args[1]} {args[2]} {args[3]}", shell=True)
            elif action == "swipe_up":
                subprocess.run("adb shell input swipe 500 1500 500 500", shell=True)
            elif action == "type" and len(args) >= 1:
                text = args[0].replace(" ", "%s") # ADB requires %s for spaces
                subprocess.run(f"adb shell input text {text}", shell=True)
            else:
                subprocess.run(f"adb shell {action}", shell=True)
            return True
        except Exception:
            return False

    def shutdown(self):
        if self.os_type == "Windows":
            os.system("shutdown /s /t 1")
        else:
            os.system("shutdown -h now")

    # --- NEW: Computer Vision (Screen Reading) ---
    def read_screen(self):
        """Takes a screenshot and extracts text using Tesseract OCR."""
        try:
            if pyautogui is None:
                return "Vision Error: pyautogui is not installed."
            if pytesseract is None or Image is None:
                return "Vision Error: pytesseract/Pillow is not installed."
            # On Windows, you might need to set tesseract_cmd path if it's not in PATH
            if self.os_type == "Windows" and os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
                pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            
            screenshot = pyautogui.screenshot()
            text = pytesseract.image_to_string(screenshot)
            return text.strip()
        except Exception as e:
            return f"Vision Error: {str(e)}. (Ensure Tesseract-OCR is installed)"

    # --- NEW: Deep Automation (Mouse & Keyboard) ---
    def pc_type(self, text: str):
        """Types text directly via keyboard simulation."""
        try:
            if pyautogui is None:
                return False
            pyautogui.write(text, interval=0.05)
            return True
        except Exception:
            return False

    def pc_click(self, x=None, y=None):
        """Clicks the mouse at current location or given coordinates."""
        try:
            if pyautogui is None:
                return False
            if x is not None and y is not None:
                pyautogui.click(int(x), int(y))
            else:
                pyautogui.click()
            return True
        except Exception:
            return False

    def pc_press(self, key: str):
        """Presses a specific keyboard key (e.g., 'enter', 'win', 'esc')."""
        try:
            if pyautogui is None:
                return False
            pyautogui.press(key)
            return True
        except Exception:
            return False

    # --- NEW: Blood Ward (Auto-Killer) ---
    def kill_process(self, pid: int):
        """Terminates a specific process ID."""
        try:
            p = psutil.Process(pid)
            p.terminate()
            return True
        except Exception:
            return False

    # --- NEW: Dominion System (Network Scanner) ---
    def scan_network(self):
        """Scans the local network for connected devices via ARP."""
        try:
            result = subprocess.run("arp -a", shell=True, capture_output=True, text=True)
            return result.stdout
        except Exception:
            return ""

    # --- NEW: Technopathy (Hardware Overclock/Control) ---
    def optimize_hardware(self):
        """
        Attempts to interact with Windows Management Instrumentation (WMI) 
        to optimize performance (simulated overclocking / resource priority).
        """
        if self.os_type != "Windows" or wmi is None:
            return "Technopathy is currently only available on Windows systems."
            
        try:
            c = wmi.WMI()
            # Fetch basic hardware info
            cpu = c.Win32_Processor()[0]
            ram = c.Win32_ComputerSystem()[0].TotalPhysicalMemory
            ram_gb = int(ram) / (1024**3)
            
            # Set all non-essential processes to low priority to "overclock" the main apps
            essential_apps = ['explorer.exe', 'python.exe', 'python3', 'node.exe', 'electron.exe']
            p = psutil.Process(os.getpid())
            p.nice(psutil.HIGH_PRIORITY_CLASS) # Elevate Igris's priority
            
            return f"Technopathy engaged. CPU: {cpu.Name}, RAM: {ram_gb:.2f}GB. My Liege, I have prioritized our core processes and throttled the rest."
        except Exception as e:
            return f"Technopathy encountered resistance: {str(e)}"
    def scan_iot_devices(self):
        """
        Scans network for common IoT ports (e.g. 80, 443, 554 for cameras, 8080 for smart hubs).
        Returns a list of potential smart devices.
        """
        try:
            # Simplified scan: checking ARP table and simulating a port scan for IoT signatures
            result = subprocess.run("arp -a", shell=True, capture_output=True, text=True)
            devices = []
            for line in result.stdout.split('\n'):
                if "dynamic" in line.lower() or "192.168." in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        mac = parts[1]
                        devices.append({"ip": ip, "mac": mac, "type": "Unknown Smart Device"})
            return devices
        except Exception:
            return []

    def control_iot_device(self, ip: str, action: str):
        """
        Attempts to send a command to an IoT device (e.g. HTTP GET/POST to smart bulbs/plugs).
        """
        try:
            # Example payload for generic smart bulbs
            if action == "on":
                # Simulated request: requests.get(f"http://{ip}/turn_on")
                return True, f"Sent 'ON' signal to {ip}."
            elif action == "off":
                # Simulated request: requests.get(f"http://{ip}/turn_off")
                return True, f"Sent 'OFF' signal to {ip}."
            elif action == "red":
                # Simulated request: requests.get(f"http://{ip}/set_color?color=red")
                return True, f"Turned device at {ip} to Blood Red."
            return False, "Unknown action."
        except Exception as e:
            return False, str(e)

    # --- NEW: Dimensional Rift (File Organizer) ---
    def organize_directory(self, path: str):
        """Automatically sorts files in a given directory into subfolders by type."""
        try:
            if not os.path.exists(path):
                return False, f"Directory {path} does not exist."
            
            categories = {
                "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
                "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv"],
                "Videos": [".mp4", ".mkv", ".avi", ".mov"],
                "Audio": [".mp3", ".wav", ".aac"],
                "Archives": [".zip", ".rar", ".7z", ".tar.gz"],
                "Executables": [".exe", ".msi", ".apk", ".bat"]
            }
            
            moved_count = 0
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path):
                    ext = os.path.splitext(item)[1].lower()
                    for cat, exts in categories.items():
                        if ext in exts:
                            cat_dir = os.path.join(path, cat)
                            if not os.path.exists(cat_dir):
                                os.makedirs(cat_dir)
                            shutil.move(item_path, os.path.join(cat_dir, item))
                            moved_count += 1
                            break
            return True, f"Moved {moved_count} files into their respective dimensions."
        except Exception as e:
            return False, str(e)
