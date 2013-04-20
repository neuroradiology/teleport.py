import sys
import json
import base64
from copy import deepcopy

def prop(name, schema):
    return {
        "name": name,
        "schema": schema
    }

class ValidationError(Exception):
    """Raised by the model system. Stores the location of the error in the
    JSON document relative to its root for a more useful stack trace.

    First parameter is the error *message*, second optional parameter is the
    object that failed validation.
    """

    def __init__(self, message, *args):
        super(ValidationError, self).__init__(message)
        self.stack = []
        # Just the message or was there also an object passed in?
        self.has_obj = len(args) > 0
        if self.has_obj:
            self.obj = args[0]

    def _print_with_format(self, func):
        # Returns the full error message with the representation
        # of its literals determined by the passed in function.
        ret = ""
        # If there is a stack, preface the message with a location
        if self.stack:
            stack = ""
            for item in reversed(self.stack):
                stack += '[' + func(item) + ']'
            ret += "Item at %s " % stack
        # Main message
        ret += self.message
        # If an object was passed in, represent it at the end
        if self.has_obj:
            ret += ": %s" % func(self.obj)
        return ret

    def __str__(self):
        return self._print_with_format(repr)

    def print_json(self):
        """Print the same message as the one you would find in a
        console stack trace, but using JSON to output all the language
        literals. This representation is used for sending error
        messages over the wire.
        """
        return self._print_with_format(json.dumps)

class UnicodeDecodeValidationError(ValidationError):
    """A subclass of :exc:`~cosmic.exceptions.ValidationError` raised
    in place of a :exc:`UnicodeDecodeError`.
    """


class BaseModel(object):

    def __init__(self, data, **kwargs):
        self.data = data

    def serialize(self):
        """Serialize could be a classmethod like normalize, but by defining it
        this way, we are allowing a more natural syntax. Both of these work
        identically:
         
            >>> Animal.serialize(cat)
            >>> cat.serialize()

        """
        return self.data

    @classmethod
    def normalize(cls, datum): # pragma: no cover
        cls.validate(datum)
        return datum

    @classmethod
    def validate(cls, datum):
        pass


class Model(BaseModel):

    def serialize(self):
        # Serialize against model schema
        schema = self.get_schema()
        return schema.serialize_data(self.data)

    @classmethod
    def normalize(cls, datum):
        # Normalize against model schema
        schema = cls.get_schema()
        datum = schema.normalize_data(datum)
        cls.validate(datum)
        return cls(datum)

    @classmethod
    def get_schema(cls):
        return cls.schema


def normalize_schema(datum):
    # Peek into the object before letting the real models
    # do proper validation
    if type(datum) != dict or "type" not in datum.keys():
        raise ValidationError("Invalid schema", datum)
        
    datum = deepcopy(datum)
    st = datum.pop("type")

    # Simple model?
    simple = [
        IntegerModel,
        FloatModel,
        StringModel,
        BinaryModel,
        BooleanModel,
        JSONData,
        Schema
    ]
    for simple_cls in simple:
        if st == simple_cls.match_type:
            schema = Schema({})
            schema.match_type = simple_cls.match_type
            schema.model_cls = simple_cls
            return schema

    comp = [
        ArraySchema,
        ObjectSchema
    ]

    for simple_cls in comp:
        if st == simple_cls.match_type:
            return simple_cls.normalize(datum)

    # Model?
    if '.' in st:
        schema = Schema({})
        schema.match_type = st
        schema.model_cls = None
        return schema

    raise ValidationError("Unknown type", st)



class Schema(Model):
    match_type = "schema"

    def normalize_data(self, datum):
        if self.model_cls == Schema:
            return normalize_schema(datum)
        return self.model_cls.normalize(datum, **self.data)

    def serialize_data(self, datum):
        return self.model_cls.serialize(datum, **self.data)

    def serialize(self):
        s = {"type": self.match_type}
        s.update(self.get_schema().serialize_data(self.data))
        return s

    @classmethod
    def get_schema(cls):
        return ObjectSchema({
            "properties": []
        })







class ObjectModel(BaseModel):
    match_type = "object"

    @classmethod
    def normalize(cls, datum, properties):
        """If *datum* is a dict, normalize it against *properties* and return
        the resulting dict. Otherwise raise a
        :exc:`~cosmic.exceptions.ValidationError`.

        *properties* must be a list of dicts, where each dict has two
        attributes: *name*, and *schema*. *name* is a string representing the
        property name, *schema* is an instance of a
        :class:`~cosmic.models.Schema` subclass, such as :class:`IntegerSchema`.

        A :exc:`~cosmic.exceptions.ValidationError` will be raised if:

        1. *datum* has a property not declared in *properties*
        2. One of the properties of *datum* does not pass validation as defined
           by the corresponding *schema*

        """
        if type(datum) == dict:
            ret = {}
            props = {}
            for prop in properties:
                props[prop["name"]] = prop["schema"]
            extra = set(datum.keys()) - set(props.keys())
            if extra:
                raise ValidationError("Unexpected properties", list(extra))
            for prop, schema in props.items():
                if prop in datum.keys():
                    try:
                        ret[prop] = schema.normalize_data(datum[prop])
                    except ValidationError as e:
                        e.stack.append(prop)
                        raise
            return ret
        raise ValidationError("Invalid object", datum)

    @classmethod
    def serialize(cls, datum, properties):
        """For each property in *properties*, serialize the corresponding
        value in *datum* (if the value exists) against the property schema.
        Return the resulting dict.
        """
        ret = {}
        for prop in properties:
            name = prop['name']
            if name in datum.keys() and datum[name] != None:
                ret[name] = prop['schema'].serialize_data(datum[name])
        return ret


