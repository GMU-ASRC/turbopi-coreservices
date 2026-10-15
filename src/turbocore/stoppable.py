"""
Register with the task manager to be stopped later.

Importing this module will register the current process with the task manager.

It will also try to unregister the process if the program exits normally.

.. code-block:: python
    import turbocore.stoppable
"""

import atexit
import warnings
from .taskmanager import TaskManager

try:
    TaskManager.register_stoppable()
except Exception as err:
    warnings.warn("Error occurred while registering as stoppable."
                  " This process won't be stopped by buttonman.\n" + str(err),
                  ImportWarning, stacklevel=2)
else:
    atexit.register(TaskManager.unregister)
