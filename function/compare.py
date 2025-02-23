from fastapi import APIRouter, UploadFile, File
import pretty_midi
import os

compare_router = APIRouter()

TIME_THRESHOLD = 0.05  # 50ms 허용
PITCH_THRESHOLD = 1    # 음 높이 차이 허용

def compare_midi(file1_path, file2_path):
    midi1 = pretty_midi.PrettyMIDI(file1_path)
    midi2 = pretty_midi.PrettyMIDI(file2_path)

    notes1 = [(note.start, note.pitch, note.end - note.start) for inst in midi1.instruments for note in inst.notes]
    notes2 = [(note.start, note.pitch, note.end - note.start) for inst in midi2.instruments for note in inst.notes]

    matched_notes = 0
    for n1 in notes1:
        for n2 in notes2:
            if abs(n1[0] - n2[0]) <= TIME_THRESHOLD and abs(n1[1] - n2[1]) <= PITCH_THRESHOLD:
                matched_notes += 1
                break

    total_notes = max(len(notes1), len(notes2))
    accuracy = (matched_notes / total_notes) * 100 if total_notes > 0 else 0
    return accuracy

@compare_router.post("/compare/")
async def compare_midi_files(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    file1_path = f"temp_{file1.filename}"
    file2_path = f"temp_{file2.filename}"

    with open(file1_path, "wb") as f:
        f.write(await file1.read())

    with open(file2_path, "wb") as f:
        f.write(await file2.read())

    accuracy = compare_midi(file1_path, file2_path)

    os.remove(file1_path)
    os.remove(file2_path)

    return {"accuracy": accuracy}
