"""
Создаёт Secret qm-mysql и qm-app для первичного развёртывания в пустом namespace.

qm-app включает стандартные секреты приложения (JWT, БД и т.д.).

На сервере K3s выполняйте от root. Обычно: **`k8s-manage.py secrets`**;
вручную после установки K3s: **`k8s-manage.py secrets -n qm`**.

Нужен доступ к API: **`kubectl`** или **`k3s kubectl`**.

Запускайте до полного GitOps-sync или после
**kubectl delete secret** … Повтор без **--force**: если секреты уже есть — команда завершится без изменений.
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
from pathlib import Path


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
    ):
        return f"<{len(val)} chars>"
    if key.endswith("_DSN") or key == "DB_DSN":
        return _redact_dsn(val)
    return val


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=(
            "Bootstrap qm-mysql + qm-app Secrets for a fresh QM stack (K3s / Kubernetes). "
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
    if argv is None:
        args = p.parse_args()
    else:
        args = p.parse_args(argv)

    _run(args)


def _run(args: argparse.Namespace) -> None:
    ns = args.namespace
    user = args.mysql_user
    db = args.mysql_database
    root_pw = secrets.token_urlsafe(24)
    app_pw = secrets.token_urlsafe(24)

    dsn_base = f"{user}:{app_pw}@tcp(mysql:3306)/"
    db_dsn = f"{dsn_base}{db}?parseTime=true"
    jwt = base64.b64encode(secrets.token_bytes(32)).decode("ascii")

    mysql_pairs: list[tuple[str, str]] = [
        ("MYSQL_ROOT_PASSWORD", root_pw),
        ("MYSQL_DATABASE", db),
        ("MYSQL_USER", user),
        ("MYSQL_PASSWORD", app_pw),
    ]
    app_pairs: list[tuple[str, str]] = [
        ("DB_DSN", db_dsn),
        ("JWT_SECRET", jwt),
    ]

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

    if not args.force:
        r = subprocess.run([*k, "get", "secret", "qm-app"], capture_output=True, text=True)
        if r.returncode == 0:
            print(
                f"OK: secrets already exist in namespace {ns!r}; use --force to recreate",
                flush=True,
            )
            return

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
