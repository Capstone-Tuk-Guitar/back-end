from fastapi import FastAPI, UploadFile, File, Form, APIRouter,Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil
from function.db import get_db_connection
from function.db import initialize_db
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

db_run_router = APIRouter()

initialize_db()

# 서버 정보
SERVER_IP = os.getenv('SERVER_IP')
SERVER_PORT = os.getenv('SERVER_PORT', '8000')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "..", "uploads", "music")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# 사용자 등록
@db_run_router.post("/create-user/")
def create_user(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    print(f"✅ 사용자 등록 요청 수신: username={username}, email={email}")

    try:
        db = get_db_connection()
        cursor = db.cursor()
        sql = "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)"
        cursor.execute(sql, (username, email, password))
        db.commit()
        user_id = cursor.lastrowid
        print(f"✅ DB에 사용자 등록 완료: user_id={user_id}")
        cursor.close()
        db.close()
        return {
            "message": "사용자 등록 완료",
            "user_id": user_id
        }

    except Exception as e:
        print(f"❌ 사용자 등록 중 오류 발생: {e}")
        return JSONResponse(status_code=500, content={"message": "서버 에러", "detail": str(e)})

@db_run_router.post("/login/")
def login(username: str = Form(...), password: str = Form(...)):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
    user = cursor.fetchone()

    cursor.close()
    db.close()

    if user:
        return {"message": "로그인 성공", "user_id": user["user_id"]}
    else:
        return JSONResponse(status_code=401, content={"message": "로그인 실패: 잘못된 username 또는 비밀번호"})

# 음원 목록 조회
@db_run_router.get("/music/{user_id}")
def get_user_music(user_id: int):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT music_id, title, composer, file_path, upload_date FROM Music WHERE user_id = %s", (user_id,))
    result = cursor.fetchall()
    cursor.close()
    db.close()

    # 상대 경로 기반 URL 생성
    for row in result:
        row['file_url'] = f"http://localhost:{SERVER_PORT}/{row['file_path']}"

    return result

@db_run_router.post("/upload-music/")
async def upload_music(
    user_id: int = Form(...),
    title: str = Form(...),
    composer: str = Form(None),
    file: UploadFile = File(...)
):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        db.close()
        return {"error": "존재하지 않는 사용자입니다. 먼저 사용자 등록 필요."}

    # 상대 경로 (DB용)
    relative_path = f"uploads/music/{file.filename}"
    # 절대 경로 (저장용)
    absolute_path = os.path.join(BASE_DIR, "..", relative_path)

    with open(absolute_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    sql = "INSERT INTO Music (user_id, title, composer, file_path, upload_date) VALUES (%s, %s, %s, %s, %s)"
    cursor.execute(sql, (user_id, title, composer, relative_path, datetime.now()))
    db.commit()
    cursor.close()
    db.close()

    return {
        "message": "음원 업로드 완료",
        "file_path": relative_path,
        "title": title,
        "filename": os.path.basename(relative_path),
        "music_id": cursor.lastrowid
    }

@db_run_router.get("/stream-music/{music_id}")
def stream_music(music_id: int):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT file_path FROM Music WHERE music_id = %s", (music_id,))
    result = cursor.fetchone()
    cursor.close()
    db.close()

    if result:
        file_path = os.path.join(BASE_DIR, "..", result[0])
        if os.path.exists(file_path):
            return FileResponse(
                path=file_path,
                media_type="audio/mpeg",
                filename=os.path.basename(file_path)
            )
        else:
            return JSONResponse(status_code=404, content={"message": "파일이 존재하지 않습니다"})
    else:
        return JSONResponse(status_code=404, content={"message": "music_id에 해당하는 음원을 찾을 수 없습니다"})

@db_run_router.delete("/delete-music/")
def delete_music(music_id: int = Query(...)):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # 🔍 SELECT 하고 나면 반드시 fetchone() 해야 다음 쿼리에서 에러 안 남
        cursor.execute("SELECT file_path FROM Music WHERE music_id = %s", (music_id,))
        result = cursor.fetchone()

        if result:
            file_path = result[0]
            if os.path.exists(file_path):
                os.remove(file_path)
            cursor.execute("DELETE FROM Music WHERE music_id = %s", (music_id,))
            db.commit()
            return {"message": "삭제 완료"}
        else:
            return {"error": "해당 곡이 존재하지 않습니다"}

    except Exception as e:
        print("❌ 삭제 실패:", e)
        return {"error": str(e)}

    finally:
        cursor.close()
        db.close()

@db_run_router.get("/get-records/{user_id}")
def get_user_records(user_id: int):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        # ✅ user_id 기준으로 record 조회 (Music 테이블 조인)
        cursor.execute("""
            SELECT 
                r.record_id, 
                m.title AS music_title,
                r.record_file,
                r.accuracy,
                r.record_date
            FROM record r
            JOIN Music m ON r.music_id = m.music_id
            WHERE m.user_id = %s
            ORDER BY r.record_date DESC
        """, (user_id,))

        records = cursor.fetchall()
        return records

    except Exception as e:
        print(f"❌ record 조회 실패: {e}")
        return {"error": str(e)}

    finally:
        cursor.close()
        db.close()
