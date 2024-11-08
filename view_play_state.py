from PySide6.QtCore import QObject, Signal, Slot
from enum import Enum

class PlayStateEnum(Enum):
    PLAYING = 1
    PAUSED = 2
    TERMINATE = 3

class PlayState():
    state_enum = None
    def play_control(self, state_machine):
        raise NotImplementedError

    def end_action(self, state_machine):
        raise NotImplementedError

class PlayingState(PlayState):
    state_enum = PlayStateEnum.PLAYING
    def play_control(self, state_machine):
        state_machine.set_state(PausedState())

    def end_action(self, state_machine):
        state_machine.set_state(TerminateState())

class PausedState(PlayState):
    state_enum = PlayStateEnum.PAUSED
    def play_control(self, state_machine):
        state_machine.set_state(PlayingState())

    def end_action(self, state_machine):
        pass

class TerminateState(PlayState):
    state_enum = PlayStateEnum.TERMINATE
    def play_control(self, state_machine):
        state_machine.set_state(PlayingState())
        pass

    def end_action(self, state_machine):
        state_machine.set_state(PausedState())

class PlayStateMachine:
    def __init__(self):
        self.state = PausedState()

    def set_state(self, state):
        self.state = state

    def play_control(self):
        self.state.play_control(self)

    def end_action(self):
        self.state.end_action(self)
