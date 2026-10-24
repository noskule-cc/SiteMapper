#!/usr/bin/env python3
"""Check that the repo is internally consistent. Exits non-zero on any failure.

Usage:
    python scripts/check.py                    # run everything, on this repo
    python scripts/check.py --only links       # run one check
    python scripts/check.py --list             # show check names
    python scripts/check.py --root ../my-maps  # check a separate map repository
    python scripts/check.py --root data/SiteMapper --projects data/projects

`--root` exists because the maps this was written to protect usually live in a
different (private) repository. Schemas and bindings still come from THIS repo —
see the two-roots note below — so there is one tool and one schema, not a copy
per map repo that drifts out of sync. `--projects` points at the projects tree
when it is not inside the root (scripts/tree.py says how it is found without
the flag).

Every check here exists because the thing it catches actually happened. None of
them need an LLM: they are enumeration and comparison, which is code's job (see
docs/code-over-llm.md). What this CANNOT check is whether prose is still true —
that still needs a human reading it.

Add a check when you find a class of drift that a script could have caught.
"""
import argparse
import glob
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not installed. Run: python -m pip install pyyaml")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree  # noqa: E402

# TWO ROOTS, DELIBERATELY.
#
# HOME is this script's own repository: the framework. It owns schema/*.yaml,
# docs/ and the .claude bindings, and those do NOT travel with a map repository.
# ROOT is the tree being checked, which defaults to HOME and is repointed by
# --root at a separate (usually private) repository of maps.
#
# The distinction matters because the alternative is to copy this script and the
# schemas next to the maps, and a FORKED SCHEMA IS WORSE THAN NO CHECK: the copy
# drifts, the maps validate green against a contract nobody updated, and the
# check reports health it cannot know about. One tool, many trees.
#
# PROJECTS is the third: the projects tree, inside ROOT or beside it
# (scripts/tree.py). Paths under it are reported relative to ROOT.
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = HOME
PROJECTS = tree.projects_root(ROOT)

# Where the user actually stood when they typed the command. Captured BEFORE the
# chdir below, because a relative --root has to resolve against the shell's cwd,
# not against this repo. Getting that wrong is not a small bug: `--root .` from a
# map repository resolved to the framework instead and reported it green, which
# is a check lying about a tree it never looked at.
INVOCATION_CWD = os.getcwd()

os.chdir(ROOT)


def home(*parts):
    """A path inside the framework repo, wherever ROOT currently points."""
    return norm(os.path.join(HOME, *parts))


def external():
    return os.path.abspath(ROOT) != os.path.abspath(HOME)

NOTES = []
# Checks that declined to run. Reported as 'skipped', never as 'ok' — a check
# that did not run must not read like one that passed.
SKIPPED = set()

DOC_GLOBS = ["README.md", "USAGE.md", "PRD.md", "Concept.md", "CLAUDE.md",
             "AGENTS.md", "docs/**/*.md"]

# Standardized aiDocs per-project docs. The fixed standard files (INDEX.md,
# AGENTS.md, README.md) link to all of them; a project legitimately declines
# the ones it has no surface for and records the decision in project-index.md.
# A link to a declined file is a note, not a failure — same rule as
# docs/tools/check-docs.py, so the two tools never disagree.
PER_PROJECT_DOCS = {
    "installation.md", "development.md", "testing.md", "release.md",
    "changelog.md", "architecture-rules.md",
    "issue-tracker.md", "wiki.md", "design-sync.md", "project-index.md",
    "skills-and-agents.md", "tools/jobs.md", "feature-map.md",
    "tools/evals.md",
}


def norm(p):
    return p.replace("\\", "/")


def show(p):
    """How a path is reported: relative to ROOT, even when it lies beside it."""
    return norm(os.path.relpath(p, ROOT))


def files(patterns):
    out = []
    for p in patterns:
        out += [norm(f) for f in glob.glob(p, recursive=True)]
    return sorted(set(out))


def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def top_keys(path, top):
    d = load(path)
    return set((d.get(top) or {}).keys())


def projects():
    """(rel, dir, project dict) for every project under PROJECTS."""
    out = []
    for rel, pd_ in tree.iter_projects(PROJECTS):
        py = os.path.join(pd_, "project.yaml")
        try:
            out.append((rel, norm(pd_), load(py).get("project") or {}))
        except yaml.YAMLError:
            continue  # check_yaml reports it
    return out


def site_workflows():
    return files(["sites/*/workflows/*.yaml"])


def project_workflows():
    """(path, project rel, project dict) for every project workflow."""
    out = []
    for rel, pd_, p in projects():
        for f in sorted(glob.glob(os.path.join(pd_, "workflows", "*.yaml"))):
            out.append((norm(f), rel, p))
    return out


def all_workflows():
    return site_workflows() + [f for f, _, _ in project_workflows()]


