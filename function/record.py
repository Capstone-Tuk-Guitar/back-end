from fastapi import APIRouter, UploadFile, File, HTTPException
import os
from datetime import datetime

record_router = APIRouter()

# uploads/record 디렉토리 지정
BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads", "record")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@record_router.post("/record/upload")
async def upload_record(file: UploadFile = File(...)):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(UPLOAD_FOLDER, f"record_{timestamp}.webm")

        with open(save_path, "wb") as f:
            f.write(await file.read())

        return {"message": "녹음 파일 저장 완료", "path": save_path}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"녹음 파일 저장 실패: {str(e)}")
