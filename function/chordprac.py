from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from chord_audio.chord_detector import AudioAnalyzer

chordprac_router = APIRouter()

@chordprac_router.websocket("/ws/chordprac")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🎸 WebSocket connection accepted")

    analyzer = AudioAnalyzer(websocket)
    analyze_task = None

    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "start":
                # 이미 실행 중이면 다시 시작하지 않음
                if analyze_task is None or analyze_task.done():
                    analyze_task = asyncio.create_task(asyncio.to_thread(analyzer.start))
                else:
                    print("음 감지 이미 켜짐...")

            elif msg == "stop":
                if analyze_task and not analyze_task.done():
                    analyzer.stop()  # 내부 플래그로 stop 신호 전달
                    try:
                        await analyze_task  # 작업 완료까지 대기
                    except asyncio.CancelledError:
                        print("asyncio 취소 에러...")
                    analyze_task = None
                else:
                    print("음 감지 이미 멈춤")

    except WebSocketDisconnect:
        print("웹소켓 연결 끊김...")
        if analyze_task and not analyze_task.done():
            analyzer.stop()
            try:
                await analyze_task
            except asyncio.CancelledError:
                print("asyncio 취소 에러...")
        print("음감지 정지...")
