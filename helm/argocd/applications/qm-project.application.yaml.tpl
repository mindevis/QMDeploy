# Шаблон: плейсхолдеры подставляет k8s-manage.py addons (GitOps bootstrap).
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: qm
  namespace: argocd
  labels:
    app.kubernetes.io/name: qm-project
    app.kubernetes.io/part-of: qm
spec:
  project: default
  source:
    repoURL: __QM_DEPLOY_REPO__
    targetRevision: __QM_GIT_REVISION__
    path: helm/qm-project
    helm:
      releaseName: qm
      valueFiles:
        - values-argocd.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: __QM_NAMESPACE__
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
