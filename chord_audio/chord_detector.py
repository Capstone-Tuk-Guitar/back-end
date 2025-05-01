import numpy as np
import sounddevice as sd
import scipy.fftpack as fftpack
import json
import time
from collections import Counter, deque

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
SAMPLE_RATE = 44100
BUFFER_SIZE = 2048
WINDOW_TIME = 0.5
HISTORY_SECONDS = 1.5
BEAT_INTERVAL = 0.5
HPS_HARMONICS = 4  # HPS에서 사용할 고조파 수


# 주파수 -> 음이름 변환
def freq_to_note_name(freq):
    if freq <= 0:
        return None
    A4 = 440.0
    semitones = 12 * np.log2(freq / A4)
    midi_note = int(round(69 + semitones))
    note_name = NOTE_NAMES[midi_note % 12]
    tolerance = 0.5  # 작은 tolerance로 설정
    for note in NOTE_NAMES:
        target_freq = A4 * (2 ** ((NOTE_NAMES.index(note) - 9) / 12))
        if abs(freq - target_freq) <= tolerance:
            return note
    return note_name


# 코드 데이터 불러오기
def load_chord_data(path='chord_notes.json'):
    with open(path, 'r') as f:
        return json.load(f)


# 코드 유사도 계산
def similarity_score(notes_detected, chord_notes_data):
    score = 0.0
    total_weight = 0.0
    for note_info in chord_notes_data:
        note = note_info["note"]
        weight = note_info.get("weight", 1.0)
        total_weight += weight
        if note in notes_detected:
            score += weight
    return score / total_weight if total_weight > 0 else 0.0


# 코드 추정
def detect_chord_from_notes(notes, chord_data):
    note_set = set(notes)
    best_match = ("Unknown", None, 0.0)
    partial_match_rules = {
        '5': (0.5, 2), 'maj': (0.6, 2), 'min': (0.6, 2), '7': (0.65, 3),
        'maj7': (0.65, 3), 'm7': (0.65, 3), 'dim': (0.6, 2), 'dim7': (0.65, 3),
        'aug': (0.6, 2), 'sus2': (0.6, 2), 'sus4': (0.6, 2), '7sus4': (0.65, 3)
    }
    for chord, types in chord_data.items():
        for chord_type, data in types.items():
            chord_notes_data = data['notes']
            chord_note_names = [n["note"] for n in chord_notes_data]
            matched_notes = note_set.intersection(set(chord_note_names))
            matched_count = len(matched_notes)
            min_score, min_notes_required = partial_match_rules.get(chord_type, (0.6, 2))
            if matched_count >= min_notes_required:
                score = similarity_score(note_set, chord_notes_data)
                if score > best_match[2] and score >= min_score:
                    best_match = (chord, chord_type, score)
    if best_match[2] > 0:
        return best_match[0], best_match[1], '추정'
    return "Unknown", None, None


def weighted_note_score(note_history, chord_data):
    score_counter = Counter()
    for frame in note_history:
        for note in frame:
            for chord in chord_data.values():
                for chord_type in chord.values():
                    for note_info in chord_type['notes']:
                        if note_info['note'] == note:
                            weight = note_info.get("weight", 1.0)
                            score_counter[note] += weight
    return [note for note, _ in score_counter.most_common()]


# HPS 적용한 주파수 추출 + 이동평균 적용
class FrequencyStabilizer:
    def __init__(self, window_len=5):
        self.freq_history = deque(maxlen=window_len)

    def smooth(self, freqs):
        self.freq_history.append(freqs)
        all_freqs = [f for frame in self.freq_history for f in frame]
        counts = Counter(all_freqs)
        most_common = [freq for freq, _ in counts.most_common(6)]
        return sorted(set(most_common))


def extract_dominant_freqs(audio, sample_rate, top_n=6, min_freq=80, max_freq=800):
    window = np.hanning(len(audio))
    spectrum = np.abs(fftpack.fft(audio * window))[:len(audio) // 2]
    freqs = np.fft.fftfreq(len(audio), 1 / sample_rate)[:len(audio) // 2]

    valid_indices = np.where((freqs >= min_freq) & (freqs <= max_freq))
    spectrum = spectrum[valid_indices]
    freqs = freqs[valid_indices]

    # HPS 알고리즘 적용
    hps_spectrum = np.copy(spectrum)
    for h in range(2, 5):
        decimated = spectrum[::h]
        hps_spectrum[:len(decimated)] *= decimated

    # 강한 주파수 탐색
    threshold = np.max(hps_spectrum) * 0.3  # threshold를 조금 높임
    strong_indices = np.where(hps_spectrum >= threshold)[0]
    if len(strong_indices) == 0:
        return []

    effective_top_n = min(top_n, len(strong_indices))
    peak_indices = strong_indices[np.argpartition(hps_spectrum[strong_indices], -effective_top_n)[-effective_top_n:]]
    dominant_freqs = sorted(freqs[peak_indices])
    return dominant_freqs


# 중복 음 제거 및 필터링
def remove_octave_duplicates(note_list):
    seen = set()
    filtered_notes = []
    for note in note_list:
        if note and note not in seen:
            seen.add(note)
            filtered_notes.append(note)
    return filtered_notes


def remove_rare_notes(note_list, history_deque, min_count=2):
    all_notes = [n for sub in history_deque for n in sub]
    valid_notes = [n for n in note_list if all_notes.count(n) >= min_count]
    return valid_notes


# 코드 감지기 클래스
class ChordDetector:
    def __init__(self):
        self.chord_data = load_chord_data()
        self.note_history = deque(maxlen=int(HISTORY_SECONDS / WINDOW_TIME))
        self.last_beat_time = time.time()
        self.previous_chord = None
        self.chord_repeat_count = 0
        self.confirmed_chord = None
        self.freq_smoother = FrequencyStabilizer(window_len=3)

    def process(self, audio_chunk):
        # 주파수 추출
        raw_freqs = extract_dominant_freqs(audio_chunk, SAMPLE_RATE)

        # 주파수 및 음표 출력
        print(f"[주파수] {np.round(raw_freqs, 2)}")

        smoothed_freqs = self.freq_smoother.smooth(raw_freqs)

        # 주파수 기반 음표 변환
        raw_notes = [freq_to_note_name(f) for f in smoothed_freqs]
        filtered_notes = remove_octave_duplicates(raw_notes)

        self.note_history.append(filtered_notes)
        smoothed_notes = remove_rare_notes(filtered_notes, self.note_history)

        # 가중치 기반 주요 노트 계산
        most_common_notes = weighted_note_score(self.note_history, self.chord_data)[:5]

        # 코드 추정
        chord = detect_chord_from_notes(most_common_notes, self.chord_data)

        # 주기마다 코드 감지
        now = time.time()
        if now - self.last_beat_time >= BEAT_INTERVAL:
            self.last_beat_time = now
            if chord[:2] == self.previous_chord:
                self.chord_repeat_count += 1
            else:
                self.chord_repeat_count = 1
            self.previous_chord = chord[:2]
            if self.chord_repeat_count >= 2:
                if self.confirmed_chord != chord[:2]:
                    self.confirmed_chord = chord[:2]
                    print(f"[코드 전환] {self.confirmed_chord[0]} {self.confirmed_chord[1]}")

        return smoothed_notes, most_common_notes, chord