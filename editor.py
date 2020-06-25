import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
os.environ["SDL_VIDEO_CENTERED"] = "1"

import sys
import pygame
import re
import json
import traceback
import threading
import PySimpleGUI as sg
from os import getcwd, listdir
from os.path import isfile, join as pathjoin, getmtime as lastmodified
from ctypes import WinDLL
from uuid import uuid4
from copy import deepcopy
from time import sleep
from itertools import chain
from subprocess import run
from typing import *

import popup_windows as popup
import layout_objects as lay
import editor_events as ev
from math_objects import Vector

# Window properties
BASE_SIZE = (1200, 600)
FPS = 60
ZOOM_MULT = 1.1
ZOOM_MIN = 4
ZOOM_MAX = 400
SAVE_LAYOUT_EVENT = pygame.USEREVENT + 1
try:
	KERNEL32 = WinDLL("kernel32")
	USER32 = WinDLL("user32")
except Exception:
	KERNEL32 = None
	USER32 = None

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


def load_level() -> Optional[Tuple[dict, str, str, str]]:
	currentdir = getcwd()
	filelist = [f for f in listdir(currentdir) if isfile(pathjoin(currentdir, f))]
	levellist = [match.group(1) for f in filelist if (match := FILE_REGEX.match(f))]
	levellist = list(dict.fromkeys(levellist))  # remove duplicates

	if len(levellist) == 0:
		popup.info(
			"PolyEditor",
			"There are no levels to edit in this folder.",
			"Tip: The game stores Sandbox levels in /Documents/Dry Cactus/Poly Bridge 2/Sandbox"
		)
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
			           "\n".join([o for o in outputs if len(o) > 0]))
			return None

	with open(jsonfile) as openfile:
		try:
			layout = json.load(openfile)
			layout["m_Bridge"]["m_Anchors"] = layout["m_Anchors"]  # both should update together in real-time
		except json.JSONDecodeError as error:
			popup.info("Problem", "Couldn't open level:",
			           f"Invalid syntax in line {error.lineno}, column {error.colno} of {jsonfile}")
			return None
		except ValueError:
			popup.info("Problem", "Couldn't open level:",
			           f"{jsonfile} is either incomplete or not actually a level")
			return None

	return layout, layoutfile, jsonfile, backupfile


