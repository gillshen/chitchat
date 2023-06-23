import datetime
import argparse
import contextlib

from core import openai, Request, BaseChat, MAX_TOKENS, count_tokens


class _NotNoneDict(dict):
    def __setitem__(self, key, value):
        if value is None:
            return
        super().__setitem__(key, value)


class Chat(BaseChat):
    @classmethod
    def from_data(
        cls,
        system_message: str = "",
        title: str = "",
        date_started: str = "",
        history: None | list[Request] = None,
    ):
        chat = cls(system_message=system_message, title=title)
        chat._date_started = date_started
        chat._history = chat._context = history or []
        return chat

    @property
    def date_started(self) -> str:
        return self._date_started

    @property
    def system_message(self) -> str:
        return self._system_message

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, title: str):
        self._title = title

    @property
    def history(self) -> list[Request]:
        return self._history

    @property
    def context(self) -> list[Request]:
        return self._context

    def reset_context(self):
        self._context = []

    def trim_context(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int = MAX_TOKENS,
        reserve_tokens: int = MAX_TOKENS // 10,
    ):
        # Remove the earliest prompt and reply if the context is too long
        if not self.context:
            return
        prompt_tokens = count_tokens(prompt, model)
        while self.tokens_used(model) + prompt_tokens + reserve_tokens > max_tokens:
            self.context.pop(0)

    def create_completion(
        self,
        model: str,
        prompt: str,
        temperature: float = None,
        top_p: float = None,
        presence_penalty: float = None,
        frequency_penalty: float = None,
        max_tokens: int = MAX_TOKENS,
        reserve_tokens: int = MAX_TOKENS // 10,
    ):
        self.trim_context(
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            reserve_tokens=reserve_tokens,
        )

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

        request = Request(
            model=model,
            prompt=prompt,
            response="".join(response_chunks),
            timestamp=str(datetime.datetime.now()),
            **params,
        )
        self.history.append(request)
        self.context.append(request)

    def _generate_messages(self) -> list[dict]:
        # generate the `message` parameter for completion
        messages = []
        for req in self.context:
            messages.append({"role": "assistant", "content": req.prompt})
            messages.append({"role": "assistant", "content": req.response})
        return messages

    @property
    def last_request(self) -> Request | None:
        with contextlib.suppress(IndexError):
            return self.history[-1]

    @property
    def last_response(self) -> str | None:
        with contextlib.suppress(AttributeError):
            return self.last_request.response

    def tokens_used(self, model: str) -> int:
        in_system = count_tokens(self._system_message, model)
        in_context = sum([req.length(model) for req in self.context])
        return in_system + in_context


def _test(args: argparse.Namespace):
    print(f"{args=}")
    chat = Chat(system_message=args.system_message)
    max_tokens = args.max_tokens
    reserve_tokens = args.reserve_tokens
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
        for content in chat.create_completion(
            prompt=prompt,
            max_tokens=max_tokens,
            reserve_tokens=reserve_tokens,
            **kwargs,
        ):
            print(content, end="")
        print("\n")
        print(f">>> token used: {chat.tokens_used(args.model)}/{MAX_TOKENS}")
        print(f">>> history: {len(chat.history)}")
        print(f">>> context: {len(chat.context)}")


# Command line use
_argparser = argparse.ArgumentParser(prog="Chat")
_argparser.add_argument("--model", default="gpt-3.5-turbo")
_argparser.add_argument("--system-message", default="You're a helpful assistant.")
_argparser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
_argparser.add_argument("--reserve_tokens", type=int, default=MAX_TOKENS // 10)
_argparser.add_argument("--temperature", type=float)
_argparser.add_argument("--top-p", type=float)


if __name__ == "__main__":
    _test(_argparser.parse_args())
