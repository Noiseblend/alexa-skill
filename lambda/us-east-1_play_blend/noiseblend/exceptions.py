class UnknownSlotError(Exception):

    """Raise when a slot doesn't have a resolution."""

    def __init__(self, slot, *args):
        super().__init__(*args)
        self.slot = slot

    def __str__(self):
        return f"Slot {self.slot} does not have a resolution match"
