from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse
from starlette.responses import Response
from starlette.background import BackgroundTask
from pathlib import Path
import tempfile
import subprocess
import os

mxl_router = APIRouter()

# MuseScore 실행 경로
MUSESCORE_PATH = r"D:\MuseScore 4\bin\MuseScore4.exe"

@mxl_router.post("/mxl-converter/")
async def mxl_converter(file: UploadFile = File(...)):
    try:
        # 1. 업로드된 MIDI 파일을 임시 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mid") as temp_midi:
            temp_midi.write(await file.read())
            temp_midi.flush()
            midi_path = temp_midi.name
            base_name = Path(file.filename).stem

        # 출력할 MXL 파일 경로
        mxl_path = midi_path.replace(".mid", ".mxl")

        # 3. MuseScore CLI 실행 : MIDI → MXL 변환
        result = subprocess.run(
            [MUSESCORE_PATH, midi_path, "-o", mxl_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # 4. 실패 처리
        if result.returncode != 0 or not os.path.exists(mxl_path) or os.path.getsize(mxl_path) < 100:
            return {
                "error": "MuseScore 변환 실패 또는 파일 손상",
                "stdout": result.stdout,
                "stderr": result.stderr
            }

        # 5. 변환된 MXL 파일 반환
        return FileResponse(
            mxl_path,
            media_type="application/vnd.recordare.musicxml",
            filename=f"{base_name}.mxl",
            background=BackgroundTask(lambda: os.remove(mxl_path)),
            headers = {
                "Content-Disposition": f'attachment; filename="{base_name}.mxl"'
            }
        )

    except Exception as e:
        return {"error": str(e)}

    finally:
        # MIDI 임시 파일은 항상 삭제
        if 'midi_path' in locals() and os.path.exists(midi_path):
            os.remove(midi_path)
