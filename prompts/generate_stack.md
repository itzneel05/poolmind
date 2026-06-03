Build a resource stack for a specific mission from available resources.

Mission: {{MISSION}}

Available resources:
{{POOL_RESOURCES}}

A stack is a curated set of resources that together enable someone to
accomplish a specific mission. Include tools, tutorials, references, and labs.

Return ONLY valid JSON:
```json
{
  "stack_name": "<short name for this stack>",
  "description": "<what this stack enables>",
  "resources": [
    {"id": "<resource id>", "title": "<exact title>", "role": "<tool|reference|guide|lab>"}
  ]
}
```
