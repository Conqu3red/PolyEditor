import PySimpleGUI as sg
#layout = [[sg.Input()],
#		[sg.Button('Read'), sg.Exit()]]

class Popup:
	def __init__(self, data):
		self.data = data
		self.layout = []
		for r,row in enumerate(self.data):
			self.layout.append([])
			for c,data in enumerate(row):
				if c == 0:
					self.layout[r].append(sg.Text(data))
				else:
					self.layout[r].append(sg.Input(data))
		self.layout.append([sg.Exit()])
		self.window = sg.Window("", self.layout, no_titlebar=True, keep_on_top=True, grab_anywhere=True)
