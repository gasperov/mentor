from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any


class ProgressStore:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._text_log_path = file_path.parent / "progress.txt"
        self._events_jsonl_path = file_path.parent / "api_events.jsonl"
        self._events_text_path = file_path.parent / "api_events.txt"
        self._lock = Lock()
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists():
            self._write({"students": {}})
        if not self._text_log_path.exists():
            self._write_text_header()
        else:
            self._ensure_text_header_schema()
        if not self._events_jsonl_path.exists():
            self._events_jsonl_path.write_text("", encoding="utf-8")
        if not self._events_text_path.exists():
            self._write_events_text_header()

    def append_attempt(self, student_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            data = self._read()
            students = data.setdefault("students", {})
            attempts = students.setdefault(student_id, [])
            attempts.append(payload)
            # Keep latest 200 attempts per student to bound file growth.
            if len(attempts) > 200:
                students[student_id] = attempts[-200:]
            self._write(data)
            self._append_text_row(student_id, payload)

    def get_attempts(self, student_id: str) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
            students = data.get("students", {})
            attempts = students.get(student_id, [])
            return list(attempts)

    def append_event(self, payload: dict[str, Any]) -> None:
        with self._lock:
            line = json.dumps(payload, ensure_ascii=True)
            with self._events_jsonl_path.open("a", encoding="utf-8") as f:
                f.write(f"{line}\n")
            self._append_events_text_row(payload)

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self._file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"students": {}}

    def _write(self, payload: dict[str, Any]) -> None:
        self._file_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _write_text_header(self) -> None:
        header = self._format_row(
            "timestamp",
            "student_id",
            "client_ip",
            "topic",
            "chapter",
            "level",
            "score",
            "knowledge_level",
        )
        line = "-" * len(header)
        self._text_log_path.write_text(f"{header}\n{line}\n", encoding="utf-8")

    def _append_text_row(self, student_id: str, payload: dict[str, Any]) -> None:
        if not self._text_log_path.exists():
            self._write_text_header()
        row = self._format_row(
            str(payload.get("timestamp", "")),
            student_id,
            str(payload.get("client_ip", "")),
            str(payload.get("topic", "")),
            str(payload.get("chapter", "")),
            str(payload.get("level", "")),
            str(payload.get("score", "")),
            str(payload.get("knowledge_level", "")),
        )
        with self._text_log_path.open("a", encoding="utf-8") as f:
            f.write(f"{row}\n")

    def _format_row(
        self,
        timestamp: str,
        student_id: str,
        client_ip: str,
        topic: str,
        chapter: str,
        level: str,
        score: str,
        knowledge_level: str,
    ) -> str:
        return (
            f"{timestamp[:25]:<25} | "
            f"{student_id[:18]:<18} | "
            f"{client_ip[:39]:<39} | "
            f"{topic[:20]:<20} | "
            f"{chapter[:20]:<20} | "
            f"{level[:18]:<18} | "
            f"{score[:5]:<5} | "
            f"{knowledge_level[:14]:<14}"
        )

    def _ensure_text_header_schema(self) -> None:
        try:
            content = self._text_log_path.read_text(encoding="utf-8")
        except OSError:
            return
        lines = content.splitlines()
        if not lines:
            self._write_text_header()
            return
        if "client_ip" in lines[0]:
            return
        old_rows = lines[2:] if len(lines) > 2 else []
        header = self._format_row(
            "timestamp",
            "student_id",
            "client_ip",
            "topic",
            "chapter",
            "level",
            "score",
            "knowledge_level",
        )
        sep = "-" * len(header)
        rebuilt = [header, sep] + old_rows
        self._text_log_path.write_text("\n".join(rebuilt) + "\n", encoding="utf-8")

    def _write_events_text_header(self) -> None:
        header = (
            f"{'timestamp':<25} | "
            f"{'endpoint':<18} | "
            f"{'status':<8} | "
            f"{'client_ip':<39} | "
            f"{'session_id':<24} | "
            f"{'student_id':<18} | "
            f"{'topic':<20} | "
            f"{'chapter':<20} | "
            f"{'test_id':<36}"
        )
        line = "-" * len(header)
        self._events_text_path.write_text(f"{header}\n{line}\n", encoding="utf-8")

    def _append_events_text_row(self, payload: dict[str, Any]) -> None:
        if not self._events_text_path.exists():
            self._write_events_text_header()
        row = (
            f"{str(payload.get('timestamp', ''))[:25]:<25} | "
            f"{str(payload.get('endpoint', ''))[:18]:<18} | "
            f"{str(payload.get('status', ''))[:8]:<8} | "
            f"{str(payload.get('client_ip', ''))[:39]:<39} | "
            f"{str(payload.get('session_id', ''))[:24]:<24} | "
            f"{str(payload.get('student_id', ''))[:18]:<18} | "
            f"{str(payload.get('topic', ''))[:20]:<20} | "
            f"{str(payload.get('chapter', ''))[:20]:<20} | "
            f"{str(payload.get('test_id', ''))[:36]:<36}"
        )
        with self._events_text_path.open("a", encoding="utf-8") as f:
            f.write(f"{row}\n")
