import argparse
from pathlib import Path

from ollama import chat

from env_loader import load_env
import os


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Ollama VLM with a local image using project env settings."
    )
    parser.add_argument(
        "--image",
        help="Path to local image file. If omitted, script asks interactively.",
    )
    parser.add_argument(
        "--prompt",
        help="Override prompt. Defaults to OLLAMA_VLM_PROMPT from .env.",
    )
    parser.add_argument(
        "--model",
        help="Override model. Defaults to OLLAMA_VLM_MODEL from .env.",
    )
    return parser.parse_args()


def resolve_image_path(image_arg: str | None) -> Path:
    if image_arg:
        candidate = image_arg.strip()
    else:
        candidate = input("Please enter the path to the image: ").strip()

    path = Path(candidate).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    return path


def main() -> None:
    load_env()
    args = parse_args()

    model_name = (args.model or os.getenv("OLLAMA_VLM_MODEL", "qwen3.5:397b-cloud")).strip()
    prompt = (
        args.prompt
        or os.getenv("OLLAMA_VLM_PROMPT", "What is in this image? Be concise.")
    ).strip()

    if not model_name:
        raise SystemExit("OLLAMA_VLM_MODEL is empty. Set it in .env or pass --model.")

    image_path = resolve_image_path(args.image)

    response = chat(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": [str(image_path)],
            }
        ],
    )

    print("Model:", model_name)
    print("Image:", image_path)
    print("Prompt:", prompt)
    print("Response:")
    print(response.message.content)


if __name__ == "__main__":
    main()
