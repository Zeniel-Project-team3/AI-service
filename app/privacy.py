import re
from copy import deepcopy
from typing import Any


_RESIDENT_ID_PATTERN = re.compile(r"^(\d{6})[-]?(\d{7})$")


def _mask_name(name: str) -> str:
    if not name:
        return ""
    if len(name) == 1:
        return "*"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + ("*" * (len(name) - 2)) + name[-1]


def _mask_resident_id(resident_id: str) -> str:
    match = _RESIDENT_ID_PATTERN.match(resident_id or "")
    if not match:
        return "RESIDENT_ID_MASKED"
    front, back = match.groups()
    return f"{front}-{'*' * len(back)}"


def parse_sigungu(address: str | None) -> str | None:
    if not address:
        return None
    parts = [p for p in re.split(r"\s+", address.strip()) if p]
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return parts[0] if parts else None


def normalize_desired_jobs(raw: Any) -> list[str]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []

    tokens = re.split(r"[\n,/]+", text)
    normalized: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        item = token.strip()
        if not item:
            continue
        item = re.sub(r"^\d+\.\s*", "", item)  # "1. 직종" -> "직종"
        item = re.sub(r"^-\s*", "", item)      # "- 직종" -> "직종"
        item = item.strip()
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def mask_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    masked = deepcopy(payload)
    masked["name"] = _mask_name(str(payload.get("name", "")))
    masked["residentId"] = _mask_resident_id(str(payload.get("residentId", "")))
    return masked


def build_embedding_text(masked_payload: dict[str, Any]) -> str:
    """임베딩용 텍스트. 나이·성별·희망직종만 사용해 유사도 검색에 쓴다."""
    desired_jobs = normalize_desired_jobs(masked_payload.get("desiredJob"))
    desired_jobs_text = ", ".join(desired_jobs) if desired_jobs else "(미정)"
    return (
        "[기본정보]\n"
        f"나이: {masked_payload.get('age')}\n"
        f"성별: {masked_payload.get('gender')}\n"
        f"희망직종: {desired_jobs_text}\n"
    )
