Generate a structured learning path from the available resources.

Goal: {{GOAL}}

Available resources:
{{POOL_RESOURCES}}

Create a week-by-week learning path. Each week should have 2-5 resources.
Order by skill_level progression. Include rationale for each resource selection.

Return ONLY valid JSON:
```json
{
  "path_name": "<descriptive name for this path>",
  "weeks": [
    {
      "label": "<Week 1: Foundation>",
      "resources": [
        {"id": "<resource id>", "title": "<exact title>", "rationale": "<why this resource first>"}
      ]
    }
  ]
}
```
