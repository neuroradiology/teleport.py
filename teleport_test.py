from unittest2 import TestCase

from copy import deepcopy

from teleport import *

struct_schema_json = {
    "type": u"Struct",
    "param": {
        "map": {
            u"foo": {
                "required": True,
                "schema": {"type": u"Boolean"},
                "doc": u"Never gonna give you up"
            },
            u"bar": {
                "required": False,
                "schema": {"type": u"Integer"}
            }
        },
        "order": [u"foo", u"bar"]
    }
}
struct_schema = from_json(Schema, struct_schema_json)

class TestStruct(TestCase):

    def test_from_json(self):
        res = from_json(struct_schema, {"foo": True, "bar": 2.0})
        self.assertEqual(res, {"foo": True, "bar": 2})
        res = from_json(struct_schema, {"foo": True})
        self.assertEqual(res, {"foo": True})

    def test_from_json_fail(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid Struct"):
            from_json(struct_schema, [])
        with self.assertRaisesRegexp(ValidationError, "Unexpected fields"):
            from_json(struct_schema, {"foo": True, "barr": 2.0})
        with self.assertRaisesRegexp(ValidationError, "Missing fields"):
            from_json(struct_schema, {"bar": 2})

class TestBoolean(TestCase):

    def test_from_json(self):
        self.assertEqual(from_json(Boolean, True), True)
        with self.assertRaisesRegexp(ValidationError, "Invalid Boolean"):
            from_json(Boolean, 0)


class TestString(TestCase):

    def test_string_okay(self):
        self.assertEqual(from_json(String, u"omg"), u"omg")
        self.assertEqual(from_json(String, "omg"), u"omg")

    def test_string_fail(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid String"):
            from_json(String, 0)
        with self.assertRaisesRegexp(UnicodeDecodeValidationError, "invalid start byte"):
            from_json(String, "\xff")


class TestMap(TestCase):

    def test_from_json_and_to_json(self):
        m = {
            u"cool": True,
            u"hip": False,
            u"groovy": True
        }
        map_schema = Map(Boolean)
        self.assertEqual(from_json(map_schema, m), m)
        with self.assertRaisesRegexp(ValidationError, "Invalid Map"):
            from_json(map_schema, [True, False])
        with self.assertRaisesRegexp(ValidationError, "must be unicode"):
            from_json(map_schema, {"nope": False})
        with self.assertRaisesRegexp(ValidationError, "Invalid Boolean"):
            from_json(map_schema, {u"cool": 0})


class TestOrderedMap(TestCase):

    def test_from_json_and_to_json(self):
        m = {
            "map": {
                u"cool": True,
                u"hip": False,
                u"groovy": True
            },
            "order": [u"cool", u"groovy", u"hip"]
        }
        md = OrderedDict([
            (u"cool", True,),
            (u"groovy", True,),
            (u"hip", False,)
        ])
        s = OrderedMap(Boolean)
        self.assertEqual(from_json(s, m), md)

        with self.assertRaisesRegexp(ValidationError, "Invalid OrderedMap"):
            m2 = deepcopy(m)
            m2["order"].append(u"cool")
            from_json(s, m2)
        with self.assertRaisesRegexp(ValidationError, "Invalid OrderedMap"):
            m2 = deepcopy(m)
            m2["order"] = [u"cool", u"groovy", u"kewl"]
            from_json(s, m2)


class TestArray(TestCase):

    def test_array(self):
        schema = Array(Boolean)
        self.assertEqual(from_json(schema, [True]), [True])

