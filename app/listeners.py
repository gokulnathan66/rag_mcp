# Firestore listeners stub


class FirestoreListener:
    def __init__(self, firestore_client, orchestrator):
        self.firestore_client = firestore_client
        self.orchestrator = orchestrator

    async def on_document_created(self, doc_snapshot):
        await self.orchestrator.ingest_collection(doc_snapshot.collection_path)

    async def on_document_updated(self, doc_snapshot, changes):
        await self.orchestrator.ingest_collection(doc_snapshot.collection_path)

    async def on_document_deleted(self, doc_id):
        # would call qdrant delete
        pass
