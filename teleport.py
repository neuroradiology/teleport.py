import base64
from collections import OrderedDict

from werkzeug.local import LocalStack


class ValidationError(Exception):
    """Raised during desearialization. Stores the location of the error in the
    JSON document relative to its root.

    First argument is the error message, second optional argument is the
    object that failed validation.
    """

    def __init__(self, message, *args):
        self.message = message
        self.stack = []
        # Just the message or was there also an object passed in?
        self.has_obj = len(args) > 0
        if self.has_obj:
            self.obj = args[0]

    def __str__(self):
        ret = ""
        # If there is a stack, preface the message with a location
        if self.stack:
            stack = ""
            for item in reversed(self.stack):
                stack += '[' + repr(item) + ']'
            ret += "Item at %s " % stack
        # Main message
        ret += self.message
        # If an struct was passed in, represent it at the end
        if self.has_obj:
            ret += ": %s" % repr(self.obj)
        return ret

class UnicodeDecodeValidationError(ValidationError):
    pass


def integer_from_json(datum):
    """If *datum* is an integer, return it; if it is a float with a 0 for
    its fractional part, return the integer part as an int. Otherwise,
    raise a :exc:`ValidationError`.
    """
    if type(datum) == int:
        return datum
    if type(datum) == float and datum.is_integer():
        return int(datum)
    raise ValidationError("Invalid Integer", datum)

def float_from_json(datum):
    """If *datum* is a float, return it; if it is an integer, cast it to a
    float and return it. Otherwise, raise a :exc:`ValidationError`.
    """
    if type(datum) == float:
        return datum
    if type(datum) == int:
        return float(datum)
    raise ValidationError("Invalid Float", datum)

def string_from_json(datum):
    """If *datum* is of unicode type, return it. If it is a string, decode
    it as UTF-8 and return the result. Otherwise, raise a
    :exc:`ValidationError`. Unicode errors are dealt
    with strictly by raising :exc:`UnicodeDecodeValidationError`, a
    subclass of the above.
    """
    if type(datum) == unicode:
        return datum
    if type(datum) == str:
        try:
            return datum.decode('utf_8')
        except UnicodeDecodeError as inst:
            raise UnicodeDecodeValidationError(unicode(inst))
    raise ValidationError("Invalid String", datum)

def binary_from_json(datum):
    """If *datum* is a base64-encoded string, decode and return it. If not
    a string, or encoding is wrong, raise :exc:`ValidationError`.
    """
    if type(datum) in (str, unicode,):
        try:
            return base64.b64decode(datum)
        except TypeError:
            raise ValidationError("Invalid base64 encoding", datum)
    raise ValidationError("Invalid Binary data", datum)

def binary_to_json(datum):
    "Encode *datum* using base64."
    return base64.b64encode(datum)

def boolean_from_json(datum):
    """If *datum* is a boolean, return it. Otherwise, raise a
    :exc:`ValidationError`.
    """
    if type(datum) == bool:
        return datum
    raise ValidationError("Invalid Boolean", datum)

class Box(object):
    """Used as a wrapper around JSON data to disambiguate None as a JSON value
    (``null``) from None as an absense of value. Its :attr:`datum` attribute
    will hold the actual JSON value.

    For example, an HTTP request body may be empty in which case your function
    may return ``None`` or it may be "null", in which case the function can
    return a :class:`Box` instance with ``None`` inside.
    """
    def __init__(self, datum):
        self.datum = datum

def json_from_json(datum):
    """Return the JSON value wrapped in a :class:`Box`.
    """
    return Box(datum)

def json_to_json(datum):
    return datum.datum

def array_from_json(datum, param):
    """If *datum* is a list, construct a new list by putting each element
    of *datum* through a serializer provided as *param*. This serializer
    may raise a :exc:`ValidationError`. If *datum* is not a
    list, :exc:`ValidationError` will also be raised.
    """
    if type(datum) == list:
        ret = []
        for i, item in enumerate(datum):
            try:
                ret.append(param.from_json(item))
            except ValidationError as e:
                e.stack.append(i)
                raise
        return ret
    raise ValidationError("Invalid Array", datum)


