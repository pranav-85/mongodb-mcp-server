class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, callable] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator
