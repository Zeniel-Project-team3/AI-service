from fastapi import FastAPI, HTTPException

from app.ai import build_llm_recommendation, create_embedding
from app.config import settings
from app.db import (
    compute_embedding_source_hash,
    get_all_client_profiles,
    get_client_embedding_vector,
    get_client_embedding_source_hash,
    get_client_profile,
    ingest_employment_training_from_excel,
    set_client_embedding_source_hash,
    search_similar_cases,
    update_client_embedding,
)
from app.privacy import build_embedding_text, mask_request_payload
from app.schemas import AiRequestDto, AiResponseDto, IngestResponseDto, ReEmbeddingResponseDto


app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/recommend", response_model=AiResponseDto)
def recommend(payload: AiRequestDto) -> AiResponseDto:
    try:
        profile = get_client_profile(payload.clientId)
        if profile is None:
            raise HTTPException(status_code=404, detail="client not found")

        masked = mask_request_payload(profile)
        query_text = build_embedding_text(masked)
        current_hash = compute_embedding_source_hash(query_text)
        saved_hash = get_client_embedding_source_hash(payload.clientId)
        if saved_hash == current_hash:
            # 기존 임베딩이 최신 입력 기준으로 이미 계산된 경우 OpenAI 호출 스킵
            query_embedding = get_client_embedding_vector(payload.clientId)
        else:
            query_embedding = create_embedding(query_text)
            update_client_embedding(payload.clientId, query_embedding)
            set_client_embedding_source_hash(payload.clientId, current_hash)

        # 해시는 동일하지만 벡터가 비어있는 예외 케이스 복구
        if query_embedding is None:
            query_embedding = create_embedding(query_text)
            update_client_embedding(payload.clientId, query_embedding)
            set_client_embedding_source_hash(payload.clientId, current_hash)
        similar_cases = search_similar_cases(
            query_embedding,
            top_k=payload.topK,
            exclude_client_id=payload.clientId,
        )
        recommendation = build_llm_recommendation(masked, similar_cases)
        return AiResponseDto(
            clientId=payload.clientId,
            maskedInput=masked,
            queryText=query_text,
            similarCases=similar_cases,
            recommendation=recommendation,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI recommendation failed: {e}") from e


@app.post("/api/v1/re-embedding", response_model=ReEmbeddingResponseDto)
def re_embedding() -> ReEmbeddingResponseDto:
    try:
        profiles = get_all_client_profiles()
        updated = 0
        for profile in profiles:
            masked = mask_request_payload(profile)
            text = build_embedding_text(masked)
            embedding = create_embedding(text)
            update_client_embedding(profile["clientId"], embedding)
            updated += 1
        return ReEmbeddingResponseDto(updatedCount=updated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-embedding failed: {e}") from e


@app.post("/api/v1/ingest-employment-training", response_model=IngestResponseDto)
def ingest_employment_training() -> IngestResponseDto:
    if not settings.ingest_excel_path:
        raise HTTPException(
            status_code=503,
            detail="INGEST_EXCEL_PATH not set. Set the env var to the Excel file path (e.g. /path/to/상담리스트_가공데이터_202602.xlsx).",
        )
    try:
        result = ingest_employment_training_from_excel(settings.ingest_excel_path)
        return IngestResponseDto(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}") from e
