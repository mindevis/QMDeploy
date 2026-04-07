"""
Создаёт Secret qm-mysql и qm-app для первичного развёртывания в пустом namespace.

qm-app включает ключи **QMServer Cloud** (лицензия) и стандартные секреты приложения (JWT, БД и т.д.).

На сервере K3s выполняйте от root. Обычно: **`k8s-manage.py --cloud-license-key-file …`** (bootstrap);
вручную: **`k8s-manage.py secrets`**.

Нужен доступ к API: **`kubectl`** или **`k3s kubectl`**. Если кластера нет: **`k8s-manage.py bootstrap --skip-argocd`**
или полный **`k8s-manage.py`** с лицензией.

Запускайте до полного GitOps-sync или после
**kubectl delete secret** … Повтор без **--force**: ошибка «уже существует».

Ключ лицензии: **`--cloud-license-key`** или **`--cloud-license-key-file`** (предпочтительно —
ключ не попадает в список аргументов процесса в `ps`). Пароль в командной строке после
`**--cloud-license-key**` по возможности удаляется из **файлов** истории (`HISTFILE`,
`~/.bash_history`, при наличии — `~/.zsh_history`); отключение: **`--no-scrub-history`** или
**`QM_NO_SCRUB_HISTORY=1`**. Память текущей сессии bash: выполните **`history -d -1`**
(или перезапустите оболочку).

Пример:
  python3 scripts/k8s-manage.py secrets -n qm --cloud-license-key-file /root/.qm-cloud-license
  python3 scripts/k8s-manage.py secrets -n qm --cloud-license-key '…' --dry-run
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_MARKER = "k8s-manage.py"
CLI_KEY_FLAG = "--cloud-license-key"


def _ensure_kubeconfig() -> None:
    if os.environ.get("KUBECONFIG"):
        return
    kc = Path("/etc/rancher/k3s/k3s.yaml")
    if kc.is_file():
        os.environ["KUBECONFIG"] = str(kc)


def _kubectl_argv0() -> list[str]:
    """['kubectl'] или ['k3s', 'kubectl'], если K3s установлен без симлинка kubectl."""
    if shutil.which("kubectl"):
        return ["kubectl"]
    if shutil.which("k3s"):
        _ensure_kubeconfig()
        return ["k3s", "kubectl"]
    print(
        "ERROR: neither kubectl nor k3s in PATH.\n"
        "On a clean server run first (as root):\n"
        "  python3 scripts/k8s-manage.py bootstrap --skip-argocd\n"
        "Then: k8s-manage.py secrets … , ghcr-credentials, and:\n"
        "  python3 scripts/k8s-manage.py",
        file=sys.stderr,
    )
    sys.exit(1)


def _redact_dsn(dsn: str) -> str:
    """Один пароль в user:password@tcp(...)."""
    return re.sub(r":([^:@]+)@", ":***@", dsn, count=1)


def _mask_secret_key(key: str, val: str) -> str:
    if key in (
        "MYSQL_ROOT_PASSWORD",
        "MYSQL_PASSWORD",
        "JWT_SECRET",
        "QMBILLING_ADMIN_SECRET",
        "QMSERVER_CLOUD_LICENSE_KEY",
    ):
        return f"<{len(val)} chars>"
    if key.endswith("_DSN") or key == "DB_DSN":
        return _redact_dsn(val)
    return val


def _candidate_histfiles() -> list[Path]:
    paths: list[Path] = []
    hf = (os.environ.get("HISTFILE") or "").strip()
    if hf:
        paths.append(Path(hf).expanduser())
    home = Path.home()
    paths.extend([home / ".bash_history", home / ".zsh_history"])
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        try:
            rp = p.resolve()
        except OSError:
            rp = p
        if rp in seen:
            continue
        seen.add(rp)
        if p.is_file():
            out.append(p)
    return out


def _scrub_last_risky_line(path: Path) -> bool:
    """
    Удаляет с конца файла первую строку, содержащую вызов k8s-manage и --cloud-license-key
    (но не --cloud-license-key-file), чтобы вырезать ключ из истории.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if not text:
        return False
    lines = text.splitlines(keepends=True)
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if SCRIPT_MARKER not in line:
            continue
        if CLI_KEY_FLAG not in line:
            continue
        if "--cloud-license-key-file" in line:
            continue
        del lines[i]
        try:
            path.write_text("".join(lines), encoding="utf-8")
        except OSError:
            return False
        return True
    return False


