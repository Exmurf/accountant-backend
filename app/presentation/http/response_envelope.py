import json
import logging
from collections.abc import Sequence

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class ApiResponseEnvelopeMiddleware:
    """Give every API response the same top-level shape.

    This lives at the HTTP boundary so route handlers and use cases keep
    returning their natural response models. It also preserves every original
    header verbatim (including both Set-Cookie headers used by authentication).
    """

    def __init__(self, app: ASGIApp, api_prefix: str = "/api/v1") -> None:
        self.app = app
        self.api_prefix = api_prefix.rstrip("/")

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http" or not self._is_api_path(scope):
            await self.app(scope, receive, send)
            return

        start_message: Message | None = None
        body_parts: list[bytes] = []
        response_started = False

        async def send_enveloped(message: Message) -> None:
            nonlocal start_message, response_started

            if message["type"] == "http.response.start":
                start_message = message
                return

            if message["type"] != "http.response.body":
                await send(message)
                return

            body_parts.append(message.get("body", b""))
            if message.get("more_body", False):
                return

            if start_message is None:
                raise RuntimeError("Response body was sent before response start")

            status_code = start_message["status"]
            payload = self._decode_payload(b"".join(body_parts))
            body = self._encode_envelope(status_code, payload)
            headers = self._with_content_length(
                start_message.get("headers", []), len(body)
            )

            response_started = True
            await send({**start_message, "headers": headers})
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                    "more_body": False,
                }
            )

        try:
            await self.app(scope, receive, send_enveloped)
        except Exception:
            if response_started:
                raise
            logger.exception("Unhandled exception while processing an API request")
            await self._send_internal_error(send)

    def _is_api_path(self, scope: Scope) -> bool:
        path = scope.get("path", "")
        return path == self.api_prefix or path.startswith(f"{self.api_prefix}/")

    @staticmethod
    def _decode_payload(body: bytes):  # type: ignore[no-untyped-def]
        if not body:
            return None
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return body.decode("utf-8", errors="replace")

    @staticmethod
    def _encode_envelope(status_code: int, payload) -> bytes:  # type: ignore[no-untyped-def]
        return json.dumps(
            {"status": status_code < 400, "data": payload},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _with_content_length(
        headers: Sequence[tuple[bytes, bytes]], body_length: int
    ) -> list[tuple[bytes, bytes]]:
        kept = [
            (name, value)
            for name, value in headers
            if name.lower() not in {b"content-length", b"content-type"}
        ]
        kept.append((b"content-type", b"application/json; charset=utf-8"))
        kept.append((b"content-length", str(body_length).encode("ascii")))
        return kept

    async def _send_internal_error(self, send: Send) -> None:
        body = self._encode_envelope(
            500,
            {"detail": "Beklenmeyen bir sunucu hatası oluştu."},
        )
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
