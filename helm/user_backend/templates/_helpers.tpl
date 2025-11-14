{{- define "user-backend.name" -}}
{{ .Chart.Name }}
{{- end -}}

{{- define "user-backend.fullname" -}}
{{ printf "%s-%s" .Release.Name .Chart.Name }}
{{- end -}}

