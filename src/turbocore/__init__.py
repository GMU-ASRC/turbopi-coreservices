from .buzzer import set_buzzer
from .taskmanager import TaskManager

register_stoppable = TaskManager.register_stoppable
unregister_stoppable = TaskManager.unregister
close_all_registered = TaskManager.close_all_registered

__all__ = [
    'set_buzzer',
    'TaskManager',
    'register_stoppable',
    'unregister_stoppable',
    'close_all_registered',
]