class ObjectSchema(Schema):
    model_cls = ObjectModel
    match_type = "object"

    @classmethod
    def get_schema(cls):
        return ObjectSchema({
            "properties": [
                prop("properties", ArraySchema({
                    "items": ObjectSchema({
                        "properties": [
                            prop("name", normalize_schema({"type": "string"})),
                            prop("schema", normalize_schema({"type": "schema"}))
                        ]
                    })
                }))
            ]
        })

    @classmethod
    def validate(cls, datum):
        """Raises :exc:`~cosmic.exception.ValidationError` if there are two
        properties with the same name.
        """
        # Additional validation to check for duplicate properties
        props = [prop["name"] for prop in datum['properties']]
        if len(props) > len(set(props)):
            raise ValidationError("Duplicate properties")




class ArrayModel(BaseModel):
    match_type = "array"

    @classmethod
    def normalize(cls, datum, items):
        """If *datum* is a list, construct a new list by putting each element
        of *datum* through a schema provided as *items*. This schema may raise
        :exc:`~cosmic.exceptions.ValidationError`. If *datum* is not a list,
        :exc:`~cosmic.exceptions.ValidationError` will be raised.
        """
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(items.normalize_data(item))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid array", datum)

    @classmethod
    def serialize(cls, datum, items):
        """Serialize each item in the *datum* list using the schema provided
        in *items*. Return the resulting list.
        """
        return [items.serialize_data(item) for item in datum]


class ArraySchema(Schema):
    model_cls = ArrayModel
    match_type = u"array"

    @classmethod
    def get_schema(cls):
        return ObjectSchema({
            "properties": [
                prop("items", normalize_schema({"type": "schema"}))
            ]
        })






class IntegerModel(BaseModel):
    match_type = "integer"

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is an integer, return it; if it is a float with a 0 for
        its fractional part, return the integer part as an int. Otherwise,
        raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == int:
            return datum
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer", datum)

    @classmethod
    def serialize(cls, datum):
        return datum





class FloatModel(BaseModel):
    match_type = "float"

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is a float, return it; if it is an integer, cast it to a
        float and return it. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == float:
            return datum
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float", datum)

    @classmethod
    def serialize(cls, datum):
        return datum





class StringModel(BaseModel):
    match_type = "string"

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is of unicode type, return it. If it is a string, decode
        it as UTF-8 and return the result. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`. Unicode errors are dealt
        with strictly by raising
        :exc:`~cosmic.exceptions.UnicodeDecodeValidationError`, a
        subclass of the above.
        """
        if type(datum) == unicode:
            return datum
        if type(datum) == str:
            try:
                return datum.decode('utf_8')
            except UnicodeDecodeError as inst:
                raise UnicodeDecodeValidationError(unicode(inst))
        raise ValidationError("Invalid string", datum)

    @classmethod
    def serialize(cls, datum):
        return datum






class BinaryModel(BaseModel):
    match_type = "binary"

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is a base64-encoded string, decode and return it. If not
        a string, or encoding is wrong, raise
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) in (str, unicode,):
            try:
                return base64.b64decode(datum)
            except TypeError:
                raise ValidationError("Invalid base64 encoding", datum)
        raise ValidationError("Invalid binary data", datum)

    @classmethod
    def serialize(cls, datum):
        """Encode *datum* in base64."""
        return base64.b64encode(datum)





class BooleanModel(BaseModel):
    match_type = "boolean"

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is a boolean, return it. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean", datum)

    @classmethod
    def serialize(cls, datum):
        return datum






class JSONData(BaseModel):
    match_type = "json"

    def __repr__(self):
        contents = json.dumps(self.data)
        if len(contents) > 60:
            contents = contents[:56] + " ..."
        return "<JSONData %s>" % contents

    @classmethod
    def from_string(cls, s):
        if s == "":
            return None
        return cls.normalize(json.loads(s))

    @classmethod
    def normalize(cls, datum):
        # No need to validate
        return cls(datum)

    @classmethod
    def to_string(cls, s):
        if s == None:
            return ""
        return json.dumps(s.serialize())




class ClassModel(ObjectModel):

    def __init__(self, **kwargs):
        self.data = {}
        self.props = {}
        for prop in self.properties:
            self.props[prop["name"]] = prop
        for key, value in kwargs.items():
            if key in self.props.keys():
                self.data[key] = value
            else:
                raise TypeError("Unexpected keyword argument '%s'" % key)

    def __getattr__(self, key):
        for prop in self.properties:
            if prop["name"] == key:
                return self.data.get(key, None)
        raise AttributeError()

    def __setattr__(self, key, value):
        for prop in self.properties:
            if prop["name"] == key:
                if value == None:
                    del self.data[key]
                else:
                    self.data[key] = value
                return
        super(ObjectModel, self).__setattr__(key, value)

    @classmethod
    def normalize(cls, datum):
        datum = cls.get_schema().normalize_data(datum)
        cls.validate(datum)
        return cls(**datum)

    def serialize(self):
        return self.get_schema().serialize_data(self.data)

    @classmethod
    def get_schema(cls):
        return ObjectSchema({
            "properties": cls.properties
        })


def normalize_json(schema, datum):
    if schema and not datum:
        raise ValidationError("Expected JSONData, found None")
    if datum and not schema:
        raise ValidationError("Expected None, found JSONData")
    if schema and datum:
        return schema.normalize_data(datum.data)
    return None

def serialize_json(schema, datum):
    if schema and not datum:
        raise ValidationError("Expected data, found None")
    if datum and not schema:
        raise ValidationError("Expected None, found data")
    if schema and datum:
        return JSONData(schema.serialize_data(datum))
    return None

