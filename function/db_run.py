from fastapi import FastAPI, UploadFile, File, Form, APIRouter,Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil
from function.db import get_db_connection
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

db_run_router = APIRouter()

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
        return JSONResponse(status_code=401, content={"message": "로그인 실패: 잘못된 ID 또는 비밀번호"})

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
        "file_path": relative_path
    }
# 음원 목록 조회

@db_run_router.get("/music/{user_id}")
def get_user_music(user_id: int):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT title, composer, file_path, upload_date FROM Music WHERE user_id = %s", (user_id,))
    result = cursor.fetchall()
    cursor.close()
    db.close()

    # 상대 경로 기반 URL 생성
    for row in result:
        row['file_url'] = f"http://localhost:{SERVER_PORT}/{row['file_path']}"

    return result

@db_run_router.delete("/delete-music/")
def delete_music(user_id: int = Query(...), title: str = Query(...)):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        # 🔍 SELECT 하고 나면 반드시 fetchone() 해야 다음 쿼리에서 에러 안 남
        cursor.execute("SELECT file_path FROM Music WHERE user_id = %s AND title = %s", (user_id, title))
        result = cursor.fetchone()

        if result:
            file_path = result[0]

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print("파일 삭제 중 오류:", e)

            # ✅ 여기서 반드시 이전 SELECT 결과를 fetch한 후에 DELETE 쿼리 실행!
            cursor.execute("DELETE FROM Music WHERE user_id = %s AND title = %s", (user_id, title))
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
