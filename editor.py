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
from os import getcwd, listdir
from os.path import isfile, join as pathjoin, getmtime as lastmodified
from subprocess import run


import game_objects as g
from popup_windows import Popup

BASE_SIZE = (1200, 600)
FPS = 60
ZOOM_MULT = 1.1
ZOOM_MIN = 1.0
ZOOM_MAX = 300.0
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BACKGROUND_BLUE = (43, 70, 104)
BACKGROUND_BLUE_GRID = (38, 63, 94)
BACKGROUND_GRAY = (162, 154, 194)
BACKGROUND_GRAY_GRID =(178, 169, 211)

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
	hitboxes = False
	dragging = False
	selecting = False
	moving = False
	mouse_x, mouse_y = 0, 0
	selecting_x, selecting_y = 0, 0
	old_mouse_x, old_mouse_y = 0, 0
	old_true_mouse_pos = [0, 0]
	popup_edit_start_pos = None
	bg_color = BACKGROUND_BLUE
	bg_color_2 = BACKGROUND_BLUE_GRID
	fg_color = WHITE

	terrain_stretches = g.LayoutList(g.TerrainStretch, layout)
	water_blocks = g.LayoutList(g.WaterBlock, layout)
	pillars = g.LayoutList(g.Pillar, layout)
	anchors = g.LayoutList(g.Anchor, layout)
	custom_shapes = g.LayoutList(g.CustomShape, layout)

	selectable_objects = lambda: tuple(chain(custom_shapes, pillars))
	holding_shift = lambda: pygame.key.get_mods() & pygame.KMOD_SHIFT

	display = pygame.display.set_mode(size, pygame.RESIZABLE)
	pygame.display.set_caption("PolyEditor")
	pygame.init()

	# Pygame loop
	while True:

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

		# Display mouse position, zoom and fps
		font = pygame.font.SysFont('Courier', 20)
		true_mouse = (mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])
		pos_text = font.render(f"[{round(true_mouse[0], 2):>6},{round(true_mouse[1], 2):>6}]", True, fg_color)
		display.blit(pos_text, (2, 5))
		font = pygame.font.SysFont('Courier', 16)
		zoom_msg = f"({str(zoom)[:4].ljust(4, '0').strip('.')})"
		zoom_size = font.size(zoom_msg)
		zoom_text = font.render(zoom_msg, True, fg_color)
		display.blit(zoom_text, (size[0]/2 - zoom_size[0]/2, 5))
		fps_msg = str(round(clock.get_fps())).rjust(2)
		fps_size = font.size(fps_msg)
		fps_text = font.render(fps_msg, True, fg_color)
		display.blit(fps_text, (size[0] - fps_size[0] - 5, 5))

		# Display controls
		font_size = 16
		font = pygame.font.SysFont('Courier', font_size, True)
		help_msg = "Wheel: Zoom | LeftClick: Move/Pan | RightClick: Make selection | ShiftClick: Multiselect | S: Save + Quit | 0: Quit"
		help_text = font.render(help_msg, True, fg_color)
		display.blit(help_text, (5, size[1] - font_size*2 - 5))
		help_msg = "Arrows: Move selected | C: Copy selected | D: Delete selected | H: Toggle hitboxes | B: Toggle color scheme"
		help_text = font.render(help_msg, True, fg_color)
		display.blit(help_text, (5, size[1] - font_size - 5))

		# Render Objects
		for terrain in terrain_stretches:
			terrain.render(display, camera, zoom, fg_color)
		for water in water_blocks:
			water.render(display, camera, zoom, fg_color)
		for shape in custom_shapes:
			shape.render(display, camera, zoom, hitboxes, fg_color)
		for pillar in pillars:
			pillar.render(display, camera, zoom)
		dyn_anc_ids = list(chain(*[shape.dynamic_anchor_ids for shape in custom_shapes]))
		for anchor in anchors:
			anchor.render(display, camera, zoom, dyn_anc_ids)

		# Listen for actions
		for event in pygame.event.get():

			if event.type == pygame.QUIT:
				if popup is not None:
					popup.delete()
				pygame.quit()
				return

			if event.type == pygame.VIDEORESIZE:
				size = event.size
				display = pygame.display.set_mode(size, pygame.RESIZABLE)

			elif event.type == pygame.MOUSEBUTTONDOWN:
				selecting_x, selecting_y = 0, 0

				if event.button == 1:  # left click
					clickarea = pygame.Rect(event.pos[0], event.pos[1], 1, 1)
					for obj in reversed(selectable_objects()):
						if obj.hitbox.colliderect(clickarea):  # dragging and multiselect
							if not holding_shift():
								moving = True
							if not obj.highlighted:
								if not holding_shift():  # clear other selections
									for o in selectable_objects():
										o.highlighted = False
								obj.highlighted = True
							elif holding_shift():
								obj.highlighted = False
							break
					if not moving:
						dragging = True
					old_mouse_x, old_mouse_y = event.pos

				if event.button == 3:  # right click
					selecting_x, selecting_y = event.pos
					mouse_x, mouse_y = event.pos
					if holding_shift():  # multiselect
						clickarea = pygame.Rect(event.pos[0], event.pos[1], 1, 1)
						for obj in reversed(selectable_objects()):
							if obj.hitbox.colliderect(clickarea):
								obj.highlighted = not obj.highlighted
					else:
						selecting = True

				if event.button == 4:  # mousewheel up
					if zoom * ZOOM_MULT <= ZOOM_MAX:
						oldtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
						zoom *= ZOOM_MULT
						newtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
						camera = [camera[0] + newtruepos[0] - oldtruepos[0], camera[1] + newtruepos[1] - oldtruepos[1]]

				if event.button == 5:  # mousewheel down
					if zoom / ZOOM_MULT >= ZOOM_MIN:
						oldtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
						zoom /= ZOOM_MULT
						newtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
						camera = [camera[0] + newtruepos[0] - oldtruepos[0], camera[1] + newtruepos[1] - oldtruepos[1]]

			elif event.type == pygame.MOUSEBUTTONUP:

				if event.button == 1:  # left click
					dragging = False
					moving = False
					hl_objs = [o for o in selectable_objects() if o.highlighted]
					if len(hl_objs) == 1 and not holding_shift():  # "drop" object
						hl_objs[0].highlighted = False

				if event.button == 3:  # right click
					selecting = False
					selecting_x, selecting_y = 0, 0

			elif event.type == pygame.MOUSEMOTION:
				mouse_x, mouse_y = event.pos
				if dragging:
					camera[0] = camera[0] + (mouse_x - old_mouse_x) / zoom
					camera[1] = camera[1] - (mouse_y - old_mouse_y) / zoom
					old_mouse_x, old_mouse_y = mouse_x, mouse_y

			elif event.type == pygame.KEYDOWN:
				move_x, move_y = 0, 0
				move = False

				if event.key == ord('b'):
					if bg_color == BACKGROUND_GRAY:
						bg_color = BACKGROUND_BLUE
						bg_color_2 = BACKGROUND_BLUE_GRID
						fg_color = WHITE
					else:
						bg_color = BACKGROUND_GRAY
						bg_color_2 = BACKGROUND_GRAY_GRID
						fg_color = BLACK

				elif event.key == ord('h'):
					hitboxes = not hitboxes

				elif event.key == ord('d'):
					# Delete selected
					for obj in [o for o in selectable_objects() if o.highlighted]:
						if type(obj) is g.Pillar:
							pillars.remove(obj)
						elif type(obj) is g.CustomShape:
							custom_shapes.remove(obj)
							for dyn_anc_id in obj.dynamic_anchor_ids:
								for anchor in [a for a in anchors]:
									if anchor.id == dyn_anc_id:
										anchors.remove(anchor)
						else:
							raise NotImplementedError(f"Deleting {type(obj).__name__}")

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
						if type(new_obj) is g.Pillar:
							pillars.append(new_obj)
						elif type(new_obj) is g.CustomShape:
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
							custom_shapes.append(new_obj)
						else:
							raise NotImplementedError(f"Copying {type(new_obj).__name__}")

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
				
				elif event.key == ord("e") and not popup_active:
					# Popup window to edit properties
					hl_objs = [o for o in selectable_objects() if o.highlighted]
					if len(hl_objs) == 1:
						popup_edit_start_pos = deepcopy(hl_objs[0].pos)
						values = [
								["X", hl_objs[0].pos["x"]],
								["Y", hl_objs[0].pos["y"]],
								["Z", hl_objs[0].pos["z"]]
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

		# Selecting shapes
		if selecting:
			select_box = pygame.draw.rect(display, (0, 255, 0),
				pygame.Rect(selecting_x, selecting_y, mouse_x - selecting_x, mouse_y - selecting_y),
				g.scale(1, zoom))
			for obj in selectable_objects():
				obj.highlighted = obj.hitbox.colliderect(select_box)

		# Move selection with mouse
		if moving:
			true_mouse_pos = [(mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])]
			move_x = true_mouse_pos[0] - old_true_mouse_pos[0]
			move_y = true_mouse_pos[1] - old_true_mouse_pos[1]
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

		old_true_mouse_pos = [(mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])]

		hl_objs = [o for o in selectable_objects() if o.highlighted]
		if popup_active and len(hl_objs) == 1:
			obj = hl_objs[0]
			try:
				popup.update()
				popup_edit_start_pos = deepcopy(obj.pos)
				x = float(popup.get(1, 0))
				y = float(popup.get(1, 1))
				z = float(popup.get(1, 2))
				if x > 100000 or y > 100000 or z > 100000:
					raise ValueError()
				obj.pos = {"x": x, "y": y, "z": z}
				print(obj.pos)
				if type(obj) is g.CustomShape:
					x_change = obj.pos["x"] - popup_edit_start_pos["x"]
					y_change = obj.pos["y"] - popup_edit_start_pos["y"]
					for pin in obj.static_pins:
						pin["x"] += x_change
						pin["y"] += y_change
					for anchor_id in obj.dynamic_anchor_ids:
						for anchor in anchors:
							if anchor.id == anchor_id:
								anchor.pos["x"] += x_change
								anchor.pos["y"] += y_change
			except ValueError:
				pass
		elif popup_active:
			popup_active = False
			popup.delete()

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
