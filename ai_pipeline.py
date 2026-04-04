import json
import os
import tempfile
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

from ollama import chat

from env_loader import load_env

load_env()

GROQ_ENDPOINT = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions").strip()

# User-configurable age for eligibility checks.
TARGET_USER_AGE = 30


def _post_json(endpoint: str, api_key: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(endpoint, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "fb-scraper/1.0")
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


def _extract_json_from_text(raw_text: str) -> dict | None:
    text = (raw_text or "").strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _default_vlm_prompt() -> str:
    return (
        "You are extracting call-for-tender visual information from images. "
        "Return JSON only with this exact shape: "
        "{"
        '\"deadline_text\":\"\",'
        '\"deadline_iso\":\"\",'
        '\"location_text\":\"\",'
        '\"is_in_sfax\":\"true|false|unknown\",'
        '\"payment_text\":\"\",'
        '\"is_paid\":\"true|false|unknown\",'
        '\"age_requirement_text\":\"\",'
        '\"min_age\":\"\",'
        '\"max_age\":\"\",'
        '\"domain\":\"\",'
        '\"prize_or_budget_text\":\"\",'
        '\"evidence\":[\"...\"]'
        "}. "
        "If a value is missing, use empty string or unknown. "
        "Focus especially on deadline, payment, age eligibility, location, and domain."
    )


def download_image_to_path(image_url: str, local_path: Path, source_url: str, platform: str) -> None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    if platform == "linkedin":
        headers["Referer"] = source_url or "https://www.linkedin.com/"

    req = request.Request(image_url, headers=headers)
    with request.urlopen(req, timeout=25) as response:
        local_path.write_bytes(response.read())


def run_ollama_vlm_on_local_images(image_paths: list[str], model_name: str, prompt: str) -> dict:
    if not image_paths:
        return {
            "status": "skipped",
            "reason": "No local image paths provided for VLM.",
        }

    try:
        response = chat(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": image_paths,
                }
            ],
        )
        return {
            "status": "ok",
            "model": model_name,
            "prompt": prompt,
            "image_count": len(image_paths),
            "response": response.message.content,
        }
    except Exception as exc:
        return {
            "status": "error",
            "model": model_name,
            "error": str(exc),
        }


def send_to_llm(project_name: str, filtered_payload: dict, vlm_result: dict, platform: str) -> dict:
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    model_name = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile").strip()
    system_prompt = os.getenv(
        "GROQ_LLM_SYSTEM_PROMPT",
        "You are an expert evaluator for Tunisian appels d'offre. "
        "Decide if a post is VALIDATED for the user based on 3 strict conditions: "
        "(1) age eligibility is unspecified or compatible with target user age, "
        "(2) work is paid (not free/voluntary), "
        "(3) location is in Sfax. "
        "Use both text and VLM extraction. Return JSON only.",
    ).strip()

    vlm_output = ""
    if isinstance(vlm_result, dict) and vlm_result.get("status") == "ok":
        vlm_output = str(vlm_result.get("response", "")).strip()

    raw_vlm_structured = _extract_json_from_text(vlm_output)

    user_payload = {
        "platform": platform,
        "project_name": project_name,
        "target_user_age": TARGET_USER_AGE,
        "source_url": filtered_payload.get("source_url", ""),
        "poster_name": filtered_payload.get("poster_name", ""),
        "post_text": filtered_payload.get("post_text", ""),
        "vlm_output": vlm_output,
        "vlm_structured": raw_vlm_structured,
        "task": (
            "Return JSON only with exact keys: "
            "validated (boolean), "
            "next_phase_ready (boolean), "
            "conditions ({age_eligible:boolean, is_paid:boolean, in_sfax:boolean}), "
            "missing_or_unclear ([string]), "
            "decision_reason (string), "
            "summary_two_sentences (string exactly two sentences), "
            "important_info ({deadline:string, prize_or_budget:string, domain:string, location:string, poster_name:string}), "
            "evidence ([string]). "
            "Set validated=true only if all 3 conditions are true. "
            "Set next_phase_ready exactly equal to validated. "
            "Summary must include deadline, prize_or_budget, and domain when available."
        ),
    }

    if not groq_api_key:
        return {
            "status": "skipped",
            "reason": "GROQ_API_KEY is not configured.",
            "payload_preview": user_payload,
        }

    if not model_name:
        return {
            "status": "skipped",
            "reason": "GROQ_LLM_MODEL is not configured.",
            "payload_preview": user_payload,
        }

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        "temperature": 0.2,
    }

    result = _post_json(endpoint=GROQ_ENDPOINT, api_key=groq_api_key, payload=payload)
    if result.get("status") != "ok":
        return result

    try:
        choices = result["response"].get("choices", [])
        final_answer = choices[0]["message"]["content"] if choices else ""
    except Exception:
        final_answer = ""

    structured = _extract_json_from_text(final_answer)

    result["model"] = model_name
    result["final_answer"] = final_answer
    result["structured"] = structured
    if isinstance(structured, dict):
        result["validated"] = bool(structured.get("validated", False))
        result["next_phase_ready"] = bool(structured.get("next_phase_ready", False))
    else:
        result["validated"] = False
        result["next_phase_ready"] = False
    return result


