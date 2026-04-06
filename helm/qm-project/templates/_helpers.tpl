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
Одна строка SMTP AUTH для boky/postfix: email:password.
Приоритет: существующий Secret smtp-relay-auth → smtpRelayUsersPlain в values → детерминированный пароль (sha256).
*/}}
{{- define "qm.smtpRelayUsersLine" -}}
{{- $email := .Values.smtpRelay.relayUserEmail | default "noreply@qx-dev.ru" -}}
{{- $ns := .Release.Namespace -}}
{{- $sec := lookup "v1" "Secret" $ns "smtp-relay-auth" -}}
{{- if and $sec (index $sec.data "SMTP_RELAY_USERS") -}}
{{- index $sec.data "SMTP_RELAY_USERS" | b64dec -}}
{{- else if .Values.smtpRelay.smtpRelayUsersPlain -}}
{{- .Values.smtpRelay.smtpRelayUsersPlain -}}
{{- else -}}
{{- $hash := sha256sum (printf "%s|%s|%s" .Release.Name $ns $email) -}}
{{- printf "%s:%s" $email (trunc 32 $hash) -}}
{{- end -}}
{{- end }}
