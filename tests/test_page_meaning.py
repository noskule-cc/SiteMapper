import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
CHECK = SCRIPTS / "check.py"
sys.path.insert(0, str(SCRIPTS))

PAGE = """\
page:
  name: Inspection Form
  url_pattern: /forms/{id}
  purpose: >
    Record one inspection. A technician fills it, a supervisor signs it.
  elements:
    - name: step-a
      type: text
      locator: { strategy: text, value: "Step A" }
    - name: step-b
      type: text
      locator: { strategy: text, value: "Step B" }
    - name: defects-radio
      type: checkbox
      locator: { strategy: role, value: radio }
    - name: entry-card
      type: container
      locator: { strategy: css, value: ".entry" }
      children:
        - name: entry-note
          type: input
          locator: { strategy: css, value: ".entry textarea" }
    - name: sign-button
      type: button
      locator: { strategy: text, value: Sign }
    - name: confirm-yes
      type: button
      locator: { strategy: text, value: "Yes" }
    - name: signature-canvas
      type: container
      locator: { strategy: css, value: canvas }
    - name: signature-dialog-save
      type: button
      locator: { strategy: aria-label, value: Save signature }
  sources:
    - { title: "Training page", url: "https://docs.example.com/inspection" }
  concepts:
    - name: round
      meaning: One pass through all steps. A repeat starts a new round.
  sections:
    - name: defects
      applies_to: [step-a, step-b]
      elements: [defects-radio, entry-card, entry-note]
      meaning: What the technician found.
      rules: ["A defect needs a note."]
      examples: ["A worn seal."]
  recipes:
    - name: open-signature
      goal: Open the signature dialog
      steps:
        - { do: click, element: sign-button }
        - { do: confirm, element: confirm-yes, note: "by element, not coordinates" }
    - name: sign-step
      goal: Sign the current step
      when: "after every field of the step is filled"
      steps:
        - { do: recipe, recipe: open-signature }
        - { do: wait, element: signature-canvas, note: "stable across two reads" }
        - { do: draw, element: signature-canvas }
        - { do: fill, element: entry-note, value: "signed" }
        - { do: click, element: signature-dialog-save }
      after: "The step shows the signature."
      gotchas: ["The canvas can look stable while it still animates."]
      uses: [open-signature]
  open_questions:
    - { question: "Who may sign step B?", docs: "Supervisor only.",
        observed: "Any user can sign.", owner: operator }
"""


def tree(page_text):
    tmp = tempfile.TemporaryDirectory()
    site = Path(tmp.name) / "sites" / "demo"
    (site / "pages").mkdir(parents=True)
    (site / "site.yaml").write_text("site:\n  name: demo\n  base_url: https://example.com\n",
                                    encoding="utf-8")
    (site / "pages" / "inspection-form.yaml").write_text(page_text, encoding="utf-8")
    return tmp


def check(page_text):
    with tree(page_text) as tmp:
        out = subprocess.run([sys.executable, str(CHECK), "--root", tmp, "--only", "meaning"],
                             capture_output=True, text=True)
    return out.returncode, out.stdout


def replaced(old, new):
    assert old in PAGE, old
    return PAGE.replace(old, new)


