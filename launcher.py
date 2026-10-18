"""First-run launcher for the Echo desktop application."""

import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
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


def command_output(command: list[str], cwd: Path | None = None, timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=cwd)
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
    global POSTGRES_PORT
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    env_file = DATA_DIR / ".env"
    if not env_file.exists():
        template = Path(__file__).resolve().parent / ".env.example"
        if template.is_file():
            contents = template.read_text(encoding="utf-8")
        else:
            contents = (
                "POSTGRES_USER=teamreport\n"
                "POSTGRES_PASSWORD=change-me-strong\n"
                "POSTGRES_DB=teamreport\n"
                "POSTGRES_PORT=5432\n"
                "DATABASE_URL=postgresql://teamreport:change-me-strong@localhost:5432/teamreport\n"
                "OLLAMA_URL=http://localhost:11434/api/generate\n"
                "OLLAMA_MODEL=qwen3:1.7b\n"
            )
        code, secret = command_output(["openssl", "rand", "-hex", "32"])
        if code != 0 or not secret:
            raise RuntimeError("OpenSSL is required to generate the Echo database password.")
        contents = contents.replace("POSTGRES_PASSWORD=change-me-strong", f"POSTGRES_PASSWORD={secret}")
        contents = contents.replace(
            "DATABASE_URL=postgresql://teamreport:change-me-strong@localhost:5432/teamreport",
            f"DATABASE_URL=postgresql://teamreport:{secret}@localhost:{POSTGRES_PORT}/teamreport",
        )
        env_file.write_text(contents, encoding="utf-8")
        env_file.chmod(0o600)
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("POSTGRES_PORT="):
            POSTGRES_PORT = int(line.partition("=")[2].strip())
            break
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


def database_port_details() -> str:
    details = []
    port = str(POSTGRES_PORT)
    code, containers = command_output(
        ["docker", "ps", "--filter", f"publish={port}", "--format", "{{.Names}}"]
    )
    if code == 0 and containers:
        details.append("Docker containers: " + containers)
    for command in ((["ss", "-ltnp", "sport", "=", f":{port}"]), (["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"])):
        if shutil.which(command[0]):
            code, output = command_output(command)
            if code == 0 and output:
                details.append(output)
                break
    return "\n".join(details) or "The process could not be identified."


def database_port_is_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", POSTGRES_PORT), timeout=0.5):
            own_code, own_container = command_output([
                "docker", "ps", "--filter", "label=com.docker.compose.project=echo",
                "--filter", "label=com.docker.compose.service=db", "--format", "{{.Names}}",
            ])
            if own_code == 0 and own_container:
                return True
            show_error(
                "PostgreSQL port is already in use",
                f"Echo needs host port {POSTGRES_PORT}, but another process or container is using it.\n\n"
                f"{database_port_details()}\n\nStop that application or configure Echo with another POSTGRES_PORT, then try again."
            )
            return False
    except OSError:
        return True


class PostgresStartupWorker(QObject):
    progress = Signal(int)
    message = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, compose: list[str], env_file: Path, compose_file: Path) -> None:
        super().__init__()
        self.compose = compose
        self.env_file = env_file
        self.compose_file = compose_file

    def compose_base_command(self) -> list[str]:
        return self.compose + [
            "--env-file", str(self.env_file), "-f", str(self.compose_file), "-p", "echo",
        ]

    def diagnostics(self) -> str:
        base = self.compose_base_command()
        _, status = command_output(base + ["ps"])
        _, logs = command_output(base + ["logs", "--tail", "100", "db"])
        return f"Compose status:\n{status[-800:]}\n\nPostgreSQL logs:\n{logs[-1200:]}"

    def health_status(self) -> str:
        code, output = command_output(self.compose_base_command() + ["ps", "-q", "db"])
        container_id = output.splitlines()[-1].strip() if code == 0 and output else ""
        if not container_id:
            return ""
        code, output = command_output(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id]
        )
        return output.strip() if code == 0 else ""

    def failure_message(self, details: str, timed_out: bool = False) -> str:
        lowered = details.lower()
        if timed_out or "timed out" in lowered or "timeout" in lowered:
            category = "Docker timed out while downloading or starting PostgreSQL."
        elif "permission denied" in lowered or "permission" in lowered or "docker.sock" in lowered:
            category = "Docker permission error. Add your user to the docker group or start Echo with Docker access."
        elif "address already in use" in lowered or "port is already allocated" in lowered:
            category = f"PostgreSQL port {POSTGRES_PORT} is already in use."
        else:
            category = "PostgreSQL did not become healthy."
        return f"{category}\n\n{details[-2200:]}"

    def run(self) -> None:
        base = self.compose_base_command()
        if self.health_status() == "healthy":
            self.message.emit("Echo's PostgreSQL database is already healthy.")
            self.finished.emit(True, "")
            return

        self.message.emit("Starting PostgreSQL. The first launch may take several minutes.")
        command = base + ["up", "-d", "db"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=300, cwd=self.compose_file.parent)
            details = (result.stdout + result.stderr).strip()
            if result.returncode != 0:
                self.finished.emit(False, self.failure_message(details + "\n\n" + self.diagnostics()))
                return
        except subprocess.TimeoutExpired as exc:
            details = (exc.stdout or "") + (exc.stderr or "")
            self.finished.emit(False, self.failure_message(details + "\n\n" + self.diagnostics(), timed_out=True))
            return
        except (FileNotFoundError, OSError) as exc:
            self.finished.emit(False, self.failure_message(str(exc) + "\n\n" + self.diagnostics()))
            return

        for attempt in range(60):
            health = self.health_status()
            self.progress.emit(attempt + 1)
            if health == "healthy":
                self.finished.emit(True, "")
                return
            time.sleep(2)
        self.finished.emit(False, self.failure_message(self.diagnostics()))


def start_postgres(compose: list[str], env_file: Path) -> bool:
    compose_file = DATA_DIR / "docker-compose.yml"
    if not compose_file.is_file():
        compose_file = resource_path("docker-compose.yml")
    if not database_port_is_available():
        return False

    progress = QProgressDialog("Starting PostgreSQL. The first launch may take several minutes.", "Cancel", 0, 60)
    progress.setWindowTitle("Starting Echo")
    progress.setAutoClose(False)
    progress.setValue(0)
    progress.show()
    thread = QThread()
    worker = PostgresStartupWorker(compose, env_file, compose_file)
    result: list[tuple[bool, str]] = []
    worker.progress.connect(progress.setValue)
    worker.message.connect(progress.setLabelText)
    worker.finished.connect(lambda ready, details: result.append((ready, details)))
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    thread.start()
    while thread.isRunning():
        QApplication.processEvents()
        if progress.wasCanceled():
            progress.setLabelText("Waiting for PostgreSQL startup to finish...")
        time.sleep(0.05)
    ready, details = result[0] if result else (False, "PostgreSQL startup stopped unexpectedly.")
    progress.close()
    if not ready:
        show_error("PostgreSQL startup failed", details)
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