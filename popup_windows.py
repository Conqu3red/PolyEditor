import gc
import PySimpleGUI as sg
import game_objects as g
from typing import *

POS_X, POS_Y, POS_Z = "X", "Y", "Z"
WIDTH, HEIGHT = "Width", "Height"
SCALE_X, SCALE_Y, SCALE_Z = "Scale X", "Scale Y", "Scale Z"
ROT_X, ROT_Y, ROT_Z = "Rot. X", "Rot. Y", "Rotation"
FLIP = "Flip"
RGB_R, RGB_G, RGB_B = "Red", "Green", "Blue"

BACKGROUND_COLOR = "#2A4567"
ERROR_BACKGROUND_COLOR = "#9F2A2A"

PAD = (5, 5)

FRAME_OPTIONS = {
	"relief": sg.RELIEF_SOLID,
	"border_width": 1,
	"element_justification": "center",
	"pad": (0, 0)
}

NOTIF_OPTIONS = {
	"no_titlebar": True,
	"keep_on_top": True,
	"grab_anywhere": True,
	"margins": (0, 0),
	"element_justification": "center"
}


def info(title: str, *msg, read=True) -> Union[str, sg.Window]:
	"""Opens a window and returns when the user closes it or presses Ok"""
	layout = [[sg.Text(m)] for m in msg] + [[sg.Ok(size=(5, 1), pad=PAD)]]
	window = sg.Window(title, layout, element_justification='center', return_keyboard_events=not read)
	if not read:
		return window
	result, _ = window.read(close=True)
	window.layout = None
	# noinspection PyUnusedLocal
	window = None
	gc.collect()
	return result


def notif(*msg: Any, read=True) -> Union[str, sg.Window]:
	"""Opens a borderless window and returns when the user presses Ok"""
	layout = [[sg.Text(m)] for m in msg] + [[sg.Ok(size=(5, 1), pad=PAD)]]
	window = sg.Window("", [[sg.Frame("", layout, **FRAME_OPTIONS)]], **NOTIF_OPTIONS, return_keyboard_events=not read)
	if not read:
		return window
	result, _ = window.read(close=True)
	window.layout = None
	# noinspection PyUnusedLocal
	window = None
	gc.collect()
	return result


def yes_no(*msg: Any, read=True) -> Union[str, sg.Window]:
	"""Opens a borderless window and returns whether the user pressed Yes or No"""
	layout = [[sg.Text(m)] for m in msg] + [[sg.Yes(size=(5, 1), pad=PAD), sg.No(size=(5, 1), pad=PAD)]]
	window = sg.Window("", [[sg.Frame("", layout, **FRAME_OPTIONS)]], **NOTIF_OPTIONS, return_keyboard_events=not read)
	if not read:
		return window
	result, _ = window.read(close=True)
	window.layout = None
	# noinspection PyUnusedLocal
	window = None
	gc.collect()
	return result


def ok_cancel(*msg: Any, read=True) -> Union[str, sg.Window]:
	"""Opens a borderless window and returns whether the user pressed Ok or Cancel"""
	layout = [[sg.Text(m)] for m in msg] + [[sg.Ok(size=(5, 1), pad=PAD), sg.Cancel(size=(8, 1), pad=PAD)]]
	window = sg.Window("", [[sg.Frame("", layout, **FRAME_OPTIONS)]], **NOTIF_OPTIONS, return_keyboard_events=not read)
	if not read:
		return window
	result, _ = window.read(close=True)
	window.layout = None
	# noinspection PyUnusedLocal
	window = None
	gc.collect()
	return result


def selection(title: str, msg: Any, items: List[str]) -> Optional[str]:
	"""Opens a window where the user can select an item from a list, then closes and returns the selection"""
	listbox = sg.Listbox(values=items, size=(60, 10), pad=(0, 5), bind_return_key=True, default_values=[items[0]])
	layout = [[sg.Text(msg)], [listbox], [sg.Ok(size=(5, 1))]]
	window = sg.Window(title, layout, element_justification='left', return_keyboard_events=True)
	while True:
		event, content = window.read()
		if event == sg.WIN_CLOSED or event == "Escape:27":
			window.close()
			window.layout = None
			# noinspection PyUnusedLocal
			window = None
			gc.collect()
			return None
		elif event == "Ok" or event == 0:
			window.close()
			window.layout = None
			# noinspection PyUnusedLocal
			window = None
			gc.collect()
			return content[0][0]
		elif event == "Up:38" or event == "Left:37":
			index = items.index(content[0][0]) - 1
			listbox.set_value([items[index % len(items)]])
		elif event == "Down:40" or event == "Right:39":
			index = items.index(content[0][0]) + 1
			listbox.set_value([items[index % len(items)]])