def _scrub_shell_history_files() -> bool:
    """Несколько попыток: bash дописывает HISTFILE не сразу."""
    for delay_ms in (0, 80, 200, 500, 1000):
        if delay_ms:
            time.sleep(delay_ms / 1000.0)
        for p in _candidate_histfiles():
            if _scrub_last_risky_line(p):
                return True
    return False


def _load_license(args: argparse.Namespace) -> tuple[str, bool]:
    """Возвращает (ключ, license_via_cli_literal)."""
    if getattr(args, "cloud_license_key_file", None) is not None:
        p = args.cloud_license_key_file.expanduser()
        if not p.is_file():
            print(f"ERROR: license file not found: {p}", file=sys.stderr)
            sys.exit(1)
        raw = p.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            print("ERROR: license file is empty.", file=sys.stderr)
            sys.exit(1)
        return raw, False
    lic = (args.cloud_license_key or "").strip()
    return lic, True


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=(
            "Bootstrap qm-mysql + qm-app Secrets for a fresh QM stack (K3s / Kubernetes). "
            "License: --cloud-license-key or --cloud-license-key-file. "
            "--dry-run previews without kubectl."
        )
    )
    p.add_argument("-n", "--namespace", default="qm", help="namespace (default: qm)")
    p.add_argument(
        "--mysql-user",
        default="qmuser",
        help="application MySQL user (must match privileges for MYSQL_DATABASE)",
    )
    p.add_argument(
        "--mysql-database",
        default="qmserver",
        help="MYSQL_DATABASE / основная БД QMServer (должна совпадать с init MySQL)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="удалить существующие qm-mysql и qm-app в namespace перед созданием",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="только проверка и сводка (секреты в выводе маскируются); kubectl create не вызывается",
    )
    p.add_argument(
        "--no-scrub-history",
        action="store_true",
        help="не удалять строку с --cloud-license-key из файлов истории оболочки",
    )
    key_src = p.add_mutually_exclusive_group(required=True)
    key_src.add_argument(
        "--cloud-license-key",
        metavar="KEY",
        help="Лицензионный ключ (после выполнения по возможности стирается строка в HISTFILE).",
    )
    key_src.add_argument(
        "--cloud-license-key-file",
        type=Path,
        metavar="PATH",
        help="Файл с ключом (рекомендуется: ключ не в argv/ps; chmod 600).",
    )
    p.add_argument(
        "--cloud-license-ips",
        default="",
        metavar="IPS",
        help="Привязка лицензии: внешние IP нод через запятую. Опционально.",
    )
    p.add_argument(
        "--cloud-license-machine-ids",
        default="",
        metavar="IDS",
        help="Привязка лицензии: machine-id через запятую. Опционально.",
    )
    p.add_argument(
        "--cloud-license-node-names",
        default="",
        metavar="NAMES",
        help="Привязка лицензии: имена Kubernetes node через запятую. Опционально.",
    )
    if argv is None:
        args = p.parse_args()
    else:
        args = p.parse_args(argv)

    lic, license_via_cli = _load_license(args)
    if not lic:
        print("ERROR: Cloud license must be non-empty.", file=sys.stderr)
        sys.exit(1)

    scrub_enabled = (
        license_via_cli
        and not args.no_scrub_history
        and os.environ.get("QM_NO_SCRUB_HISTORY", "").strip() != "1"
    )

    try:
        _run(args, lic)
    finally:
        if scrub_enabled:
            if _scrub_shell_history_files():
                print(
                    "Removed the last matching line with the license from shell history file(s). "
                    "In this interactive bash session run:  history -d -1",
                    flush=True,
                )
            else:
                print(
                    "Could not find/remove this command in history files yet. "
                    "Try:  history -d -1   in bash, or use --cloud-license-key-file next time.",
                    flush=True,
                )


