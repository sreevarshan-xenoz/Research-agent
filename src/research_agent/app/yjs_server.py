"""
Yjs CRDT WebSocket server for collaborative real-time editing.

Handles the Yjs sync protocol (step1/step2) and awareness protocol
using the y-py Python bindings to the Rust Yrs CRDT implementation.

Supports:
- Per-document rooms with in-memory YDoc instances
- Sync protocol: receive SyncStep1 → respond with SyncStep2
- Update broadcasting to all connected clients in a room
- Awareness protocol for cursor presence
- File-system persistence for document recovery
- Room lifecycle management
"""

from __future__ import annotations

import asyncio
import logging
import os
import struct
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from y_py import YDoc, apply_update, encode_state_as_update, encode_state_vector
except ImportError:
    YDoc = None
    apply_update = None
    encode_state_as_update = None
    encode_state_vector = None

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
MESSAGE_SYNC = 0
MESSAGE_AWARENESS = 1
SYNC_STEP1 = 0
SYNC_STEP2 = 1
SYNC_UPDATE = 2

DEFAULT_PERSIST_DIR = Path("data/yjs_docs")


@dataclass
class RoomState:
    """State for a collaborative editing room (one per document)."""
    ydoc: Any  # YDoc instance (or None if y-py unavailable)
    clients: dict[WebSocket, dict[str, Any]] = field(default_factory=dict)
    last_activity: float = field(default_factory=time.time)

    @property
    def client_count(self) -> int:
        return len(self.clients)


