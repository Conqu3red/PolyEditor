import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
os.environ["SDL_VIDEO_CENTERED"] = "1"

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
from os.path import isfile, join as pathjoin, getmtime as lastmodified
from subprocess import run
from time import sleep

import game_objects as g
import popup_windows as popup

# Window properties
BASE_SIZE = (1200, 600)
FPS = 60
ZOOM_MULT = 1.1
ZOOM_MIN = 4
ZOOM_MAX = 400
MENU_EVENT = pygame.USEREVENT + 1
SAVE_EVENT = pygame.USEREVENT + 2
# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BACKGROUND_BLUE = (43, 70, 104)
BACKGROUND_BLUE_DARK = (31, 46, 63)
BACKGROUND_BLUE_GRID = (38, 63, 94)
BACKGROUND_GRAY = (162, 154, 194)
BACKGROUND_GRAY_GRID = (178, 169, 211)

try:  # When bundled as single executable
	# noinspection PyUnresolvedReferences
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


def load_level():
	currentdir = getcwd()
	filelist = [f for f in listdir(currentdir) if isfile(pathjoin(currentdir, f))]
	levellist = [match.group(1) for match in [FILE_REGEX.match(f) for f in filelist] if match]
	levellist = list(dict.fromkeys(levellist))  # remove duplicates

	if len(levellist) == 0:
		popup.info("PolyEditor", "There are no levels to edit in this folder")
		sys.exit()

	leveltoedit = popup.selection("PolyEditor", "Choose a level to edit:", levellist)
	if leveltoedit is None:
		sys.exit()

	layoutfile = leveltoedit + LAYOUT_EXTENSION
	jsonfile = leveltoedit + JSON_EXTENSION
	backupfile = leveltoedit + BACKUP_EXTENSION

	if (
			layoutfile in filelist
			and (jsonfile not in filelist or lastmodified(layoutfile) > lastmodified(jsonfile))
	):
		program = run(f"{POLYCONVERTER} {layoutfile}", capture_output=True)
		if program.returncode != SUCCESS_CODE:
			outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
			popup.info("Error", f"There was a problem converting {layoutfile} to json:",
			           "\n".join([o for o in outputs if len(o) > 0]),)
			return

	with open(jsonfile) as openfile:
		try:
			layout = json.load(openfile)
			layout["m_Bridge"]["m_Anchors"] = layout["m_Anchors"]  # both should update together in real-time
		except json.JSONDecodeError as error:
			popup.info("Problem", "Couldn't open level:",
			           f"Invalid syntax in line {error.lineno}, column {error.colno} of {jsonfile}")
			return
		except ValueError:
			popup.info("Problem", "Couldn't open level:",
			           f"{jsonfile} is either incomplete or not actually a level")
			return

	return layout, layoutfile, jsonfile, backupfile


