from unittest2 import TestCase
from copy import deepcopy

from teleport import *

array_schema = {
    "type": "array",
    "items": {
        "type": "boolean"
    }
}
object_schema = {
    "type": "object",
    "properties": [
        {
            "name": "foo",
            "schema": {"type": "boolean"}
        },
        {
            "name": "bar",
            "schema": {"type": "integer"}
        }
    ]
}
deep_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": [
            {
                "name": "foo",
                "schema": {"type": "boolean"}
            },
            {
                "name": "bar",
                "schema": {"type": "integer"}
            }
        ]
    }
}

class TestSchema(TestCase):
    pass