class MeaningCheck(unittest.TestCase):
    def test_a_valid_map_passes(self):
        code, out = check(PAGE)
        self.assertEqual(code, 0, out)

    def test_each_broken_meaning_is_caught(self):
        cases = {
            "section element": (
                "elements: [defects-radio, entry-card, entry-note]",
                "elements: [defects-radio, nope-card]", "'nope-card' is not an element"),
            "applies_to": ("applies_to: [step-a, step-b]", "applies_to: [step-a, step-z]",
                           "sections[0].applies_to: 'step-z' is not an element"),
            "step element": ("{ do: draw, element: signature-canvas }",
                             "{ do: draw, element: canvas-2 }",
                             "element 'canvas-2' is not an element of this page"),
            "unknown do": ("{ do: draw, element: signature-canvas }",
                           "{ do: scribble, element: signature-canvas }",
                           "do is not one of: click, fill"),
            "missing recipe": ("{ do: recipe, recipe: open-signature }",
                               "{ do: recipe, recipe: open-dialog }",
                               "recipe 'open-dialog' is not a recipe of this page"),
            "element needed": ("{ do: draw, element: signature-canvas }", "{ do: draw }",
                               "a `do: draw` step needs `element`"),
            "cycle": ("        - { do: confirm, element: confirm-yes, note: \"by element, "
                      "not coordinates\" }",
                      "        - { do: recipe, recipe: sign-step }",
                      "reaches itself"),
            "uses": ("uses: [open-signature]", "uses: [ghost]",
                     "uses: 'ghost' is not a recipe"),
            "source url": ("https://docs.example.com/inspection", "docs.example.com/x",
                           "sources[0]: url is not an http(s) link"),
            "question owner": ("observed: \"Any user can sign.\", owner: operator",
                               "observed: \"Any user can sign.\"",
                               "open_questions[0]: owner is missing"),
            "question observed": ("observed: \"Any user can sign.\", ", "",
                                  "open_questions[0]: observed is missing"),
            "unknown key": ("      rules: [", "      rule: [",
                            "sections[0]: 'rule' is not a key here; allowed: name, "
                            "applies_to, elements, meaning, rules, examples"),
            "unknown step key": ("note: \"stable across two reads\"",
                                 "hint: \"stable across two reads\"",
                                 "'hint' is not a key here; allowed: do, element, note, "
                                 "recipe, value"),
            "duplicate recipe": ("name: open-signature\n", "name: sign-step\n",
                                 "name 'sign-step' is used twice"),
        }
        for label, (old, new, expected) in cases.items():
            with self.subTest(label):
                code, out = check(replaced(old, new))
                self.assertEqual(code, 1, out)
                self.assertIn(expected, out)


class MeaningExport(unittest.TestCase):
    def page_node(self, page_text):
        import libtree
        with tree(page_text) as tmp:
            libtree.set_root(tmp)
            doc = json.loads(libtree.render())
        site = doc["nodes"][0]["children"][0]
        return site["children"][0]["children"][0]

    def test_a_page_node_carries_its_meaning_as_markdown(self):
        md = self.page_node(PAGE)["markdown"]
        for expected in (
            "**Purpose.** Record one inspection. A technician fills it, a supervisor signs it.",
            "Sources: [Training page](https://docs.example.com/inspection)",
            "- **round**: One pass through all steps.",
            "- **defects** (on `step-a`, `step-b`): What the technician found.",
            "  - Rule: A defect needs a note.",
            "#### sign-step",
            "Sign the current step\n\nWhen: after every field of the step is filled",
            "2. wait `signature-canvas` · stable across two reads",
            "4. fill `entry-note` = `signed`",
            "After: The step shows the signature.",
            "- The canvas can look stable while it still animates.",
            "- **Who may sign step B?** Docs: Supervisor only. Observed: Any user can sign. "
            "Owner: operator",
        ):
            self.assertIn(expected, md)

    def test_a_recipe_renders_as_a_flowchart_in_step_order(self):
        md = self.page_node(PAGE)["markdown"]
        chart = md.split("#### sign-step", 1)[1].split("```mermaid\n", 1)[1].split("```")[0]
        self.assertEqual(chart.splitlines(), [
            "flowchart TD",
            '  s1[["recipe open-signature"]] --> s2',
            '  s2["wait signature-canvas"] --> s3',
            '  s3["draw signature-canvas"] --> s4',
            '  s4["fill entry-note"] --> s5',
            '  s5["click signature-dialog-save"]',
        ])

    def test_a_page_without_meaning_has_no_markdown(self):
        bare = "page:\n  name: Bare\n  url_pattern: /bare\n  elements: []\n"
        self.assertNotIn("markdown", self.page_node(bare))


if __name__ == "__main__":
    unittest.main()
