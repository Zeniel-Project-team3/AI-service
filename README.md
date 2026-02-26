# AI 추천 서비스 (ai-service)

내담자 프로필 기반 유사 케이스 검색 + GPT 추천(직무/훈련/상담 질문 등)을 제공하는 API입니다.

- **Java 백엔드 팀**: 아래 **「Java 백엔드 팀용」**만 보면 됩니다. Docker 이미지 pull 후 `.env`만 맞추면 됩니다.
- **AI 팀**: **「AI 팀용 (개발·실험)」**에서 DB 구축, uvicorn 실행, Docker 빌드, API 상세까지 확인하세요.

## 목차

### [Java 백엔드 팀용 (Docker 이미지로 연동)](#java-백엔드-팀용-docker-이미지로-연동)
- [요구사항](#요구사항)
- [1. .env 준비](#1-env-준비)
- [2. 이미지 pull 및 실행](#2-이미지-pull-및-실행)
- [3. 동작 확인](#3-동작-확인)
- [4. Java에서 호출](#4-java에서-호출)
- [5. Java 연동 (Request/Response)](#5-java-연동-requestresponse)

### [AI 팀용 (개발·실험)](#ai-팀용-개발실험)
- [요구사항](#요구사항-1)
- [1. DB 준비](#1-db-준비)
- [2. DB 구축 방법 (둘 중 하나 선택)](#2-db-구축-방법-둘-중-하나-선택)
- [3. .env 설정](#3-env-설정)
- [4. 실행 방법](#4-실행-방법)
- [5. 임베딩·유사도 요약](#5-임베딩유사도-요약)
- [6. DB 구조 (스키마)](#6-db-구조-스키마)
- [7. /api/v1/recommend 동작 요약](#7-apiv1recommend-동작-요약)
- [8. /api/v1/re-embedding 동작 요약](#8-apiv1-re-embedding-동작-요약)
- [9. /api/v1/ingest-employment-training 동작요약](#9-apiv1ingest-employment-training-동작요약)


---

# Java 백엔드 팀용 (Docker 이미지로 연동)

**전제:** 데이터베이스는 본인 로컬에 이미 구축된 상태입니다. AI 서비스는 GitHub 사설 저장소의 Docker 이미지를 pull 받아 사용합니다.

## 요구사항

- **Docker**
- **`.env` 파일** — DB 접속 정보, OpenAI API 키 (이미지에 포함되지 않으므로 반드시 로컬에서 설정)

## 1. .env 준비

`ai-service/.env`를 만들고 다음을 채웁니다.

**필수**

- `OPENAI_API_KEY` — GPT·임베딩 호출용
- `DB_URL` 또는 `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` — **로컬에 띄운 PostgreSQL** 접속 정보

**DB 주소**

- **컨테이너에서 ai-service를 실행할 때**  
  DB가 호스트(같은 PC)에서 돌면, 컨테이너 안에서는 호스트를 **`host.docker.internal`**로 접속해야 합니다.  
  예: `DB_URL=host.docker.internal:5432/postgres`  
  **Linux**에서는 `host.docker.internal`이 기본이 아니므로, 아래 `docker run`에 **`--add-host=host.docker.internal:host-gateway`** 를 붙입니다.
- **호스트에서 직접 uvicorn으로 실행할 때**  
  DB 주소는 **`127.0.0.1`** 또는 **`localhost`** (예: `DB_URL=127.0.0.1:5432/postgres`).

예시 (로컬 pgvector 기준, 컨테이너에서 실행):

```env
OPENAI_API_KEY=sk-...
DB_URL=host.docker.internal:5432/postgres
DB_USERNAME=postgres
DB_PASSWORD=postgres
```

## 2. 이미지 pull 및 실행

**비공개 이미지인 경우** — 먼저 로그인 (GitHub 사용자명 + Personal Access Token, scope: `read:packages`):

```bash
docker login ghcr.io -u <GitHub사용자명> -p <PAT>
```

**pull 및 실행:**

```bash
cd ai-service   # .env가 있는 디렉터리
docker pull ghcr.io/zeniel-project-team3/ai-service:latest
# 또는 :gpt-model 등 사용 중인 태그

# Linux: --add-host 필요. Windows/Mac Docker Desktop은 생략 가능
docker run -d -p 8001:8001 --env-file .env --name ai-recommendation \
  --add-host=host.docker.internal:host-gateway \
  ghcr.io/zeniel-project-team3/ai-service:latest
```

레포가 public이면 패키지도 public일 때 로그인 없이 `docker pull` 가능합니다.

## 3. 동작 확인

```bash
curl -X POST "http://localhost:8001/api/v1/recommend" \
  -H "Content-Type: application/json" \
  -d '{"clientId": 1, "topK": 5}'
```

## 4. Java에서 호출

- **URL:** `POST http://<호스트>:8001/api/v1/recommend`
- **Request:** `{"clientId": number, "topK": number}` — `topK` 생략 시 5
- **Response:** `clientId`, `maskedInput`, `queryText`, `similarCases`, `recommendation` (추천 직무·훈련·서비스·질문 등)


---

## 5. Java 연동 (Request/Response)

**URL:** `POST http://<호스트>:8001/api/v1/recommend`

### Request

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| clientId | number | O | 내담자 ID (DB `clients.id`) |
| topK | number | X | 유사 케이스 개수 (기본 5, 1~20) |

예: `{"clientId": 1, "topK": 5}`

### Response

| 필드 | 타입 | 설명 |
|------|------|------|
| clientId | number | 요청한 내담자 ID |
| maskedInput | object | 마스킹된 내담자 정보 |
| queryText | string | 임베딩에 사용한 텍스트 |
| similarCases | array | 유사 케이스 목록 |
| recommendation | object | 추천 결과 |

`recommendation` 내부:

| 필드 | 타입 | 설명 |
|------|------|------|
| recommendedJobsByProfile | string[] | 나이·성별·학력·역량·전공만 고려한 추천 직무 3개 |
| recommendedJobsByDesiredJob | string[] | 희망직종 반영 추천 직무 3개 |
| recommendedTrainings | string[] | 추천 직업훈련 과정명 |
| recommendedCompanies | string[] | 추천 취업처 |
| expectedSalaryRange | string \| null | 예상 연봉 범위 |
| suggestedServices | string[] | 제안 서비스 |
| coreQuestions | string[] | 상담 핵심 질문 |
| reason | string \| null | 추천 근거 |

### Java 호출 예시

```java
AiRequestDto request = new AiRequestDto(123, 5);
AiResponseDto response = restClient.post()
    .uri("http://localhost:8001/api/v1/recommend")
    .body(request)
    .retrieve()
    .body(AiResponseDto.class);
```

| 환경 | `<호스트>` 예시 |
|------|------------------|
| Java와 같은 PC에서 Docker 실행 | localhost |
| Docker Compose 등 같은 네트워크 | 서비스 이름 또는 localhost |
| 다른 서버에 배포 | 해당 서버 IP 또는 도메인 |


---

# AI 팀용 (개발·실험)

개발 시 uvicorn으로 실행하고, 필요 시 Docker 이미지 빌드·푸시까지 진행할 때 참고하는 문서입니다. **현재 README의 거의 모든 내용을 포함합니다.**

## 요구사항

- **Docker** (DB·이미지 빌드용)
- **Python 3.11+** (uvicorn 개발 실행)
- **`.env`** (DB 접속 정보, OpenAI API 키)

---

## 1. DB 준비

AI 서비스는 **pgvector 확장**이 있는 PostgreSQL에 접속해야 합니다.

**PostgreSQL + pgvector 실행 (이미 띄웠으면 생략)**

```bash
docker run -d --name pgvector -p 5432:5432 \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -v pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg17

docker exec -it pgvector psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

또는 `ai-service` 디렉터리에서 한 번만 실행하면 된다. `db/init/01-enable-vector.sql` 덕분에 vector 확장이 자동으로 생성된다.

```bash
cd ai-service
docker compose up -d
```

확인:

```bash
docker compose ps
docker exec -it pgvector psql -U postgres -d postgres -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

**DB 접속 주소 (실행 환경별)**

- **호스트에서 실행 (uvicorn)**  
  DB가 같은 PC에서 돌면 `.env`의 DB 주소는 **`127.0.0.1`** 또는 **`localhost`**.  
  예: `DB_URL=127.0.0.1:5432/postgres`
- **도커 컨테이너에서 실행**  
  DB가 호스트에서 돌면 컨테이너 안에서는 **`host.docker.internal`**.  
  예: `DB_URL=host.docker.internal:5432/postgres`  
  **Linux**에서는 `docker run` 시 **`--add-host=host.docker.internal:host-gateway`** 를 붙인다.

---

## 2. DB 구축 방법 (둘 중 하나 선택)

공통 흐름: **데이터 적재 → ai-service 기동 → re-embedding**.

1. **데이터 적재** — 방법 1(CSV) 또는 방법 2(엑셀)로 테이블·데이터를 채운다.
2. **ai-service 기동** — uvicorn 또는 Docker.
3. **re-embedding** — `POST /api/v1/re-embedding` 으로 모든 내담자 임베딩을 계산해 DB에 넣는다. 이 단계를 거쳐야 추천 API가 유사 케이스를 검색할 수 있다.

### 방법 1: 이미 구성된 CSV로 구축

`Backend/database/` 의 CSV(`clients.csv`, `consultation.csv`, `training.csv`, `employments.csv`)로 테이블 생성·데이터 적재를 한 번에 한다.

**`database` 폴더 (필수):**

- 시드 스크립트는 **`DATABASE_DIR`**(또는 `CSV_DATABASE_DIR`)이 **필수**이다. **ai-service/.env** 에 CSV가 있는 폴더의 **절대 경로**를 넣어 두면 된다. 비우면 스크립트가 에러로 종료한다.
- 스크립트 실행 시 **ai-service/.env** 를 자동으로 읽는다.

```
Backend/
├── ai-service/
│   └── scripts/
│       └── seed_from_csv.py
└── database/           ← 예: .env에 DATABASE_DIR=/path/to/Backend/database
    ├── clients.csv
    ├── consultation.csv
    ├── employments.csv
    └── training.csv
```

스크립트는 **Backend 루트에서** `python3 ai-service/scripts/seed_from_csv.py` 로 실행한다.

1. **PostgreSQL + pgvector** 실행 (위 참고).
2. **ai-service `.env`** 에 DB 접속 정보 설정 (호스트 uvicorn 시 `DB_URL=127.0.0.1:5432/postgres` 등).
3. **시드 스크립트 실행** (Backend 루트에서):

   ```bash
   cd /path/to/Backend
   python3 ai-service/scripts/seed_from_csv.py
   ```

4. **ai-service 기동** 후 **re-embedding** 호출:

   ```bash
   # 터미널 1
   cd ai-service && uvicorn app.main:app --host 0.0.0.0 --port 8001

   # 터미널 2
   curl -X POST "http://localhost:8001/api/v1/re-embedding"
   ```

5. **추천 API 테스트:**

   ```bash
   curl -X POST "http://localhost:8001/api/v1/recommend" \
     -H "Content-Type: application/json" \
     -d '{"clientId": 1, "topK": 5}'
   ```

### 방법 2: 엑셀 원본 파일로 구축

`POST /api/v1/ingest-employment-training` 은 **clients 테이블을 만들거나 적재하지 않는다.** employment, training, consultation 테이블만 생성·적재하고, 엑셀의 "참여자 이름 + 주민등록번호"로 **이미 있는 clients**와 매칭한다.  
그래서 방법 2를 쓰려면 **clients는 미리 다른 방법으로 채워 두어야 한다.**

1. **PostgreSQL + pgvector** 실행.
2. **clients 테이블 + 내담자 데이터**를 먼저 넣기 (둘 중 하나):
   - **Java 시드 SQL:** Backend 레포의 `src/main/java/com/zeniel/utility/generate_embed_column.sql` 등을 psql로 실행해 clients 테이블과 시드 데이터를 넣는다.
   ```bash
   cd /home/kosa/Backend
   docker exec -i pgvector psql -U postgres -d postgres < src/main/java/com/zeniel/utility/generate_embed_column.sql
   ``` 
3. **`.env`** 에 엑셀 경로 설정:

   ```env
   INGEST_EXCEL_PATH=/절대경로/상담리스트_가공데이터_202602.xlsx
   ```

4. **ai-service 기동** 후 **ingest** 호출 (테이블 없으면 생성 후 데이터 적재):

   ```bash
   curl -X POST "http://localhost:8001/api/v1/ingest-employment-training"
   ```

5. **re-embedding** 호출:

   ```bash
   curl -X POST "http://localhost:8001/api/v1/re-embedding"
   ```

6. **추천 API 테스트:** 위와 동일하게 `POST /api/v1/recommend` 호출.

---

## 3. .env 설정

`ai-service/.env`를 준비한다. 없으면 `.env.example`을 복사한 뒤 값만 수정.

```bash
cp .env.example .env
```

**필수**

- `OPENAI_API_KEY` — GPT·임베딩 호출용
- `DB_URL` 또는 `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` — PostgreSQL 접속 정보

**선택**

- `INGEST_EXCEL_PATH` — 엑셀 ingest(`POST /api/v1/ingest-employment-training`) 사용 시 엑셀 파일 절대 경로. 비우면 ingest 호출 시 503.
- `RECOMMEND_MODE` — **기본값 `fast`** (5초 내 응답 목표). 정확도 우선이면 `accuracy`.

| RECOMMEND_MODE | 설명 |
|----------------|------|
| **fast** (기본) | 유사 케이스 3건만 GPT에 전달, 응답 속도 우선. |
| **accuracy**   | 유사 케이스 5건 전달, 추천 품질 우선. |

예시 (로컬 pgvector, 호스트에서 uvicorn 실행 시).

**Option A) DB_URL 한 줄로 (Java/Spring과 동일하게):**

```env
OPENAI_API_KEY=sk-...
DB_URL=127.0.0.1:5432/postgres
DB_USERNAME=postgres
DB_PASSWORD=postgres
```

**Option B) 호스트·포트·DB명 따로 (uvicorn 시 `DB_HOST=localhost`, Docker 시 `DB_HOST=host.docker.internal` 등):**

```env
OPENAI_API_KEY=sk-...
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=postgres
```

---

## 4. 실행 방법

### 4.1 개발용: uvicorn (로컬 실험)

```bash
cd ai-service
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

호출 예:

```bash
curl -s -X POST "http://localhost:8001/api/v1/recommend" \
  -H "Content-Type: application/json" \
  -d '{"clientId":1,"topK":5}' | jq .
```

### 4.2 Docker 이미지 빌드 및 실행

같은 디렉터리에서 빌드 후 실행:

```bash
cd ai-service
docker build -t ai-recommendation-service .
docker run -d -p 8001:8001 --env-file .env --name ai-recommendation ai-recommendation-service
```

Linux에서 DB가 호스트에 있으면:

```bash
docker run -d -p 8001:8001 --env-file .env --name ai-recommendation \
  --add-host=host.docker.internal:host-gateway \
  ai-recommendation-service
```

### 4.3 GitHub Container Registry (ghcr.io) 이미지

- **자동 푸시:** `main`(또는 설정된 브랜치)에 push 시 GitHub Actions가 이미지를 빌드해 `ghcr.io`에 푸시.
- **수동 실행:** 저장소 **Actions** → **Build and Push ai-service to GHCR** → **Run workflow**.
- **이미지 주소 예:** `ghcr.io/zeniel-project-team3/ai-service:latest` (또는 `:main`, `:gpt-model` 등)
- **pull 후 실행:** (비공개 시 `docker login ghcr.io` 후) `docker pull ...` → `docker run ... --env-file .env ...`

---

## 5. 임베딩·유사도 요약

- **임베딩:** 내담자 **나이, 성별, 희망직종**만 모아 한 문장으로 만든 뒤, OpenAI `text-embedding-3-small`로 벡터화. 희망직종 없으면 "(미정)".
- **유사도:** DB의 다른 내담자 임베딩과 **코사인 거리**로 비교해, 거리가 작은 순으로 Top-K.
- **추천:** 희망직종 있으면 유사 케이스 기반으로 직무·훈련·질문 추천. 희망직종 없으면 나이·성별·학력·역량·전공 + 유사 케이스로 희망직종 후보 3개까지 포함.
- **해시:** 요청 시 나이·성별·희망직종 텍스트의 해시를 비교해, 바뀌었을 때만 새로 임베딩 계산·저장.

---

## 6. DB 구조 (스키마)

**필요한 테이블**

| 테이블 | 필수 여부 | 비고 |
|--------|-----------|------|
| **clients** | **필수** | 내담자 마스터. embedding vector(1536), pgvector 확장 필요. |
| employment / employments | 선택 | 있으면 유사 케이스에 취업 정보 포함. |
| training | 선택 | 있으면 유사 케이스에 훈련 이력 포함. |
| consultation | 선택 | 있으면 유사 케이스에 상담 요약 포함. |

**테이블별 필요 필드 (AI 서비스가 읽거나 씀)**

| 테이블 | 유일 키 | 주요 필드 |
|--------|---------|-----------|
| **clients** | id | name, resident_id, age, gender, education, desired_job, competency, address, university, major, embedding |
| employment | id | client_id, job_title, company_name, salary |
| training | id | client_id, course_name |
| consultation | id | client_id, summary |

- **`embedding_source_hash`** (선택): 있으면 **나이·성별·희망직종**으로 만든 텍스트의 해시를 저장해, 다음 요청 시 같은 입력이면 OpenAI 임베딩 호출을 건너뜀. 없어도 동작(매번 임베딩 재계산).
  - **컬럼을 쓰고 싶다면** `clients` 테이블에 아래 SQL로 추가:

    ```sql
    ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS embedding_source_hash VARCHAR(64);
    ```

  - psql 예: `docker exec -i pgvector psql -U postgres -d postgres -c "ALTER TABLE clients ADD COLUMN IF NOT EXISTS embedding_source_hash VARCHAR(64);"`

---

## 7. /api/v1/recommend 동작 요약

한 번 호출 시:

- **프로필 조회:** clients에서 id, name, resident_id, age, gender, education, desired_job, competency, address, university, major → maskedInput·queryText 생성.
- **임베딩:** age, gender, desired_job만 합쳐 임베딩 텍스트 → OpenAI → embedding 저장·유사도 검색.
- **유사 케이스:** clients + employment + training + consultation join → similarCases 반환.
- **GPT + rule-based:** maskedInput + similarCases → recommendation 생성 (직무·훈련·서비스·질문 등).

---

## 8. /api/v1/re-embedding 동작 요약

**clients** 테이블의 **전체 내담자**에 대해, 나이·성별·희망직종으로 임베딩 텍스트를 만들고 OpenAI로 새 임베딩을 계산한 뒤 **clients.embedding**을 일괄 갱신하는 API.

- **호출:** `POST /api/v1/re-embedding` (body 없음)
- **동작:** 전체 프로필 조회 → 각 내담자마다 나이·성별·희망직종으로 임베딩 텍스트 생성 → OpenAI 임베딩 API 호출 → `clients.embedding` 갱신. (embedding_source_hash 유무와 관계없이 전원 재계산)
- **응답:** `{ "updatedCount": N }` (갱신된 내담자 수)
- **용도:** 임베딩에 쓰는 필드(나이·성별·희망직종) 정의가 바뀌었을 때, 또는 DB를 새로 채운 뒤 일괄 임베딩을 맞추고 싶을 때 사용.

---

## 9. /api/v1/ingest-employment-training 동작요약

엑셀 원본 파일 한 개를 읽어 **employment, training, consultation** 테이블에 적재하는 API.

- **전제:** `.env`에 `INGEST_EXCEL_PATH`로 엑셀 절대 경로 설정. **clients** 테이블은 이미 존재하며, 엑셀의 "참여자 이름 + 주민등록번호"로 매칭.
- **호출:** `POST /api/v1/ingest-employment-training` (body 없음)
- 테이블이 없으면 `CREATE TABLE IF NOT EXISTS` 후 INSERT.


