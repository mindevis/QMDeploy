"""
Полный сброс K3s на ноде: очистка рабочих нагрузок (Helm / namespaces), затем k3s-killall + uninstall,
опционально кэш /opt/qm, перезагрузка ОС.

Только от root на сервере (или на worker с --agent). Не удаляет лицензии /root/.qm-cloud-license и PAT.

Пример (control-plane / одиночный сервер):

  python3 scripts/k8s-manage.py reset-k3s --yes

Worker-нода (после отключения от кластера или параллельно; без kubectl-чистки):

  python3 scripts/k8s-manage.py reset-k3s --agent --yes

Сухой прогон:

  python3 scripts/k8s-manage.py reset-k3s --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from k8s_manage.addons import helm_cmd, kubectl_cmd, uninstall_argocd, uninstall_minio

_PROTECTED_NS = frozenset({"kube-system", "kube-public", "kube-node-lease", "default"})
_K3S_KILLALL = Path("/usr/local/bin/k3s-killall.sh")
_K3S_UNINSTALL_SERVER = Path("/usr/local/bin/k3s-uninstall.sh")
_K3S_UNINSTALL_AGENT = Path("/usr/local/bin/k3s-agent-uninstall.sh")
_DEFAULT_OPT_QM = Path("/opt/qm")


def _ensure_kubeconfig_env() -> None:
    if os.environ.get("KUBECONFIG"):
        return
    kc = Path("/etc/rancher/k3s/k3s.yaml")
    if kc.is_file():
        os.environ["KUBECONFIG"] = str(kc)


def _require_root() -> None:
    if os.geteuid() != 0:
        print("ОШИБКА: reset-k3s нужно запускать от root.", file=sys.stderr)
        sys.exit(1)


def _kubectl_argv0() -> list[str]:
    if shutil.which("kubectl"):
        return ["kubectl"]
    if shutil.which("k3s"):
        _ensure_kubeconfig_env()
        return ["k3s", "kubectl"]
    return []


def _cluster_api_reachable(kbase: list[str]) -> bool:
    if not kbase:
        return False
    r = subprocess.run(
        [*kbase, "get", "--raw", "/healthz"],
        capture_output=True,
        timeout=30,
    )
    return r.returncode == 0 and (r.stdout or b"").strip() == b"ok"


def _helm_uninstall_all(args: argparse.Namespace) -> None:
    ensure = shutil.which("helm")
    if not ensure:
        print("Helm не найден — пропуск helm uninstall -A.", flush=True)
        return
    h = helm_cmd(args)
    r = subprocess.run([*h, "list", "-A", "-o", "json"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Helm list -A не удался (код {r.returncode}) — продолжаем.", flush=True)
        return
    raw = (r.stdout or "").strip()
    if not raw or raw == "[]":
        return
    try:
        releases = json.loads(raw)
    except json.JSONDecodeError:
        print("Helm: не разобрали JSON списка релизов — продолжаем.", flush=True)
        return
    for rel in releases:
        name = rel.get("name")
        namespace = rel.get("namespace")
        if not name or not namespace:
            continue
        print(f"Helm: uninstall {name!r} (ns {namespace}) …", flush=True)
        subprocess.run([*h, "uninstall", name, "-n", namespace], check=False)


def _delete_user_namespaces(args: argparse.Namespace) -> None:
    k = kubectl_cmd(args)
    r = subprocess.run(
        [*k, "get", "namespaces", "-o", "json"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("kubectl get namespaces не удался — пропуск удаления namespace.", flush=True)
        return
    try:
        payload = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        print("kubectl: некорректный JSON namespace — пропуск.", flush=True)
        return
    names = [
        item.get("metadata", {}).get("name")
        for item in payload.get("items", [])
        if item.get("metadata", {}).get("name")
    ]
    for ns in names:
        if ns in _PROTECTED_NS:
            continue
        print(f"kubectl: delete namespace {ns!r} (--wait=false) …", flush=True)
        subprocess.run([*k, "delete", "namespace", ns, "--wait=false"], check=False)


def _strip_default_namespace(args: argparse.Namespace) -> None:
    k = kubectl_cmd(args)
    print("kubectl: очистка ресурсов в namespace default …", flush=True)
    subprocess.run([*k, "delete", "all", "--all", "-n", "default", "--wait=false"], check=False)
    subprocess.run(
        [*k, "delete", "pvc", "--all", "-n", "default", "--wait=false"],
        check=False,
    )


def _run_optional_shell(path: Path, dry_run: bool, label: str) -> None:
    if not path.is_file():
        print(f"{label}: нет скрипта {path} — пропуск.", flush=True)
        return
    if not os.access(path, os.X_OK):
        print(f"{label}: {path} не исполняемый — пробуем sh.", flush=True)
        cmd = ["sh", str(path)]
    else:
        cmd = [str(path)]
    if dry_run:
        print(f"DRY-RUN: {' '.join(cmd)}", flush=True)
        return
    print(f"Выполняем: {' '.join(cmd)} …", flush=True)
    subprocess.run(cmd, check=False)


def _remove_opt_qm(dry_run: bool, path: Path) -> None:
    if not path.exists():
        print(f"Каталог {path} не найден — нечего удалять.", flush=True)
        return
    if dry_run:
        print(f"DRY-RUN: rm -rf {path}", flush=True)
        return
    print(f"Удаление кэша QMDeploy: rm -rf {path} …", flush=True)
    shutil.rmtree(path, ignore_errors=True)


def _reboot(dry_run: bool) -> None:
    if dry_run:
        print("DRY-RUN: systemctl reboot", flush=True)
        return
    print("Перезагрузка сервера через systemctl reboot …", flush=True)
    subprocess.run(["systemctl", "reboot"], check=False)
    # Если systemctl недоступен:
    # os.execvp("shutdown", ["shutdown", "-r", "now"])


def _confirm(yes: bool) -> None:
    if yes:
        return
    print(
        "\nВНИМАНИЕ: будет удалены рабочие нагрузки Kubernetes (кроме системных namespace), "
        "затем K3s и данные кластера, опционально /opt/qm, затем перезагрузка.\n"
        "Секреты в /root/.ghcr-credentials и файлы лицензий скрипт НЕ трогает.\n"
    )
    if input("Введите YES для продолжения: ").strip() != "YES":
        print("Отменено.", flush=True)
        sys.exit(0)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=(
            "Полное удаление пользовательского стека в K3s, деинсталляция K3s и перезагрузка ноды. "
            "Только root."
        )
    )
    p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Не спрашивать подтверждение (обязательно в automation)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Только распечатать шаги, ничего не выполнять",
    )
    p.add_argument("--kubeconfig", help="Путь к kubeconfig (иначе как в K3s bootstrap)")
    p.add_argument(
        "--agent",
        action="store_true",
        help="Только worker: пропустить kubectl/helm, выполнить k3s-killall и k3s-agent-uninstall",
    )
    p.add_argument(
        "--keep-opt-qm",
        action="store_true",
        help="Не удалять кэш QMDeploy (по умолчанию удаляется /opt/qm если существует)",
    )
    p.add_argument(
        "--opt-qm-path",
        type=Path,
        default=_DEFAULT_OPT_QM,
        metavar="PATH",
        help=f"Каталог кэша sync-from-github (по умолчанию {_DEFAULT_OPT_QM})",
    )
    p.add_argument(
        "--no-reboot",
        action="store_true",
        help="После uninstall не перезагружать (для отладки)",
    )
    p.add_argument(
        "--skip-minio",
        action="store_true",
        help="Не вызывать удаление MinIO (namespace minio по умолчанию)",
    )
    if argv is None:
        args = p.parse_args()
    else:
        args = p.parse_args(argv)

    if args.dry_run:
        args.yes = True
    else:
        _require_root()
        _confirm(args.yes)

    if args.kubeconfig:
        os.environ["KUBECONFIG"] = args.kubeconfig
    else:
        _ensure_kubeconfig_env()

    if not args.agent:
        kube_base = _kubectl_argv0()
        if kube_base == ["k3s", "kubectl"] and args.kubeconfig:
            kube_base = [*kube_base, "--kubeconfig", args.kubeconfig]
        elif kube_base == ["kubectl"] and args.kubeconfig:
            kube_base = ["kubectl", "--kubeconfig", args.kubeconfig]

        if kube_base and _cluster_api_reachable(kube_base):
            addon_ns = SimpleNamespace(
                kubeconfig=args.kubeconfig,
                minio_namespace="minio",
            )
            print("Кластер доступен: удаление Argo CD (если есть) …", flush=True)
            if shutil.which("helm"):
                if not args.dry_run:
                    uninstall_argocd(addon_ns)
                else:
                    print(
                        "DRY-RUN: uninstall_argocd (applications, helm argocd, ns argocd)",
                        flush=True,
                    )
            else:
                print("Helm не в PATH — Application Argo удаляются через kubectl (без helm uninstall).", flush=True)
                if not args.dry_run:
                    k = kubectl_cmd(args)
                    subprocess.run(
                        [
                            *k,
                            "delete",
                            "applications.argoproj.io",
                            "--all",
                            "-n",
                            "argocd",
                            "--wait=false",
                        ],
                        check=False,
                    )

            if not args.skip_minio:
                print("MinIO: полное удаление (если namespace есть) …", flush=True)
                if shutil.which("helm"):
                    if not args.dry_run:
                        uninstall_minio(addon_ns)
                    else:
                        print("DRY-RUN: uninstall_minio (helm minio, ns minio)", flush=True)
                elif not args.dry_run:
                    print("MinIO: helm нет — полагаемся на удаление namespace minio ниже.", flush=True)

            print("Helm: uninstall всех оставшихся релизов (-A) …", flush=True)
            if not args.dry_run:
                _helm_uninstall_all(args)
            else:
                print("DRY-RUN: helm list -A && helm uninstall по каждому", flush=True)

            print("kubectl: удаление пользовательских namespace …", flush=True)
            if not args.dry_run:
                _delete_user_namespaces(args)
                _strip_default_namespace(args)
            else:
                print(
                    "DRY-RUN: kubectl delete ns (кроме kube-system, kube-public, "
                    "kube-node-lease, default); зачистка default",
                    flush=True,
                )
        else:
            print(
                "API Kubernetes недоступен или нет kubectl — пропускаем снятие манифестов.",
                flush=True,
            )
    else:
        print("Режим --agent: пропуск kubectl/helm.", flush=True)

    _run_optional_shell(_K3S_KILLALL, args.dry_run, "K3s killall")

    if args.agent:
        if _K3S_UNINSTALL_AGENT.is_file() or args.dry_run:
            _run_optional_shell(_K3S_UNINSTALL_AGENT, args.dry_run, "K3s agent uninstall")
        else:
            print(
                "ОШИБКА: не найден k3s-agent-uninstall.sh (это worker-нода с K3s?).",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        if _K3S_UNINSTALL_SERVER.is_file():
            _run_optional_shell(_K3S_UNINSTALL_SERVER, args.dry_run, "K3s server uninstall")
        elif _K3S_UNINSTALL_AGENT.is_file():
            print(
                "Найден только k3s-agent-uninstall.sh — выполняем его (роль worker?).",
                flush=True,
            )
            _run_optional_shell(_K3S_UNINSTALL_AGENT, args.dry_run, "K3s agent uninstall")
        elif args.dry_run:
            print("DRY-RUN: k3s-uninstall.sh (не найден на этом хосте — пропуск)", flush=True)
        else:
            print(
                "ОШИБКА: не найдены k3s-uninstall.sh / k3s-agent-uninstall.sh. "
                "K3s не установлен или нестандартный путь.",
                file=sys.stderr,
            )
            sys.exit(1)

    if not args.keep_opt_qm:
        _remove_opt_qm(args.dry_run, args.opt_qm_path)

    if args.dry_run:
        print("DRY-RUN завершён.", flush=True)
        return

    if args.no_reboot:
        print("Готово (--no-reboot). Перезагрузите сервер вручную перед новым bootstrap.", flush=True)
        return

    _reboot(dry_run=False)

