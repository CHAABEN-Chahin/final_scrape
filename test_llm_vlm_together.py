import argparse
import json
from pathlib import Path

from ai_pipeline import run_ollama_vlm_on_local_images, send_to_llm
from env_loader import load_env
import os


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Ollama VLM + Groq LLM chained together."
    )
    parser.add_argument("--image", required=True, help="Path to a local image file")
    parser.add_argument(
        "--text",
        required=True,
        help="Post text to combine with VLM output in the LLM stage",
    )
    parser.add_argument(
        "--project-name",
        default="manual_test_project",
        help="Project name used in payload",
    )
    parser.add_argument(
        "--source-url",
        default="https://example.com/manual-test",
        help="Source URL used in payload",
    )
    parser.add_argument(
        "--poster-name",
        default="manual_test_poster",
        help="Poster name used in payload",
    )
    return parser.parse_args()


def main() -> None:
    load_env()
    args = parse_args()

    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists() or not image_path.is_file():
        raise SystemExit(f"Image not found: {image_path}")

    vlm_model = os.getenv("OLLAMA_VLM_MODEL", "qwen3.5:397b-cloud").strip()
    vlm_prompt = os.getenv(
        "OLLAMA_VLM_PROMPT",
        "Extract tender details from this image in JSON.",
    ).strip()

    platform = "facebook"

    vlm_result = run_ollama_vlm_on_local_images(
        image_paths=[str(image_path)],
        model_name=vlm_model,
        prompt=vlm_prompt,
    )

    filtered_payload = {
        "source_url": args.source_url,
        "poster_name": args.poster_name,
        "post_text": args.text,
        "images": [str(image_path)],
    }
    llm_result = send_to_llm(args.project_name, filtered_payload, vlm_result, platform)

    result = {
        "vlm": vlm_result,
        "llm": llm_result,
        "final_decision": {
            "validated": bool(llm_result.get("validated", False)),
            "next_phase_ready": bool(llm_result.get("next_phase_ready", False)),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
