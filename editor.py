import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
import re
import json
from sys import exit
from uuid import uuid4
from copy import deepcopy
from os import getcwd, listdir
from os.path import exists, isfile, join as pathjoin, getmtime as lastmodified
from subprocess import run

from game_objects import LayoutList, CustomShape


SIZE = [1200, 600]
ZOOM_MULT = 1.1
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BACKGROUND_BLUE = (43, 70, 104)
BACKGROUND_GRAY = (162, 154, 194)

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


if __name__ != "__main__":
	exit()

print("Booted up PolyEditor")

if not exists(POLYCONVERTER):
	print(f"Error: Cannot find {POLYCONVERTER} in this folder")
	entertoexit()

program = run(f"{POLYCONVERTER} test", capture_output=True)
if program.returncode == GAMEPATH_ERROR_CODE:  # game install not found
	print(program.stdout.decode('utf-8').strip())
	entertoexit()
elif program.returncode == FILE_ERROR_CODE:  # as "test" is not a valid file
	pass
else:  # .NET not installed?
	print("Unexpected error:\n")
	print(program.stderr.decode('utf-8').strip())
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
		outputs = [program.stdout.decode('utf-8').strip(), program.stderr.decode('utf-8').strip()]
		for o in [o for o in outputs if len(o) > 0]:
			print(o)
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


print(f"Opening {leveltoedit} in the editor")

start_x, start_y = 0, 0
mouse_x, mouse_y = 0, 0
zoom = 20
camera = [SIZE[0] / zoom / 2, -(SIZE[1] / zoom / 2 + 10)]
clock = pygame.time.Clock()
fps = 60
hitboxes = False
dragging = False
selecting = False
selected_shapes = []
bg_color = BACKGROUND_BLUE
extras_color = WHITE

custom_shapes = LayoutList(CustomShape, layout["m_CustomShapes"])
anchors = layout["m_Anchors"]

display = pygame.display.set_mode(SIZE)
pygame.display.set_caption("PolyEditor")
pygame.init()

done = False
while not done:

	display.fill(bg_color)
	# Mouse position
	font = pygame.font.SysFont('Courier', 20)
	true_mouse = (mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])
	pos_text = font.render(f"[{round(true_mouse[0], 1):>5},{round(true_mouse[1], 1):>5}]", True, extras_color)
	display.blit(pos_text, (2, 5))
	# Key actions
	font = pygame.font.SysFont('Courier', 18, True)
	help_msg = "LClick: Camera | RClick: Select | Arrows: Move | C: Copy | D: Delete | S: Save | H: Hitboxes | B: Colors"
	help_text = font.render(help_msg, True, extras_color)
	help_size = font.size(help_msg)
	display.blit(help_text, (round((SIZE[0] - help_size[0]) / 2 - 3), SIZE[1] - help_size[1] - 3))
	# Mark 0,0 for reference
	pygame.draw.line(display, extras_color, (round(zoom * (-1 + camera[0])), round(-zoom * camera[1])),
	                                     (round(zoom * (1 + camera[0])), round(-zoom * camera[1])), 1)
	pygame.draw.line(display, extras_color, (round(zoom * camera[0]), round(-zoom * (-1 + camera[1]))),
	                                     (round(zoom * camera[0]), round(-zoom * (1 + camera[1]))), 1)
	# Render Custom Shapes
	for shape in custom_shapes:
		shape.render(display, camera, zoom, anchors, hitboxes)

	for event in pygame.event.get():
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
				oldtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
				zoom *= ZOOM_MULT
				newtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
				camera = [camera[0] + newtruepos[0] - oldtruepos[0], camera[1] + newtruepos[1] - oldtruepos[1]]
			if event.button == 5:
				oldtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
				zoom /= ZOOM_MULT
				newtruepos = [event.pos[0]/zoom - camera[0], -(event.pos[1]/zoom - camera[1])]
				camera = [camera[0] + newtruepos[0] - oldtruepos[0], camera[1] + newtruepos[1] - oldtruepos[1]]
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
			mouse_x, mouse_y = event.pos
			if dragging:
				camera[0] = camera[0] + (mouse_x - old_mouse_x) / zoom
				camera[1] = camera[1] - (mouse_y - old_mouse_y) / zoom
				old_mouse_x, old_mouse_y = mouse_x, mouse_y
			if selecting:
				mouse_x, mouse_y = event.pos
		elif event.type == pygame.KEYDOWN:
			if event.key == ord('b'):
				if bg_color == BACKGROUND_GRAY:
					bg_color = BACKGROUND_BLUE
					extras_color = WHITE
				else:
					bg_color = BACKGROUND_GRAY
					extras_color = BLACK
			if event.key == ord('h'):
				hitboxes = not hitboxes
			if event.key == ord('d'):
				# Delete selected
				for shape in [s for s in custom_shapes if s.highlighted]:
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
						# Add to anchors list
						new_anchors = []
						for i, anchor_id in enumerate(shape.dynamic_anchors):
							for anchor in anchors:
								if anchor["m_Guid"] == anchor_id:
									new_anchor = deepcopy(anchor)
									new_anchor["m_Guid"] = new_shape.dynamic_anchors[i]
									new_anchors.append(new_anchor)
						anchors.extend(new_anchors)
						# Shift down-right
						new_shape.position["x"] += 1
						new_shape.position["y"] -= 1
						for c, pin in enumerate(new_shape.static_pins):
							new_shape.static_pins[c]["x"] += 1
							new_shape.static_pins[c]["y"] -= 1
						for anchor_id in new_shape.dynamic_anchors:
							for c, anchor in enumerate(anchors[:]):
								if anchor["m_Guid"] == anchor_id:
									anchors[c]["m_Pos"]["x"] += 1
									anchors[c]["m_Pos"]["y"] -= 1
				custom_shapes.extend(new_shapes)
			if event.key == ord("s"):
				print("Saving...")
				jsonstr = json.dumps(layout, indent=2)
				jsonstr = re.sub(r"(\r\n|\r|\n)( ){6,}", r" ", jsonstr) # limit depth to 3 levels
				jsonstr = re.sub(r"(\r\n|\r|\n)( ){4,}([}\]])", r" \3", jsonstr)
				with open(jsonfile, 'w') as openfile:
					openfile.write(jsonstr)
				program = run(f"{POLYCONVERTER} {jsonfile}", capture_output=True)
				if program.returncode == SUCCESS_CODE:
					pygame.quit()
					if program.stdout is None or len(program.stdout) < 6:
						print("No new changes to apply.")
					else:
						if "backup" in str(program.stdout):
							print(f"Created backup {backupfile}")
						print(f"Applied changes to {layoutfile}!")
					print("Done!")
					entertoexit()
				elif program.returncode == FILE_ERROR_CODE:  # Failed to save?
					print(program.stdout.decode('utf-8').strip())
				else:
					outputs = [program.stdout.decode('utf-8').strip(), program.stderr.decode('utf-8').strip()]
					print(f"Unexpected error:")
					for o in [o for o in outputs if len(o) > 0]:
						print(o)

	# Selecting shapes
	if selecting:
		select_box = pygame.draw.rect(display, (0, 255, 0),
		                              pygame.Rect(start_x, start_y, mouse_x - start_x, mouse_y - start_y), 1)
		true_current = (mouse_x / zoom - camera[0]), (-mouse_y / zoom - camera[1])
		selected_shapes = []
		for shape in custom_shapes:
			shape.highlighted = shape.hitbox.colliderect(select_box)

	pygame.display.flip()
	clock.tick(fps)
