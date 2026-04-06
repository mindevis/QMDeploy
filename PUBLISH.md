# Вынести QMDeploy в отдельный репозиторий

1. На GitHub создайте пустой репозиторий **`QMDeploy`** (без README, если копируете готовое дерево).

2. В каталоге **`QMDeploy`** (этот репозиторий):

```bash
cd QMDeploy
git init -b main
git add .
git commit -m "chore: initial QMDeploy (Helm + K3s scripts)"
git remote add origin git@github.com:mindevis/QMDeploy.git
git push -u origin main
```

3. В **монорепозитории QMProject** удалите встроенную папку **`QMDeploy`** из индекса (если она была закоммичена как обычные файлы) и подключите submodule:

```bash
cd /path/to/QMProject
git rm -r --cached QMDeploy 2>/dev/null || true
rm -rf QMDeploy
git submodule add git@github.com:mindevis/QMDeploy.git QMDeploy
git add .gitmodules QMDeploy
git commit -m "chore: add QMDeploy submodule"
```

4. Релизы: аннотированный тег **`vX.Y.Z`** на коммите, где **`VERSION`** и **`Chart.yaml`** совпадают с номером релиза.