def array_to_json(datum, param):
    """Serialize each item in the *datum* iterable using *param*. Return
    the resulting values in a list.
    """
    return [param.to_json(item) for item in datum]

def struct_from_json(datum, param):
    """If *datum* is a dict, deserialize it against *param* and return
    the resulting dict. Otherwise raise a :exc:`ValidationError`.

    A :exc:`ValidationError` will be raised if:

    1. *datum* is missing a required field
    2. *datum* has a field not declared in *param*.
    3. One of the values of *datum* does not pass validation as defined
       by the *schema* of the corresponding field.
    """
    if type(datum) == dict:
        ret = {}
        required = {}
        optional = {}
        for name, field in param.items():
            if field["required"] == True:
                required[name] = field["schema"]
            else:
                optional[name] = field["schema"]
        missing = set(required.keys()) - set(datum.keys())
        if missing:
            raise ValidationError("Missing fields", list(missing))
        extra = set(datum.keys()) - set(required.keys() + optional.keys())
        if extra:
            raise ValidationError("Unexpected fields", list(extra))
        for field, schema in optional.items() + required.items():
            if field in datum.keys():
                try:
                    ret[field] = schema.from_json(datum[field])
                except ValidationError as e:
                    e.stack.append(field)
                    raise
        return ret
    else:
        raise ValidationError("Invalid Struct", datum)

def struct_to_json(datum, param):
    ret = {}
    for name, field in param.items():
        schema = field['schema']
        if name in datum.keys() and datum[name] != None:
            ret[name] = schema.to_json(datum[name])
    return ret

def map_from_json(datum, param):
    """If *datum* is a dict, deserialize it, otherwise raise a
    :exc:`ValidationError`. The keys of the dict must be unicode, and the
    values will be deserialized using *param*.
    """
    if type(datum) == dict:
        ret = {}
        for key, val in datum.items():
            if type(key) != unicode:
                raise ValidationError("Map key must be unicode", key)
            try:
                ret[key] = param.from_json(val)
            except ValidationError as e:
                e.stack.append(key)
                raise
        return ret
    raise ValidationError("Invalid Map", datum)

def map_to_json(datum, param):
    ret = {}
    for key, val in datum.items():
        ret[key] = param.to_json(val)
    return ret

Integer = {"type": "Integer"}
Float = {"type": "Float"}
String = {"type": "String"}
Boolean = {"type": "Boolean"}
Binary = {"type": "Binary"}
JSON = {"type": "JSON"}
Schema = {"type": "Schema"}
Array = lambda param: {"type": "Array", "param": param}
Map = lambda param: {"type": "Map", "param": param}


def identity(datum):
    return datum

class T(object):

    types = {
        "Integer": (None, integer_from_json, identity),
        "Float": (None, float_from_json, identity),
        "String": (None, string_from_json, identity),
        "Boolean": (None, boolean_from_json, identity),
        "Binary": (None, binary_from_json, binary_to_json),
        "JSON": (None, json_from_json, json_to_json),
        "Array": (Schema, array_from_json, array_to_json),
        "Map": (Schema, map_from_json, map_to_json),
    }

    def __init__(self, json_schema):
        self.json_schema = json_schema
        self.type_name = json_schema["type"]

        if self.type_name == "Schema":
            self.from_json = lambda datum: self.__class__(datum)
            self.to_json = lambda datum: datum.json_schema
            return

        param_schema, from_json, to_json = self.types[self.type_name]

        if param_schema is None:
            self.from_json = from_json
            self.to_json = to_json
        else:
            param = T(param_schema).from_json(json_schema["param"])
            self.from_json = lambda datum: from_json(datum, param)
            self.to_json = lambda datum: to_json(datum, param)

