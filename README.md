# AI 추천 서비스 (ai-service)

내담자 프로필 기반 유사 케이스 검색 + GPT 추천(직무/훈련/상담 질문 등)을 제공하는 API입니다.  
**Java 팀은 Python 설치 없이 Docker만 있으면 실행·연동할 수 있습니다.**

---

## 임베딩·유사도 검색이란?

- **임베딩값**: 내담자 **나이, 성별, 희망직종**만 모아 한 문장으로 만든 뒤, OpenAI 임베딩 API(`text-embedding-3-small`)로 받은 **숫자 벡터**입니다. (희망직종이 없으면 "(미정)"으로 넣음)
- **유사도**: DB에 저장된 다른 내담자 임베딩과 **코사인 거리**로 비교해, 거리가 작은 순으로 Top-K를 뽑습니다.

**추천직무는 2가지로**

- **희망직종이 있을 때**: 유사 케이스(나이·성별·희망직종 기준)를 바탕으로, 그 희망직종을 반영한 직무·훈련·연봉·서비스·질문을 추천합니다.
- **희망직종이 없을 때**: 나이·성별·학력·역량·전공과 유사 케이스를 고려해 **희망직종 후보(추천 직무) 3개**까지 포함해 추천합니다. (직종이 고민될 때 직종까지 추천)

**DB에 이미 임베딩이 있는 경우**

- 요청 시 **나이·성별·희망직종**으로 만든 텍스트의 해시를 비교합니다.  
  해시가 이전과 다르면(값이 바뀌었거나 임베딩에 쓰는 필드가 변경된 경우) **새로 임베딩을 계산해 DB에 덮어씁니다.**  
  해시가 같으면 기존 임베딩을 그대로 씁니다.

---

## 요구사항

- **Docker** (이미지 빌드 및 컨테이너 실행)
- **.env 파일** (DB 접속 정보, OpenAI API 키)

---

## DB가 이미 구성된 경우 (요약)

**데이터베이스가 이미 띄워져 있고, `clients` 등 스키마·데이터가 준비되어 있다면** 아래만 하면 됩니다.

1. **`.env` 설정** — `DB_URL`(또는 DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD), `OPENAI_API_KEY` 반드시 설정.
2. **서비스 실행** — `docker build` 후 `docker run` (또는 로컬에서는 `uvicorn app.main:app --host 0.0.0.0 --port 8001`).
3. **호출** — `POST http://localhost:8001/api/v1/recommend` 에 `{"clientId": 1, "topK": 5}` 등으로 요청.

- `employment`, `training` 테이블이 없어도 **recommend**는 동작합니다. (유사 케이스에 취업·훈련 정보만 빠질 뿐.)
- **ingest**(`/api/v1/ingest-employment-training`)는 선택 사항입니다. 사용하려면 `.env`에 **`INGEST_EXCEL_PATH`** 로 엑셀 파일 경로를 넣어야 하며, 호출 시 해당 경로의 파일을 읽어 채웁니다.

---

## 1. DB 준비

AI 서비스는 **pgvector 확장**이 있는 PostgreSQL에 접속해야 합니다.

**팀원들은 프로젝트 루트 `readme.md`대로 각자 localhost에 pgvector를 띄워 두고 있습니다.**  
(동일 이미지 `pgvector/pgvector:pg17`, 포트 5432, 계정 postgres/postgres)  
→ 그 DB에 연결하면 되므로 **별도 DB 띄울 필요 없이** 아래 `.env`에 `127.0.0.1:5432/postgres` 등 접속 정보만 넣으면 됩니다.

DB를 아직 안 띄웠다면 루트 `readme.md` 1~2단계를 먼저 진행하세요.  
또는 이 디렉터리에서만 pgvector를 쓰고 싶다면:

```bash
cd ai-service
docker compose up -d
```

- 위 명령은 **DB 서버(컨테이너)만 띄우는 것**입니다. DB·테이블을 생성하는 단계는 아닙니다.

확인:

