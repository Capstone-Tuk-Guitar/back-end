import sys
import numpy as np
import copy
from threading import Thread
from pyaudio import PyAudio, paInt16
from tuner_audio.threading_helper import ProtectedList

class AudioAnalyzer(Thread):
    """ This AudioAnalyzer reads the microphone and finds the frequency of the loudest tone. """

    # 설정값: 기타 같은 현악기 소리를 감지하도록 조정됨
    SAMPLING_RATE = 48000  # 일반적으로 44100 또는 48000 사용
    CHUNK_SIZE = 1024  # 한번에 읽을 샘플 개수
    BUFFER_TIMES = 50  # 버퍼 크기 결정
    ZERO_PADDING = 3  # FFT 계산 시 제로 패딩 (분해능 향상)
    NUM_HPS = 3  # Harmonic Product Spectrum 적용 단계

    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def __init__(self, queue, input_device_index=None):
        super().__init__()  # Thread 초기화 (불필요한 인자 전달 방지)
        self.queue = queue
        self.buffer = np.zeros(self.CHUNK_SIZE * self.BUFFER_TIMES)
        self.hanning_window = np.hanning(len(self.buffer))
        self.running = False
        self.input_device_index = input_device_index  # 입력 장치 인덱스 저장

        try:
            self.audio_object = PyAudio()
            self.stream = self.audio_object.open(
                format=paInt16,
                channels=1,
                rate=self.SAMPLING_RATE,
                input=True,
                output=False,
                frames_per_buffer=self.CHUNK_SIZE,
                input_device_index=self.input_device_index  # 장치 인덱스 적용
            )
        except Exception as e:
            sys.stderr.write(f'Error: Line {sys.exc_info()[-1].tb_lineno} {type(e).__name__} {e}\n')
            return

    @staticmethod
    def frequency_to_number(freq, a4_freq=440.0):
        """ 주어진 주파수를 노트 넘버(예: A4 = 69)로 변환 """
        if freq == 0:
            sys.stderr.write("Error: No frequency data. Program has potentially no access to microphone\n")
            return 0
        return 12 * np.log2(freq / a4_freq) + 69

    @staticmethod
    def number_to_frequency(number, a4_freq=440.0):
        """ 노트 넘버(예: 69)를 주파수(Hz)로 변환 """
        return a4_freq * 2.0 ** ((number - 69) / 12.0)

    @staticmethod
    def number_to_note_name(number):
        """ 노트 넘버를 노트 이름(예: 69 -> 'A')으로 변환 """
        return AudioAnalyzer.NOTE_NAMES[int(round(number) % 12)]

    @staticmethod
    def frequency_to_note_name(frequency, a4_freq=440.0):
        """ 주파수를 노트 이름(예: 440 -> 'A')으로 변환 """
        number = AudioAnalyzer.frequency_to_number(frequency, a4_freq)
        return AudioAnalyzer.number_to_note_name(number)

    def run(self):
        """ 마이크 입력을 처리하고 FFT를 통해 가장 큰 주파수를 감지 """
        self.running = True

        while self.running:
            try:
                # 마이크 데이터 읽기
                data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                data = np.frombuffer(data, dtype=np.int16)

                # 기존 버퍼에서 데이터를 이동 후 새로운 데이터 추가
                self.buffer[:-self.CHUNK_SIZE] = self.buffer[self.CHUNK_SIZE:]
                self.buffer[-self.CHUNK_SIZE:] = data

                # FFT 수행 (제로 패딩 + 해닝 윈도우 적용)
                magnitude_data = abs(np.fft.fft(np.pad(
                    self.buffer * self.hanning_window,
                    (0, len(self.buffer) * self.ZERO_PADDING),
                    "constant"
                )))

                # FFT 결과에서 절반만 사용
                magnitude_data = magnitude_data[:int(len(magnitude_data) / 2)]

                # HPS (Harmonic Product Spectrum) 적용
                magnitude_data_orig = copy.deepcopy(magnitude_data)
                for i in range(2, self.NUM_HPS + 1):
                    hps_len = int(np.ceil(len(magnitude_data) / i))
                    magnitude_data[:hps_len] *= magnitude_data_orig[::i]

                # 주파수 배열 생성
                frequencies = np.fft.fftfreq(int((len(magnitude_data) * 2) / 1), 1. / self.SAMPLING_RATE)

                # 60Hz 이하 주파수 제거
                for i, freq in enumerate(frequencies):
                    if freq > 60:
                        magnitude_data[:i - 1] = 0
                        break

                # 가장 강한 주파수를 큐에 추가
                self.queue.put(round(frequencies[np.argmax(magnitude_data)], 2))

            except Exception as e:
                sys.stderr.write(f'Error: Line {sys.exc_info()[-1].tb_lineno} {type(e).__name__} {e}\n')

        # 마이크 스트림 정리
        self.stream.stop_stream()
        self.stream.close()
        self.audio_object.terminate()