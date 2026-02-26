#!/usr/bin/env python3
"""
database/ 폴더의 CSV로 PostgreSQL(pgvector) DB를 구축하는 스크립트.
Backend 레포 루트에서 실행: python ai-service/scripts/seed_from_csv.py
또는 ai-service에서: python scripts/seed_from_csv.py

스크립트 실행 시 ai-service/.env 를 자동으로 읽는다. (Backend 루트에서 실행해도 ai-service/.env 적용)
필수: .env에 DB_URL(또는 DB_HOST/...) 설정.
필수: .env에 DATABASE_DIR(또는 CSV_DATABASE_DIR)에 CSV 폴더 경로 설정. 비우면 에러로 종료.
CSV 스키마:
  - clients.csv: 8번째 컬럼(헤더 "embedding") → DB의 education 컬럼
  - consultation.csv: summary
  - employments.csv: job_title, company_name, salary
  - training.csv: course_name
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

# ai-service/app 사용을 위해 경로 추가
_SCRIPT_DIR = Path(__file__).resolve().parent
_AI_SERVICE_ROOT = _SCRIPT_DIR.parent
_BACKEND_ROOT = _AI_SERVICE_ROOT.parent
if str(_AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_SERVICE_ROOT))

# ai-service/.env 로드 (Backend 루트에서 실행해도 DB_*, DATABASE_DIR 등 적용)
from dotenv import load_dotenv
_env_file = _AI_SERVICE_ROOT / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

# CSV가 있는 폴더. .env의 DATABASE_DIR(또는 CSV_DATABASE_DIR) 필수. 비우면 에러.
_env_db_dir = os.environ.get("DATABASE_DIR") or os.environ.get("CSV_DATABASE_DIR")
if not _env_db_dir or not _env_db_dir.strip():
    print("ERROR: DATABASE_DIR (or CSV_DATABASE_DIR) is required. Set it in ai-service/.env to the path of the folder containing clients.csv, etc.")
    sys.exit(1)
DATABASE_DIR = Path(_env_db_dir.strip()).resolve()


def _get_conn():
    from app.db import get_conn
    return get_conn()


def run_sql(conn, sql: str, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())


def enable_pgvector(conn):
    run_sql(conn, "CREATE EXTENSION IF NOT EXISTS vector;")


def create_tables(conn):
    # clients: CSV 8번째 컬럼을 education으로 저장. embedding은 vector(1536).
    run_sql(
        conn,
        """
        CREATE TABLE IF NOT EXISTS clients (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(255),
            birth_date VARCHAR(50),
            resident_id VARCHAR(20),
            phone VARCHAR(50),
            age INTEGER,
            gender VARCHAR(20),
            education VARCHAR(255),
            business_type VARCHAR(100),
            join_type VARCHAR(100),
            join_stage VARCHAR(100),
            competency VARCHAR(500),
            desired_job TEXT,
            address TEXT,
            university VARCHAR(255),
            major VARCHAR(255),
            embedding vector(1536),
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            embedding_source_hash VARCHAR(64)
        );
        """
    )
    run_sql(
        conn,
        """
        CREATE TABLE IF NOT EXISTS consultation (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            summary TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    run_sql(
        conn,
        """
        CREATE TABLE IF NOT EXISTS training (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            course_name TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    run_sql(
        conn,
        """
        CREATE TABLE IF NOT EXISTS employments (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            job_title VARCHAR(255),
            company_name VARCHAR(255),
            salary INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    conn.commit()


def load_clients(conn, path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        # CSV 헤더에 embedding 두 번 있음 → 8번째(인덱스 7)를 education으로 사용
        with conn.cursor() as cur:
            for row in reader:
                if len(row) < 17:
                    continue
                try:
                    age = int(row[5]) if row[5].strip() else None
                except ValueError:
                    age = None
                cur.execute(
                    """
                    INSERT INTO clients (
                        id, name, birth_date, resident_id, phone, age, gender,
                        education, business_type, join_type, join_stage,
                        competency, desired_job, address, university, major,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        birth_date = EXCLUDED.birth_date,
                        resident_id = EXCLUDED.resident_id,
                        phone = EXCLUDED.phone,
                        age = EXCLUDED.age,
                        gender = EXCLUDED.gender,
                        education = EXCLUDED.education,
                        business_type = EXCLUDED.business_type,
                        join_type = EXCLUDED.join_type,
                        join_stage = EXCLUDED.join_stage,
                        competency = EXCLUDED.competency,
                        desired_job = EXCLUDED.desired_job,
                        address = EXCLUDED.address,
                        university = EXCLUDED.university,
                        major = EXCLUDED.major,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        int(row[0]) if row[0].strip() else None,
                        row[1].strip() or None,
                        row[2].strip() or None,
                        row[3].strip() or None,
                        row[4].strip() or None,
                        age,
                        row[6].strip() or None,
                        row[7].strip() or None,  # education (CSV에는 embedding으로 표기)
                        row[8].strip() or None,
                        row[9].strip() or None,
                        row[10].strip() or None,
                        row[11].strip() or None,
                        row[12].strip().replace("\n", " ").strip() or None,
                        row[13].strip() or None,
                        row[14].strip() or None,
                        row[15].strip() or None,
                        (row[17].strip() or None) if len(row) > 17 else None,
                        (row[18].strip() or None) if len(row) > 18 else None,
                    ),
                )
    conn.commit()
    print(f"  clients: loaded from {path.name}")


def load_consultation(conn, path: Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # header
        with conn.cursor() as cur:
            for row in reader:
                if len(row) < 3:
                    continue
                summary = (row[2].strip() or None) if row[2].strip() else None
                cur.execute(
                    "INSERT INTO consultation (id, client_id, summary) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (int(row[0]), int(row[1]), summary),
                )
    conn.commit()
    print(f"  consultation: loaded from {path.name}")


def load_training(conn, path: Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # header
        with conn.cursor() as cur:
            for row in reader:
                if len(row) < 3:
                    continue
                cur.execute(
                    "INSERT INTO training (id, client_id, course_name) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (int(row[0]), int(row[1]), (row[2].strip() or None) if row[2].strip() else None),
                )
    conn.commit()
    print(f"  training: loaded from {path.name}")


def load_employments(conn, path: Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # header
        with conn.cursor() as cur:
            for row in reader:
                if len(row) < 5:
                    continue
                try:
                    salary = int(row[4]) if row[4].strip() else None
                except (ValueError, TypeError):
                    salary = None
                cur.execute(
                    """INSERT INTO employments (id, client_id, job_title, company_name, salary)
                       VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                    (
                        int(row[0]),
                        int(row[1]),
                        (row[2].strip() or None) if len(row) > 2 and row[2].strip() else None,
                        (row[3].strip() or None) if len(row) > 3 and row[3].strip() else None,
                        salary,
                    ),
                )
    conn.commit()
    print(f"  employments: loaded from {path.name}")


def reset_sequences(conn):
    for table in ("clients", "consultation", "training", "employments"):
        run_sql(
            conn,
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1));",
        )
    conn.commit()
    print("  sequences updated for id columns.")


def main():
    if not DATABASE_DIR.exists():
        print(f"ERROR: database dir not found: {DATABASE_DIR}")
        sys.exit(1)
    with _get_conn() as conn:
        print("1. Enabling pgvector...")
        enable_pgvector(conn)
        print("2. Creating tables...")
        create_tables(conn)
        print("3. Loading CSV data...")
        load_clients(conn, DATABASE_DIR / "clients.csv")
        load_consultation(conn, DATABASE_DIR / "consultation.csv")
        load_training(conn, DATABASE_DIR / "training.csv")
        load_employments(conn, DATABASE_DIR / "employments.csv")
        reset_sequences(conn)
    print("Done. Next: start ai-service and call POST /api/v1/re-embedding to fill client embeddings.")


if __name__ == "__main__":
    main()