def apps():
    """(name, dir, app dict) for every app under ROOT/apps."""
    out = []
    for name, ad in tree.iter_apps(ROOT):
        try:
            out.append((name, norm(ad), load(os.path.join(ad, "app.yaml")).get("app") or {}))
        except yaml.YAMLError:
            continue
    return out


def site_environment(site_name):
    """settings.policy.environment as the runner resolves it: framework
    config.yaml, then the tree's config.yaml, then site.yaml — most specific
    wins (schema/settings.yaml). A site that sets nothing is the config's
    default tier, usually production."""
    sy = f"sites/{site_name}/site.yaml"
    if not os.path.exists(sy):
        return None
    env = None
    for cfg in (home("config.yaml"), "config.yaml"):
        if os.path.exists(cfg):
            env = ((((load(cfg).get("settings") or {}).get("policy")) or {})
                   .get("environment") or env)
    policy = ((load(sy).get("site") or {}).get("settings") or {}).get("policy") or {}
    return policy.get("environment") or env


def app_of_site(site_name):
    """(app name, tier) for a site that is a tier of an app, else (None, None)."""
    for name, _, a in apps():
        for tier, site in (a.get("tiers") or {}).items():
            if site == site_name:
                return name, tier
    return None, None


def tier_keys(w, tiers=None):
    """The fixture blocks that are keyed by tier: `common` and every dict-valued
    key that names a tier (of the given app, else any known tier name). A
    dict-valued fixture that is simply structured data (a table of expected
    rows) is not a block."""
    names = set(tiers or []) | set(tree.TIER_SYNONYMS)
    return {k for k, v in (w.get("fixtures") or {}).items()
            if isinstance(v, dict) and (k == "common" or k in names)}


def exists_cased(path):
    """os.path.exists is case-INSENSITIVE on Windows/NTFS, so a link whose case
    does not match the file resolves here and breaks on Linux CI or a
    case-sensitive volume. Compare against the real directory listing instead."""
    path = os.path.normpath(path)
    if not os.path.exists(path):
        return False
    parts = path.replace("\\", "/").split("/")
    cur = ""
    for i, part in enumerate(parts):
        if part in ("", ".", ".."):
            cur = os.path.join(cur, part) if cur else part
            continue
        try:
            entries = os.listdir(cur or ".")
        except OSError:
            return False
        if part not in entries:
            return False
        cur = os.path.join(cur, part) if cur else part
    return True


def strip_fences(text):
    """Markdown links inside code fences are examples, not references."""
    return re.sub(r"```.*?```", "", text, flags=re.S)


# --------------------------------------------------------------------------
# checks: each returns a list of failure strings
# --------------------------------------------------------------------------

def check_yaml():
    """Every YAML file parses."""
    fails = []
    targets = files(["config.yaml", "schema/*.yaml", "sites/**/*.yaml",
                     "apps/**/*.yaml", "data/**/*.yaml"])
    targets += [norm(f) for f in glob.glob(os.path.join(PROJECTS, "**", "*.yaml"),
                                           recursive=True)]
    for f in sorted(set(targets)):
        try:
            load(f)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            line = mark.line + 1 if mark else "?"
            fails.append(f"{show(f)}:{line}  {getattr(e, 'problem', e)}")
    return fails


def schema_map():
    """(top-level key, schema file in HOME, files under ROOT or PROJECTS)."""
    return [
        ("site", "schema/site.yaml", files(["sites/*/site.yaml"])),
        ("app", "schema/app.yaml", files(["apps/*/app.yaml"])),
        ("project", "schema/project.yaml",
         [norm(os.path.join(d, "project.yaml")) for _, d, _ in projects()]),
        ("group", "schema/group.yaml",
         [norm(os.path.join(d, "group.yaml")) for _, d, has in tree.iter_groups(PROJECTS) if has]),
        ("page", "schema/page.yaml", files(["sites/*/pages/*.yaml"])),
        ("persona", "schema/persona.yaml", files(["sites/*/personas/*.yaml"])),
        ("workflow", "schema/workflow.yaml", all_workflows()),
    ]


def check_schema():
    """Files use no top-level key the schema does not define, and vice versa.

    Shallow on purpose: the schemas are commented YAML templates, and those
    comments are real documentation. A key-set diff catches the drift we hit
    without forcing a rewrite to JSON Schema that would gut them.
    """
    fails = []
    for top, schema, paths in schema_map():
        # The schema is the framework's; the files are the checked tree's.
        schema = home(schema)
        if not os.path.exists(schema):
            fails.append(f"missing schema: {schema}")
            continue
        allowed = top_keys(schema, top)
        used = set()
        for f in paths:
            extra = top_keys(f, top) - allowed
            used |= top_keys(f, top)
            if extra:
                fails.append(f"{show(f)}: key(s) not in {schema}: {sorted(extra)}")
        unused = allowed - used
        if unused and paths:
            # Not a failure: an optional key written by tooling (verified_at) is
            # legitimately absent until that tooling has run. Worth surfacing so a
            # schema documenting something that never existed still gets noticed.
            NOTES.append(f"{schema}: defines key(s) no file currently uses: {sorted(unused)}")
    return fails


