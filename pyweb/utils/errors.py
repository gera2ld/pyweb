class HTTPError(Exception):
    def __init__(self, status_code, long_msg='Error occurred!'):
        super().__init__()
        self.status_code = status_code
        self.long_msg = long_msg

class HeadersSentError(Exception): pass
