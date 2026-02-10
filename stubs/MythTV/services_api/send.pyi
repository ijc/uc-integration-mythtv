from ._version import __version__ as __version__
from .mythversions import MYTHTV_VERSION_LIST as MYTHTV_VERSION_LIST
from _typeshed import Incomplete

class Send:
    host: Incomplete
    port: Incomplete
    endpoint: Incomplete
    jsondata: Incomplete
    postdata: Incomplete
    rest: Incomplete
    session_token: Incomplete
    opts: Incomplete
    session: Incomplete
    server_version: str
    logger: Incomplete
    def __init__(self, host, port: int = 6544) -> None: ...
    def send(self, endpoint: str = '', postdata=None, jsondata=None, rest: str = '', opts=None): ...
    def close_session(self) -> None: ...
    @property
    def get_server_version(self): ...
    @property
    def get_opts(self): ...
    def get_headers(self, header=None): ...

class SessionException:
    errors: Incomplete
    def __init__(self) -> None: ...
