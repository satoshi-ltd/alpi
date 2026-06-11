from alpi import tools


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_no_union_type_lists_in_tool_schemas():
    offenders = [
        f"{cls.name}: {node}"
        for cls in tools.all_tools()
        for node in _walk(cls.parameters)
        if isinstance(node.get("type"), list)
    ]
    assert not offenders, offenders


def test_every_array_declares_items():
    offenders = [
        f"{cls.name}: {node}"
        for cls in tools.all_tools()
        for node in _walk(cls.parameters)
        if node.get("type") == "array" and "items" not in node
    ]
    assert not offenders, offenders
