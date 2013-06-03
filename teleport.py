import base64
from collections import OrderedDict

from werkzeug.local import LocalStack


class TypeMap(object):
    """Teleport is made extendable by allowing the application to define a
    custom mapping of type names (strings such as ``"Integer"``) to serializer
    classes. I could have defined a global mapping object for all applications
    to share, like Python's own :keyword:`sys.modules`, but this would
    prohibit multiple Teleport extentions to operate in clean isolation.
    Global state is evil, and Teleport successfully avoids it using Werkzeug's
    brilliant `Context Locals <http://werkzeug.pocoo.org/docs/local/>`_.

    To extend Teleport with your custom type, subclass :class:`TypeMap`::

        class ExtendedTypeMap(TypeMap):

            def __getitem__(self, name):
                if name == "YesNoMaybe":
                    return (YesNoMaybe, None,)
                else:
                    return BUILTIN_TYPES[name]

    :class:`ExtendedTypeMap` is an extention of Teleport, to enable it within
    a specific code block, use Python's :keyword:`with` statement::

        # Only built-in types accessible here
        with ExtendedTypeMap():
            # Built-in types as well as "YesNoMaybe" are accessible
            with TypeMap():
                # Only built-in types here
                pass

    To avoid repeating this :keyword:`with` statement, put it at the entry
    point of your program. If your program is a WSGI server, use the
    :meth:`middleware` method to set the mapping for the entire
    application.

    If you are planning to serialize schemas containing custom types, Teleport
    will get the type name from the serializer class (it can also be overridden
    with the :attr:`type_name` attribute)::

        >>> Schema.to_json(YesNoMaybe)
        {'type': 'YesNoMaybe'}

    When you deserialize it (whether it is done by the same program or by a
    different program entirely), you need to ensure it will have access to
    the custom types that you defined.
    """

    def __getitem__(self, name):
        return BUILTIN_TYPES[name]

    def middleware(self, wsgi_app):
        """To use in `Flask <http://flask.pocoo.org/>`_::

            app = Flask(__name__)

            app.wsgi_app = ExtendedTypeMap().middleware(app.wsgi_app)
            app.run()

        In `Django <https://www.djangoproject.com/>`_ (see the
        auto-generated ``wsgi.py`` module)::

            from django.core.wsgi import get_wsgi_application
            application = get_wsgi_application()
            application = ExtendedTypeMap().middleware(application)

        """
        def wrapped(environ, start_response):
            with self:
                return wsgi_app(environ, start_response)
        return wrapped

    def __enter__(self):
        _ctx_stack.push(self)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        _ctx_stack.pop()


_ctx_stack = LocalStack()
# If no TypeMap is found on the stack, use the global object
_global_map = TypeMap()

def _get_current_map():
    if _ctx_stack.top != None:
        return _ctx_stack.top
    else:
        return _global_map


# Some syntax sugar
def required(name, schema):
    return (name, {"schema": schema},)



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

class UnknownTypeValidationError(ValidationError):
    pass



class Basic(object):

    @classmethod
    def from_box(cls, box):
        if box == None:
            raise ValidationError("Non-empty value expected")
        return cls.from_json(box.datum)

    @classmethod
    def to_box(cls, datum):
        return Box(cls.to_json(datum))



class Parametrized(object):

    def __init__(self, param):
        self.param = param

    def from_box(self, box):
        return self.from_json(box.datum)

    def to_box(self, datum):
        return Box(self.to_json(datum))



class BasicWrapper(Basic):

    @classmethod
    def from_box(cls, datum):
        datum = cls.schema.from_box(datum)
        return cls.inflate(datum)

    @classmethod
    def to_box(cls, datum):
        datum = cls.deflate(datum)
        return cls.schema.to_box(datum)

    @classmethod
    def inflate(cls, datum): # pragma: no cover
        return datum

    @classmethod
    def deflate(cls, datum): # pragma: no cover
        return datum



class ParametrizedWrapper(Parametrized):

    def from_box(self, datum):
        datum = self.schema.from_box(datum)
        return self.inflate(datum)

    def to_box(self, datum):
        datum = self.deflate(datum)
        return self.schema.to_box(datum)

    def inflate(self, datum): # pragma: no cover
        return datum

    def deflate(self, datum): # pragma: no cover
        return datum



