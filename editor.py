import pygame
import math
import re
import json
from sys import exit
from uuid import uuid4
from copy import deepcopy
from squaternion import Quaternion
from os import getcwd, listdir
from os.path import exists, isfile, join as pathjoin, getmtime as lastmodified
from subprocess import run

SIZE = [1200, 600]
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)

JSON_EXTENSION = ".layout.json"
LAYOUT_EXTENSION = ".layout"
BACKUP_EXTENSION = ".layout.backup"
FILE_REGEX = re.compile(f"^(.+)({JSON_EXTENSION}|{LAYOUT_EXTENSION})$")

POLYCONVERTER = "PolyConverter.exe"
SUCCESS_CODE = 0
JSON_ERROR_CODE = 1
CONVERSION_ERROR_CODE = 2
FILE_ERROR_CODE = 3
GAMEPATH_ERROR_CODE = 4


def entertoexit():
	input("\nPress Enter to exit...")
	exit()


def centroid(vertexes):
	_x_list = [vertex[0] for vertex in vertexes]
	_y_list = [vertex[1] for vertex in vertexes]
	_len = len(vertexes)
	_x = sum(_x_list) / _len
	_y = sum(_y_list) / _len
	return [_x, _y]


def rotate(origin, point, angle):
	"""Rotate a point counterclockwise by a given angle around a given origin.
	The angle should be given in degrees.
	"""
	angle = math.radians(angle)

	ox, oy = origin
	px, py = point

	qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
	qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
	return [qx, qy]


class CustomShape:
	"""Acts as a wrapper for a dictionary in m_CustomShapes"""
	def __init__(self, dict):
		self._dict = deepcopy(dict)
		points = [[p["x"] * self.scale["x"], p["y"] * self.scale["y"]]
				  for p in self._dict["m_PointsLocalSpace"]]
		self._center = centroid(points)
		self.highlighted = False
		self.hitbox = None

	def render(self, display, camera, zoom, anchors, draw_hitbox):
		# Add base position and adjust for the camera position
		points_pixels = [[int(zoom * (self.position["x"] + point[0] + camera[0])),
		                  int(zoom * -(self.position["y"] + (point[1]) + camera[1]))]
		                 for point in self.points]

		self.hitbox = pygame.draw.polygon(display, self.color, points_pixels)

		# Draw static pins
		pins = [[int(zoom * (pin["x"] + camera[0]) - zoom / 8),
		         int(zoom * -(pin["y"] + camera[0]) - zoom / 8)]
		        for pin in self.static_pins]
		for pin in pins:
			pygame.draw.ellipse(display, (165, 42, 42), (pin[0], pin[1], int(zoom / 4), int(zoom / 4)))
		# Draw dynamic anchors
		for anchor_id in self.dynamic_anchors:
			for anchor in anchors:
				if anchor_id == anchor["m_Guid"]:
					# print(anchor)
					# print((anchor["m_Pos"]["x"]+camera[0])*zoom,(anchor["m_Pos"]["y"]+camera[1])*zoom)
					rect = (int((anchor["m_Pos"]["x"] + camera[0]) * zoom - zoom / 8),
							int(-(anchor["m_Pos"]["y"] + camera[1]) * zoom - zoom / 8),
							int(zoom / 4),
							int(zoom / 4))
					pygame.draw.rect(display, (255, 255, 255), rect)
		if draw_hitbox:
			pygame.draw.rect(display, (0, 255, 0), self.hitbox, 1)
		if self.highlighted:
			pygame.draw.polygon(display, (255, 255, 0), points_pixels, 1)
		# print(self.color)

	@property
	def position(self):
		return self._dict["m_Pos"]
	@position.setter
	def position(self, value):
		self._dict["m_Pos"] = value

	@property
	def rotation(self):
		rot = self._dict["m_Rot"]
		return Quaternion(rot["w"], rot["x"], rot["y"], rot["z"]).to_euler(degrees=True)
	@rotation.setter
	def rotation(self, value):
		q = Quaternion.from_euler(*value, degrees=True)
		self._dict["m_Rot"] = {"x": q[1], "y": q[2], "z": q[3], "w": q[0]}
		self._dict["m_RotationDegrees"] = value[2]

	@property
	def scale(self):
		return self._dict["m_Scale"]
	@scale.setter
	def scale(self, value):
		self._dict["m_Scale"] = value

	@property
	def color(self):
		return [v*255 for v in self._dict["m_Color"].values()]
	@color.setter
	def color(self, value):
		self._dict["m_Color"] = {"r": value[0]/255, "g": value[1]/255, "b": value[2]/255, "a": value[3]/255}

	@property
	def points(self):
		return [rotate(self._center, [p["x"] * self.scale["x"], p["y"] * self.scale["y"]], self.rotation[2])
				  for p in self._dict["m_PointsLocalSpace"]]
	@points.setter
	def points(self, values):
		values = [rotate(self._center, p, -self.rotation[2]) for p in values]
		self._dict["m_PointsLocalSpace"] = [{"x": p[0], "y": p[1]} for p in values]

	@property
	def static_pins(self):
		return self._dict["m_StaticPins"]
	@static_pins.setter
	def static_pins(self, values):
		self._dict["m_StaticPins"] = values

	@property
	def dynamic_anchors(self):
		return self._dict["m_StaticPins"]
	@dynamic_anchors.setter
	def dynamic_anchors(self, values):
		self._dict["m_DynamicAnchorGuids"] = values



