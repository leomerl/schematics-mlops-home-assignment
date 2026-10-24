{{- define "bl-ranker.labels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/part-of: bl-ranker
{{- end }}

{{- define "bl-ranker.image" -}}
image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
imagePullPolicy: {{ .Values.image.pullPolicy }}
{{- end }}

{{- define "bl-ranker.podSecurity" -}}
securityContext:
  runAsNonRoot: true
  runAsUser: {{ .Values.podUser }}
  fsGroup: {{ .Values.podUser }}
{{- end }}

{{- define "bl-ranker.secretEnv" -}}
- name: {{ .key }}
  valueFrom:
    secretKeyRef:
      name: {{ .root.Values.secretName }}
      key: {{ .key }}
      optional: true
{{- end }}

{{- define "bl-ranker.registryEnv" -}}
{{- if .Values.databricks.enabled }}
- name: MLFLOW_TRACKING_URI
  value: databricks
- name: MLFLOW_REGISTRY_URI
  value: databricks-uc
- name: DATABRICKS_HOST
  value: {{ .Values.databricks.host | quote }}
{{ include "bl-ranker.secretEnv" (dict "root" . "key" "DATABRICKS_TOKEN") }}
- name: REGISTERED_MODEL_NAME
  value: {{ .Values.databricks.modelName | quote }}
{{- else }}
- name: MLFLOW_TRACKING_URI
  value: "http://mlflow:{{ .Values.mlflow.port }}"
- name: REGISTERED_MODEL_NAME
  value: {{ .Values.registry.modelName | quote }}
{{- end }}
{{- end }}

{{- define "bl-ranker.gitopsEnv" -}}
- name: GITOPS_REPO_URL
  value: {{ .Values.gitops.repoUrl | quote }}
- name: GITOPS_BRANCH
  value: {{ .Values.gitops.branch | quote }}
- name: GITOPS_MODELS_FILE
  value: {{ .Values.gitops.modelsFile | quote }}
{{ include "bl-ranker.secretEnv" (dict "root" . "key" "GITOPS_TOKEN") }}
{{- end }}
