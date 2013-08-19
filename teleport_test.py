from unittest2 import TestCase

from copy import deepcopy

from teleport import *

array_schema = {
    "type": u"Array",
    "param": {
        "type": u"Boolean"
    }
}
struct_schema = {
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
map_schema = {
    "type": u"Map",
    "param": {"type": "Boolean"}
}
ordered_map_schema = {
    "type": u"OrderedMap",
    "param": {"type": "Boolean"}
}
deep_schema = {
    "type": u"Array",
    "param": struct_schema
}
array_serializer = from_json(Schema, array_schema)
struct_serializer = from_json(Schema, struct_schema)
deep_serializer = from_json(Schema, deep_schema)
map_serializer = from_json(Schema, map_schema)
ordered_map_serializer = from_json(Schema, ordered_map_schema)

class TestSchema(TestCase):

    def test_to_json_schema(self):
        self.assertEqual(array_schema, to_json(Schema, array_serializer))
        self.assertEqual(struct_schema, to_json(Schema, struct_serializer))
        self.assertEqual(deep_schema, to_json(Schema, deep_serializer))
        struct_s = Struct([
            required(u"foo", Boolean, u"Never gonna give you up"),
            optional(u"bar", Integer)
        ])
        self.assertEqual(to_json(Schema, struct_s), struct_schema)

    def test_schema_subclass_delegation(self):
        self.assertEqual(from_json(Schema, {"type": u"Integer"}), Integer)
        self.assertEqual(from_json(Schema, {"type": u"Float"}), Float)
        self.assertEqual(from_json(Schema, {"type": u"Boolean"}), Boolean)
        self.assertEqual(from_json(Schema, {"type": u"String"}), String)
        self.assertEqual(from_json(Schema, {"type": u"Binary"}), Binary)
        self.assertEqual(from_json(Schema, {"type": u"Schema"}), Schema)
        self.assertEqual(from_json(Schema, {"type": u"JSON"}), JSON)

    def test_schema_duplicate_fields(self):
        s = deepcopy(struct_schema)
        s["param"]["order"].append("blah")
        with self.assertRaisesRegexp(ValidationError, "Invalid OrderedMap"):
            from_json(Schema, s)

    def test_schema_not_struct(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid Schema: True"):
            from_json(Schema, True)

    def test_schema_unknown_type(self):
        with self.assertRaisesRegexp(ValidationError, "Unknown type"):
            from_json(Schema, {"type": "number"})

    def test_deep_schema_validation_stack(self):
        # Test Python representatioon
        with self.assertRaisesRegexp(ValidationError, "\[0\]\[u'bar'\]"):
            from_json(deep_serializer, [{"foo": True, "bar": False}])

    def test_unexpected_param(self):
        s = deepcopy(array_schema)
        s["type"] = "Integer"
        with self.assertRaisesRegexp(ValidationError, "Unexpected param"):
            from_json(Schema, s)

    def test_missing_param(self):
        s = deepcopy(struct_schema)
        del s["param"]
        with self.assertRaisesRegexp(ValidationError, "Missing param"):
            from_json(Schema, s)



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


class TestArray(TestCase):

    def test_from_json(self):
        self.assertEqual(from_json(array_serializer, [True, False]), [True, False])
        with self.assertRaisesRegexp(ValidationError, "Invalid Array"):
            from_json(array_serializer, ("no", "tuples",))
        with self.assertRaisesRegexp(ValidationError, "Invalid Boolean"):
            from_json(array_serializer, [True, False, 1])


class TestMap(TestCase):

    def test_from_json_and_to_json(self):
        m = {
            u"cool": True,
            u"hip": False,
            u"groovy": True
        }
        self.assertEqual(from_json(map_serializer, m), m)
        self.assertEqual(to_json(map_serializer, m), m)
        with self.assertRaisesRegexp(ValidationError, "Invalid Map"):
            from_json(map_serializer, [True, False])
        with self.assertRaisesRegexp(ValidationError, "must be unicode"):
            from_json(map_serializer, {"nope": False})
        with self.assertRaisesRegexp(ValidationError, "Invalid Boolean"):
            from_json(map_serializer, {u"cool": 0})


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
        self.assertEqual(from_json(ordered_map_serializer, m), md)
        self.assertEqual(to_json(ordered_map_serializer, md), m)
        with self.assertRaisesRegexp(ValidationError, "Invalid OrderedMap"):
            m2 = deepcopy(m)
            m2["order"].append(u"cool")
            from_json(ordered_map_serializer, m2)
        with self.assertRaisesRegexp(ValidationError, "Invalid OrderedMap"):
            m2 = deepcopy(m)
            m2["order"] = [u"cool", u"groovy", u"kewl"]
            from_json(ordered_map_serializer, m2)


class TestStruct(TestCase):

    def test_from_json(self):
        res = from_json(struct_serializer, {"foo": True, "bar": 2.0})
        self.assertEqual(res, {"foo": True, "bar": 2})
        res = from_json(struct_serializer, {"foo": True})
        self.assertEqual(res, {"foo": True})

    def test_from_json_fail(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid Struct"):
            from_json(struct_serializer, [])
        with self.assertRaisesRegexp(ValidationError, "Unexpected fields"):
            from_json(struct_serializer, {"foo": True, "barr": 2.0})
        with self.assertRaisesRegexp(ValidationError, "Missing fields"):
            from_json(struct_serializer, {"bar": 2})

    def test_to_json(self):
        res = to_json(struct_serializer, {"foo": True})
        self.assertEqual(res, {"foo": True})
        res = to_json(struct_serializer, {"foo": True, "bar": None})
        self.assertEqual(res, {"foo": True})


class Suit(BasicWrapper):
    schema = String

    @staticmethod
    def assemble(datum):
        if datum not in ["hearts", "spades", "clubs", "diamonds"]:
            raise ValidationError("Invalid Suit", datum)
        return datum

class SuitArray(BasicWrapper):
    schema = Array(Suit)


class TestSuits(TestCase):

    def test_from_json(self):
        suits = ["hearts", "clubs", "clubs"]
        self.assertEqual(from_json(SuitArray, suits), suits)
        with self.assertRaisesRegexp(ValidationError, "Invalid Suit"):
            suits = ["hearts", "clubs", "clubz"]
            self.assertEqual(from_json(SuitArray, suits), suits)

    def test_to_json(self):
        self.assertEqual(to_json(Suit, u"hearts"), u"hearts")


class AllSuits(TypeMap):

    def __getitem__(self, name):
        if name == "Array":
            return BUILTIN_TYPES["Array"]
        elif name == "suit":
            return (Suit, None,)
        else:
            raise KeyError()


class TestTypeMap(TestCase):

    def test_custom_type_map_okay(self):

        with AllSuits():
            self.assertEqual(from_json(Schema, {
                "type": "suit"
            }), Suit)
            self.assertEqual(from_json(Schema, {
                "type": "Array",
                "param": {"type": "suit"}
            }).__class__, Array)

    def test_custom_type_map_fail(self):

        from_json(Schema, {"type": "Integer"})

        with self.assertRaises(UnknownTypeValidationError):
            with AllSuits():
                from_json(Schema, {"type": "Integer"})

    def test_wsgi_middleware(self):
        # Inspired by https://github.com/mitsuhiko/werkzeug/blob/master/werkzeug/testapp.py
        from werkzeug.wrappers import BaseResponse
        from werkzeug.test import Client

        def test_app(environ, start_response):
            # Needs to access AllSuits
            S = from_json(Schema, {"type": "suit"})
            response = BaseResponse(S.__name__, mimetype="text/plain")
            return response(environ, start_response)

        test_app = AllSuits().middleware(test_app)

        c = Client(test_app, BaseResponse)
        resp = c.get('/')

        self.assertEqual(resp.data, "Suit")

