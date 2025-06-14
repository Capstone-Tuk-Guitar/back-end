from fastapi import APIRouter, UploadFile, File, HTTPException
import os
from datetime import datetime
from dotenv import load_dotenv
import subprocess

music_record_router = APIRouter()

load_dotenv()
FFMPEG_PATH = os.getenv("FFMPEG_PATH")

if not FFMPEG_PATH or not os.path.exists(FFMPEG_PATH):
    raise RuntimeError("FFMPEG 경로 오류.")

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads", "record")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@music_record_router.post("/record/upload")
async def upload_record(file: UploadFile = File(...)):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        webm_filename = f"record_{timestamp}.webm"
        mp3_filename = f"record_{timestamp}.mp3"

        webm_path = os.path.join(UPLOAD_FOLDER, webm_filename)
        mp3_path = os.path.join(UPLOAD_FOLDER, mp3_filename)

        # webm 저장
        with open(webm_path, "wb") as f:
            f.write(await file.read())

        # FFmpeg로 mp3변환
        command = [
            FFMPEG_PATH,
            "-i", webm_path,
            "-vn",  # 비디오 제거
            "-ar", "44100",  # 샘플링 주파수
            "-ac", "2",  # 스테레오
            "-b:a", "192k",  # 비트레이트
            mp3_path
        ]

        subprocess.run(command, check=True)

        os.remove(webm_path)

        return {
            "message": "녹음 저장 및 mp3 변환 완료",
            "mp3_path": mp3_path
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"FFmpeg 변환 실패: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"녹음 파일 저장 실패: {e}")
