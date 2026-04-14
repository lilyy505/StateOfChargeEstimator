from typing import Any
import pyjson5
import os
from interpret import CanInterpreter



def parse_json5(json_file: str) -> Any:
    def replace_includes(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: replace_includes(v) for k, v in obj.items()} # type: ignore
        elif isinstance(obj, list):
            return [replace_includes(elem) for elem in obj] # type: ignore
        elif isinstance(obj, str) and obj.startswith("$"):
            filename = obj[1:]
            # change filename to be relative to the current file
            # also catch fopen errors and replace with {}
            filename = os.path.join(os.path.dirname(json_file), filename)
            if not os.path.exists(filename):
                return {}
            with open(filename, "r") as f:
                return pyjson5.load(f) # type: ignore
        else:
            return obj

    with open(json_file, "r") as f:
        parsed_json = pyjson5.load(f) # type: ignore
    return replace_includes(parsed_json)


class ConfigParseException(Exception):
    pass

class ModuleLoadException(Exception):
    def __init__(self, reason: str, source: Exception | None):
        self.reason = reason
        self.source = source

class ArgumentSource:
    def __init__(self, parsed_json: Any, can_interpreter: CanInterpreter, resource_name: str):
        self.parsed_json = parsed_json
        self.can_interpreter = can_interpreter
        self.resource_name = resource_name

    def get_arg(self, name: str, t: type, /, prompt_if_missing: bool = True) -> Any:
        arg: Any
        if name in self.parsed_json:
            arg = self.parsed_json[name]
        elif prompt_if_missing:
            arg = self._prompt_for_arg(name, t)
        else:
            raise ConfigParseException(f"Missing argument {name}")

        if isinstance(arg, t):
            return arg
        else:
            raise ConfigParseException(f"Invalid argument {name}: expected type {t}")

    def arg_in_json(self, name: str) -> bool:
        return name in self.parsed_json

    def _prompt_for_arg(self, name: str, t: type) -> Any:
        user_input = input(f'Enter argument "{name}" for {self.resource_name}: ')
        if t is int:
            return int(user_input)
        elif t is str:
            return user_input
        elif t is bool:
            return user_input.lower() == "true"
        else:
            raise ConfigParseException(f'Unsupported type "{t}"')

class TextSource:
    def __init__(self, text_file: str):
        self.text_file = text_file
        self.arguments = self._parse_text_file(text_file)

    def _parse_text_file(self, text_file: str) -> dict:
        args = {}
        if not os.path.exists(text_file):
            raise ConfigParseException(f"Text file {text_file} does not exist.")

        with open(text_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    args[key.strip()] = value.strip()
                else:
                    raise ConfigParseException(f"Malformed line in config file: {line}")
        return args

    def get_arg(self, name: str, t: type) -> any:
        if name in self.arguments:
            try:
                return self._convert(self.arguments[name], t)
            except Exception as e:
                raise ConfigParseException(f"Invalid argument {name}: expected type {t.__name__}") from e
        else:
            return self._prompt_for_arg(name, t)

    def arg_in_file(self, name: str) -> bool:
        return name in self.arguments

    def _prompt_for_arg(self, name: str, t: type) -> any:
        user_input = input(f'Enter argument "{name}" for {self.text_file}: ')
        try:
            return self._convert(user_input, t)
        except Exception as e:
            raise ConfigParseException(f"Invalid input for argument {name}") from e

    def _convert(self, value: str, t: type) -> any:
        if t is int:
            return int(value)
        elif t is bool:
            lower = value.lower()
            if lower in ["true", "yes", "1"]:
                return True
            elif lower in ["false", "no", "0"]:
                return False
            else:
                raise ValueError(f"Cannot convert '{value}' to bool")
        elif t is str:
            return value
        else:
            raise ConfigParseException(f'Unsupported type "{t}"')

def prompt_for_yes_or_no(text: str) -> bool:
    """
    Gives a y/n prompt to the user. This function takes care of adding "(y/n)" to the end of the
    prompt.
    Returns true if the user entered yes, and false if the user entered no.
    """
    while True:
        response: str = input(text + " (y/n): ")
        if response.strip().lower() == 'y':
            return True
        elif response.strip().lower() == 'n':
            return False
        else:
            print("Please enter 'y' or 'n'.")

# logging.basicConfig(format='[%(asctime)s]%(levelname)-7s:%(name)s: %(message)s', datefmt='%m/%d/%y %H:%M:%S', level="DEBUG")
# class Log(object):
#     MAGENTA = '\033[95m'
#     BLUE = '\033[94m'
#     GREEN = '\033[92m'
#     YELLOW = '\033[93m'
#     RED = '\033[91m'
#     GREY = '\033[0m'  # normal
#     ENDC = '\033[0m'


#     def __init__(self, name):
#         self.logger = logging.getLogger(name)
#         self.extra={'logger_name': name, 'endColor': self.ENDC, 'color': self.GREEN}


#     def info(self, msg):
#         self.extra['color'] = self.GREY
#         self.logger.info(msg, extra=self.extra)

#     def debug(self, msg):
#         self.extra['color'] = self.BLUE
#         self.logger.debug(msg, extra=self.extra)

#     def warning(self, msg):
#         self.extra['color'] = self.YELLOW
#         self.logger.warning(msg, extra=self.extra)

#     def error(self, msg):
#         self.extra['color'] = self.RED
#         self.logger.error(msg, extra=self.extra)
