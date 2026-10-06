"""Content-free Inventory error bases, independent of models and workflows."""


class InventoryError(RuntimeError):
    pass


class InvalidInventoryInput(InventoryError):
    pass
