from pathlib import Path
import json

from fastapi import FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import GradeRequest, GradeResult, GeneratedTest, ProgressResponse, TestRequest
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


@app.on_event("startup")
def startup() -> None:
    sleep_blocker.enable()


@app.on_event("shutdown")
def shutdown() -> None:
    sleep_blocker.disable()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.post("/api/tests/generate", response_model=GeneratedTest)
def generate_test(req: TestRequest, x_session_id: str | None = Header(default=None)) -> GeneratedTest:
    try:
        return service.generate_test(req, session_id=x_session_id or "anonymous")
    except AIClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/tests/grade", response_model=GradeResult)
async def grade_test(
    request: Request,
    x_session_id: str | None = Header(default=None),
    x_student_id: str | None = Header(default=None),
) -> GradeResult:
    try:
        req = await _parse_grade_request(request)
        return service.grade_test(
            req,
            session_id=x_session_id or "anonymous",
            student_id=x_student_id or "anonymous",
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/progress", response_model=ProgressResponse)
def get_progress(x_student_id: str | None = Header(default=None)) -> ProgressResponse:
    return service.get_progress(student_id=x_student_id or "anonymous")


async def _parse_grade_request(request: Request) -> GradeRequest:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type.lower():
        payload = await request.json()
        return GradeRequest.model_validate(payload)

    form = await request.form()
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
