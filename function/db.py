import mysql.connector
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

def get_db_connection():
    connection = mysql.connector.connect(
        host=os.getenv('SERVER_IP'),  # IPv4
        user='guitar_db',        # MySQL 계정
        password='dlffprrlxk',# 비밀번호
        database='guitar_db',    # DB 이름
        port=3306                # 포트
    )
    return connection