SECRET_REF = re.compile(r"env:\w+|keyring:[^/]+/.+")


def check_credentials():
    """Persona credential_ref values are env: or keyring: references, never a secret."""
    fails = []
    for f in files(["sites/*/personas/*.yaml"]):
        refs = ((load(f) or {}).get("persona") or {}).get("credential_ref") or {}
        if not isinstance(refs, dict):
            fails.append(f"{show(f)}: credential_ref is not a mapping of username and "
                         "password references (the value is not shown)")
            continue
        for key, ref in refs.items():
            if ref and not SECRET_REF.fullmatch(str(ref)):
                fails.append(f"{show(f)}: credential_ref.{key} is not an env: or keyring: "
                             "reference (the value is not shown)")
    return fails


def declared_scripts(d):
    return {x.get("name") for x in (d.get("scripts") or []) if isinstance(x, dict)}


def scripts_on_disk(folder):
    return {os.path.basename(f) for f in glob.glob(f"{folder}/scripts/*")
            if os.path.isfile(f) and os.path.basename(f) not in
            ("README.md", "requirements.txt")}


def check_listings():
    """site.yaml / project.yaml / app.yaml agree with what is on disk, and refs resolve."""
    fails = []
    for sd in sorted(glob.glob("sites/*")):
        sd = norm(sd)
        sy = f"{sd}/site.yaml"
        if not os.path.exists(sy):
            fails.append(f"{sd}: no site.yaml")
            continue
        s = load(sy).get("site") or {}
        for key, sub in (("pages", "pages"), ("workflows", "workflows")):
            listed = set(s.get(key) or [])
            actual = {os.path.basename(f) for f in glob.glob(f"{sd}/{sub}/*.yaml")}
            for m in sorted(listed - actual):
                fails.append(f"{sy}: {key} lists '{m}' but the file does not exist")
            for m in sorted(actual - listed):
                fails.append(f"{sy}: {sub}/{m} exists but is not listed under {key}")
        for m in sorted(declared_scripts(s) - scripts_on_disk(sd)):
            fails.append(f"{sy}: scripts declares '{m}' but the file does not exist")
        if not s.get("mapped_at"):
            fails.append(f"{sy}: no mapped_at")

    for name, ad, a in apps():
        ay = f"{ad}/app.yaml"
        for m in sorted(declared_scripts(a) - scripts_on_disk(ad)):
            fails.append(f"{show(ay)}: scripts declares '{m}' but the file does not exist")

    for rel, pd_, p in projects():
        py = f"{pd_}/project.yaml"
        listed = set(p.get("workflows") or [])
        actual = {os.path.basename(f) for f in glob.glob(f"{pd_}/workflows/*.yaml")}
        for m in sorted(listed - actual):
            fails.append(f"{show(py)}: workflows lists '{m}' but the file does not exist")
        for m in sorted(actual - listed):
            fails.append(f"{show(py)}: workflows/{m} exists but is not listed")
        for s in p.get("sites") or []:
            if not os.path.isdir(f"sites/{s}"):
                fails.append(f"{show(py)}: sites references '{s}', which is not a directory under sites/")
        for m in sorted(declared_scripts(p) - scripts_on_disk(pd_)):
            fails.append(f"{show(py)}: scripts declares '{m}' but the file does not exist")
        # People's input is in the folder; what runs learned is in the store.
        for d in p.get("data") or []:
            if not os.path.exists(os.path.join(pd_, str(d))):
                fails.append(f"{show(py)}: data lists '{d}' but the file does not exist")
        for st in p.get("state") or []:
            if os.path.exists(os.path.join(pd_, str(st))):
                fails.append(f"{show(py)}: state names '{st}', which exists in the project "
                             "folder — a run-written file lives in the state store, not in git")
        if p.get("kind") not in tree.PROJECT_KINDS:
            fails.append(f"{show(py)}: kind is '{p.get('kind') or ''}' — must be one of "
                         f"{', '.join(tree.PROJECT_KINDS)} (schema/project.yaml)")
        if p.get("kind") == "producer" and not p.get("dataset"):
            fails.append(f"{show(py)}: kind: producer but no `dataset` — a producer names what it writes")
        sched = p.get("schedule") or {}
        if sched and not (sched.get("every") and sched.get("instance")):
            fails.append(f"{show(py)}: schedule needs both `every` and `instance` "
                         "(the one machine that runs it)")
        if p.get("app") and p["app"] not in {n for n, _, _ in apps()}:
            fails.append(f"{show(py)}: app '{p['app']}' has no apps/{p['app']}/app.yaml")

    # workflow -> site references (this is what iot-portal broke)
    for f in all_workflows():
        w = load(f).get("workflow") or {}
        for s in (w.get("sites") or ([w.get("site")] if w.get("site") else [])):
            s = str(s)
            if s.startswith("$"):
                continue  # environment-parameterised; resolved at run time
            if not os.path.isdir(f"sites/{s}"):
                fails.append(f"{show(f)}: site '{s}' is not a directory under sites/")
        if not w.get("mode"):
            fails.append(f"{show(f)}: no `mode` — a runner cannot tell if this needs an LLM")
        if w.get("effect") not in tree.EFFECT_VALUES:
            fails.append(f"{show(f)}: effect is '{w.get('effect') or ''}' — must be one of "
                         f"{' | '.join(tree.EFFECT_VALUES)}; a missing one lets a writing "
                         "workflow skip the rollback check")
    return fails


