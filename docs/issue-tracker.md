# Issue Tracker

Project management using GitHub Issues. Adopted from the aiDocs framework.

**Proposals, open decisions and planned work live here — not in the repo.** There
is no `docs/proposals/` folder: a decision not yet made is an issue, so it has one
home, a discussion thread and a close state. See `KNOWLEDGE_PLACEMENT.md`.

## Conventions

Types, labels and fields are discoverable via the GitHub API. These rules aren't:

1. **Use issue types** for classification — not labels
2. **Use labels** for the feature area the issue touches
3. **Label the feature, not the data.** Most issues need one label
4. **Use the sub-issue feature** to link children to epics
5. **Set the estimate** — Fibonacci (1, 2, 3, 5, 8, 13), stated in the body
6. **Title format** — imperative verb + concise description
7. **Epic estimate** — sum of its sub-issue estimates

### Estimate scale

| Points | Complexity                                         |
|--------|----------------------------------------------------|
| 1      | Trivial — config change, copy fix                  |
| 2      | Small — single file, data already available        |
| 3      | Medium — new component, aggregation logic          |
| 5      | Large — schema migration, new data capture, multi-file |
| 8      | XL — architectural change, cross-cutting concern   |
| 13     | XXL — epic-scale, should probably be split         |

### Available types

`Task` · `Bug` · `Feature` · `Spike` · `Documentation` · `Story` · `Refactor` ·
`Epic` · `Idea`

Set the type with the GraphQL API — the `gh` CLI has no `--type` flag:

```bash
gh api graphql -f query='mutation{updateIssue(input:{
  id:"<issue-node-id>", issueTypeId:"<type-id>"}){issue{number issueType{name}}}}'
```

Look both ids up with:

```bash
gh api graphql -f query='{repository(owner:"noskule-cc",name:"SiteMapper"){
  issueTypes(first:20){nodes{id name}} issue(number:N){id}}}'
```

## Differences from the aiDocs baseline

- **No Projects v2 board.** The aiDocs rules "add every issue to the project" and
  "set sprint status to Backlog" do not apply until one exists. Estimates go in
  the issue body instead of a project field.
- **No wiki.** The aiDocs rule "update wiki when closing issues that add
  significant functionality" maps here to updating the affected map, workflow
  companion `.md`, or `results/` record.
