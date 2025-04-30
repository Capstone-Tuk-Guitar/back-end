'''from fastapi import APIRouter, UploadFile, File
import os
import uuid
from music21 import converter, pitch, note

compare_detail_router = APIRouter()

# 피치 이름 변환
def get_pitch_name(p):
    try:
        return str(pitch.Pitch(p))
    except:
        return None

# 리듬을 문자열로 변환
def rhythm_to_string(value):
    mapping = {
        4.0: "온음표",
        2.0: "2분음표",
        1.0: "4분음표",
        0.5: "8분음표",
        0.25: "16분음표"
    }
    return mapping.get(round(value, 2), f"{round(value, 2)}분음표")

# 노트 + 시작시간 추출
def get_notes_time(midi_path):
    midi = converter.parse(midi_path)
    notes_with_time = []

    for n in midi.flatten().notes:
        if isinstance(n, note.Note):
            pitch_name = get_pitch_name(str(n.pitch))
            start_time = n.offset
            notes_with_time.append((pitch_name, start_time))

    return notes_with_time

# 리듬 + 시작시간 추출
def get_rhythms_time(midi_path):
    midi = converter.parse(midi_path)
    rhythms_with_time = []

    for n in midi.flatten().notes:
        if isinstance(n, note.Note):
            rhythm_value = round(n.duration.quarterLength, 2)
            rhythm_str = rhythm_to_string(rhythm_value)
            start_time = n.offset
            rhythms_with_time.append((rhythm_str, start_time))

    return rhythms_with_time

# 차이점 추출 (피치/리듬 둘 다 사용)
def differences_time(list1, list2, type_="pitch"):
    min_len = min(len(list1), len(list2))
    differences = []

    for i in range(min_len):
        if list1[i][0] != list2[i][0]:
            differences.append({
                "차이 나는 음표 번호": i + 1,
                "1번째 파일 값": list1[i][0],
                "2번째 파일 값": list2[i][0],
                "시간": round(float(list1[i][1]), 2)
            })

    # 파일 길이 차이 처리
    if len(list1) > min_len:
        for i in range(min_len, len(list1)):
            differences.append({
                "차이 나는 음표 번호": i + 1,
                "1번째 파일 값": list1[i][0],
                "시간": round(float(list1[i][1]), 2)
            })
    elif len(list2) > min_len:
        for i in range(min_len, len(list2)):
            differences.append({
                "차이 나는 음표 번호": i + 1,
                "2번째 파일 값": list2[i][0],
                "시간": round(float(list2[i][1]), 2)
            })

    return differences

# FastAPI 엔드포인트
@compare_detail_router.post("/compare/detail/")
async def compare_midi_files_detailed(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    file1_path = f"temp_{uuid.uuid4()}_{file1.filename}"
    file2_path = f"temp_{uuid.uuid4()}_{file2.filename}"

    with open(file1_path, "wb") as f:
        f.write(await file1.read())
    with open(file2_path, "wb") as f:
        f.write(await file2.read())

    # 피치 & 리듬 추출
    notes1_with_time = get_notes_time(file1_path)
    notes2_with_time = get_notes_time(file2_path)
    rhythms1_with_time = get_rhythms_time(file1_path)
    rhythms2_with_time = get_rhythms_time(file2_path)

    # 차이 계산
    note_diffs = differences_time(notes1_with_time, notes2_with_time, type_="pitch")
    rhythm_diffs = differences_time(rhythms1_with_time, rhythms2_with_time, type_="rhythm")

    # 피치, 리듬 수 비교 정보
    note_count_info = ""
    if len(notes1_with_time) > len(notes2_with_time):
        note_count_info = f"피치 수는 {file1.filename}가 더 많음"
    elif len(notes1_with_time) < len(notes2_with_time):
        note_count_info = f"피치 수는 {file2.filename}가 더 많음"

    rhythm_count_info = ""
    if len(rhythms1_with_time) > len(rhythms2_with_time):
        rhythm_count_info = f"리듬 수는 {file1.filename}가 더 많음"
    elif len(rhythms1_with_time) < len(rhythms2_with_time):
        rhythm_count_info = f"리듬 수는 {file2.filename}가 더 많음"

    # 임시 파일 삭제
    os.remove(file1_path)
    os.remove(file2_path)

    # 결과 반환
    return {
        "음 높낮이 차이": note_diffs,
        "리듬 차이": rhythm_diffs,
        "피치 수 정보": note_count_info,
        "리듬 수 정보": rhythm_count_info
    }'''

from fastapi import APIRouter, UploadFile, File
import os
import uuid
from music21 import converter, note, chord, interval, pitch as m21pitch

compare_detail_router = APIRouter()

# 특징 추출
def extract_music21_features(file_path):
    score = converter.parse(file_path)
    flat_notes = score.parts[0].flat.notes

    pitches = []
    rhythms = []
    intervals = []

    prev_note = None
    for element in flat_notes:
        if isinstance(element, note.Note):
            pitches.append(element.pitch.midi)
            rhythms.append(element.duration.quarterLength)
            if prev_note:
                iv = interval.Interval(noteStart=prev_note, noteEnd=element)
                intervals.append(iv.semitones)
            prev_note = element
        elif isinstance(element, chord.Chord):
            pitches.append(element.notes[0].pitch.midi)
            rhythms.append(element.duration.quarterLength)
            if prev_note:
                iv = interval.Interval(noteStart=prev_note, noteEnd=element.notes[0])
                intervals.append(iv.semitones)
            prev_note = element.notes[0]

    return pitches, rhythms, intervals

# 유사도 계산
def compare_sequences(seq1, seq2, tolerance):
    min_len = min(len(seq1), len(seq2))
    score = 100.0
    for i in range(min_len):
        if abs(seq1[i] - seq2[i]) > tolerance:
            score -= 1.0
    score = max(score, 0.0)
    return score / 100.0

# 차이 리스트 추출
def get_differences(seq1, seq2, tolerance, label):
    min_len = min(len(seq1), len(seq2))
    differences = []
    for i in range(min_len):
        if abs(seq1[i] - seq2[i]) > tolerance:
            val1 = seq1[i]
            val2 = seq2[i]

            # 음 높낮이: MIDI → 음 이름
            if label == "pitch":
                val1 = m21pitch.Pitch(midi=seq1[i]).nameWithOctave
                val2 = m21pitch.Pitch(midi=seq2[i]).nameWithOctave

            # 리듬: 초 단위 문자열
            elif label == "rhythm":
                val1 = f"{seq1[i]:.2f}초"
                val2 = f"{seq2[i]:.2f}초"

            # 시간도 소수점 둘째 자리까지
            differences.append({
                "차이 나는 음표 번호": i + 1,
                "1번째 파일 값": val1,
                "2번째 파일 값": val2,
                "시간": round(i * 0.5, 2)
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

    pitch1, rhythm1, interval1 = extract_music21_features(file1_path)
    pitch2, rhythm2, interval2 = extract_music21_features(file2_path)

    pitch_diff_list = get_differences(pitch1, pitch2, tolerance=1, label="pitch")
    rhythm_diff_list = get_differences(rhythm1, rhythm2, tolerance=0.25, label="rhythm")
    interval_diff_list = get_differences(interval1, interval2, tolerance=1, label="interval")

    os.remove(file1_path)
    os.remove(file2_path)

    return {
        "음 높낮이 차이": pitch_diff_list,
        "리듬 차이": rhythm_diff_list,
        "멜로디 간격 차이": interval_diff_list
    }


