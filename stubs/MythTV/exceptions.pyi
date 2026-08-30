from MythTV.static import ERRCODES as ERRCODES
from _typeshed import Incomplete

class MythError(Exception, ERRCODES):
    ecode: Incomplete
    ename: str
    args: Incomplete
    message: Incomplete
    def __init__(self, *args) -> None: ...

class MythBEError(MythError):
    ename: str
    args: Incomplete
    ecode: Incomplete
    def __init__(self, *args) -> None: ...
