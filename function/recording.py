from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

recording_router = APIRouter()

# record 폴더 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORD_DIR = os.path.join(BASE_DIR, "..", "record")
os.makedirs(RECORD_DIR, exist_ok=True)

# 녹음 파일 목록 (.webm)
@recording_router.get("/record-files")
def list_record_files():
    try:
        files = [f for f in os.listdir(RECORD_DIR) if f.endswith(".webm")]
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 특정 파일 스트리밍 또는 다운로드
@recording_router.get("/record-files/{filename}")
def get_record_file(filename: str):
    file_path = os.path.join(RECORD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/webm", filename=filename)
    raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")