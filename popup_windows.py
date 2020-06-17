from tkinter import *


class Popup:
	def __init__(self, values):
		self.root = Tk()
		self.root.overrideredirect(True)
		self.root.protocol("WM_DELETE_WINDOW", self.delete)
		self.main_dialog = Frame(self.root)
		self.values = values
		self.table = []
		for i in range(len(values)):  # Rows
			self.table.append([])
			for j in range(len(values[0])):  # Columns
				if j == 0:
					b = Label(self.root, text=values[i][j])
				else:
					var = DoubleVar(value=values[i][j])
					b = Spinbox(self.root, textvariable=var, width=10)
				b.grid(row=i, column=j)
				self.table[i].append(b)
		self.update()
		self.root.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+500+300")

	def delete(self):
		try:
			self.root.destroy()  # rip
		except:
			pass

	def get(self, grid_x, grid_y):
		return self.table[grid_y][grid_x].get()

	def update(self):
		self.root.update_idletasks()
		self.root.update()
		self.root.lift()
