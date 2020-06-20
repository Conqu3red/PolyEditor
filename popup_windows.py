import PySimpleGUI as sg

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


def info(title, *msg):
	layout = [[sg.Text(m)] for m in msg] + [[sg.Ok(size=(5, 1), pad=PAD)]]
	window = sg.Window(title, layout, element_justification='center')
	return window.read(close=True)[0]


def notif(*msg):
	layout = [[sg.Text(m)] for m in msg] + [[sg.Ok(size=(5, 1), pad=PAD)]]
	window = sg.Window("", layout, **NOTIF_OPTIONS)
	return window.read(close=True)[0]


def yes_no(*msg):
	layout = [[sg.Text(m)] for m in msg] + [[sg.Yes(size=(5, 1), pad=PAD), sg.No(size=(5, 1), pad=PAD)]]
	window = sg.Window("", [[sg.Frame("", layout, **FRAME_OPTIONS)]], **NOTIF_OPTIONS)
	return window.read(close=True)[0]


def ok_cancel(*msg):
	layout = [[sg.Text(m)] for m in msg] + [[sg.Ok(size=(5, 1), pad=PAD), sg.Cancel(size=(8, 1), pad=PAD)]]
	window = sg.Window("", [[sg.Frame("", layout, **FRAME_OPTIONS)]], **NOTIF_OPTIONS)
	return window.read(close=True)[0]


def selection(title, msg, items):
	listbox = sg.Listbox(values=items, size=(60, 10), pad=(0, 5), bind_return_key=True, default_values=[items[0]])
	layout = [[sg.Text(msg)], [listbox], [sg.Ok(size=(4, 1))]]
	window = sg.Window(title, layout, element_justification='left', return_keyboard_events=True)
	while True:
		event, content = window.read()
		if event == sg.WIN_CLOSED or event == "Escape:27":
			window.close()
			return None
		elif event == "Ok" or event == 0:
			window.close()
			return content[0][0]
		elif event == "Up:38" or event == "Left:37":
			index = items.index(content[0][0]) - 1
			index %= len(items)
			listbox.set_value([items[index]])
		elif event == "Down:40" or event == "Right:39":
			index = items.index(content[0][0]) + 1
			index %= len(items)
			listbox.set_value([items[index]])


def open_menu():
	controls = "Escape: Menu\nMouse Wheel: Zoom\nLeft Click: Move or pan\nRight Click: Make selection\n" \
	           "Shift+Click: Multi-select\nE: Edit shape properties\nP: Edit shape points\n" \
	           "C: Copy selected\nD: Delete selected\nS: Save changes"
	frame = sg.Frame(
		"",
		[[sg.Button("Back to editor", size=(28, 1), pad=((15, 15), (15, 3)))],
		 [sg.Button("Save", size=(28, 1), pad=(5, 3))],
		 [sg.Button("Toggle hitboxes", size=(13, 1), pad=(3, 3)),
		  sg.Button("Color scheme", size=(13, 1), pad=(3, 3))],
		 [sg.Button("Change level", size=(13, 1), pad=(3, 9)),
		  sg.Button("Quit", size=(13, 1), pad=(3, 9))],
		 [sg.Text("Controls", size=(21, 1), justification="center", relief=sg.RELIEF_RIDGE, border_width=4)],
		 [sg.Text(controls, justification='left', pad=((0, 0), (5, 15)))]],
		**FRAME_OPTIONS
	)
	return sg.Window("", [[frame]], return_keyboard_events=True, no_titlebar=True, keep_on_top=True, margins=(0, 0))


class EditObject:
	def __init__(self, data):
		if data is None:
			self.window = None
			return
		self.data = data
		self.layout = []
		for r, row in enumerate(self.data):
			self.layout.append([])
			for c, data in enumerate(row):
				if c == 0:
					self.layout[r].append(sg.Text(data, justification='center', size=(6, None)))
				else:
					inp = sg.Input(data, justification='left', size=(10, None))
					self.layout[r].append(inp)
		self.window = sg.Window(
			"Object properties", self.layout, keep_on_top=True, alpha_channel=0.7, disable_minimize=True)

	def __bool__(self):
		return self.window is not None and not self.window.TKrootDestroyed

	def close(self):
		if self.window is not None:
			self.window.close()

	# TODO: Move all input validations to this class, somehow.
