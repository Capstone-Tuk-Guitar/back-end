from fastapi import APIRouter, HTTPException
from music21 import converter, harmony, tempo
import os

xml_info_router = APIRouter()

@xml_info_router.get("/xml_info/{music_id}")
async def get_chord_timing(music_id: int):
    file_path = r"C:\Download\takajii_-_rain intro.xml" # 본인 takajii_-_rain intro.xml 파일경로 넣기

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="XML file not found")

    try:
        score = converter.parse(file_path)

        # 템포 추출 (없으면 기본 76)
        bpm = 76
        for t in score.recurse().getElementsByClass(tempo.MetronomeMark):
            if t.number:
                bpm = t.number
                break

        seconds_per_beat = 60.0 / bpm

        chords = []
        for el in score.recurse():
            if isinstance(el, harmony.ChordSymbol):
                measure_num = el.measureNumber
                offset_in_measure = float(el.offset)
                beats_from_start = ((measure_num - 1) * 4) + offset_in_measure
                start_time = beats_from_start * seconds_per_beat
                chords.append({
                    "chord": el.figure,
                    "time": round(start_time, 2)
                })

        return {"bpm": bpm, "chords": chords}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")
