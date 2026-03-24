from seagull.log import logger
from seagull.signals import initialized, get_generators


class FooPlugin:
    @staticmethod
    @initialized.connect
    def initialized_signal(seagull):
        logger.info(f"Initialized '{seagull}'.")

    @classmethod
    def register(cls):
        logger.info("Registering 'foo_plugin' as a class.")
