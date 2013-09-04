from unittest2 import TestCase

from copy import deepcopy

from teleport import *


## TEST PRIMITIVES

class TestFloat(TestCase):

    def test_from_json(self):
        self.assertEqual(from_json(Float, 1), 1.0)
        self.assertEqual(from_json(Float, 1.0), 1.0)
        with self.assertRaisesRegexp(ValidationError, "Invalid Float"):
            from_json(Float, True)

    def test_to_json(self):
        self.assertEqual(to_json(Float, 1.1), 1.1)


class TestInteger(TestCase):

    def test_from_json(self):
        self.assertEqual(from_json(Integer, 1), 1)
        self.assertEqual(from_json(Integer, 1.0), 1)
        with self.assertRaisesRegexp(ValidationError, "Invalid Integer"):
            from_json(Integer, 1.1)

    def test_to_json(self):
        self.assertEqual(to_json(Integer, 1), 1)


class TestBoolean(TestCase):

    def test_from_json(self):
        self.assertEqual(from_json(Boolean, True), True)
        with self.assertRaisesRegexp(ValidationError, "Invalid Boolean"):
            from_json(Boolean, 0)

    def test_to_json(self):
        self.assertEqual(to_json(Boolean, True), True)


class TestString(TestCase):

    def test_string_okay(self):
        self.assertEqual(from_json(String, u"omg"), u"omg")
        self.assertEqual(from_json(String, "omg"), u"omg")

    def test_string_fail(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid String"):
            from_json(String, 0)
        with self.assertRaisesRegexp(UnicodeDecodeValidationError, "invalid start byte"):
            from_json(String, "\xff")

    def test_to_json(self):
        self.assertEqual(to_json(String, u"yo"), u"yo")


class TestBinary(TestCase):

    def test_from_json(self):
        self.assertEqual(from_json(Binary, 'YWJj'), "abc")
        self.assertEqual(from_json(Binary, u'YWJj'), "abc")
        with self.assertRaisesRegexp(ValidationError, "Invalid base64"):
            # Will complain about incorrect padding
            from_json(Binary, "a")
        with self.assertRaisesRegexp(ValidationError, "Invalid Binary"):
            from_json(Binary, 1)

    def test_to_json(self):
        self.assertEqual(to_json(Binary, "abc"), "YWJj")


class TestJSON(TestCase):

    def test_from_json(self):
        self.assertTrue(isinstance(from_json(JSON, "A string?"), Box))
        self.assertEqual(from_json(JSON, 'ABC').datum, "ABC")

    def test_to_json(self):
        self.assertEqual(to_json(JSON, Box("abc")), "abc")

## TEST PARAMETRIZED

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
array_schema_json = {
    "type": u"Array",
    "param": {
        "type": u"Boolean"
    }
}
map_schema_json = {
    "type": u"Map",
    "param": {"type": "Boolean"}
}
ordered_map_schema_json = {
    "type": u"OrderedMap",
    "param": {"type": "Boolean"}
}
struct_schema = from_json(Schema, struct_schema_json)
array_schema = from_json(Schema, array_schema_json)
map_schema = from_json(Schema, map_schema_json)
ordered_map_schema = from_json(Schema, ordered_map_schema_json)




class TestArray(TestCase):

    def test_from_json(self):
        self.assertEqual(from_json(array_schema, [True, False]), [True, False])
        self.assertEqual(to_json(array_schema, [True, False]), [True, False])
        with self.assertRaisesRegexp(ValidationError, "Invalid Array"):
            from_json(array_schema, ("no", "tuples",))
        with self.assertRaisesRegexp(ValidationError, "Invalid Boolean"):
            from_json(array_schema, [True, False, 1])


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

    def test_to_json(self):
        res = to_json(struct_schema, {"foo": True})
        self.assertEqual(res, {"foo": True})
        res = to_json(struct_schema, {"foo": True, "bar": None})
        self.assertEqual(res, {"foo": True})


class TestMap(TestCase):

    def test_from_json_and_to_json(self):
        m = {
            u"cool": True,
            u"hip": False,
            u"groovy": True
        }
        self.assertEqual(from_json(map_schema, m), m)
        self.assertEqual(to_json(map_schema, m), m)
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
        self.assertEqual(from_json(ordered_map_schema, m), md)
        self.assertEqual(to_json(ordered_map_schema, md), m)

        with self.assertRaisesRegexp(ValidationError, "Invalid OrderedMap"):
            m2 = deepcopy(m)
            m2["order"].append(u"cool")
            from_json(ordered_map_schema, m2)
        with self.assertRaisesRegexp(ValidationError, "Invalid OrderedMap"):
            m2 = deepcopy(m)
            m2["order"] = [u"cool", u"groovy", u"kewl"]
            from_json(ordered_map_schema, m2)

