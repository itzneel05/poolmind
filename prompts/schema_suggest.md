Analyze current resource schema usage and suggest improvements.

Current schema version: {{SCHEMA_VERSION}}

Aggregated pool data across all resources suggests the following patterns:
- Fields commonly left empty
- Fields with high variance
- Emerging resource types not well captured

Return ONLY valid JSON:
```json
{
  "suggested_new_fields": [
    {"name": "<field name>", "type": "string|integer|boolean|list", "reasoning": "<why needed>"}
  ],
  "reasoning": "<summary of proposed changes>"
}
```