if __name__ != "__main__":
	exit()


if not exists(POLYCONVERTER):
	print(f"Error: Cannot find {POLYCONVERTER} in this folder")
	entertoexit()

program = run(f"{POLYCONVERTER} test", capture_output=True)
if program.returncode == GAMEPATH_ERROR_CODE:  # game install not found
	print(program.stdout)
	entertoexit()
elif program.returncode == FILE_ERROR_CODE:  # as "test" is not a valid file
	pass
else:  # .NET not installed?
	print("Unexpected error:\n")
	print(program.stdout)
	entertoexit()

currentdir = getcwd()
filelist = [f for f in listdir(currentdir) if isfile(pathjoin(currentdir, f))]
levellist = [match.group(1) for match in [FILE_REGEX.match(f) for f in filelist] if match]
levellist = list(dict.fromkeys(levellist))  # remove duplicates

leveltoedit = None

if len(levellist) == 0:
	print("There are no levels to edit in the current folder")
	entertoexit()
elif len(levellist) == 1:
	leveltoedit = levellist[0]
else:
	print("[#] Enter the number of the level you want to edit:")
	print("\n".join([f" ({i + 1}). {s}" for (i, s) in enumerate(levellist)]))
	while True:
		try:
			index = int(input())
		except ValueError:
			pass
		if 0 < index < len(levellist) + 1:
			leveltoedit = levellist[index - 1]
			break

layoutfile = leveltoedit + LAYOUT_EXTENSION
jsonfile = leveltoedit + JSON_EXTENSION
backupfile = leveltoedit + BACKUP_EXTENSION

if (layoutfile in filelist and
		(jsonfile not in filelist or lastmodified(layoutfile) > lastmodified(jsonfile))):
	program = run(f"{POLYCONVERTER} {layoutfile}", capture_output=True)
	if program.returncode == SUCCESS_CODE:
		if program.stdout is not None and len(program.stdout) >= 6:
			print(f"{'Created' if 'Created' in str(program.stdout) else 'Updated'} {jsonfile}!")
	else:
		print(f"Error: There was a problem converting {layoutfile}. Full output below:\n")
		print(program.stdout)
		entertoexit()

with open(jsonfile) as openfile:
	try:
		layout = json.load(openfile)
		layout["m_Bridge"]["m_Anchors"] = layout["m_Anchors"] # both should update together in real-time
	except json.JSONDecodeError as error:
		print(f"Syntax error in line {error.lineno}, column {error.colno} of {jsonfile}")
		entertoexit()
	except ValueError:
		print(f"Error: {jsonfile} is either incomplete or not a valid level")
		entertoexit()

print("Layout Loaded Successfully!")

start_x, start_y = 0, 0
mouse_x, mouse_y = 0, 0
camera = [SIZE[0] / 2, -(SIZE[1] / 2)]
clock = pygame.time.Clock()
fps = 60
zoom = 1
hitboxes = False
dragging = False
selecting = False
selected_shapes = []

custom_shapes = [CustomShape(s) for s in layout["m_CustomShapes"]]
anchors = layout["m_Anchors"]

display = pygame.display.set_mode(SIZE)
pygame.init()
pygame.draw.rect(display, BLUE, (200, 150, 100, 50))
for shape in custom_shapes:
	shape.render(display, camera, zoom, anchors, hitboxes)
print()