def main(layout, layoutfile, jsonfile, backupfile):

	moused_over = True
	size = BASE_SIZE
	zoom = 20
	camera = [size[0] / zoom / 2, -(size[1] / zoom / 2 + 5)]
	clock = pygame.time.Clock()
	edit_object_window = popup.EditObjectWindow(None)
	draw_points = False
	hitboxes = False
	panning = False
	selecting = False
	moving = False
	point_moving = False
	last_zoom = 0

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

	print(f"Number of Custom Shapes: {len(custom_shapes)}")
	display = pygame.display.set_mode(size, pygame.RESIZABLE)
	pygame.display.set_caption("PolyEditor")
	if ICON is not None:
		pygame.display.set_icon(pygame.image.load(ICON))
	pygame.init()

	menu_button_font = pygame.font.SysFont("Courier", 20, True)
	menu_button = pygame.Surface(tuple(map(add, (10, 6), menu_button_font.size("Menu"))))
	menu_button.fill(BACKGROUND_BLUE_DARK)
	pygame.draw.rect(menu_button, BLACK, menu_button.get_rect(), 1)
	menu_button.blit(menu_button_font.render("Menu", True, WHITE), (5, 4))
	menu_button_rect = None

	# Pygame loop
	while True:

		# Listen for actions
		for event in pygame.event.get():

			if event.type == pygame.QUIT:
				edit_object_window.close()
				if popup.yes_no("Quit and lose any unsaved changes?") == "Yes":
					pygame.quit()
					sys.exit()

			elif event.type == pygame.ACTIVEEVENT:
				if event.state == 1:
					moused_over = event.gain == 1
				if event.state == 6:  # minimized
					if edit_object_window and not event.gain:
						edit_object_window._window.minimize()

			elif event.type == pygame.VIDEORESIZE:
				display = pygame.display.set_mode(event.size, pygame.RESIZABLE)
				size = event.size
				g.HITBOX_SURFACE = pygame.Surface(event.size, pygame.SRCALPHA, 32)

			elif event.type == MENU_EVENT:
				edit_object_window.close()

				menu_window = popup.open_menu()
				if not event.clicked:
					menu_window.read()  # Ignore escape key released event

				while True:
					action = menu_window.read()[0]
					pygame.event.clear()
					if action == "Back to editor" or action == "Escape:27":
						break
					if action == "Save":
						pygame.event.post(pygame.event.Event(SAVE_EVENT, {}))
						break
					elif action == "Toggle hitboxes":
						hitboxes = not hitboxes
						break
					elif action == "Color scheme":
						if bg_color == BACKGROUND_GRAY:
							bg_color = BACKGROUND_BLUE
							bg_color_2 = BACKGROUND_BLUE_GRID
							fg_color = WHITE
						else:
							bg_color = BACKGROUND_GRAY
							bg_color_2 = BACKGROUND_GRAY_GRID
							fg_color = BLACK
						break
					if action == "Change level":
						if popup.ok_cancel("You will lose any unsaved changes.") == "Ok":
							menu_window.close()
							pygame.quit()
							return
					elif action == "Quit":
						if popup.yes_no("Quit and lose any unsaved changes?") == "Yes":
							pygame.quit()
							sys.exit()
				menu_window.close()

			elif event.type == SAVE_EVENT:
				edit_object_window.close()
				jsonstr = json.dumps(layout, indent=2)
				jsonstr = re.sub(r"(\r\n|\r|\n)( ){6,}", r" ", jsonstr)  # limit depth to 3 levels
				jsonstr = re.sub(r"(\r\n|\r|\n)( ){4,}([}\]])", r" \3", jsonstr)
				with open(jsonfile, "w") as openfile:
					openfile.write(jsonstr)
				program = run(f"{POLYCONVERTER} {jsonfile}", capture_output=True)
				if program.returncode == SUCCESS_CODE:
					output = program.stdout.decode().strip()
					if len(output) == 0:
						popup.notif("No new changes to apply.")
					else:
						if "backup" in program.stdout.decode():
							popup.notif(f"Applied changes to {layoutfile}!", f"(Created backup {backupfile})")
						else:
							popup.notif(f"Applied changes to {layoutfile}!")
				elif program.returncode == FILE_ERROR_CODE:  # failed to write file?
					popup.notif("Couldn't save:", program.stdout.decode().strip())
				else:
					outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
					popup.notif(f"Unexpected error while trying to save:",
					            "\n".join([o for o in outputs if len(o) > 0]))

			elif event.type == pygame.MOUSEBUTTONDOWN:
				if event.button == 1:  # left click
					if menu_button_rect.collidepoint(event.pos):
						pygame.event.post(pygame.event.Event(MENU_EVENT, {"clicked": True}))
						continue

					for obj in reversed(selectable_objects()):
						if obj.click_hitbox.collidepoint(event.pos):  # dragging and multiselect
							if type(obj) is g.CustomShape:
								clicked_point = [p for p in obj.point_hitboxes if p.collidepoint(event.pos)]
								if clicked_point:
									point_moving = True
									obj.selected_points = [p.collidepoint(event.pos) for p in obj.point_hitboxes]
									point_editing_shape = obj
									for o in selectable_objects():
										o.highlighted = False
									edit_object_window.close()
									break
								elif holding_shift() and obj.add_point_hitbox:
									if obj.add_point_hitbox.collidepoint(event.pos):
										obj.append_point(obj.add_point[2], obj.add_point[0])
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
								edit_object_window.close()
							elif holding_shift():
								obj.highlighted = False
								edit_object_window.close()
							break
					if not (moving or point_moving):
						panning = True
						dragndrop_pos = true_mouse_pos()
					old_mouse_pos = event.pos

				if event.button == 3:  # right click
					edit_object_window.close()
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
					last_zoom = 30

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
					last_zoom = 30

			elif event.type == pygame.MOUSEBUTTONUP:

				if event.button == 1:  # left click
					if point_moving:
						selected_shape.selected_points = []
						selected_shape = None
						point_moving = False
					if (
							not holding_shift() and dragndrop_pos is not None
							and ((not panning and dragndrop_pos != true_mouse_pos())
							     or (panning and dragndrop_pos == true_mouse_pos()))
					):
						hl_objs = [o for o in selectable_objects() if o.highlighted]
						if len(hl_objs) == 1:
							hl_objs[0].highlighted = False
					if not panning:
						edit_object_window.close()
					panning = False
					moving = False

				if event.button == 3:  # right click
					selecting = False
					edit_object_window.close()

			elif event.type == pygame.MOUSEMOTION:
				mouse_pos = event.pos
				if panning:
					camera[0] = camera[0] + (mouse_pos[0] - old_mouse_pos[0]) / zoom
					camera[1] = camera[1] - (mouse_pos[1] - old_mouse_pos[1]) / zoom
					old_mouse_pos = mouse_pos

			elif event.type == pygame.KEYDOWN:
				move_x, move_y = 0, 0
				move = False

				if event.key == pygame.K_ESCAPE:
					pygame.event.post(pygame.event.Event(MENU_EVENT, {"clicked": False}))

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

				elif event.key == pygame.K_s:
					pygame.event.post(pygame.event.Event(SAVE_EVENT, {}))

				elif event.key == pygame.K_p:
					draw_points = not draw_points

				elif event.key == pygame.K_h:
					hitboxes = not hitboxes

				elif event.key == pygame.K_d:
					# Delete selected
					for obj in [o for o in selectable_objects() if o.highlighted]:
						if type(obj) is g.CustomShape:
							for dyn_anc_id in obj.dynamic_anchor_ids:
								for anchor in [a for a in anchors]:
									if anchor.id == dyn_anc_id:
										anchors.remove(anchor)
						object_lists[obj.list_name].remove(obj)

				elif event.key == pygame.K_c:
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

				elif event.key == pygame.K_e:
					# Popup window to edit properties
					hl_objs = [o for o in selectable_objects() if o.highlighted]
					if edit_object_window:  # remove previous
						edit_object_window.close()
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
						values = {popup.POS_X: obj.pos["x"],
						          popup.POS_Y: obj.pos["y"],
						          popup.POS_Z: obj.pos["z"]}
						if type(obj) is g.CustomShape:
							rot = obj.rotations
							values[popup.SCALE_X] = obj.scale["x"]
							values[popup.SCALE_Y] = obj.scale["y"]
							values[popup.SCALE_Z] = obj.scale["z"]
							values[popup.ROT_Z] = rot[2]  # Z first
							values[popup.ROT_X] = rot[0]
							values[popup.ROT_Y] = rot[1]
							values[popup.FLIP] = obj.flipped
						edit_object_window = popup.EditObjectWindow(values)

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
			rect = pygame.Rect(selecting_pos[0], selecting_pos[1],
			                   mouse_pos[0] - selecting_pos[0], mouse_pos[1] - selecting_pos[1])
			select_box = pygame.draw.rect(display, g.SELECT_COLOR, rect, 1)
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
		if edit_object_window and len(hl_objs) == 1:
			obj = hl_objs[0]
			# The current solution to running both the edit window GUI and the pygame GUI is to make the
			#  popup window blocking, but run a single frame of the main window whenever an event is read
			#  (such as pressing a key or moving the mouse).
			# The popup window will also be non-blocking when your mouse is not over the popup window,
			#  but that currently carries the old tkinter problem where most key inputs are missed/ignored
			#  as long as the window remains non-blocking.
			timeout = 10 if moused_over else None
			event, values = edit_object_window.read(timeout)
			if event == sg.WIN_CLOSED or event == "Exit":
				edit_object_window.close()
			elif event == "Leave" or event == sg.TIMEOUT_KEY:
				pass
			else:
				# Position
				x, y, z = values[popup.POS_X], values[popup.POS_Y], values[popup.POS_Z]
				x_change, y_change, z_change = x - obj.pos["x"], y - obj.pos["y"], z - obj.pos["z"]
				if abs(x_change) > 0.000001 or abs(y_change) > 0.000001 or abs(z_change) > 0.000001:
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
					obj.scale = {"x": values[popup.SCALE_X], "y": values[popup.SCALE_Y], "z": values[popup.SCALE_Z]}
					# Rotation
					oldrot = obj.rotations
					rotx, roty, rotz = values[popup.ROT_X], values[popup.ROT_Y], values[popup.ROT_Z]
					rotx_change, roty_change, rotz_change = rotx - oldrot[0], roty - oldrot[1], rotz - oldrot[2]
					if abs(rotx_change) > 0.000001 or abs(roty_change) > 0.000001 or abs(rotz_change) > 0.000001:
						obj.rotations = (rotx, roty, rotz)
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
					# Flipped
					old_flipped = obj.flipped
					obj.flipped = values[popup.FLIP]
					if old_flipped != obj.flipped:
						for pin in obj.static_pins:
							newpin = g.rotate((pin["x"], pin["y"]), -oldrot[2], (obj.pos["x"], obj.pos["y"]))
							newpin = (2 * obj.pos["x"] - newpin[0], newpin[1])
							newpin = g.rotate(newpin, oldrot[2], (obj.pos["x"], obj.pos["y"]))
							pin["x"] = newpin[0]
							pin["y"] = newpin[1]
						for anchor_id in obj.dynamic_anchor_ids:
							for anchor in anchors:
								if anchor.id == anchor_id:
									newanchor = g.rotate((anchor.pos["x"], anchor.pos["y"]), -oldrot[2], (obj.pos["x"], obj.pos["y"]))
									newanchor = (2 * obj.pos["x"] - newanchor[0], newanchor[1])
									newanchor = g.rotate(newanchor, oldrot[2], (obj.pos["x"], obj.pos["y"]))
									anchor.pos["x"] = newanchor[0]
									anchor.pos["y"] = newanchor[1]
		else:
			edit_object_window.close()
		
		true_mouse_change = tuple(map(sub, true_mouse_pos(), old_true_mouse_pos))
		old_true_mouse_pos = true_mouse_pos()
		
		# Render Objects
		for terrain in terrain_stretches:
			terrain.render(display, camera, zoom, fg_color)
		for water in water_blocks:
			water.render(display, camera, zoom, fg_color)
		point_mode = g.PointMode(draw_points, delete_points, add_points, mouse_pos, true_mouse_change, holding_shift())
		for shape in custom_shapes:
			shape.render(display, camera, zoom, hitboxes, point_mode)
		for pillar in pillars:
			pillar.render(display, camera, zoom, hitboxes)
		dyn_anc_ids = list(chain(*[shape.dynamic_anchor_ids for shape in custom_shapes]))
		for anchor in anchors:
			anchor.render(display, camera, zoom, dyn_anc_ids)

		# Display mouse position, zoom and fps
		font = pygame.font.SysFont("Courier", 20)
		pos_msg = f"[{round(true_mouse_pos()[0], 2):>6},{round(true_mouse_pos()[1], 2):>6}]"
		pos_text = font.render(pos_msg, True, fg_color)
		display.blit(pos_text, (2, 5))
		font = pygame.font.SysFont("Courier", 16)
		zoom_msg = f"({zoom})"
		zoom_size = font.size(zoom_msg)
		zoom_text = font.render(zoom_msg, True, fg_color)
		display.blit(zoom_text, (round(size[0] / 2 - zoom_size[0] / 2), 5))
		fps_msg = str(round(clock.get_fps())).rjust(2)
		fps_size = font.size(fps_msg)
		fps_text = font.render(fps_msg, True, fg_color)
		display.blit(fps_text, (size[0] - fps_size[0] - 5, 5))

		# Display buttons
		menu_button_rect = display.blit(menu_button, (10, size[1] - menu_button.get_size()[1] - 10))

		last_zoom = max(0, last_zoom - 1)
		pygame.display.flip()
		if not edit_object_window or moused_over:  # Don't run the clock while other window is focused
			clock.tick(FPS)


