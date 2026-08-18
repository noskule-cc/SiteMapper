# `data/` — the scaffold for your own map repository

**Nothing real goes in this folder.** It is a copyable skeleton, committed to the
public framework repo so the split it describes is a thing you can run rather
than a paragraph you have to follow.

## Why there are two repositories

The framework — schema, docs, checks, and `sites/sitemapper-demo` — is generic
and public. A map of a *real* application is not. It describes somebody's
internal systems: page structure, API endpoints, account identifiers, and the
gotchas that only exist in production. Its run outputs are worse: customer
names, device serials, mail bodies, employee records.

So maps and runs live in a private repository of your own, laid out exactly like
this one. Same paths, same schema, same tooling — only the access control
differs.

## Bootstrapping

```bash
# 1. copy this skeleton out, next to the framework checkout
cp -r data ../my-maps && cd ../my-maps

# 2. it is a repository in its own right
mv gitignore.template .gitignore
git init -b main && git add -A && git commit -m "Initial map repository"

# 3. create it PRIVATE, and check that it is
gh repo create <owner>/my-maps --private --source . --push
gh repo view <owner>/my-maps --json visibility
```

Then fill in `config.yaml`, write your rules into `docs/guardrails.md`, and map
your first site with `/map-site`. `schema/*.yaml` in the framework repo is the
format reference for everything you write.

## Layout

```
my-maps/                       (private)
  config.yaml                  settings.contact, settings.mailboxes
  docs/guardrails.md           your standing rules
  sites/<site>/                site.yaml, pages/, workflows/, scripts/, results/
  projects/<project>/          cross-site workflows, data, results/
```

## The two rules that make the split hold

Both are mechanical, because a rule that depends on remembering is a rule that
fails on a Friday afternoon.

**Identity is referenced, never written.** A map says `mailboxes.customer_a` and
`settings.contact.email`; the values resolve from `config.yaml` in the private
repo. So a map file never contains an address or a phone number, and one that
does is visibly wrong. See `schema/settings.yaml`.

**Run outputs are excluded as a class.** `gitignore.template` excludes every
`results/` directory outright, not one path at a time. A new project's runs are
private by default rather than committed and reviewed afterwards — which is
exactly the failure this layout exists to prevent.