def editor(layout: dict, layoutfile: str, jsonfile: str, backupfile: str, events: ev.EventLane):
	zoom = 20
	size = Vector(BASE_SIZE)
	camera = Vector(0, 0)
	clock = pygame.time.Clock()
	paused = False
	pause_force_render = False
	draw_points = False
	draw_hitboxes = False
	panning = False
	selecting = False
	moving = False
	point_moving = False
	mouse_pos = Vector(0, 0)
	old_mouse_pos = Vector(0, 0)
	old_true_mouse_pos = Vector(0, 0)
	selecting_pos = Vector(0, 0)
	dragndrop_pos = Vector(0, 0)
	object_being_edited: Optional[lay.SelectableObject] = None
	selected_shape: Optional[lay.CustomShape] = None
	bg_color = BACKGROUND_BLUE
	bg_color_2 = BACKGROUND_BLUE_GRID
	fg_color = WHITE

	object_lists = [
		terrain_stretches := lay.LayoutList(lay.TerrainStretch, layout),
		water_blocks := lay.LayoutList(lay.WaterBlock, layout),
		custom_shapes := lay.LayoutList(lay.CustomShape, layout),
		pillars := lay.LayoutList(lay.Pillar, layout),
		anchors := lay.LayoutList(lay.Anchor, layout)
	]
	objects: Dict[Type[lay.LayoutObject], lay.LayoutList] = {li.cls: li for li in object_lists}

	selectable_objects = lambda: tuple(chain(custom_shapes, pillars))
	holding_shift = lambda: pygame.key.get_mods() & pygame.KMOD_SHIFT
	true_mouse_pos = lambda: mouse_pos.flip_y() / zoom - camera

	# Start pygame
	display = pygame.display.set_mode(size, pygame.RESIZABLE)
	pygame.display.set_caption("PolyEditor")
	if ICON:
		pygame.display.set_icon(pygame.image.load(ICON))
	pygame.init()
	if USER32:  # Maximize
		USER32.ShowWindow(USER32.GetForegroundWindow(), 3)
		for pyevent in pygame.event.get():
			if pyevent.type == pygame.VIDEORESIZE:
				size = Vector(pyevent.size)
				display = pygame.display.set_mode(size, pygame.RESIZABLE)
	lay.DUMMY_SURFACE = pygame.Surface(size, pygame.SRCALPHA, 32)
	camera = (size / zoom / 2 + (0, 10)).flip_y()

	menu_button_font = pygame.font.SysFont("Courier", 20, True)
	menu_button = pygame.Surface(Vector(menu_button_font.size("Menu")) + (10, 6))
	menu_button.fill(BACKGROUND_BLUE_DARK)
	pygame.draw.rect(menu_button, BLACK, menu_button.get_rect(), 1)
	menu_button.blit(menu_button_font.render("Menu", True, WHITE), (5, 4))
	menu_button_rect = None

	# Editor loop
	while True:

		# Process editor events
		if (event := events.read()) is not None:

			if event == ev.CLOSE_EDITOR:
				pygame.quit()
				events.send(ev.DONE)
				return

			elif event == ev.DONE:
				paused = False

			elif object_being_edited:
				if event == ev.EXIT:
					object_being_edited = None
					events.send(ev.CLOSE_OBJ_EDIT)
				elif hasattr(event, "values"):
					values = event.values
					hl_objs = [o for o in selectable_objects() if o.selected]
					if len(hl_objs) == 1:
						obj = hl_objs[0]
						obj.pos = Vector(values[popup.POS_X], values[popup.POS_Y], values[popup.POS_Z])
						if isinstance(obj, lay.CustomShape):
							obj.scale = Vector(values[popup.SCALE_X], values[popup.SCALE_Y], values[popup.SCALE_Z])
							obj.rotations = Vector(values[popup.ROT_X], values[popup.ROT_Y], values[popup.ROT_Z])
							obj.color = Vector(values[popup.RGB_R], values[popup.RGB_G], values[popup.RGB_B])
							obj.flipped = values[popup.FLIP]
							obj.calculate_hitbox()
						elif isinstance(obj, lay.Pillar):
							obj.height = values[popup.HEIGHT]
					else:  # Multiple objects
						for obj in hl_objs:
							if isinstance(obj, lay.CustomShape):
								obj.color = (values[popup.RGB_R], values[popup.RGB_G], values[popup.RGB_B])

			elif paused:
				if event in (ev.MENU_RETURN, ev.ESCAPE, ev.FOCUS_OUT):
					events.send(ev.DONE)
					paused = False
				elif event == ev.MENU_SAVE:
					pygame.event.post(pygame.event.Event(SAVE_LAYOUT_EVENT, {}))
					events.send(ev.DONE)
					paused = False
				elif event == ev.MENU_HITBOXES:
					draw_hitboxes = not draw_hitboxes
					pause_force_render = True
				elif event == ev.MENU_COLORS:
					if bg_color == BACKGROUND_GRAY:
						bg_color = BACKGROUND_BLUE
						bg_color_2 = BACKGROUND_BLUE_GRID
						fg_color = WHITE
					else:
						bg_color = BACKGROUND_GRAY
						bg_color_2 = BACKGROUND_GRAY_GRID
						fg_color = BLACK
					pause_force_render = True
				elif event == ev.MENU_CHANGE_LEVEL:
					events.send(ev.RESTART_PROGRAM)
				elif event == ev.MENU_QUIT:
					events.send(ev.CLOSE_PROGRAM, force=False)

		# Proccess pygame events
		for pyevent in pygame.event.get():

			if pyevent.type == pygame.QUIT:
				events.send(ev.CLOSE_PROGRAM, force=True)

			elif pyevent.type == pygame.ACTIVEEVENT:
				if pyevent.state == 6 and not pyevent.gain:  # Minimized
					object_being_edited = None
					events.send(ev.CLOSE_OBJ_EDIT)
					events.send(ev.DONE)

			elif pyevent.type == pygame.VIDEORESIZE:
				size = Vector(pyevent.size)
				display = pygame.display.set_mode(size, pygame.RESIZABLE)
				lay.DUMMY_SURFACE = pygame.Surface(size, pygame.SRCALPHA, 32)
				pause_force_render = True

			elif (
					paused and pyevent.type == pygame.KEYDOWN
					and pyevent.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE)
			):
				events.send(ev.DONE)
				paused = False
				continue

			if paused:
				continue

			elif pyevent.type == SAVE_LAYOUT_EVENT:
				jsonstr = json.dumps(layout, indent=2)
				jsonstr = re.sub(r"(\r\n|\r|\n)( ){6,}", r" ", jsonstr)  # limit depth to 3 levels
				jsonstr = re.sub(r"(\r\n|\r|\n)( ){4,}([}\]])", r" \3", jsonstr)
				with open(jsonfile, "w") as openfile:
					openfile.write(jsonstr)
				program = run(f"{POLYCONVERTER} {jsonfile}", capture_output=True)
				if program.returncode == SUCCESS_CODE:
					output = program.stdout.decode().strip()
					if len(output) == 0:
						events.send(popup.notif, "Saved! No new changes to apply.")
						paused = True
					else:
						if "backup" in program.stdout.decode():
							events.send(popup.notif, f"Saved level as {layoutfile}!",
							                         f"(Copied original to {backupfile})")
						else:
							events.send(popup.notif, f"Saved level as {layoutfile}!", )
				elif program.returncode == FILE_ERROR_CODE:  # failed to write file?
					events.send(popup.notif, "Couldn't save:", program.stdout.decode().strip())
				else:
					outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
					events.send(popup.notif, f"Unexpected error while trying to save:",
					                         "\n".join([o for o in outputs if len(o) > 0]))

			elif pyevent.type == pygame.MOUSEBUTTONDOWN:
				if pyevent.button == 1:  # left click
					if menu_button_rect.collidepoint(pyevent.pos):
						events.send(popup.open_menu, clicked=True)
						paused = True
						continue

					if draw_points:
						# Point editing
						for obj in reversed(custom_shapes):
							if draw_points and obj.bounding_box.collidepoint(*pyevent.pos):
								clicked_point = [p.collidepoint(pyevent.pos) for p in obj.point_hitboxes]
								if holding_shift() and obj.add_point_hitbox:
									if obj.add_point_hitbox.collidepoint(pyevent.pos):
										obj.add_point(obj.add_point_closest[2], obj.add_point_closest[0])
										obj.selected_point_index = obj.add_point_closest[2]
										point_moving = True
										selected_shape = obj
										break
								elif True in clicked_point:
									point_moving = True
									obj.selected_point_index = clicked_point.index(True)
									selected_shape = obj
									for o in selectable_objects():
										o.selected = False
									object_being_edited = None
									events.send(ev.CLOSE_OBJ_EDIT)
									break
					if not point_moving:
						# Dragging and multiselect
						for obj in reversed(selectable_objects()):
							if obj.collidepoint(pyevent.pos):
								if not holding_shift():
									moving = True
									dragndrop_pos = true_mouse_pos() if not obj.selected else Vector()
								if not obj.selected:
									if not holding_shift():  # clear other selections
										for o in selectable_objects():
											o.selected = False
									obj.selected = True
									object_being_edited = None
									events.send(ev.CLOSE_OBJ_EDIT)
								elif holding_shift():
									obj.selected = False
									object_being_edited = None
									events.send(ev.CLOSE_OBJ_EDIT)
								break
						if not (moving or point_moving):
							panning = True
							dragndrop_pos = true_mouse_pos()
						old_mouse_pos = Vector(pyevent.pos)

				if pyevent.button == 3:  # right click
					object_being_edited = None
					events.send(ev.CLOSE_OBJ_EDIT)
					# Delete point
					deleted_point = False
					if draw_points:
						for obj in reversed(custom_shapes):
							if obj.bounding_box.collidepoint(*pyevent.pos):
								for i, point in enumerate(obj.point_hitboxes):
									if point.collidepoint(pyevent.pos):
										if len(obj.points) > 3:
											obj.del_point(i)
										deleted_point = True
										break
								if deleted_point:
									break
					if not deleted_point:
						if not point_moving or moving or holding_shift():
							selecting_pos = Vector(pyevent.pos)
							selecting = True

				if pyevent.button == 4:  # mousewheel up
					zoom_old_pos = true_mouse_pos()
					if not holding_shift() and round(zoom * (ZOOM_MULT - 1)) >= 1:
						zoom = round(zoom * ZOOM_MULT)
					else:
						zoom += 1
					zoom = min(zoom, ZOOM_MAX)
					zoom_new_pos = true_mouse_pos()
					camera += zoom_new_pos - zoom_old_pos

				if pyevent.button == 5:  # mousewheel down
					zoom_old_pos = true_mouse_pos()
					if not holding_shift() and round(zoom / (ZOOM_MULT - 1)) >= 1:
						zoom = round(zoom / ZOOM_MULT)
					else:
						zoom -= 1
					zoom = max(zoom, ZOOM_MIN)
					zoom_new_pos = true_mouse_pos()
					camera += zoom_new_pos - zoom_old_pos

			elif pyevent.type == pygame.MOUSEBUTTONUP:

				if pyevent.button == 1:  # left click
					if point_moving:
						selected_shape.selected_point_index = None
						selected_shape = None
						point_moving = False
					if (
							not holding_shift() and dragndrop_pos
							and ((not panning and dragndrop_pos != true_mouse_pos())
							     or (panning and dragndrop_pos == true_mouse_pos()))
					):
						hl_objs = [o for o in selectable_objects() if o.selected]
						for obj in hl_objs:
							obj.selected = False
						object_being_edited = None
						events.send(ev.CLOSE_OBJ_EDIT)

					panning = False
					moving = False

				if pyevent.button == 3:  # right click
					selecting = False

			elif pyevent.type == pygame.MOUSEMOTION:
				mouse_pos = Vector(pyevent.pos)
				if panning:
					camera += (mouse_pos - old_mouse_pos).flip_y() / zoom
					old_mouse_pos = mouse_pos

			elif pyevent.type == pygame.KEYDOWN:
				move_x, move_y = 0, 0
				move = False

				if pyevent.key == pygame.K_ESCAPE:
					events.send(popup.open_menu, clicked=False)
					object_being_edited = None
					paused = True
					continue

				elif pyevent.key == pygame.K_LEFT:
					move_x = -1
					move = True

				elif pyevent.key == pygame.K_RIGHT:
					move_x = 1
					move = True

				elif pyevent.key == pygame.K_UP:
					move_y = 1
					move = True

				elif pyevent.key == pygame.K_DOWN:
					move_y = -1
					move = True

				elif pyevent.key == pygame.K_s:
					pygame.event.post(pygame.event.Event(SAVE_LAYOUT_EVENT, {}))

				elif pyevent.key == pygame.K_p:
					draw_points = not draw_points

				elif pyevent.key == pygame.K_h:
					draw_hitboxes = not draw_hitboxes

				elif pyevent.key == pygame.K_d:
					# Delete selected
					for obj in [o for o in selectable_objects() if o.selected]:
						if isinstance(obj, lay.CustomShape):
							for dyn_anc_id in obj.dynamic_anchor_ids:
								for anchor in [a for a in anchors]:
									if anchor.id == dyn_anc_id:
										anchors.remove(anchor)
						objects[type(obj)].remove(obj)

				elif pyevent.key == pygame.K_c:
					# Copy Selected
					for old_obj in [o for o in selectable_objects() if o.selected]:
						new_obj = type(old_obj)(deepcopy(old_obj.dictionary))
						old_obj.selected = False
						new_obj.selected = True
						if isinstance(old_obj, lay.CustomShape):
							new_anchors = []
							for i in range(len(old_obj.dynamic_anchor_ids)):
								for anchor in [a for a in anchors if a.id == old_obj.dynamic_anchor_ids[i]]:
									new_anchor = deepcopy(anchor)
									new_anchor.id = str(uuid4())
									new_anchors.append(new_anchor)
							anchors.extend(new_anchors)
							new_obj.dynamic_anchor_ids = [a.id for a in new_anchors]
							new_obj.anchors = new_anchors
						new_obj.pos += (1, -1)
						objects[type(new_obj)].append(new_obj)

				elif pyevent.key == pygame.K_e:
					# Popup window to edit object properties
					hl_objs = [o for o in selectable_objects() if o.selected]
					if len(hl_objs) == 0:  # under cursor
						for obj in reversed(selectable_objects()):
							if obj.collidepoint(mouse_pos):
								obj.selected = True
								hl_objs.append(obj)
								break
					if object_being_edited:  # clear previous
						for obj in hl_objs:
							obj.selected = False
						hl_objs.clear()
						object_being_edited = None
						events.send(ev.CLOSE_OBJ_EDIT)
					elif len(hl_objs) == 1:
						obj = hl_objs[0]
						values = {popup.POS_X: obj.pos.x,
						          popup.POS_Y: obj.pos.y,
						          popup.POS_Z: obj.pos.z}
						if isinstance(obj, lay.CustomShape):
							rot = obj.rotations
							values[popup.SCALE_X] = obj.scale.x
							values[popup.SCALE_Y] = obj.scale.y
							values[popup.SCALE_Z] = obj.scale.z
							values[popup.ROT_Z] = rot.z  # Z first
							values[popup.ROT_X] = rot.x
							values[popup.ROT_Y] = rot.y
							values[popup.RGB_R] = obj.color[0]
							values[popup.RGB_G] = obj.color[1]
							values[popup.RGB_B] = obj.color[2]
							values[popup.FLIP] = obj.flipped
						elif isinstance(obj, lay.Pillar):
							values[popup.HEIGHT] = obj.height
						object_being_edited = obj
						events.send(ev.OPEN_OBJ_EDIT, values=values)
					elif len(hl_objs) > 1:
						values = {}
						for i in range(len(hl_objs)):
							if isinstance(hl_objs[i], lay.CustomShape):
								values[popup.RGB_R] = hl_objs[i].color[0]
								values[popup.RGB_G] = hl_objs[i].color[1]
								values[popup.RGB_B] = hl_objs[i].color[2]
								object_being_edited = hl_objs[i]
								events.send(ev.OPEN_OBJ_EDIT, values=values)
								break
				# Move selection with keys
				if move:
					hl_objs = [o for o in selectable_objects() if o.selected]
					for obj in hl_objs:
						obj.pos += (move_x, move_y)
					if len(hl_objs) == 0:
						camera -= (move_x, move_y)
					elif object_being_edited and len(hl_objs) == 1 and object_being_edited == hl_objs[0]:
						events.send(ev.UPDATE_OBJ_EDIT,
						            values={popup.POS_X: hl_objs[0].pos.x, popup.POS_Y: hl_objs[0].pos.y})

		# Don't render while paused
		if paused and not pause_force_render:
			clock.tick(FPS)
			continue

		# Render background
		display.fill(bg_color)
		block_size = zoom
		line_width = lay.scale(1, zoom)
		shift = (camera * zoom % block_size).round()
		for x in range(shift.x, size.x, block_size):
			pygame.draw.line(display, bg_color_2, (x, 0), (x, size.y), line_width)
		for y in range(-shift.y, size.y, block_size):
			pygame.draw.line(display, bg_color_2, (0, y), (size.x, y), line_width)

		# Move selection with mouse
		if moving:
			hl_objs = [o for o in selectable_objects() if o.selected]
			for obj in hl_objs:
				obj.pos += true_mouse_pos() - old_true_mouse_pos
			if object_being_edited and len(hl_objs) == 1 and object_being_edited == hl_objs[0]:
				events.send(ev.UPDATE_OBJ_EDIT,
				            values={popup.POS_X: hl_objs[0].pos.x, popup.POS_Y: hl_objs[0].pos.y})

		true_mouse_change = true_mouse_pos() - old_true_mouse_pos
		old_true_mouse_pos = true_mouse_pos()

		# Render Objects
		for terrain in terrain_stretches:
			terrain.render(display, camera, zoom, fg_color)
		for water in water_blocks:
			water.render(display, camera, zoom, fg_color)
		shape_args = lay.ShapeRenderArgs(draw_points, draw_hitboxes, holding_shift(), mouse_pos, true_mouse_change)
		for shape in custom_shapes:
			shape.render(display, camera, zoom, shape_args)
		for shape in custom_shapes:
			shape.render_points(display, camera, zoom, shape_args)
		if shape_args.top_point is not None:
			color = lay.HIGHLIGHT_COLOR if shape_args.selected_point is not None else lay.POINT_COLOR
			shape_args.top_point.render(display, color, round(zoom * lay.POINT_SELECTED_RADIUS))
		for pillar in pillars:
			pillar.render(display, camera, zoom, draw_hitboxes)
		dyn_anc_ids = list(chain(*[shape.dynamic_anchor_ids for shape in custom_shapes]))
		for anchor in anchors:
			anchor.render(display, camera, zoom, dyn_anc_ids)

		# Selecting shapes
		if selecting:
			rect = (min(selecting_pos.x, mouse_pos.x),
			        min(selecting_pos.y, mouse_pos.y),
			        abs(mouse_pos.x - selecting_pos.x),
			        abs(mouse_pos.y - selecting_pos.y))
			pygame.draw.rect(display, lay.SELECT_COLOR, rect, 1)
			mask = lay.rect_hitbox_mask(rect, zoom)
			for obj in selectable_objects():
				if not holding_shift():
					obj.selected = obj.colliderect(rect, mask)
				elif obj.colliderect(rect, mask):  # multiselect
					obj.selected = True

		# Display mouse position, zoom and fps
		font = pygame.font.SysFont("Courier", 20)
		pos_msg = f"[{round(true_mouse_pos().x, 2):>6},{round(true_mouse_pos().y, 2):>6}]"
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
		menu_button_rect = display.blit(menu_button, (10, size.y - menu_button.get_size()[1] - 10))

		pause_force_render = False
		pygame.display.flip()
		clock.tick(FPS)


