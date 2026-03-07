import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hmac
import json
import math
from io import BytesIO
from pathlib import Path
import secrets
import ssl
import sys
import time

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import GradeRequest, GradeResult, GeneratedTest, ProgressResponse, TestRequest
from app.config import settings
from app.services.openai_client import AIClient, AIClientError
from app.services.power import SleepBlocker
from app.services.progress_store import ProgressStore
from app.services.test_service import TestService

progress_store = ProgressStore(Path(__file__).parent.parent / "data" / "progress.json")
service = TestService(
    ai_client=AIClient(),
    progress_store=progress_store,
)
sleep_blocker = SleepBlocker()
static_dir = Path(__file__).parent / "static"
THROTTLE_SECONDS = 60.0
UI_TOKEN_COOKIE = "ocenime_ui_token"
UI_TOKEN_HEADER = "x-ui-token"


class EndpointRateLimiter:
    def __init__(self, window_seconds: float) -> None:
        self._window_seconds = window_seconds
        self._last_seen: dict[tuple[str, str], float] = {}

    def enforce(self, endpoint: str, identity: str) -> None:
        key = (endpoint, identity)
        now = time.monotonic()
        previous = self._last_seen.get(key)
        if previous is not None:
            elapsed = now - previous
            if elapsed < self._window_seconds:
                retry_after = max(1, math.ceil(self._window_seconds - elapsed))
                raise HTTPException(
                    status_code=429,
                    detail=f"Prevec zahtevkov. Poskusi znova cez {retry_after} sekund.",
                    headers={"Retry-After": str(retry_after)},
                )
        self._last_seen[key] = now


rate_limiter = EndpointRateLimiter(window_seconds=THROTTLE_SECONDS)


def _is_ignorable_windows_reset(context: dict) -> bool:
    exc = context.get("exception")
    if not isinstance(exc, ConnectionResetError):
        return False
    if getattr(exc, "winerror", None) != 10054:
        return False
    message = str(context.get("message") or "")
    handle = context.get("handle")
    return "_ProactorBasePipeTransport" in message or "_ProactorBasePipeTransport" in repr(handle)


def _loop_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    if _is_ignorable_windows_reset(context):
        return
    loop.default_exception_handler(context)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if sys.platform.startswith("win"):
        asyncio.get_running_loop().set_exception_handler(_loop_exception_handler)
    sleep_blocker.enable()
    try:
        yield
    finally:
        sleep_blocker.disable()


