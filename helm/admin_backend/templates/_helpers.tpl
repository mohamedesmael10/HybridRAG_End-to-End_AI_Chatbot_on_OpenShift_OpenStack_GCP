{{- define "admin-backend.name" -}}
{{ .Chart.Name }}
{{- end -}}

{{- define "admin-backend.fullname" -}}
{{ printf "%s-%s" .Release.Name .Chart.Name }}
{{- end -}}

