import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
PROJECTS_FILE = ROOT / "data" / "projects.json"
PROJECT_IMAGES = ROOT / "images" / "projects"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_IMAGE_BYTES + 32 * 1024
ADMIN_PASSWORD = os.environ.get("TEAK_ADMIN_PASSWORD", "")
HOST = os.environ.get("TEAK_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", os.environ.get("TEAK_PORT", "8000")))
ALLOWED_CATEGORIES = {
    "Home renovation",
    "Office renovation",
    "Office design",
    "Interior design",
    "Flooring",
    "Repairs",
    "Construction",
}
IMAGE_FORMATS = {
    "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": (
        ".webp",
        lambda data: len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP",
    ),
    "image/gif": (".gif", lambda data: data.startswith((b"GIF87a", b"GIF89a"))),
}
SESSION_KEY = hashlib.sha256(
    (ADMIN_PASSWORD or secrets.token_urlsafe(32)).encode("utf-8")
).digest()


def load_projects():
    if not PROJECTS_FILE.exists():
        return []
    with PROJECTS_FILE.open("r", encoding="utf-8") as file:
        projects = json.load(file)
    if not isinstance(projects, list):
        raise ValueError("Project gallery data must be a JSON list.")
    return projects


def save_projects(projects):
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = PROJECTS_FILE.with_suffix(".json.tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(projects, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary_file, PROJECTS_FILE)


def signed_session():
    expiry = str(int(datetime.now(timezone.utc).timestamp()) + 8 * 60 * 60)
    signature = hmac.new(SESSION_KEY, expiry.encode("ascii"), hashlib.sha256).hexdigest()
    return expiry, signature


class WebsiteHandler(SimpleHTTPRequestHandler):
    server_version = "TeakLocalPreview"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' https://images.unsplash.com blob: data:; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        content_length = self.request_length()
        if content_length > 4096:
            raise ValueError("Request is too large.")
        data = json.loads(self.rfile.read(content_length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object.")
        return data

    def request_length(self):
        value = self.headers.get("Content-Length", "")
        if not value.isdigit():
            raise ValueError("A valid Content-Length header is required.")
        return int(value)

    def is_local_request(self):
        address = self.client_address[0]
        return address in ("127.0.0.1", "::1")

    def has_valid_session(self):
        if not ADMIN_PASSWORD and self.is_local_request():
            return True

        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        cookie = cookies.get("teak_admin")
        if cookie is None:
            return False

        try:
            expiry, signature = cookie.value.split(".", 1)
            if not expiry.isdigit() or int(expiry) < int(datetime.now(timezone.utc).timestamp()):
                return False
            expected = hmac.new(SESSION_KEY, expiry.encode("ascii"), hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature, expected)
        except (ValueError, OverflowError):
            return False

    def same_origin_request(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if not origin or not host:
            return False
        parsed_origin = urlsplit(origin)
        forwarded_proto = self.headers.get("X-Forwarded-Proto", "")
        expected_scheme = forwarded_proto if forwarded_proto in ("http", "https") else "http"
        return parsed_origin.scheme == expected_scheme and parsed_origin.netloc == host

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/projects":
            try:
                self.send_json(200, load_projects())
            except (OSError, ValueError, json.JSONDecodeError):
                self.send_json(500, {"error": "The project gallery could not be loaded."})
            return

        if path == "/api/admin/session":
            self.send_json(200, {"authenticated": self.has_valid_session()})
            return

        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/admin/login":
            self.handle_login()
            return
        if path == "/api/projects":
            self.handle_create_project()
            return
        self.send_json(404, {"error": "Not found."})

    def do_PUT(self):
        project_id = self.project_id_from_path()
        if project_id is None:
            self.send_json(404, {"error": "Not found."})
            return
        self.handle_update_project(project_id)

    def do_DELETE(self):
        project_id = self.project_id_from_path()
        if project_id is None:
            self.send_json(404, {"error": "Not found."})
            return
        if not self.authorize_mutation():
            return

        try:
            projects = load_projects()
            remaining = [project for project in projects if project.get("id") != project_id]
            if len(remaining) == len(projects):
                self.send_json(404, {"error": "Project not found."})
                return
            removed = next(project for project in projects if project.get("id") == project_id)
            save_projects(remaining)
            self.remove_managed_image(removed.get("image", ""))
            self.send_json(200, {"projects": remaining})
        except (OSError, ValueError, json.JSONDecodeError):
            self.send_json(500, {"error": "The project could not be deleted."})

    def project_id_from_path(self):
        match = re.fullmatch(r"/api/projects/([0-9a-f-]{36})", urlsplit(self.path).path)
        return match.group(1) if match else None

    def handle_login(self):
        if not self.same_origin_request():
            self.send_json(403, {"error": "Login must come from this site."})
            return
        try:
            data = self.read_json()
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Enter a valid password."})
            return

        if ADMIN_PASSWORD:
            valid_password = isinstance(data.get("password"), str) and hmac.compare_digest(
                data["password"], ADMIN_PASSWORD
            )
        else:
            valid_password = self.is_local_request()
        if not valid_password:
            self.send_json(401, {"error": "The password is incorrect."})
            return

        expiry, signature = signed_session()
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        self.send_json_with_cookie(
            200,
            {"authenticated": True},
            f"teak_admin={expiry}.{signature}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800{secure}",
        )

    def send_json_with_cookie(self, status, value, cookie):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorize_mutation(self):
        if not self.same_origin_request():
            self.send_json(403, {"error": "This request must come from the site."})
            return False
        if not self.has_valid_session():
            self.send_json(401, {"error": "Sign in to manage project photos."})
            return False
        return True

    def read_project_upload(self):
        content_length = self.request_length()
        if content_length > MAX_REQUEST_BYTES:
            raise ValueError("Each image must be smaller than 10 MB.")

        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data;"):
            raise ValueError("Choose an image and enter its project details.")

        raw_message = (
            b"MIME-Version: 1.0\r\nContent-Type: "
            + content_type.encode("latin-1")
            + b"\r\n\r\n"
            + self.rfile.read(content_length)
        )
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        if not message.is_multipart():
            raise ValueError("The uploaded form is invalid.")

        fields = {}
        image_bytes = None
        image_type = None
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            payload = part.get_payload(decode=True) or b""
            if name == "image":
                image_bytes = payload
                image_type = part.get_content_type().lower()
            elif name in ("title", "category", "description"):
                fields[name] = payload.decode("utf-8").strip()

        if not fields.get("title") or len(fields["title"]) > 100:
            raise ValueError("Enter a project title of 1–100 characters.")
        if fields.get("category") not in ALLOWED_CATEGORIES:
            raise ValueError("Choose a valid project category.")
        if len(fields.get("description", "")) > 500:
            raise ValueError("Keep the description under 500 characters.")
        if image_bytes is not None:
            image_format = IMAGE_FORMATS.get(image_type)
            if image_format is None or not image_format[1](image_bytes):
                raise ValueError("Use a valid JPEG, PNG, WebP, or GIF image.")
            if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
                raise ValueError("Each image must be between 1 byte and 10 MB.")
            fields["image_bytes"] = image_bytes
            fields["image_extension"] = image_format[0]
        return fields

    def handle_create_project(self):
        if not self.authorize_mutation():
            return
        image_path = None
        try:
            fields = self.read_project_upload()
            if "image_bytes" not in fields:
                raise ValueError("Choose a project image to upload.")
            PROJECT_IMAGES.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid.uuid4().hex}{fields['image_extension']}"
            image_path = PROJECT_IMAGES / filename
            image_path.write_bytes(fields["image_bytes"])
            project = {
                "id": str(uuid.uuid4()),
                "title": fields["title"],
                "category": fields["category"],
                "description": fields.get("description", ""),
                "image": f"images/projects/{filename}",
                "alt": fields["title"],
                "placeholder": False,
            }
            projects = [project] + load_projects()
            save_projects(projects)
            self.send_json(201, {"project": project})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            if image_path is not None:
                image_path.unlink(missing_ok=True)
            self.send_json(400, {"error": str(error)})
        except OSError:
            if image_path is not None:
                image_path.unlink(missing_ok=True)
            self.send_json(500, {"error": "The project image could not be saved."})

    def handle_update_project(self, project_id):
        if not self.authorize_mutation():
            return
        new_image_path = None
        try:
            fields = self.read_project_upload()
            projects = load_projects()
            project = next((item for item in projects if item.get("id") == project_id), None)
            if project is None:
                self.send_json(404, {"error": "Project not found."})
                return

            old_image = project.get("image", "")
            project.update(
                {
                    "title": fields["title"],
                    "category": fields["category"],
                    "description": fields.get("description", ""),
                    "alt": fields["title"],
                    "placeholder": False,
                }
            )
            if "image_bytes" in fields:
                PROJECT_IMAGES.mkdir(parents=True, exist_ok=True)
                filename = f"{uuid.uuid4().hex}{fields['image_extension']}"
                new_image_path = PROJECT_IMAGES / filename
                new_image_path.write_bytes(fields["image_bytes"])
                project["image"] = f"images/projects/{filename}"

            save_projects(projects)
            if project.get("image") != old_image:
                self.remove_managed_image(old_image)
            self.send_json(200, {"project": project})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            if new_image_path is not None:
                new_image_path.unlink(missing_ok=True)
            self.send_json(400, {"error": str(error)})
        except OSError:
            if new_image_path is not None:
                new_image_path.unlink(missing_ok=True)
            self.send_json(500, {"error": "The project could not be updated."})

    @staticmethod
    def remove_managed_image(image):
        if not isinstance(image, str) or not image.startswith("images/projects/"):
            return
        filename = image.removeprefix("images/projects/")
        if filename and Path(filename).name == filename:
            (PROJECT_IMAGES / filename).unlink(missing_ok=True)

    def log_message(self, format_string, *args):
        super().log_message(format_string, *args)


if not ADMIN_PASSWORD and HOST not in ("127.0.0.1", "localhost", "::1"):
    raise SystemExit(
        "Set TEAK_ADMIN_PASSWORD to a strong password before exposing the gallery manager."
    )

try:
    load_projects()
except (OSError, ValueError, json.JSONDecodeError) as error:
    raise SystemExit(f"Could not load data/projects.json: {error}") from error

with ThreadingHTTPServer((HOST, PORT), WebsiteHandler) as server:
    print(f"Teak Flooring & Interiors is available at http://{HOST}:{PORT}")
    if not ADMIN_PASSWORD:
        print("Gallery uploads are enabled for this computer only.")
    server.serve_forever()
