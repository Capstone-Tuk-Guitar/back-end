import time
import numpy as np
import pyaudio
import asyncio
from threading import Thread
from tuner_audio.threading_helper import ProtectedList
from tuner_audio.audio_analyzer import AudioAnalyzer
from fastapi import APIRouter, WebSocket
from threading import Thread

class Tuner:
    A4_FREQ = 440
    MIN_FREQ = 50
    ROLLING_AVG_WINDOW = 3

    def __init__(self):
        self.queue = ProtectedList(buffer_size=8)
        self.analyzer = AudioAnalyzer(self.queue, input_device_index=self.get_audio_interface_index())
        self.running = False
        self.last_freqs = []
        self.clients = set()

    def get_audio_interface_index(self):
        audio = pyaudio.PyAudio()
        for i in range(audio.get_device_count()):
            dev_info = audio.get_device_info_by_index(i)
            if "US-2x2HR" in dev_info["name"]:
                return i
        return None

    async def register_client(self, websocket):
        await websocket.accept()
        self.clients.add(websocket)
        try:
            while True:
                await asyncio.sleep(1)
        except:
            self.clients.remove(websocket)

    async def send_data(self, freq, note):
        data = {"frequency": freq, "note": note}
        await asyncio.gather(*(client.send_json(data) for client in self.clients))

    def get_stable_frequency(self, freq):
        if freq < self.MIN_FREQ:
            return None

        self.last_freqs.append(freq)
        if len(self.last_freqs) > self.ROLLING_AVG_WINDOW:
            self.last_freqs.pop(0)

        return np.mean(self.last_freqs)

    def run(self):
        self.running = True
        self.analyzer.start()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.running:
            freq = self.queue.get()
            if freq:
                stable_freq = self.get_stable_frequency(freq)
                if stable_freq:
                    note = self.analyzer.frequency_to_note_name(stable_freq, self.A4_FREQ)
                    print(f"Detected Frequency: {stable_freq:.2f} Hz → Nearest Note: {note}")
                    loop.run_until_complete(self.send_data(stable_freq, note))

            time.sleep(0.02)

    def stop(self):
        self.running = False
        self.analyzer.running = False
        self.analyzer.join()

tuner_app = APIRouter()
tuner = Tuner()

@tuner_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    tuner.clients.add(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except:
        tuner.clients.remove(websocket)

@tuner_app.on_event("startup")
def start_tuner():
    Thread(target=tuner.run, daemon=True).start()

@tuner_app.on_event("shutdown")
def stop_tuner():
    tuner.stop()