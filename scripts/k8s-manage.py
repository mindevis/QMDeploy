#!/usr/bin/env python3
"""
QMDeploy — единая точка входа для K3s / Helm / Argo CD / секретов / дополнений.

Подкоманды (можно опустить **bootstrap** — команды с флагом вида **--...** сразу идут в bootstrap):

  bootstrap   Скрипт **install-k3s-helm.py**: K3s, Helm, опционально greenfield-secrets, Argo + Application **qm**.
  secrets     **create-greenfield-secrets.py** — только **qm-mysql** / **qm-app** (**--dry-run**, ключ лицензии …).
  addons      **install-optional-addons.py** — **--argocd**, **--s3**, деинсталляции и т.д.

Примеры:

  python3 scripts/k8s-manage.py --cloud-license-key-file /root/.qm-cloud-license
  python3 scripts/k8s-manage.py bootstrap --help
  python3 scripts/k8s-manage.py secrets --cloud-license-key-file /root/.lic --dry-run
  python3 scripts/k8s-manage.py addons --argocd --s3
  python3 scripts/k8s-manage.py --version
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

_DELEGATE = {
    "bootstrap": HERE / "install-k3s-helm.py",
    "secrets": HERE / "create-greenfield-secrets.py",
    "addons": HERE / "install-optional-addons.py",
}


def _bundle_version() -> str:
    vf = ROOT / "VERSION"
    if vf.is_file():
        return vf.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return "unknown"


def _run(delegate_key: str, forward: list[str]) -> int:
    script = _DELEGATE[delegate_key]
    if not script.is_file():
        print(f"ERROR: missing script {script}", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(script), *forward])


def _print_top_help() -> None:
    prog = Path(sys.argv[0]).name
    print(
        f"""Usage:
  python3 scripts/{prog} [bootstrap] [args …]   # по умолчанию; см. install-k3s-helm.py
  python3 scripts/{prog} secrets [args …]      # create-greenfield-secrets.py
  python3 scripts/{prog} addons [args …]       # install-optional-addons.py
  python3 scripts/{prog} --version

Greenfield (чистый сервер), один проход:
  python3 scripts/{prog} --cloud-license-key-file /root/.qm-cloud-license

См. также QMDeploy/README.md"""
    )


def main() -> int:
    argv = sys.argv[1:]

    if not argv:
        return _run("bootstrap", [])

    if argv in (["-h"], ["--help"], ["help"]):
        _print_top_help()
        return 0

    if argv in (["--version"], ["-V"], ["version"]):
        print(_bundle_version())
        return 0

    head, *tail = argv
    if head in _DELEGATE:
        return _run(head, tail)

    # Первый токен не подкоманда — считаем аргументами bootstrap (как раньше install-k3s-helm.py).
    return _run("bootstrap", argv)


if __name__ == "__main__":
    sys.exit(main())
