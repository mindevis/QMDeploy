"""Создание Secret docker-registry ghcr-credentials для pull образов с ghcr.io (Cloud)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from k8s_manage.secrets import _kubectl_argv0

GHCR_DOCKER_SERVER = "ghcr.io"
DEFAULT_CLOUD_GHCR_USERNAME = "mindevis"
DEFAULT_CREDENTIALS_PATH = Path("/root/.ghcr-credentials")


def parse_ghcr_credentials_file(path: Path, default_username: str) -> tuple[str, str] | None:
    """
    Одна непустая строка (не комментарий) — PAT; username = GHCR_USERNAME или default_username (Cloud: mindevis).
    Две или больше — первая строка username, вторая PAT (остальное игнорируется).
    """
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines: list[str] = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    if not lines:
        return None
    if len(lines) == 1:
        return (default_username, lines[0])
    return (lines[0], lines[1])


def ensure_namespace(kbase: list[str], ns: str) -> None:
    r = subprocess.run(
        [*kbase, "create", "namespace", ns],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 and "AlreadyExists" not in (r.stderr or ""):
        print(r.stderr or r.stdout, file=sys.stderr)
        sys.exit(1)


def apply_ghcr_pull_secret(
    *,
    namespace: str,
    username: str,
    token: str,
    secret_name: str = "ghcr-credentials",
    force: bool = False,
) -> None:
    """kubectl create secret docker-registry … apply."""
    kbase = _kubectl_argv0()
    ensure_namespace(kbase, namespace)
    if force:
        subprocess.run(
            [*kbase, "delete", "secret", secret_name, "-n", namespace],
            capture_output=True,
        )
    proc = subprocess.run(
        [
            *kbase,
            "create",
            "secret",
            "docker-registry",
            secret_name,
            "-n",
            namespace,
            f"--docker-server={GHCR_DOCKER_SERVER}",
            f"--docker-username={username}",
            f"--docker-password={token}",
            "--dry-run=client",
            "-o",
            "yaml",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr)
        sys.exit(1)
    apply = subprocess.run(
        [*kbase, "apply", "-f", "-"],
        input=proc.stdout,
        text=True,
        capture_output=True,
    )
    if apply.returncode != 0:
        print(apply.stderr or apply.stdout, file=sys.stderr)
        sys.exit(1)
    print(
        f"OK: Secret {secret_name!r} (docker-registry {GHCR_DOCKER_SERVER}) in namespace {namespace!r}",
        flush=True,
    )


def maybe_apply_ghcr_from_file(
    *,
    namespace: str,
    cred_path: Path | None,
    default_username: str,
    skip: bool,
    force: bool,
    dry_run: bool = False,
) -> None:
    if skip:
        return
    path = (cred_path if cred_path is not None else DEFAULT_CREDENTIALS_PATH).expanduser()
    parsed = parse_ghcr_credentials_file(path, default_username)
    if parsed is None:
        if path.is_file():
            print(
                f"WARNING: {path} has no usable credentials; pods may fail to pull images. "
                "One line: PAT only (Cloud: user mindevis or GHCR_USERNAME). Two lines: username then PAT.",
                file=sys.stderr,
            )
        else:
            print(
                f"WARNING: missing {path} — ImagePullBackOff until docker-registry secret ghcr-credentials exists. "
                f"Cloud: create chmod 600 file with one line (PAT) — user defaults to {default_username!r}.",
                file=sys.stderr,
            )
        return
    user, token = parsed
    if dry_run:
        print(
            f"DRY-RUN: would create Secret docker-registry ghcr-credentials -n {namespace!r} "
            f"--docker-server={GHCR_DOCKER_SERVER} --docker-username={user!r} "
            f"--docker-password=<{len(token)} chars>",
            flush=True,
        )
        return
    print(f"GHCR pull secret: server={GHCR_DOCKER_SERVER}, user={user!r} …", flush=True)
    apply_ghcr_pull_secret(namespace=namespace, username=user, token=token, force=force)
