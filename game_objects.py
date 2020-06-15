import pygame
import math
from squaternion import Quaternion


def centroid(vertexes):
	_x_list = [vertex[0] for vertex in vertexes]
	_y_list = [vertex[1] for vertex in vertexes]
	_len = len(vertexes)
	_x = sum(_x_list) / _len
	_y = sum(_y_list) / _len
	return [_x, _y]


def rotate(origin, point, angle):
	"""Rotate a point counterclockwise by a given angle around a given origin.
	The angle should be given in degrees.
	"""
	angle = math.radians(angle)

	ox, oy = origin
	px, py = point

	qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
	qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
	return [qx, qy]


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
		pins = [[int(zoom * (pin["x"] + camera[0]) - zoom / 8),
		         int(zoom * -(pin["y"] + camera[0]) - zoom / 8)]
		        for pin in self.static_pins]
		for pin in pins:
			pygame.draw.ellipse(display, (165, 42, 42), (pin[0], pin[1], int(zoom / 4), int(zoom / 4)))
		# Draw dynamic anchors
		for anchor_id in self.dynamic_anchors:
			for anchor in anchors:
				if anchor_id == anchor["m_Guid"]:
					# print(anchor)
					# print((anchor["m_Pos"]["x"]+camera[0])*zoom,(anchor["m_Pos"]["y"]+camera[1])*zoom)
					rect = (int((anchor["m_Pos"]["x"] + camera[0]) * zoom - zoom / 8),
							int(-(anchor["m_Pos"]["y"] + camera[1]) * zoom - zoom / 8),
							int(zoom / 4),
							int(zoom / 4))
					pygame.draw.rect(display, (255, 255, 255), rect)
		if draw_hitbox:
			pygame.draw.rect(display, (0, 255, 0), self.hitbox, 1)
		if self.highlighted:
			pygame.draw.polygon(display, (255, 255, 0), points_pixels, 1)
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
		return Quaternion(rot["w"], rot["x"], rot["y"], rot["z"]).to_euler(degrees=True)
	@rotation.setter
	def rotation(self, value):
		q = Quaternion.from_euler(*value, degrees=True)
		self._dict["m_Rot"] = {"x": q[1], "y": q[2], "z": q[3], "w": q[0]}
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
		return self._dict["m_StaticPins"]
	@dynamic_anchors.setter
	def dynamic_anchors(self, values):
		self._dict["m_DynamicAnchorGuids"] = values