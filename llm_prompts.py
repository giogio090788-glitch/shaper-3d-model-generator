"""Prompt enhancement via LLM providers.

These models (GPT, Claude, Kimi K3, Qwen, Llama) can't emit meshes — they
expand a short idea into a rich, structured prompt that the actual 3D
engines (local procedural, Shap-E, Meshy, Tripo, Stability) consume.
"""
import os
import requests


class LLMError(Exception):
    pass


SYSTEM = (
    "You are a prompt engineer for 3D model generation. Rewrite the user's "
    "idea as ONE detailed prompt (80 words max) describing a single 3D model: "
    "overall shape, structure, materials, colors, art style and proportions. "
    "Reply with the prompt only — no preamble, no quotes, no markdown."
)

# OpenAI-compatible chat endpoints: provider -> (url, default model, key env var)
OPENAI_COMPAT = {
    "openai": ("https://api.openai.com/v1/chat/completions",
               "gpt-4o-mini", "OPENAI_API_KEY"),
    "kimi": ("https://api.moonshot.ai/v1/chat/completions",
             "kimi-k3", "MOONSHOT_API_KEY"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
             "qwen-plus", "DASHSCOPE_API_KEY"),
    "llama": ("https://openrouter.ai/api/v1/chat/completions",
              "meta-llama/llama-3.3-70b-instruct", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1/chat/completions",
               "llama3.1", None),
}

PROVIDERS = sorted(OPENAI_COMPAT) + ["claude"]


def enhance(prompt: str, provider: str, api_key: str | None = None,
            model: str | None = None, timeout: int = 90) -> str:
    if provider == "none":
        return prompt
    if provider == "claude":
        return _anthropic(prompt, api_key, model, timeout)
    if provider in OPENAI_COMPAT:
        return _openai_compat(prompt, provider, api_key, model, timeout)
    raise LLMError(f"Unknown LLM provider: {provider}")


def _openai_compat(prompt: str, provider: str, api_key: str | None,
                   model: str | None, timeout: int) -> str:
    url, default_model, env = OPENAI_COMPAT[provider]
    key = api_key or (os.environ.get(env) if env else None)
    if env and not key:
        raise LLMError(f"No {provider} API key — paste one in the UI or set {env}.")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model or default_model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        raise LLMError(f"{provider} request failed: {e}")
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected {provider} response: {str(data)[:200]}") from e


def _anthropic(prompt: str, api_key: str | None, model: str | None,
               timeout: int) -> str:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("No Anthropic API key — paste one in the UI or set ANTHROPIC_API_KEY.")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or "claude-sonnet-4-5",
        "max_tokens": 300,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        raise LLMError(f"Anthropic request failed: {e}")
    data = r.json()
    try:
        return "".join(b["text"] for b in data["content"]
                       if b.get("type") == "text").strip()
    except (KeyError, TypeError) as e:
        raise LLMError(f"Unexpected Anthropic response: {str(data)[:200]}") from e
