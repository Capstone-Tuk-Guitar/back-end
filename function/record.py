from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import shutil
import uuid
from datetime import datetime
import subprocess

record_router = APIRouter()

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "..", "uploads", "record")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@record_router.post("/record/upload")
async def upload_record(file: UploadFile = File(...)):
    try:
        # 저장 이름 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex
        original_name = f"{uid}_{timestamp}.webm"
        mp3_name = f"{uid}_{timestamp}.mp3"

        webm_path = os.path.join(UPLOAD_DIR, original_name)
        mp3_path = os.path.join(UPLOAD_DIR, mp3_name)

        # webm 파일 저장
        with open(webm_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # ffmpeg로 mp3 변환
        result = subprocess.run(
            ["ffmpeg", "-i", webm_path, "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k", mp3_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="ffmpeg 변환 실패")

        # (선택) 원본 webm 삭제
        os.remove(webm_path)

        return JSONResponse(content={
            "message": "녹음 저장 및 mp3 변환 완료",
            "filename": mp3_name,
            "path": mp3_path
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"녹음 저장 실패: {str(e)}")
