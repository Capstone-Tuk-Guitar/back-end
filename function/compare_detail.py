from fastapi import APIRouter, UploadFile, File
import os
import uuid
from music21 import converter, note, chord, tempo as m21tempo

compare_detail_router = APIRouter()

def get_seconds_per_quarter(score):
    bpm = None
    for mm in score.recurse().getElementsByClass(m21tempo.MetronomeMark):
        if getattr(mm, "number", None):
            bpm = mm.number
            break
    if bpm is None:
        bpm = 76.0
    return 60.0 / float(bpm)

# 리듬 추출
def extract_rhythms(file_path):
    score = converter.parse(file_path)
    seconds_per_quarter = get_seconds_per_quarter(score)
    flat_notes = score.parts[0].flatten().notes
    rhythms = []
    for element in flat_notes:
        # element.offset는 quarter-length 단위(예: 0, 1.0, 1.5 등)일 수 있음 -> 초로 변환
        offset_quarters = float(element.offset)
        offset_seconds = offset_quarters * seconds_per_quarter
        rhythms.append(offset_seconds)
    return rhythms

# 마디 단위 => 조성 및 그 마디의 시작 음표 인덱스 추출
def extract_key_per_measure(file_path):
    score = converter.parse(file_path)
    part = score.parts[0]
    key_list = []
    note_counter = 1
    for measure in part.getElementsByClass('Measure'):
        notes_in_measure = [n for n in measure.notes]
        if not notes_in_measure:
            continue
        k = measure.analyze('key')
        key_list.append({
            "key": f"{k.tonic.name} {k.mode}",
            "start_note": note_counter
        })
        note_counter += len(notes_in_measure)
    return key_list

# 마디 단위 조성 차이 탐지 (리스트 반환)
def get_key_differences(keys1, keys2):
    min_len = min(len(keys1), len(keys2))
    differences = []
    for i in range(min_len):
        if keys1[i]["key"] != keys2[i]["key"]:
            differences.append({
                "차이 나는 음표 번호": keys1[i]["start_note"],
                "파일1": keys1[i]["key"],
                "파일2": keys2[i]["key"]
            })
    return differences

# 리듬(시작시간) 차이 탐지
def get_rhythm_differences(seq1, seq2, tolerance):
    min_len = min(len(seq1), len(seq2))
    differences = []
    for i in range(min_len):
        t1 = float(seq1[i])
        t2 = float(seq2[i])
        diff = abs(t1 - t2)
        if diff > tolerance:
            differences.append({
                "차이 나는 음표 개수": i + 1,
                "1번째 파일 음정": f"{t1:.3f}초",
                "2번째 파일 음정": f"{t2:.3f}초",
                "시간": round(diff, 3)  # 시작 시간의 절대 차이 (초)
            })
    return differences

@compare_detail_router.post("/compare/detail/")
async def compare_midi_detail(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    file1_path = f"temp_{uuid.uuid4()}_{file1.filename}"
    file2_path = f"temp_{uuid.uuid4()}_{file2.filename}"

    with open(file1_path, "wb") as f:
        f.write(await file1.read())
    with open(file2_path, "wb") as f:
        f.write(await file2.read())

    try:
        rhythm1 = extract_rhythms(file1_path)
        rhythm2 = extract_rhythms(file2_path)

        keys1 = extract_key_per_measure(file1_path)
        keys2 = extract_key_per_measure(file2_path)

        key_diff_list = get_key_differences(keys1, keys2)
        rhythm_diff_list = get_rhythm_differences(rhythm1, rhythm2, tolerance=0.25)

    finally:
        # 임시 파일은 항상 삭제
        if os.path.exists(file1_path):
            os.remove(file1_path)
        if os.path.exists(file2_path):
            os.remove(file2_path)

    return {
        "조성 차이": key_diff_list,
        "리듬 차이": rhythm_diff_list
    }
