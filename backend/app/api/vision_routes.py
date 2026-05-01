"""
Vision System API Routes
Handles image processing, OCR, screen capture, and computer vision tasks
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import os
import io
from datetime import datetime

from app.core.vision_system import (
    ObjectDetector, FaceRecognizer, ActivityRecognizer,
    VisionSystem
)
from app.core.daemon_master import daemon_master

router = APIRouter(prefix="/api/vision", tags=["vision"])

# Initialize vision components
object_detector = ObjectDetector()
face_recognizer = FaceRecognizer()
activity_recognizer = ActivityRecognizer()
vision_system = VisionSystem()


@router.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    """
    Analyze uploaded image for objects, faces, and scene
    """
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/vision_{datetime.now().timestamp()}_{file.filename}"
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        # Run analysis
        results = {}
        
        # Object detection
        try:
            object_results = await object_detector.detect_objects(temp_path)
            results["objects"] = object_results
        except Exception as e:
            results["objects"] = {"error": str(e)}
        
        # Face detection
        try:
            face_results = await face_recognizer.detect_faces(temp_path)
            results["faces"] = face_results
        except Exception as e:
            results["faces"] = {"error": str(e)}
        
        # Activity analysis
        try:
            activity_results = await activity_recognizer.recognize(temp_path)
            results["activity"] = activity_results
        except Exception as e:
            results["activity"] = {"error": str(e)}
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "filename": file.filename,
            "analysis": results
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")


@router.post("/ocr")
async def perform_ocr(file: UploadFile = File(...), language: str = "eng"):
    """
    Perform OCR on uploaded image
    """
    try:
        # Save file temporarily
        temp_path = f"/tmp/ocr_{datetime.now().timestamp()}_{file.filename}"
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        # Perform OCR using vision system
        result = await vision_system.process_image(temp_path, 'ocr')
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "language": language,
            "result": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")


@router.post("/ocr/screen")
async def capture_and_ocr(region: Dict[str, int] = None):
    """
    Capture screen and perform OCR
    """
    try:
        # Capture screen using vision system
        screenshot_path = await vision_system.capture_screen()
        
        # Perform OCR
        result = await vision_system.process_image(screenshot_path, 'ocr')
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "screenshot_path": screenshot_path,
            "result": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screen OCR failed: {str(e)}")


@router.post("/screen/capture")
async def capture_screen(region: Dict[str, int] = None):
    """
    Capture screen screenshot
    """
    try:
        screenshot_path = await vision_system.capture_screen()
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "path": screenshot_path,
            "url": f"/screenshots/{os.path.basename(screenshot_path)}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screen capture failed: {str(e)}")


@router.post("/detect-faces")
async def detect_faces_endpoint(file: UploadFile = File(...)):
    """
    Detect faces in image
    """
    try:
        temp_path = f"/tmp/face_{datetime.now().timestamp()}_{file.filename}"
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        result = await face_recognizer.detect_faces(temp_path)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "faces": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Face detection failed: {str(e)}")


@router.post("/recognize-activity")
async def recognize_activity(file: UploadFile = File(...)):
    """
    Recognize activity in image/video
    """
    try:
        temp_path = f"/tmp/activity_{datetime.now().timestamp()}_{file.filename}"
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        result = await activity_recognizer.recognize(temp_path)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "activity": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Activity recognition failed: {str(e)}")


@router.get("/detect-objects/realtime")
async def get_object_detector_status():
    """
    Get object detector status
    """
    return {
        "status": "ready",
        "detector": "ObjectDetector",
        "supported_objects": list(object_detector.common_objects.keys())
    }


@router.post("/batch-process")
async def batch_process_images(files: List[UploadFile] = File(...)):
    """
    Process multiple images in batch
    """
    results = []
    
    for file in files:
        try:
            temp_path = f"/tmp/batch_{datetime.now().timestamp()}_{file.filename}"
            contents = await file.read()
            with open(temp_path, "wb") as f:
                f.write(contents)
            
            # Run object detection
            detection = await object_detector.detect_objects(temp_path)
            
            results.append({
                "filename": file.filename,
                "status": "success",
                "objects": detection
            })
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
        "total": len(files),
        "successful": len([r for r in results if r["status"] == "success"]),
        "results": results
    }


# Aether Eye Daemon integration
@router.get("/aether-eye/status")
async def get_aether_eye_status():
    """
    Get Aether Eye daemon status
    """
    daemon = daemon_master.get_daemon("aether_eye")
    if daemon:
        return daemon.get_status()
    return {"error": "Aether Eye daemon not available"}


@router.post("/aether-eye/capture")
async def aether_eye_capture():
    """
    Capture screen using Aether Eye daemon
    """
    daemon = daemon_master.get_daemon("aether_eye")
    if daemon and hasattr(daemon, 'capture_screen'):
        result = await daemon.capture_screen()
        return result
    return {"error": "Aether Eye daemon not available"}


@router.post("/aether-eye/ocr")
async def aether_eye_ocr(image_path: str):
    """
    Perform OCR using Aether Eye daemon
    """
    daemon = daemon_master.get_daemon("aether_eye")
    if daemon and hasattr(daemon, 'queue_vision_task'):
        daemon.queue_vision_task(image_path, 'ocr')
        return {"status": "queued", "daemon": "aether_eye"}
    return {"error": "Aether Eye daemon not available"}
