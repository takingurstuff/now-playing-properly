from enum import Enum


class PluginConflictResolvStrat(Enum):
    LOW_FIRST = 0
    LOW_FIRST = "low_prio_first"
    HIGH_FIRST = 1
    HIGH_FIRST = "hi_prio_first"
