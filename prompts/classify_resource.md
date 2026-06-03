You are a cybersecurity resource classifier. Classify the resource below.

Resource:
- Title: {{TITLE}}
- URL: {{URL}}
- Text snippet: {{TEXT_SNIPPET}}

Return ONLY valid JSON with this exact structure:
```json
{
  "type": "<one of: article|tutorial|writeup|tool|repository|cheatsheet|book|course|video|playlist|paper|report|dataset|lab|ctf|framework|table|index|ranking|note|thread|newsletter|podcast|interview|config|template|extension|dashboard|search_engine|api|community|event|certification|glossary|mindmap|other>",
  "domain": "<one of: web|network|mobile|cloud|api|wireless|iot|osint|soc|blueteam|redteam|purpleteam|malware|forensics|cryptography|reverse_engineering|exploit_dev|social_engineering|physical|governance|privacy|ai_security|supply_chain|devsecops|identity|blockchain|ics_ot|career|general>",
  "subdomain": "<specific vulnerability or technology, or null>",
  "skill_level": "<beginner|intermediate|advanced|expert|all>",
  "format": "<text|video|interactive|audio|tool|hands-on|mixed>",
  "temporal_relevance": "<evergreen|time-sensitive|historical|emerging>",
  "time_to_value": "<5min|30min|2hr|1day|1week+>",
  "cost": "<free|freemium|paid|one-time|subscription>",
  "confidence": <integer 0-100>
}
```
