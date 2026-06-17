import json
import ssl
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import current_app


class AIConfigError(RuntimeError):
    """DeepSeek 配置缺失时抛出。"""


class AIResponseError(RuntimeError):
    """DeepSeek 返回内容不符合预期时抛出。"""


def chat_json(messages, temperature=0.2):
    """调用 DeepSeek，并要求模型返回 JSON 对象。"""
    api_key = (current_app.config.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        raise AIConfigError("DeepSeek API Key 未配置，请在 app/config.py 的 DEEPSEEK_API_KEY 中填写。")

    base_url = str(current_app.config.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).rstrip("/")
    timeout = current_app.config.get("DEEPSEEK_TIMEOUT", 30)
    max_tokens = current_app.config.get("DEEPSEEK_MAX_TOKENS", 1200)
    payload = {
        "model": current_app.config.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    try:
        request = urllib_request.Request(
            url=f"{base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        context = ssl.create_default_context()
        with urllib_request.urlopen(request, timeout=timeout, context=context) as response:
            response_text = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        message = detail or exc.reason or str(exc)
        raise AIResponseError(f"DeepSeek 调用失败：{message}") from exc
    except urllib_error.URLError as exc:
        raise AIResponseError(f"DeepSeek 网络请求失败：{exc.reason}") from exc

    try:
        response_data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise AIResponseError("DeepSeek 返回内容不是合法 JSON。") from exc

    choices = response_data.get("choices") or []
    if not choices:
        raise AIResponseError("DeepSeek 返回内容为空。")

    choice = choices[0]
    content = (choice.get("message") or {}).get("content") or ""
    if not content:
        raise AIResponseError("DeepSeek 返回内容为空。")
    if choice.get("finish_reason") == "length":
        raise AIResponseError("DeepSeek 返回被截断，请适当缩短输入内容。")

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIResponseError("DeepSeek 返回内容不是合法 JSON。") from exc
