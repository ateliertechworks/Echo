"""First-run launcher for the Echo desktop application."""

import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog


APP_NAME = "Echo"
DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
LOG_DIR = DATA_DIR / "logs"
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / relative


def show_error(title: str, text: str) -> None:
    QMessageBox.critical(None, title, text)


def command_output(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 1, str(exc)
    return result.returncode, (result.stdout + result.stderr).strip()


def compose_command() -> list[str] | None:
    if shutil.which("docker"):
        code, _ = command_output(["docker", "compose", "version"])
        if code == 0:
            return ["docker", "compose"]
    if shutil.which("docker-compose"):
        code, _ = command_output(["docker-compose", "version"])
        if code == 0:
            return ["docker-compose"]
    return None


def ensure_runtime_files() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    env_file = DATA_DIR / ".env"
    if not env_file.exists():
        env_file.write_text(
            "POSTGRES_USER=teamreport\n"
            "POSTGRES_PASSWORD=change-me-strong\n"
            "POSTGRES_DB=teamreport\n"
            f"POSTGRES_PORT={POSTGRES_PORT}\n"
            f"DATABASE_URL=postgresql://teamreport:change-me-strong@localhost:{POSTGRES_PORT}/teamreport\n"
            "OLLAMA_URL=http://localhost:11434/api/generate\n"
            f"OLLAMA_MODEL={MODEL}\n",
            encoding="utf-8",
        )
    os.environ["ECHO_DATA_DIR"] = str(DATA_DIR)
    os.environ["POSTGRES_PORT"] = str(POSTGRES_PORT)
    return env_file


def check_docker() -> list[str] | None:
    if not shutil.which("docker") and not shutil.which("docker-compose"):
        show_error(
            "Docker is required",
            "Echo needs Docker to run PostgreSQL. Install Docker Desktop or Docker Engine, then launch Echo again.",
        )
        return None
    compose = compose_command()
    if compose is None:
        show_error(
            "Docker Compose is unavailable",
            "Docker is installed, but Docker Compose is not available. Install the Docker Compose plugin and try again.",
        )
        return None
    code, details = command_output(["docker", "info"])
    if code != 0:
        show_error(
            "Docker is not running",
            "Start Docker, wait until it is ready, and then open Echo again.\n\n"
            f"Docker reported: {details[-400:]}",
        )
        return None
    return compose


def start_postgres(compose: list[str], env_file: Path) -> bool:
    command = compose + [
        "--env-file", str(env_file), "-f", str(resource_path("docker-compose.yml")),
        "-p", "echo", "up", "-d", "db",
    ]
    code, details = command_output(command)
    if code != 0:
        show_error("PostgreSQL could not start", f"Docker Compose failed:\n\n{details[-1200:]}")
        return False

    progress = QProgressDialog("Waiting for PostgreSQL to become ready...", "Cancel", 0, 60)
    progress.setWindowTitle("Starting Echo")
    progress.setAutoClose(False)
    progress.setValue(0)
    progress.show()
    ready = False
    for attempt in range(60):
        QApplication.processEvents()
        if progress.wasCanceled():
            break
        try:
            with socket.create_connection(("127.0.0.1", POSTGRES_PORT), timeout=1):
                ready = True
                break
        except OSError:
            time.sleep(1)
            progress.setValue(attempt + 1)
    progress.close()
    if not ready:
        show_error("PostgreSQL is not ready", "Echo could not connect to PostgreSQL on localhost. Check Docker and try again.")
    return ready


def ensure_model() -> bool:
    if not shutil.which("ollama"):
        show_error(
            "Ollama is required",
            "Echo needs Ollama for its local Qwen model. Install Ollama, start it, and then open Echo again.",
        )
        return False
    code, details = command_output(["ollama", "list"])
    if code != 0:
        show_error("Ollama is not running", "Start Ollama and then open Echo again.\n\n" + details[-400:])
        return False
    if any(line.split()[0] == MODEL for line in details.splitlines()[1:] if line.split()):
        return True
    answer = QMessageBox.question(
        None, "Download Qwen model?",
        f"The local model {MODEL} is not installed. Download it through Ollama now?\n\n"
        "The download may be several gigabytes.",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
    )
    if answer != QMessageBox.Yes:
        return False
    progress = QProgressDialog("Downloading Qwen model...", "Cancel", 0, 0)
    progress.setWindowTitle("Setting up Echo")
    progress.setAutoClose(False)
    progress.show()
    process = subprocess.Popen(
        ["ollama", "pull", MODEL], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    last_line = "Downloading Qwen model..."
    while process.poll() is None:
        QApplication.processEvents()
        if progress.wasCanceled():
            process.terminate()
            process.wait(timeout=5)
            progress.close()
            return False
        if process.stdout:
            line = process.stdout.readline().strip()
            if line:
                last_line = line
                progress.setLabelText(last_line)
    progress.close()
    if process.returncode != 0:
        show_error("Qwen model download failed", last_line)
        return False
    return True


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_DIR / "echo.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    env_file = ensure_runtime_files()
    compose = check_docker()
    if compose is None or not start_postgres(compose, env_file) or not ensure_model():
        return 1
    logging.info("Runtime checks completed; starting Echo frontend")
    from echo_app.app import main as frontend_main

    frontend_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())