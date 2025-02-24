from fastapi import APIRouter, UploadFile, File
import os
from music21 import converter, interval, chord, pitch

compare_router = APIRouter()

def is_pitch_similar(pitch1, pitch2, tolerance=1):
    """두 음표 간의 피치(Pitch)가 특정 오차 범위 내에서 유사한지 확인"""
    try:
        p1 = pitch.Pitch(pitch1).midi  # MIDI 번호 변환 (예: C4 -> 60)
        p2 = pitch.Pitch(pitch2).midi
        return abs(p1 - p2) <= tolerance
    except:
        return False

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

def extract_notes(midi_path, tolerance=1):
    """MIDI 파일에서 음표(Pitch) 목록을 추출 (오차 적용)"""
    midi = converter.parse(midi_path)
    notes = []
    for element in midi.flat.notes:
        if element.isNote:
            notes.append(str(element.pitch))
    return normalize_pitches(notes, tolerance)

def extract_rhythms(midi_path, tolerance=0.2):
    """MIDI 파일에서 리듬(Duration) 목록을 추출 (오차 적용)"""
    midi = converter.parse(midi_path)
    rhythms = [n.duration.quarterLength for n in midi.flat.notes]
    return [round(rhythm / tolerance) * tolerance for rhythm in rhythms]

def extract_intervals(midi_path, tolerance=2):
    """MIDI 파일에서 멜로디 패턴(Interval) 목록을 추출 (오차 적용)"""
    midi = converter.parse(midi_path)
    notes = [n.pitch for n in midi.flat.notes if n.isNote]
    intervals = [interval.Interval(notes[i], notes[i + 1]).name for i in range(len(notes) - 1)]
    return intervals

def calculate_similarity_with_tolerance(list1, list2):
    """오차 범위를 적용한 유사도 계산"""
    set1, set2 = set(list1), set(list2)
    common_elements = set1.intersection(set2)
    total_elements = set1.union(set2)
    return len(common_elements) / len(total_elements) if total_elements else 0

def compare_midi_files_with_tolerance(midi1_path, midi2_path):
    """오차 범위를 적용하여 MIDI 파일 비교"""
    notes1, notes2 = extract_notes(midi1_path), extract_notes(midi2_path)
    rhythms1, rhythms2 = extract_rhythms(midi1_path), extract_rhythms(midi2_path)
    intervals1, intervals2 = extract_intervals(midi1_path), extract_intervals(midi2_path)

    pitch_similarity = calculate_similarity_with_tolerance(notes1, notes2)
    rhythm_similarity = calculate_similarity_with_tolerance(rhythms1, rhythms2)
    interval_similarity = calculate_similarity_with_tolerance(intervals1, intervals2)

    final_similarity = (pitch_similarity * 0.5) + (rhythm_similarity * 0.3) + (interval_similarity * 0.2)

    return {
        "pitch_similarity": round(pitch_similarity, 3),
        "rhythm_similarity": round(rhythm_similarity, 3),
        "interval_similarity": round(interval_similarity, 3),
        "final_similarity": round(final_similarity, 3)
    }

@compare_router.post("/compare/")
async def compare_midi_files(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    file1_path = f"temp_{file1.filename}"
    file2_path = f"temp_{file2.filename}"

    with open(file1_path, "wb") as f:
        f.write(await file1.read())

    with open(file2_path, "wb") as f:
        f.write(await file2.read())

    similarity_result = compare_midi_files_with_tolerance(file1_path, file2_path)

    os.remove(file1_path)
    os.remove(file2_path)

    return similarity_result
