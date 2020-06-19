import PySimpleGUI as sg


class Popup:
	def __init__(self, data):
		self.data = data
		self.layout = []
		for r, row in enumerate(self.data):
			self.layout.append([])
			for c, data in enumerate(row):
				if c == 0:
					self.layout[r].append(sg.Text(data))
				else:
					self.layout[r].append(sg.Input(data))
		self.window = sg.Window("Object properties", self.layout, keep_on_top=True, alpha_channel=0.7)
