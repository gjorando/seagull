from blinker import Signal, signal
from ordered_set import OrderedSet

Signal.set_class = OrderedSet

initialized = signal("seagull.initialized")
finalized = signal("seagull.finalized")
all_generators_finalized = signal("seagull.all_generators_finalized")
get_generators = signal("seagull.get_generators")
