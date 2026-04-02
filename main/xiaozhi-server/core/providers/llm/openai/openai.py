import httpx
import openai
from openai.types import CompletionUsage
from config.logger import setup_logging
from core.utils.util import check_model_key
from core.providers.llm.base import LLMProviderBase
from typing import Dict, Any

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        self.api_key = config.get("api_key")
        if "base_url" in config:
            self.base_url = config.get("base_url")
        else:
            self.base_url = config.get("url")
        timeout = config.get("timeout", 300)
        self.timeout = int(timeout) if timeout else 300

        param_defaults = {
            "max_tokens": int,
            "temperature": lambda x: round(float(x), 1),
            "top_p": lambda x: round(float(x), 1),
            "frequency_penalty": lambda x: round(float(x), 1),
        }

        for param, converter in param_defaults.items():
            value = config.get(param)
            try:
                setattr(
                    self,
                    param,
                    converter(value) if value not in (None, "") else None,
                )
            except (ValueError, TypeError):
                setattr(self, param, None)

        logger.debug(
            f"Intent recognition parameter initialization: {self.temperature}, {self.max_tokens}, {self.top_p}"
        )

        model_key_msg = check_model_key("LLM", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=httpx.Timeout(self.timeout))

    @staticmethod
    def _is_unsupported_error(err: Exception) -> bool:
        msg = str(err).lower()
        return (
            "unsupported" in msg
            or "does not support" in msg
            or "not supported" in msg
        )

    def _strip_optional(self, params: Dict[str, Any], optional_keys) -> Dict[str, Any]:
        """Return a copy with unsupported/optional keys removed."""
        cleaned = dict(params)
        for k in optional_keys:
            cleaned.pop(k, None)
        return cleaned

    def _create_chat_completion(self, request_params: Dict[str, Any], optional_keys) -> Any:
        """
        Call OpenAI API with graceful downgrade when model rejects some params.
        First try with all provided params; on 'unsupported' errors, retry without optional keys.
        """
        try:
            return self.client.chat.completions.create(**request_params)
        except Exception as e:
            if self._is_unsupported_error(e) and optional_keys:
                logger.bind(tag=TAG).warning(
                    f"Model rejected some params, retrying without optional params. Error: {e}"
                )
                stripped = self._strip_optional(request_params, optional_keys)
                return self.client.chat.completions.create(**stripped)
            raise

    @staticmethod
    def normalize_dialogue(dialogue):
        """Automatically fix messages with missing content in dialogue"""
        for msg in dialogue:
            if "role" in msg and "content" not in msg:
                msg["content"] = ""
        return dialogue

    def response(self, session_id, dialogue, **kwargs):
        try:
            dialogue = self.normalize_dialogue(dialogue)

            request_params = {
                "model": self.model_name,
                "messages": dialogue,
                "stream": True,
            }

            # Add optional parameters, only add when parameter is not None
            optional_params = {
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
                "top_p": kwargs.get("top_p", self.top_p),
                "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
            }

            optional_keys_present = []
            for key, value in optional_params.items():
                if value is not None:
                    request_params[key] = value
                    optional_keys_present.append(key)

            responses = self._create_chat_completion(request_params, optional_keys_present)

            is_active = True
            for chunk in responses:
                try:
                    delta = chunk.choices[0].delta if getattr(chunk, "choices", None) else None
                    content = getattr(delta, "content", "") if delta else ""
                except IndexError:
                    content = ""
                if content:
                    if "<think>" in content:
                        is_active = False
                        content = content.split("<think>")[0]
                    if "</think>" in content:
                        is_active = True
                        content = content.split("</think>")[-1]
                    if is_active:
                        yield content

        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")

    def response_with_functions(self, session_id, dialogue, functions=None, **kwargs):
        try:
            dialogue = self.normalize_dialogue(dialogue)

            request_params = {
                "model": self.model_name,
                "messages": dialogue,
                "stream": True,
                "tools": functions,
            }

            optional_params = {
                "max_completion_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
                "top_p": kwargs.get("top_p", self.top_p),
                "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
            }

            optional_keys_present = []
            for key, value in optional_params.items():
                if value is not None:
                    request_params[key] = value
                    optional_keys_present.append(key)

            stream = self._create_chat_completion(request_params, optional_keys_present)

            for chunk in stream:
                if getattr(chunk, "choices", None):
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", "")
                    tool_calls = getattr(delta, "tool_calls", None)
                    yield content, tool_calls
                elif isinstance(getattr(chunk, "usage", None), CompletionUsage):
                    usage_info = getattr(chunk, "usage", None)
                    logger.bind(tag=TAG).info(
                        f"Token consumption: input {getattr(usage_info, 'prompt_tokens', 'Unknown')},"
                        f"output {getattr(usage_info, 'completion_tokens', 'Unknown')},"
                        f"total {getattr(usage_info, 'total_tokens', 'Unknown')}"
                    )

        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in function call streaming: {e}")
            yield f"【OpenAI服务响应异常: {e}】", None
