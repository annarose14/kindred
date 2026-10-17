"""Thin LLM wrapper. Tests replace it with a fake, so nothing here is called in tests."""
import json
import os

from dotenv import load_dotenv

load_dotenv()


class LLMError(Exception):
    pass


class GroqLLM:
    def __init__(self, api_key=None, model=None):
        from groq import Groq
        self.client = Groq(api_key=api_key or os.getenv("GROQ_API_KEY"))
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    def chat_json(self, system, user):
        try:
            reply = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                temperature=0.2,
                reasoning_effort="low",
            )
            return json.loads(reply.choices[0].message.content)
        except Exception as e:
            raise LLMError(str(e)) from e
