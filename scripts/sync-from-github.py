#!/usr/bin/env python3
"""
Скачивает чарт qm-project и скрипты QMDeploy с GitHub (raw) в каталог кэша.

- QM_HELM_BASE_URL — raw URL каталога .../helm (чарт qm-project/).
- QM_DEPLOY_BASE_URL — raw URL корня репозитория QMDeploy (скрипты в scripts/).
  Если не задан — из QM_HELM_BASE_URL: .../helm → родитель.
"""
from __future__ import annotations

import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

HELM_BUNDLE_FILES = [
    "qm-project/Chart.yaml",
    "qm-project/values.yaml",
    "qm-project/templates/_helpers.tpl",
    "qm-project/templates/configmap-mysql.yaml",
    "qm-project/templates/configmap-qmserver.yaml",
    "qm-project/templates/deployment-qmadmin.yaml",
    "qm-project/templates/deployment-qmdocs.yaml",
    "qm-project/templates/deployment-qmnetwork.yaml",
    "qm-project/templates/deployment-qmserver.yaml",
    "qm-project/templates/deployment-qmweb.yaml",
    "qm-project/templates/ingress.yaml",
    "qm-project/templates/mysql.yaml",
    "qm-project/templates/namespace.yaml",
    "qm-project/templates/phpmyadmin.yaml",
    "qm-project/templates/NOTES.txt",
    "qm-project/templates/pvc-qmserver.yaml",
    "qm-project/templates/pvc-qmweb.yaml",
]

DEPLOY_PYTHON_SCRIPTS = [
    "scripts/sync-from-github.py",
    "scripts/k8s-manage.py",
    "scripts/k8s_manage/__init__.py",
    "scripts/k8s_manage/cli.py",
    "scripts/k8s_manage/bootstrap.py",
    "scripts/k8s_manage/secrets.py",
    "scripts/k8s_manage/ghcr_credentials.py",
    "scripts/k8s_manage/addons.py",
    "scripts/k8s_manage/reset_k3s.py",
]

DEFAULT_HELM_BASE_URL = (
    "https://raw.githubusercontent.com/mindevis/QMDeploy/main/helm"
)
DEFAULT_DEPLOY_BASE_URL = "https://raw.githubusercontent.com/mindevis/QMDeploy/main"


def _default_qm_deploy_root() -> Path:
    env = os.environ.get("QM_DEPLOY_ROOT", "").strip()
    if env:
        return Path(env)
    if os.geteuid() == 0:
        return Path("/opt/qm")
    xdg = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(xdg) / "qm"


def _helm_cache_root() -> Path:
    v = os.environ.get("QM_HELM_CACHE", "").strip()
    if v:
        return Path(v)
    return _default_qm_deploy_root()


def _deploy_semver() -> str:
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        vf = d / "VERSION"
        if vf.is_file():
            return vf.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return "1.2.0"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url, headers={"User-Agent": f"qm-sync-chart/{_deploy_semver()}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError as e:
        print(f"ERROR: HTTP {e.code} при загрузке {url}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: {e.reason!r} при загрузке {url}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"ERROR: не удалось записать {dest}: {e}", file=sys.stderr)
        sys.exit(1)


def _chmod_executable(path: Path) -> None:
    if path.is_file():
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def deploy_base_url() -> str:
    explicit = os.environ.get("QM_DEPLOY_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    helm = os.environ.get("QM_HELM_BASE_URL", DEFAULT_HELM_BASE_URL).rstrip("/")
    if helm.endswith("/helm"):
        return helm[: -len("/helm")]
    return DEFAULT_DEPLOY_BASE_URL.rstrip("/")


def main() -> None:
    helm_base = os.environ.get("QM_HELM_BASE_URL", DEFAULT_HELM_BASE_URL).rstrip("/")
    dep_base = deploy_base_url()
    cache_root = _helm_cache_root()
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"ERROR: не удалось создать каталог кэша {cache_root}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Helm (chart) URL: {helm_base}")
    print(f"Deploy (scripts) URL: {dep_base}")
    print(f"Cache:              {cache_root}")
    print(f"QMDeploy bundle:    {_deploy_semver()}  (VERSION)")

    ver_dest = cache_root / "VERSION"
    ver_url = f"{dep_base}/VERSION"
    print(f"  <- {ver_url}")
    _download(ver_url, ver_dest)

    for rel in HELM_BUNDLE_FILES:
        dest = cache_root / rel
        url = f"{helm_base}/{rel}"
        print(f"  <- {url}")
        _download(url, dest)

    for rel in DEPLOY_PYTHON_SCRIPTS:
        dest = cache_root / rel
        url = f"{dep_base}/{rel}"
        print(f"  <- {url}")
        _download(url, dest)
        _chmod_executable(dest)

    print(f"Done: chart at {cache_root / 'qm-project'}")
    print(f"      scripts: {', '.join(DEPLOY_PYTHON_SCRIPTS)}")


if __name__ == "__main__":
    main()
