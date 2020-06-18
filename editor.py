import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
os.environ['SDL_VIDEO_CENTERED'] = '1'

import sys
import pygame
import re
import json
from uuid import uuid4
from copy import deepcopy
from itertools import chain
from operator import add, sub
from os import getcwd, listdir
from os.path import isfile, join as pathjoin, getmtime as lastmodified
from subprocess import run
import PySimpleGUI as sg


import game_objects as g
from popup_windows import Popup

BASE_SIZE = (1200, 600)
FPS = 60
ZOOM_MULT = 1.1
ZOOM_MIN = 2.0
ZOOM_MAX = 400.0
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BACKGROUND_BLUE = (43, 70, 104)
BACKGROUND_BLUE_GRID = (38, 63, 94)
BACKGROUND_GRAY = (162, 154, 194)
BACKGROUND_GRAY_GRID = (178, 169, 211)

try:  # when bundled as single executable
	POLYCONVERTER = pathjoin(sys._MEIPASS, "PolyConverter.exe")
except AttributeError:
	POLYCONVERTER = "PolyConverter.exe"
JSON_EXTENSION = ".layout.json"
LAYOUT_EXTENSION = ".layout"
BACKUP_EXTENSION = ".layout.backup"
FILE_REGEX = re.compile(f"^(.+)({JSON_EXTENSION}|{LAYOUT_EXTENSION})$")
SUCCESS_CODE = 0
JSON_ERROR_CODE = 1
CONVERSION_ERROR_CODE = 2
FILE_ERROR_CODE = 3
GAMEPATH_ERROR_CODE = 4