def check_companions():
    """Every workflow YAML has its sibling .md (USAGE.md + schema require it)."""
    return [f"{show(f)}: no companion {os.path.basename(f)[:-5]}.md"
            for f in all_workflows() if not os.path.exists(f[:-5] + ".md")]


def check_apps():
    """An app's tiers are real sites whose environment agrees with the tier key.

    Three GG+connect tiers were three unrelated sites for a year; nothing could
    say they were one application. The app is that fact's one home, so it has
    to be right: every tier names an existing site, the site's own
    settings.policy.environment says the same tier, no site is a tier of two
    apps, and an app script is not also a site's script.
    """
    fails = []
    seen = {}
    site_scripts = {}
    for sd in glob.glob("sites/*"):
        s = load(f"{sd}/site.yaml").get("site") or {} if os.path.exists(f"{sd}/site.yaml") else {}
        for name in declared_scripts(s):
            site_scripts.setdefault(name, []).append(os.path.basename(sd))
    for name, ad, a in apps():
        ay = show(f"{ad}/app.yaml")
        tiers = a.get("tiers") or {}
        if not tiers:
            fails.append(f"{ay}: no tiers — an app is the map from tier to site")
        for tier, site in tiers.items():
            if not os.path.isdir(f"sites/{site}"):
                fails.append(f"{ay}: tier '{tier}' names '{site}', not a directory under sites/")
                continue
            if site in seen:
                fails.append(f"{ay}: site '{site}' is already a tier of app '{seen[site]}'")
            seen[site] = name
            env = site_environment(site)
            if tree.tier_name(env) != tree.tier_name(tier):
                fails.append(f"{ay}: tier '{tier}' is sites/{site}, whose "
                             f"settings.policy.environment is '{env or ''}' — the two must agree")
        ref = (a.get("parity") or {}).get("reference")
        if ref and ref not in tiers:
            fails.append(f"{ay}: parity.reference '{ref}' is not a tier of this app")
        for sc in declared_scripts(a):
            for site in site_scripts.get(sc, []):
                fails.append(f"{ay}: script '{sc}' is also declared by sites/{site}/site.yaml "
                             "— a name has one home")
    return fails


def check_placement():
    """A site workflow is a building block; what makes it a project workflow is not valid there.

    Five dev UI tests and a copy of a project's staging test sat under sites
    because nothing said where a test goes. The keys that express "on these
    tiers", "reads these maps" and "per tier" exist only for project
    workflows, so a test filed under a site cannot say what it needs and the
    author moves it. The same rule forbids a site workflow from naming
    another site to reach a script.
    """
    fails = []
    for f in site_workflows():
        w = load(f).get("workflow") or {}
        own = norm(f).split("/")[1]
        for key in ("tiers", "sites"):
            if w.get(key):
                fails.append(f"{show(f)}: `{key}` is a project-workflow key — a site workflow "
                             "is a building block of one site (schema/site.yaml)")
        if tier_keys(w, [t for _, _, a in apps() for t in (a.get("tiers") or {})]):
            fails.append(f"{show(f)}: tier-keyed fixtures belong to a project workflow with "
                         "`tiers` — a site workflow has one site")
        sites, _ = tree.step_sites(w)
        for s in sorted(sites - {own}):
            fails.append(f"{show(f)}: a step runs on '{s}', but this workflow belongs to "
                         f"'{own}' — a workflow that touches two sites is a project workflow")
    return fails


