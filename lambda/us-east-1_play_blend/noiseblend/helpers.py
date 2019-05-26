def listify(items):
    comma_separated = ", ".join(item for item in items[:-1])
    return f"{comma_separated} and {items[-1]}"


def cap(val, _min, _max):
    return min(max(val, _min), _max)
