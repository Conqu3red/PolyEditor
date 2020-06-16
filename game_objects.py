import pygame
import math

DYNAMIC_ANCHOR_COLOR = (222, 168, 62)
DYNAMIC_ANCHOR_BORDER = (0, 0, 0)
ANCHOR_SIZE = 0.15
STATIC_PIN_COLOR = (0, 0, 0)
STATIC_PIN_BORDER = (50, 50, 50)
PIN_SIZE = 0.12


def centroid(points):
	count = len(points)
	x = sum(p[0] for p in points) / count
	y = sum(p[1] for p in points) / count
	return x, y


def rotate(origin, point, angle, deg=True):
	"""Rotate a point by a given angle counterclockwise around a given origin"""
	if deg:
		angle = math.radians(angle)
	ox, oy = origin
	px, py = point
	x = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
	y = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
	return x, y


def quaternion(x, y, z, deg=True):
	"""Converts euler anglesto a quaternion
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

	def __init__(self, dictionary):
		self._dict = dictionary

	@property
	def dictionary(self):
		return self._dict


class LayoutList:
	"""Acts a wrapper for the list of dictionaries that represent a list of objects in the layout."""

	def __init__(self, cls, objects):
		if not issubclass(cls, LayoutObject): raise TypeError()
		self._dictlist = objects
		self._objlist = [cls(o) for o in objects]

	def append(self, elem):
		self._dictlist.append(elem.dictionary)
		self._objlist.append(elem)

	def extend(self, elems):
		self._dictlist.extend([e.dictionary for e in elems])
		self._objlist.extend(elems)

	def remove(self, elem):
		self._dictlist.remove(elem.dictionary)
		self._objlist.remove(elem)

	def __iter__(self):
		return self._objlist.__iter__()


class CustomShape(LayoutObject):
	def __init__(self, dictionary):
		super().__init__(dictionary)
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
		for pin in self.static_pins:
			rect = (round(zoom * (pin["x"] + camera[0] - PIN_SIZE)),
			        round(zoom * -(pin["y"] + camera[1] + PIN_SIZE)),
			        round(zoom * PIN_SIZE * 2),
			        round(zoom * PIN_SIZE * 2))
			pygame.draw.ellipse(display, STATIC_PIN_COLOR, rect)
		# Draw dynamic anchors
		for anchor_id in self.dynamic_anchors:
			for anchor in anchors:
				if anchor_id == anchor["m_Guid"]:
					rect = (round(zoom * (anchor["m_Pos"]["x"] + camera[0] - ANCHOR_SIZE)),
					        round(zoom * -(anchor["m_Pos"]["y"] + camera[1] + ANCHOR_SIZE)),
					        round(zoom * ANCHOR_SIZE * 2),
					        round(zoom * ANCHOR_SIZE * 2))
					pygame.draw.rect(display, DYNAMIC_ANCHOR_COLOR, rect)
					pygame.draw.rect(display, DYNAMIC_ANCHOR_BORDER, rect, max(1, round(rect[2] / 15)))
		if draw_hitbox:
			pygame.draw.rect(display, (0, 255, 0), self.hitbox, 1)
		if self.highlighted:
			pygame.draw.polygon(display, (255, 255, 0), points_pixels, 2)
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
		return euler_angles(rot["x"], rot["y"], rot["z"], rot["w"])
	@rotation.setter
	def rotation(self, value):
		q = quaternion(*value)
		self._dict["m_Rot"] = {"x": q[0], "y": q[1], "z": q[2], "w": q[3]}
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
		return self._dict["m_DynamicAnchorGuids"]
	@dynamic_anchors.setter
	def dynamic_anchors(self, values):
		self._dict["m_DynamicAnchorGuids"] = values