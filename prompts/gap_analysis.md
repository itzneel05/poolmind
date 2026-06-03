Analyze this cybersecurity resource pool for gaps and weaknesses.

Current pool stats:
{{POOL_STATS}}

Identify underserved domains, skill levels, resource types, and temporal gaps.
Suggest specific actions to fill each gap.

Return ONLY valid JSON:
```json
{
  "gaps": [
    {
      "domain": "<domain name>",
      "issue": "<what's missing or underserved>",
      "suggestion": "<specific action to fix>"
    }
  ],
  "priority_gaps": ["<domain: issue>"]
}
```
