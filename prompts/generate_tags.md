Generate cybersecurity tags for this resource.

Title: {{TITLE}}
Domain: {{DOMAIN}}
Type: {{TYPE}}
Content: {{BODY_TEXT}}

Rules:
- Generate 5-15 tags
- All lowercase, hyphenated (e.g. sql-injection, not SQLi)
- Include: vulnerability types, tools, techniques, platforms, frameworks
- No generic tags like "security" or "hacking" unless truly relevant

Return ONLY valid JSON:
```json
{
  "tags": ["tag1", "tag2", "tag3"],
  "confidence": <integer 0-100>
}
```
