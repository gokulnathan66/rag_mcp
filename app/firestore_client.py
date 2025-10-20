# Firestore client stub (async)


class FirestoreClient:
    def __init__(self, project_id: str = None, credentials_path: str = None):
        self.project_id = project_id
        self.credentials_path = credentials_path

    async def list_documents(self, collection_name: str, filters: dict = None):
        # Return an empty iterator for now
        return []

    async def get_document(self, doc_path: str):
        return None

    async def watch_collection(self, collection_name: str, callback):
        # Placeholder for setting up real-time listeners
        pass
