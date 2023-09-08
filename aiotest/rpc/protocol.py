# encoding: utf-8

import msgpack


class Message():
    def __init__(self, message_type, data, node_id):
        self.type = message_type
        self.data = data
        self.node_id = node_id
    
    def __repr__(self):
        return f"<Message {self.type}:{self.node_id}>"
    
    def serialize(self):
        "Pack object o and return packed bytes"
        return msgpack.packb((self.type, self.data, self.node_id))
    
    @classmethod
    def unserialize(cls, data):
        "Unpack an object"
        return cls(*msgpack.unpackb(data, raw=False, strict_map_key=False))
