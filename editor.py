import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
os.environ['SDL_VIDEO_CENTERED'] = '1'

import sys
import pygame
import re
import json
import traceback
import ctypes
import PySimpleGUI as sg
from uuid import uuid4
from copy import deepcopy
from itertools import chain
from operator import add, sub
from os import getcwd, listdir
from os.path import exists, isfile, join as pathjoin, getmtime as lastmodified
from subprocess import run
from time import sleep

import game_objects as g
from popup_windows import EditObjectPopup

BASE_SIZE = (1200, 600)
FPS = 60
ZOOM_MULT = 1.1
ZOOM_MIN = 4
ZOOM_MAX = 400
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BACKGROUND_BLUE = (43, 70, 104)
BACKGROUND_BLUE_GRID = (38, 63, 94)
BACKGROUND_GRAY_GRID = (178, 169, 211)
BACKGROUND_GRAY = (162, 154, 194)

try:  # When bundled as single executable
	TEMP_FILES = sys._MEIPASS
	POLYCONVERTER = pathjoin(TEMP_FILES, "PolyConverter.exe")
	ICON = pathjoin(TEMP_FILES, "favicon.ico")
except AttributeError:
	TEMP_FILES = None
	POLYCONVERTER = "PolyConverter.exe"
	ICON = None
JSON_EXTENSION = ".layout.json"
LAYOUT_EXTENSION = ".layout"
BACKUP_EXTENSION = ".layout.backup"
FILE_REGEX = re.compile(f"^(.+)({JSON_EXTENSION}|{LAYOUT_EXTENSION})$")
SUCCESS_CODE = 0
JSON_ERROR_CODE = 1
CONVERSION_ERROR_CODE = 2
FILE_ERROR_CODE = 3
GAMEPATH_ERROR_CODE = 4


def choose_file():
	currentdir = getcwd()
	filelist = [f for f in listdir(currentdir) if isfile(pathjoin(currentdir, f))]
	levellist = [match.group(1) for match in [FILE_REGEX.match(f) for f in filelist] if match]
	levellist = list(dict.fromkeys(levellist))  # remove duplicates

	if len(levellist) == 0:
		sg.Popup("There are no levels to edit in this folder", title="PolyEditor")
		sys.exit()

	listbox = sg.Listbox(
		values=levellist, size=(60, 10), pad=((0, 0), (0, 5)), bind_return_key=True, default_values=[levellist[0]])
	window = sg.Window("PolyEditor", layout=[[sg.Text("Choose a level to edit:")], [listbox], [sg.Ok()]])
	event = window.read(close=True)
	if event[0] == sg.WIN_CLOSED:
		sys.exit()
	else:
		leveltoedit = event[1][0][0]

	layoutfile = leveltoedit + LAYOUT_EXTENSION
	jsonfile = leveltoedit + JSON_EXTENSION
	backupfile = leveltoedit + BACKUP_EXTENSION

	if (layoutfile in filelist and
			(jsonfile not in filelist or lastmodified(layoutfile) > lastmodified(jsonfile))):
		program = run(f"{POLYCONVERTER} {layoutfile}", capture_output=True)
		if program.returncode != SUCCESS_CODE:
			outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
			sg.Popup(f"There was a problem converting {layoutfile} to json:",
				"\n".join([o for o in outputs if len(o) > 0]), title="Error")
			return

	with open(jsonfile) as openfile:
		try:
			layout = json.load(openfile)
			layout["m_Bridge"]["m_Anchors"] = layout["m_Anchors"]  # both should update together in real-time
		except json.JSONDecodeError as error:
			sg.Popup("Couldn't open level:",
				f"Invalid syntax in line {error.lineno}, column {error.colno} of {jsonfile}", title="Problem")
			return
		except ValueError:
			sg.Popup("Couldn't open level:",
				f"{jsonfile} is either incomplete or not actually a level", title="Problem")
			return

	return layout, layoutfile, jsonfile, backupfile