def check_tiers():
    """A workflow's `tiers` are the app's, complete, and the environment parameter matches.

    "Must exist and pass on every tier" was undeclarable: a workflow missing
    on one environment could be intent or accident. Now required ⊆ allowed ⊆
    the app's tiers, every other tier is in `absent` with a reason, the
    `environment` select offers exactly the allowed tiers, and a tier-keyed
    fixtures block exists for each of them.
    """
    fails = []
    app_tiers = {n: set((a.get("tiers") or {}).keys()) for n, _, a in apps()}
    for f, rel, p in project_workflows():
        w = load(f).get("workflow") or {}
        t = w.get("tiers")
        if not t:
            continue
        if not isinstance(t, dict):
            fails.append(f"{show(f)}: tiers must be a mapping with required/allowed/absent")
            continue
        app = p.get("app")
        if not app or app not in app_tiers:
            fails.append(f"{show(f)}: declares tiers but project '{rel}' names no existing `app`")
            continue
        required = set(t.get("required") or [])
        allowed = set(t.get("allowed") or required)
        absent = t.get("absent") or {}
        if not required:
            fails.append(f"{show(f)}: tiers.required is empty — name at least one tier")
        for x in sorted(required - allowed):
            fails.append(f"{show(f)}: tier '{x}' is required but not allowed")
        for x in sorted(allowed - app_tiers[app]):
            fails.append(f"{show(f)}: tier '{x}' is not a tier of app '{app}' "
                         f"({', '.join(sorted(app_tiers[app]))})")
        for x in sorted(app_tiers[app] - allowed - set(absent)):
            fails.append(f"{show(f)}: tier '{x}' of app '{app}' is neither allowed nor "
                         "declared absent with a reason — a missing counterpart is a decision")
        for x, why in absent.items():
            if x in allowed:
                fails.append(f"{show(f)}: tier '{x}' is both allowed and absent")
            if not why:
                fails.append(f"{show(f)}: tiers.absent.{x} has no reason")
        params = {p_.get("name"): p_ for p_ in (w.get("parameters") or []) if isinstance(p_, dict)}
        env = params.get("environment")
        if not env or env.get("type") != "select":
            fails.append(f"{show(f)}: declares tiers but has no `environment` select parameter")
        elif set(env.get("options") or []) != allowed:
            fails.append(f"{show(f)}: environment options {sorted(env.get('options') or [])} "
                         f"differ from tiers.allowed {sorted(allowed)}")
        keyed = tier_keys(w, app_tiers[app]) - {"common"}
        if keyed:
            for x in sorted(allowed - keyed):
                fails.append(f"{show(f)}: no fixtures.{x} block, but tier '{x}' is allowed")
            for x in sorted(keyed - allowed):
                fails.append(f"{show(f)}: fixtures.{x} exists, but '{x}' is not an allowed tier")
    return fails


def check_scripts():
    """A script is declared in exactly one home, and every caller is covered by it.

    `read_signup_mail.py` served three mail providers from one provider's
    folder; `ggplus_auth.py` served three tiers from the prod site, so a dev
    workflow listed prod just to reach it. The home is derived from the
    callers: a site's script is only called by steps on that site; a
    project's script only by that project's workflows (another project's call
    is a note); an app's script only by steps on its tiers or by projects of
    that app. An undeclared script fails; a declared script nobody calls is a
    note.
    """
    fails = []
    site_decl, proj_decl, app_decl = {}, {}, {}
    for sd in glob.glob("sites/*"):
        sy = f"{sd}/site.yaml"
        if os.path.exists(sy):
            for n in declared_scripts(load(sy).get("site") or {}):
                site_decl.setdefault(n, set()).add(os.path.basename(sd))
    for rel, _, p in projects():
        for n in declared_scripts(p):
            proj_decl.setdefault(n, set()).add(rel)
    app_sites = {}
    for name, _, a in apps():
        for n in declared_scripts(a):
            app_decl.setdefault(n, set()).add(name)
        app_sites[name] = set((a.get("tiers") or {}).values())
    for n in set(proj_decl) & set(app_decl):
        fails.append(f"script '{n}' is declared by project(s) {sorted(proj_decl[n])} and "
                     f"app(s) {sorted(app_decl[n])} — a name has one home")

    called = set()
    for f in all_workflows():
        w = load(f).get("workflow") or {}
        is_site = norm(f).startswith("sites/")
        owner = norm(f).split("/")[1] if is_site else None
        proj = next((rel for ff, rel, _ in project_workflows() if ff == f), None)
        papp = next((p.get("app") for ff, _, p in project_workflows() if ff == f), None)
        default = w.get("site")
        values = tree.fixture_values(w)
        for s in tree.steps_of(w):
            name = s.get("script")
            if not name:
                continue
            called.add(name)
            ref = str(s.get("site") or default or "")
            sites = values.get(ref[1:], set()) if ref.startswith("$") else ({ref} if ref else set())
            homes = []
            ok = False
            if name in site_decl:
                homes.append(f"site(s) {sorted(site_decl[name])}")
                ok = ok or bool(sites) and sites <= site_decl[name]
            if name in proj_decl:
                homes.append(f"project(s) {sorted(proj_decl[name])}")
                if proj in proj_decl[name]:
                    ok = True
                elif proj is not None:
                    NOTES.append(f"{show(f)}: calls '{name}' of project(s) "
                                 f"{sorted(proj_decl[name])} — a second project using a "
                                 "script is the sign it may belong to an app or the lib")
                    ok = True
            if name in app_decl:
                homes.append(f"app(s) {sorted(app_decl[name])}")
                for an in app_decl[name]:
                    if papp == an or (sites and sites <= app_sites[an]):
                        ok = True
            if not homes:
                fails.append(f"{show(f)}: step calls script '{name}', declared by no site, "
                             "project or app")
            elif not ok:
                where = f"on site(s) {sorted(sites)}" if sites else "with no site"
                fails.append(f"{show(f)}: calls '{name}' {where}"
                             f"{' from project ' + proj if proj else ''}, but it is declared by "
                             f"{'; '.join(homes)} — the home must cover every caller "
                             "(schema/project.yaml)")
    for n in sorted((set(site_decl) | set(proj_decl) | set(app_decl)) - called):
        NOTES.append(f"script '{n}' is declared but no workflow step calls it")
    return fails


