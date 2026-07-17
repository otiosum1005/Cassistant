from openai import OpenAI
from .config import load_config

class LLMClient:
    def __init__(self):
        self.config = load_config()
        self.client = OpenAI(
            base_url=self.config.llm_base_url,
            api_key=self.config.llm_api_key,
            timeout=self.config.llm_timeout
        )

    def completion(self, messages, temperature=None, stream=False):
        temp = temperature if temperature is not None else self.config.llm_temperature
        return self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=messages,
            temperature=temp,
            stream=stream
        )
