import time
import numpy as np
import pyaudio
import asyncio
import websockets
from threading import Thread
import uvicorn
from fastapi import FastAPI, WebSocket, APIRouter
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
        self.analyzer = AudioAnalyzer(self.queue, input_device_index=self.get_audio_interface_index())
        self.running = False
        self.last_freqs = []
        self.clients = set()

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

    async def send_data(self, freq, note):
        """ 주파수와 음계 데이터를 WebSocket으로 전송 """
        data = {"frequency": freq, "note": note}
        # 기존의 asyncio.run()을 사용하지 않고, 현재 실행 중인 루프에서 실행되도록 변경
        await asyncio.gather(*(client.send_json(data) for client in self.clients))

    def get_stable_frequency(self, freq):
        """ 주파수를 안정적으로 필터링 """
        if freq < self.MIN_FREQ:
            return None  # 잡음 제거

        self.last_freqs.append(freq)
        if len(self.last_freqs) > self.ROLLING_AVG_WINDOW:
            self.last_freqs.pop(0)

        return np.mean(self.last_freqs)

    def run(self):
        """ 주파수 분석 실행 및 WebSocket 전송 """
        self.running = True
        self.analyzer.start()

        # 🔹 새로운 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.running:
            freq = self.queue.get()
            if freq:
                stable_freq = self.get_stable_frequency(freq)
                if stable_freq:
                    note = self.analyzer.frequency_to_note_name(stable_freq, self.A4_FREQ)
                    print(f"Detected Frequency: {stable_freq:.2f} Hz → Nearest Note: {note}")

                    # 🔹 새로운 이벤트 루프에서 실행
                    loop.run_until_complete(self.send_data(stable_freq, note))

            time.sleep(0.02)

    def stop(self):
        """ 튜너 중지 """
        self.running = False
        self.analyzer.running = False
        self.analyzer.join()

tuner = Tuner()

@tuner_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """ WebSocket 엔드포인트 """
    await websocket.accept()
    tuner.clients.add(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except:
        tuner.clients.remove(websocket)

@tuner_router.on_event("startup")
def start_tuner():
    """ FastAPI 서버가 시작될 때 Tuner 실행 """
    Thread(target=tuner.run, daemon=True).start()

@tuner_router.on_event("shutdown")
def stop_tuner():
    """ FastAPI 서버가 종료될 때 Tuner 정리 """
    tuner.stop()