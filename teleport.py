import sys
import json
import base64
from collections import OrderedDict
from copy import deepcopy



def field(name, schema):
    return {
        "name": name,
        "schema": schema
    }


class ValidationError(Exception):
    pass

class UnicodeDecodeValidationError(ValidationError):
    pass


class StringType(object):

    def deserialize(self, datum):
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

    def serialize(self, datum):
        return datum


class ArrayType(object):

    def __init__(self, items):
        self.items = items

    def deserialize(self, datum):
        return [items.deserialize(item) for item in datum]

    def serialize(self, datum):
        return [items.serialize(item) for item in datum]

    @classmethod
    def get_param_type(cls):
        return SchemaType()


class StructType(object):

    def __init__(self, fields):
        self.fields = fields

    def deserialize(self, datum):
        ret = {}
        for field in self.fields:
            name = field["name"]
            schema = field["schema"]
            if name in datum.keys():
                ret[name] = schema.deserialize(datum[name])
        return ret

    def serialize(self, datum):
        ret = {}
        for field in self.fields:
            name = field["name"]
            schema = field["schema"]
            if name in datum.keys():
                ret[name] = schema.serialize(datum[name])
        return ret

    @classmethod
    def get_param_type(cls):
        return ArrayType(StructType([
            field("name", StringType()),
            field("schema", SchemaType())
        ]))

class SchemaType(object):
    pass