def main(layout, layoutfile, jsonfile, backupfile):

	size = BASE_SIZE
	zoom = 20
	camera = [size[0] / zoom / 2, -(size[1] / zoom / 2 + 5)]
	clock = pygame.time.Clock()
	popup = None
	popup_active = False
	draw_points = False
	hitboxes = False
	dragging = False
	selecting = False
	moving = False
	point_moving = False

	add_points = False
	delete_points = False
	selected_shape = None

	mouse_pos = (0, 0)
	old_mouse_pos = (0, 0)
	old_true_mouse_pos = (0, 0)
	selecting_pos = (0, 0)
	dragndrop_pos = (0, 0)
	bg_color = BACKGROUND_BLUE
	bg_color_2 = BACKGROUND_BLUE_GRID
	fg_color = WHITE

	terrain_stretches = g.LayoutList(g.TerrainStretch, layout)
	water_blocks = g.LayoutList(g.WaterBlock, layout)
	custom_shapes = g.LayoutList(g.CustomShape, layout)
	pillars = g.LayoutList(g.Pillar, layout)
	anchors = g.LayoutList(g.Anchor, layout)
	object_lists = {objs.list_name: objs for objs in
	                [terrain_stretches, water_blocks, custom_shapes, pillars, anchors]}

	selectable_objects = lambda: tuple(chain(custom_shapes, pillars))
	holding_shift = lambda: pygame.key.get_mods() & pygame.KMOD_SHIFT
	true_mouse_pos = lambda: (mouse_pos[0] / zoom - camera[0], -mouse_pos[1] / zoom - camera[1])

	display = pygame.display.set_mode(size, pygame.RESIZABLE)
	pygame.display.set_caption("PolyEditor")
	if ICON is not None:
		pygame.display.set_icon(pygame.image.load(ICON))
	pygame.init()

	# Pygame loop
	while True:

		# Listen for actions
		for event in pygame.event.get():

			if event.type == pygame.QUIT:
				if popup is not None:
					popup.window.close()
				answer = sg.popup_yes_no("Quit and lose any unsaved changes?",
					no_titlebar=True, keep_on_top=True, grab_anywhere=True)
				if answer == "Yes":
					pygame.quit()
					sys.exit()

			if event.type == pygame.ACTIVEEVENT:
				if event.state == 6:  # minimized
					if popup_active and not event.gain:
						popup.window.minimize()

			if event.type == pygame.VIDEORESIZE:
				display = pygame.display.set_mode(event.size, pygame.RESIZABLE)
				size = event.size
				g.HITBOX_SURFACE = pygame.Surface(event.size, pygame.SRCALPHA, 32)

			elif event.type == pygame.MOUSEBUTTONDOWN:
				if event.button == 1:  # left click
					for obj in reversed(selectable_objects()):
						if obj.click_hitbox.collidepoint(event.pos):  # dragging and multiselect
							if type(obj) is g.CustomShape:
								clicked_point = [p for p in obj.point_hitboxes if p.collidepoint(event.pos)]
								if clicked_point:
									if popup_active:
										popup.window.close()
										popup_active = False
									point_moving = True
									obj.selected_points = [p.collidepoint(event.pos) for p in obj.point_hitboxes]
									selected_shape = obj
									break
							if not obj.hitbox.collidepoint(event.pos):
								break
							if not holding_shift():
								moving = True
								dragndrop_pos = true_mouse_pos() if not obj.highlighted else None
							if not obj.highlighted:
								if not holding_shift():  # clear other selections
									for o in selectable_objects():
										o.highlighted = False
								obj.highlighted = True
								if popup_active:
									popup.window.close()
									popup_active = False
							elif holding_shift():
								obj.highlighted = False
								if popup_active:
									popup.window.close()
									popup_active = False
							break
					if not (moving or point_moving):
						dragging = True
						dragndrop_pos = true_mouse_pos()
					old_mouse_pos = event.pos

				if event.button == 3:  # right click
					if popup_active:
						popup.window.close()
						popup_active = False
					mouse_pos = event.pos
					selecting_pos = event.pos
					if not point_moving or moving:
						selecting = True

				if event.button == 4:  # mousewheel up
					old_pos = true_mouse_pos()
					if not holding_shift() and round(zoom * (ZOOM_MULT - 1)) >= 1:
						zoom = round(zoom * ZOOM_MULT)
					else:
						zoom += 1
					if zoom > ZOOM_MAX:
						zoom = ZOOM_MAX
					new_pos = true_mouse_pos()
					camera = [camera[i] + new_pos[i] - old_pos[i] for i in range(2)]

				if event.button == 5:  # mousewheel down
					old_pos = true_mouse_pos()
					if not holding_shift() and round(zoom / (ZOOM_MULT - 1)) >= 1:
						zoom = round(zoom / ZOOM_MULT)
					else:
						zoom -= 1
					if zoom < ZOOM_MIN:
						zoom = ZOOM_MIN
					new_pos = true_mouse_pos()
					camera = [camera[i] + new_pos[i] - old_pos[i] for i in range(2)]

			elif event.type == pygame.MOUSEBUTTONUP:

				if event.button == 1:  # left click
					if point_moving:
						selected_shape.selected_points = []
						selected_shape = None
						point_moving = False
					if not holding_shift() and dragndrop_pos is not None and\
							((not dragging and dragndrop_pos != true_mouse_pos())
							 or (dragging and dragndrop_pos == true_mouse_pos())):
						hl_objs = [o for o in selectable_objects() if o.highlighted]
						if len(hl_objs) == 1:
							hl_objs[0].highlighted = False
					dragging = False
					moving = False

				if event.button == 3:  # right click
					selecting = False

			elif event.type == pygame.MOUSEMOTION:
				mouse_pos = event.pos
				if dragging:
					camera[0] = camera[0] + (mouse_pos[0] - old_mouse_pos[0]) / zoom
					camera[1] = camera[1] - (mouse_pos[1] - old_mouse_pos[1]) / zoom
					old_mouse_pos = mouse_pos

			elif event.type == pygame.KEYDOWN:
				move_x, move_y = 0, 0
				move = False

				if event.key == ord('b'):
					# Toggle color scheme
					if bg_color == BACKGROUND_GRAY:
						bg_color = BACKGROUND_BLUE
						bg_color_2 = BACKGROUND_BLUE_GRID
						fg_color = WHITE
					else:
						bg_color = BACKGROUND_GRAY
						bg_color_2 = BACKGROUND_GRAY_GRID
						fg_color = BLACK

				elif event.key == ord('h'):
					# Toggle hitboxes
					hitboxes = not hitboxes
				
				elif event.key == ord('p'):
					# Toggle showing points
					draw_points = not draw_points

				elif event.key == ord('d'):
					# Delete selected
					for obj in [o for o in selectable_objects() if o.highlighted]:
						if type(obj) is g.CustomShape:
							for dyn_anc_id in obj.dynamic_anchor_ids:
								for anchor in [a for a in anchors]:
									if anchor.id == dyn_anc_id:
										anchors.remove(anchor)
						object_lists[obj.list_name].remove(obj)

				elif event.key == pygame.K_LEFT:
					move_x = -1
					move = True

				elif event.key == pygame.K_RIGHT:
					move_x = 1
					move = True

				elif event.key == pygame.K_UP:
					move_y = 1
					move = True

				elif event.key == pygame.K_DOWN:
					move_y = -1
					move = True

				elif event.key == ord("c"):
					# Copy Selected
					for old_obj in [o for o in selectable_objects() if o.highlighted]:
						new_obj = deepcopy(old_obj)
						old_obj.highlighted = False
						new_obj.pos["x"] += 1
						new_obj.pos["y"] -= 1
						if type(new_obj) is g.CustomShape:
							new_obj.dynamic_anchor_ids = [str(uuid4()) for _ in old_obj.dynamic_anchor_ids]
							for i in range(len(new_obj.dynamic_anchor_ids)):
								for anchor in [a for a in anchors if a.id == old_obj.dynamic_anchor_ids[i]]:
									new_anchor = deepcopy(anchor)
									new_anchor.id = new_obj.dynamic_anchor_ids[i]
									anchors.append(new_anchor)
							for c, pin in enumerate(new_obj.static_pins):
								new_obj.static_pins[c]["x"] += 1
								new_obj.static_pins[c]["y"] -= 1
							for dyn_anc_id in new_obj.dynamic_anchor_ids:
								for anchor in anchors:
									if anchor.id == dyn_anc_id:
										anchor.pos["x"] += 1
										anchor.pos["y"] -= 1
						object_lists[new_obj.list_name].append(new_obj)

				elif event.key == ord('0'):
					if popup_active:
						popup.window.close()
					answer = sg.popup_yes_no("Quit and lose any unsaved changes?",
						no_titlebar=True, keep_on_top=True, grab_anywhere=True)
					if answer == "Yes":
						pygame.quit()
						return

				elif event.key == ord("s"):
					if popup_active:
						popup.window.close()
						popup_active = False
					jsonstr = json.dumps(layout, indent=2)
					jsonstr = re.sub(r"(\r\n|\r|\n)( ){6,}", r" ", jsonstr)  # limit depth to 3 levels
					jsonstr = re.sub(r"(\r\n|\r|\n)( ){4,}([}\]])", r" \3", jsonstr)
					with open(jsonfile, 'w') as openfile:
						openfile.write(jsonstr)
					program = run(f"{POLYCONVERTER} {jsonfile}", capture_output=True)
					if program.returncode == SUCCESS_CODE:
						output = program.stdout.decode().strip()
						if len(output) == 0:
							sg.Popup("No new changes to apply.",
								no_titlebar=True, keep_on_top=True, grab_anywhere=True)
						else:
							if "backup" in program.stdout.decode():
								sg.Popup(f"Applied changes to {layoutfile}!", f"(Created backup {backupfile})",
									no_titlebar=True, keep_on_top=True, grab_anywhere=True)
							else:
								sg.Popup(f"Applied changes to {layoutfile}!",
									no_titlebar=True, keep_on_top=True, grab_anywhere=True)
					elif program.returncode == FILE_ERROR_CODE:  # failed to write file?
						sg.Popup("Couldn't save:", program.stdout.decode().strip(),
							no_titlebar=True, keep_on_top=True, grab_anywhere=True)
					else:
						outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
						sg.Popup(f"Unexpected error while trying to save:", "\n".join([o for o in outputs if len(o) > 0]),
							no_titlebar=True, keep_on_top=True, grab_anywhere=True)
				
				elif event.key == ord('e'):
					# Popup window to edit properties
					hl_objs = [o for o in selectable_objects() if o.highlighted]
					if popup_active:  # remove previous
						popup.window.close()
						popup_active = False
						for obj in hl_objs:
							obj.highlighted = False
						hl_objs.clear()
					if len(hl_objs) == 0:  # under cursor
						clickarea = pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1)
						for obj in reversed(selectable_objects()):
							if obj.hitbox.colliderect(clickarea):
								obj.highlighted = True
								hl_objs.append(obj)
								break
					if len(hl_objs) == 1:
						obj = hl_objs[0]
						values = [
							["X", obj.pos["x"]],
							["Y", obj.pos["y"]],
							["Z", obj.pos["z"]]
						]
						if type(obj) is g.CustomShape:
							rot = obj.rotations
							values.extend([
								["Scale X", obj.scale["x"]],
								["Scale Y", obj.scale["y"]],
								["Scale Z", obj.scale["z"]],
								["Rotation", rot[2]],
								["Rot. X", rot[0]],
								["Rot. Y", rot[1]]
							])
						popup = EditObjectPopup(values)
						popup_active = True

				# Move selection with keys
				if move:
					hl_objs = [o for o in selectable_objects() if o.highlighted]
					if len(hl_objs) == 0:
						camera = [camera[0] - move_x, camera[1] - move_y]
					for obj in hl_objs:
						obj.pos["x"] += move_x
						obj.pos["y"] += move_y
						if type(obj) is g.CustomShape:
							for pin in obj.static_pins:
								pin["x"] += move_x
								pin["y"] += move_y
							for dyn_anc_id in obj.dynamic_anchor_ids:
								for anchor in anchors:
									if anchor.id == dyn_anc_id:
										anchor.pos["x"] += move_x
										anchor.pos["y"] += move_y

		# Render background
		display.fill(bg_color)
		block_size = zoom
		line_width = g.scale(1, zoom)
		shift = (round(camera[0] * zoom % block_size), round(camera[1] * zoom % block_size))
		for x in range(shift[0], size[0], block_size):
			pygame.draw.line(display, bg_color_2, (x, 0), (x, size[1]), line_width)
		for y in range(-shift[1], size[1], block_size):
			pygame.draw.line(display, bg_color_2, (0, y), (size[0], y), line_width)

		# Selecting shapes
		if selecting:
			select_box = pygame.draw.rect(display, g.SELECT_COLOR,
				pygame.Rect(selecting_pos[0], selecting_pos[1],
				            mouse_pos[0] - selecting_pos[0], mouse_pos[1] - selecting_pos[1]), 1)
			for obj in selectable_objects():
				if not holding_shift():
					obj.highlighted = obj.hitbox.colliderect(select_box)
				elif obj.hitbox.colliderect(select_box):  # multiselect
					obj.highlighted = True

		# Move selection with mouse
		if moving:
			move_x = true_mouse_pos()[0] - old_true_mouse_pos[0]
			move_y = true_mouse_pos()[1] - old_true_mouse_pos[1]
			for obj in selectable_objects():
				if obj.highlighted:
					obj.pos["x"] += move_x
					obj.pos["y"] += move_y
					if type(obj) is g.CustomShape:
						for pin in obj.static_pins:
							pin["x"] += move_x
							pin["y"] += move_y
						for dyn_anc_id in obj.dynamic_anchor_ids:
							for anchor in anchors:
								if anchor.id == dyn_anc_id:
									anchor.pos["x"] += move_x
									anchor.pos["y"] += move_y

		hl_objs = [o for o in selectable_objects() if o.highlighted]
		if popup_active and len(hl_objs) == 1:
			obj = hl_objs[0]
			try:
				# TODO: Still drops a few inputs, even more with lower timeout
				gui_evnt, values = popup.window.read(timeout=100)
				if gui_evnt == sg.WIN_CLOSED or gui_evnt == 'Exit':
					popup.window.close()
					popup_active = False
					raise ValueError()

				# TODO: Change input color to red when value is invalid

				# Position
				try:
					x = float(values[0])
					x = max(min(x, 10000), -10000)
				except ValueError:
					x = obj.pos["x"]
				try:
					y = float(values[1])
					y = max(min(y, 10000), -10000)
				except ValueError:
					y = obj.pos["y"]
				try:
					z = float(values[2])
					z = max(min(z, 10000), -10000)
				except ValueError:
					z = obj.pos["z"]

				x_change, y_change, z_change = x - obj.pos["x"], y - obj.pos["y"], z - obj.pos["z"]
				obj.pos = {"x": x, "y": y, "z": z}
				if type(obj) is g.CustomShape:
					for pin in obj.static_pins:
						pin["x"] += x_change
						pin["y"] += y_change
					for anchor_id in obj.dynamic_anchor_ids:
						for anchor in anchors:
							if anchor.id == anchor_id:
								anchor.pos["x"] += x_change
								anchor.pos["y"] += y_change

				if type(obj) is g.CustomShape:

					# Scale (Has no effect on pins and anchors in-game)
					try:
						scalex = float(values[3])
						scalex = max(min(scalex, 10), 0.01)
					except ValueError:
						scalex = obj.scale["x"]
					try:
						scaley = float(values[4])
						scaley = max(min(scaley, 10), 0.01)
					except ValueError:
						scaley = obj.scale["y"]
					try:
						scalez = float(values[5])
						scalez = max(min(scalez, 10), 0.01)
					except ValueError:
						scalez = obj.scale["z"]

					obj.scale = {"x": scalex, "y": scaley, "z": scalez}

					# Rotation
					oldrot = obj.rotations
					try:
						rotz = float(values[6])
						rotz = max(min(rotz, 180), -180)
					except ValueError:
						rotz = oldrot[2]
					try:
						rotx = float(values[7])
						rotx = max(min(rotx, 180), -180)
					except ValueError:
						rotx = oldrot[0]
					try:
						roty = float(values[8])
						roty = max(min(roty, 180), -180)
					except ValueError:
						roty = oldrot[1]

					rotx_change, roty_change, rotz_change = rotx - oldrot[0], roty - oldrot[1], rotz - oldrot[2]
					obj.rotations = (rotx, roty, rotz)
					if abs(rotz_change) > 0.000009:
						for pin in obj.static_pins:
							newpin = g.rotate(
								(pin["x"], pin["y"]), rotz_change, (obj.pos["x"], obj.pos["y"]))
							pin["x"] = newpin[0]
							pin["y"] = newpin[1]
						for anchor_id in obj.dynamic_anchor_ids:
							for anchor in anchors:
								if anchor.id == anchor_id:
									newanchor = g.rotate(
										(anchor.pos["x"], anchor.pos["y"]), rotz_change, (obj.pos["x"], obj.pos["y"]))
									anchor.pos["x"] = newanchor[0]
									anchor.pos["y"] = newanchor[1]

			except ValueError:  # invalid position
				pass
		
		true_mouse_change = tuple(map(sub, true_mouse_pos(), old_true_mouse_pos))
		old_true_mouse_pos = true_mouse_pos()
		
		# Render Objects
		for terrain in terrain_stretches:
			terrain.render(display, camera, zoom, fg_color)
		for water in water_blocks:
			water.render(display, camera, zoom, fg_color)
		point_mode = g.PointMode(draw_points, delete_points, add_points, mouse_pos, true_mouse_change)
		for shape in custom_shapes:
			shape.render(display, camera, zoom, hitboxes, point_mode)
		for pillar in pillars:
			pillar.render(display, camera, zoom, hitboxes)
		dyn_anc_ids = list(chain(*[shape.dynamic_anchor_ids for shape in custom_shapes]))
		for anchor in anchors:
			anchor.render(display, camera, zoom, dyn_anc_ids)

		# Display mouse position, zoom and fps
		font = pygame.font.SysFont('Courier', 20)
		pos_msg = f"[{round(true_mouse_pos()[0], 2):>6},{round(true_mouse_pos()[1], 2):>6}]"
		pos_text = font.render(pos_msg, True, fg_color)
		display.blit(pos_text, (2, 5))
		font = pygame.font.SysFont('Courier', 16)
		zoom_msg = f"({zoom})"
		zoom_size = font.size(zoom_msg)
		zoom_text = font.render(zoom_msg, True, fg_color)
		display.blit(zoom_text, (round(size[0] / 2 - zoom_size[0] / 2), 5))
		fps_msg = str(round(clock.get_fps())).rjust(2)
		fps_size = font.size(fps_msg)
		fps_text = font.render(fps_msg, True, fg_color)
		display.blit(fps_text, (size[0] - fps_size[0] - 5, 5))

		# Display controls
		font_size = 16
		font = pygame.font.SysFont('Courier', font_size, True)
		help_msg = "LeftClick: Move / Pan | RightClick: Select | " \
		           "ShiftClick: Multi-select | Arrows: Move | S: Save | 0: Change level"
		help_text = font.render(help_msg, True, fg_color)
		display.blit(help_text, (5, size[1] - font_size*2 - 5))
		help_msg = "P: Edit points | E: Edit object | C: Copy selected | D: Delete selected | " \
		           "H: Toggle hitboxes | B: Toggle color scheme"
		help_text = font.render(help_msg, True, fg_color)
		display.blit(help_text, (5, size[1] - font_size - 5))

		pygame.display.flip()
		clock.tick(FPS)


