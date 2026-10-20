"""Сквозные сценарии: загрузка → обработка → поиск, и права на коллекции."""

import asyncio
import io
import uuid
from collections.abc import Awaitable, Callable

import httpx
import pytest
from PIL import Image, ImageDraw

from .conftest import Login

pytestmark = pytest.mark.integration


def _image() -> bytes:
    """Уникальная картинка: случайные цветные фигуры."""

    rng = uuid.uuid4().bytes
    image = Image.new("RGB", (800, 600), (rng[0], rng[1], rng[2]))
    draw = ImageDraw.Draw(image)
    for index in range(0, 12, 3):
        x, y = rng[index] * 3, rng[index + 1] * 2
        draw.ellipse((x, y, x + 200, y + 150), fill=(rng[index + 2], 255 - rng[index], 128))

    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


async def _wait(check: Callable[[], Awaitable[bool]], *, timeout: float = 180) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not await check():
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError("Background processing did not finish in time.")
        await asyncio.sleep(2)


async def _upload(api: httpx.AsyncClient, collection_id: str, content: bytes, title: str) -> dict:
    ticket = (
        await api.post(
            "/uploads",
            json={
                "collectionId": collection_id,
                "filename": "photo.jpg",
                "contentType": "image/jpeg",
                "size": len(content),
            },
        )
    ).raise_for_status().json()

    async with httpx.AsyncClient() as storage:
        (await storage.put(ticket["url"], content=content, headers=ticket["headers"])).raise_for_status()

    return (
        await api.post(f"/uploads/{ticket['uploadId']}/complete", json={"title": title})
    ).raise_for_status().json()


async def test_upload_processing_and_search(login: Login) -> None:
    api = await login("ivanov")
    collection = (await api.post("/collections", json={"name": f"Тест {uuid.uuid4()}"})).raise_for_status().json()
    content = _image()
    marker = uuid.uuid4().hex[:8]

    asset = await _upload(api, collection["id"], content, f"Ракурс изделия {marker}")
    assert asset["version"]["status"] == "processing"
    assert asset["kind"] == "image"

    # Повторное подтверждение идемпотентно
    again = (await api.post(f"/uploads/{asset['version']['id']}/complete", json={})).raise_for_status().json()
    assert again["id"] == asset["id"]

    async def processed() -> bool:
        current = (await api.get(f"/assets/{asset['id']}")).raise_for_status().json()
        return current["version"]["status"] == "ready"

    await _wait(processed)
    current = (await api.get(f"/assets/{asset['id']}")).raise_for_status().json()
    assert current["version"]["meta"]["width"] == 800

    async with httpx.AsyncClient() as cdn:
        thumbnail = await cdn.get(current["version"]["urls"]["thumbnail"])
        assert thumbnail.status_code == 200
        assert thumbnail.headers["content-type"] == "image/webp"

    async def found_by_image() -> bool:
        response = await api.post(
            "/search/by-image",
            files={"image": ("query.jpg", content, "image/jpeg")},
            data={"collectionIds": collection["id"]},
        )
        items = response.raise_for_status().json()["items"]
        return bool(items) and items[0]["asset"]["id"] == asset["id"]

    await _wait(found_by_image)

    found = (await api.post("/search", json={"query": marker})).raise_for_status().json()
    assert asset["id"] in [item["asset"]["id"] for item in found["items"]]

    (await api.post(f"/assets/{asset['id']}/trash")).raise_for_status()
    (await api.delete(f"/assets/{asset['id']}")).raise_for_status()
    (await api.delete(f"/collections/{collection['id']}")).raise_for_status()


async def test_collection_access_is_defined_by_backend(login: Login) -> None:
    owner, colleague = await login("ivanov"), await login("petrova")
    me = (await colleague.get("/me")).raise_for_status().json()
    collection = (
        await owner.post("/collections", json={"name": f"Закрытая {uuid.uuid4()}", "visibility": "private"})
    ).raise_for_status().json()

    assert (await colleague.get(f"/collections/{collection['id']}")).status_code == 404

    (
        await owner.put(f"/collections/{collection['id']}/members", json={"userId": me["id"], "role": "viewer"})
    ).raise_for_status()

    visible = (await colleague.get(f"/collections/{collection['id']}")).raise_for_status().json()
    assert visible["permissions"] == ["read"]

    upload = await colleague.post(
        "/uploads",
        json={"collectionId": collection["id"], "filename": "a.jpg", "contentType": "image/jpeg", "size": 10},
    )
    assert upload.status_code == 403

    (await owner.delete(f"/collections/{collection['id']}")).raise_for_status()
