{{- /* helpers for user-frontend chart */ -}}

{{- define "user-frontend.name" -}}
{{ .Chart.Name }}
{{- end -}}

{{- define "user-frontend.fullname" -}}
{{ printf "%s-%s" .Release.Name .Chart.Name }}
{{- end -}}

{{- /* stable selector labels (must match existing Deployment if already created) */ -}}
{{- define "user-frontend.selectorLabels" -}}
app: esmael-user-frontend-user-frontend
{{- end -}}
