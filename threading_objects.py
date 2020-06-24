# noinspection PyUnresolvedReferences
from threading import Thread
# noinspection PyUnresolvedReferences
from queue import Queue, Empty


class Event:
	"""An event characterized by a key and which can contain custom attributes"""
	def __init__(self, key, *args, **attributes):
		self.key = key
		self.attributes = attributes
		self.args = args

	def __getattr__(self, item: str):
		return self.attributes[item]

	def __getitem__(self, item: int):
		return self.args[item]

	def __eq__(self, other):
		return self.key == other

	def __ne__(self, other):
		return self.key != other


class SimpleQueue:
	"""A wrapper to two queues, in order to easily send events back and forth between threads"""
	def __init__(self, get_queue=Queue(), put_queue=Queue()):
		self.get_queue = get_queue
		self.put_queue = put_queue

	def get(self, block=False, timeout: float = None) -> Event:
		"""Remove and return an item from the queue. Will raise Empty if block is False and the queue is empty"""
		return self.get_queue.get(block, timeout)

	def put(self, key, *args, **attributes):
		"""Put an event into the queue"""
		self.put_queue.put(Event(key, *args, **attributes))

	def inverse(self) -> 'SimpleQueue':
		"""Returns a SimpleQueue with the current inner get and put queues but swapped"""
		return SimpleQueue(self.put_queue, self.get_queue)
