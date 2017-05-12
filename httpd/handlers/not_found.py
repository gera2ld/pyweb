from .base import BaseHandler, based_on_fs

__all__ = ['NotFoundHandler']

class NotFoundHandler(BaseHandler):
    async def handle(self):
        self.parent.send_error(404)
        return True