done = False
while not done:
	for event in pygame.event.get():
		display.fill((0, 0, 0))
		if event.type == pygame.QUIT:
			done = True
			pygame.quit()
			exit()
		elif event.type == pygame.MOUSEBUTTONDOWN:
			start_x, start_y = 0, 0
			if event.button == 1:
				dragging = True
				old_mouse_x, old_mouse_y = event.pos
				offset_x = 0
				offset_y = 0
			if event.button == 4:
				zoom += zoom * 0.1
			if event.button == 5:
				zoom += -(zoom * 0.1)
			if event.button == 3:
				start_x, start_y = event.pos
				mouse_x, mouse_y = event.pos
				selecting = True
				true_start = (mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])
		elif event.type == pygame.MOUSEBUTTONUP:
			if event.button == 1:
				dragging = False
			if event.button == 3:
				selecting = False
				start_x, start_y = 0, 0
		elif event.type == pygame.MOUSEMOTION:
			if dragging:
				mouse_x, mouse_y = event.pos
				camera[0] = camera[0] + (mouse_x - old_mouse_x) / zoom
				camera[1] = camera[1] - (mouse_y - old_mouse_y) / zoom
				old_mouse_x, old_mouse_y = mouse_x, mouse_y
			if selecting:
				mouse_x, mouse_y = event.pos
		elif event.type == pygame.KEYDOWN:
			if event.key == ord('h'):
				hitboxes = not hitboxes
			if event.key == ord('d'):
				# Delete selected
				for shape in custom_shapes:
					if shape.highlighted:
						layout["m_CustomShapes"].remove(shape._dict)
						custom_shapes.remove(shape)
			# Moving selection
			x_change, y_change = 0, 0
			move = False
			if event.key == pygame.K_LEFT:
				x_change = -1
				move = True
			if event.key == pygame.K_RIGHT:
				x_change = 1
				move = True
			if event.key == pygame.K_UP:
				y_change = 1
				move = True
			if event.key == pygame.K_DOWN:
				y_change = -1
				move = True

			if move:
				for shape in custom_shapes:
					if shape.highlighted:
						shape.position["x"] += x_change
						shape.position["y"] += y_change
						for c, pin in enumerate(shape.static_pins):
							shape.static_pins[c]["x"] += x_change
							shape.static_pins[c]["y"] += y_change
						for anchor_id in shape.dynamic_anchors:
							for c, anchor in enumerate(anchors[:]):
								if anchor["m_Guid"] == anchor_id:
									anchors[c]["m_Pos"]["x"] += x_change
									anchors[c]["m_Pos"]["y"] += y_change
				move = False
			if event.key == ord("c"):
				new_shapes = []
				for shape in custom_shapes:
					if shape.highlighted:
						new_shape = deepcopy(shape)
						shape.highlighted = False
						# Assing new guids
						new_shape.dynamic_anchors = [str(uuid4()) for _ in new_shape.dynamic_anchors]
						# Add to shapes list
						new_shapes.append(new_shape)
						layout["m_CustomShapes"].append(new_shape._dict)
						# Add to anchors list
						new_anchors = []
						for i, anchor_id in enumerate(shape.dynamic_anchors):
							for anchor in anchors:
								if anchor["m_Guid"] == anchor_id:
									new_anchor = deepcopy(anchor)
									new_anchor["m_Guid"] = new_shape.dynamic_anchors[i]
									new_anchors.append(new_anchor)
						anchors.extend(new_anchors)
				custom_shapes.extend(new_shapes)
			if event.key == ord("s"):
				print(f"Saving changes to {jsonfile}...")
				with open(jsonfile, 'w') as openfile:
					json.dump(layout, openfile, indent=2)
				print(f"Applied changes to {jsonfile}!")
				print("Converting...")
				program = run(f"{POLYCONVERTER} {jsonfile}", capture_output=True)
				if program.returncode == SUCCESS_CODE:
					pygame.quit()
					if program.stdout is None or len(program.stdout) < 6:
						print("No changes to apply.")
					else:
						if "backup" in str(program.stdout):
							print(f"Created backup {backupfile}")
						print(f"Applied changes to {layoutfile}!")
					print("Done!")
					entertoexit()
				elif program.returncode == FILE_ERROR_CODE:  # Failed to save?
					print(program.stdout)
				else:
					print(f"Unexpected error:\n{program.stdout}")

	# Selecting shapes
	if selecting:
		# print(f"True mouse position: {(mouse_x/zoom-camera[0])},{(-mouse_y/zoom-camera[1])}")
		select_box = pygame.draw.rect(display, (0, 255, 0),
									  pygame.Rect(start_x, start_y, mouse_x - start_x, mouse_y - start_y), 1)
		true_current = (mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])
		# print(true_start,true_current)
		selected_shapes = []
		for shape in custom_shapes:
			shape.highlighted = shape.hitbox.colliderect(select_box)

	# Render Shapes
	for shape in custom_shapes:
		shape.render(display, camera, zoom, anchors, hitboxes)

	pygame.display.flip()
	clock.tick(fps)