```bash
docker compose ps
docker exec -it pgvector psql -U postgres -d postgres -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

시드/스키마가 필요하면 (선택):

```bash
docker exec -i pgvector psql -U postgres -d postgres < /home/kosa/Backend/src/main/java/com/zeniel/utility/generate_embed_column.sql
```

- 위 SQL 파일은 **postgres DB + 테이블 1개(`clients`) + `clients` 시드 데이터**까지 넣는 과정입니다.  
- **`employment`, `training`, `consultation`** 테이블은 Java 시드 SQL에 없어서 **우리가 따로 만든다.** AI 서비스에서 엑셀 ingest(`POST /api/v1/ingest-employment-training`) 호출 시 세 테이블 모두 `CREATE TABLE IF NOT EXISTS`로 생성한 뒤, 엑셀 데이터를 채운다.

### DB 구조 (스키마)

AI 서비스가 사용하는 PostgreSQL 스키마 요약입니다. **pgvector** 확장 필요 (`CREATE EXTENSION vector;`).

**필요한 테이블 종류**

| 개수 | 테이블 | 필수 여부 | 비고 |
|------|--------|-----------|------|
| **1개** | **`clients`** | **필수** | 내담자 마스터. 없으면 recommend 자체가 안 됨. |
| 2개 | `employment`, `training` | 선택 | 없어도 recommend는 동작. 있으면 유사 케이스에 취업·훈련 정보 포함. |
| 3개 | `consultation` | 선택 | 없어도 recommend는 동작. 있으면 유사 케이스에 상담 내역 포함. |

**테이블별 설명**

| 테이블 | 설명 |
|--------|------|
| `clients` | 내담자 마스터. Java 쪽 SQL 덤프 또는 시드로 채움. 임베딩·유사도 검색의 기준. |
| `consultation` | 상담 내역. AI 서비스 엑셀 ingest 시 `CREATE TABLE IF NOT EXISTS`로 생성 후 채움. |
| `employment` | 취업 이력(취업처·직무·급여 등). 엑셀 ingest로 채움. **job_title**이 있는 행만 유사 케이스 검색에 사용. |
| `training` | 직업훈련 이력(과정명·기간 등). 엑셀 ingest로 채움. |

**팀 전달용: 테이블별 유일 키 · 필요 필드**

| 테이블 | 유일 키 | 필요한 필드 (AI 서비스가 읽거나 씀) |
|--------|---------|--------------------------------------|
| **clients** | `id` | **필수:** id, name, resident_id, age, gender, education, desired_job, competency, address, university, major, embedding. |
| **employment** | `id` | client_id, job_title, company_name, salary (유사 케이스: 클라이언트당 최신 1건, job_title 있는 행만 사용). |
| **training** | `id` | client_id, course_name (유사 케이스: 클라이언트당 distinct로 배열). |
| **consultation** | `id` | client_id, summary (유사 케이스: 클라이언트당 최신 1건). |

- `clients.embedding`은 vector(1536) 타입, pgvector 확장 필요.
- `embedding_source_hash`는 AI 서비스가 선택적으로 쓰는 컬럼(없어도 동작함). 팀 DB에 없으면 넣지 않아도 됨.

---

### 어떤 정보를 뽑아서 어디에 merge(사용)하는지

/api/v1/recommend 한 번 호출 시
- 프로필 조회: clients에서 id, name, resident_id, age, gender, education, desired_job, competency, address, university, major → maskedInput·queryText 생성
- 임베딩: 그중 age, gender, desired_job만 합쳐서 임베딩 텍스트 → OpenAI → embedding 저장·유사도 검색
- 유사 케이스: clients + employment(job_title 있는 사람만) + training + consultation를 join해서 similarCases로 반환 (address 제외)
- GPT: maskedInput의 age, gender, education, desiredJobs, competency, major + similarCases 각 건 → recommendation 생성
- rule-based: similarCases에서 trainings, jobTitle, desiredJob, companyName, salary 뽑아서 초안 생성 후 GPT가 보정


---

## 2. .env 설정

`ai-service/.env` 파일을 준비합니다. 없으면 `.env.example`을 복사한 뒤 값만 수정하세요.

```bash
cp .env.example .env
# .env를 열어 DB 접속 정보·OPENAI_API_KEY 등 수정
```

**필수:**

- `OPENAI_API_KEY` — GPT·임베딩 호출용
- `DB_URL` 또는 `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` — 위에서 준비한 PostgreSQL 접속 정보

**선택:**

- `INGEST_EXCEL_PATH` — 엑셀 ingest(`POST /api/v1/ingest-employment-training`) 사용 시 엑셀 파일 절대 경로. 비우면 ingest 호출 시 503.
- `RECOMMEND_MODE` — 추천 모드. **기본값 `fast`**(5초 내 응답 목표). 정확도 우선이면 `accuracy`.

**추천 모드 (RECOMMEND_MODE)**

| 값 | 설명 |
|----|------|
| **fast** (기본) | 5초 버전. 유사 케이스 3건만 GPT에 전달, 토큰·온도 제한으로 응답 속도 우선. |
| **accuracy** | 정확도 우선. 유사 케이스 5건 전달, 토큰·온도 완화로 추천 품질 우선. |

**예시 (로컬 pgvector 컨테이너 사용 시):**

```env
OPENAI_API_KEY=sk-...
DB_URL=127.0.0.1:5432/postgres
DB_USERNAME=postgres
DB_PASSWORD=postgres
```

---

## 3. AI 서비스 실행 (Docker, Python 불필요)

같은 디렉터리에서 이미지 빌드 후 실행합니다.

```bash
cd ai-service
docker build -t ai-recommendation-service .
docker run -d -p 8001:8001 --env-file .env --name ai-recommendation ai-recommendation-service
```

---

### GitHub Container Registry (ghcr.io) 이미지

이미지는 **GitHub Container Registry**에 올라가며, 팀원은 빌드 없이 바로 pull해서 쓸 수 있습니다.

**자동 푸시**

- `main` 브랜치에 `ai-service/` 변경이 push되면 GitHub Actions가 이미지를 빌드해 `ghcr.io`에 푸시합니다.
- 수동 실행: 저장소 **Actions** → **Build and Push ai-service to GHCR** → **Run workflow**.

**이미지 주소 (팀 레포 기준)**

- `ghcr.io/zeniel-project-team3/backend/ai-service:latest`  
  (또는 `ghcr.io/zeniel-project-team3/backend/ai-service:main`, `ghcr.io/zeniel-project-team3/backend/ai-service:<sha>`)

**로컬에서 pull 후 실행 (빌드 없이)**

```bash
# 비공개 이미지인 경우: 먼저 로그인 (GitHub 사용자명 + Personal Access Token, scope: read:packages)
docker login ghcr.io -u <GitHub사용자명> -p <PAT>
cd ~/Backend/ai-service
docker pull ghcr.io/zeniel-project-team3/backend/ai-service:gpt-model
# docker stop ai-recommendation && docker rm ai-recommendation
docker run -d -p 8005:8001 --env-file .env --name ai-recommendation ghcr.io/zeniel-project-team3/backend/ai-service:gpt-model
```

레포가 **public**이면 패키지도 public으로 두었을 때 로그인 없이 `docker pull` 가능합니다.

---

동작 확인 (같은 PC에서):

```bash
curl -X POST "http://localhost:8001/api/v1/recommend" \
  -H "Content-Type: application/json" \
  -d '{"clientId":1,"topK":5}'
```

---

## 4. Java에서 호출

**URL:** `POST http://<호스트>:8001/api/v1/recommend`  
**Python 쪽에서 받는 값:** `clientId`, `topK` 두 가지입니다.

### Request (Input JSON)

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `clientId` | number | O | 내담자 ID (DB `clients.id`) |
| `topK` | number | X | 유사 케이스 개수 (기본 5, 1~20) |

예시:

```json
{
  "clientId": 1,
  "topK": 5
}
```

`topK` 생략 시 5로 처리됩니다.

### Response (Output JSON)

| 필드 | 타입 | 설명 |
|------|------|------|
| `clientId` | number | 요청한 내담자 ID |
| `maskedInput` | object | 마스킹된 내담자 정보 (이름·주민번호 마스킹) |
| `queryText` | string | 임베딩에 사용한 텍스트 |
| `similarCases` | array | 유사 케이스 목록 (jobTitle이 있는 사람만 포함, 각 항목: clientId, score, age, gender, desiredJob, competency, education, major, university, jobTitle, companyName, salary, trainings, consultationSummary) |
| `recommendation` | object | 추천 결과 |

`recommendation` 내부:

| 필드 | 타입 | 설명 |
|------|------|------|
| `recommendedJobsByProfile` | string[] | 나이·성별·학력·역량·전공만 고려한 추천 직무 3개 (희망직종 미반영) |
| `recommendedJobsByDesiredJob` | string[] | 희망직종을 고려한 추천 직무 3개 |
| `recommendedTrainings` | string[] | 추천 직업훈련 과정명 등 |
| `recommendedCompanies` | string[] | 추천 취업처 |
| `expectedSalaryRange` | string \| null | 예상 연봉 범위 |
| `suggestedServices` | string[] | 제안 서비스 (직업심리검사, 일경험 등) |
| `coreQuestions` | string[] | 이번 상담 핵심 질문 |
| `reason` | string \| null | 추천 근거 |

예시:

```json
{
  "clientId": 1,
  "maskedInput": {
    "clientId": 1,
    "name": "정*현",
    "residentId": "900226-*******",
    "age": 35,
    "gender": "남",
    "education": "2/3년제 대졸",
    "desiredJob": "편집디자이너\n영상편집\n음악강사",
    "competency": "C",
    "address": "울산광역시 남구 ...",
    "university": "동아방송예술대학교",
    "major": "음향제작과"
  },
  "queryText": "[기본정보]\n나이: 35\n...",
  "similarCases": [
    {
      "clientId": 10,
      "score": 0.919484,
      "age": 32,
      "gender": "여",
      "desiredJob": "경리사무원\n일반사무원",
      "competency": "C",
      "education": "대졸",
      "major": "음학과",
      "university": "대경대학교",
      "jobTitle": "경리사무원",
      "companyName": null,
      "salary": null,
      "trainings": ["전산회계1급 자격증취득과정 B\n그린컴퓨터아카데미\n..."],
      "consultationSummary": "이관자 진행 확인 필요\n..."
    }
  ],
  "recommendation": {
    "recommendedJobsByProfile": ["사무직", "경리사무원", "일반사무원"],
    "recommendedJobsByDesiredJob": ["편집디자이너", "영상편집", "콘텐츠 기획"],
    "recommendedTrainings": ["전산회계1급 자격증취득과정 B\n그린컴퓨터아카데미\n..."],
    "recommendedCompanies": [],
    "expectedSalaryRange": "2,800만원~3,500만원 수준",
    "suggestedServices": ["직업심리검사", "일경험 프로그램", "국민취업지원제도 연계 상담"],
    "coreQuestions": ["희망 직종으로 취업하기 위해 ...", "..."],
    "reason": "유사 사례 기반 추천."
  }
}
```

### Java 호출 예시

같은 PC에서 Docker로 띄운 경우:

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
| Java와 같은 PC에서 Docker 실행 | `localhost` |
| Docker Compose 등 같은 네트워크 | 서비스 이름 또는 `localhost` |
| 다른 서버에 배포 | 해당 서버 IP 또는 도메인 |

---

## 6. (개발용) Python 로컬 실행

AI 담당이 코드 수정 후 로컬에서 바로 돌려볼 때만 사용합니다. **Java 팀은 이 단계 없이 Docker만 쓰면 됩니다.**

```bash
cd ai-service
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

호출
```
curl -s -X POST "http://localhost:8001/api/v1/recommend"   -H "Content-Type: application/json"   -d '{"clientId":1,"topK":5}' | jq .
```