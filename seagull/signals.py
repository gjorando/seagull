from blinker import Signal, signal
from ordered_set import OrderedSet

Signal.set_class = OrderedSet

initialized = signal("seagull.initialized")
