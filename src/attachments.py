import asyncio
import json
from pathlib import Path
from typing import Annotated

from chainlit.auth import get_current_user
from chainlit.data.storage_clients.base import BaseStorageClient
from chainlit.user import User
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse

PREFIX = "/attachments"


class AttachmentStore(BaseStorageClient):
    """Keeps Attachments on local disk for Chainlit's data layer and serves them back."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.router = APIRouter()
        self.router.add_api_route(PREFIX + "/{object_key:path}", self._serve)

    def mount(self, app: FastAPI) -> None:
        app.include_router(self.router)
        # Chainlit's catch-all UI route is already registered and would answer first.
        app.router.routes.insert(0, app.router.routes.pop())

    async def upload_file(
        self,
        object_key: str,
        data: bytes | str,
        mime: str = "application/octet-stream",
        overwrite: bool = True,  # Chainlit always overwrites; ignored.
        content_disposition: str | None = None,
    ) -> dict:
        path = self._path(object_key)
        content = data.encode() if isinstance(data, str) else data
        # Only the filename is kept: whether it opens inline depends on the mime type.
        _, _, filename = (content_disposition or "").partition(";")
        meta = {"mime": mime, "filename": filename.strip()}
        await asyncio.to_thread(write, path, content, meta)
        return {"object_key": object_key, "url": await self.get_read_url(object_key)}

    async def delete_file(self, object_key: str) -> bool:
        return await asyncio.to_thread(delete, self._path(object_key), self.root)

    async def get_read_url(self, object_key: str) -> str:
        return f"{PREFIX}/{object_key}"

    async def close(self) -> None:
        pass

    def _path(self, object_key: str) -> Path:
        path = (self.root / object_key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(
                f"Object key outside the attachments directory: {object_key}"
            )
        return path

    async def _serve(
        self, object_key: str, user: Annotated[User | None, Depends(get_current_user)]
    ) -> FileResponse:
        # Chainlit returns no user when login is off; Attachments always need one.
        if user is None:
            raise HTTPException(status_code=401)
        try:
            path = self._path(object_key)
            meta = await asyncio.to_thread(read_meta, path)
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404) from None
        # A PDF is more useful opened in the browser; anything else downloads.
        kind = "inline" if meta["mime"] == "application/pdf" else "attachment"
        disposition = "; ".join(filter(None, [kind, meta["filename"]]))
        return FileResponse(
            path,
            media_type=meta["mime"],
            headers={"Content-Disposition": disposition},
        )


def meta_path(path: Path) -> Path:
    return path.with_name(path.name + ".json")


def read_meta(path: Path) -> dict:
    # Both files must exist, so a key naming a metadata file isn't an Attachment.
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(meta_path(path).read_text())


def write(path: Path, content: bytes, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    meta_path(path).write_text(json.dumps(meta))


def delete(path: Path, root: Path) -> bool:
    meta_path(path).unlink(missing_ok=True)
    if not path.is_file():
        return False
    path.unlink()
    # Drop the Thread's directories once they're empty, but never the root itself.
    for parent in path.parents:
        if parent == root or any(parent.iterdir()):
            break
        parent.rmdir()
    return True
