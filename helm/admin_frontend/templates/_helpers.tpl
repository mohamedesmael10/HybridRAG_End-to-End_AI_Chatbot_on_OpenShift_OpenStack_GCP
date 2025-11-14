{{- define "admin-frontend.name" -}}
{{ .Chart.Name }}
{{- end -}}

{{- define "admin-frontend.fullname" -}}
{{ printf "%s-%s" .Release.Name .Chart.Name }}
{{- end -}}