def main():
	global POLYCONVERTER

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
	if TEMP_FILES:
		print("Finished loading!")
		sleep(0.5)
		if USER32:
			USER32.ShowWindow(KERNEL32.GetConsoleWindow(), 0)

	# Ensure the converter is working
	lap = 0
	while True:
		lap += 1
		program = run(f"{POLYCONVERTER} test", capture_output=True)
		if program.returncode == GAMEPATH_ERROR_CODE:  # game install not found
			popup.info("Problem", program.stdout.decode().strip())
			sys.exit()
		elif program.returncode == FILE_ERROR_CODE:  # as "test" is not a valid file
			break  # All OK
		else:
			outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
			if lap == 1 and "dotnet" in outputs[1]:  # .NET not installed
				currentdir = getcwd()
				filelist = [f for f in listdir(currentdir) if isfile(pathjoin(currentdir, f))]
				found = False
				for file in filelist:
					if re.compile(r"PolyConverter(.+)?\.exe$").match(file):
						POLYCONVERTER = file
						found = True
						break
				if not found:
					popup.info("Problem",
					           "It appears you don't have .NET installed.",
					           "Please download the optional converter executable (which includes .NET) from "
					           "https://github.com/JbCoder/PolyEditor/releases and place it in this same folder. "
					           "Then run PolyEditor again.")
					sys.exit()
			else:
				popup.info("Error", "Unexpected converter error:",
				           "\n".join([o for o in outputs if len(o) > 0]))
				sys.exit()

	# Main loop
	close_program = False
	while not close_program:

		if not (editor_args := load_level()):
			continue

		# We run the pygame-based editor in a secondary thread and any additional windows here in the main thread.
		# It has to be in that order because tkinter can't run unless it's in the main thread
		events = ev.EventLane()
		pygame_thread = threading.Thread(target=editor, args=(*editor_args, events.flipped()), daemon=True)
		pygame_thread.start()

		object_editing_window = popup.EditObjectWindow(None)

		close_editor = False
		while not close_editor:
			event = events.read(block=not object_editing_window)

			if event is None:
				pass

			# Main Menu
			elif event == popup.open_menu:
				object_editing_window.close()
				menu_window = popup.open_menu()
				close_menu, cleared_popup = False, False
				while not close_menu:
					event = events.read()
					if event is None:
						window_event = menu_window.read(timeout=10)[0]
						if window_event == ev.TIMEOUT:
							pass
						elif window_event == ev.FOCUS_OUT and cleared_popup:
							cleared_popup = False
						else:
							events.send(window_event)
					elif event == ev.RESTART_PROGRAM:
						if popup.ok_cancel("You will lose any unsaved changes.") == "Ok":
							close_menu, close_editor = True, True
						else:
							cleared_popup = True
					elif event == ev.CLOSE_PROGRAM:
						if event.force or popup.yes_no("Quit and lose any unsaved changes?") == "Yes":
							close_menu, close_editor, close_program = True, True, True
						else:
							cleared_popup = True
					elif event == ev.DONE:
						close_menu = True
				if not close_editor:
					events.send(ev.DONE)
				popup.safe_close(menu_window)

			# Popup Message
			elif event in (popup.info, popup.notif, popup.yes_no, popup.ok_cancel):
				object_editing_window.close()
				popup_window = event(*event.args, read=False)
				popup_result = None
				while not popup_result:
					event = events.read()
					if event is None:
						window_event = popup_window.read(timeout=10)[0]
						if window_event in ev.NOTIF_ANSWERS:
							popup_result = window_event
					if event == ev.DONE:
						break
					elif event == ev.CLOSE_PROGRAM:
						close_editor, close_program = True, True
						break
				events.send(ev.DONE, result=popup_result)
				popup.safe_close(popup_window)

			elif event == ev.OPEN_OBJ_EDIT:
				object_editing_window.close()
				object_editing_window = popup.EditObjectWindow(event.values)

			elif event == ev.UPDATE_OBJ_EDIT:
				if object_editing_window:
					for key, val in event.values.items():
						object_editing_window.inputs[key].update(str(val))

			elif event == ev.CLOSE_OBJ_EDIT:
				object_editing_window.close()

			elif event == ev.CLOSE_EDITOR:
				close_editor = True

			elif event == ev.CLOSE_PROGRAM:
				close_editor, close_program = True, True

			elif event == ev.DONE:
				pass

			# Any function, if needed for whatever reason
			elif callable(event.key):
				event(*event.args)
				events.send(ev.DONE)

			else:
				print(f"Warning: Unrecognized event {event}")

			if object_editing_window:
				window_event, window_values = object_editing_window.read(timeout=10)
				if window_event != ev.TIMEOUT:
					events.send(window_event, values=window_values)

		events.send(ev.CLOSE_EDITOR)
		events.read(block=True)


if __name__ == "__main__":
	try:
		main()
	except Exception as main_exception:
		if TEMP_FILES:
			popup.info("Error", "An unexpected error occurred while running PolyEditor:", traceback.format_exc())
		else:
			raise main_exception