class YjsServerManager:
    """Manages Yjs document rooms and WebSocket connections.

    Each document room has:
    - A YDoc (CRDT document)
    - Multiple connected clients
    - File-system persistence
    - Awareness state for cursor presence
    """

    def __init__(self, persist_dir: str | Path | None = None) -> None:
        self.persist_dir = Path(persist_dir) if persist_dir else DEFAULT_PERSIST_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.rooms: dict[str, RoomState] = {}
        self._yjs_available = all([
            YDoc is not None,
            apply_update is not None,
            encode_state_as_update is not None,
            encode_state_vector is not None,
        ])
        if not self._yjs_available:
            logger.warning("y-py not available — collaborative editing will use basic relay mode")

    def _get_doc_path(self, doc_name: str) -> Path:
        """Get the persistence file path for a document."""
        safe = doc_name.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self.persist_dir / f"{safe}.yjs"

    def _load_doc_from_disk(self, doc_name: str, ydoc: Any) -> None:
        """Load persisted updates into a YDoc."""
        doc_path = self._get_doc_path(doc_name)
        if not doc_path.exists():
            return
        try:
            data = doc_path.read_bytes()
            offset = 0
            while offset < len(data):
                chunk_len = struct.unpack("!I", data[offset:offset + 4])[0]
                offset += 4
                if offset + chunk_len > len(data):
                    break
                chunk = data[offset:offset + chunk_len]
                offset += chunk_len
                apply_update(ydoc, chunk)
            logger.info("Loaded doc %s: %d bytes", doc_name, len(data))
        except Exception as exc:
            logger.warning("Failed to load doc %s: %s", doc_name, exc)

    def _persist_update(self, doc_name: str, update: bytes) -> None:
        """Append a binary update to the persist file."""
        try:
            doc_path = self._get_doc_path(doc_name)
            with open(doc_path, "ab") as f:
                f.write(struct.pack("!I", len(update)))
                f.write(update)
        except Exception as exc:
            logger.warning("Failed to persist update for %s: %s", doc_name, exc)

    def get_or_create_room(self, doc_name: str) -> RoomState:
        """Get or create a collaborative editing room for a document."""
        if doc_name not in self.rooms:
            ydoc = YDoc() if self._yjs_available else None
            if self._yjs_available:
                self._load_doc_from_disk(doc_name, ydoc)
                # Auto-save on every update
                # observe_updates may not exist in all y_py versions
                try:
                    ydoc.observe_updates(lambda upd: self._persist_update(doc_name, upd))
                except AttributeError:
                    logger.warning("y_py YDoc does not support observe_updates; auto-persistence disabled")
            self.rooms[doc_name] = RoomState(ydoc=ydoc)
            logger.info("Created room: %s", doc_name)
        return self.rooms[doc_name]

    def remove_empty_rooms(self, older_than_seconds: float = 3600) -> int:
        """Clean up rooms with no clients and no recent activity."""
        now = time.time()
        to_remove = [
            name for name, room in self.rooms.items()
            if not room.clients and now - room.last_activity > older_than_seconds
        ]
        for name in to_remove:
            del self.rooms[name]
        if to_remove:
            logger.info("Cleaned up %d inactive rooms", len(to_remove))
        return len(to_remove)

    # ── WebSocket Handler ─────────────────────────────────────

    async def handle_websocket(self, ws: WebSocket, doc_name: str) -> None:
        """Handle a WebSocket connection for collaborative editing.

        Implements the Yjs sync protocol:
        - Message type 0 (SYNC): SyncStep1, SyncStep2, or Update
        - Message type 1 (AWARENESS): Cursor presence data
        """
        await ws.accept()
        room = self.get_or_create_room(doc_name)
        room.clients[ws] = {"connected_at": time.time()}
        room.last_activity = time.time()

        logger.info(
            "Client connected to room '%s' (%d clients)",
            doc_name, room.client_count,
        )

        try:
            if self._yjs_available and room.ydoc is not None:
                # Send SyncStep1 (state vector) to new client so it can compute diff
                sv = encode_state_vector(room.ydoc)
                sync_msg = self._build_sync_message(SYNC_STEP1, sv)
                await ws.send_bytes(sync_msg)

            while True:
                data = await ws.receive_bytes()
                room.last_activity = time.time()

                if not data:
                    continue

                message_type = data[0]

                if message_type == MESSAGE_SYNC:
                    await self._handle_sync_message(ws, room, doc_name, data)
                elif message_type == MESSAGE_AWARENESS:
                    await self._broadcast_awareness(ws, room, data)
                else:
                    logger.debug("Unknown message type: %d", message_type)

        except WebSocketDisconnect:
            logger.info("Client disconnected from room '%s'", doc_name)
        except Exception as exc:
            logger.warning("WebSocket error in room '%s': %s", doc_name, exc)
        finally:
            room.clients.pop(ws, None)
            if not room.clients:
                # Schedule cleanup after 5 minutes of inactivity
                room.last_activity = time.time()

    def _build_sync_message(self, substep: int, data: bytes) -> bytes:
        """Build a Yjs sync protocol message.

        Format: [message_type(1)][substep(1)][data(N)]
        """
        return bytes([MESSAGE_SYNC, substep]) + data

    async def _handle_sync_message(
        self, ws: WebSocket, room: RoomState, doc_name: str, data: bytes,
    ) -> None:
        """Handle Yjs sync protocol messages."""
        if len(data) < 2:
            return

        substep = data[1]
        payload = data[2:]

        if not self._yjs_available or room.ydoc is None:
            # Basic relay mode: broadcast to all other clients
            await self._broadcast_to_room(ws, room, data)
            return

        if substep == SYNC_STEP1:
            # Client sent their state vector — compute and send diff
            try:
                update = encode_state_as_update(room.ydoc, payload)
                reply = self._build_sync_message(SYNC_STEP2, update)
                await ws.send_bytes(reply)
            except Exception as exc:
                logger.warning("SyncStep1 error: %s", exc)

        elif substep == SYNC_STEP2:
            # Client sent their diff update — apply it
            try:
                apply_update(room.ydoc, payload)
                # Broadcast update to all other clients in room
                await self._broadcast_to_room(ws, room, data)
            except Exception as exc:
                logger.warning("SyncStep2 error: %s", exc)

        elif substep == SYNC_UPDATE:
            # Client sent an incremental update
            try:
                apply_update(room.ydoc, payload)
                await self._broadcast_to_room(ws, room, data)
            except Exception as exc:
                logger.warning("SyncUpdate error: %s", exc)

        else:
            logger.debug("Unknown sync substep: %d", substep)

    async def _broadcast_awareness(
        self, ws: WebSocket, room: RoomState, data: bytes,
    ) -> None:
        """Broadcast awareness (cursor presence) to all other clients in room."""
        await self._broadcast_to_room(ws, room, data)

    async def _broadcast_to_room(
        self, sender: WebSocket, room: RoomState, data: bytes,
    ) -> None:
        """Broadcast a message to all clients in the room except the sender."""
        if not room.clients:
            return

        stale_clients: list[WebSocket] = []
        for client in list(room.clients.keys()):
            if client == sender:
                continue
            try:
                await client.send_bytes(data)
            except Exception:
                stale_clients.append(client)

        # Clean up stale clients
        for client in stale_clients:
            room.clients.pop(client, None)

    # ── Awareness State ──────────────────────────────────────

    def get_awareness_state(self, doc_name: str) -> list[dict[str, Any]]:
        """Get current awareness state (connected users) for a room."""
        room = self.rooms.get(doc_name)
        if not room:
            return []
        clients_info = []
        for ws, info in room.clients.items():
            clients_info.append({
                "connected_at": info.get("connected_at", 0),
                "uptime_seconds": time.time() - info.get("connected_at", time.time()),
            })
        return clients_info

    # ── Health ────────────────────────────────────────────────

    def get_health(self) -> dict[str, Any]:
        """Get server health information."""
        return {
            "yjs_available": self._yjs_available,
            "rooms": len(self.rooms),
            "total_clients": sum(r.client_count for r in self.rooms.values()),
            "persist_dir": str(self.persist_dir),
        }


# Module-level singleton
_yjs_manager: YjsServerManager | None = None


def get_yjs_manager() -> YjsServerManager:
    """Get the global Yjs server manager instance."""
    global _yjs_manager
    if _yjs_manager is None:
        _yjs_manager = YjsServerManager()
    return _yjs_manager


def reset_yjs_manager() -> None:
    """Reset the global manager (for testing)."""
    global _yjs_manager
    _yjs_manager = None
