#!/usr/bin/env python3
"""
QMDeploy: при необходимости ставит K3s, затем helm upgrade --install для чарта qm-project.

Требуется: Helm 3 в PATH. Установка K3s: curl get.k3s.io (обычно нужен root/sudo).

Переменные окружения: NAMESPACE (по умолчанию qm), RELEASE_NAME (по умолчанию qm),
KUBECONFIG (по умолчанию /etc/rancher/k3s/k3s.yaml), INSTALL_K3S_VERSION (опционально).

Все аргументы командной строки передаются в helm после имени чарта (например -f values.yaml).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "helm" / "qm-project"


def _has_cluster_cli() -> bool:
    return bool(shutil.which("kubectl") or shutil.which("k3s"))


def _install_k3s() -> None:
    print("Installing K3s …", flush=True)
    env = os.environ.copy()
    subprocess.run(
        "curl -sfL https://get.k3s.io | sh -",
        shell=True,
        check=True,
        env=env,
    )


def _warn_missing_secrets(namespace: str) -> None:
    """Подсказка до helm: без qm-mysql поды упадут до создания секретов."""
    if os.environ.get("SKIP_SECRET_CHECK"):
        return
    if not shutil.which("kubectl"):
        return
    r = subprocess.run(
        ["kubectl", "get", "secret", "qm-mysql", "-n", namespace],
        capture_output=True,
    )
    if r.returncode != 0:
        helper = ROOT / "scripts" / "create-greenfield-secrets.py"
        print(
            f"WARNING: secret qm-mysql not in namespace {namespace!r}. "
            f"Create secrets first, e.g.: python3 {helper} -n {namespace}\n"
            f"(suppress: SKIP_SECRET_CHECK=1)",
            file=sys.stderr,
        )


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(
            "Usage: sudo python3 install-k3s-helm.py [helm args, e.g. -f values.yaml --set k=v]\n"
            f"  Chart: {CHART}\n"
            f"  Release: {os.environ.get('RELEASE_NAME', 'qm')}, "
            f"namespace: {os.environ.get('NAMESPACE', 'qm')}",
        )
        sys.exit(0)

    if not (CHART / "Chart.yaml").is_file():
        print(f"ERROR: chart not found: {CHART / 'Chart.yaml'}", file=sys.stderr)
        sys.exit(1)

    if not shutil.which("helm"):
        print(
            "ERROR: install Helm 3 first: https://helm.sh/docs/intro/install/",
            file=sys.stderr,
        )
        sys.exit(1)

    if not _has_cluster_cli():
        _install_k3s()

    if "KUBECONFIG" not in os.environ:
        os.environ["KUBECONFIG"] = "/etc/rancher/k3s/k3s.yaml"

    namespace = os.environ.get("NAMESPACE", "qm")
    release = os.environ.get("RELEASE_NAME", "qm")
    helm_extra = sys.argv[1:]

    _warn_missing_secrets(namespace)

    cmd = [
        "helm",
        "upgrade",
        "--install",
        release,
        str(CHART),
        "--namespace",
        namespace,
        "--create-namespace",
        *helm_extra,
    ]
    subprocess.run(cmd, check=True)
    print(f"OK: helm release {release} (namespace {namespace})", flush=True)


if __name__ == "__main__":
    main()
