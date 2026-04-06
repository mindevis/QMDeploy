#!/usr/bin/env python3
"""
Опциональная установка Argo CD и MinIO (S3) через Helm 3 — отдельно от чарта qm-project.

Требуется: kubectl, Helm 3, доступ к кластеру.

Пример:

  chmod +x install-optional-addons.py
  ./install-optional-addons.py --argocd --s3
  ./install-optional-addons.py --argocd --argocd-skip-qm-app   # только Argo CD без Application qm
  ./install-optional-addons.py --s3 --minio-root-password 'секрет'
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _deploy_semver() -> str:
    """Semver из deploy/VERSION (обход вверх по каталогам). Fallback — если файла нет."""
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        vf = d / "VERSION"
        if vf.is_file():
            return vf.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return "1.2.0"


def helm_cmd(args: argparse.Namespace) -> list[str]:
    cmd = ["helm"]
    if args.kubeconfig:
        cmd.extend(["--kubeconfig", args.kubeconfig])
    return cmd


def kubectl_cmd(args: argparse.Namespace) -> list[str]:
    cmd = ["kubectl"]
    if args.kubeconfig:
        cmd.extend(["--kubeconfig", args.kubeconfig])
    return cmd


def ensure_helm() -> None:
    if not shutil.which("helm"):
        print("ОШИБКА: нужен Helm 3 (команда helm в PATH).", file=sys.stderr)
        sys.exit(1)


def ensure_kubectl() -> None:
    if not shutil.which("kubectl"):
        print("ОШИБКА: нужен kubectl (команда kubectl в PATH).", file=sys.stderr)
        sys.exit(1)


def run(cmd: list[str], check: bool = True) -> None:
    subprocess.run(cmd, check=check)


def install_argocd(args: argparse.Namespace) -> None:
    h = helm_cmd(args)
    run([*h, "repo", "add", "argo", "https://argoproj.github.io/argo-helm"], check=False)
    run([*h, "repo", "update"])
    ver: list[str] = []
    if args.argocd_chart_version:
        ver = ["--version", args.argocd_chart_version]
    values_file = (
        Path(__file__).resolve().parent.parent / "helm" / "argocd" / "values-k3s.yaml"
    )
    if not values_file.is_file():
        print(f"ОШИБКА: нет файла Helm values: {values_file}", file=sys.stderr)
        sys.exit(1)
    print("Helm: установка Argo CD (namespace argocd) …", flush=True)
    run(
        [
            *h,
            "upgrade",
            "--install",
            "argocd",
            "argo/argo-cd",
            "-n",
            "argocd",
            "--create-namespace",
            "-f",
            str(values_file),
            "--set",
            f"global.domain={args.argocd_host}",
            "--wait",
            "--timeout",
            "15m",
            *ver,
        ]
    )
    print(
        f"Argo CD UI: https://{args.argocd_host}/ — пароль admin: "
        "kubectl -n argocd get secret argocd-initial-admin-secret "
        "-o jsonpath='{.data.password}' | base64 -d && echo",
        flush=True,
    )
    apply_argocd_qm_application(args)


def apply_argocd_qm_application(args: argparse.Namespace) -> None:
    """Регистрирует в Argo CD Application «qm» на чарт qm-project из Git."""
    if args.argocd_skip_qm_app:
        print("Пропуск Application qm (--argocd-skip-qm-app).", flush=True)
        return
    ensure_kubectl()
    tpl = (
        Path(__file__).resolve().parent.parent
        / "helm"
        / "argocd"
        / "applications"
        / "qm-project.application.yaml.tpl"
    )
    if not tpl.is_file():
        print(f"ОШИБКА: нет шаблона Application: {tpl}", file=sys.stderr)
        sys.exit(1)
    text = tpl.read_text(encoding="utf-8")
    text = text.replace("__QM_DEPLOY_REPO__", args.qm_repo_url)
    text = text.replace("__QM_GIT_REVISION__", args.qm_repo_revision)
    text = text.replace("__QM_NAMESPACE__", args.qm_namespace)
    print(
        "kubectl: Application argocd/qm (Helm qm-project из Git, синхронизация с кластером) …",
        flush=True,
    )
    subprocess.run(
        [*kubectl_cmd(args), "apply", "-f", "-"],
        input=text.encode("utf-8"),
        check=True,
    )
    print(
        f"В UI Argo CD появится приложение «qm». Секреты qm-mysql / qm-app создайте в namespace "
        f"{args.qm_namespace} (чарт их не создаёт).",
        flush=True,
    )


def install_minio(args: argparse.Namespace) -> None:
    h = helm_cmd(args)
    run([*h, "repo", "add", "bitnami", "https://charts.bitnami.com/bitnami"], check=False)
    run([*h, "repo", "update"])
    extra: list[str] = ["--set", f"auth.rootUser={args.minio_root_user}"]
    if args.minio_root_password:
        extra.extend(["--set", f"auth.rootPassword={args.minio_root_password}"])
    print(f"Helm: установка MinIO (namespace {args.minio_namespace}) …", flush=True)
    run(
        [
            *h,
            "upgrade",
            "--install",
            "minio",
            "bitnami/minio",
            "-n",
            args.minio_namespace,
            "--create-namespace",
            "--wait",
            "--timeout",
            "15m",
            *extra,
        ]
    )
    print(
        f"MinIO: сервис minio.{args.minio_namespace}.svc.cluster.local (порты см. helm status). "
        "Учётные данные — см. вывод chart или secret.",
        flush=True,
    )


def main() -> None:
    p = argparse.ArgumentParser(
        description="Helm: опционально Argo CD и/или MinIO (S3). Нужен хотя бы один флаг --argocd | --s3."
    )
    p.add_argument("--argocd", action="store_true", help="Argo CD (chart argo/argo-cd, ns argocd)")
    p.add_argument("--s3", action="store_true", help="MinIO S3 (chart bitnami/minio)")
    p.add_argument("--kubeconfig", help="Kubeconfig для helm/kubectl")
    p.add_argument(
        "--argocd-host",
        default="k3s.qx-dev.ru",
        help="FQDN Argo CD (global.domain, Ingress; по умолчанию k3s.qx-dev.ru)",
    )
    p.add_argument("--argocd-chart-version", help="Версия Helm-чарта argo-cd")
    p.add_argument(
        "--argocd-skip-qm-app",
        action="store_true",
        help="Не создавать Application qm в Argo CD (только установка Argo CD)",
    )
    p.add_argument(
        "--qm-repo-url",
        default="https://github.com/mindevis/QMDeploy.git",
        help="Git QMDeploy для Application qm (публичный HTTPS или зарегистрированный в Argo CD)",
    )
    p.add_argument(
        "--qm-repo-revision",
        default="main",
        help="Ветка или тег QMDeploy (Argo targetRevision)",
    )
    p.add_argument(
        "--qm-namespace",
        default="qm",
        help="Namespace релиза QM (destination Application)",
    )
    p.add_argument("--minio-namespace", default="minio", help="Namespace для MinIO")
    p.add_argument("--minio-root-user", default="minioadmin")
    p.add_argument("--minio-root-password", help="Пароль root MinIO (Bitnami: auth.rootPassword)")
    p.add_argument("--dry-run", action="store_true", help="Только описание шагов")
    p.add_argument(
        "--deploy-version",
        action="store_true",
        help="Вывести semver Kubernetes deploy bundle (deploy/VERSION) и выйти",
    )
    args = p.parse_args()
    if args.deploy_version:
        print(_deploy_semver())
        return
    if not args.argocd and not args.s3:
        print("Укажите хотя бы один флаг: --argocd или --s3", file=sys.stderr)
        sys.exit(1)
    if args.dry_run:
        if args.argocd:
            vf = Path(__file__).resolve().parent.parent / "helm" / "argocd" / "values-k3s.yaml"
            print(
                "DRY-RUN: helm upgrade --install argocd argo/argo-cd -n argocd --create-namespace "
                f"-f {vf} --set global.domain={args.argocd_host}"
            )
            if not args.argocd_skip_qm_app:
                print(
                    "DRY-RUN: kubectl apply -f -  # Application argocd/qm из "
                    "helm/argocd/applications/qm-project.application.yaml.tpl "
                    f"(repo={args.qm_repo_url}, revision={args.qm_repo_revision}, "
                    f"namespace={args.qm_namespace})"
                )
        if args.s3:
            print(
                f"DRY-RUN: helm upgrade --install minio bitnami/minio -n {args.minio_namespace} --create-namespace"
            )
        sys.exit(0)
    ensure_helm()
    if args.argocd:
        install_argocd(args)
    if args.s3:
        install_minio(args)


if __name__ == "__main__":
    main()
