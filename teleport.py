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
    """If *datum* is an integer, return it; if it is a float with a 0 for its
    fractional part, return the integer part as an int. Otherwise, raise a
    :exc:`ValidationError`.
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
    """If *datum* is of unicode type, return it. If it is a string, decode it
    as UTF-8 and return the result. Otherwise, raise a
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

def binary_from_json(datum):
    """If *datum* is a base64-encoded string, decode and return it. If not a
    string, or encoding is wrong, raise :exc:`ValidationError`.
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

def ordered_map_stuff(param):

    def assemble_ordered_map(datum):
        """:exc:`ValidationError` is raised if *order* does not correspond to
        the keys in *map*. The native form is Python's :class:`OrderedDict`.
        """
        order = datum["order"]
        keys = datum["map"].keys()
        if len(order) != len(keys) or set(order) != set(keys):
            raise ValidationError("Invalid OrderedMap", datum)
        # Turn into OrderedDict instance
        ret = OrderedDict()
        for key in order:
            ret[key] = datum["map"][key]
        return ret

    def disassemble_ordered_map(datum):
        return {
            "map": dict(datum.items()),
            "order": datum.keys()
        }

    wrapper_schema = Struct([
        required("map", Map(param)),
        required("order", Array(String)),
    ])

    def ordered_map_from_json(datum, from_json):
        return assemble_ordered_map(from_json(wrapper_schema, datum))

    def ordered_map_to_json(datum, to_json):
        return to_json(wrapper_schema, disassemble_ordered_map(datum))

    return (ordered_map_from_json, ordered_map_to_json)


def array_stuff(param):

    def array_from_json(datum, from_json):
        """If *datum* is a list, construct a new list by putting each element of
        *datum* through a serializer provided as *param*. This serializer may
        raise a :exc:`ValidationError`. If *datum* is not a list,
        :exc:`ValidationError` will also be raised.
        """
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(from_json(param, item))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid Array", datum)

    def array_to_json(datum, to_json):
        """Serialize each item in the *datum* iterable using *param*. Return
        the resulting values in a list.
        """
        return [to_json(param, item) for item in datum]

    return (array_from_json, array_to_json)

def map_stuff(param):

    def map_from_json(datum, from_json):
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
                    ret[key] = from_json(param, val)
                except ValidationError as e:
                    e.stack.append(key)
                    raise
            return ret
        raise ValidationError("Invalid Map", datum)

    def map_to_json(datum, to_json):
        ret = {}
        for key, val in datum.items():
            ret[key] = to_json(param, val)
        return ret

    return (map_from_json, map_to_json)


def struct_stuff(param):

    def struct_from_json(datum, from_json):
        """If *datum* is a dict, deserialize it against *param* and return the
        resulting dict. Otherwise raise a :exc:`ValidationError`.

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
                        ret[field] = from_json(schema, datum[field])
                    except ValidationError as e:
                        e.stack.append(field)
                        raise
            return ret
        else:
            raise ValidationError("Invalid Struct", datum)

    def struct_to_json(datum, to_json):
        ret = {}
        for name, field in param.items():
            schema = field['schema']
            if name in datum.keys() and datum[name] != None:
                ret[name] = to_json(schema, datum[name])
        return ret

    return (struct_from_json, struct_to_json)





# Some syntax sugar
def required(name, schema, doc=None):
    return (name, {"schema": schema, "required": True, "doc": doc})

def optional(name, schema, doc=None):
    return (name, {"schema": schema, "required": False, "doc": doc})


def identity(datum):
    return datum


class Symbol(object):
    def __init__(self, param):
        self.param = param

class String(Symbol):
    type_name = "String"
class Integer(Symbol):
    type_name = "Integer"
class Float(Symbol):
    type_name = "Float"
class Boolean(Symbol):
    type_name = "Boolean"
class Schema(Symbol):
    type_name = "Schema"
class JSON(Symbol):
    type_name = "JSON"
class Binary(Symbol):
    type_name = "Binary"
class Array(Symbol):
    type_name = "Array"
class Map(Symbol):
    type_name = "Map"
class OrderedMap(Symbol):
    type_name = "OrderedMap"
class Struct(Symbol):
    type_name = "Struct"
    def __init__(self, param):
        if isinstance(param, OrderedDict):
            self.param = param
        else:
            self.param = OrderedDict(param)

basic_types = {
    "Boolean": (Boolean, boolean_from_json, identity),
    "String": (String, string_from_json, identity),
    "Integer": (Integer, integer_from_json, identity),
    "Float": (Float, float_from_json, identity),
    "JSON": (JSON, json_from_json, json_to_json),
    "Binary": (Binary, binary_from_json, binary_to_json),
}

parametrized_types = {
    "Array": (Array, Schema, array_stuff),
    "Map": (Map, Schema, map_stuff),
    "OrderedMap": (OrderedMap, Schema, ordered_map_stuff),
    "Struct": (Struct, OrderedMap(Struct([
                    required("schema", Schema),
                    required("required", Boolean),
                    optional("doc", String)
                ])), struct_stuff)
}

class Teleport(object):

    def from_json(self, schema, datum):
        if schema.type_name in basic_types:
            return basic_types[schema.type_name][1](datum)
        elif schema.type_name in parametrized_types:
            (_from_json, _) = parametrized_types[schema.type_name][2](schema.param)
            return _from_json(datum, self.from_json)
        elif schema == Schema:
            if datum["type"] in basic_types:
                return basic_types[datum["type"]][0]
            elif datum["type"] in parametrized_types:
                (schema, param_schema, stuff) = parametrized_types[datum['type']]
                param = self.from_json(param_schema, datum['param'])
                return schema(param)
            elif datum["type"] == "Schema":
                return Schema

    def to_json(self, schema, datum):
        if schema.type_name in basic_types:
            return basic_types[schema.type_name][2](datum)
        elif schema.type_name in parametrized_types:
            (_, _to_json) = parametrized_types[schema.type_name][2](schema.param)
            return _to_json(datum, self.to_json)

default = Teleport()

from_json = default.from_json
to_json = default.to_json


