import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def request_json(url, *, provider, headers, timeout, payload=None):
    request = Request(url, headers={"Content-Type": "application/json", **headers})
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        status = error.code
        error.close()
        raise ProviderError(
            f"{provider} returned HTTP {status}", retryable=status in (408, 429) or status >= 500
        ) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ProviderError(f"{provider} did not return a usable response") from None