class BasicPrimitive(Basic):

    @staticmethod
    def from_json(datum): # pragma: no cover
        return datum

    @staticmethod
    def to_json(datum): # pragma: no cover
        return datum



class ParametrizedPrimitive(Parametrized):
    pass



class Integer(BasicPrimitive):

    @staticmethod
    def from_json(datum):
        """If *datum* is an integer, return it; if it is a float with a 0 for
        its fractional part, return the integer part as an int. Otherwise,
        raise a :exc:`ValidationError`.
        """
        if type(datum) == int:
            return datum
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid Integer", datum)



class Float(BasicPrimitive):

    @staticmethod
    def from_json(datum):
        """If *datum* is a float, return it; if it is an integer, cast it to a
        float and return it. Otherwise, raise a :exc:`ValidationError`.
        """
        if type(datum) == float:
            return datum
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid Float", datum)



class String(BasicPrimitive):

    @staticmethod
    def from_json(datum):
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



class Binary(BasicPrimitive):

    @staticmethod
    def from_json(datum):
        """If *datum* is a base64-encoded string, decode and return it. If not
        a string, or encoding is wrong, raise :exc:`ValidationError`.
        """
        if type(datum) in (str, unicode,):
            try:
                return base64.b64decode(datum)
            except TypeError:
                raise ValidationError("Invalid base64 encoding", datum)
        raise ValidationError("Invalid Binary data", datum)

    @staticmethod
    def to_json(datum):
        "Encode *datum* using base64."
        return base64.b64encode(datum)



class Boolean(BasicPrimitive):

    @staticmethod
    def from_json(datum):
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



class JSON(BasicPrimitive):

    @staticmethod
    def from_box(datum):
        return datum

    @staticmethod
    def to_box(datum):
        return datum

    @staticmethod
    def from_json(datum):
        """Return the JSON value wrapped in a :class:`Box`.
        """
        return Box(datum)

    @staticmethod
    def to_json(datum):
        return datum.datum



class Array(ParametrizedPrimitive):
    """The argument *param* is a serializer that defines the type of each item
    in the array.
    """

    def from_json(self, datum):
        """If *datum* is a list, construct a new list by putting each element
        of *datum* through a serializer provided as *param*. This serializer
        may raise a :exc:`ValidationError`. If *datum* is not a
        list, :exc:`ValidationError` will also be raised.
        """
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(self.param.from_box(Box(item)))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid Array", datum)

    def to_json(self, datum):
        """Serialize each item in the *datum* iterable using *param*. Return
        the resulting values in a list.
        """
        return [self.param.to_json(item) for item in datum]



class Struct(ParametrizedPrimitive):
    """*param* must be an :class:`OrderedDict`, where the keys are field
    names, and values are dicts with two items: *schema* (serializer) and
    *required* (Boolean). For each pair, *schema* is used to serialize and
    deserialize a dict value matched by the corresponding key.

    For convenience, :class:`Struct` can be instantiated with a list of tuples
    like the constructor of :class:`OrderedDict`.
    """

    def __init__(self, param):
        if type(param) == list:
            param = OrderedDict(param)
        self.param = param

    def from_json(self, datum):
        """If *datum* is a dict, deserialize it against *param* and return
        the resulting dict. Otherwise raise a :exc:`ValidationError`.

        A :exc:`ValidationError` will be raised if:

        1. *datum* is missing a required field
        2. *datum* has a field not declared in *param*.
        3. One of the values of *datum* does not pass validation as defined
           by the *schema* of the corresponding field.
        """
        if type(datum) == dict:
            boxes = {}
            for key, val in datum.items():
                if val != None:
                    boxes[key] = Box(val)
            ret = {}
            extra = set(boxes.keys()) - set(self.param.keys())
            if extra:
                raise ValidationError("Unexpected fields", list(extra))
            for field, f in self.param.items():
                schema = f["schema"]
                box = boxes.get(field, None)
                try:
                    r = schema.from_box(box)
                    if r:
                        ret[field] = r
                except ValidationError as e:
                    e.stack.append(field)
                    raise
            return ret
        else:
            raise ValidationError("Invalid Struct", datum)

    def to_json(self, datum):
        ret = {}
        for name, field in self.param.items():
            schema = field['schema']
            if name in datum.keys() and datum[name] != None:
                b = schema.to_box(datum[name])
                if b:
                    ret[name] = b.datum
        return ret



