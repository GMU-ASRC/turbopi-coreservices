"""
Track button press and release states for AndurilUI-like click/hold/release interface.

This module is used by the button manager to manage button presses and releases.
It tracks how long a button has been held down, and sends short click or long hold
events to the button manager.

.. seealso::
    * :py:mod:`turbocore.buttonman`
    * :py:mod:`turbocore.debouncer`

"""


try:
    import statemachine
except (ImportError, ModuleNotFoundError):
    statemachine = None


class PushStateMachine(statemachine.StateMachine):
    idle = statemachine.State(initial=True)
    down = statemachine.State()
    held = statemachine.State()
    rlsd = statemachine.State()
    unheld = statemachine.State()

    def __init__(self, *args, hold_period=0.35, timeout=0.45, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_down = 0
        self.t_rlsd = 0
        self.hold_period = hold_period
        self.timeout = timeout
        # these are the functions to call when a button state is reached
        # they should be set after initialization by external code
        self.short_press = lambda: None
        self.long_press = lambda: None
        self.holding = lambda: None
        self.done = lambda: None

    cycle = (down.to(held, cond='held_long_enough', after='send_hold')
           | rlsd.to(idle, cond='rlsd_long_enough', after='send_done')
         | unheld.to(idle, cond='rlsd_long_enough', after='send_done')
           | idle.to.itself(internal=True)
           | held.to.itself(internal=True)
           | down.to.itself(internal=True)
           | rlsd.to.itself(internal=True)
           | unheld.to.itself(internal=True)
    )

    pushed = (idle.to(down)
            | rlsd.to(down)
          | unheld.to(down))
    released = (down.to(rlsd, after='send_short')
              | held.to(unheld, after='send_long'))

    # quik_press = down.to(rlsd)
    # long_press = held.to(unheld)
    # holding = down.to(held)
    # done = idle.from_(unheld) | idle.from_(rlsd)

    # in the following actions, the `t` argument must be passed in the state transition
    # in the send() function.
    # https://python-statemachine.readthedocs.io/en/latest/actions.html

    @pushed.on
    def pushed_sideffect(self, t: int):
        self.t_down = t
        # print("pushed", t)
        # return True

    @released.on
    def released_sideffect(self, t: int):
        self.t_rlsd = t
        # return True

    def held_long_enough(self, t: int):
        return (t - self.t_down) > (self.hold_period * 1E9)

    def rlsd_long_enough(self, t: int):
        return (t - self.t_rlsd) > (self.timeout * 1E9)

    # @quik_press.after
    def send_short(self):
        # print("short press")
        self.short_press()

    # @long_press.after
    def send_long(self):
        # print("long press")
        self.long_press()

    # @holding.after
    def send_hold(self):
        # print("holding")
        self.holding()

    # @done.after
    def send_done(self):
        # print("----------------")
        self.done()

    # def after_transition(self, event: str, source: statemachine.State, target: statemachine.State, event_data):
        # print(f"Running {event} from {source!s} to {target!s}: {event_data.trigger_data.kwargs!r}")
