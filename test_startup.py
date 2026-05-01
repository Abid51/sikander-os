#!/usr/bin/env python3
"""
Igris System Startup Test
Tests if the system can actually start without errors
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print('=' * 70)
print('IGRIS SYSTEM - STARTUP FEASIBILITY TEST')
print('=' * 70)
print()

try:
    print('Step 1: Loading FastAPI application...')
    from fastapi import FastAPI
    from app.core.ai_core import IgrisBrain
    from app.system.os_control import SystemController
    from app.api import routes, voice_routes, cloud_routes
    print('[OK] All core imports successful')
    print()
    
    print('Step 2: Creating FastAPI app instance...')
    app = FastAPI(title="Igris Test")
    print('[OK] FastAPI app created')
    print()
    
    print('Step 3: Registering routes...')
    app.include_router(routes.router)
    app.include_router(voice_routes.router)
    app.include_router(cloud_routes.router)
    print('[OK] All routes registered')
    print()
    
    print('Step 4: Checking router configuration...')
    route_count = len(app.routes)
    print(f'[OK] Total routes available: {route_count}')
    print()
    
    print('Step 5: Cloud AI system readiness...')
    from app.core.cloud_ai import cloud_ai
    status = cloud_ai.get_status()
    print(f'[OK] Cloud AI Status: {status}')
    print()
    
    print('Step 6: Voice control readiness...')
    from app.core.voice_control import voice_command_handler
    print(f'[OK] Voice control auto-mode: {voice_command_handler.auto_mode}')
    print()
    
    print('=' * 70)
    print('STARTUP TEST RESULT: SUCCESS')
    print('=' * 70)
    print()
    print('System CAN start successfully with:')
    print('  python backend/main.py')
    print()
    print('Available APIs:')
    print('  - Core API: http://localhost:8000/api/*')
    print('  - Voice API: http://localhost:8000/api/voice/*')
    print('  - Cloud AI API: http://localhost:8000/api/cloud/*')
    print()
    print('API Documentation:')
    print('  - http://localhost:8000/docs')
    print()
    
except Exception as e:
    print(f'[FAIL] Startup test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