def main():
	currentdir = getcwd()
	filelist = [f for f in listdir(currentdir) if isfile(pathjoin(currentdir, f))]
	levellist = [match.group(1) for match in [FILE_REGEX.match(f) for f in filelist] if match]
	levellist = list(dict.fromkeys(levellist))  # remove duplicates

	if len(levellist) == 0:
		print("[>] There are no levels to edit in the current folder")
		return
	elif len(levellist) == 1:
		leveltoedit = levellist[0]
	else:
		print("[#] Enter the number of the level you want to edit:")
		print("\n".join([f" ({i + 1}) {s}" for (i, s) in enumerate(levellist)]))
		index = -1
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
			output = program.stdout.decode().strip()
			if len(output) > 0:
				print(f"[>] {'Created' if 'Created' in output else 'Updated'} {jsonfile}")
		else:
			print(f"[Error] There was a problem converting {layoutfile} to json")
			outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
			print("\n".join([o for o in outputs if len(o) > 0]))
			return

	with open(jsonfile) as openfile:
		try:
			layout = json.load(openfile)
			layout["m_Bridge"]["m_Anchors"] = layout["m_Anchors"]  # both should update together in real-time
		except json.JSONDecodeError as error:
			print(f"[Error] Invalid syntax in line {error.lineno}, column {error.colno} of {jsonfile}")
			return
		except ValueError:
			print(f"[Error] {jsonfile} is either incomplete or not a valid level")
			return

	print(f"[>] Opening {leveltoedit} in the editor")

	size = BASE_SIZE
	zoom = 20.0
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
	pygame.init()

	# Pygame loop
	while True:

		# Listen for actions
		for event in pygame.event.get():

			if event.type == pygame.QUIT:
				if popup is not None:
					popup.window.close()
				pygame.quit()
				return

			if event.type == pygame.VIDEORESIZE:
				display = pygame.display.set_mode(event.size, pygame.RESIZABLE)
				size = event.size
				g.HITBOX_SURFACE = pygame.Surface(event.size, pygame.SRCALPHA, 32)

			elif event.type == pygame.MOUSEBUTTONDOWN:
				if popup_active:
					popup.window.close()
					popup_active = False

				if event.button == 1:  # left click
					for obj in reversed(selectable_objects()):
						if obj.click_hitbox.collidepoint(event.pos):  # dragging and multiselect
							if type(obj) is g.CustomShape:
								clicked_point = [p for p in obj.point_hitboxes if p.collidepoint(event.pos)]
								if clicked_point:
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
							elif holding_shift():
								obj.highlighted = False
							break
					if not (moving or point_moving):
						dragging = True
						dragndrop_pos = true_mouse_pos()
					old_mouse_pos = event.pos

				if event.button == 3:  # right click
					mouse_pos = event.pos
					selecting_pos = event.pos
					if not point_moving or moving:
						selecting = True

				if event.button == 4:  # mousewheel up
					z_old_pos = true_mouse_pos()
					zoom *= ZOOM_MULT
					if zoom > ZOOM_MAX:
						zoom = ZOOM_MAX
					z_new_pos = true_mouse_pos()
					camera = [camera[i] + z_new_pos[i] - z_old_pos[i] for i in range(2)]

				if event.button == 5:  # mousewheel down
					z_old_pos = true_mouse_pos()
					zoom /= ZOOM_MULT
					if zoom < ZOOM_MIN:
						zoom = ZOOM_MIN
					z_new_pos = true_mouse_pos()
					camera = [camera[i] + z_new_pos[i] - z_old_pos[i] for i in range(2)]

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
					pygame.quit()
					print("[#] Closed without saving")
					return

				elif event.key == ord("s"):
					print("[>] Saving...")
					jsonstr = json.dumps(layout, indent=2)
					jsonstr = re.sub(r"(\r\n|\r|\n)( ){6,}", r" ", jsonstr)  # limit depth to 3 levels
					jsonstr = re.sub(r"(\r\n|\r|\n)( ){4,}([}\]])", r" \3", jsonstr)
					with open(jsonfile, 'w') as openfile:
						openfile.write(jsonstr)
					program = run(f"{POLYCONVERTER} {jsonfile}", capture_output=True)
					if program.returncode == SUCCESS_CODE:
						pygame.quit()
						output = program.stdout.decode().strip()
						if len(output) == 0:
							print("[>] No new changes to apply")
						else:
							if "backup" in program.stdout.decode():
								print(f"[>] Created backup {backupfile}")
							print(f"[>] Applied changes to {layoutfile}")
						print("[#] Done!")
						return
					elif program.returncode == FILE_ERROR_CODE:  # failed to save?
						print(program.stdout.decode().strip())
					else:
						outputs = [program.stdout.decode().strip(), program.stderr.decode().strip()]
						print(f"Unexpected error:\n" + "\n".join([o for o in outputs if len(o) > 0]))
				
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
						popup_start_pos = deepcopy(hl_objs[0].pos)
						values = [
								["X", popup_start_pos["x"]],
								["Y", popup_start_pos["y"]],
								["Z", popup_start_pos["z"]]
							]
						popup = Popup(values)
						popup_active = True

				# Move selection with keys
				if move:
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

		# Render background
		display.fill(bg_color)
		block_size = round(zoom)
		line_width = g.scale(1, zoom)
		shift = (round(camera[0] * zoom % block_size), round(camera[1] * zoom % block_size))
		if block_size > 3:
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
				gui_evnt, values = popup.window.read(timeout=100)
				if gui_evnt == sg.WIN_CLOSED or gui_evnt == 'Exit':
					popup.window.close()
					popup_active = False
					raise ValueError()
				x = float(values[0])
				y = float(values[1])
				z = float(values[2])
				if abs(x) > 100000 or abs(y) > 100000 or abs(z) > 1000:
					raise ValueError()
				x_change, y_change, z_change = x - obj.pos["x"], y - obj.pos["y"], z - obj.pos["z"]
				if abs(x_change) < 0.0001:  # prevent rounding-based microchanges
					x_change = 0
				if abs(y_change) < 0.0001:
					y_change = 0
				if abs(z_change) < 0.0001:
					z_change = 0
				obj.pos["x"] += x_change
				obj.pos["y"] += y_change
				obj.pos["z"] += z_change
				if type(obj) is g.CustomShape:
					for pin in obj.static_pins:
						pin["x"] += x_change
						pin["y"] += y_change
					for anchor_id in obj.dynamic_anchor_ids:
						for anchor in anchors:
							if anchor.id == anchor_id:
								anchor.pos["x"] += x_change
								anchor.pos["y"] += y_change
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
		zoom_msg = f"({str(zoom)[:4].ljust(4, '0').strip('.')})"
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
		help_msg = "Wheel: Zoom | LeftClick: Move / Pan | RightClick: Make selection | " \
		           "ShiftClick: Multiselect | S: Save + Quit | 0: Quit"
		help_text = font.render(help_msg, True, fg_color)
		display.blit(help_text, (5, size[1] - font_size*2 - 5))
		help_msg = "Arrows: Move | E: Precise Move | C: Copy selected | D: Delete selected | " \
		           "H: Toggle hitboxes | B: Toggle color scheme"
		help_text = font.render(help_msg, True, fg_color)
		display.blit(help_text, (5, size[1] - font_size - 5))

		pygame.display.flip()
		clock.tick(FPS)


if __name__ == "__main__":
	os.system("title PolyEditor Console")
	print("[#] Booted up PolyEditor")

	# Test run
	lap = 0
	while True:
		lap += 1
		program = run(f"{POLYCONVERTER} test", capture_output=True)
		if program.returncode == GAMEPATH_ERROR_CODE:  # game install not found
			print(program.stdout.decode().strip())
			input("\nPress Enter to exit...")
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
					print("It appears you don't have .NET installed.")
					print("Please download 'PolyConverter including NET.exe' from "
					      "https://github.com/JbCoder/PolyEditor/releases and place it in this same folder. "
					      "Then run this program again.")
					sys.exit()
			else:
				print(f"Unexpected PolyConverter error:\n" + "\n".join([o for o in outputs if len(o) > 0]))
				input("\nPress Enter to exit...")
				sys.exit()

	# Meta loop
	try:
		while True:
			main()
			input("\n[#] Press Enter to run the program again or Ctrl+C to exit\n")
	except KeyboardInterrupt:  # Ctrl+C
		pass
