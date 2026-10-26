class QueueWiseError(Exception):
    """Base class for expected (user-facing) domain errors."""


class InvalidQueueTransition(QueueWiseError):
    pass


class SlotUnavailable(QueueWiseError):
    pass


class OutsideBusinessHours(QueueWiseError):
    pass