class Map(ParametrizedPrimitive):
    """The argument *param* is a serializer that defines the type of each item
    in the map.
    """

    def from_json(self, datum):
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
                    ret[key] = self.param.from_box(Box(val))
                except ValidationError as e:
                    e.stack.append(key)
                    raise
            return ret
        raise ValidationError("Invalid Map", datum)

    def to_json(self, datum):
        ret = {}
        for key, val in datum.items():
            ret[key] = self.param.to_json(val)
        return ret



class OrderedMap(ParametrizedWrapper):
    """The argument *param* is a serializer that defines the type of each item
    in the map.

    Internal schema::

        Struct([
            required(u"map", Map(param)),
            required(u"order", Array(String))
        ])

    The order of the items in *map* is not preserved by JSON, hence the
    existence of *order*, an array of keys in *map*.
    """

    def __init__(self, param):
        self.param = param
        self.schema = Struct([
            required(u"map", Map(param)),
            required(u"order", Array(String))
        ])

    def inflate(self, datum):
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

    def deflate(self, datum):
        return {
            "map": dict(datum.items()),
            "order": datum.keys()
        }



class Schema(BasicPrimitive):

    @staticmethod
    def to_json(datum):
        """If the serializer passed in as *datum* has a :meth:`serialize_self`
        method, use it. Otherwise, return a simple schema by finding the type
        in the serializer's :attr:`type_name` attribute.
        """
        # Type name is declared explicitly
        if hasattr(datum, "type_name"):
            type_name = datum.type_name
        # If datum is a class, use its name
        elif datum.__class__ == type:
            type_name = datum.__name__
        # Otherwise assume it's an instance
        else:
            type_name = datum.__class__.__name__
        param_schema = _get_current_map()[type_name][1]
        if param_schema != None:
            return {
                "type": type_name,
                "param": param_schema.to_box(datum.param).datum
            }
        else:
            return {"type": type_name}

    @staticmethod
    def from_json(datum):
        """Datum must be a dict with a key *type* that has a string value.
        This value will me passed into the :meth:`get` method of the current
        :class:`TypeMap` instance to get the matching serializer. If no serializer
        is found, :exc:`UnknownTypeValidationError` will be raised.
        """
        # Peek into dict struct to get the type
        if type(datum) != dict or "type" not in datum.keys():
            raise ValidationError("Invalid Schema", datum)

        t = datum["type"]

        # Try to get the serializer class from the current TypeMap
        try:
            serializer, param_schema = _get_current_map()[t]
        except KeyError:
            raise UnknownTypeValidationError("Unknown type", t)

        # Deserialize or instantiate
        if param_schema != None:
            param = param_schema.from_box(Box(datum["param"]))
            return serializer(param)
        else:
            return serializer



class Nothing(BasicPrimitive):

    @staticmethod
    def from_box(nothing):
        if nothing != None:
            raise ValidationError("Nothing expected", nothing)
        return None

    @staticmethod
    def to_box(nothing):
        return None



class Maybe(ParametrizedPrimitive):

    def from_box(self, datum):
        if datum == None:
            return None
        return self.param.from_box(datum)

    def to_box(self, datum):
        if datum == None:
            return None
        return self.param.to_box(datum)



class Dynamic(BasicWrapper):
    schema = Struct([
        required("schema", Schema),
        required("datum", Maybe(JSON))
    ])

    @staticmethod
    def inflate(datum):
        return {
            "schema": datum["schema"],
            "datum": datum["schema"].from_box(datum.get("datum", None))
        }

    @staticmethod
    def deflate(datum):
        return {
            "schema": datum["schema"],
            "datum": datum["schema"].to_box(datum["datum"])
        }




BUILTIN_TYPES = {
    "Maybe": (Maybe, Schema),
    "Nothing": (Nothing, None),
    "Dynamic": (Dynamic, None),
    "Integer": (Integer, None),
    "Float": (Float, None),
    "String": (String, None),
    "Binary": (Binary, None),
    "Boolean": (Boolean, None),
    "Schema": (Schema, None),
    "JSON": (JSON, None),
    "Array": (Array, Schema),
    "Map": (Map, Schema),
    "OrderedMap": (OrderedMap, Schema),
    "Struct": (Struct, OrderedMap(Struct([
        required(u"schema", Schema)
    ])))
}
