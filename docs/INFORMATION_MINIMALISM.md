# Information Minimalism

Document what a skilled developer or LLM would need to work with the project — skip what they can derive from the code, structure, or naming.

## The 3-Question Test

Before writing documentation, answer these in order:

1. **Would a skilled developer need this?**
   - NO → Don't document.
   - YES → Continue to Q2.

2. **Is it obvious from the code, structure, or naming?**
   - YES → Don't document.
   - NO → Continue to Q3.

3. **Does it duplicate existing content?**
   - YES → Reference the existing source instead.
   - NO → Document it.

## What to Document

- Behavioral intent and domain knowledge
- Non-obvious "why" behind decisions
- Gotchas, quirks, and workarounds
- Constraint rationale

## What to Skip

- What the code does (read the code)
- Standard patterns and conventions
- Obvious parameters and return values
- Anything derivable from file names and structure

## Applied to SiteMapper

- Page YAML `gotchas` fields capture non-obvious behavior — this is the primary documentation surface.
- Workflow steps should be self-describing via their `description` field.
- Don't duplicate information between page maps and workflow steps.
- Schema files document their own structure via comments.
