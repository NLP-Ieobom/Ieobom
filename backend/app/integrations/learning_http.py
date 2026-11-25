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
        try:
            body = json.loads(error.read(4096))
            detail = body.get("error", {}).get("message")
        except (OSError, ValueError, AttributeError):
            detail = None
        finally:
            error.close()
        message = f"{provider} returned HTTP {status}"
        if isinstance(detail, str):
            message += f": {detail[:500]}"
        raise ProviderError(
            message, retryable=status in (408, 429) or status >= 500
        ) from None
    except TimeoutError:
        raise ProviderError(f"{provider} timed out after {timeout}s") from None
    except (URLError, OSError, ValueError):
        raise ProviderError(f"{provider} did not return a usable response") from None