def send_to_vlm(project_name: str, filtered_payload: dict, platform: str) -> dict:
    model_name = os.getenv("OLLAMA_VLM_MODEL", "qwen3.5:397b-cloud").strip()
    prompt = os.getenv(
        "OLLAMA_VLM_PROMPT",
        _default_vlm_prompt(),
    ).strip()
    image_urls = filtered_payload.get("images", [])
    source_url = str(filtered_payload.get("source_url", "") or "")

    if not model_name:
        return {
            "status": "skipped",
            "reason": "OLLAMA_VLM_MODEL is not configured.",
            "payload_preview": {
                "platform": platform,
                "project_name": project_name,
                "source_url": filtered_payload.get("source_url", ""),
                "poster_name": filtered_payload.get("poster_name", ""),
                "image_urls": image_urls,
                "task": prompt,
            },
        }

    if not image_urls:
        return {
            "status": "skipped",
            "reason": "No image URLs available for VLM analysis.",
            "payload_preview": {
                "platform": platform,
                "project_name": project_name,
                "source_url": filtered_payload.get("source_url", ""),
                "poster_name": filtered_payload.get("poster_name", ""),
                "task": prompt,
            },
        }

    downloaded_paths: list[str] = []
    with tempfile.TemporaryDirectory(prefix="fb_vlm_") as temp_dir:
        for idx, image_url in enumerate(image_urls, start=1):
            try:
                ext = Path(image_url.split("?", 1)[0]).suffix or ".jpg"
                local_path = Path(temp_dir) / f"image_{idx}{ext}"
                download_image_to_path(
                    image_url=image_url,
                    local_path=local_path,
                    source_url=source_url,
                    platform=platform,
                )
                downloaded_paths.append(str(local_path))
            except Exception as exc:
                print(f"Failed to download image for VLM: {image_url} ({exc})")

        if not downloaded_paths:
            return {
                "status": "error",
                "reason": "All image downloads failed; cannot call VLM.",
            }

        return run_ollama_vlm_on_local_images(
            image_paths=downloaded_paths,
            model_name=model_name,
            prompt=prompt,
        )


def run_ai_preparation(project_name: str, filtered_payload: dict, platform: str) -> dict:
    vlm_result = send_to_vlm(project_name, filtered_payload, platform)
    llm_result = send_to_llm(project_name, filtered_payload, vlm_result, platform)
    final_decision = {
        "validated": bool(llm_result.get("validated", False)),
        "next_phase_ready": bool(llm_result.get("next_phase_ready", False)),
    }

    next_phase_payload = None
    if final_decision["next_phase_ready"]:
        structured = llm_result.get("structured") if isinstance(llm_result, dict) else None
        important_info = structured.get("important_info", {}) if isinstance(structured, dict) else {}

        conclusion_two_sentences = ""
        deadline = ""
        price = ""
        domain = ""

        if isinstance(structured, dict):
            conclusion_two_sentences = str(structured.get("summary_two_sentences", "")).strip()
            deadline = str(important_info.get("deadline", "")).strip()
            price = str(important_info.get("prize_or_budget", "")).strip()
            domain = str(important_info.get("domain", "")).strip()

        # Fallback to VLM extracted fields when LLM leaves values empty.
        vlm_structured = None
        if isinstance(vlm_result, dict) and vlm_result.get("status") == "ok":
            vlm_structured = _extract_json_from_text(str(vlm_result.get("response", "")))
        if isinstance(vlm_structured, dict):
            if not deadline:
                deadline = str(vlm_structured.get("deadline_text", "")).strip()
            if not price:
                price = str(vlm_structured.get("prize_or_budget_text", "")).strip()
            if not domain:
                domain = str(vlm_structured.get("domain", "")).strip()

        next_phase_payload = {
            "platform": platform,
            "category": platform,
            "project_name": project_name,
            "source_url": filtered_payload.get("source_url", ""),
            "conclusion_two_sentences": conclusion_two_sentences,
            "price": price,
            "deadline": deadline,
            "domain": domain,
        }

    return {
        "vlm": vlm_result,
        "llm": llm_result,
        "final_decision": final_decision,
        "next_phase_payload": next_phase_payload,
    }
