import os
import asyncio
from openai import AsyncOpenAI, APIError, RateLimitError
from novel_bot.config.settings import settings
from loguru import logger
from typing import Any

class LLMProvider:
    def __init__(self):
        api_key = settings.NVIDIA_API_KEY
        base_url = settings.NVIDIA_BASE_URL

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = settings.model_name
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        logger.info(f"Initialized LLM Provider with model: {self.model} at {base_url}")

    async def chat(self, messages: list[dict], tools: list[dict] = None) -> Any:
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.9,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(**params)
                return response.choices[0].message
            except (APIError, RateLimitError) as e:
                last_error = e
                logger.warning(f"LLM API Error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"LLM API failed after {self.max_retries} attempts")
            except Exception as e:
                # Handle JSON parsing errors and other unexpected errors from the API
                error_msg = str(e)
                if "unexpected end of data" in error_msg or "JSON" in error_msg or "parse" in error_msg.lower():
                    last_error = e
                    logger.warning(f"LLM API Response Parse Error (attempt {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"LLM API failed after {self.max_retries} attempts due to response parsing errors")
                else:
                    logger.error(f"Unexpected LLM API Error: {e}")
                    raise

        raise last_error
