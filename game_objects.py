import pygame
import pygame.gfxdraw
import math
from copy import deepcopy
from operator import add, sub


HIGHLIGHT_COLOR = (255, 255, 0)
SELECT_COLOR = (0, 255, 0)
HITBOX_COLOR = (255, 0, 255)
HITBOX_CENTER_WIDTH = 3
SHAPE_HIGHLIGHTED_WIDTH = 2

ANCHOR_RADIUS = 0.16
ANCHOR_COLOR = (235, 0, 50)
ANCHOR_BORDER = (0, 0, 0)
DYNAMIC_ANCHOR_COLOR = (222, 168, 62)

PIN_RADIUS = 0.125
STATIC_PIN_COLOR = (0, 0, 0)
STATIC_PIN_BORDER = (50, 50, 50)

POINT_RADIUS = PIN_RADIUS / 2
POINT_COLOR = (255, 255, 255)

TERRAIN_MAIN_WIDTH = 25.25
TERRAIN_SMALL_WIDTH = 4.0
TERRAIN_BASE_HEIGHT = 5.0
TERRAIN_BORDER_WIDTH = 2
WATER_EDGE_WIDTH = 1

PILLAR_WIDTH = 1.0
PILLAR_COLOR = (195, 171, 149, 150)
PILLAR_BORDER = (105, 98, 91)
PILLAR_BORDER_WIDTH = 1


def scale(min_width, zoom, factor=30):
	"""Scales the width of a line to the zoom level"""
	return max(min_width, round(zoom / (factor / min_width)))


def rotate(point, angle, origin=(0, 0), deg=True):
	"""Rotate a point by a given angle counterclockwise around (0,0)"""
	if deg:
		angle = math.radians(angle)
	px, py = tuple(map(sub, point, origin))
	x = math.cos(angle) * px - math.sin(angle) * py + origin[0]
	y = math.sin(angle) * px + math.cos(angle) * py + origin[1]
	return x, y


def quaternion(x, y, z, deg=True):
	"""Converts euler angles to a quaternion
	https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles"""
	if deg:
		x = math.radians(x)
		y = math.radians(y)
		z = math.radians(z)

	cx = math.cos(x * 0.5)
	sx = math.sin(x * 0.5)
	cy = math.cos(y * 0.5)
	sy = math.sin(y * 0.5)
	cz = math.cos(z * 0.5)
	sz = math.sin(z * 0.5)

	qx = sx * cy * cz - cx * sy * sz
	qy = cx * sy * cz + sx * cy * sz
	qz = cx * cy * sz - sx * sy * cz
	qw = cx * cy * cz + sx * sy * sz
	return qx, qy, qz, qw


def euler_angles(qx, qy, qz, qw, deg=True):
	"""Converts a quaternion to euler angles
	https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles"""
	sx_cy = 2 * (qw * qx + qy * qz)
	cx_cy = 1 - 2 * (qx**2 + qy**1)
	x = math.atan2(sx_cy, cx_cy)

	sy = 2 * (qw * qy - qz * qx)
	y = math.asin(sy) if -1 < sy < 1 else math.copysign(math.pi / 2, sy)

	sz_cy = 2 * (qw * qz + qx * qy)
	cz_cy = 1 - 2 * (qy**2 + qz**2)
	z = math.atan2(sz_cy, cz_cy)

	if deg:
		x = math.degrees(x)
		y = math.degrees(y)
		z = math.degrees(z)
	return x, y, z


class LayoutObject:
	"""Acts as a wrapper for the dictionary that represents an object in the layout."""
	list_name = None

	def __init__(self, dictionary):
		self._dict = dictionary

	@property
	def dictionary(self):
		return self._dict

	@property
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		self._dict["m_Pos"] = value


