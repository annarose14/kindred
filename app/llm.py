"""Thin LLM wrapper with a saved-answer cache and a backup model. Tests replace it with a fake.

Resilience, in order:
  1. Saved answer: the same request (for example a sample note) reuses the earlier answer instantly.
  2. Main model (GROQ_MODEL).
  3. Backup model (GROQ_FALLBACK_MODEL): Groq's limits are per model, so this often still works.
  4. If all fail, the caller falls back to plain rules (see intake.rules_profile, planner.fallback_plan).
"""
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "llm"


class LLMError(Exception):
    pass


class GroqLLM:
    def __init__(self, api_key=None, model=None, fallback_model=None, use_cache=True):
        from groq import Groq
        # Fail fast: a slow model call must not keep a link worker (or a judge) waiting.
        self.client = Groq(api_key=api_key or os.getenv("GROQ_API_KEY"), timeout=15.0, max_retries=0)
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.fallback_model = fallback_model or os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
        self.use_cache = use_cache
        self.last_model = None
        if use_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, system, user):
        key = hashlib.sha256(json.dumps([self.model, system, user]).encode()).hexdigest()[:32]
        return CACHE_DIR / f"{key}.json"

    def _call(self, model, system, user):
        reply = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.2,
            reasoning_effort="low",
        )
        return json.loads(reply.choices[0].message.content)

    def chat_json(self, system, user):
        cache_file = self._cache_file(system, user)
        if self.use_cache and cache_file.exists():
            self.last_model = "saved answer"
            return json.loads(cache_file.read_text())
        errors = []
        for model in dict.fromkeys([self.model, self.fallback_model]):
            if not model:
                continue
            try:
                data = self._call(model, system, user)
            except Exception as e:  # rate limit, timeout, bad JSON: try the next model
                errors.append(f"{model}: {type(e).__name__}")
                continue
            self.last_model = model
            if self.use_cache and isinstance(data, dict):
                cache_file.write_text(json.dumps(data))
            return data
        raise LLMError("; ".join(errors) or "no model configured")
