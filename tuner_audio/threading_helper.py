from threading import Lock


class ProtectedList:
    """ Simple queue to share data between Threads with lock protection.
        Standard buffer length is only 8! """

    def __init__(self, buffer_size=8):
        self.elements = []
        self.buffer_size = buffer_size
        self.lock = Lock()

    def put(self, element):
        with self.lock:
            self.elements.append(element)
            if len(self.elements) > self.buffer_size:
                self.elements.pop(0)

    def get(self):
        with self.lock:
            if self.elements:
                return self.elements.pop(0)
            return None

    def __repr__(self):
        with self.lock:
            return str(self.elements)
