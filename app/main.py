import base64
import binascii
import hmac
from pathlib import Path
import json
from io import BytesIO

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import GradeRequest, GradeResult, GeneratedTest, ProgressResponse, TestRequest
from app.config import settings
from app.services.openai_client import AIClient, AIClientError
from app.services.power import SleepBlocker
from app.services.progress_store import ProgressStore
from app.services.test_service import TestService

app = FastAPI(title="LearnMe - Test Generator")

service = TestService(
    ai_client=AIClient(),
    progress_store=ProgressStore(Path(__file__).parent.parent / "data" / "progress.json"),
)
sleep_blocker = SleepBlocker()
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class BasicAuth:
    def __init__(self, users_file: Path) -> None:
        self._users_file = users_file
        self._users: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        if not self._users_file.exists():
            raise RuntimeError(f"Basic auth users file was not found: {self._users_file}")

        payload = json.loads(self._users_file.read_text(encoding="utf-8"))
        users: dict[str, str] = {}

        if isinstance(payload, dict) and isinstance(payload.get("users"), list):
            for item in payload["users"]:
                if not isinstance(item, dict):
                    continue
                username = str(item.get("username") or "").strip()
                password = str(item.get("password") or "")
                if username and password:
                    users[username] = password
        elif isinstance(payload, dict):
            for username, password in payload.items():
                if username and isinstance(password, str) and password:
                    users[str(username)] = password

        if not users:
            raise RuntimeError(
                f"Basic auth users file has no valid users: {self._users_file}. "
                "Expected {'users':[{'username':'...','password':'...'}]}."
            )

        self._users = users

    def verify_authorization_header(self, authorization: str | None) -> bool:
        if not authorization:
            return False
        scheme, _, encoded = authorization.partition(" ")
        if scheme.lower() != "basic" or not encoded:
            return False

        try:
            decoded = base64.b64decode(encoded).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return False

        username, sep, password = decoded.partition(":")
        if not sep or not username:
            return False
        expected_password = self._users.get(username)
        if expected_password is None:
            return False
        return hmac.compare_digest(expected_password, password)


basic_auth = BasicAuth(settings.resolve_path(settings.basic_auth_users_file)) if settings.basic_auth_enabled else None


@app.on_event("startup")
def startup() -> None:
    if basic_auth:
        basic_auth.reload()
    sleep_blocker.enable()


@app.on_event("shutdown")
def shutdown() -> None:
    sleep_blocker.disable()


@app.middleware("http")
async def require_basic_auth(request: Request, call_next):
    if not settings.basic_auth_enabled:
        return await call_next(request)
    if basic_auth and basic_auth.verify_authorization_header(request.headers.get("authorization")):
        return await call_next(request)
    return Response(
        content="Unauthorized",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="LearnMe", charset="UTF-8"'},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.post("/api/tests/generate", response_model=GeneratedTest)
def generate_test(
    req: TestRequest, response: Response, x_session_id: str | None = Header(default=None)
) -> GeneratedTest:
    try:
        result = service.generate_test(req, session_id=x_session_id or "anonymous")
        _set_ai_model_headers(response)
        return result
    except AIClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/tests/grade", response_model=GradeResult)
async def grade_test(
    request: Request,
    response: Response,
    x_session_id: str | None = Header(default=None),
    x_student_id: str | None = Header(default=None),
) -> GradeResult:
    try:
        req = await _parse_grade_request(request)
        result = service.grade_test(
            req,
            session_id=x_session_id or "anonymous",
            student_id=x_student_id or "anonymous",
        )
        _set_ai_model_headers(response)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIClientError as exc:
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


def run() -> None:
    import uvicorn

    certfile = settings.resolve_path(settings.ssl_certfile)
    keyfile = settings.resolve_path(settings.ssl_keyfile)
    if not certfile.exists() or not keyfile.exists():
        missing = [str(path) for path in (certfile, keyfile) if not path.exists()]
        missing_str = ", ".join(missing)
        raise RuntimeError(
            f"HTTPS certificates were not found: {missing_str}. "
            "Create cert/key files and configure SSL_CERTFILE and SSL_KEYFILE."
        )

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        ssl_certfile=str(certfile),
        ssl_keyfile=str(keyfile),
    )


if __name__ == "__main__":
    run()
