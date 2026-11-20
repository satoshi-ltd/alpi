def __getattr__(name: str):
    if name == "AlpiApp":
        from alpi.tui.app import AlpiApp

        return AlpiApp
    raise AttributeError(f"module 'alpi.tui' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals(), "AlpiApp"})


__all__ = ["AlpiApp"]
