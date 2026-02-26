import json
import re
from typing import Any

from openai import OpenAI

from app.config import settings
from app.privacy import normalize_desired_jobs


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
    )


def create_embedding(text: str) -> list[float]:
    response = _client().embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding


def build_rule_based_recommendation(similar_cases: list[dict[str, Any]]) -> dict[str, Any]:
    training_candidates: list[str] = []
    job_candidates: list[str] = []
    company_candidates: list[str] = []
    salaries: list[int] = []

    for case in similar_cases:
        training_candidates.extend(_normalize_training_courses(case.get("trainings", [])))
        if case.get("jobTitle"):
            job_candidates.extend(normalize_desired_jobs(case["jobTitle"]))
        if case.get("desiredJob"):
            job_candidates.extend(normalize_desired_jobs(case["desiredJob"]))
        if case.get("companyName"):
            company_candidates.append(case["companyName"])
        if isinstance(case.get("salary"), int):
            salaries.append(case["salary"])

    def dedup_keep_order(values: list[str], limit: int) -> list[str]:
        seen = set()
        out = []
        for v in values:
            if not v or v in seen:
                continue
            seen.add(v)
            out.append(v)
            if len(out) >= limit:
                break
        return out

    salary_range = None
    if salaries:
        salary_range = f"{min(salaries):,}원 ~ {max(salaries):,}원"

    jobs_dedup = dedup_keep_order(job_candidates, 5)
    # 프로필(유사 케이스)만 본 추천 = 유사 케이스의 실제 취업 직종(jobTitle)으로 채움
    by_profile = dedup_keep_order(job_candidates, 3)
    return {
        "recommendedJobsByProfile": by_profile,
        "recommendedJobsByDesiredJob": jobs_dedup,
        "recommendedTrainings": dedup_keep_order(training_candidates, 5),
        "recommendedCompanies": dedup_keep_order(company_candidates, 5),
        "expectedSalaryRange": salary_range,
        "suggestedServices": [
            "직업심리검사",
            "일경험 프로그램",
            "국민취업지원제도 연계 상담",
        ],
        "coreQuestions": [
            "희망 직종으로 취업하기 위해 가장 먼저 해결해야 할 장애물은 무엇인가요?",
            "최근 3개월 내 바로 실행 가능한 행동 1가지는 무엇인가요?",
            "훈련과정 수강 후 취업까지의 목표 시점을 어떻게 설정하시겠어요?",
        ],
        "reason": "유사 사례의 취업직종/훈련이력/급여 정보를 기반으로 우선순위 추천을 구성했습니다.",
    }


def _normalize_training_courses(raw_trainings: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        value = item.strip()
        if not value:
            return
        value = re.sub(r"^[\"'`]+|[\"'`]+$", "", value)
        value = re.sub(r"^[\-\u2022]+\s*", "", value)
        value = re.sub(r"\s{2,}", " ", value).strip()
        # 기관명 단독 라인은 제외 (과정명이 아님)
        if re.search(r"(학원|대학교|대학|아카데미|센터)$", value):
            if not re.search(r"(과정|취득|실무|훈련|자격)", value):
                return
        if not value:
            return
        if value in seen:
            return
        seen.add(value)
        normalized.append(value)

    def clean_line(line: str) -> str:
        line = line.strip()
        line = re.sub(r"^[\"'`]+|[\"'`]+$", "", line)
        line = re.sub(r"^[\-\u2022]+\s*", "", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        return line

    def extract_period(text: str) -> str | None:
        m = re.search(
            r"(\d{4}[./-]\d{1,2}[./-]\d{1,2}\s*~\s*\d{4}[./-]\d{1,2}[./-]\d{1,2})",
            text,
        )
        return m.group(1).replace(".", "-").replace("/", "-") if m else None

    def extract_institution(lines: list[str]) -> str | None:
        for raw_line in lines:
            line = clean_line(raw_line)
            if not line:
                continue
            if "훈련기관" in line and ":" in line:
                return clean_line(line.split(":", 1)[1])
            if re.search(r"(학원|아카데미|센터|대학교|대학|직업전문학교)$", line):
                return line
        return None

    def extract_course(lines: list[str], text: str) -> str | None:
        m = re.search(r"훈련과정\s*[:：]\s*(.+)", text)
        if m:
            return clean_line(m.group(1).split("\n")[0])
        for raw_line in lines:
            line = clean_line(raw_line)
            if not line:
                continue
            if re.search(r"\d{4}[./-]\d{1,2}[./-]\d{1,2}", line):
                continue
            if "훈련기관" in line or "훈련기간" in line:
                continue
            if re.search(r"(학원|아카데미|센터|대학교|대학|직업전문학교)$", line):
                continue
            if len(line) >= 4:
                return line
        return None

    for raw in raw_trainings:
        if not raw:
            continue
        text = str(raw).replace("\r", "\n")
        lines = text.split("\n")
        course = extract_course(lines, text)
        institution = extract_institution(lines)
        period = extract_period(text)

        if course:
            parts = [course]
            if institution:
                parts.append(institution)
            if period:
                parts.append(period)
            add("\n".join(parts))
        else:
            fallback = clean_line(lines[0]) if lines else ""
            add(fallback)

    return normalized


def build_llm_recommendation(
    masked_input: dict[str, Any],
    similar_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    if not similar_cases:
        return build_rule_based_recommendation(similar_cases)

    is_fast = (settings.recommend_mode or "fast").strip().lower() == "fast"
    if is_fast:
        max_cases = min(3, len(similar_cases))
        max_tokens = 380
        temperature = 0.2
        mode = "quick"
    else:
        max_cases = min(5, len(similar_cases))
        max_tokens = 550
        temperature = 0.3
        mode = "accuracy"
    base = build_rule_based_recommendation(similar_cases)
    compressed_cases = similar_cases[:max_cases]
    compressed_cases = [
        {
            "clientId": case.get("clientId"),
            "score": case.get("score"),
            "desiredJobs": normalize_desired_jobs(case.get("desiredJob")),
            "competency": case.get("competency"),
            "education": case.get("education"),
            "major": case.get("major"),
            "university": case.get("university"),
            "jobTitles": normalize_desired_jobs(case.get("jobTitle")),
            "companyName": case.get("companyName"),
            "salary": case.get("salary"),
            "trainings": case.get("trainings") or [],
            "consultationSummary": case.get("consultationSummary"),
        }
        for case in compressed_cases
    ]

    desired_jobs_list = normalize_desired_jobs(masked_input.get("desiredJob"))

    system_prompt = (
        "너는 고용 상담 AI다. 반드시 JSON만 반환한다. "
        "PII(이름/주민번호)는 절대 생성하거나 복원하지 않는다. "
        "추천 직무는 반드시 두 종류를 모두 채운다: "
        "(1) recommendedJobsByProfile: 나이·성별·학력·역량·전공만 보고(희망직종은 보지 않음) 적합한 직무 3개, 1위~3위. 꼭 3개. "
        "(2) recommendedJobsByDesiredJob: 내담자 희망직종을 반영한 직무 3개, 1위~3위. 꼭 3개. "
        "recommendedTrainings는 위 추천 직무와 연관된 과정명 3개. "
        "expectedSalaryRange, suggestedServices 3개, coreQuestions 3개, recommendedCompanies, reason 한 문장."
    )
    user_prompt = {
        "mode": mode,
        "input": {
            "age": masked_input.get("age"),
            "gender": masked_input.get("gender"),
            "education": masked_input.get("education"),
            "desiredJobs": desired_jobs_list,
            "competency": masked_input.get("competency"),
            "major": masked_input.get("major"),
        },
        "similarCases": compressed_cases,
        "baseRecommendation": base,
        "outputFormat": {
            "recommendedJobsByProfile": "배열 3개, 나이·성별·학력·역량·전공만 고려한 직무(희망직종 미반영)",
            "recommendedJobsByDesiredJob": "배열 3개, 희망직종 반영한 직무",
            "recommendedTrainings": "배열 3개, 추천 직무와 연관된 과정명",
            "recommendedCompanies": "배열",
            "expectedSalaryRange": "추천 직무 기준 연봉 범위 문자열",
            "suggestedServices": "배열 3개, 중요도순",
            "coreQuestions": "배열 3개, 중요도순",
            "reason": "GPT 판단 근거",
        },
    }

    try:
        response = _client().chat.completions.create(
            model=settings.chat_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or "{}"

        parsed = json.loads(content)
        fallback_by_profile = base.get("recommendedJobsByProfile") or []
        base.update({k: v for k, v in parsed.items() if v is not None})
        def take3(lst: list | None) -> list[str]:
            if not lst:
                return []
            return [str(x).strip() for x in lst if x][:3]
        base["recommendedJobsByProfile"] = take3(base.get("recommendedJobsByProfile"))
        base["recommendedJobsByDesiredJob"] = take3(base.get("recommendedJobsByDesiredJob"))
        # GPT가 recommendedJobsByProfile을 비워두면 rule-based(유사 케이스 jobTitle)로 채움
        if not base["recommendedJobsByProfile"]:
            base["recommendedJobsByProfile"] = take3(fallback_by_profile) or take3(base.get("recommendedJobsByDesiredJob"))
        base["recommendedTrainings"] = take3(base.get("recommendedTrainings"))
        base["suggestedServices"] = take3(base.get("suggestedServices"))
        base["coreQuestions"] = take3(base.get("coreQuestions"))
        return base
    except Exception:
        return build_rule_based_recommendation(similar_cases)
