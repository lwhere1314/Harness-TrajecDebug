"""Small Anthropic-compatible endpoint preflight for Harbor runs."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib import error, request


PROFILE_ALIASES = {
    "token_plan": "token-plan",
    "seed": "seed-coding-plan",
    "seed_coding_plan": "seed-coding-plan",
    "kimi-code": "kimi",
    "kimi_code": "kimi",
}

PROFILE_ENV = {
    "anthropic": ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", None),
    "seed-coding-plan": ("SEED_CODING_PLAN_BASE_URL", "SEED_CODING_PLAN_API_KEY", None),
    "token-plan": ("TOKEN_PLAN_BASE_URL", "TOKEN_PLAN_API_KEY", None),
    "ark": ("ARK_BASE_URL", "ARK_API_KEY", "https://ark.cn-beijing.volces.com/api/coding"),
    "dashscope": (
        "DASHSCOPE_BASE_URL",
        "DASHSCOPE_API_KEY",
        "https://coding.dashscope.aliyuncs.com/apps/anthropic",
    ),
    "kimi": ("KIMI_BASE_URL", "KIMI_API_KEY", "https://api.kimi.com/coding/"),
}


def messages_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/messages"):
        return base
    if base.endswith("/v1"):
        return base + "/messages"
    return base + "/v1/messages"


def normalize_profile(profile: str | None) -> str:
    raw = (profile or "auto").strip().lower()
    return PROFILE_ALIASES.get(raw, raw)


def _first_present_source(values: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        if values.get(name):
            return name
    return names[-1]


def resolve_endpoint_config(
    *,
    profile: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    values = env if env is not None else os.environ
    normalized = normalize_profile(profile)
    if normalized == "auto":
        resolved_profile = values.get("HTD_ENDPOINT_RESOLVED_PROFILE")
        if not resolved_profile:
            if values.get("ANTHROPIC_BASE_URL") or values.get("ANTHROPIC_API_KEY"):
                resolved_profile = "anthropic"
            elif values.get("SEED_CODING_PLAN_BASE_URL") or values.get("SEED_CODING_PLAN_API_KEY"):
                resolved_profile = "seed-coding-plan"
            elif values.get("TOKEN_PLAN_BASE_URL") or values.get("TOKEN_PLAN_API_KEY"):
                resolved_profile = "token-plan"
            else:
                resolved_profile = "auto"
        return {
            "profile": normalized,
            "resolved_profile": resolved_profile,
            "base_url": base_url
            or values.get("ANTHROPIC_BASE_URL")
            or values.get("SEED_CODING_PLAN_BASE_URL")
            or values.get("TOKEN_PLAN_BASE_URL"),
            "api_key": api_key
            or values.get("ANTHROPIC_API_KEY")
            or values.get("SEED_CODING_PLAN_API_KEY")
            or values.get("TOKEN_PLAN_API_KEY"),
            "base_url_source": "explicit"
            if base_url
            else _first_present_source(
                values,
                ("ANTHROPIC_BASE_URL", "SEED_CODING_PLAN_BASE_URL", "TOKEN_PLAN_BASE_URL"),
            ),
            "api_key_source": "explicit"
            if api_key
            else _first_present_source(
                values,
                ("ANTHROPIC_API_KEY", "SEED_CODING_PLAN_API_KEY", "TOKEN_PLAN_API_KEY"),
            ),
        }

    if normalized not in PROFILE_ENV:
        return {
            "profile": normalized,
            "base_url": base_url,
            "api_key": api_key,
            "error": f"unknown endpoint profile: {profile}",
        }

    base_env, key_env, default_base_url = PROFILE_ENV[normalized]
    return {
        "profile": normalized,
        "resolved_profile": values.get("HTD_ENDPOINT_RESOLVED_PROFILE") or normalized,
        "base_url": base_url or values.get(base_env) or default_base_url,
        "api_key": api_key or values.get(key_env),
        "base_url_source": "explicit" if base_url else (base_env if values.get(base_env) else "profile_default"),
        "api_key_source": "explicit" if api_key else key_env,
    }


def check_endpoint(
    base_url: str,
    api_key: str,
    model: str,
    timeout_sec: float = 20.0,
) -> dict[str, Any]:
    url = messages_url(base_url)
    body = {
        "model": model,
        "max_tokens": 8,
        "messages": [{"role": "user", "content": "Reply OK."}],
    }
    payload = json.dumps(body).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": api_key,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_sec) as response:
            raw = response.read(4096).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "kind": "ok" if 200 <= response.status < 300 else "http_error",
                "url": url,
                "body_excerpt": raw[:500],
            }
    except error.HTTPError as exc:
        raw = exc.read(4096).decode("utf-8", errors="replace")
        kind = "rate_limited" if exc.code == 429 else "http_error"
        return {
            "ok": False,
            "status": exc.code,
            "kind": kind,
            "url": url,
            "body_excerpt": raw[:500],
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "kind": "request_error",
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check an Anthropic-compatible Messages endpoint without printing secrets.")
    parser.add_argument(
        "--endpoint-profile",
        default=os.environ.get("HTD_ENDPOINT_PROFILE", "auto"),
        help="Endpoint profile: auto, anthropic, seed-coding-plan, token-plan, ark, dashscope, or kimi.",
    )
    parser.add_argument("--base-url")
    parser.add_argument("--api-key")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "kimi-k2.6"))
    parser.add_argument("--timeout-sec", type=float, default=20.0)
    parser.add_argument("--allow-fail", action="store_true", help="Exit 0 even when the endpoint check fails.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = resolve_endpoint_config(
        profile=args.endpoint_profile,
        base_url=args.base_url,
        api_key=args.api_key,
    )
    if config.get("error"):
        result = {
            "ok": False,
            "kind": "bad_endpoint_profile",
            "status": None,
            "profile": config.get("profile"),
            "resolved_profile": config.get("resolved_profile"),
            "error": config.get("error"),
        }
    elif not config.get("base_url") or not config.get("api_key"):
        result = {
            "ok": False,
            "kind": "missing_credentials",
            "status": None,
            "profile": config.get("profile"),
            "resolved_profile": config.get("resolved_profile"),
            "base_url_source": config.get("base_url_source"),
            "api_key_source": config.get("api_key_source"),
        }
    else:
        result = check_endpoint(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=args.model,
            timeout_sec=args.timeout_sec,
        )
        result["profile"] = config.get("profile")
        result["resolved_profile"] = config.get("resolved_profile")
        result["base_url_source"] = config.get("base_url_source")
        result["api_key_source"] = config.get("api_key_source")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") or args.allow_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
