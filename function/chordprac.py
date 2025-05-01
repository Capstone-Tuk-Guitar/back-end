from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import numpy as np
import sounddevice as sd
from chord_audio.chord_detector import ChordDetector, SAMPLE_RATE, BUFFER_SIZE, WINDOW_TIME

chordprac_router = APIRouter()
detector = ChordDetector()

@chordprac_router.websocket("/ws/chordprac")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")

    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    def audio_callback(indata, frames, time_info, status):
        if stop_event.is_set():
            return

        try:
            audio = indata[:, 0]
            freqs, notes, chord = detector.process(audio)

            result = {
                "frequencies": np.round(freqs, 2).tolist() if isinstance(freqs, np.ndarray) else [],
                "notes": notes if notes else [],
                "chord": {
                    "root": chord[0] if chord else "",
                    "type": chord[1] if chord else "",
                    "certainty": chord[2] if chord else 0.0
                }
            }

            # websocket이 살아있을 때만 전송
            if not stop_event.is_set():
                future = asyncio.run_coroutine_threadsafe(websocket.send_json(result), loop)
                future.result()
        except Exception as e:
            print("Error in audio_callback:", e)
            stop_event.set()

    async def audio_stream_loop():
        try:
            with sd.InputStream(
                callback=audio_callback,
                channels=1,
                samplerate=SAMPLE_RATE,
                blocksize=BUFFER_SIZE,
            ):
                while not stop_event.is_set():
                    await asyncio.sleep(WINDOW_TIME)
        except Exception as e:
            print("Stream error:", e)
            stop_event.set()

    # ✅ audio stream은 백그라운드 Task로 실행
    audio_task = asyncio.create_task(audio_stream_loop())

    try:
        # ✅ 웹소켓이 닫힐 때까지 기다림
        while True:
            await websocket.receive_text()  # 아무 메시지 안 보내도 닫히면 예외 발생함
    except WebSocketDisconnect:
        print("WebSocket disconnected by client.")
    except Exception as e:
        print("Receive loop error:", e)
    finally:
        stop_event.set()
        await audio_task  # audio 루프 종료 대기
        print("Cleanup done.")