def check_parity():
    """Every page map of an app's reference tier exists on its other tiers, or is a declared gap.

    Staging had no map for the pages the signup suite drives while prod had
    one; nobody noticed for two months. The reference tier's page list is
    compared with every other tier's, both ways; a difference is a defect
    unless app.yaml declares it with a reason, and a declared gap that no
    longer differs is stale and fails too.
    """
    fails = []
    for name, ad, a in apps():
        ay = show(f"{ad}/app.yaml")
        tiers = a.get("tiers") or {}
        parity = a.get("parity") or {}
        ref = parity.get("reference")
        if not ref or ref not in tiers:
            continue  # check_apps reports a bad reference
        gaps = {}
        for g in parity.get("gaps") or []:
            if not isinstance(g, dict) or not g.get("tier") or not g.get("page"):
                fails.append(f"{ay}: a parity gap needs tier, page and why")
                continue
            if not g.get("why"):
                fails.append(f"{ay}: gap {g.get('tier')}/{g.get('page')} has no reason")
            gaps.setdefault(g["tier"], set()).add(g["page"])
        ref_pages = {os.path.basename(f) for f in glob.glob(f"sites/{tiers[ref]}/pages/*.yaml")}
        for tier, site in tiers.items():
            if tier == ref:
                continue
            pages = {os.path.basename(f) for f in glob.glob(f"sites/{site}/pages/*.yaml")}
            differs = ref_pages ^ pages
            declared = gaps.get(tier, set())
            for pg in sorted(differs - declared):
                side = "missing on" if pg in ref_pages else "only on"
                fails.append(f"{ay}: page '{pg}' is {side} tier '{tier}' ({site}) and not "
                             "declared under parity.gaps")
            for pg in sorted(declared - differs):
                fails.append(f"{ay}: gap {tier}/{pg} is stale — the page no longer differs "
                             f"from '{ref}'")
        for tier in gaps:
            if tier not in tiers or tier == ref:
                fails.append(f"{ay}: parity.gaps names tier '{tier}', which is not a compared tier")
    return fails


def check_rollback():
    """A workflow that writes says how its change could be undone.

    The only copy of the state before a production role sync lived in a
    session scratchpad. A mutating or destructive workflow now declares
    `rollback: snapshot` (and a `snapshot:` phase that captures the pre-state)
    or `rollback: none` with a reason.
    """
    fails = []
    for f in all_workflows():
        w = load(f).get("workflow") or {}
        if w.get("effect") not in ("mutating", "destructive"):
            if w.get("snapshot"):
                fails.append(f"{show(f)}: has a snapshot phase but effect is "
                             f"'{w.get('effect') or ''}', not mutating or destructive")
            continue
        rb = w.get("rollback")
        if rb not in tree.ROLLBACK_VALUES:
            fails.append(f"{show(f)}: effect '{w.get('effect')}' needs rollback: "
                         f"snapshot | none (schema/workflow.yaml)")
        elif rb == "none" and not w.get("rollback_reason"):
            fails.append(f"{show(f)}: rollback: none needs a rollback_reason")
        elif rb == "snapshot":
            caps = [s.get("capture") for s in (w.get("snapshot") or []) if isinstance(s, dict)]
            if not any(caps):
                fails.append(f"{show(f)}: rollback: snapshot needs a `snapshot:` phase with at "
                             "least one capture — that capture is the pre-state")
    return fails


def check_actions():
    """Every step's action is one the runner and the skills know; a person step says why.

    A `human` step without a reason pauses a run with nothing to tell the person
    who picks it up, and one in `teardown` would surface as a broken teardown
    instead of a waiting run. An unknown action failed only at run time. A
    step without `action` is allowed only in an agentic workflow. A script
    step's `shape` must parse as a shape: a misspelled type name (`strng`) would
    otherwise fail mid-run and stop a workflow whose script was fine.
    """
    fails = []
    for f in all_workflows():
        w = load(f).get("workflow") or {}
        for phase in tree.PHASES + ("teardown",):
            for i, s in enumerate(w.get(phase) or []):
                if not isinstance(s, dict):
                    continue
                where = f"{show(f)}: {phase}[{i}]"
                action = s.get("action")
                if action is None and w.get("mode") == "agentic":
                    continue
                if action not in tree.ACTIONS:
                    fails.append(f"{where}: unknown action '{action}' "
                                 f"({' | '.join(tree.ACTIONS)})")
                elif action == "human":
                    if not s.get("reason"):
                        fails.append(f"{where}: a human step needs a `reason`")
                    if "kind" in s and s["kind"] not in tree.HUMAN_KINDS:
                        fails.append(f"{where}: kind '{s['kind']}' is not "
                                     f"{' | '.join(tree.HUMAN_KINDS)}")
                    if phase == "teardown":
                        fails.append(f"{where}: a human step cannot be in teardown")
                if s.get("shape") is not None:
                    problem = (tree.shape_problem(s["shape"]) if action == "script"
                               else "shape: only a script step has an output shape")
                    if problem:
                        fails.append(f"{where}: {problem}")
    return fails