app = FastAPI(title="OceniMe - Test Generator", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    response = FileResponse(static_dir / "index.html")
    token = secrets.token_urlsafe(24)
    response.set_cookie(
        key=UI_TOKEN_COOKIE,
        value=token,
        secure=True,
        httponly=False,
        samesite="strict",
        max_age=24 * 60 * 60,
        path="/",
    )
    return response


@app.post("/api/tests/generate", response_model=GeneratedTest)
def generate_test(
    request: Request, req: TestRequest, response: Response, x_session_id: str | None = Header(default=None)
) -> GeneratedTest:
    client_ip = _request_client_ip(request)
    session_id = x_session_id or "anonymous"
    try:
        _ensure_ui_request_token(request)
        rate_limiter.enforce(endpoint="generate", identity=_request_identity(request, x_session_id))
        result = service.generate_test(req, session_id=session_id)
        _set_ai_model_headers(response)
        _log_api_event(
            endpoint="generate",
            status="ok",
            client_ip=client_ip,
            session_id=session_id,
            student_id="",
            topic=req.topic,
            chapter=req.chapter,
            test_id=result.test_id,
        )
        return result
    except HTTPException as exc:
        _log_api_event(
            endpoint="generate",
            status=f"error:{exc.status_code}",
            client_ip=client_ip,
            session_id=session_id,
            student_id="",
            topic=req.topic,
            chapter=req.chapter,
            test_id="",
        )
        raise
    except AIClientError as exc:
        _log_api_event(
            endpoint="generate",
            status="error:502",
            client_ip=client_ip,
            session_id=session_id,
            student_id="",
            topic=req.topic,
            chapter=req.chapter,
            test_id="",
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/tests/grade", response_model=GradeResult)
async def grade_test(
    request: Request,
    response: Response,
    x_session_id: str | None = Header(default=None),
    x_student_id: str | None = Header(default=None),
) -> GradeResult:
    client_ip = _request_client_ip(request)
    session_id = x_session_id or "anonymous"
    student_id = x_student_id or "anonymous"
    try:
        _ensure_ui_request_token(request)
        rate_limiter.enforce(endpoint="grade", identity=_request_identity(request, x_session_id))
        req = await _parse_grade_request(request)
        result = service.grade_test(
            req,
            session_id=session_id,
            student_id=student_id,
            client_ip=client_ip,
        )
        _set_ai_model_headers(response)
        _log_api_event(
            endpoint="grade",
            status="ok",
            client_ip=client_ip,
            session_id=session_id,
            student_id=student_id,
            topic="",
            chapter="",
            test_id=req.test_id,
        )
        return result
    except HTTPException as exc:
        _log_api_event(
            endpoint="grade",
            status=f"error:{exc.status_code}",
            client_ip=client_ip,
            session_id=session_id,
            student_id=student_id,
            topic="",
            chapter="",
            test_id="",
        )
        raise
    except KeyError as exc:
        _log_api_event(
            endpoint="grade",
            status="error:404",
            client_ip=client_ip,
            session_id=session_id,
            student_id=student_id,
            topic="",
            chapter="",
            test_id="",
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        _log_api_event(
            endpoint="grade",
            status="error:409",
            client_ip=client_ip,
            session_id=session_id,
            student_id=student_id,
            topic="",
            chapter="",
            test_id="",
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AIClientError as exc:
        _log_api_event(
            endpoint="grade",
            status="error:502",
            client_ip=client_ip,
            session_id=session_id,
            student_id=student_id,
            topic="",
            chapter="",
            test_id="",
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/progress", response_model=ProgressResponse)
def get_progress(x_student_id: str | None = Header(default=None)) -> ProgressResponse:
    return service.get_progress(student_id=x_student_id or "anonymous")


@app.get("/api/connect/qr")
def connect_qr(data: str = Query(min_length=1, max_length=1024)) -> Response:
    try:
        import qrcode
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="QR podpora ni na voljo. Namesti odvisnosti z: pip install -r requirements.txt",
        ) from exc

    img = qrcode.make(data)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


async def _parse_grade_request(request: Request) -> GradeRequest:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type.lower():
        payload = await request.json()
        return GradeRequest.model_validate(payload)

    try:
        form = await request.form()
    except AssertionError as exc:
        if "python-multipart" in str(exc):
            raise HTTPException(
                status_code=500,
                detail=(
                    "Za multipart/form-data manjka odvisnost 'python-multipart'. "
                    "Namesti pakete z: pip install -r requirements.txt"
                ),
            ) from exc
        raise
    test_id = str(form.get("test_id") or "").strip()
    if not test_id:
        raise HTTPException(status_code=422, detail="Manjka test_id.")

    raw_answers = str(form.get("answers_json") or "{}")
    try:
        parsed_answers = json.loads(raw_answers)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="answers_json ni veljaven JSON.") from exc

    if not isinstance(parsed_answers, dict):
        raise HTTPException(status_code=422, detail="answers_json mora biti objekt.")

    answers: dict[str, str] = {str(k): str(v) for k, v in parsed_answers.items()}

    for key, value in form.multi_items():
        if not key.startswith("image_") or not isinstance(value, UploadFile):
            continue
        question_id = key[len("image_") :].strip()
        if not question_id:
            continue
        _validate_image_upload(value)
        marker = f"[Prilozena slika odgovora: {value.filename or 'brez_imena'}]"
        existing = answers.get(question_id, "").strip()
        answers[question_id] = f"{existing}\n{marker}".strip() if existing else marker

    return GradeRequest(test_id=test_id, answers=answers)


def _validate_image_upload(file: UploadFile) -> None:
    content_type = (file.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail=f"Datoteka '{file.filename}' ni slika.")


def _set_ai_model_headers(response: Response) -> None:
    configured, used = service.get_model_info()
    response.headers["X-AI-Model-Configured"] = configured
    response.headers["X-AI-Model-Used"] = used


def _request_identity(request: Request, x_session_id: str | None) -> str:
    session = (x_session_id or "").strip()
    if session:
        return session
    client_host = request.client.host if request.client else ""
    if client_host:
        return client_host
    return "anonymous"


def _request_client_ip(request: Request) -> str:
    # Prefer proxy chain if present, then fallback to direct socket IP.
    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _ensure_ui_request_token(request: Request) -> None:
    cookie_token = (request.cookies.get(UI_TOKEN_COOKIE) or "").strip()
    header_token = (request.headers.get(UI_TOKEN_HEADER) or "").strip()
    if not cookie_token or not header_token:
        raise HTTPException(status_code=403, detail="Dostop zavrnjen (manjka UI varnostni zeton).")
    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="Dostop zavrnjen (neveljaven UI varnostni zeton).")


def _log_api_event(
    endpoint: str,
    status: str,
    client_ip: str,
    session_id: str,
    student_id: str,
    topic: str,
    chapter: str,
    test_id: str,
) -> None:
    progress_store.append_event(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "status": status,
            "client_ip": client_ip,
            "session_id": session_id,
            "student_id": student_id,
            "topic": topic,
            "chapter": chapter,
            "test_id": test_id,
        }
    )


def _validate_tls_certificate_pair(certfile: Path, keyfile: Path) -> None:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
    except ssl.SSLError as exc:
        raise RuntimeError(
            "SSL_CERTFILE/SSL_KEYFILE are not a valid TLS certificate pair in PEM format. "
            "Note: SSH keys (from ssh-keygen, like id_ed25519) cannot be used as HTTPS certificates."
        ) from exc


def run() -> None:
    import uvicorn

    if sys.platform.startswith("win"):
        # Avoid noisy Proactor disconnect tracebacks on Windows when clients reset connections.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    certfile = settings.resolve_path(settings.ssl_certfile)
    keyfile = settings.resolve_path(settings.ssl_keyfile)
    if not certfile.exists() or not keyfile.exists():
        missing = [str(path) for path in (certfile, keyfile) if not path.exists()]
        missing_str = ", ".join(missing)
        raise RuntimeError(
            f"HTTPS certificates were not found: {missing_str}. "
            "Create cert/key files and configure SSL_CERTFILE and SSL_KEYFILE."
        )
    _validate_tls_certificate_pair(certfile, keyfile)

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        ssl_certfile=str(certfile),
        ssl_keyfile=str(keyfile),
        timeout_keep_alive=5,
        timeout_graceful_shutdown=5,
    )


if __name__ == "__main__":
    run()
