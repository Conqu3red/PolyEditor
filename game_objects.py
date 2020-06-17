import pygame
import math

HIGHLIGHT_COLOR = (255, 255, 0)
HITBOX_COLOR = (0, 255, 0)
SHAPE_HIGHLIGHTED_WIDTH = 2

ANCHOR_RADIUS = 0.16
ANCHOR_COLOR = (235, 0, 50)
ANCHOR_BORDER = (0, 0, 0)
DYNAMIC_ANCHOR_COLOR = (222, 168, 62)

PIN_RADIUS = 0.125
STATIC_PIN_COLOR = (0, 0, 0)
STATIC_PIN_BORDER = (50, 50, 50)

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


def rotate(point, angle, deg=True):
	"""Rotate a point by a given angle counterclockwise around (0,0)"""
	if deg:
		angle = math.radians(angle)
	px, py = point
	x = math.cos(angle) * px - math.sin(angle) * py
	y = math.sin(angle) * px + math.cos(angle) * py
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


class LayoutList:
	"""Acts a wrapper for a list of dictionaries in the layout, allowing you to treat them as objects."""

	def __init__(self, cls, layout):
		if not issubclass(cls, LayoutObject): raise TypeError()
		self._dictlist = layout[cls.list_name]
		self._objlist = [cls(o) for o in self._dictlist]

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
	
	def __len__(self):
		return self._objlist.__len__()

	def __getitem__(self, item):
		return self._objlist.__getitem__(item)


class Anchor(LayoutObject):
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
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		self._dict["m_Pos"] = value

	@property
	def id(self) -> str:
		return self._dict["m_Guid"]
	@id.setter
	def id(self, value):
		self._dict["m_Guid"] = value


class TerrainStretch(LayoutObject):
	def __init__(self, dictionary):
		super().__init__(dictionary)

	def render(self, display, camera, zoom, color):
		if self.width == TERRAIN_MAIN_WIDTH:  # main terrain
			x = zoom * (self.pos["x"] - (0 if self.flipped else self.width) + camera[0])
		else:
			x = zoom * (self.pos["x"] - self.width / 2 * (-1 if self.flipped else 1) + camera[0])
		rect = (round(x), round(zoom * -(self.height + camera[1])), round(zoom * self.width), round(zoom * self.height))
		pygame.draw.rect(display, color, rect, TERRAIN_BORDER_WIDTH)

	@property
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		self._dict["m_Pos"] = value

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
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		self._dict["m_Pos"] = value

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
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		self._dict["m_Pos"] = value

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
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		self._dict["m_Pos"] = value

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


class Pillar(LayoutObject):
	list_name = "m_Pillars"

	def __init__(self, dictionary):
		super().__init__(dictionary)
		self.highlighted = False
		self.hitbox = None

	def render(self, display, camera, zoom):
		rect = (round(zoom * (self.pos["x"] - PILLAR_WIDTH / 2 + camera[0])),
				round(zoom * -(self.pos["y"] + self.height + camera[1])),
				round(zoom * PILLAR_WIDTH),
				round(zoom * self.height))
		self.hitbox = pygame.Rect(rect)
		surf = pygame.Surface((rect[2], rect[3]))
		surf.fill(PILLAR_COLOR)
		surf.set_alpha(PILLAR_COLOR[3])
		if not self.highlighted:
			pygame.draw.rect(surf, PILLAR_BORDER, (0, 0, rect[2], rect[3]), scale(PILLAR_BORDER_WIDTH, zoom))
		display.blit(surf, (rect[0], rect[1]))
		if self.highlighted:
			pygame.draw.rect(display, HIGHLIGHT_COLOR, rect, scale(SHAPE_HIGHLIGHTED_WIDTH, zoom))

	@property
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		self._dict["m_Pos"] = value

	@property
	def height(self):
		return self._dict["m_Height"]
	@height.setter
	def height(self, value):
		self._dict["m_Height"] = value


class CustomShape(LayoutObject):
	list_name = "m_CustomShapes"

	def __init__(self, dictionary):
		super().__init__(dictionary)
		self.highlighted = False
		self.hitbox = None

	def render(self, display, camera, zoom, draw_hitbox, border_color):
		# Add base position and adjust for the camera position
		points_pixels = [[round(zoom * (self.pos["x"] + point[0] + camera[0])),
		                  round(zoom * -(self.pos["y"] + point[1] + camera[1]))]
		                 for point in self.points]

		self.hitbox = pygame.draw.polygon(display, self.color, points_pixels)

		# Draw static pins
		for pin in self.static_pins:
			rect = (round(zoom * (pin["x"] + camera[0] - PIN_RADIUS)),
			        round(zoom * -(pin["y"] + camera[1] + PIN_RADIUS)),
			        round(zoom * PIN_RADIUS * 2),
			        round(zoom * PIN_RADIUS * 2))
			pygame.draw.ellipse(display, STATIC_PIN_COLOR, rect)
		if draw_hitbox:
			pygame.draw.rect(display, HITBOX_COLOR, self.hitbox, 1)
		if self.highlighted:
			pygame.draw.polygon(display, HIGHLIGHT_COLOR, points_pixels, scale(SHAPE_HIGHLIGHTED_WIDTH, zoom))

	@property
	def pos(self):
		return self._dict["m_Pos"]
	@pos.setter
	def pos(self, value):
		self._dict["m_Pos"] = value

	@property
	def rotations(self):
		rot = self._dict["m_Rot"]
		return euler_angles(rot["x"], rot["y"], rot["z"], rot["w"])
	@rotations.setter
	def rotations(self, values):
		q = quaternion(*values)
		self._dict["m_Rot"] = {"x": q[0], "y": q[1], "z": q[2], "w": q[3]}
		self._dict["m_RotationDegrees"] = values[2]

	@property
	def flipped(self) -> bool:
		return self._dict["m_Flipped"]
	@flipped.setter
	def flipped(self, value):
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
		list = []
		for p in self._dict["m_PointsLocalSpace"]:
			point = (p["x"] * self.scale["x"], p["y"] * self.scale["y"])
			if self.flipped:
				point = (-point[0], point[1])
			point = rotate(point, self.rotations[2])
			list.append(point)
		return tuple(list)
	@points.setter
	def points(self, values):
		values = [rotate(p, -self.rotations[2]) for p in values]
		if self.flipped:
			values = [(-p[0], p[1]) for p in values]
		self._dict["m_PointsLocalSpace"] = [{"x": p[0], "y": p[1]} for p in values]

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
