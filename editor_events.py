from queue import Queue, Empty
from typing import *

DONE = "done"
CLOSE_PROGRAM = "exit"
CLOSE_EDITOR = "close"
OPEN_OBJ_EDIT = "openobj"
UPDATE_OBJ_EDIT = "updateobj"
CLOSE_OBJ_EDIT = "closeobj"
RESTART_PROGRAM = "restart"

TIMEOUT = "__TIMEOUT__"

NOTIF_ANSWERS = (
	OK := "Ok", CANCEL := "Cancel", YES := "Yes", NO := "No",
	EXIT := "Exit", FOCUS_OUT := "FocusOut", ESCAPE := chr(27)
)

MENU_BUTTONS = (
	MENU_RETURN := "Back to editor", MENU_SAVE := "Save", MENU_CHANGE_LEVEL := "Change level", MENU_QUIT := "Quit",
	MENU_HITBOXES := "Toggle hitboxes", MENU_COLORS := "Color scheme"
)


class EditorEvent:
	"""An object identified by a key and which can contain custom attributes"""
	def __init__(self, key, *args, **attributes):
		self.key = key
		self.attributes = attributes
		self.args = args

	def __getattr__(self, item):
		try:
			return self.attributes[item]
		except KeyError:
			pass
		raise AttributeError(f"This event of key {self.key} has no attribute {item}")

	def __getitem__(self, item: int):
		return self.args[item]

	def __eq__(self, other):
		"""This event's key is equal to the value"""
		return self.key == other

	def __ne__(self, other):
		return self.key != other

	def __call__(self, *args, **kwargs):
		"""Call this event's key, assuming it is a function"""
		return self.key(*args, **kwargs)

	def __str__(self):
		return f"({self.key}, {self.attributes}, {self.args})"


class EventLane:
	"""A wrapper to two queues, in order to send discrete events back and forth between two threads"""
	def __init__(self, read_queue=Queue(), send_queue=Queue()):
		self.read_queue = read_queue
		self.send_queue = send_queue

	def read(self, block=False, timeout: int = None) -> Optional[EditorEvent]:
		"""Remove and return an item from the read_queue. Will be None if block is False and there are no events.
		A timeout in milliseconds will set how long to wait before returning None if no event was found."""
		try:
			if timeout is not None:
				timeout /= 1000
			return self.read_queue.get(block, timeout)
		except Empty:
			return None

	def send(self, key, *args, **attributes):
		"""Create an EditorEvent and put it in the send_queue"""
		self.send_queue.put(EditorEvent(key, *args, **attributes))

	def flipped(self) -> 'EventLane':
		"""Returns an EventLane with the same queues as this one but swapped"""
		return EventLane(self.send_queue, self.read_queue)