def open_menu() -> sg.Window:
	"""Returns a new opened window with the layout of the game's menu"""
	controls = "Escape: Menu\nMouse Wheel: Zoom\nLeft Click: Move or pan\nRight Click: Make selection\n" \
	           "Shift+Click: Multi-select\nE: Edit shape attributes\nP: Point editing mode" \
	           "\n └> Shift+Click: Add, Right Click: Delete\n" \
	           "C: Clone selected\nD: Delete selected\nS: Save changes"
	frame = sg.Frame(
		"",
		[[sg.Button("Back to editor", size=(28, 1), pad=((15, 15), (15, 3)))],
		 [sg.Button("Save", size=(28, 1), pad=(5, 3))],
		 [sg.Button("Toggle hitboxes", size=(13, 1), pad=(5, 3)),
		  sg.Button("Color scheme", size=(13, 1), pad=(5, 3))],
		 [sg.Button("Change level", size=(13, 1), pad=(5, 12)),
		  sg.Button("Quit", size=(13, 1), pad=(5, 12))],
		 [sg.Text("Controls", size=(27, 1), justification="center", relief=sg.RELIEF_RIDGE, border_width=4)],
		 [sg.Text(controls, justification="left", pad=((0, 0), (0, 15)))]],
		**FRAME_OPTIONS
	)
	return sg.Window("", [[frame]], return_keyboard_events=True, no_titlebar=True, keep_on_top=True, margins=(0, 0))


class EditObjectWindow:
	"""A dedicated window where the user can alter various attributes of a selectable object"""
	def __init__(self, data: Optional[Dict[str, Any]], obj: Optional[g.SelectableObject]):
		self._window = None
		if data is None:
			self.data = None
			self.obj = None
			self.inputs = None
			return
		self.data = data.copy()
		self.obj = obj
		self.inputs = {}
		self._layout = []
		for name, value in self.data.items():
			if name == FLIP:
				row = [sg.Button(name, size=(8, 1))]
				self._layout.append(row)
			else:
				row = [sg.Text(name, justification="center", size=(6, 1)),
				       sg.Input(value, justification="left", size=(10, 1))]
				self.inputs[name] = row[1]
				self._layout.append(row)

	def open(self):
		"""Initializes and opens the window"""
		self._window = sg.Window("Object properties", self._layout, keep_on_top=True, element_justification="center",
		                         alpha_channel=0.7, disable_minimize=True, return_keyboard_events=True)
		self._window.read(timeout=0)
		self._window.bind("<Leave>", "Leave")  # mouse leaves an element

	def read(self, timeout: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
		"""Returns the event name and a validated list of values when an event occurs"""
		if not self.__bool__(): raise ValueError("The window was destroyed")

		event, raw_values = self._window.read(timeout)

		if event == "Leave" or event == sg.WIN_CLOSED or event == sg.TIMEOUT_KEY:
			return event, self.data

		if event == FLIP:
			self.data[FLIP] = not self.data[FLIP]
			return event, self.data

		# Validate and set data when key is pressed
		for i, key in enumerate(self.data.keys()):
			invalid = False

			if key == FLIP:  # button
				continue

			try:
				self.data[key] = float(raw_values[i])
			except ValueError:
				invalid = True
			else:
				if key in (POS_X, POS_Y):
					invalid = not -1000.0 <= self.data[key] <= 1000.0  # TODO: Fix render crash somewhere above 1000
					self.data[key] = max(min(self.data[key], 1000.0), -1000.0)
				elif key == POS_Z:
					invalid = not -500.0 <= self.data[key] <= 500.0
					self.data[key] = max(min(self.data[key], 500.0), -500.0)
				elif key in (SCALE_X, SCALE_Y, SCALE_Z):
					invalid = not 0.01 <= self.data[key] <= 10.0
					self.data[key] = max(min(self.data[key], 10.0), 0.01)
				elif key in (ROT_X, ROT_Y, ROT_Z):
					invalid = not -180.0 <= self.data[key] <= 180.0
					self.data[key] = max(min(self.data[key], 180.0), -180.0)
				elif key in (WIDTH, HEIGHT):
					invalid = not 0.1 <= self.data[key] <= 100.0
					self.data[key] = max(min(self.data[key], 100.0), 0.1)
				elif key in (RGB_R, RGB_G, RGB_B):
					invalid = not 0 <= self.data[key] <= 255
					self.data[key] = max(min(self.data[key], 255), 0)
				else:
					print(f"Warning: Didn't validate {key} input as its name couldn't be recognized")

			if invalid:
				self.inputs[key].update(background_color=ERROR_BACKGROUND_COLOR)
			else:
				self.inputs[key].update(background_color=BACKGROUND_COLOR)

		return event, self.data

	def close(self):
		if self._window is not None:
			self._window.close()
			self._window.layout = None
			self._layout = None
			self._window = None
			self.inputs = None
			gc.collect()

	def __bool__(self):
		return self._window is not None and not self._window.TKrootDestroyed
