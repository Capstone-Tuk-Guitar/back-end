from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from function.convert import convert_router  # convert.py의 router 불러오기
from function.compare import compare_router  # compare.py의 router 불러오기

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