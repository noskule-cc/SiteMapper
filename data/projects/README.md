# `projects/` — cross-site work

A project groups workflows that span more than one site, plus the reference data
and run outputs they need.

```
projects/<project>/
  project.yaml         description, the sites it spans, workflow + data listings
  workflows/           <name>.yaml + <name>.md companion
  <reference>.yaml     lookup tables the workflows read — listed under `data:`
  results/             run outputs — gitignored, see the repo's .gitignore
```

Format: `schema/project.yaml` in the framework repo.

A workflow belongs here rather than under `sites/` as soon as its steps run
against more than one site. Steps name the site they run on, and `capture:`
passes values between them — across sites, in one workflow.

Reference data listed under `data:` is worth a note: keep lookup tables as YAML
the workflow reads, never as constants inside a script. Coverage changes; scripts
should not have to.
