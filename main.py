from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from function.convert import convert_router
from function.compare import compare_router
from function.tuner import tuner_router
from function.mxlConverter import mxl_router
from function.db_run import db_run_router
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")



app.include_router(convert_router)
app.include_router(compare_router)
app.include_router(tuner_router)
app.include_router(mxl_router)
app.include_router(db_run_router)