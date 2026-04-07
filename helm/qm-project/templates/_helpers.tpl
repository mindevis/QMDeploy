{{/*
Full container image: ghcr.io/<owner>/<name>:<tag> or images.<name> override.
Names: qmserver, qmadmin, qmweb, qmdocs, qmnetwork, qmsecret
*/}}
{{- define "qm.image" -}}
{{- $root := index . 0 -}}
{{- $svc := index . 1 -}}
{{- $override := index $root.Values.images $svc -}}
{{- if and $override (ne $override "") -}}
{{- $override -}}
{{- else -}}
{{- printf "ghcr.io/%s/%s:%s" $root.Values.ghcrOwner $svc $root.Values.imageTag -}}
{{- end -}}
{{- end }}

{{/*
imagePullPolicy: rolling tags like :latest / :free-latest must use Always or kubelet keeps stale layers.
*/}}
{{- define "qm.imagePullPolicy" -}}
{{- $img := . -}}
{{- if or (contains ":latest" $img) (contains ":free-latest" $img) -}}
Always
{{- else -}}
IfNotPresent
{{- end -}}
{{- end }}

{{- define "qm.labels" -}}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: qm-project
{{- end }}

{{/*
Аннотация pod template: меняется CI bump (imageRevisions.<svc>) при том же image:…:latest,
чтобы Argo CD и Kubernetes сделали rollout и подтянули новый digest из GHCR.
*/}}
{{- define "qm.podImageRevisionBlock" -}}
{{- $root := index . 0 }}
{{- $svc := index . 1 }}
{{- $r := index ($root.Values.imageRevisions | default dict) $svc }}
{{- if $r }}
      annotations:
        qm-project.io/image-revision: {{ $r | quote }}
{{- end }}
{{- end }}

{{/*
Defaults for qmnetwork when .Values.qmnetwork is missing (e.g. helm upgrade --reuse-values after chart added qmnetwork).
*/}}
{{- define "qm.qmnetwork.defaultResources" -}}
requests:
  cpu: 25m
  memory: 32Mi
limits:
  cpu: 500m
  memory: 256Mi
{{- end }}

{{/*
Пароль SMTP AUTH для relay/QMNetwork (без user:).
Приоритет: ключ QMNETWORK_SMTP_PASSWORD в smtp-relay-auth → разбор SMTP_RELAY_USERS → smtpRelayUsersPlain → sha256(release|ns|email) первые 32 hex.
*/}}
{{- define "qm.smtpRelayPasswordPlain" -}}
{{- $email := .Values.smtpRelay.relayUserEmail | default "noreply@qx-dev.ru" -}}
{{- $ns := .Release.Namespace -}}
{{- $sec := lookup "v1" "Secret" $ns "smtp-relay-auth" -}}
{{- if and $sec (index $sec.data "QMNETWORK_SMTP_PASSWORD") -}}
{{- index $sec.data "QMNETWORK_SMTP_PASSWORD" | b64dec -}}
{{- else if and $sec (index $sec.data "SMTP_RELAY_USERS") -}}
{{- $line := index $sec.data "SMTP_RELAY_USERS" | b64dec | trim -}}
{{- $m := regexFindSubmatch "^(.+?):(.+)$" $line -}}
{{- if and $m (ge (len $m) 3) -}}
{{- index $m 2 -}}
{{- else -}}
{{- $hash := sha256sum (printf "%s|%s|%s" .Release.Name $ns $email) -}}
{{- trunc 32 $hash -}}
{{- end -}}
{{- else if .Values.smtpRelay.smtpRelayUsersPlain -}}
{{- $line := .Values.smtpRelay.smtpRelayUsersPlain | trim -}}
{{- $prefix := printf "%s:" $email -}}
{{- if hasPrefix $prefix $line -}}
{{- trimPrefix $prefix $line -}}
{{- else -}}
{{- $m := regexFindSubmatch "^(.+?):(.+)$" $line -}}
{{- if and $m (ge (len $m) 3) -}}
{{- index $m 2 -}}
{{- else -}}
{{- $hash := sha256sum (printf "%s|%s|%s" .Release.Name $ns $email) -}}
{{- trunc 32 $hash -}}
{{- end -}}
{{- end -}}
{{- else -}}
{{- $hash := sha256sum (printf "%s|%s|%s" .Release.Name $ns $email) -}}
{{- trunc 32 $hash -}}
{{- end -}}
{{- end }}

{{/*
Одна строка SMTP AUTH для boky/postfix: текущий relayUserEmail + пароль из qm.smtpRelayPasswordPlain.
*/}}
{{- define "qm.smtpRelayUsersLine" -}}
{{- $email := .Values.smtpRelay.relayUserEmail | default "noreply@qx-dev.ru" -}}
{{- printf "%s:%s" $email (include "qm.smtpRelayPasswordPlain" .) -}}
{{- end }}
