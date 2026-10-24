"""What a script step's `shape` matches and what --learn-shape infers from an output."""
import random
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run  # noqa: E402
import tree  # noqa: E402

OUTPUTS = [
    {"items": [{"v": 1}, {"v": "one"}, {"v": True}]},
    {"items": [{"a": 1, "b": "x"}, {"a": "s"}]},
    [{"a": 1}, 5],
    [[{"a": 1}], [{"a": 1, "b": 2}], []],
    [None, {"a": 1}],
    [{"a": None}, {"a": [1]}, {"a": {"b": 1}}],
    [{"a": [1]}, {"a": {"x": 1}}],
    [[1, "a"], [{"x": 1}]],
    {"user": None, "users": [{"id": 1, "boss": None}, {"id": 2, "boss": {"id": 1}}]},
    {"closed_at": None},
    [{"closed_at": None}, {"closed_at": "2026-10-01"}],
    {"by_id": {"101": {"title": "a"}, "102": {}}},
    None, 1, 1.5, "s", True, [], {},
]


def random_value(rng: random.Random, depth: int = 0):
    kinds = ["null", "bool", "number", "string"] + (["list", "object"] if depth < 4 else [])
    kind = rng.choice(kinds)
    if kind == "list":
        return [random_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    if kind == "object":
        return {rng.choice("abcd"): random_value(rng, depth + 1) for _ in range(rng.randint(0, 3))}
    return {"null": None, "bool": rng.random() < 0.5, "number": rng.randint(0, 9),
            "string": "x"}[kind]


class ShapeTest(unittest.TestCase):
    def test_every_output_matches_the_shape_learned_from_it(self):
        rng = random.Random(72)
        for value in OUTPUTS + [random_value(rng) for _ in range(2000)]:
            shape = run.infer_shape(value)
            self.assertEqual((tree.shape_problem(shape), run.shape_mismatch(shape, value)),
                             ("", None), f"{value!r} learned {shape!r}")

    def test_items_that_disagree_on_a_type_leave_the_key_unconstrained(self):
        self.assertEqual(run.infer_shape({"items": [{"v": 1, "k": "a"}, {"v": "one", "k": "b"},
                                                    {"v": True, "k": "c"}]}),
                         {"items": [{"v": "null", "k": "string"}]})
        self.assertEqual(run.infer_shape([[1], ["a"]]), [[]])
        self.assertEqual(run.infer_shape([{"a": 1, "b": 2}, {"a": "x"}]), [{"a": "null"}])

    def test_an_unconstrained_key_must_still_be_there(self):
        shape = run.infer_shape([{"a": 1, "u": None}, {"a": 2, "u": {"id": 1}}])
        self.assertEqual(shape, [{"a": "number", "u": "null"}])
        self.assertEqual(run.shape_mismatch(shape, [{"a": 3}]), "$[0].u: missing")
        self.assertIsNone(run.shape_mismatch(shape, [{"a": 3, "u": [1]}]))

    def test_a_null_item_takes_the_type_of_the_others(self):
        self.assertEqual(run.infer_shape([{"c": None}, {"c": "2026-10-01"}]),
                         [{"c": "string"}])
        self.assertEqual(run.infer_shape([{"c": None}, {"c": {"id": 1}}]), [{"c": "null"}])

    def test_a_null_matches_a_scalar_but_not_an_object_or_a_list(self):
        shape = {"title": "string", "user": {"id": "number"}, "labels": ["string"]}
        self.assertIsNone(run.shape_mismatch(shape, {"title": None, "user": {"id": None},
                                                     "labels": [None]}))
        self.assertEqual(run.shape_mismatch(shape, {"title": "a", "user": None, "labels": []}),
                         "$.user: expected object, got null")
        self.assertEqual(run.shape_mismatch(shape, {"title": "a", "user": {}, "labels": None}),
                         "$.user.id: missing")
        self.assertEqual(run.shape_mismatch({"labels": ["string"]}, {"labels": None}),
                         "$.labels: expected list, got null")

    def test_a_null_output_matches_only_a_null_shape(self):
        self.assertEqual(run.shape_mismatch({"items": []}, None), "$: expected object, got null")
        self.assertEqual(run.shape_mismatch("number", None), "$: expected number, got null")
        self.assertIsNone(run.shape_mismatch("null", None))

    def test_a_mapping_keyed_by_ids_learns_as_any_object(self):
        self.assertEqual(run.infer_shape({"by_id": {"101": {"title": "a"}}}), {"by_id": {}})
        self.assertEqual(run.infer_shape({"5f0c9a1b-0d1e-4c2a-9b3d-1a2b3c4d5e6f": 1,
                                          "deadbeef01": 2}), {})
        self.assertEqual(run.infer_shape({"101": 1, "name": "x"}),
                         {"101": "number", "name": "string"})
        self.assertIsNone(run.shape_mismatch({"by_id": {}}, {"by_id": {"102": {"t": "b"}}}))
        self.assertEqual(tree.shape_problem({"by_id": {}}), "")


if __name__ == "__main__":
    unittest.main()
