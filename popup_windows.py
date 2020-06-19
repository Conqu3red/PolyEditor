import PySimpleGUI as sg

BTN_PAD = ((5, 5), (5, 0))


# Using sg.Window instead of sg.Popup as that doesn't have element justification

def info(title, *msg):
	window = sg.Window(title, [[sg.Text(m)] for m in msg] + [[sg.Ok(pad=BTN_PAD)]],
	                   element_justification='center')
	return window.read(close=True)[0]


def selection(title, msg, items):
	listbox = sg.Listbox(
		values=items, size=(60, 10), pad=((0, 0), (0, 5)), bind_return_key=True, default_values=[items[0]])
	window = sg.Window(title, layout=[[sg.Text(msg)], [listbox], [sg.Ok()]],
	                   element_justification='left')
	event = window.read(close=True)
	return None if event[0] == sg.WIN_CLOSED else event[1][0][0]


def notif(*msg):
	window = sg.Window("", [[sg.Text(m)] for m in msg] + [[sg.Ok(pad=BTN_PAD)]],
	                   no_titlebar=True, keep_on_top=True, grab_anywhere=True, element_justification='center')
	return window.read(close=True)[0]


def yes_no(*msg):
	window = sg.Window("", [[sg.Text(m)] for m in msg] + [[sg.Yes(pad=BTN_PAD), sg.No(pad=BTN_PAD)]],
	                   no_titlebar=True, keep_on_top=True, grab_anywhere=True, element_justification='center')
	return window.read(close=True)[0]


def ok_cancel(*msg):
	window = sg.Window("", [[sg.Text(m)] for m in msg] + [[sg.Ok(pad=BTN_PAD), sg.Cancel(pad=BTN_PAD)]],
	                   no_titlebar=True, keep_on_top=True, grab_anywhere=True, element_justification='center')
	return window.read(close=True)[0]


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
