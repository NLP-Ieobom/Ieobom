import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    def __init__(
        self, message: str, *, retryable: bool = True, http_status: int | None = None,
        retry_after: str | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.http_status = http_status
        self.retry_after = retry_after


class ProviderOutputError(ProviderError):
    """The provider replied, but its generated output could not be used safely."""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


def request_json(url, *, provider, headers, timeout, payload=None):
    request = Request(url, headers={"Content-Type": "application/json", **headers})
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        status = error.code
        retry_after = error.headers.get("Retry-After")
        try:
            raw = error.read(4096).decode("utf-8", "replace")
        except OSError:
            raw = ""
        finally:
            error.close()
        try:
            detail = json.loads(raw).get("error", {}).get("message")
        except (ValueError, AttributeError):
            detail = None
        if not isinstance(detail, str):
            # 레이트리밋 응답은 error.message 구조가 아니라 본문을 그대로 남겨야 정체를 알 수 있다.
            detail = " ".join(raw.split())
        message = f"{provider} returned HTTP {status}"
        if detail:
            message += f": {detail[:500]}"
        raise ProviderError(
            message, retryable=status in (408, 429) or status >= 500, http_status=status,
            retry_after=retry_after,
        ) from None
    except TimeoutError:
        raise ProviderError(f"{provider} timed out after {timeout}s") from None
    except (URLError, OSError, ValueError):
        raise ProviderError(f"{provider} did not return a usable response") from None
