from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

recording_router = APIRouter()

BASE_DIR = os.path.dirname(__file__)
RECORD_FOLDER = os.path.join(BASE_DIR, "..", "uploads", "record")
os.makedirs(RECORD_FOLDER, exist_ok=True)


@recording_router.get("/record-files/")
async def list_recordings():
    try:
        files = os.listdir(RECORD_FOLDER)
        mp3_files = [f for f in files if f.lower().endswith(".mp3")]
        mp3_files.sort(reverse=True)  # 최신순 정렬
        return {"recording": mp3_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"녹음 목록 조회 실패: {str(e)}")


@recording_router.get("/record-files/{filename}")
async def get_recording(filename: str):
    file_path = os.path.join(RECORD_FOLDER, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="audio/mpeg", filename=filename)