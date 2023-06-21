import typing
import json
import datetime
import functools
import argparse

import openai
import tiktoken


DEFAULT_MODEL = "gpt-3.5-turbo"

with open("chat_settings.json", encoding="utf-8") as _f:
    chat_settings = json.load(_f)

openai.api_key = chat_settings.get("key", "")
openai.api_base = chat_settings.get("base", openai.api_base)
MAX_TOKENS = chat_settings.get("max_tokens", 4097)

del _f


class _Request(typing.NamedTuple):
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


class _NotNoneDict(dict):
    def __setitem__(self, key, value):
        if value is None:
            return
        super().__setitem__(key, value)


class Chat:
    def __init__(
        self,
        name: str = "",
        system_message: str = "",
        reserve_tokens: int = MAX_TOKENS // 10,
    ):
        self.name = name or str(datetime.datetime.now())
        self._system_message = system_message
        self.reserve_tokens = reserve_tokens

        # a complete record of conversation
        self._history: list[_Request] = []

        # a subset of self.history
        self._context: list[_Request] = []

    def __str__(self):
        return self.name

    @property
    def history(self):
        return self._history

    @property
    def context(self):
        return self._context

    def reset_context(self):
        self._context = []

    def create_completion(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = None,
        top_p: float = None,
        presence_penalty: float = None,
        frequency_penalty: float = None,
    ):
        # Remove the earliest prompt and reply if the context is too long
        while self.tokens_used(model) + self.reserve_tokens > MAX_TOKENS:
            self._context.pop(0)

        messages = [{"role": "system", "content": self._system_message}]
        messages.extend(self._generate_messages())
        messages.append({"role": "user", "content": prompt})

        params = _NotNoneDict()
        params["temperature"] = temperature
        params["top_p"] = top_p
        params["presence_penalty"] = presence_penalty
        params["frequency_penalty"] = frequency_penalty

        response_chunks = []
        for chunk in openai.ChatCompletion.create(
            model=model,
            stream=True,
            messages=messages,
            **params,
        ):
            delta = chunk["choices"][0]["delta"]
            try:
                content = delta["content"]
            except KeyError:
                # sometimes `delta` is missing `content`
                continue
            response_chunks.append(content)
            yield content

        request = _Request(
            model=model,
            prompt=prompt,
            response="".join(response_chunks),
            timestamp=str(datetime.datetime.now()),
            **params,
        )
        self._history.append(request)
        self._context.append(request)

    def _generate_messages(self) -> list[dict]:
        # generate the `message` parameter for completion
        messages = []
        for req in self._context:
            messages.append({"role": "assistant", "content": req.prompt})
            messages.append({"role": "assistant", "content": req.response})
        return messages

    def tokens_used(self, model: str) -> int:
        in_system = count_tokens(self._system_message, model)
        in_context = sum([req.length(model) for req in self._context])
        return in_system + in_context


@functools.lru_cache(maxsize=None)
def count_tokens(text: str, model: str):
    """Return the number of tokens in string `s`."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


def _test(args: argparse.Namespace):
    print(f"{args=}")
    chat = Chat(
        system_message=args.system_message,
        reserve_tokens=args.reserve_tokens,
    )
    kwargs = _NotNoneDict(model=args.model)
    kwargs["temperature"] = args.temperature
    kwargs["top_p"] = args.top_p

    while True:
        try:
            prompt = input("> ")
        except KeyboardInterrupt:
            print("\n>>> session ended")
            return
        if prompt == "--reset":
            chat.reset_context()
            print(">>> context has been reset")
            continue
        print(">>>")
        for content in chat.create_completion(prompt=prompt, **kwargs):
            print(content, end="")
        print("\n")
        print(f">>> token used: {chat.tokens_used(args.model)}/{MAX_TOKENS}")
        print(f">>> history: {len(chat.history)}")
        print(f">>> context: {len(chat.context)}")


# Command line use
_argparser = argparse.ArgumentParser(prog="Chat")
_argparser.add_argument("--model", default="gpt-3.5-turbo")
_argparser.add_argument("--system-message", default="You're a helpful assistant.")
_argparser.add_argument("--reserve_tokens", type=int, default=MAX_TOKENS // 10)
_argparser.add_argument("--temperature", type=float)
_argparser.add_argument("--top-p", type=float)


if __name__ == "__main__":
    _test(_argparser.parse_args())
