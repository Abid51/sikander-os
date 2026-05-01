#!/usr/bin/env python3
"""
FINAL VERIFICATION CHECKLIST
Igris Advanced AI OS - Complete System Verification
"""

import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class VerificationChecklist:
    def __init__(self):
        self.checks = []
        self.root = Path("c:/Users/AABI/Downloads/sikander-os")
    
    def check_file_exists(self, filename, description):
        """Check if file exists"""
        path = self.root / filename
        exists = path.exists()
        status = "✅" if exists else "❌"
        self.checks.append((status, description, str(path)))
        return exists
    
    def check_file_contains(self, filename, search_string, description):
        """Check if file contains specific text"""
        path = self.root / filename
        if not path.exists():
            self.checks.append(("❌", f"{description} (FILE NOT FOUND)", str(path)))
            return False
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                found = search_string in content
                status = "✅" if found else "❌"
                self.checks.append((status, description, filename))
                return found
        except Exception as e:
            self.checks.append(("❌", f"{description} (ERROR: {str(e)})", filename))
            return False
    
    def run_all_checks(self):
        """Run all verification checks"""
        print("\n" + "="*70)
        print("IGRIS ADVANCED AI OS - FINAL VERIFICATION CHECKLIST")
        print("="*70 + "\n")
        
        print("📁 MARKDOWN FILES (Should be ONLY 4):")
        print("-" * 70)
        self.check_file_exists("README.md", "1. README.md (main documentation)")
        self.check_file_exists("QUICKSTART.md", "2. QUICKSTART.md (quick guide)")
        self.check_file_exists("QUICK_START.md", "3. QUICK_START.md (alternative guide)")
        self.check_file_exists("CLOUD_AI_SETUP.md", "4. CLOUD_AI_SETUP.md (cloud integration guide)")
        
        print("\n🐍 BACKEND CORE FILES:")
        print("-" * 70)
        self.check_file_exists("backend/main.py", "5. Backend main server")
        self.check_file_exists("backend/requirements.txt", "6. Python dependencies")
        self.check_file_exists("backend/app/core/ai_core.py", "7. AI core module")
        
        print("\n☁️  CLOUD AI INTEGRATION:")
        print("-" * 70)
        self.check_file_exists("backend/app/core/cloud_ai.py", "8. Cloud AI providers (NEW)")
        self.check_file_exists("backend/app/api/cloud_routes.py", "9. Cloud API endpoints (NEW)")
        self.check_file_contains("backend/requirements.txt", "aiohttp", "10. aiohttp in requirements")
        self.check_file_contains("backend/main.py", "from app.api import cloud_routes", "11. Cloud routes imported in main.py")
        self.check_file_contains("backend/main.py", "app.include_router(cloud_routes.router)", "12. Cloud routes registered in FastAPI")
        
        print("\n🎤 VOICE INTEGRATION:")
        print("-" * 70)
        self.check_file_contains("backend/app/api/voice_routes.py", "from app.core.cloud_ai import cloud_ai", "13. Cloud AI imported in voice routes")
        self.check_file_contains("backend/app/api/voice_routes.py", "use_cloud_ai", "14. Voice routes support cloud AI")
        
        print("\n🧪 TEST SCRIPTS:")
        print("-" * 70)
        self.check_file_exists("test_cloud_ai.py", "15. Cloud AI test script (NEW)")
        self.check_file_exists("test_igris_system.py", "16. System test script")
        
        print("\n⚙️  CONFIGURATION:")
        print("-" * 70)
        self.check_file_exists(".env.example", "17. Environment template (NEW)")
        self.check_file_contains(".env.example", "GROQ_API_KEY", "18. Groq API key in template")
        self.check_file_contains(".env.example", "HF_API_KEY", "19. HuggingFace API key in template")
        
        print("\n📄 DOCUMENTATION:")
        print("-" * 70)
        self.check_file_contains("README.md", "CLOUD AI INTEGRATION", "20. Cloud AI section in README")
        self.check_file_contains("CLOUD_AI_SETUP.md", "Groq", "21. Groq setup in CLOUD_AI_SETUP.md")
        self.check_file_contains("CLOUD_AI_SETUP.md", "HuggingFace", "22. HuggingFace setup docs")
        self.check_file_contains("CLOUD_AI_SETUP.md", "Replicate", "23. Replicate setup docs")
        
        print("\n📱 FRONTEND:")
        print("-" * 70)
        self.check_file_exists("frontend/src/App.tsx", "24. Frontend React app")
        self.check_file_exists("frontend/package.json", "25. Frontend dependencies")
        
        print("\n🗂️  PROJECT STRUCTURE:")
        print("-" * 70)
        self.check_file_exists("backend/", "26. Backend folder")
        self.check_file_exists("frontend/", "27. Frontend folder")
        self.check_file_exists("1_install.bat", "28. Install batch file")
        self.check_file_exists("2_start.bat", "29. Start batch file")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print verification summary"""
        print("\n" + "="*70)
        print("VERIFICATION RESULTS")
        print("="*70 + "\n")
        
        for status, description, location in self.checks:
            print(f"{status} {description}")
        
        passed = sum(1 for s, _, _ in self.checks if s == "✅")
        total = len(self.checks)
        
        print(f"\n{'='*70}")
        print(f"✅ PASSED: {passed}/{total}")
        
        if passed == total:
            print("\n🎉 ALL CHECKS PASSED - SYSTEM IS READY!")
            print("\nNext Steps:")
            print("1. Set Cloud API Key: $env:GROQ_API_KEY = 'your_key'")
            print("2. Install dependencies: pip install -r backend/requirements.txt")
            print("3. Start backend: python backend/main.py")
            print("4. Test cloud AI: python test_cloud_ai.py")
            return True
        else:
            failed = total - passed
            print(f"\n⚠️  FAILED: {failed} checks")
            print("\nPlease address the failed items above.")
            return False

if __name__ == "__main__":
    checker = VerificationChecklist()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
