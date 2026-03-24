from seagull.log import logger
from seagull.signals import initialized


class FooPlugin:
    @classmethod
    def initialized_signal(cls, seagull):
        logger.info(f"Initialized '{seagull}'.")

    @classmethod
    def register(cls):
        logger.info("Registering 'foo_plugin' as a class.")
        initialized.connect(cls.initialized_signal)


def register():
    logger.info("Registering 'foo_plugin' as a module.")
    initialized.connect(FooPlugin.initialized_signal)
