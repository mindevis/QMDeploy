#!/usr/bin/env python3
"""
Создаёт Secret qm-mysql и qm-app для первичного развёртывания в пустом namespace.

qm-app включает ключи **QMServer Cloud** (лицензия) и **QMSecret** (master key + service token),
как в GitOps-пути (**values-argocd.yaml**: qmsecret.enabled: true).

На сервере K3s выполняйте от root (тот же kubeconfig, что и у install-k3s-helm.py).

Запускайте до bootstrap (install-k3s-helm.py / Argo sync) на новом кластере или после
kubectl delete secret … при смене паролей. Повтор без --force: ошибка «уже существует».

Пример:
  export QMSERVER_CLOUD_LICENSE_KEY='…'   # или --cloud-license-key
  python3 scripts/create-greenfield-secrets.py -n qm
  python3 scripts/create-greenfield-secrets.py -n qm --force   # переустановка секретов
"""
from __future__ import annotations

import argparse
import base64
import os
import secrets
import subprocess
import sys


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Bootstrap qm-mysql + qm-app Secrets for a fresh QM stack (K3s / Kubernetes). "
            "Cloud: requires QMServer Cloud license key; generates QMSecret keys for qm-app."
        )
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
    p.add_argument(
        "--cloud-license-key",
        default=os.environ.get("QMSERVER_CLOUD_LICENSE_KEY", ""),
        metavar="KEY",
        help=(
            "Лицензионный ключ QMServer Cloud (или задайте env QMSERVER_CLOUD_LICENSE_KEY). "
            "Обязателен: без него QMServer в K8s не пройдёт проверку лицензии."
        ),
    )
    p.add_argument(
        "--cloud-license-ips",
        default=os.environ.get("QMSERVER_CLOUD_LICENSE_IPS", ""),
        metavar="IPS",
        help="Привязка лицензии: внешние IP нод через запятую (env QMSERVER_CLOUD_LICENSE_IPS). Опционально.",
    )
    p.add_argument(
        "--cloud-license-machine-ids",
        default=os.environ.get("QMSERVER_CLOUD_LICENSE_MACHINE_IDS", ""),
        metavar="IDS",
        help="Привязка лицензии: machine-id через запятую (env QMSERVER_CLOUD_LICENSE_MACHINE_IDS). Опционально.",
    )
    p.add_argument(
        "--cloud-license-node-names",
        default=os.environ.get("QMSERVER_CLOUD_LICENSE_NODE_NAMES", ""),
        metavar="NAMES",
        help="Привязка лицензии: имена Kubernetes node через запятую (env QMSERVER_CLOUD_LICENSE_NODE_NAMES). Опционально.",
    )
    args = p.parse_args()

    lic = (args.cloud_license_key or "").strip()
    if not lic:
        print(
            "ERROR: QMServer Cloud requires a license. Set --cloud-license-key or "
            "environment variable QMSERVER_CLOUD_LICENSE_KEY.",
            file=sys.stderr,
        )
        sys.exit(1)

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
    qmsecret_master = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    qmsecret_token = secrets.token_urlsafe(32)

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
    app_pairs: list[tuple[str, str]] = [
        ("DB_DSN", db_dsn),
        ("QMNETWORK_MYSQL_DSN", qmn_dsn),
        ("JWT_SECRET", jwt),
        ("QMBILLING_ADMIN_SECRET", billing),
        ("QMNETWORK_INTERNAL_SECRET", qmi),
        ("QMSERVER_CLOUD_LICENSE_KEY", lic),
        ("QMSECRET_MASTER_KEY", qmsecret_master),
        ("QMSECRET_SERVICE_TOKEN", qmsecret_token),
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

    create_secret("qm-app", app_pairs)

    print(f"OK: secrets qm-mysql and qm-app in namespace {ns}", flush=True)
    print(
        "Next: python3 scripts/install-k3s-helm.py   # от root: K3s, Helm, Argo CD + Application qm",
        flush=True,
    )


if __name__ == "__main__":
    main()
