from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

KLANGO_API_URL = "https://api.klang.io/transcription"
API_KEY = os.getenv("API_KEY")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/transcription/")
async def transcription(
        model: str = Form(...),
        title: str = Form(...),
        composer: str = Form(...),
        file: UploadFile = File(...),
        outputs: str = Form(...)
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
            KLANGO_API_URL, params=params, files=files, data=data, headers=headers
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


@app.get("/download/{job_id}/{output_type}")
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