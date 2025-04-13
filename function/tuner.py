import time
import numpy as np
import pyaudio
import asyncio
from threading import Thread
from fastapi import WebSocket, APIRouter
from tuner_audio.threading_helper import ProtectedList
from tuner_audio.audio_analyzer import AudioAnalyzer

tuner_router = APIRouter()

class Tuner:
    """ Guitar tuner using AudioAnalyzer """

    A4_FREQ = 440  # A4 기준 주파수
    MIN_FREQ = 50  # 최소 감지 주파수
    ROLLING_AVG_WINDOW = 3  # 이동 평균 필터 창 크기

    def __init__(self):
        self.queue = ProtectedList(buffer_size=8)
        self.analyzer = None  # 기존 analyzer를 None으로 설정
        self.running = False
        self.last_freqs = []
        self.clients = set()
        self.thread = None  # 실행 중인 스레드 저장

    def get_audio_interface_index(self):
        """ 오디오 인터페이스(예: US-2x2HR) 인덱스를 찾음 """
        audio = pyaudio.PyAudio()
        for i in range(audio.get_device_count()):
            dev_info = audio.get_device_info_by_index(i)
            if "US-2x2HR" in dev_info["name"]:  # 원하는 오디오 인터페이스 이름 입력
                return i
        return None  # 기본 장치를 사용

    async def register_client(self, websocket: WebSocket):
        """ WebSocket 클라이언트 등록 """
        await websocket.accept()
        self.clients.add(websocket)

        try:
            while True:
                await asyncio.sleep(1)
        except:
            self.clients.remove(websocket)
            await self.check_clients()

    async def send_data(self, frequency, note):
        """ WebSocket으로 주파수 및 음계 전송 """
        data = {"frequency": frequency, "note": note}
        disconnected_clients = []

        for client in self.clients:
            try:
                await client.send_json(data)
            except Exception:
                disconnected_clients.append(client)

        for client in disconnected_clients:
            self.clients.remove(client)

        await self.check_clients()

    def get_stable_frequency(self, freq):
        """ 주파수를 안정적으로 필터링 """
        if freq < self.MIN_FREQ:
            return None

        self.last_freqs.append(freq)
        if len(self.last_freqs) > self.ROLLING_AVG_WINDOW:
            self.last_freqs.pop(0)

        return np.mean(self.last_freqs)

    def run(self):
        """ 주파수 분석 실행 및 WebSocket 전송 """
        if self.running:
            return

        self.running = True
        self.analyzer = AudioAnalyzer(self.queue, input_device_index=self.get_audio_interface_index())  # 🔹 새 analyzer 생성
        self.analyzer.start()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.running:
            if not self.clients:
                self.running = False
                break

            freq = self.queue.get()
            if freq:
                stable_freq = self.get_stable_frequency(freq)
                if stable_freq:
                    note = self.analyzer.frequency_to_note_name(stable_freq, self.A4_FREQ)
                    print(f"Detected Frequency: {stable_freq:.2f} Hz → Nearest Note: {note}")

                    loop.run_until_complete(self.send_data(stable_freq, note))

            time.sleep(0.02)

    async def check_clients(self):
        if not self.clients:
            self.stop()

    def stop(self): # 튜너 정지
        if not self.running:
            return

        self.running = False
        if self.analyzer:
            self.analyzer.running = False
            self.analyzer.join()
            self.analyzer = None  # 기존 analyzer 제거
        self.thread = None  # 스레드 초기화

    def restart(self):
        if not self.running and (self.thread is None or not self.thread.is_alive()):
            self.thread = Thread(target=self.run, daemon=True)
            self.thread.start()

tuner = Tuner()

@tuner_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """ WebSocket 엔드포인트 """
    await websocket.accept()
    tuner.clients.add(websocket)

    tuner.restart()  # WebSocket 연결 시 튜너 재시작

    try:
        while True:
            await asyncio.sleep(1)
    except:
        tuner.clients.remove(websocket)
        await tuner.check_clients()

@tuner_router.on_event("startup")
def start_tuner():
    pass

@tuner_router.on_event("shutdown")
def stop_tuner():
    tuner.stop()