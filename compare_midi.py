from music21 import converter, interval, chord
from difflib import SequenceMatcher


def extract_notes(midi_path):
    """MIDI 파일에서 음표(Pitch) 목록을 추출 (코드 포함)"""
    midi = converter.parse(midi_path)
    notes = []

    for element in midi.flat.notes:
        if element.isNote:
            notes.append(str(element.pitch))
        elif element.isChord:
            notes.append('.'.join(str(n) for n in element.pitches))  # 코드의 모든 음 포함

    return notes


def extract_rhythms(midi_path):
    """MIDI 파일에서 리듬(Duration) 목록을 추출"""
    midi = converter.parse(midi_path)
    return [n.duration.quarterLength for n in midi.flat.notes]


def extract_intervals(midi_path):
    """MIDI 파일에서 멜로디 패턴(Interval) 목록을 추출"""
    midi = converter.parse(midi_path)
    notes = [n.pitch for n in midi.flat.notes if n.isNote]

    intervals = []
    for i in range(len(notes) - 1):
        interval_obj = interval.Interval(notes[i], notes[i + 1])
        intervals.append(interval_obj.name)

    return intervals


def extract_chords(midi_path):
    """MIDI 파일에서 코드 진행(Chord Progression) 목록을 추출"""
    midi = converter.parse(midi_path)
    chords = []

    for element in midi.chordify().flat.notes:
        if element.isChord:
            chords.append('.'.join(str(n) for n in element.pitches))

    return chords


def calculate_similarity(list1, list2):
    """두 리스트의 유사도를 SequenceMatcher를 사용해 계산"""
    return SequenceMatcher(None, list1, list2).ratio()


def compare_midi_files(midi1_path, midi2_path):
    """두 개의 MIDI 파일을 비교하여 여러 요소의 유사도를 계산"""

    # 비교 요소 추출
    notes1, notes2 = extract_notes(midi1_path), extract_notes(midi2_path)
    rhythms1, rhythms2 = extract_rhythms(midi1_path), extract_rhythms(midi2_path)
    intervals1, intervals2 = extract_intervals(midi1_path), extract_intervals(midi2_path)
    chords1, chords2 = extract_chords(midi1_path), extract_chords(midi2_path)

    # 유사도 계산
    pitch_similarity = calculate_similarity(notes1, notes2)
    rhythm_similarity = calculate_similarity(rhythms1, rhythms2)
    interval_similarity = calculate_similarity(intervals1, intervals2)
    chord_similarity = calculate_similarity(chords1, chords2)

    # 최종 유사도 (가중치 적용)
    final_similarity = (pitch_similarity * 0.4) + (rhythm_similarity * 0.3) + \
                       (interval_similarity * 0.2) + (chord_similarity * 0.1)

    return {
        "pitch_similarity": round(pitch_similarity, 3),
        "rhythm_similarity": round(rhythm_similarity, 3),
        "interval_similarity": round(interval_similarity, 3),
        "chord_similarity": round(chord_similarity, 3),
        "final_similarity": round(final_similarity, 3)
    }