class SelectableObject(LayoutObject):
	def __init__(self, dictionary):
		super().__init__(dictionary)
		self.highlighted = False
		self._hitbox_zoom = 1
		self._hitbox_moved = False
		self._hitbox_camera = None
		self._hitbox = None

	def collidepoint(self, point, camera):
		oldpoint = point
		point = (round(point[0] - self._hitbox_camera[0] + camera[0]),
		         round(point[1] - self._hitbox_camera[1] + camera[1]))
		size = self._hitbox.get_size()
		return bool(self._hitbox.get_at(point)) if 0 <= point[0] <= size[0] and 0 <= point[1] <= size[1] else False

	def colliderect(self, point, camera):
		return False

	@property
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		print("Moved")
		self._dict["m_Pos"] = value


class LayoutList:
	"""Acts a wrapper for a list of dictionaries in the layout, allowing you to treat them as objects."""

	def __init__(self, cls, layout):
		if not issubclass(cls, LayoutObject): raise TypeError()
		self._dictlist = layout[cls.list_name]
		self._objlist = [cls(o) for o in self._dictlist]
		self.list_name = cls.list_name
		self.cls = cls

	def append(self, elem):
		self._dictlist.append(elem.dictionary)
		self._objlist.append(elem)

	def extend(self, elems):
		self._dictlist.extend([e.dictionary for e in elems])
		self._objlist.extend(elems)

	def remove(self, elem):
		self._dictlist.remove(elem.dictionary)
		self._objlist.remove(elem)

	def __len__(self):
		return self._objlist.__len__()

	def __iter__(self):
		return self._objlist.__iter__()

	def __getitem__(self, item):
		return self._objlist.__getitem__(item)


class Anchor(LayoutObject):
	list_name = "m_Anchors"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display, camera, zoom, dynamic_anchor_ids):
		color = ANCHOR_COLOR
		for dyn_anc_id in dynamic_anchor_ids:
			if self.id == dyn_anc_id:
				color = DYNAMIC_ANCHOR_COLOR
				break
		rect = (round(zoom * (self.pos["x"] + camera[0] - ANCHOR_RADIUS)),
		        round(zoom * -(self.pos["y"] + camera[1] + ANCHOR_RADIUS)),
		        round(zoom * ANCHOR_RADIUS * 2),
		        round(zoom * ANCHOR_RADIUS * 2))
		pygame.draw.rect(display, color, rect)
		pygame.draw.rect(display, ANCHOR_BORDER, rect, max(1, round(rect[2] / 15)))

	@property
	def id(self) -> str:
		return self._dict["m_Guid"]
	@id.setter
	def id(self, value):
		self._dict["m_Guid"] = value


class TerrainStretch(LayoutObject):
	list_name = "m_TerrainStretches"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display, camera, zoom, color):
		if self.width == TERRAIN_MAIN_WIDTH:  # main terrain
			x = zoom * (self.pos["x"] - (0 if self.flipped else self.width) + camera[0])
		else:
			x = zoom * (self.pos["x"] - self.width / 2 * (-1 if self.flipped else 1) + camera[0])
		rect = (round(x), round(zoom * -(self.height + camera[1])), round(zoom * self.width), round(zoom * self.height))
		pygame.draw.rect(display, color, rect, scale(TERRAIN_BORDER_WIDTH, zoom))

	@property
	def flipped(self) -> bool:
		return self._dict["m_Flipped"]
	@flipped.setter
	def flipped(self, value):
		self._dict["m_Flipped"] = value

	@property
	def width(self):
		return TERRAIN_MAIN_WIDTH if self._dict["m_TerrainIslandType"] == 0 else TERRAIN_SMALL_WIDTH

	@property
	def height(self):
		return TERRAIN_BASE_HEIGHT + self.pos["y"]


class WaterBlock(LayoutObject):
	list_name = "m_WaterBlocks"

	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display, camera, zoom, color):
		start = (zoom * (self.pos["x"] - self.width/2 + camera[0]), zoom * -(self.height + camera[1]))
		end = (zoom * (self.pos["x"] + self.width/2 + camera[0]), zoom * -(self.height + camera[1]))
		pygame.draw.line(display, color, start, end, scale(WATER_EDGE_WIDTH, zoom))

	@property
	def width(self):
		return self._dict["m_Width"]
	@width.setter
	def width(self, value):
		self._dict["m_Width"] = value

	@property
	def height(self):
		return self._dict["m_Height"]
	@height.setter
	def height(self, value):
		self._dict["m_Height"] = value


