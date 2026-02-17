You are generating a GitHub Pull Request description.

Based on:
1. The GitHub Issue description
2. The actual code changes made (files added/modified/removed)
3. The feature behavior after implementation

Generate a clean, professional PR description in Markdown with the following strict structure:

# Summary
- Clearly explain what problem this PR solves.
- Describe what was added/changed at a functional level (not just files).
- Mention backward compatibility if applicable.
- Keep it concise but technically precise.

# Changes
- Group changes logically (Feature Additions, Backend Changes, UI Changes, Database Changes, etc.).
- For each modified file, briefly explain *what changed and why*.
- Avoid raw diffs — summarize intent.

# Behavior Details (if applicable)
- Explain how the system behaves before vs after.
- Mention defaults, fallbacks, config changes, flags, environment variables, etc.

# Test Plan
This section must be thorough and practical.

Follow these rules:
- Use Markdown checkboxes (- [ ])
- Cover happy path, edge cases, and regression validation.
- Include negative tests if relevant.
- Include backward compatibility validation.
- Include persistence/config validation if settings are involved.
- Include logs validation if retries, toggles, or backend behavior changed.
- Ensure steps are reproducible and verifiable.
- Do NOT write vague items like "Test feature works".
- Write test steps that a reviewer can actually execute.

If performance or metrics are involved:
- Include validation of output format.
- Include validation of generated artifacts (JSON, logs, DB tables, etc.)

If UI changes are involved:
- Verify visibility, placement, defaults, persistence, and interaction behavior.

If database changes are involved:
- Verify schema updates
- Verify data correctness
- Verify existing data not broken

If API changes are involved:
- Verify request/response structure
- Verify backward compatibility when new fields are missing

# Output (if applicable)
- Mention generated artifacts (files, logs, reports, tables).
- Mention where they are stored.

Constraints:
- Keep language professional and concise.
- No emojis.
- No marketing language.
- No unnecessary verbosity.
- Assume reviewer is technical.
- Format must be clean GitHub-ready Markdown.