def _run(args: argparse.Namespace, lic: str) -> None:
    ns = args.namespace
    user = args.mysql_user
    db = args.mysql_database
    root_pw = secrets.token_urlsafe(24)
    app_pw = secrets.token_urlsafe(24)

    dsn_base = f"{user}:{app_pw}@tcp(mysql:3306)/"
    db_dsn = f"{dsn_base}{db}?parseTime=true"
    jwt = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    billing = secrets.token_hex(32)

    mysql_pairs: list[tuple[str, str]] = [
        ("MYSQL_ROOT_PASSWORD", root_pw),
        ("MYSQL_DATABASE", db),
        ("MYSQL_USER", user),
        ("MYSQL_PASSWORD", app_pw),
    ]
    app_pairs: list[tuple[str, str]] = [
        ("DB_DSN", db_dsn),
        ("JWT_SECRET", jwt),
        ("QMBILLING_ADMIN_SECRET", billing),
        ("QMSERVER_CLOUD_LICENSE_KEY", lic),
    ]
    ips = (args.cloud_license_ips or "").strip()
    if ips:
        app_pairs.append(("QMSERVER_CLOUD_LICENSE_IPS", ips))
    mids = (args.cloud_license_machine_ids or "").strip()
    if mids:
        app_pairs.append(("QMSERVER_CLOUD_LICENSE_MACHINE_IDS", mids))
    nodes = (args.cloud_license_node_names or "").strip()
    if nodes:
        app_pairs.append(("QMSERVER_CLOUD_LICENSE_NODE_NAMES", nodes))

    if args.dry_run:
        print("DRY-RUN: cluster will not be modified.\n", flush=True)
        print(f"Namespace: {ns}", flush=True)
        print(f"Would ensure namespace exists (kubectl create namespace {ns}, ignore AlreadyExists).", flush=True)
        if args.force:
            print("Would delete secrets qm-mysql, qm-app if present (--force).", flush=True)
        print("\nSecret qm-mysql (keys):", flush=True)
        for key, val in mysql_pairs:
            print(f"  {key}: {_mask_secret_key(key, val)}", flush=True)
        print("\nSecret qm-app (keys):", flush=True)
        for key, val in app_pairs:
            print(f"  {key}: {_mask_secret_key(key, val)}", flush=True)
        print(
            "\nNext without --dry-run: same command without --dry-run to apply.",
            flush=True,
        )
        print(
            "Then: python3 scripts/k8s-manage.py   # от root: K3s, Helm, Argo CD + Application qm",
            flush=True,
        )
        return

    kbase = _kubectl_argv0()
    k = [*kbase, "-n", ns]

    r = subprocess.run([*kbase, "create", "namespace", ns], capture_output=True, text=True)
    if r.returncode != 0 and "AlreadyExists" not in (r.stderr or ""):
        print(r.stderr or r.stdout, file=sys.stderr)
        sys.exit(1)

    if args.force:
        subprocess.run([*k, "delete", "secret", "qm-mysql"], capture_output=True)
        subprocess.run([*k, "delete", "secret", "qm-app"], capture_output=True)

    def create_secret(name: str, pairs: list[tuple[str, str]]) -> None:
        cmd = [*k, "create", "secret", "generic", name]
        for key, val in pairs:
            cmd.append(f"--from-literal={key}={val}")
        r2 = subprocess.run(cmd, capture_output=True, text=True)
        if r2.returncode != 0:
            print(r2.stderr or r2.stdout, file=sys.stderr)
            sys.exit(1)

    create_secret("qm-mysql", mysql_pairs)
    create_secret("qm-app", app_pairs)

    print(f"OK: secrets qm-mysql and qm-app in namespace {ns}", flush=True)
    print(
        "Next: python3 scripts/k8s-manage.py   # от root: K3s, Helm, Argo CD + Application qm",
        flush=True,
    )
