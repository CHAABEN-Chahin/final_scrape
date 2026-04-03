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


def send_to_llm(project_name: str, filtered_payload: dict, vlm_result: dict) -> dict:
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    model_name = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile").strip()
    system_prompt = os.getenv(
        "GROQ_LLM_SYSTEM_PROMPT",
        "You are an analyst. Produce a concise final answer using both text and image analysis.",
    ).strip()

    vlm_output = ""
    if isinstance(vlm_result, dict) and vlm_result.get("status") == "ok":
        vlm_output = str(vlm_result.get("response", "")).strip()

    user_payload = {
        "project_name": project_name,
        "source_url": filtered_payload.get("source_url", ""),
        "poster_name": filtered_payload.get("poster_name", ""),
        "post_text": filtered_payload.get("post_text", ""),
        "vlm_output": vlm_output,
        "task": "Generate one final answer that combines the post text with the image analysis.",
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

    result["model"] = model_name
    result["final_answer"] = final_answer
    return result


def send_to_vlm(project_name: str, filtered_payload: dict) -> dict:
    model_name = os.getenv("OLLAMA_VLM_MODEL", "qwen3.5:397b-cloud").strip()
    prompt = os.getenv(
        "OLLAMA_VLM_PROMPT",
        "What is in this image? Be concise.",
    ).strip()
    image_urls = filtered_payload.get("images", [])

    if not model_name:
        return {
            "status": "skipped",
            "reason": "OLLAMA_VLM_MODEL is not configured.",
            "payload_preview": {
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
                request.urlretrieve(image_url, local_path)
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


def run_ai_preparation(project_name: str, filtered_payload: dict) -> dict:
    vlm_result = send_to_vlm(project_name, filtered_payload)
    llm_result = send_to_llm(project_name, filtered_payload, vlm_result)
    return {
        "vlm": vlm_result,
        "llm": llm_result,
    }