class Pillar(SelectableObject):
	list_name = "m_Pillars"

	def __init__(self, dictionary):
		super().__init__(dictionary)
		self._surface = None

	def render(self, display, camera, zoom):
		rect = (round(zoom * (self.pos["x"] - PILLAR_WIDTH / 2 + camera[0])),
		        round(zoom * -(self.pos["y"] + self.height + camera[1])),
		        round(zoom * PILLAR_WIDTH),
		        round(zoom * self.height))
		if self._hitbox is None or self._hitbox.get_size() != display.get_size():
			print("Created pillar surface")
			self._surface = pygame.Surface(display.get_size(), pygame.SRCALPHA, 32)
			self._surface.set_alpha(PILLAR_COLOR[3])
		else:
			self._surface.fill(0)
		self._hitbox = pygame.mask.from_surface(self._surface, PILLAR_COLOR[3] - 1)
		pygame.draw.rect(self._surface, PILLAR_COLOR, rect)
		if not self.highlighted:
			pygame.draw.rect(self._surface, PILLAR_BORDER, rect, scale(PILLAR_BORDER_WIDTH, zoom))
		display.blit(self._surface, (0, 0))
		if self.highlighted:
			pygame.draw.rect(display, HIGHLIGHT_COLOR, rect, scale(SHAPE_HIGHLIGHTED_WIDTH, zoom, 60))

	@property
	def height(self):
		return self._dict["m_Height"]
	@height.setter
	def height(self, value):
		self._dict["m_Height"] = value

	def collidepoint(self, point, camera):
		return False


