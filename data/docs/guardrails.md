# Guardrails — <your deployment>

Standing rules every session follows, whichever agent is driving. Written from
[GUARDRAILS.template.md](../../docs/GUARDRAILS.template.md) in the framework
repo, which explains the categories and how to write a rule that holds.

Deliberately **not** named `SECURITY.md`: GitHub claims that filename for
vulnerability-disclosure policy, which this is not.

**These are behavioural rules, not enforced ones.** The tools an agent holds are
configured per user, not per project, so nothing here can be enforced from inside
the repository. That is exactly why it is written down: the rule is the
enforcement.

---

Replace everything below with your own. The headings are the categories worth
covering, and the notes say what a good rule looks like — delete a heading only
once you are sure it does not apply.

## <External system> access

If an agent authenticates as you against a system with a broad blast radius —
a ticket tracker, a wiki, a cloud console — say exactly which projects it may
touch and which operations are allowed. A table beats a paragraph, because the
answer has to be checkable before a call, not after.

## Credentials are a human action

Never type a password, MFA code or API secret — not into a form, not into a
script, not into a file. If a site needs auth, confirm the human is logged in
and continue from their session. No committed file may contain a secret; a map
references a run-time secret (`credential_ref: env:…`), never the value.

## Writing through a UI is gated by `settings.policy.permissions`

The machine-readable authorization model (allow/ask/deny per action class —
see the framework's `docs/PERMISSIONS.md`), resolved through the layered
`settings:` block; form submission is a `write`-class action (the old
`safe_to_submit_forms: true` still acts as `write: allow`). Do not flip a
permission to unblock a workflow — it is set per scope for a reason, and
flipping it at site level silently authorizes every page of that site for
every future run.

## Production writes

Name any environment that looks like a sandbox and is not. Shared downstream
records are the usual trap: two front ends that write one integration record
mean a "staging" test writes production data. Record the evidence with the
fact, in the site or project file, not only here.

## Destructive actions, especially in teardown

A test may only delete what that same run created, located by identity and never
by position. Teardown runs best-effort after failures — precisely when the page
is least likely to be in the state the step assumed.

## What may be committed

State whether this repository is public or private, and what that means for run
outputs, customer identifiers and personal data. If it is private, say what
still must not be committed: secrets, and anything you would not want in every
clone forever.
