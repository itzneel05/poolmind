Given a newly added resource, suggest related resources from the existing pool.

New resource:
- Title: {{TITLE}}
- Domain: {{DOMAIN}}

Existing pool (sample):
{{POOL_TITLES}}

Return ONLY valid JSON:
```json
{
  "related_titles": ["<exact title from pool>", "<exact title from pool>"],
  "next_step_title": "<exact title of the most logical next resource to study after this one, or null>",
  "confidence": <integer 0-100>
}
```

Only suggest titles that exist EXACTLY in the pool list above.
