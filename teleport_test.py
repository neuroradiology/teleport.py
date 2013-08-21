from unittest2 import TestCase

from copy import deepcopy

from teleport import *

class TestFloat(TestCase):

    def test_from_json(self):
        self.assertEqual(T(Float).from_json(1), 1.0)
        self.assertEqual(T(Float).from_json(1.0), 1.0)
        with self.assertRaisesRegexp(ValidationError, "Invalid Float"):
            T(Float).from_json(True)

    def test_to_json(self):
        self.assertEqual(T(Float).to_json(1.1), 1.1)


class TestInteger(TestCase):

    def test_from_json(self):
        self.assertEqual(T(Integer).from_json(1), 1)
        self.assertEqual(T(Integer).from_json(1.0), 1)
        with self.assertRaisesRegexp(ValidationError, "Invalid Integer"):
            T(Integer).from_json(1.1)

    def test_to_json(self):
        self.assertEqual(T(Integer).to_json(1), 1)


class TestBoolean(TestCase):

    def test_from_json(self):
        self.assertEqual(T(Boolean).from_json(True), True)
        with self.assertRaisesRegexp(ValidationError, "Invalid Boolean"):
            T(Boolean).from_json(0)

    def test_to_json(self):
        self.assertEqual(T(Boolean).to_json(True), True)


class TestString(TestCase):

    def test_string_okay(self):
        self.assertEqual(T(String).from_json(u"omg"), u"omg")
        self.assertEqual(T(String).from_json("omg"), u"omg")

    def test_string_fail(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid String"):
            T(String).from_json(0)
        with self.assertRaisesRegexp(UnicodeDecodeValidationError, "invalid start byte"):
            T(String).from_json("\xff")

    def test_to_json(self):
        self.assertEqual(T(String).to_json(u"yo"), u"yo")


class TestBinary(TestCase):

    def test_from_json(self):
        self.assertEqual(T(Binary).from_json('YWJj'), "abc")
        self.assertEqual(T(Binary).from_json(u'YWJj'), "abc")
        with self.assertRaisesRegexp(ValidationError, "Invalid base64"):
            # Will complain about incorrect padding
            T(Binary).from_json("a")
        with self.assertRaisesRegexp(ValidationError, "Invalid Binary"):
            T(Binary).from_json(1)

    def test_to_json(self):
        self.assertEqual(T(Binary).to_json("abc"), "YWJj")


class TestJSON(TestCase):

    def test_from_json(self):
        self.assertTrue(isinstance(T(JSON).from_json("A string?"), Box))
        self.assertEqual(T(JSON).from_json('ABC').datum, "ABC")

    def test_to_json(self):
        self.assertEqual(T(JSON).to_json(Box("abc")), "abc")


class TestMap(TestCase):

    def test_from_json_and_to_json(self):
        m = {
            u"cool": True,
            u"hip": False,
            u"groovy": True
        }
        map_serializer = T(Map(Boolean))
        self.assertEqual(map_serializer.from_json(m), m)
        self.assertEqual(map_serializer.to_json(m), m)
        with self.assertRaisesRegexp(ValidationError, "Invalid Map"):
            map_serializer.from_json([True, False])
        with self.assertRaisesRegexp(ValidationError, "must be unicode"):
            map_serializer.from_json({"nope": False})
        with self.assertRaisesRegexp(ValidationError, "Invalid Boolean"):
            map_serializer.from_json({u"cool": 0})


class Blah(TestCase):

    def test_schema(self):
        s = Array(Array(Integer))
        self.assertEqual(s, {
            "type": "Array",
            "param": {
                "type": "Array",
                "param": {"type": "Integer"}
            }
        })
        self.assertEqual(T(s).from_json([[2.0]]), [[2.0]])

    def test_trivial(self):
        self.assertEqual(T(Integer).from_json(1.0), 1)
        with self.assertRaises(ValidationError):
            T(Integer).from_json(1.1)
