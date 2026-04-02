import json
import os
from urllib import request
from urllib.error import HTTPError, URLError


def _post_json(endpoint: str, api_key: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(endpoint, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw_response": body}
            return {
                "status": "ok",
                "http_status": response.status,
                "response": parsed,
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "status": "error",
            "http_status": exc.code,
            "error": body,
        }
    except URLError as exc:
        return {
            "status": "error",
            "http_status": None,
            "error": str(exc),
        }


def send_to_llm(project_name: str, filtered_payload: dict) -> dict:
    endpoint = os.getenv("LLM_API_URL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()

    payload = {
        "project_name": project_name,
        "source_url": filtered_payload.get("source_url", ""),
        "poster_name": filtered_payload.get("poster_name", ""),
        "post_text": filtered_payload.get("post_text", ""),
        "task": "Analyze this social post text. Return structured summary only.",
    }

    if not endpoint:
        return {
            "status": "skipped",
            "reason": "LLM_API_URL is not configured.",
            "payload_preview": payload,
        }

    return _post_json(endpoint=endpoint, api_key=api_key, payload=payload)


def send_to_vlm(project_name: str, filtered_payload: dict) -> dict:
    endpoint = os.getenv("VLM_API_URL", "").strip()
    api_key = os.getenv("VLM_API_KEY", "").strip()

    payload = {
        "project_name": project_name,
        "source_url": filtered_payload.get("source_url", ""),
        "poster_name": filtered_payload.get("poster_name", ""),
        "image_urls": filtered_payload.get("images", []),
        "task": "Analyze these social post images. Return structured summary only.",
    }

    if not endpoint:
        return {
            "status": "skipped",
            "reason": "VLM_API_URL is not configured.",
            "payload_preview": payload,
        }

    return _post_json(endpoint=endpoint, api_key=api_key, payload=payload)


def run_ai_preparation(project_name: str, filtered_payload: dict) -> dict:
    llm_result = send_to_llm(project_name, filtered_payload)
    vlm_result = send_to_vlm(project_name, filtered_payload)
    return {
        "llm": llm_result,
        "vlm": vlm_result,
    }
