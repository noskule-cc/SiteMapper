# `projects/` — questions

A site holds maps and building blocks. A project holds a **question**: any
workflow whose run is itself the deliverable — a test with a verdict, a producer
of a dataset, a report, a migration. If a workflow needs tiers, a schedule, a
kind or a run folder, it is a project workflow.

The projects tree may sit inside the lib's folder (this layout) or beside it in
a shared data tree (`data/projects` next to `data/SiteMapper`); the framework's
tools find either (`scripts/tree.py`). Group projects in folders; a folder with a
`project.yaml` is a project at any depth.

```
projects/
  <group>/group.yaml     optional: the group's name, description and order
  <group>/<project>/
    project.yaml         kind, app, the sites whose maps it reads, workflows, data, state, keep
    workflows/           <name>.yaml + <name>.md companion
    data/                reference data PEOPLE maintain — listed under `data:`
    scripts/             scripts only this project's workflows call
```

Formats: `schema/project.yaml`, `schema/group.yaml` in the framework repo. No
`results/` here: a run writes to the runs store (`schema/run.yaml`), never into
the tree, and `check.py` fails a results folder.

A workflow that must run on several tiers of one application is **one file**
here: it names the app's tiers under `tiers:`, takes the tier from its
`environment` parameter, and keys its fixtures by tier. Never a copy per site.

Reference data listed under `data:` is worth a note: keep lookup tables as YAML
the workflow reads, never as constants inside a script. Coverage changes; scripts
should not have to. What a run learns for the next run is `state:`, and lives in
the state store, not here.
