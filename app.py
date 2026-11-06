from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DATA_FILE = ROOT / "data.json"
TEMPLATES_FILE = ROOT / "templates.json"
CORRECTIONS_DIR = ROOT / "corrections"


DEFAULT_DATA = {
    "templates": [
        {
            "id": "fase-1-padrao",
            "max_grade": 10,
            "criteria": [
                {
                    "id": "Estrutura",
                    "comments": [
                        {"id": "OK", "message": "Estrutura adequada."},
                        {"id": "ORG", "message": "Organize melhor a sequência das ideias."},
                    ],
                },
                {
                    "id": "Conteúdo",
                    "comments": [
                        {"id": "OK", "message": "Conteúdo adequado."},
                        {"id": "APR", "message": "Aprofunde a discussão dos conceitos principais."},
                    ],
                },
            ],
            "header_comments": [
                {"id": "OK", "message": "Obrigado pela entrega."},
            ],
            "footer_comments": [
                {"id": "REV", "message": "Revise os pontos indicados antes da próxima entrega."},
            ],
        },
        {
            "id": "fase-2-padrao",
            "max_grade": 10,
            "criteria": [
                {
                    "id": "Correções",
                    "comments": [
                        {"id": "OK", "message": "As correções solicitadas foram contempladas."},
                        {"id": "PEN", "message": "Ainda há ajustes pendentes em relação à etapa anterior."},
                    ],
                },
                {
                    "id": "Resultado",
                    "comments": [
                        {"id": "OK", "message": "Resultado final adequado."},
                        {"id": "FIN", "message": "Finalize melhor a apresentação do resultado."},
                    ],
                },
            ],
            "header_comments": [
                {"id": "RET", "message": "Segue o retorno da segunda fase."},
            ],
            "footer_comments": [
                {"id": "ENC", "message": "Bom trabalho no fechamento da atividade."},
            ],
        },
    ],
    "corrections": [],
}


