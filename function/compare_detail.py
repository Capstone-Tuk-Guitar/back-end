from fastapi import APIRouter, UploadFile, File
import os
import uuid
from music21 import converter, note, chord, stream

compare_detail_router = APIRouter()

# 리듬 추출
def extract_rhythms(file_path):
    score = converter.parse(file_path)
    flat_notes = score.parts[0].flatten().notes
    rhythms = []
    for element in flat_notes:
        rhythms.append(element.offset)  # 시작 시간 기준
    return rhythms

# 마디 단위 조성 추출
def extract_key_per_measure(file_path):
    score = converter.parse(file_path)
    part = score.parts[0]
    key_list = []
    note_counter = 1
    for measure in part.getElementsByClass('Measure'):
        k = measure.analyze('key')
        first_note = measure.notes[0] if measure.notes else None
        key_list.append({
            "key": f"{k.tonic.name} {k.mode}",
            "start_note": note_counter
        })
        note_counter += len(measure.notes)
    return key_list

# 리듬 차이 계산
def get_rhythm_differences(seq1, seq2, tolerance):
    min_len = min(len(seq1), len(seq2))
    differences = []
    for i in range(min_len):
        if abs(seq1[i] - seq2[i]) > tolerance:
            differences.append({
                "차이 나는 음표 번호": i + 1,
                "1번째 파일 음정": f"{float(seq1[i]):.3f}초",
                "2번째 파일 음정": f"{float(seq2[i]):.3f}초",
                "시간": round(i * 0.5, 2)
            })
    return differences

# 조성 차이 계산
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

@compare_detail_router.post("/compare/detail/")
async def compare_midi_detail(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    file1_path = f"temp_{uuid.uuid4()}_{file1.filename}"
    file2_path = f"temp_{uuid.uuid4()}_{file2.filename}"

    with open(file1_path, "wb") as f:
        f.write(await file1.read())
    with open(file2_path, "wb") as f:
        f.write(await file2.read())

    rhythm1 = extract_rhythms(file1_path)
    rhythm2 = extract_rhythms(file2_path)

    keys1 = extract_key_per_measure(file1_path)
    keys2 = extract_key_per_measure(file2_path)

    key_diff_list = get_key_differences(keys1, keys2)
    rhythm_diff_list = get_rhythm_differences(rhythm1, rhythm2, tolerance=0.25)

    os.remove(file1_path)
    os.remove(file2_path)

    return {
        "조성 차이": key_diff_list,
        "리듬 차이": rhythm_diff_list
    }
