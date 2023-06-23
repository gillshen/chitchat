import json
import functools
import typing
import abc
import datetime

import openai
import tiktoken

with open("chat_settings.json", encoding="utf-8") as _f:
    chat_settings = json.load(_f)

openai.api_key = chat_settings.get("key", "")
openai.api_base = chat_settings.get("base", openai.api_base)
DEFAULT_MODEL = chat_settings.get("default_model", "gpt-3.5-turbo")
MAX_TOKENS = chat_settings.get("max_tokens", 4097)

del _f


@functools.lru_cache(maxsize=None)
def count_tokens(text: str, model: str):
    """Return the number of tokens in string `s`."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


class Request(typing.NamedTuple):
    model: str = DEFAULT_MODEL
    prompt: None | str = None
    response: None | str = None
    timestamp: None | str = None

    # OpenAI doc:
    # > What sampling temperature to use, between 0 and 2. Higher values
    # > like 0.8 will make the output more random, while lower values
    # > like 0.2 will make it more focused and deterministic.
    temperature: None | float = None

    # OpenAI doc:
    # > An alternative to sampling with temperature, called nucleus sampling,
    # > where the model considers the results of the tokens with `top_p`
    # > probability mass. So 0.1 means only the tokens comprising the top
    # > 10% probability mass are considered.
    top_p: None | float = None

    # OpenAI doc:
    # > Number between -2.0 and 2.0. Positive values penalize new tokens
    # > based on whether they appear in the text so far, increasing the
    # > model's likelihood to talk about new topics.
    presence_penalty: None | float = None

    # OpenAI doc:
    # > Number between -2.0 and 2.0. Positive values penalize new tokens
    # > based on their existing frequency in the text so far, decreasing
    # > the model's likelihood to repeat the same line verbatim.
    frequency_penalty: None | float = None

    def length(self, model: str = None):
        model = model or self.model
        prompt_length = count_tokens(self.prompt, self.model)
        response_length = count_tokens(self.response, self.model)
        return prompt_length + response_length


class BaseChat(abc.ABC):
    def __init__(self, *, system_message: str = "", title: str = ""):
        # `_date_started` and `_system_message` shall be readonly
        self._date_started = str(datetime.datetime.now())
        self._system_message = system_message

        # `_title` may be altered
        self._title = title or self._date_started

        # A complete record of the conversation minus the system message
        self._history: list[Request] = []

        # A subset of `self._history`, to serve as the context for completion
        self._context: list[Request] = []

    def __str__(self):
        return self._title

    @classmethod
    @abc.abstractmethod
    def from_data(
        cls,
        system_message: str = "",
        title: str = "",
        date_started: str = "",
        history: None | list[Request] = None,
    ):
        pass

    @property
    @abc.abstractmethod
    def date_started(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def system_message(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def title(self) -> str:
        pass

    @title.setter
    @abc.abstractmethod
    def title(self, title: str):
        pass

    @property
    @abc.abstractmethod
    def history(self) -> list[Request]:
        pass

    @property
    @abc.abstractmethod
    def context(self) -> list[Request]:
        pass

    @abc.abstractmethod
    def reset_context(self):
        pass

    @abc.abstractmethod
    def trim_context(
        self,
        model: str,
        max_tokens: int = MAX_TOKENS,
        reserve_tokens: int = MAX_TOKENS // 10,
    ):
        pass

    @abc.abstractmethod
    def create_completion(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = None,
        top_p: float = None,
        presence_penalty: float = None,
        frequency_penalty: float = None,
        max_tokens: int = MAX_TOKENS,
        reserve_tokens: int = MAX_TOKENS // 10,
    ):
        pass

    @property
    @abc.abstractmethod
    def last_request(self) -> Request | None:
        pass

    @property
    @abc.abstractmethod
    def last_response(self) -> str | None:
        pass

    @abc.abstractmethod
    def tokens_used(self, model: str) -> int:
        pass
