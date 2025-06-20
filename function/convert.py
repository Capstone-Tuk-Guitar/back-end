from fastapi import APIRouter, Form, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
import os
import shutil
import requests
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

convert_router = APIRouter()

KLANGIO_API_URL = "https://api.klang.io/transcription"
API_KEY = os.getenv("API_KEY")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 🟢 음악 리스트 가져오기
@convert_router.get("/songs/")
async def get_songs():
    files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".mp3")]
    songs = [{"title": f, "artist": "Unknown", "difficulty": "Custom", "filename": f} for f in files]
    return songs

# 음악 업로드 API
@convert_router.post("/upload/")
async def upload_song(file: UploadFile):
    filename = file.filename if file.filename.endswith(".mp3") else f"{file.filename}.mp3"
    file_path = os.path.join(UPLOAD_DIR, filename)

    # 중복 체크 (파일명이 동일하면 새로운 이름 생성)
    counter = 1
    base_name, ext = os.path.splitext(filename)
    while os.path.exists(file_path):
        filename = f"{base_name}_{counter}{ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        counter += 1

    # 파일 저장
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"title": filename, "artist": "Unknown", "filename": filename}

# 음악 삭제 API
@convert_router.delete("/delete/")
async def delete_song(title: str):
    file_path = os.path.join(UPLOAD_DIR, title)
    if os.path.exists(file_path):
        os.remove(file_path)  # 파일 삭제
        return {"message": "Deleted"}
    return {"error": "파일을 찾을 수 없습니다."}

# 음악 파일 제공 API
@convert_router.get("/uploads/{filename}")
async def get_song_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/mpeg", filename=filename)
    return {"error": "파일을 찾을 수 없습니다."}

# 음악 변환 API (Klangio)
@convert_router.post("/convert/transcription/")
async def transcription(
        model: str = Form(...),
        title: str = Form(...),
        composer: str = Form(...),
        file: UploadFile = File(...),
        outputs: str = Form(...),
):
    try:
        files = {"file": (file.filename, file.file, file.content_type)}
        params = {"model": model, "title": title, "composer": composer}
        data = {"outputs": outputs}

        headers = {
            "accept": "application/json",
            "kl-api-key": API_KEY,
        }

        response = requests.post(
            KLANGIO_API_URL, params=params, files=files, data=data, headers=headers
        )

        if not response.ok:
            raise HTTPException(status_code=response.status_code, detail=f"Klango API Error: {response.text}")

        response_data = response.json()
        job_id = response_data.get("job_id")

        if not job_id:
            raise HTTPException(status_code=500, detail="Job ID를 가져오지 못했습니다.")

        return JSONResponse(content={"job_id": job_id}, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# 변환된 파일 다운로드 API
@convert_router.get("/convert/download/{job_id}/{output_type}")
async def download_file(job_id: str, output_type: str):
    try:
        DOWNLOAD_URL = f"https://api.klang.io/job/{job_id}/{output_type}"
        headers = {"accept": "application/json", "kl-api-key": API_KEY}

        response = requests.get(DOWNLOAD_URL, headers=headers, stream=True)

        if response.status_code == 200:
            return StreamingResponse(
                response.iter_content(),
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={job_id}.{output_type}"}
            )
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Download Failed: {response.text}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")