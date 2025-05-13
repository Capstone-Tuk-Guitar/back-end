from fastapi import APIRouter, UploadFile, File, Form
import os
import uuid
from music21 import converter, interval, pitch
from function.db import get_db_connection

compare_router = APIRouter()

def normalize_pitches(notes, tolerance=1):
    """음표 리스트를 MIDI 값으로 변환하여 오차 적용"""
    normalized = []
    for n in notes:
        try:
            midi_value = pitch.Pitch(n).midi
            normalized.append(round(midi_value / tolerance) * tolerance)
        except:
            normalized.append(n)
    return normalized

def extract_notes(midi_path, tolerance=2):
    """MIDI 파일에서 음표(Pitch) 목록을 추출 (오차 적용)"""
    midi = converter.parse(midi_path)
    notes = []
    for element in midi.flat.notes:
        if element.isNote:
            notes.append(str(element.pitch))
    return normalize_pitches(notes, tolerance)

def extract_rhythms(midi_path, tolerance=0.3):
    """MIDI 파일에서 리듬(Duration) 목록을 추출 (오차 적용)"""
    midi = converter.parse(midi_path)
    rhythms = [n.duration.quarterLength for n in midi.flat.notes]
    return [round(rhythm / tolerance) * tolerance for rhythm in rhythms]

def extract_intervals(midi_path, tolerance=3):
    """MIDI 파일에서 멜로디 패턴(Interval) 목록을 추출 (오차 적용)"""
    midi = converter.parse(midi_path)
    notes = [n.pitch for n in midi.flat.notes if n.isNote]

    raw_intervals = []
    for i in range(len(notes) - 1):
        try:
            iv = interval.Interval(notes[i], notes[i + 1])
            raw_intervals.append(iv.semitones)
        except:
            continue

    normalized_intervals = [round(i / tolerance) * tolerance for i in raw_intervals]
    return normalized_intervals

def calculate_penalty_score(list1, list2, tolerance):
    """100점 시작 후, tolerance 밖일 때마다 1점 감점"""
    min_len = min(len(list1), len(list2))
    if min_len == 0:
        return 0.0

    score = 100.0
    for i in range(min_len):
        try:
            if abs(float(list1[i]) - float(list2[i])) > tolerance:
                score -= 1.0
        except:
            continue

    # 점수는 0점 밑으로 내려가지 않게
    score = max(score, 0.0)

    return score / 100.0  # 0~1로 변환해서 반환

def compare_midi_files_with_penalty(midi1_path, midi2_path):
    """MIDI 파일 비교"""
    notes1, notes2 = extract_notes(midi1_path), extract_notes(midi2_path)
    rhythms1, rhythms2 = extract_rhythms(midi1_path), extract_rhythms(midi2_path)
    intervals1, intervals2 = extract_intervals(midi1_path), extract_intervals(midi2_path)

    pitch_similarity = calculate_penalty_score(notes1, notes2, tolerance=2) #한 음 차이 허용
    rhythm_similarity = calculate_penalty_score(rhythms1, rhythms2, tolerance=0.5)
    interval_similarity = calculate_penalty_score(intervals1, intervals2, tolerance=2)

    final_similarity = (pitch_similarity * 0.4) + (rhythm_similarity * 0.5) + (interval_similarity * 0.1)

    return {
        "pitch_similarity": round(pitch_similarity, 3),
        "rhythm_similarity": round(rhythm_similarity, 3),
        "interval_similarity": round(interval_similarity, 3),
        "final_similarity": round(final_similarity, 3)
    }

@compare_router.post("/compare/")
async def compare_midi_files(
    user_id: int = Form(...),  # ✅ user_id 추가
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    # UUID로 임시 파일 저장
    file1_path = f"temp_{uuid.uuid4()}_{file1.filename}"
    file2_path = f"temp_{uuid.uuid4()}_{file2.filename}"

    with open(file1_path, "wb") as f:
        f.write(await file1.read())

    with open(file2_path, "wb") as f:
        f.write(await file2.read())

    # 유사도 비교 (원래 너가 쓰던 비교 함수)
    similarity_result = compare_midi_files_with_penalty(file1_path, file2_path)

    # DB 연결
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # ✅ user_id + file_path 둘 다 조건으로 music_id 찾기
        cursor.execute(
            "SELECT music_id FROM Music WHERE user_id = %s AND file_path LIKE %s",
            (user_id, f"%{file1.filename}%")
        )
        music_list = cursor.fetchall()  # ✅ 반드시 fetchall()

        if not music_list:
            print(f"❌ user_id={user_id} / file={file1.filename} 에 대한 music_id를 찾지 못함")
        else:
            for music in music_list:
                music_id = music[0]
                cursor.execute("""
                    INSERT INTO record (music_id, record_file, accuracy, record_date)
                    VALUES (%s, %s, %s, NOW())
                """, (music_id, file2.filename, similarity_result["final_similarity"]))
                print(f"✅ record 테이블 저장 완료: music_id={music_id}, record_file={file2.filename}, accuracy={similarity_result['final_similarity']}")

            db.commit()

    except Exception as e:
        print(f"❌ record 테이블 저장 실패: {e}")

    finally:
        cursor.close()
        db.close()

    # 임시 파일 삭제
    os.remove(file1_path)
    os.remove(file2_path)

    # 결과 반환
    return similarity_result