from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

KLANGO_API_URL = "https://api.klang.io/transcription"
API_KEY = "0xkl-8b23398583b430e7a81ee4618de80079"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React 개발 서버 주소
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/transcription/")
async def transcription(
        model: str = Form(..., description="Model type (e.g., guitar)"),
        title: str = Form(..., description="Title of the song"),
        composer: str = Form(..., description="Composer of the song"),
        file: UploadFile = File(..., description="The audio file to transcribe"),
        outputs: str = Form(..., description="Comma-separated output formats (e.g., pdf,midi)"),
):
    try:
        files = {"file": (file.filename, file.file, file.content_type)}

        params = {
            "model": model,
            "title": title,
            "composer": composer,
        }

        data = {
            "outputs": outputs,  # outputs를 문자열 그대로 전달
        }

        headers = {
            "accept": "application/json",
            "kl-api-key": API_KEY,
        }

        response = requests.post(
            KLANGO_API_URL,
            params=params,
            files=files,
            data=data,
            headers=headers,
        )

        if not response.ok:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"{response.status_code}: Klango API Error: {response.text}",
            )

        response_data = response.json()
        job_id = response_data.get("job_id")

        if not job_id:
            raise HTTPException(status_code=500, detail="Job ID를 가져오지 못했습니다.")

        return JSONResponse(content={"job_id": job_id}, status_code=response.status_code)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")