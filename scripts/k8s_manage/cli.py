"""Unified CLI dispatcher for k8s-manage.py."""
from __future__ import annotations

import sys
from pathlib import Path

from k8s_manage.addons import main as addons_main
from k8s_manage.bootstrap import main as bootstrap_main
from k8s_manage.secrets import main as secrets_main

# QMDeploy root: this file is scripts/k8s_manage/cli.py → parents[2]
_ROOT = Path(__file__).resolve().parents[2]


def _bundle_version() -> str:
    vf = _ROOT / "VERSION"
    if vf.is_file():
        return vf.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return "unknown"


def _print_top_help() -> None:
    prog = Path(sys.argv[0]).name
    print(
        f"""Usage:
  python3 scripts/{prog} [bootstrap] [args …]   # по умолчанию; см. bootstrap --help
  python3 scripts/{prog} secrets [args …]      # greenfield Secrets qm-mysql / qm-app
  python3 scripts/{prog} addons [args …]       # Argo CD / MinIO и т.д.
  python3 scripts/{prog} reset-k3s [args …]    # полный снос K3s + перезагрузка (root)
  python3 scripts/{prog} --version

Greenfield (чистый сервер), один проход:
  python3 scripts/{prog} --cloud-license-key-file /root/.qm-cloud-license

См. также QMDeploy/README.md"""
    )


def main() -> int:
    argv = sys.argv[1:]

    if not argv:
        bootstrap_main(None)
        return 0

    if argv in (["-h"], ["--help"], ["help"]):
        _print_top_help()
        return 0

    if argv in (["--version"], ["-V"], ["version"]):
        print(_bundle_version())
        return 0

    head, *tail = argv
    if head == "bootstrap":
        bootstrap_main(tail if tail else None)
        return 0
    if head == "secrets":
        secrets_main(tail if tail else None)
        return 0
    if head == "addons":
        addons_main(tail if tail else None)
        return 0
    if head == "reset-k3s":
        from k8s_manage.reset_k3s import main as reset_k3s_main

        reset_k3s_main(tail if tail else None)
        return 0

    bootstrap_main(argv)
    return 0
