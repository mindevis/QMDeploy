#!/usr/bin/env python3
"""
Обновляет helm/qm-project/values-argocd.yaml для GitOps без пина полного ref образа в images.*:
  imageTag: latest
  images.<service>: ""  → ghcr.io/<ghcrOwner>/<service>:latest
  imageRevisions.<service>: <тег из --image-ref> — меняет аннотацию pod, чтобы Argo выкатил новый digest.

Аргумент --image-ref: ghcr.io/org/name:tag — tag (short SHA, latest, semver) пишется в imageRevisions.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

VALID_SERVICES = frozenset({"qmdocs", "qmadmin", "qmweb", "qmserver", "qmnetwork", "qmsecret"})


def parse_image_tag(image_ref: str) -> str:
    if not image_ref or ":" not in image_ref:
        return ""
    return image_ref.rsplit(":", 1)[-1].strip()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--service",
        required=True,
        choices=sorted(VALID_SERVICES),
        help="Сервис, для которого обновить imageRevisions",
    )
    p.add_argument(
        "--image-ref",
        default="",
        help="Полная ссылка на образ (тег после последнего : попадёт в imageRevisions.<service>)",
    )
    p.add_argument(
        "--file",
        default="helm/qm-project/values-argocd.yaml",
        help="Путь относительно корня репозитория QMDeploy",
    )
    args = p.parse_args()

    try:
        from ruamel.yaml import YAML
    except ImportError:
        print("Нужен пакет ruamel.yaml: pip install -r scripts/requirements-gitops.txt", file=sys.stderr)
        sys.exit(1)

    root = Path(__file__).resolve().parent.parent
    path = root / args.file
    if not path.is_file():
        print(f"Файл не найден: {path}", file=sys.stderr)
        sys.exit(1)

    yaml = YAML()
    yaml.preserve_quotes = True
    text = path.read_text(encoding="utf-8")
    data = yaml.load(text) or {}

    data["imageTag"] = "latest"
    if not data.get("ghcrOwner"):
        data["ghcrOwner"] = "mindevis"
    if "images" not in data or data["images"] is None:
        data["images"] = {}
    for svc in sorted(VALID_SERVICES):
        data["images"][svc] = ""

    if "imageRevisions" not in data or data["imageRevisions"] is None:
        data["imageRevisions"] = {}
    for svc in sorted(VALID_SERVICES):
        data["imageRevisions"].setdefault(svc, "")
    tag = parse_image_tag(args.image_ref)
    if tag:
        data["imageRevisions"][args.service] = tag

    with path.open("w", encoding="utf-8") as fp:
        yaml.dump(data, fp)


if __name__ == "__main__":
    main()