def read_json_file(path: Path, fallback: dict | list) -> dict | list:
    if not path.exists():
        return json.loads(json.dumps(fallback))
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json_file(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def correction_file_path(correction_id: str) -> Path:
    return CORRECTIONS_DIR / f"{slug(correction_id)}.json"


def migrate_legacy_data() -> None:
    if TEMPLATES_FILE.exists() or not DATA_FILE.exists():
        return
    legacy = read_json_file(DATA_FILE, DEFAULT_DATA)
    save_data(
        {
            "templates": legacy.get("templates", DEFAULT_DATA["templates"]),
            "corrections": legacy.get("corrections", []),
        }
    )


def load_templates() -> list:
    payload = read_json_file(TEMPLATES_FILE, {"templates": DEFAULT_DATA["templates"]})
    if isinstance(payload, list):
        return payload
    return payload.get("templates", [])


def save_templates(templates: list) -> None:
    write_json_file(TEMPLATES_FILE, {"templates": templates})


def load_corrections() -> list:
    CORRECTIONS_DIR.mkdir(exist_ok=True)
    corrections = []
    for path in sorted(CORRECTIONS_DIR.glob("*.json")):
        correction = read_json_file(path, {})
        if isinstance(correction, dict) and correction.get("id"):
            corrections.append(correction)
    return corrections


def save_correction(correction: dict) -> None:
    write_json_file(correction_file_path(correction["id"]), correction)


def delete_correction_file(correction_id: str) -> None:
    path = correction_file_path(correction_id)
    if path.exists():
        path.unlink()


def load_data() -> dict:
    migrate_legacy_data()
    if not TEMPLATES_FILE.exists():
        save_templates(json.loads(json.dumps(DEFAULT_DATA["templates"])))
    return {"templates": load_templates(), "corrections": load_corrections()}


def save_data(data: dict) -> None:
    save_templates(data.get("templates", []))
    CORRECTIONS_DIR.mkdir(exist_ok=True)
    current_ids = {correction["id"] for correction in data.get("corrections", [])}
    for path in CORRECTIONS_DIR.glob("*.json"):
        existing = read_json_file(path, {})
        if isinstance(existing, dict) and existing.get("id") not in current_ids:
            path.unlink()
    for correction in data.get("corrections", []):
        save_correction(correction)


def slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    return clean or "item"


def ok_comment(message: str = "OK") -> dict:
    return {"id": "OK", "message": message}


def normalize_template(template: dict) -> dict:
    normalized = {
        "id": slug(str(template.get("id", ""))),
        "max_grade": float(template.get("max_grade") or 0),
        "criteria": [],
        "header_comments": list(template.get("header_comments") or []),
        "footer_comments": list(template.get("footer_comments") or []),
    }

    for criterion in template.get("criteria") or []:
        criterion_id = str(criterion.get("id", "")).strip()
        if not criterion_id:
            continue
        comments = list(criterion.get("comments") or [])
        if not any(comment.get("id") == "OK" for comment in comments):
            comments.insert(0, ok_comment("OK"))
        normalized["criteria"].append({"id": criterion_id, "comments": comments})

    return normalized


def find_template(data: dict, template_id: str) -> dict | None:
    return next((item for item in data["templates"] if item["id"] == template_id), None)


def find_correction(data: dict, correction_id: str) -> dict | None:
    return next((item for item in data["corrections"] if item["id"] == correction_id), None)


def selected_comments_for_template(template: dict) -> dict:
    return {
        criterion["id"]: ["OK"] if any(comment["id"] == "OK" for comment in criterion["comments"]) else []
        for criterion in template["criteria"]
    }


def make_work_item(index: int) -> dict:
    return {
        "id": f"trabalho-{index}",
        "student_name": "",
        "shared_observation": "",
    }


def next_work_item_index(correction: dict) -> int:
    highest = 0
    for work_item in correction.get("work_items", []):
        match = re.search(r"(\d+)$", str(work_item.get("id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def work_item_for_student(index: int, student_name: str) -> dict:
    work_item = make_work_item(index)
    work_item["student_name"] = student_name
    return work_item


def ensure_work_item_for_phase(work_item: dict, template: dict, phase: str) -> None:
    phase_data = work_item.setdefault(
        phase,
        {
            "grade": 0,
            "delivery_stage": "Regular",
            "corrected": False,
            "selected_comments": {},
            "header_comments": [],
            "footer_comments": [],
        },
    )
    phase_data.setdefault("grade", 0)
    phase_data.setdefault("delivery_stage", "Regular")
    phase_data.setdefault("corrected", False)
    phase_data.setdefault("selected_comments", {})
    phase_data.setdefault("header_comments", [])
    phase_data.setdefault("footer_comments", [])

    for criterion_id, defaults in selected_comments_for_template(template).items():
        selected = phase_data["selected_comments"].setdefault(criterion_id, defaults)
        if isinstance(selected, str):
            phase_data["selected_comments"][criterion_id] = [selected]
        elif not isinstance(selected, list):
            phase_data["selected_comments"][criterion_id] = list(defaults)


def ensure_correction_integrity(data: dict, correction: dict) -> None:
    templates_by_phase = {
        "phase1": find_template(data, correction["phase1_template_id"]),
        "phase2": find_template(data, correction["phase2_template_id"]),
    }
    correction.setdefault("work_items", [])
    for work_item in correction.get("work_items", []):
        work_item.setdefault("student_name", "")
        work_item.setdefault("shared_observation", "")
        for phase, template in templates_by_phase.items():
            if template and phase in work_item:
                ensure_work_item_for_phase(work_item, template, phase)


def choose_folder_dialog() -> str:
    if sys.platform.startswith("win"):
        command = [
            "powershell",
            "-NoProfile",
            "-STA",
            "-Command",
            (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$form = New-Object System.Windows.Forms.Form;"
                "$form.TopMost = $true;"
                "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$dialog.ShowNewFolderButton = $true;"
                "if ($dialog.ShowDialog($form) -eq [System.Windows.Forms.DialogResult]::OK) {"
                "  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
                "  Write-Output $dialog.SelectedPath;"
                "}"
            ),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            return result.stdout.strip()
        except Exception:
            pass

    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return ""

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory()
    root.destroy()
    return selected or ""


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Não foi possível criar um nome único para {path.name}.")


def safe_flattened_name(filename: str) -> str:
    name = PurePosixPath(filename).name.strip()
    if not name or name in {".", ".."}:
        return ""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name)


def convert_word_to_pdf(word_file: Path, pdf_file: Path) -> tuple[bool, str]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$ErrorActionPreference = 'Stop';"
            "$word = New-Object -ComObject Word.Application;"
            "$word.Visible = $false;"
            "$word.DisplayAlerts = 0;"
            "try {"
            f"$doc = $word.Documents.Open({json.dumps(str(word_file))});"
            f"$doc.SaveAs([ref]{json.dumps(str(pdf_file))}, [ref]17);"
            "$doc.Close($false);"
            "} finally { $word.Quit(); }"
        ),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except Exception as error:
        return False, str(error)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "Falha ao converter arquivo Word.").strip()
    return True, ""


def import_zip_students(data: dict, correction: dict, source_dir: Path, destination_dir: Path, phase: str) -> dict:
    if phase not in {"phase1", "phase2"}:
        raise ValueError("Fase inválida.")
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError("A pasta de origem não existe.")
    destination_dir.mkdir(parents=True, exist_ok=True)
    data_dir = destination_dir / "dados"
    pdf_dir = destination_dir / "pdf"
    python_dir = destination_dir / "python"
    data_dir.mkdir(exist_ok=True)
    pdf_dir.mkdir(exist_ok=True)

    zip_files = sorted(source_dir.glob("*.zip"))
    loose_pdf_files = sorted(source_dir.glob("*.pdf"))
    imported_students = []
    copied_pdfs = 0
    copied_python = 0
    converted_word = 0
    conversion_errors = []

    for zip_path in zip_files:
        student_folder_name = safe_flattened_name(zip_path.stem) or slug(zip_path.stem)
        student_name = zip_path.stem.replace("_", " ").strip()
        if not student_name:
            continue
        imported_students.append(student_name)
        student_dir = data_dir / student_folder_name
        student_dir.mkdir(exist_ok=True)

        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                filename = safe_flattened_name(member.filename)
                if not filename:
                    continue
                target = unique_path(student_dir / filename)
                with archive.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)

        for extracted_file in student_dir.iterdir():
            if not extracted_file.is_file():
                continue
            suffix = extracted_file.suffix.lower()
            if suffix == ".pdf":
                shutil.copy2(extracted_file, unique_path(pdf_dir / extracted_file.name))
                copied_pdfs += 1
            elif suffix in {".doc", ".docx"}:
                pdf_target = unique_path(pdf_dir / f"{extracted_file.stem}.pdf")
                ok, error = convert_word_to_pdf(extracted_file, pdf_target)
                if ok:
                    converted_word += 1
                else:
                    conversion_errors.append(f"{extracted_file.name}: {error}")
            elif suffix == ".py":
                python_dir.mkdir(exist_ok=True)
                shutil.copy2(extracted_file, unique_path(python_dir / extracted_file.name))
                copied_python += 1

    for pdf_path in loose_pdf_files:
        student_folder_name = safe_flattened_name(pdf_path.stem) or slug(pdf_path.stem)
        student_name = pdf_path.stem.replace("_", " ").strip()
        if not student_name:
            continue
        imported_students.append(student_name)
        student_dir = data_dir / student_folder_name
        student_dir.mkdir(exist_ok=True)
        copied_to_data = unique_path(student_dir / pdf_path.name)
        shutil.copy2(pdf_path, copied_to_data)
        shutil.copy2(copied_to_data, unique_path(pdf_dir / copied_to_data.name))
        copied_pdfs += 1

    existing_by_name = {
        item.get("student_name", "").strip().casefold(): item
        for item in correction.get("work_items", [])
        if item.get("student_name", "").strip()
    }
    blank_items = [
        item for item in correction.get("work_items", [])
        if not item.get("student_name", "").strip()
    ]
    next_index = next_work_item_index(correction)
    added_students = 0
    reused_blank_slots = 0

    for student_name in imported_students:
        key = student_name.casefold()
        work_item = existing_by_name.get(key)
        if work_item is None:
            if blank_items:
                work_item = blank_items.pop(0)
                work_item["student_name"] = student_name
                reused_blank_slots += 1
            else:
                work_item = work_item_for_student(next_index, student_name)
                correction.setdefault("work_items", []).append(work_item)
                next_index += 1
            existing_by_name[key] = work_item
        newly_enrolled = phase not in work_item
        template_id = correction[f"{phase}_template_id"]
        template = find_template(data, template_id)
        if template:
            ensure_work_item_for_phase(work_item, template, phase)
        if newly_enrolled:
            added_students += 1

    correction["student_count"] = len(correction.get("work_items", []))
    ensure_correction_integrity(data, correction)
    return {
        "zip_count": len(zip_files),
        "loose_pdf_count": len(loose_pdf_files),
        "students": imported_students,
        "added_students": added_students,
        "reused_blank_slots": reused_blank_slots,
        "copied_pdfs": copied_pdfs,
        "converted_word": converted_word,
        "copied_python": copied_python,
        "conversion_errors": conversion_errors,
        "data_dir": str(data_dir),
        "pdf_dir": str(pdf_dir),
        "python_dir": str(python_dir) if python_dir.exists() else "",
    }


class AppHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        clean_path = unquote(urlparse(path).path)
        if clean_path == "/":
            return str(STATIC / "index.html")
        return str(ROOT / clean_path.lstrip("/"))

    def log_message(self, format: str, *args) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), format % args))

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/state":
            data = load_data()
            for correction in data["corrections"]:
                ensure_correction_integrity(data, correction)
            save_data(data)
            self.send_json(data)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = load_data()
        payload = self.read_json()

        if path == "/api/select-folder":
            self.send_json({"path": choose_folder_dialog()})
            return

        if path == "/api/templates":
            template = normalize_template(payload)
            if not template["id"]:
                self.send_json({"error": "Identificador obrigatório."}, HTTPStatus.BAD_REQUEST)
                return
            if find_template(data, template["id"]):
                self.send_json({"error": "Já existe um template com esse identificador."}, HTTPStatus.CONFLICT)
                return
            data["templates"].append(template)
            save_data(data)
            self.send_json(template, HTTPStatus.CREATED)
            return

        if path == "/api/corrections":
            correction_id = slug(str(payload.get("id", "")))
            phase1 = str(payload.get("phase1_template_id", ""))
            phase2 = str(payload.get("phase2_template_id", ""))
            if not correction_id or find_correction(data, correction_id):
                self.send_json({"error": "Identificador inválido ou já usado."}, HTTPStatus.BAD_REQUEST)
                return
            if not find_template(data, phase1) or not find_template(data, phase2):
                self.send_json({"error": "Selecione templates válidos para as duas fases."}, HTTPStatus.BAD_REQUEST)
                return
            correction = {
                "id": correction_id,
                "phase1_template_id": phase1,
                "phase2_template_id": phase2,
                "student_count": max(int(payload.get("student_count") or 0), 0),
                "work_items": [],
            }
            ensure_correction_integrity(data, correction)
            data["corrections"].append(correction)
            save_data(data)
            self.send_json(correction, HTTPStatus.CREATED)
            return

        if path.startswith("/api/corrections/") and path.endswith("/import-zips"):
            correction_id = path.split("/")[3]
            correction = find_correction(data, correction_id)
            if not correction:
                self.send_json({"error": "Correção não encontrada."}, HTTPStatus.NOT_FOUND)
                return
            try:
                phase = str(payload.get("phase", ""))
                if phase not in {"phase1", "phase2"}:
                    self.send_json({"error": "Selecione uma fase válida."}, HTTPStatus.BAD_REQUEST)
                    return
                if not find_template(data, correction.get(f"{phase}_template_id", "")):
                    self.send_json({"error": "A fase selecionada não possui um template configurado."}, HTTPStatus.BAD_REQUEST)
                    return
                summary = import_zip_students(
                    data,
                    correction,
                    Path(str(payload.get("source_dir", ""))),
                    Path(str(payload.get("destination_dir", ""))),
                    phase,
                )
            except (ValueError, zipfile.BadZipFile, OSError) as error:
                self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            save_data(data)
            self.send_json(summary)
            return

        if path.startswith("/api/templates/") and path.endswith("/comments"):
            template_id = path.split("/")[3]
            template = find_template(data, template_id)
            if not template:
                self.send_json({"error": "Template não encontrado."}, HTTPStatus.NOT_FOUND)
                return
            area = payload.get("area")
            comment = {"id": str(payload.get("id", "")).strip(), "message": str(payload.get("message", "")).strip()}
            if not comment["id"] or not comment["message"]:
                self.send_json({"error": "Identificador e mensagem são obrigatórios."}, HTTPStatus.BAD_REQUEST)
                return
            if area == "criterion":
                criterion_id = payload.get("criterion_id")
                criterion = next((item for item in template["criteria"] if item["id"] == criterion_id), None)
                if not criterion:
                    self.send_json({"error": "Critério não encontrado."}, HTTPStatus.NOT_FOUND)
                    return
                criterion["comments"].append(comment)
            elif area == "header":
                template["header_comments"].append(comment)
            elif area == "footer":
                template["footer_comments"].append(comment)
            else:
                self.send_json({"error": "Área inválida."}, HTTPStatus.BAD_REQUEST)
                return
            save_data(data)
            self.send_json(template)
            return

        if path.startswith("/api/corrections/") and path.endswith("/work-items"):
            correction_id = path.split("/")[3]
            correction = find_correction(data, correction_id)
            if not correction:
                self.send_json({"error": "Correção não encontrada."}, HTTPStatus.NOT_FOUND)
                return
            ensure_correction_integrity(data, correction)
            work_item = make_work_item(next_work_item_index(correction))
            correction["work_items"].append(work_item)
            correction["student_count"] = len(correction["work_items"])
            ensure_correction_integrity(data, correction)
            save_data(data)
            self.send_json(work_item, HTTPStatus.CREATED)
            return

        self.send_json({"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        data = load_data()

        if path.startswith("/api/corrections/"):
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[0] == "api" and parts[1] == "corrections" and parts[3] == "work-items":
                correction = find_correction(data, parts[2])
                if not correction:
                    self.send_json({"error": "Correção não encontrada."}, HTTPStatus.NOT_FOUND)
                    return
                ensure_correction_integrity(data, correction)
                original_count = len(correction["work_items"])
                correction["work_items"] = [
                    item for item in correction["work_items"] if item["id"] != parts[4]
                ]
                if len(correction["work_items"]) == original_count:
                    self.send_json({"error": "Aluno não encontrado."}, HTTPStatus.NOT_FOUND)
                    return
                correction["student_count"] = len(correction["work_items"])
                save_data(data)
                self.send_json({"ok": True})
                return

        self.send_json({"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        data = load_data()
        payload = self.read_json()

        if path.startswith("/api/templates/"):
            template_id = path.split("/")[3]
            current = find_template(data, template_id)
            if not current:
                self.send_json({"error": "Template não encontrado."}, HTTPStatus.NOT_FOUND)
                return
            updated = normalize_template({**current, **payload, "id": template_id})
            current.update(updated)
            save_data(data)
            self.send_json(current)
            return

        if path.startswith("/api/corrections/"):
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[0] == "api" and parts[1] == "corrections" and parts[3] == "work-items":
                correction = find_correction(data, parts[2])
                if not correction:
                    self.send_json({"error": "Correção não encontrada."}, HTTPStatus.NOT_FOUND)
                    return
                ensure_correction_integrity(data, correction)
                work_item = next((item for item in correction["work_items"] if item["id"] == parts[4]), None)
                if not work_item:
                    self.send_json({"error": "Trabalho não encontrado."}, HTTPStatus.NOT_FOUND)
                    return
                work_item.update(payload)
                ensure_correction_integrity(data, correction)
                save_data(data)
                self.send_json(work_item)
                return

        self.send_json({"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)


def main() -> None:
    STATIC.mkdir(exist_ok=True)
    load_data()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), AppHandler)
    print(f"Servidor iniciado em http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