def check_produced():
    """Nothing a run wrote is in the tree: no results/ or state/ under sites or projects.

    164 run files were committed as 'exceptions' to a gitignore, including
    171 MB of device logs. Run output has one home, the runs store
    (schema/run.yaml); learned state has the state store. A folder of either
    name under a site or a project is the old layout and fails.
    """
    fails = []
    for sd in sorted(glob.glob("sites/*")):
        for bad in ("results", "state"):
            if os.path.isdir(f"{sd}/{bad}"):
                fails.append(f"{norm(sd)}/{bad}/: run-written files do not live in the tree "
                             "— runs go to the runs store, learned state to the state store")
    for rel, pd_, _ in projects():
        for bad in ("results", "state"):
            if os.path.isdir(f"{pd_}/{bad}"):
                fails.append(f"{show(pd_)}/{bad}/: run-written files do not live in the tree "
                             "— runs go to the runs store, learned state to the state store")
    # A .gitignore does not untrack files that were already tracked: a migration
    # moved 164 committed results into runs/ and they stayed in git. Ask git.
    import subprocess
    runs = tree.runs_root(ROOT)
    for store in (runs, os.path.join(os.path.dirname(runs), "state")):
        if not os.path.isdir(store):
            continue
        try:
            out = subprocess.run(["git", "-C", store, "ls-files", "--", "."],
                                 capture_output=True, text=True, timeout=30).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        tracked = [line for line in out.splitlines() if line.strip()]
        if tracked:
            fails.append(f"{show(store)}/: {len(tracked)} file(s) tracked by git, e.g. "
                         f"{tracked[0]} — produced data is never committed; "
                         "`git rm -r --cached` it")
    return fails


def check_links():
    """Markdown links and page `screenshot:` paths resolve."""
    fails = []
    for f in files(DOC_GLOBS):
        base = os.path.dirname(f)
        for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", strip_fences(open(f, encoding="utf-8").read())):
            t = m.group(1)
            if t.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = os.path.join(base, t.split("#")[0])
            if not os.path.exists(os.path.normpath(target)):
                docs_rel = norm(os.path.relpath(os.path.normpath(target), "docs"))
                if docs_rel in PER_PROJECT_DOCS:
                    NOTES.append(f"{f}: '{t}' is a standardized per-project doc "
                                 "this project declined — see docs/project-index.md")
                    continue
                fails.append(f"{f}: broken link -> {t}")
            elif not exists_cased(target):
                fails.append(f"{f}: link case does not match the file -> {t} "
                             "(resolves on Windows, breaks on Linux/CI)")
    for f in files(["sites/*/pages/*.yaml"]):
        shot = (load(f).get("page") or {}).get("screenshot")
        if shot and not os.path.exists(os.path.join(os.path.dirname(os.path.dirname(f)), shot)):
            fails.append(f"{f}: screenshot -> {shot} does not exist")
    return fails


