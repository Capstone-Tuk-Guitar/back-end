from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
import os
import tempfile
import subprocess
import xml.etree.ElementTree as ET
from music21 import converter
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

mxl_router = APIRouter()

# MuseScore 실행 경로
MUSESCORE_PATH = os.getenv("MUSESCORE_PATH")

@mxl_router.post("/mxl-converter/")
async def convert_to_mxl(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    try:
        # 임시 작업 디렉토리 생성
        with tempfile.TemporaryDirectory() as tmpdir:
            midi_path = os.path.join(tmpdir, file.filename)             # 업로드된 MIDI 파일 경로
            musicxml_path = os.path.join(tmpdir, "output.musicxml")     # 생성될 MusicXML 파일 경로
            container_dir = os.path.join(tmpdir, "META-INF")            # MXL 메타데이터 디렉토리
            os.makedirs(container_dir, exist_ok=True)

            # 업로드된 MIDI 파일 저장
            with open(midi_path, "wb") as f:
                f.write(await file.read())

            # MuseScore CLI로 MIDI → MusicXML 변환
            result = subprocess.run([MUSESCORE_PATH, "-o", musicxml_path, midi_path], capture_output=True, text=True)
            # 변환 실패 시 에러 반환
            if result.returncode != 0 or not os.path.exists(musicxml_path):
                return {"error": "MuseScore 변환 실패", "stderr": result.stderr}

            # MusicXML 파일 정리
            try:
                tree = ET.parse(musicxml_path)
                root = tree.getroot()

                # 악보 상단 제목/크레딧 제거
                for credit in root.findall("credit"):
                    root.remove(credit)

                # credit-words (악보 상단 텍스트) 제거
                for parent in root.iter():
                    for child in list(parent):
                        if child.tag == "credit-words":
                            parent.remove(child)

                # 연주 지시문 등 direction-type 내부 텍스트 제거
                for direction_type in root.findall(".//direction-type"):
                    for words in direction_type.findall("words"):
                        direction_type.remove(words)

                # <note> 내부 <lyric> 제거 (가사)
                for note in root.findall(".//note"):
                    for lyric in note.findall("lyric"):
                        note.remove(lyric)

                # identification/creator 제거
                ident = root.find("identification")
                if ident is not None:
                    for creator in ident.findall("creator"):
                        ident.remove(creator)

                # direction 블록 전체 제거
                for part in root.findall(".//part"):
                    for measure in part.findall("measure"):
                        for direction in list(measure):
                            if direction.tag == "direction":
                                if direction.find("direction-type/metronome") is not None:
                                    measure.remove(direction)

                # 정리된 XML 파일 저장
                tree.write(musicxml_path, encoding="utf-8", xml_declaration=True)

            except Exception as e:
                return {"error": f"MusicXML 정리 오류: {str(e)}"}

            # MusicXML 파일을 임시 경로에 복사
            final_path = os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()) + ".musicxml")
            with open(musicxml_path, "rb") as src, open(final_path, "wb") as dst:
                dst.write(src.read())

            # 응답 후 파일 자동 삭제
            if background_tasks:
                background_tasks.add_task(os.remove, final_path)

            # 최종 MusicXML 파일 반환
            return FileResponse(final_path, media_type="application/vnd.recordare.musicxml+xml", filename="converted.musicxml")

    except Exception as e:
        return {"error": str(e)}