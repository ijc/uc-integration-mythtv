class BEConnection:
    pass


class BEEventConnection(BEConnection):
    def __init__(self, backend, port, localname=None, deadline: float = 10.0, level: int = 2) -> None: ...
