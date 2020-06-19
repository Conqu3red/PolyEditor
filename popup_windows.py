import PySimpleGUI as sg


class EditObjectPopup:
	def __init__(self, data):
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
