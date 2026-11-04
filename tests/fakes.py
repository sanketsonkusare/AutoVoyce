"""In-memory stand-ins for external services, shared by tests."""


class FakeIndex:
    """Mimics the parts of a Pinecone integrated-inference index we use."""

    def __init__(self):
        self.records: dict[str, list[dict]] = {}
        self.search_calls: list[dict] = []
        self.upsert_calls: list[dict] = []
        self.fail_rerank = False
        self.fail_search = False

    def upsert_records(self, namespace, records):
        self.upsert_calls.append({"namespace": namespace, "count": len(records)})
        stored = self.records.setdefault(namespace, [])
        by_id = {r["_id"]: i for i, r in enumerate(stored)}
        for record in records:
            if record["_id"] in by_id:
                stored[by_id[record["_id"]]] = dict(record)
            else:
                stored.append(dict(record))

    def search(self, namespace, query, fields=None, rerank=None):
        self.search_calls.append(
            {"namespace": namespace, "query": query, "fields": fields, "rerank": rerank}
        )
        if self.fail_search:
            raise RuntimeError("search failed")
        if rerank is not None and self.fail_rerank:
            raise RuntimeError("rerank quota exceeded")
        words = set(query["inputs"]["text"].lower().split())
        records = self.records.get(namespace, [])
        ranked = sorted(
            records,
            key=lambda r: -len(words & set(r.get("chunk_text", "").lower().split())),
        )[: query["top_k"]]
        if rerank is not None:
            ranked = ranked[: rerank["top_n"]]
        hits = [
            {"_id": r["_id"], "fields": {f: r[f] for f in (fields or []) if f in r}}
            for r in ranked
        ]
        return {"result": {"hits": hits}}

    def describe_index_stats(self):
        return {"namespaces": {ns: {"vector_count": len(v)} for ns, v in self.records.items()}}

    def delete_namespace(self, namespace):
        self.records.pop(namespace, None)


from typing import Any  # noqa: E402

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, AIMessageChunk  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult  # noqa: E402


class FakeChatModel(BaseChatModel):
    """Streams the given chunks; raises after `fail_after` chunks if set."""

    chunks: list[Any] = []
    fail_after: int | None = None
    calls: list[list] = []

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        text = "".join(c if isinstance(c, str) else c[0]["text"] for c in self.chunks)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(list(messages))
        for i, chunk in enumerate(self.chunks):
            if self.fail_after is not None and i >= self.fail_after:
                raise RuntimeError("model failed")
            yield ChatGenerationChunk(message=AIMessageChunk(content=chunk))