if __name__ == "__main__":
	try:
		# PySimpleGUI
		sg.LOOK_AND_FEEL_TABLE["PolyEditor"] = {
			"BACKGROUND": "#1F2E3F",
			"TEXT": "#FFFFFF",
			"INPUT": "#2B4668",
			"TEXT_INPUT": "#FFFFFF",
			"SCROLL": "#2B4668",
			"BUTTON": ("#FFFFFF", "#2B4668"),
			"PROGRESS": ("#01826B", "#D0D0D0"),
			"BORDER": 1,
			"SLIDER_DEPTH": 0,
			"PROGRESS_DEPTH": 0
		}
		sg.theme("PolyEditor")
		sg.set_global_icon(ICON)

		# Hide console at runtime. We enable it with PyInstaller so that the user knows it's doing something.
		if TEMP_FILES is not None:
			print("Finished loading!")
			sleep(0.5)
			kernel32 = ctypes.WinDLL("kernel32")
			user32 = ctypes.WinDLL("user32")
			user32.ShowWindow(kernel32.GetConsoleWindow(), 0)

		# Ensure the converter is working
		lap = 0
		while True:
			lap += 1
			test_program = run(f"{POLYCONVERTER} test", capture_output=True)
			if test_program.returncode == GAMEPATH_ERROR_CODE:  # game install not found
				popup.info("Problem", test_program.stdout.decode().strip())
				sys.exit()
			elif test_program.returncode == FILE_ERROR_CODE:  # as "test" is not a valid file
				break  # All OK
			else:
				test_outputs = [test_program.stdout.decode().strip(), test_program.stderr.decode().strip()]
				if lap == 1 and "dotnet" in test_outputs[1]:  # .NET not installed
					test_dir = getcwd()
					test_filelist = [f for f in listdir(test_dir) if isfile(pathjoin(test_dir, f))]
					test_found = False
					for file in test_filelist:
						if re.compile(r"^PolyConverter(.+)?\.exe$").match(file):
							POLYCONVERTER = file
							test_found = True
							break
					if not test_found:
						popup.info("Problem",
						           "It appears you don't have .NET installed.",
						           "Please download 'PolyConverter including NET.exe' from "
						           "https://github.com/JbCoder/PolyEditor/releases and place it in this same folder. "
						           "Then run this program again.")
						sys.exit()
				else:
					popup.info("Error", "Unexpected converter error:", "\n".join([o for o in test_outputs if len(o) > 0]))
					sys.exit()

		# Meta loop
		while True:
			args = load_level()
			if args is not None:
				main(*args)

	except Exception as e:
		popup.info("Error", "An unexpected error occurred while running PolyEditor:", traceback.format_exc())
