"""Bounded PANS startup recovery. Never infer distance from a shell response."""
class UwbStartup:
    def __init__(self, now):
        self.started = now
        self.phase = 'observe'
        self.deadline = now + 3.0
        self.tail = b''
        self.saw_data = False
        self.saw_dist = False
        self.prompt = False

    def feed(self, data):
        if not data:
            return
        self.saw_data = True
        self.tail = (self.tail + data)[-8192:]
        if b'DIST,' in self.tail:
            self.saw_dist = True
        if b'dwm>' in self.tail:
            self.prompt = True

    def action(self, now):
        if self.saw_dist:
            self.phase = 'done'
        if self.phase == 'done' or now < self.deadline:
            return None
        if self.phase == 'observe':
            if self.prompt:
                self.phase = 'done'
                return b'lec\r'
            if self.saw_data:
                self.phase = 'done'  # Unrecognized output: do not blindly toggle.
                return None
            self.phase = 'shell'
            self.deadline = now + 3.0
            return b'\r\r'
        if self.phase == 'shell':
            self.phase = 'done'
            if self.prompt:
                return b'lec\r'
        return None
