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

def array_from_json(datum, param, from_json):
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

def array_to_json(datum, param):
    """Serialize each item in the *datum* iterable using *param*. Return
    the resulting values in a list.
    """
    return [param.to_json(item) for item in datum]

def struct_from_json(datum, param, from_json):
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

def struct_to_json(datum, param):
    ret = {}
    for name, field in param.items():
        schema = field['schema']
        if name in datum.keys() and datum[name] != None:
            ret[name] = schema.to_json(datum[name])
    return ret


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


def map_from_json(datum, param, from_json):
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

def map_to_json(datum, param):
    ret = {}
    for key, val in datum.items():
        ret[key] = param.to_json(val)
    return ret

def assemble_even(datum):
    if datum % 2 != 0:
        raise ValidationError("Not even")
    return datum

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
    pass
class Boolean(Symbol):
    pass
class Schema(Symbol):
    pass
class Array(Symbol):
    pass
class Map(Symbol):
    pass
class OrderedMap(Symbol):
    pass
class Struct(Symbol):
    def __init__(self, param):
        if isinstance(param, OrderedDict):
            self.param = param
        else:
            self.param = OrderedDict(param)



def from_json(schema, datum):
    if schema == Boolean:
        return boolean_from_json(datum)
    elif schema == String:
        return string_from_json(datum)
    elif schema == Schema:
        if datum["type"] == "Boolean":
            return Boolean
        elif datum["type"] == "String":
            return String
        elif datum["type"] == "Schema":
            return Schema
        elif datum["type"] == "Array":
            param = from_json(Schema, datum["param"])
            return Array(param)
        elif datum["type"] == "Map":
            param = from_json(Schema, datum["param"])
            return Map(param)
        elif datum["type"] == "OrderedMap":
            param = from_json(Schema, datum["param"])
            return OrderedMap(param)
        elif datum["type"] == "Struct":
            param = from_json(OrderedMap(Struct([
                required("name", String),
                required("schema", Schema),
                required("required", Boolean)
            ])), datum["param"])
            return Struct(param)
    elif schema.__class__ == Array:
        return array_from_json(datum, schema.param, from_json)
    elif schema.__class__ == Map:
        return map_from_json(datum, schema.param, from_json)
    elif schema.__class__ == OrderedMap:
        datum = from_json(Struct([
            required("map", Map(schema.param)),
            required("order", Array(String)),
        ]), datum)
        return assemble_ordered_map(datum)
    elif schema.__class__ == Struct:
        return struct_from_json(datum, schema.param, from_json)


