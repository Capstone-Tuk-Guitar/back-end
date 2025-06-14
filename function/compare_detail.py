from fastapi import APIRouter, UploadFile, File
import os
import uuid
from music21 import converter, note, chord, interval, pitch as m21pitch

compare_detail_router = APIRouter()

# 특징 추출
def extract_music21_features(file_path):
    score = converter.parse(file_path)
    flat_notes = score.parts[0].flatten().notes

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
                val1 = f"{float(seq1[i]):.2f}초"
                val2 = f"{float(seq2[i]):.2f}초"

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


