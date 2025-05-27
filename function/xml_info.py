from fastapi import APIRouter, UploadFile, File, HTTPException
from music21 import converter, harmony, tempo
import tempfile

xml_info_router = APIRouter()

@xml_info_router.post("/xml_info/")
async def get_chord_timing(file: UploadFile = File(...)):
    try:
        # 임시파일에 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        score = converter.parse(tmp_path)

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
            "power": "5", "fifth": "5"
        }

        chords = []
        for el in score.recurse():
            if isinstance(el, harmony.ChordSymbol):
                root = el.root().name if el.root() else "Unknown"
                kind_raw = el.chordKind
                kind_mapped = kind_map.get(kind_raw, kind_raw)
                chord_name = f"{root} {kind_mapped}".strip()

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