if __name__ == "__main__":
	try:
		# PySimpleGUI
		sg.LOOK_AND_FEEL_TABLE["PolyEditor"] = {
			'BACKGROUND': '#1F2E3F',
			'TEXT': '#FFFFFF',
			'INPUT': '#2B4668',
			'TEXT_INPUT': '#FFFFFF',
			'SCROLL': '#2B4668',
			'BUTTON': ('#FFFFFF', '#2B4668'),
			'PROGRESS': ('#01826B', '#D0D0D0'),
			'BORDER': 1, 'SLIDER_DEPTH': 0, 'PROGRESS_DEPTH': 0
		}
		sg.theme("PolyEditor")
		sg.set_global_icon(ICON)

		# Hide console at runtime. We enable it with PyInstaller so that the user knows it's doing something.
		if TEMP_FILES is not None:
			print("Finished loading!")
			sleep(0.5)
			kernel32 = ctypes.WinDLL('kernel32')
			user32 = ctypes.WinDLL('user32')
			user32.ShowWindow(kernel32.GetConsoleWindow(), 0)

		# Test run
		lap = 0
		while True:
			lap += 1
			program = run(f"{POLYCONVERTER} test", capture_output=True)
			if program.returncode == GAMEPATH_ERROR_CODE:  # game install not found
				sg.Popup(program.stdout.decode().strip(), title="Problem")
				sys.exit()
			elif program.returncode == FILE_ERROR_CODE:  # as "test" is not a valid file
				break  # All OK
			else:
				outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
				if lap == 1 and "dotnet" in outputs[1]:  # .NET not installed
					currentdir = getcwd()
					filelist = [f for f in listdir(currentdir) if isfile(pathjoin(currentdir, f))]
					found_new = False
					for file in filelist:
						if re.compile(r"^PolyConverter(.+)?\.exe$").match(file):
							POLYCONVERTER = file
							found_new = True
							break
					if not found_new:
						sg.Popup(
							"It appears you don't have .NET installed.",
							"Please download 'PolyConverter including NET.exe' from "
							"https://github.com/JbCoder/PolyEditor/releases and place it in this same folder. "
							"Then run this program again.",
							title="Problem")
						sys.exit()
				else:
					sg.Popup(f"Unexpected converter error:", "\n".join([o for o in outputs if len(o) > 0]), title="Error")
					sys.exit()

		# Meta loop
		while True:
			args = choose_file()
			if args is not None:
				main(*args)

	except Exception as e:
		sg.Popup("An unexpected error occurred while running PolyEditor:", traceback.format_exc(), title="Error")
