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


def initialize_db():
    db = get_db_connection()
    cursor = db.cursor()

    # users 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL,
        email VARCHAR(255),
        password VARCHAR(255)
    )
    """)

    # music 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Music (
        music_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        title VARCHAR(255) NOT NULL,
        composer VARCHAR(255),
        file_path VARCHAR(500),
        upload_date DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)

    # record 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS record (
        record_id INT AUTO_INCREMENT PRIMARY KEY,
        music_id INT,
        record_file VARCHAR(255) NOT NULL,
        accuracy FLOAT,
        record_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (music_id) REFERENCES Music(music_id) ON DELETE CASCADE
    )
    """)



    db.commit()
    cursor.close()
    db.close()