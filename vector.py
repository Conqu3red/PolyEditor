import math
from typing import *
from itertools import zip_longest

Number = Union[int, float]


def is_iterable(value):
	return hasattr(value, "__iter__")


def is_dict(value):
	return hasattr(value, "items")


class Vector(Tuple[Number, ...]):
	"""A tuple with useful element-wise operations as well as point operations"""

	_keys = ("x", "y", "z", "w")

	def __new__(cls, *values: Union[Number, Dict[Any, Number], Iterable[Number]]) -> 'Vector':
		"""Create a new vector from a series of values or an iterable"""
		if len(values) > 0 and is_iterable(values[0]):
			if len(values) > 1:
				raise TypeError("Unexpected parameters after iterable in constructor")
			if is_dict(values[0]):
				return cls.from_dict(values[0])
			return super().__new__(Vector, values[0])
		return super().__new__(Vector, values)

	@classmethod
	def from_dict(cls, d: Dict[str, Number]) -> 'Vector':
		"""Returns a new vector in the format [x, y(, z(, w))]"""
		return Vector(d[cls._keys[i]] for i in range(min(len(d), len(cls._keys))))

	def __getattr__(self, name: str) -> Number:
		"""x, y, z, w"""
		try:
			return self[self._keys.index(name)]
		except (ValueError, IndexError):
			pass
		raise AttributeError(f"Vector of size {self.size} has no attribute '{name}'")

	def __getitem__(self, index: Union[int, str, slice]) -> Union[Number, 'Vector']:
		try:
			return Vector(res) if is_iterable(res := super().__getitem__(index)) else res
		except TypeError:
			pass
		return self.__getattr__(index)

	def __add__(self, other: Sequence[Number]) -> 'Vector':
		"""Element-wise addition"""
		return Vector(a + b for a, b in zip_longest(self, other, fillvalue=0))

	__radd__ = __add__

	def __sub__(self, other: Sequence[Number]) -> 'Vector':
		"""Element-wise substraction"""
		return Vector(a - b for a, b in zip_longest(self, other, fillvalue=0))

	__rsub__ = __sub__

	def __mul__(self, other: Union[Number, Sequence[Number]]) -> 'Vector':
		"""Element-wise multiplication"""
		if is_iterable(other):
			return Vector(a * b for a, b in zip_longest(self, other, fillvalue=1))
		return Vector(a * other for a in self)

	__rmul__ = __mul__

	def __truediv__(self, other: Union[Number, Sequence[Number]]) -> 'Vector':
		"""Element-wise division"""
		if is_iterable(other):
			return Vector(a / b for a, b in zip_longest(self, other, fillvalue=1))
		return Vector(a / other for a in self)

	def __floordiv__(self, other: Union[Number, Sequence[Number]]) -> 'Vector':
		"""Element-wise floor division"""
		if is_iterable(other):
			return Vector(a // b for a, b in zip_longest(self, other, fillvalue=1))
		return Vector(a // other for a in self)

	def __mod__(self, other: Union[Number, Sequence[Number]]) -> 'Vector':
		"""Element-wise modulo"""
		if is_iterable(other):
			return Vector(a % b for a, b in zip_longest(self, other, fillvalue=1))
		return Vector(a % other for a in self)

	def __pow__(self, other: Union[Number, Sequence[Number]], mod=None) -> 'Vector':
		"""Element-wise exponentiation"""
		if is_iterable(other):
			return Vector(pow(a, b, mod) for a, b in zip_longest(self, other, fillvalue=1))
		return Vector(pow(a, other, mod) for a in self)

	def __matmul__(self, other):
		raise NotImplementedError("Cross product is left as an excercise for the reader :^)")

	__rmatmul__ = __matmul__

	@property
	def size(self):
		"""The number of items in this vector"""
		return len(self)

	def to_dict(self, base: Dict[str, Number] = None) -> Dict[str, Number]:
		"""Returns a dictionary in the format {x, y(, z(, w))}.
		If a base dictionary is provided, the values are written to it instead of a new dictionary"""
		base = base if base else {}
		for i in range(min(self.size, len(self._keys))):
			base[self._keys[i]] = self[i]
		return base

	def round(self) -> 'Vector':
		"""Returns a new vector with all values rounded to integers"""
		return Vector(round(a) for a in self)

	def flip_x(self, origin: Sequence[Number] = (0, 0), only_if=True):
		"""Returns a new vector with the y coordinate inverted"""
		return Vector(2 * origin[0] - self[0], self[1]) if only_if else self

	def flip_y(self, origin: Sequence[Number] = (0, 0), only_if=True):
		"""Returns a new vector with the y coordinate inverted"""
		return Vector(self[0], 2 * origin[1] - self[1]) if only_if else self

	def rotate(self, angle: float, origin: Sequence[Number] = (0, 0), deg=True) -> 'Vector':
		"""Rotate this point by a given angle counterclockwise in the Z axis"""
		if deg:
			angle = math.radians(angle)
		px, py = self[0] - origin[0], self[1] - origin[1]
		x = math.cos(angle) * px - math.sin(angle) * py + origin[0]
		y = math.sin(angle) * px + math.cos(angle) * py + origin[1]
		return Vector(x, y) if self.size == 2 else Vector(x, y, self[2])

	def flip(self, point: Sequence[Number], angle: float, deg=True):
		"""Flip this point along an axis defined by a point and an angle"""
		return self.rotate(-angle, point, deg).flip_x(point).rotate(angle, point, deg)

	def quaternion(self, deg=True) -> 'Vector':
		"""Returns a new quaternion (x, y, z, w) from these euler angles (x, y, z)
		https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles"""
		x = math.radians(self[0]) if deg else self[0]
		y = math.radians(self[1]) if deg else self[1]
		z = math.radians(self[2]) if deg else self[2]

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
		return Vector(qx, qy, qz, qw)

	def euler_angles(self, deg=True) -> 'Vector':
		"""Returns new euler angles (x, y, z) from this quaternion (x, y, z, w)
		https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles"""
		qx, qy, qz, qw = self
		sx_cy = 2 * (qw * qx + qy * qz)
		cx_cy = 1 - 2 * (qx ** 2 + qy ** 1)
		x = math.atan2(sx_cy, cx_cy)

		sy = 2 * (qw * qy - qz * qx)
		y = math.asin(sy) if -1 < sy < 1 else math.copysign(math.pi / 2, sy)

		sz_cy = 2 * (qw * qz + qx * qy)
		cz_cy = 1 - 2 * (qy ** 2 + qz ** 2)
		z = math.atan2(sz_cy, cz_cy)

		if deg:
			x = math.degrees(x)
			y = math.degrees(y)
			z = math.degrees(z)
		return Vector(x, y, z)

	def closest_point(self, l1: 'Vector', l2: 'Vector') -> Optional['Vector']:
		"""Finds the closest point in a line defined by l1 and l2"""
		try:
			s1 = (l2[1] - l1[1]) / (l2[0] - l1[0])
			s2 = -1 / s1
			a1 = (l1[1] - l1[0] * s1)
			a2 = (self[1] - self[0] * s2)
			x = -(a2 - a1) / (s2 - s1)
			return Vector(x, s1 * x + a1) if l1[0] <= x <= l2[0] or l2[0] <= x <= l1[0] else None
		except ZeroDivisionError:
			if l2[0] - l1[0] == 0:  # Vertical line
				return Vector(l1[0], self[1]) if l1[1] <= self[1] <= l2[1] or l2[1] <= self[1] <= l1[1] else None
			else:  # Horizontal Line
				return Vector(self[0], l1[1]) if l1[0] <= self[0] <= l2[0] or l2[0] <= self[0] <= l1[0] else None
