from collections import defaultdict


class MemoryStore:
    def __init__(self):
        self._documents = defaultdict(list)

    async def list_documents(self, thread_id):
        return list(self._documents[thread_id])
