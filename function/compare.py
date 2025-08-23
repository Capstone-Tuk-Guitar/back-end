from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import os
import uuid
import numpy as np
import pretty_midi as pm
from fastdtw import fastdtw
from scipy.spatial.distance import cosine
from function.db import get_db_connection

compare_router = APIRouter()

def _safe_chroma(m: pm.PrettyMIDI, fs: int = 50):
    """(T,12) 크로마 시퀀스. 프레임 L2 정규화 """
    chroma = m.get_chroma(fs=fs).T  # (T,12)
    if chroma.size == 0:
        return chroma

    # 프레임 정규화
    norms = np.linalg.norm(chroma, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    chroma = chroma / norms

    beats = m.get_beats()  # seconds array
    if beats is None or len(beats) < 2:
        return chroma

    T = chroma.shape[0]
    times = np.arange(T) / fs
    beat_edges = list(beats) + [m.get_end_time()]

    pooled = []
    for i in range(len(beat_edges) - 1):
        t0, t1 = beat_edges[i], beat_edges[i + 1]
        mask = (times >= t0) & (times < t1)
        if not np.any(mask):
            continue
        pooled.append(chroma[mask].mean(axis=0))

    if not pooled:
        return chroma

    pooled = np.vstack(pooled)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return pooled / norms


def _pitchclass_histogram(m: pm.PrettyMIDI):

    hist = np.zeros(12, dtype=float)
    for inst in m.instruments:
        if getattr(inst, "is_drum", False):
            continue
        for note in inst.notes:
            dur = max(note.end - note.start, 0.0)
            pc = note.pitch % 12
            hist[pc] += dur
    if hist.sum() == 0:
        return np.ones(12) / 12.0
    return hist / hist.sum()


def _dtw_chroma_similarity(A: np.ndarray, B: np.ndarray) -> float:
    """
    크로마 시퀀스 DTW 유사도(0~1)
    """
    if A.size == 0 or B.size == 0:
        return 0.0

    def _cos(a, b):
        d = cosine(a, b)
        if np.isnan(d):
            d = 1.0
        return float(np.clip(d, 0.0, 1.0))

    distance, path = fastdtw(A, B, dist=_cos)
    avg_dist = distance / max(1, len(path))
    sim = 1.0 - float(np.clip(avg_dist, 0.0, 1.0))
    return float(np.clip(sim, 0.0, 1.0))

def _hist_similarity(h1: np.ndarray, h2: np.ndarray) -> float:
    """
    코사인 유사도(0~1)
    """
    n1 = np.linalg.norm(h1)
    n2 = np.linalg.norm(h2)
    if n1 == 0 or n2 == 0:
        return 0.0
    sim = float(np.dot(h1, h2) / (n1 * n2))
    return float(np.clip(sim, 0.0, 1.0))

def compare_midi_files(midi1_path, midi2_path):

    m1 = pm.PrettyMIDI(midi1_path)
    m2 = pm.PrettyMIDI(midi2_path)

    A = _safe_chroma(m1, fs=50)
    B = _safe_chroma(m2, fs=50)
    dtw_sim = _dtw_chroma_similarity(A, B)

    h1 = _pitchclass_histogram(m1)
    h2 = _pitchclass_histogram(m2)
    hist_sim = _hist_similarity(h1, h2)

    final = 0.7 * dtw_sim + 0.3 * hist_sim

    return {
        "pitch_similarity": round(dtw_sim, 3),
        "rhythm_similarity": round(hist_sim, 3),
        "final_similarity": round(final, 3),
    }

@compare_router.post("/compare/")
async def compare_midi_files(
    user_id: int = Form(...),
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    def _is_midi(name: str) -> bool:
        n = (name or "").lower()
        return n.endswith(".mid") or n.endswith(".midi")

    if not _is_midi(file1.filename) or not _is_midi(file2.filename):
        raise HTTPException(status_code=400, detail="Both files must be .mid/.midi")

    # UUID로 임시 파일 저장
    file1_path = f"temp_{uuid.uuid4()}_{file1.filename}"
    file2_path = f"temp_{uuid.uuid4()}_{file2.filename}"

    with open(file1_path, "wb") as f:
        f.write(await file1.read())
    with open(file2_path, "wb") as f:
        f.write(await file2.read())

    # 유사도 계산
    similarity_result = compare_midi_files(file1_path, file2_path)

    db = get_db_connection()
    cursor = db.cursor()

    try:
        file1.filename = os.path.splitext(file1.filename)[0]
        filename_only = os.path.basename(file1.filename)
        cursor.execute(
            "SELECT music_id FROM Music WHERE user_id = %s AND file_path LIKE %s",
            (user_id, f"%{filename_only}%")
        )
        music_list = cursor.fetchall()

        if not music_list:
            print(f"❌ user_id={user_id} / file={filename_only} 에 대한 music_id를 찾지 못함")
        else:
            for music in music_list:
                music_id = music[0]
                cursor.execute("""
                    INSERT INTO record (music_id, record_file, accuracy, record_date)
                    VALUES (%s, %s, %s, NOW())
                """, (music_id, file2.filename, similarity_result["final_similarity"]))
                print(f"✅ record 저장 완료: music_id={music_id}, record_file={file2.filename}, accuracy={similarity_result['final_similarity']}")
            db.commit()

    except Exception as e:
        print(f"❌ record 테이블 저장 실패: {e}")

    finally:
        cursor.close()
        db.close()

        # 임시 파일 삭제
        for p in (file1_path, file2_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except:
                pass

    return similarity_result
