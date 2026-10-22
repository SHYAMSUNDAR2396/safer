class Problem(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail
