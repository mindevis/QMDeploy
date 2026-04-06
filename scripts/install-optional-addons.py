#!/usr/bin/env python3
"""
Опциональная установка Argo CD и MinIO (S3) через Helm 3 — отдельно от чарта qm-project.

Требуется: kubectl, Helm 3, доступ к кластеру.

Пример:

  chmod +x install-optional-addons.py
  ./install-optional-addons.py --argocd --s3
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
    return "1.0.0"


def helm_cmd(args: argparse.Namespace) -> list[str]:
    cmd = ["helm"]
    if args.kubeconfig:
        cmd.extend(["--kubeconfig", args.kubeconfig])
    return cmd


def ensure_helm() -> None:
    if not shutil.which("helm"):
        print("ОШИБКА: нужен Helm 3 (команда helm в PATH).", file=sys.stderr)
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
