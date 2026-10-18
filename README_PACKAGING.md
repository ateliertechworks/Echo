# Echo Linux release packaging

Echo is a PySide6 desktop application. The release installer supports Ubuntu
Linux amd64 (`x86_64`) only. Docker runs PostgreSQL, and Ollama downloads the
`qwen3:1.7b` model locally during installation or first launch.

## Create the release package

From the repository root, build and package Echo:

```bash
chmod +x create-release-package.sh
./create-release-package.sh
```

The script runs `build_linux.sh`, checks every required input, creates:

- `Echo-Linux-Installer.tar.gz`
- `SHA256SUMS`

The archive contains the complete `dist/Echo` PyInstaller onedir tree, installer,
production Docker Compose file, desktop entry, migrations, assets, `.env.example`,
and this documentation. The installed executable is
`~/.local/share/Echo/Echo/Echo`. It does not
include `.env`, passwords, database files, logs, `__pycache__`, `.git`, or
development virtual environments. The script never uploads or publishes files.

## Publish a GitHub release

Create a GitHub Release and upload exactly these two files:

```text
Echo-Linux-Installer.tar.gz
SHA256SUMS
```

Choose a release tag, for example `v1.0.2`. The tag must match the `ECHO_RELEASE_VERSION`
value in `install-echo.sh`.

## Configure the one-line installer

At the top of `install-echo.sh`, replace:

```bash
OWNER="OWNER"
REPOSITORY="REPOSITORY"
ECHO_RELEASE_VERSION="v1.0.2"
```

with the GitHub owner, repository name, and release tag. For example:

```bash
OWNER="harsha"
REPOSITORY="Echo"
ECHO_RELEASE_VERSION="v1.0.2"
```

Commit and push `install-echo.sh` after changing these values. Do not publish a
release until `create-release-package.sh` has generated both release files.

## User installation

After `install-echo.sh` is available on the repository's `main` branch, users
run this one command from a normal, non-root Ubuntu amd64 account:

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/REPOSITORY/main/install-echo.sh | bash
```

The bootstrap checks Ubuntu and amd64, verifies `curl`, `tar`, and `sha256sum`,
downloads the archive and checksum file from the specified GitHub Release,
verifies the archive before extracting it, and runs the main installer. The
main installer asks for `sudo` only when it needs to install system packages
or configure services.

## Test on a clean Ubuntu machine

Use a fresh Ubuntu amd64 virtual machine or another clean machine. Make sure
the machine has network access, then run the one-line command above. Confirm
that the installer:

1. Installs Docker and Docker Compose when missing.
2. Installs or upgrades Ollama to a Qwen3-compatible version.
3. Downloads `qwen3:1.7b`.
4. Creates the Echo application launcher.
5. Starts Echo from the applications menu.

For a syntax-only check before publishing:

```bash
bash -n install-echo.sh
bash -n create-release-package.sh
bash -n Echo_Linux_Installer.sh
```

## Uninstall Echo

Stop and remove Echo's PostgreSQL container, then remove Echo's installed
files and desktop launcher:

```bash
cd ~/.local/share/Echo
docker compose down -v
rm -rf ~/.local/share/Echo ~/.local/share/applications/echo.desktop
```

Ollama, Docker, and the downloaded Ollama model are shared system resources and
are not removed by this command. Remove them separately only if no other
application needs them.
