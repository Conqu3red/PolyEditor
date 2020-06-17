import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
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

SIZE = [1200, 600]
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

	start_x, start_y = 0, 0
	mouse_x, mouse_y = 0, 0
	old_mouse_x, old_mouse_y = 0, 0
	zoom = 20.0
	camera = [SIZE[0] / zoom / 2, -(SIZE[1] / zoom / 2 + 5)]
	clock = pygame.time.Clock()
	fps = 60
	hitboxes = False
	dragging = False
	selecting = False
	moving = False
	old_mouse_pos = [0,0]
	bg_color = BACKGROUND_BLUE
	bg_color_2 = BACKGROUND_BLUE_GRID
	fg_color = WHITE

	terrain_stretches = g.LayoutList(g.TerrainStretch, layout)
	water_blocks = g.LayoutList(g.WaterBlock, layout)
	pillars = g.LayoutList(g.Pillar, layout)
	anchors = g.LayoutList(g.Anchor, layout)
	custom_shapes = g.LayoutList(g.CustomShape, layout)

	display = pygame.display.set_mode(SIZE)
	pygame.display.set_caption("PolyEditor")
	pygame.init()

	# Main loop
	while True:
		# Render background
		display.fill(bg_color)
		block_size = round(zoom)
		line_width = g.scale(1, zoom)
		shift = (round(camera[0] * zoom % block_size), round(camera[1] * zoom % block_size))
		if block_size > 3:
			for x in range(0, SIZE[0], block_size):
				pygame.draw.line(display, bg_color_2, (x+shift[0], 0), (x+shift[0], SIZE[1]), line_width)
			for y in range(0, SIZE[1], block_size):
				pygame.draw.line(display, bg_color_2, (0, y-shift[1]), (SIZE[0], y-shift[1]), line_width)

		# Display mouse position and zoom
		font = pygame.font.SysFont('Courier', 20)
		true_mouse = (mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])
		pos_text = font.render(f"[{round(true_mouse[0], 2):>6},{round(true_mouse[1], 2):>6}]", True, fg_color)
		display.blit(pos_text, (2, 5))
		zoom_msg = f"({str(zoom)[:4].ljust(4, '0').strip('.')})"
		zoom_size = font.size(zoom_msg)
		zoom_text = font.render(zoom_msg, True, fg_color)
		display.blit(zoom_text, (SIZE[0] - zoom_size[0] - 2, 5))

		# Display controls
		font_size = 16
		font = pygame.font.SysFont('Courier', font_size, True)
		help_msg = "Mouse Wheel: Zoom | Left Click: Move camera | Right Click: Make selection | S: Save + Quit | 0: Quit"
		help_text = font.render(help_msg, True, fg_color)
		display.blit(help_text, (5, SIZE[1] - font_size*2 - 5))
		help_msg = "Arrows: Move selected | C: Copy selected | D: Delete selected | H: Toggle hitboxes | B: Toggle color scheme"
		help_text = font.render(help_msg, True, fg_color)
		display.blit(help_text, (5, SIZE[1] - font_size - 5))

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
				pygame.quit()
				return

			elif event.type == pygame.MOUSEBUTTONDOWN:
				start_x, start_y = 0, 0
				if event.button == 1:
					clickarea = pygame.Rect(event.pos[0], event.pos[1], 1, 1)
					for i in reversed(range(len(custom_shapes))):
						if (custom_shapes[i].hitbox.colliderect(clickarea)):
							if (custom_shapes[i].highlighted == False):
								if (not(pygame.key.get_mods() & pygame.KMOD_SHIFT)):
									for enshape in custom_shapes:
										enshape.highlighted = False
								custom_shapes[i].highlighted = True
							elif (pygame.key.get_mods() & pygame.KMOD_SHIFT): custom_shapes[i].highlighted = False
							if (not(pygame.key.get_mods() & pygame.KMOD_SHIFT)): moving = True
							break
					if (moving == False): 
						dragging = True  # left click
					old_mouse_x, old_mouse_y = event.pos

				if event.button == 3:  # right click
					start_x, start_y = event.pos
					mouse_x, mouse_y = event.pos
					selecting = True

				if event.button == 4:  # mousewheel up
					oldtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
					zoom *= ZOOM_MULT
					if (zoom > 700): zoom = 700

					newtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
					camera = [camera[0] + newtruepos[0] - oldtruepos[0], camera[1] + newtruepos[1] - oldtruepos[1]]
				if event.button == 5:  # mousewheel down
					oldtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
					zoom /= ZOOM_MULT
					if (zoom < 10): zoom = 10

					newtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
					camera = [camera[0] + newtruepos[0] - oldtruepos[0], camera[1] + newtruepos[1] - oldtruepos[1]]
			elif event.type == pygame.MOUSEBUTTONUP:
				if event.button == 1:  # left click
					dragging = False
					moving = False
				if event.button == 3:  # right click
					selecting = False
					start_x, start_y = 0, 0

			elif event.type == pygame.MOUSEMOTION:
				mouse_x, mouse_y = event.pos
				if dragging:
					camera[0] = camera[0] + (mouse_x - old_mouse_x) / zoom
					camera[1] = camera[1] - (mouse_y - old_mouse_y) / zoom
					old_mouse_x, old_mouse_y = mouse_x, mouse_y
				if selecting:
					mouse_x, mouse_y = event.pos

			elif event.type == pygame.KEYDOWN:
				# Moving selection
				x_change, y_change = 0, 0
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
					for shape in [s for s in custom_shapes if s.highlighted]:
						custom_shapes.remove(shape)
						for dyn_anc_id in shape.dynamic_anchor_ids:
							for anchor in [a for a in anchors]:
								if anchor.id == dyn_anc_id:
									anchors.remove(anchor)
					for pillar in [p for p in pillars if p.highlighted]:
						pillars.remove(pillar)

				elif event.key == pygame.K_LEFT:
					x_change = -1
					move = True

				elif event.key == pygame.K_RIGHT:
					x_change = 1
					move = True

				elif event.key == pygame.K_UP:
					y_change = 1
					move = True

				elif event.key == pygame.K_DOWN:
					y_change = -1
					move = True

				elif event.key == ord("c"):
					# Copy Selected
					for shape in [s for s in custom_shapes if s.highlighted]:
						new_shape = deepcopy(shape)
						shape.highlighted = False
						# Assing new ids
						new_shape.dynamic_anchor_ids = [str(uuid4()) for _ in new_shape.dynamic_anchor_ids]
						# Add to shapes list
						custom_shapes.append(new_shape)
						# Add to anchors list
						for i in range(len(shape.dynamic_anchor_ids)):
							for anchor in [a for a in anchors if a.id == shape.dynamic_anchor_ids[i]]:
								new_anchor = deepcopy(anchor)
								new_anchor.id = new_shape.dynamic_anchor_ids[i]
								anchors.append(new_anchor)
						# Shift down-right
						new_shape.pos["x"] += 1
						new_shape.pos["y"] -= 1
						for c, pin in enumerate(new_shape.static_pins):
							new_shape.static_pins[c]["x"] += 1
							new_shape.static_pins[c]["y"] -= 1
						for dyn_anc_id in new_shape.dynamic_anchor_ids:
							for anchor in anchors:
								if anchor.id == dyn_anc_id:
									anchor.pos["x"] += 1
									anchor.pos["y"] -= 1
					for pillar in [p for p in pillars if p.highlighted]:
						new_pillar = deepcopy(pillar)
						pillar.highlighted = False
						pillars.append(new_pillar)
						new_pillar.pos["x"] += 1
						new_pillar.pos["y"] -= 1

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

				if move:
					for shape in custom_shapes:
						if shape.highlighted:
							shape.pos["x"] += x_change
							shape.pos["y"] += y_change
							for pin in shape.static_pins:
								pin["x"] += x_change
								pin["y"] += y_change
							for dyn_anc_id in shape.dynamic_anchor_ids:
								for anchor in anchors:
									if anchor.id == dyn_anc_id:
										anchor.pos["x"] += x_change
										anchor.pos["y"] += y_change
					for pillar in pillars:
						if pillar.highlighted:
							pillar.pos["x"] += x_change
							pillar.pos["y"] += y_change

		# Selecting shapes
		if selecting:
			select_box = pygame.draw.rect(display, (0, 255, 0),
										  pygame.Rect(start_x, start_y, mouse_x - start_x, mouse_y - start_y), 1)
			for shape in custom_shapes:
				shape.highlighted = shape.hitbox.colliderect(select_box)
			for pillar in pillars:
				pillar.highlighted = pillar.hitbox.colliderect(select_box)

		if moving:
			current_mouse_pos = [(mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])]
			x_change = current_mouse_pos[0] - old_mouse_pos[0]
			y_change = current_mouse_pos[1] - old_mouse_pos[1]
			for shape in custom_shapes:
				if shape.highlighted:
					shape.pos["x"] += x_change
					shape.pos["y"] += y_change
					for pin in shape.static_pins:
						pin["x"] += x_change
						pin["y"] += y_change
					for dyn_anc_id in shape.dynamic_anchor_ids:
						for anchor in anchors:
							if anchor.id == dyn_anc_id:
								anchor.pos["x"] += x_change
								anchor.pos["y"] += y_change

		old_mouse_pos = [(mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])]

		pygame.display.flip()
		clock.tick(fps)


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
