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
    """(T,12) 크로마 시퀀스. 프레임 L2 정규화 + 비트 평균 풀링"""
    chroma = m.get_chroma(fs=fs).T  # (T,12)
    if chroma.size == 0:
        return chroma

    # 프레임 정규화
    norms = np.linalg.norm(chroma, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    chroma = chroma / norms

    # 비트 기준 평균 풀링
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


def _dtw_chroma_similarity(A: np.ndarray, B: np.ndarray) -> float:
    """크로마 시퀀스 DTW 유사도(0~1)"""
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

# 리듬 히스토그램 구성
def _seconds_to_beats(m: pm.PrettyMIDI, t: float) -> float:
    """초 → beat로 변환: MIDI tick을 이용 (템포 변화 반영)"""
    return m.time_to_tick(t) / m.resolution

def _quantize(value: float, centers: np.ndarray) -> int:
    """value를 가장 가까운 center index로 할당"""
    return int(np.argmin(np.abs(centers - value)))

def _duration_histogram(m: pm.PrettyMIDI) -> np.ndarray:
    """
    노트 duration을 beat 단위로 변환해 리듬 값 분포를 만듦.
    기본 bin(센터): 1/16, 삼연음(1/3), 1/8, 3/8(점8분), 1/4, 3/4(점4분), 1/2, 3/2(점2분), 1, 2, 3, 4 beats
    (필요시 아래 centers 수정 가능)
    """
    centers = np.array([0.25, 1/3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0], dtype=float)
    # 위 배열에 0.125(16분음표)나 0.375(점16분) 등을 추가/조정해도 됨

    hist = np.zeros(len(centers), dtype=float)

    for inst in m.instruments:
        if getattr(inst, "is_drum", False):
            continue
        for note in inst.notes:
            # beat 단위 duration
            dur_beats = (_seconds_to_beats(m, note.end) - _seconds_to_beats(m, note.start))
            if dur_beats <= 0:
                continue
            idx = _quantize(dur_beats, centers)
            # 카운트 기반(=리듬 '빈도' 중점). 길이 가중을 주고 싶으면 += dur_beats로 바꿔도 됨.
            hist[idx] += 1.0

    if hist.sum() == 0:
        return np.ones_like(hist) / len(hist)
    return hist / hist.sum()

def _ioi_histogram(m: pm.PrettyMIDI) -> np.ndarray:
    """
    IOI(인접 온셋 간 간격) 분포. 곡 전반의 '타격 밀도/간격' 특성 반영.
    bins는 대략적인 박 간격을 대표하도록 설정.
    """
    # 온셋 시간(beat) 수집
    onsets_beats = []
    for inst in m.instruments:
        if getattr(inst, "is_drum", False):
            continue
        onsets_beats += [_seconds_to_beats(m, n.start) for n in inst.notes]

    if len(onsets_beats) < 2:
        # 정보 부족 시 균등 분포 반환
        return np.ones(8) / 8.0

    onsets_beats = np.array(sorted(onsets_beats), dtype=float)
    ioi = np.diff(onsets_beats)
    ioi = ioi[ioi > 0]

    if ioi.size == 0:
        return np.ones(8) / 8.0

    # 대표 간격(센터): 촘촘→성긴
    centers = np.array([0.25, 1/3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0], dtype=float)
    hist = np.zeros(len(centers), dtype=float)
    for v in ioi:
        idx = _quantize(v, centers)
        hist[idx] += 1.0

    if hist.sum() == 0:
        return np.ones_like(hist) / len(hist)
    return hist / hist.sum()

def _rhythm_vector(m: pm.PrettyMIDI) -> np.ndarray:
    """
    리듬 특징 벡터: [duration_hist | ioi_hist]를 이어붙인 벡터
    """
    d = _duration_histogram(m)
    i = _ioi_histogram(m)
    vec = np.concatenate([d, i], axis=0)
    # L2 정규화(코사인 유사도 안정화)
    n = np.linalg.norm(vec)
    if n == 0:
        return vec
    return vec / n

def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """코사인 유사도(0~1)"""
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    sim = float(np.dot(v1, v2) / (n1 * n2))
    return float(np.clip(sim, 0.0, 1.0))

def compare_midi(midi1_path: str, midi2_path: str):
    m1 = pm.PrettyMIDI(midi1_path)
    m2 = pm.PrettyMIDI(midi2_path)

    # 1) 멜로디/화성 흐름: 크로마 DTW
    A = _safe_chroma(m1, fs=50)
    B = _safe_chroma(m2, fs=50)
    dtw_sim = _dtw_chroma_similarity(A, B)

    # 2) 리듬 특징: duration + IOI 히스토그램
    r1 = _rhythm_vector(m1)
    r2 = _rhythm_vector(m2)
    rhythm_sim = _cosine_similarity(r1, r2)

    # 최종: 멜로디(DTW) 0.7 + 리듬 0.3
    final = 0.7 * dtw_sim + 0.3 * rhythm_sim

    return {
        "pitch_similarity": round(dtw_sim, 3),     # 멜로디/화성 흐름(크로마-DTW)
        "rhythm_similarity": round(rhythm_sim, 3), # 리듬(길이+온셋 간격)
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
    similarity_result = compare_midi(file1_path, file2_path)

    # DB 저장 + 최신 5개 유지 정리
    db = get_db_connection()
    cursor = db.cursor()
    unique_music_ids = set()

    try:
        file1_stem = os.path.splitext(os.path.basename(file1.filename))[0]
        cursor.execute(
            "SELECT music_id FROM Music WHERE user_id = %s AND file_path LIKE %s",
            (user_id, f"%{file1_stem}%")
        )
        music_list = cursor.fetchall()

        if not music_list:
            print(f"❌ user_id={user_id} / file={file1_stem} 에 대한 music_id를 찾지 못함")
        else:
            for (music_id,) in music_list:
                cursor.execute(
                    """
                    INSERT INTO record (music_id, record_file, accuracy, record_date)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    (music_id, file2.filename, similarity_result["final_similarity"])
                )
                unique_music_ids.add(music_id)
                print(
                    f"✅ record 저장 완료: music_id={music_id}, record_file={file2.filename}, "
                    f"accuracy={similarity_result['final_similarity']}"
                )

            for music_id in unique_music_ids:
                cursor.execute(
                    """
                    DELETE r FROM record r
                    WHERE r.music_id = %s
                      AND r.record_id NOT IN (
                        SELECT record_id FROM (
                          SELECT record_id
                          FROM record
                          WHERE music_id = %s
                          ORDER BY record_date DESC, record_id DESC
                          LIMIT 5
                        ) AS keepers
                      )
                    """,
                    (music_id, music_id)
                )

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"❌ record 테이블 저장/정리 실패: {e}")
    finally:
        cursor.close()
        db.close()

    try:
        os.remove(file1_path)
        os.remove(file2_path)
    except Exception:
        pass

    return similarity_result
