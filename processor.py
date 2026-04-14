from utils import ArgumentSource
from message import Message

class Processor:
    """
    Processor is the base class for all processors. It takes in list of messages and returns an altered list of messages.
    This could be used to filter out messages, add new messages, or remap/change existing messages.
    """
    def __init__(self, arg_source: ArgumentSource):
        pass

    def handle(self, messages: list[Message]) -> list[Message]:
        return messages