class CustomShape(SelectableObject):
	list_name = "m_CustomShapes"

	def __init__(self, dictionary):
		super().__init__(dictionary)
		self.selected_points = []
		self.point_hitboxes = []

	def render(self, display, camera, zoom, point_mode):
		# TODO: Move point editing logic to its own function
		base_points = self.points
		# Move point if a point is selected
		if self.selected_points:
			for i, point in enumerate(base_points):
				if self.selected_points[i]:
					newpoints = list(base_points)
					newpoints[i] = tuple(map(add, point, point_mode.mouse_change))
					base_points = tuple(newpoints)
					self.points = base_points
					break

		points_pixels = [[round(zoom * (self.pos["x"] + point[0] + camera[0])),
		                  round(zoom * -(self.pos["y"] + point[1] + camera[1]))]
		                 for point in base_points]

		if self._hitbox is None or zoom != self._hitbox_zoom or self._hitbox_moved:
			surface = pygame.Surface(display.get_size(), pygame.SRCALPHA, 32)
			rect = pygame.draw.polygon(surface, (0, 0, 0), points_pixels)
			self._hitbox = pygame.mask.from_surface(surface, 0)
			self._hitbox_camera = camera.copy()
			self._hitbox_zoom = zoom
			self._hitbox_moved = False
			print("Created polygon hitbox")

		pygame.gfxdraw.aapolygon(display, points_pixels, self.color)
		pygame.gfxdraw.filled_polygon(display, points_pixels, self.color)

		for pin in self.static_pins:
			rect = [round(zoom * (pin["x"] + camera[0])), round(zoom * -(pin["y"] + camera[1]))]
			pygame.gfxdraw.aacircle(display, rect[0], rect[1], round(zoom * PIN_RADIUS), STATIC_PIN_COLOR)
			pygame.gfxdraw.filled_circle(display, rect[0], rect[1], round(zoom * PIN_RADIUS), STATIC_PIN_COLOR)

		if self.highlighted:
			# TODO: Find an antialias solution
			pygame.draw.polygon(display, HIGHLIGHT_COLOR, points_pixels, scale(SHAPE_HIGHLIGHTED_WIDTH, zoom, 60))

		self.point_hitboxes = []
		if point_mode.draw_points:
			# Update center to actual center of rectangle
			if self.selected_points.count(1):
				_pos = deepcopy(self.pos)
				# TODO
				self.pos["x"] = self._hitbox.center[0] / zoom - camera[0]
				self.pos["y"] = -(self._hitbox.center[1] / zoom) - camera[1]
				self.points = tuple([(point[0] + _pos["x"] - self.pos["x"], point[1] + _pos["y"] - self.pos["y"])
				                     for point in self.points])
			# Render points
			for i, point in enumerate(points_pixels):
				rect = pygame.Rect(round(point[0] - zoom * POINT_RADIUS),
				                   round(point[1] - zoom * POINT_RADIUS),
				                   round(POINT_RADIUS),
				                   round(POINT_RADIUS))
				self.point_hitboxes.append(rect)
				if len(self.selected_points) < len(self.point_hitboxes):
					self.selected_points = [0 for _ in self.point_hitboxes]
				divisor = 1.7 if self.point_hitboxes[i].collidepoint(*point_mode.mouse_pos) else 2
				if self.selected_points[i]:
					pygame.gfxdraw.aacircle(
						display, point[0], point[1], round(zoom * PIN_RADIUS / divisor), HIGHLIGHT_COLOR)
					pygame.gfxdraw.filled_circle(
						display, point[0], point[1], round(zoom * PIN_RADIUS / divisor), HIGHLIGHT_COLOR)
				else:
					pygame.gfxdraw.aacircle(
						display, point[0], point[1], round(zoom * PIN_RADIUS / divisor), POINT_COLOR)
					pygame.gfxdraw.filled_circle(
						display, point[0], point[1], round(zoom * PIN_RADIUS / divisor), POINT_COLOR)

	@property
	def rotations(self):
		rot = self._dict["m_Rot"]
		return euler_angles(rot["x"], rot["y"], rot["z"], rot["w"])
	@rotations.setter
	def rotations(self, values):
		"""Does not automatically rotate pins and anchors"""
		q = quaternion(*values)
		self._dict["m_Rot"] = {"x": q[0], "y": q[1], "z": q[2], "w": q[3]}
		self._dict["m_RotationDegrees"] = values[2]

	@property
	def flipped(self) -> bool:
		return self._dict["m_Flipped"]
	@flipped.setter
	def flipped(self, value):
		"""Does not automatically flip pins and anchors"""
		self._dict["m_Flipped"] = value

	@property
	def scale(self):
		return self._dict["m_Scale"]
	@scale.setter
	def scale(self, value):
		self._dict["m_Scale"] = value

	@property
	def color(self):
		return tuple(v*255 for v in self._dict["m_Color"].values())
	@color.setter
	def color(self, value):
		self._dict["m_Color"] = {"r": value[0]/255, "g": value[1]/255, "b": value[2]/255, "a": value[3]/255}

	@property
	def points(self):
		pts = []
		for p in self._dict["m_PointsLocalSpace"]:
			point = (p["x"] * self.scale["x"], p["y"] * self.scale["y"])
			if self.flipped:
				point = (-point[0], point[1])
			point = rotate(point, self.rotations[2])
			pts.append(point)
		return tuple(pts)
	@points.setter
	def points(self, values):
		values = [rotate(p, -self.rotations[2]) for p in values]
		if self.flipped:
			values = [(-p[0], p[1]) for p in values]
		self._dict["m_PointsLocalSpace"] = [{"x": p[0] / self.scale["x"], "y": p[1] / self.scale["y"]} for p in values]

	@property
	def static_pins(self):
		return self._dict["m_StaticPins"]
	@static_pins.setter
	def static_pins(self, values):
		self._dict["m_StaticPins"] = values

	@property
	def dynamic_anchor_ids(self):
		return self._dict["m_DynamicAnchorGuids"]
	@dynamic_anchor_ids.setter
	def dynamic_anchor_ids(self, values):
		self._dict["m_DynamicAnchorGuids"] = values


class PointMode:
	"""Contains the relevant states while the editor is in custom shaoe point editing mode"""
	def __init__(self, draw_points, delete_points, add_points, mouse_pos, mouse_change):
		self.draw_points = draw_points
		self.delete_points = delete_points
		self.add_points = add_points
		self.mouse_pos = mouse_pos
		self.mouse_change = mouse_change
