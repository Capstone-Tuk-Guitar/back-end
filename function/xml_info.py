from fastapi import APIRouter, HTTPException
from music21 import converter, harmony, tempo
import os

xml_info_router = APIRouter()

@xml_info_router.get("/xml_info/{music_id}")
async def get_chord_timing(music_id: int):
    file_path = r"C:\Download\takajii_-_rain intro.xml"  # 본인 XML 파일 경로

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="XML file not found")

    try:
        score = converter.parse(file_path)

        # 템포 추출 (없으면 기본값 76)
        bpm = 76
        for t in score.recurse().getElementsByClass(tempo.MetronomeMark):
            if t.number:
                bpm = t.number
                break

        seconds_per_beat = 60.0 / bpm

        kind_map = {
            "major": "major",
            "minor": "minor",
            "dominant": "7",
            "dominant-seventh": "7",
            "major-seventh": "maj7",
            "minor-seventh": "m7",
            "diminished": "dim",
            "diminished-seventh": "dim7",
            "augmented": "aug",
            "suspended-second": "sus2",
            "suspended-fourth": "sus4",
            "power": "5",
            "fifth": "5"
        }

        chords = []
        for el in score.recurse():
            if isinstance(el, harmony.ChordSymbol):
                # 코드 이름 직접 생성
                root = el.root().name if el.root() else "Unknown"
                kind_raw = el.chordKind

                # 특별 처리: 7sus4
                if kind_raw in ["dominant", "dominant-seventh"] and el.chordKind == "suspended-fourth":
                    chord_name = f"{root} 7sus4"
                else:
                    kind_mapped = kind_map.get(kind_raw, kind_raw)
                    chord_name = f"{root} {kind_mapped}".strip()

                # 시간 계산
                measure_num = el.measureNumber
                offset_in_measure = float(el.offset)
                beats_from_start = ((measure_num - 1) * 4) + offset_in_measure
                start_time = beats_from_start * seconds_per_beat

                chords.append({
                    "chord": chord_name,
                    "time": round(start_time, 2)
                })

        return {"bpm": bpm, "chords": chords}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")
