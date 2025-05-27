import numpy as np
import json
import sounddevice as sd
import asyncio
import time

SAMPLE_FREQ = 48000
WINDOW_TIME = 0.3
WINDOW_SIZE = int(SAMPLE_FREQ * WINDOW_TIME)
WINDOW_STEP = int(WINDOW_SIZE // 2)
NUM_HPS = 5
POWER_THRESH = 1e-6
CONCERT_PITCH = 440
WHITE_NOISE_THRESH = 0.2

DELTA_FREQ = SAMPLE_FREQ / WINDOW_SIZE
OCTAVE_BANDS = [50, 100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]
ALL_NOTES = ["A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#"]
HANN_WINDOW = np.hanning(WINDOW_SIZE)

with open('chord_notes.json') as f:
    chord_data = json.load(f)

def find_closest_note_name(pitch):
    i = int(np.round(np.log2(pitch / CONCERT_PITCH) * 12))
    note = ALL_NOTES[i % 12]
    return note

def detect_top4_chords(detected_notes):
    detected_notes_set = set(detected_notes)
    chord_candidates = []

    for root, chords in chord_data.items():
        for chord_type, data in chords.items():
            score = 0
            total_weight = 0
            matched_notes = 0
            all_matched = True
            root_bonus_given = False

            for note_info in data["notes"]:
                note = note_info["note"]
                weight = note_info.get("weight", 1.0)
                total_weight += weight

                if note in detected_notes_set:
                    score += weight
                    matched_notes += 1
                    if not root_bonus_given and note == root:
                        score += 0.12
                        root_bonus_given = True
                else:
                    all_matched = False

            if total_weight == 0:
                continue

            match_score = score / total_weight

            if chord_type in ["sus2", "sus4", "7sus4", "dim", "dim7", "aug"]:
                if matched_notes < 3:
                    continue
                elif matched_notes == 3:
                    match_score += 0.1
                else:
                    match_score += 0.03
            elif chord_type == "5":
                if matched_notes < 2:
                    continue
                required_notes = set([n["note"] for n in data["notes"]])
                if not required_notes.issubset(detected_notes_set):
                    continue
                match_score -= 0.1
            else:
                if matched_notes < 2:
                    continue
                third_note = next((n["note"] for n in data["notes"] if n.get("role") == "third"), None)
                if third_note and third_note not in detected_notes_set:
                    continue

            if all_matched:
                match_score += 0.3

            chord_name = f"{root} {chord_type}"
            chord_candidates.append((chord_name, match_score))

    chord_candidates.sort(key=lambda x: x[1], reverse=True)
    return chord_candidates[:4]


class AudioAnalyzer:
    def __init__(self, websocket):
        self.websocket = websocket
        self.window_samples = np.zeros(WINDOW_SIZE)
        self.note_history = []
        self.running = False
        self.loop = asyncio.get_event_loop()

    def stop(self):
        self.running = False

    def callback(self, indata, frames, time_info, status):
        if not self.running:
            return

        if status:
            return

        if any(indata):
            # 새로운 오디오 데이터를 기존 윈도우 끝에 붙이고 앞부분 잘라서 유지
            self.window_samples = np.concatenate((self.window_samples, indata[:, 0]))
            self.window_samples = self.window_samples[len(indata[:, 0]):]

            # 비동기 분석 함수 실행 (이벤트 루프에 안전하게 등록)
            asyncio.run_coroutine_threadsafe(self.process_audio(), self.loop)
        else:
            print("no input")

    async def process_audio(self):
        signal_power = (np.linalg.norm(self.window_samples, ord=2) ** 2) / len(self.window_samples)
        if signal_power < POWER_THRESH:
            if self.websocket:
                try:
                    await self.websocket.send_json({
                        "top4_chords": [],
                        "primary": None,
                        "status": "listening..."
                    })
                except Exception as e:
                    print(f"음 감지 실패: {e}")
            return

        hann_samples = self.window_samples * HANN_WINDOW
        magnitude_spec = abs(np.fft.rfft(hann_samples))
        freqs = np.fft.rfftfreq(len(hann_samples), 1 / SAMPLE_FREQ)

        # 62Hz 이하 주파수는 제거
        for i in range(int(62 / DELTA_FREQ)):
            magnitude_spec[i] = 0

        # 옥타브 밴드별로 평균 에너지 구해 노이즈 필터링
        for j in range(len(OCTAVE_BANDS) - 1):
            ind_start = int(OCTAVE_BANDS[j] / DELTA_FREQ)
            ind_end = int(OCTAVE_BANDS[j + 1] / DELTA_FREQ)
            ind_end = min(ind_end, len(magnitude_spec))
            avg_energy = (np.linalg.norm(magnitude_spec[ind_start:ind_end], ord=2) ** 2) / (ind_end - ind_start)
            avg_energy = avg_energy ** 0.5
            for i in range(ind_start, ind_end):
                if magnitude_spec[i] < WHITE_NOISE_THRESH * avg_energy:
                    magnitude_spec[i] = 0

        peak_threshold = np.max(magnitude_spec) * 0.3
        peak_indices = [i for i in magnitude_spec.argsort()[::-1] if magnitude_spec[i] > peak_threshold]
        peak_freqs = []
        for i in peak_indices:
            freq = freqs[i]
            if freq > 50:
                peak_freqs.append(freq)
            if len(peak_freqs) >= 6:
                break

        detected_notes = list(set(find_closest_note_name(f) for f in peak_freqs))

        if len(detected_notes) <= 1:
            return

        self.note_history.append(detected_notes)
        if len(self.note_history) > 4:
            self.note_history.pop(0)

        all_notes = [note for sublist in self.note_history for note in sublist]
        note_counts = {note: all_notes.count(note) for note in set(all_notes)}
        stable_notes = [note for note, count in note_counts.items() if count >= 2]

        if stable_notes:
            top4 = detect_top4_chords(stable_notes)

            if top4 and self.websocket:
                top4_names = [name for name, score in top4]
                primary = top4_names[0] if top4_names else None
                data = {
                    "top4_chords": top4_names,
                    "primary": primary
                }
                try:
                    await self.websocket.send_json(data)
                except Exception as e:
                    print(f"Top-4 데이터 전송 실패: {e}")
        else:
            print("안정된 음 기다리는 중...")

    def start(self):
        self.running = True
        try:
            with sd.InputStream(
                channels=1,
                samplerate=SAMPLE_FREQ,
                blocksize=WINDOW_STEP,
                callback=self.callback,
            ):
                while self.running:
                    time.sleep(0.1)
        except Exception as e:
            if self.websocket:
                # 현재 이벤트 루프에 안전하게 coroutine 실행 예약
                asyncio.run_coroutine_threadsafe(
                    self.websocket.send_json({"error": str(e)}),
                    self.loop
                )
            print(f"Audio stream error: {e}")
