Parse this natural language search query into structured filters.

Query: {{QUERY}}

Available domains: web, network, mobile, cloud, api, wireless, iot, osint, soc, blueteam, redteam, purpleteam, malware, forensics, cryptography, reverse_engineering, exploit_dev, social_engineering, physical, governance, privacy, ai_security, supply_chain, devsecops, identity, blockchain, ics_ot, career, general

Available skill levels: beginner, intermediate, advanced, expert, all
Available formats: text, video, interactive, audio, tool, hands-on, mixed
Available costs: free, freemium, paid, one-time, subscription
Available types: article, tutorial, writeup, tool, repository, cheatsheet, book, course, video, lab, paper, other

Return ONLY valid JSON:
```json
{
  "domain": "<domain or null>",
  "subdomain": "<specific topic or null>",
  "skill_level": "<level or null>",
  "type": "<type or null>",
  "format": "<format or null>",
  "cost": "<cost or null>",
  "time_to_value_max_minutes": <integer or null>,
  "keywords": ["keyword1", "keyword2"],
  "confidence": <integer 0-100>
}
```
