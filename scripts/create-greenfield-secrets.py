#!/usr/bin/env python3
"""
Создаёт Secret qm-mysql и минимальный qm-app для первичного развёртывания в пустом namespace.

Запускайте до bootstrap (install-k3s-helm.py / Argo sync) на новом кластере или после
kubectl delete secret … при смене паролей. Повтор без --force: ошибка «уже существует».

Пример:
  python3 scripts/create-greenfield-secrets.py -n qm
  python3 scripts/create-greenfield-secrets.py -n qm --force   # переустановка секретов
"""
from __future__ import annotations

import argparse
import base64
import secrets
import subprocess
import sys


def main() -> None:
    p = argparse.ArgumentParser(
        description="Bootstrap qm-mysql + qm-app Secrets for a fresh QM stack (K3s / Kubernetes)."
    )
    p.add_argument("-n", "--namespace", default="qm", help="namespace (default: qm)")
    p.add_argument(
        "--mysql-user",
        default="qmuser",
        help="application MySQL user (must match GRANT in mysql-config 100-qmnetwork.sql)",
    )
    p.add_argument(
        "--mysql-database",
        default="qmserver",
        help="MYSQL_DATABASE / основная БД QMServer (БД qmnetwork создаётся init-скриптом)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="удалить существующие qm-mysql и qm-app в namespace перед созданием",
    )
    args = p.parse_args()

    ns = args.namespace
    user = args.mysql_user
    db = args.mysql_database
    root_pw = secrets.token_urlsafe(24)
    app_pw = secrets.token_urlsafe(24)

    dsn_base = f"{user}:{app_pw}@tcp(mysql:3306)/"
    db_dsn = f"{dsn_base}{db}?parseTime=true"
    qmn_dsn = f"{dsn_base}qmnetwork?parseTime=true"
    jwt = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    billing = secrets.token_hex(32)
    qmi = secrets.token_hex(24)

    k = ["kubectl", "-n", ns]

    r = subprocess.run(["kubectl", "create", "namespace", ns], capture_output=True, text=True)
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

    create_secret(
        "qm-mysql",
        [
            ("MYSQL_ROOT_PASSWORD", root_pw),
            ("MYSQL_DATABASE", db),
            ("MYSQL_USER", user),
            ("MYSQL_PASSWORD", app_pw),
        ],
    )
    create_secret(
        "qm-app",
        [
            ("DB_DSN", db_dsn),
            ("QMNETWORK_MYSQL_DSN", qmn_dsn),
            ("JWT_SECRET", jwt),
            ("QMBILLING_ADMIN_SECRET", billing),
            ("QMNETWORK_INTERNAL_SECRET", qmi),
        ],
    )

    print(f"OK: secrets qm-mysql and qm-app in namespace {ns}", flush=True)
    print(
        "Next: sudo python3 scripts/install-k3s-helm.py   # GitOps: K3s, Helm, Argo CD + Application qm",
        flush=True,
    )


if __name__ == "__main__":
    main()