def check_bindings():
    """Every project doc is navigable, and every skill/agent is registered.

    Catches both halves of the orphan problem: a doc nobody can navigate to
    (interface.md was orphaned for weeks) and a skill or agent that exists but
    appears in no registry, so no host can route to it.

    Since the aiDocs migration, a skill/agent file carries its COMPLETE
    instructions — there is no second neutral copy under docs/ to point at, so
    a near-empty file is now the defect (it used to be the requirement).
    """
    # Framework-only. A map repository has no docs/ set and no .claude/ files —
    # those belong to the tool, not to the maps — so running this against
    # --root would check nothing and report success, which is worse than saying
    # so out loud.
    if external():
        SKIPPED.add("bindings")
        NOTES.append("bindings: framework-only — the docs set and .claude/ "
                     "belong to the tool, not to a map repository")
        return []

    fails = []
    reachable = ""
    for nav in ("docs/INDEX.md", "docs/AGENTS.md", "docs/README.md",
                "docs/project-index.md", "docs/skills-and-agents.md"):
        if os.path.exists(nav):
            reachable += open(nav, encoding="utf-8").read()

    # Entry points and generated views are never orphans.
    NON_ORPHANS = {"INDEX.md", "AGENTS.md", "README.md", "project-index.md",
                   "skills-and-agents.md", "inventory.md"}
    for f in files(["docs/*.md", "docs/tools/*.md"]):
        rel_name = norm(os.path.relpath(f, "docs"))
        if os.path.basename(f) in NON_ORPHANS:
            continue
        if rel_name not in reachable and os.path.basename(f) not in reachable:
            fails.append(f"{f}: not referenced from docs/INDEX.md, docs/AGENTS.md, "
                         "docs/README.md, docs/project-index.md or "
                         "docs/skills-and-agents.md")

    registry = "docs/skills-and-agents.md"
    if not os.path.exists(registry):
        fails.append(f"{registry}: missing — skills and agents have no registry")
        return fails
    reg = open(registry, encoding="utf-8").read()

    for f in files([".claude/skills/*/SKILL.md", ".claude/agents/*.md"]):
        if ".template" in os.path.basename(f):
            continue
        name = (os.path.basename(os.path.dirname(f)) if f.endswith("SKILL.md")
                else os.path.basename(f)[:-3])
        if name not in reg:
            fails.append(f"{f}: '{name}' is not listed in {registry}")
        body = open(f, encoding="utf-8").read()
        if len(body.splitlines()) < 20:
            fails.append(f"{f}: {len(body.splitlines())} lines — a skill or agent "
                         "carries its complete instructions, not a pointer")
        for host_tool in re.findall(r"\b(?:tabs_context_mcp|read_page|get_page_text|"
                                    r"form_input|read_console_messages)\b", body):
            fails.append(f"{f}: names the host tool '{host_tool}' — tool names "
                         "belong in docs/host-bindings.md only")
    return fails


def generated_is_stale(module, out_attr="OUT"):
    # The generators are the framework's (import from HOME); the tree they walk
    # is the checked one (set_root to ROOT). Both must be set, or a --root run
    # silently regenerates the framework's own views instead.
    sys.path.insert(0, os.path.join(HOME, "scripts"))
    mod = __import__(module)
    mod.set_root(ROOT, PROJECTS)
    __import__("inventory").set_root(ROOT, PROJECTS)
    out = getattr(mod, out_attr)
    cur = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    if cur != mod.render():
        hint = f" --root {norm(ROOT)}" if external() else ""
        return [f"{norm(os.path.relpath(out, ROOT))} is stale — "
                f"run: python scripts/inventory.py{hint}"]
    return []


def check_inventory():
    """docs/inventory.md is current."""
    return generated_is_stale("inventory")


def check_overview():
    """docs/overview.html is current."""
    return generated_is_stale("overview")


def check_lib_tree():
    """lib-tree.json is current."""
    return generated_is_stale("libtree")


CHECKS = {
    "yaml": check_yaml,
    "schema": check_schema,
    "credentials": check_credentials,
    "listings": check_listings,
    "companions": check_companions,
    "apps": check_apps,
    "placement": check_placement,
    "tiers": check_tiers,
    "scripts": check_scripts,
    "parity": check_parity,
    "rollback": check_rollback,
    "actions": check_actions,
    "produced": check_produced,
    "links": check_links,
    "bindings": check_bindings,
    "inventory": check_inventory,
    "overview": check_overview,
    "lib_tree": check_lib_tree,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", choices=sorted(CHECKS), help="run a single check")
    ap.add_argument("--list", action="store_true", help="list check names")
    ap.add_argument("--root", help="check this tree instead of the script's own repo "
                                   "(e.g. a private map repository). Schemas and "
                                   "bindings still come from the framework.")
    ap.add_argument("--projects", help="the projects tree, when it is not inside --root "
                                       "(default: <root>/projects, else <root>/../projects)")
    args = ap.parse_args()

    global ROOT, PROJECTS
    if args.root:
        ROOT = os.path.abspath(os.path.join(INVOCATION_CWD, args.root))
        if not os.path.isdir(ROOT):
            sys.exit(f"--root is not a directory: {ROOT}")
        os.chdir(ROOT)
    PROJECTS = tree.projects_root(
        ROOT, os.path.join(INVOCATION_CWD, args.projects) if args.projects else None)
    if args.root or args.projects:
        print(f"checking {norm(ROOT)}  (projects: {show(PROJECTS)}, schemas from {norm(HOME)})")
        print()

    if args.list:
        for name, fn in sorted(CHECKS.items()):
            print(f"{name:12} {(fn.__doc__ or '').splitlines()[0]}")
        return 0

    selected = [args.only] if args.only else list(CHECKS)
    total = 0
    for name in selected:
        fails = CHECKS[name]()
        total += len(fails)
        status = ("skipped" if name in SKIPPED
                  else "ok" if not fails else f"{len(fails)} FAILED")
        print(f"[{name}] {status}")
        for msg in fails:
            print(f"  FAIL  {msg}")
    for msg in NOTES:
        print(f"  note  {msg}")
    skipped = SKIPPED & set(selected)
    tail = f", {len(skipped)} skipped" if skipped else ""
    print(f"\n{len(selected) - len(skipped)} checks run, {total} failures, "
          f"{len(NOTES)} notes{tail}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
