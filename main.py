from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from function.convert import convert_router
from function.compare import compare_router
from function.tuner import tuner_router
from function.tuner import Tuner

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(convert_router)
app.include_router(compare_router)
app.include_router(tuner_router)

