import os
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
from services.env_config import load_backend_env

load_backend_env()


class MemoryStore:
    """
    Mongo-backed persistent store.
    Kept as `MemoryStore` to avoid changing import paths in the codebase.
    """

    def __init__(self) -> None:
        mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
        db_name = os.getenv("MONGO_DB_NAME", "timetable_app")

        self._mongo_available = False
        self._counters_mem: dict[str, int] = {}
        self._uploaded_files_mem: dict[str, dict[str, Any]] = {}
        self._scoped_mappings_mem: dict[tuple[str, str], dict[str, Any]] = {}
        self._generated_timetables_mem: dict[str, dict[str, Any]] = {}
        self._faculty_occupancy_mem: list[dict[str, Any]] = []
        self._users_mem: dict[str, dict[str, Any]] = {}
        self._sessions_mem: dict[str, dict[str, Any]] = {}

        self._mongo_error = None
        try:
            self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self._db = self._client[db_name]
            self._counters: Collection = self._db["counters"]
            self._uploaded_files: Collection = self._db["uploaded_files"]
            self._scoped_mappings: Collection = self._db["scoped_mappings"]
            self._generated_timetables: Collection = self._db["generated_timetables"]
            self._faculty_occupancy: Collection = self._db["faculty_occupancy"]
            self._users: Collection = self._db["users"]
            self._sessions: Collection = self._db["sessions"]

            self._uploaded_files.create_index("id", unique=True)
            self._scoped_mappings.create_index([("mapType", 1), ("scopeKey", 1)], unique=True)
            self._generated_timetables.create_index("id", unique=True)
            self._faculty_occupancy.create_index([("faculty", 1), ("day", 1), ("period", 1), ("sourceId", 1)], unique=True)
            self._faculty_occupancy.create_index("sourceId")
            self._users.create_index("username", unique=True)
            self._sessions.create_index("id", unique=True)
            self._sessions.create_index("username")
            
            # Test connection immediately
            self._client.admin.command('ping')
            self._mongo_available = True
        except Exception as e:
            self._mongo_available = False
            self._mongo_error = str(e)

    def ping(self) -> None:
        if not self._mongo_available:
            err = f"MongoDB unavailable: {self._mongo_error}" if self._mongo_error else "MongoDB unavailable"
            raise RuntimeError(err)
        self._db.command("ping")

    def _next_sequence(self, key: str) -> int:
        if not self._mongo_available:
            next_value = self._counters_mem.get(key, 0) + 1
            self._counters_mem[key] = next_value
            return next_value
        doc = self._counters.find_one_and_update(
            {"_id": key},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(doc["seq"])

    def next_file_id(self, prefix: str) -> str:
        return f"{prefix}_{self._next_sequence('file')}"

    def next_timetable_id(self) -> str:
        sequence = self._next_sequence("timetable")
        stamp = datetime.now().strftime("%Y%m%d")
        return f"tt_{stamp}_{sequence:03d}"

    def next_user_id(self) -> str:
        return f"user_{self._next_sequence('user')}"

    def next_session_id(self) -> str:
        return f"session_{self._next_sequence('session')}"

    def save_file_map(self, file_id: str, payload: dict[str, Any]) -> None:
        document = {
            **payload,
            "id": file_id,
            "updatedAt": datetime.now(timezone.utc),
        }
        if not self._mongo_available:
            self._uploaded_files_mem[file_id] = document
            return
        self._uploaded_files.update_one({"id": file_id}, {"$set": document}, upsert=True)

    def get_file_map(self, file_id: str) -> dict[str, Any] | None:
        if not self._mongo_available:
            return self._uploaded_files_mem.get(file_id)
        document = self._uploaded_files.find_one({"id": file_id}, {"_id": 0})
        return document

    def save_scoped_mapping(
        self,
        map_type: str,
        scope_key: str,
        payload: dict[str, Any],
        allow_overwrite: bool = False,
    ) -> bool:
        document = {
            **payload,
            "mapType": map_type,
            "scopeKey": scope_key,
            "updatedAt": datetime.now(timezone.utc),
        }
        if not self._mongo_available:
            key = (map_type, scope_key)
            if key in self._scoped_mappings_mem and not allow_overwrite:
                return False
            self._scoped_mappings_mem[key] = document
            return True
        if allow_overwrite:
            self._scoped_mappings.update_one(
                {"mapType": map_type, "scopeKey": scope_key},
                {"$set": document},
                upsert=True,
            )
            return True
        try:
            self._scoped_mappings.insert_one(document)
            return True
        except DuplicateKeyError:
            return False

    def get_scoped_mapping(self, map_type: str, scope_key: str) -> dict[str, Any] | None:
        if not self._mongo_available:
            return self._scoped_mappings_mem.get((map_type, scope_key))
        return self._scoped_mappings.find_one({"mapType": map_type, "scopeKey": scope_key}, {"_id": 0})

    def delete_scoped_mapping(self, map_type: str, scope_key: str) -> bool:
        if not self._mongo_available:
            return self._scoped_mappings_mem.pop((map_type, scope_key), None) is not None
        result = self._scoped_mappings.delete_one({"mapType": map_type, "scopeKey": scope_key})
        return result.deleted_count > 0

    def save_timetable(self, timetable_id: str, payload: dict[str, Any]) -> None:
        document = {
            **payload,
            "id": timetable_id,
            "updatedAt": datetime.now(timezone.utc),
        }
        if not self._mongo_available:
            self._generated_timetables_mem[timetable_id] = document
            return
        self._generated_timetables.update_one({"id": timetable_id}, {"$set": document}, upsert=True)

    def get_timetable(self, timetable_id: str) -> dict[str, Any] | None:
        if not self._mongo_available:
            return self._generated_timetables_mem.get(timetable_id)
        return self._generated_timetables.find_one({"id": timetable_id}, {"_id": 0})

    def list_timetables(self) -> list[dict[str, Any]]:
        if not self._mongo_available:
            return sorted(
                self._generated_timetables_mem.values(),
                key=lambda item: item.get("updatedAt", datetime.min.replace(tzinfo=timezone.utc)),
                reverse=True,
            )
        return list(self._generated_timetables.find({}, {"_id": 0}).sort("updatedAt", -1))

    def delete_timetable(self, timetable_id: str) -> bool:
        if not self._mongo_available:
            if timetable_id in self._generated_timetables_mem:
                del self._generated_timetables_mem[timetable_id]
                return True
            return False
        res = self._generated_timetables.delete_one({"id": timetable_id})
        return res.deleted_count > 0

    def delete_all_timetables(self) -> int:
        """Delete all stored timetables and return the count of deleted documents."""
        if not self._mongo_available:
            count = len(self._generated_timetables_mem)
            self._generated_timetables_mem.clear()
            return count
        res = self._generated_timetables.delete_many({})
        return res.deleted_count

    def mark_faculty_busy(
        self,
        faculty: str,
        day: str,
        period: int,
        source_id: str,
        year: str | None = None,
        section: str | None = None,
    ) -> None:
        document = {
            "faculty": faculty,
            "day": day,
            "period": int(period),
            "sourceId": source_id,
            "year": year,
            "section": section,
            "updatedAt": datetime.now(timezone.utc),
        }
        if not self._mongo_available:
            # Check for duplicates in memory
            for idx, item in enumerate(self._faculty_occupancy_mem):
                if (
                    item["faculty"] == faculty
                    and item["day"] == day
                    and item["period"] == period
                    and item["sourceId"] == source_id
                ):
                    self._faculty_occupancy_mem[idx] = document
                    return
            self._faculty_occupancy_mem.append(document)
            return
        self._faculty_occupancy.update_one(
            {"faculty": faculty, "day": day, "period": int(period), "sourceId": source_id},
            {"$set": document},
            upsert=True,
        )

    def delete_occupancy_by_source(self, source_id: str) -> None:
        if not self._mongo_available:
            self._faculty_occupancy_mem = [item for item in self._faculty_occupancy_mem if item["sourceId"] != source_id]
            return
        self._faculty_occupancy.delete_many({"sourceId": source_id})

    def get_global_faculty_occupancy_details(self) -> list[dict[str, Any]]:
        if not self._mongo_available:
            return [item.copy() for item in self._faculty_occupancy_mem]
        return list(self._faculty_occupancy.find({}, {"_id": 0}))

    def get_global_faculty_occupancy(self) -> dict[str, set[tuple[str, int]]]:
        details = self.get_global_faculty_occupancy_details()
        occupancy: dict[str, set[tuple[str, int]]] = {}
        for item in details:
            faculty = str(item.get("faculty", "")).strip()
            if not faculty:
                continue
            occupancy.setdefault(faculty, set()).add(
                (str(item.get("day", "")).strip(), int(item.get("period", 0)))
            )
        return occupancy

    @property
    def global_faculty_occupancy(self) -> dict[str, set[tuple[str, int]]]:
        return self.get_global_faculty_occupancy()

    def save_user(self, username: str, payload: dict[str, Any]) -> None:
        document = {
            **payload,
            "username": username,
            "updatedAt": datetime.now(timezone.utc),
        }
        if not self._mongo_available:
            self._users_mem[username] = document
            return
        self._users.update_one({"username": username}, {"$set": document}, upsert=True)

    def create_user(self, username: str, payload: dict[str, Any]) -> bool:
        document = {
            **payload,
            "username": username,
            "updatedAt": datetime.now(timezone.utc),
        }
        if not self._mongo_available:
            if username in self._users_mem:
                return False
            self._users_mem[username] = document
            return True
        try:
            self._users.insert_one(document)
            return True
        except DuplicateKeyError:
            return False

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        if not self._mongo_available:
            return self._users_mem.get(username)
        return self._users.find_one({"username": username}, {"_id": 0})

    def list_users_by_creator(self, created_by: str, role: str | None = None) -> list[dict[str, Any]]:
        if not self._mongo_available:
            items = [item for item in self._users_mem.values() if item.get("createdBy") == created_by]
            if role:
                items = [item for item in items if item.get("role") == role]
            return sorted(items, key=lambda item: item.get("username", ""))
        query: dict[str, Any] = {"createdBy": created_by}
        if role:
            query["role"] = role
        return list(self._users.find(query, {"_id": 0}).sort("username", 1))

    def update_user_password(self, username: str, password_hash: str) -> bool:
        if not self._mongo_available:
            if username not in self._users_mem:
                return False
            self._users_mem[username]["passwordHash"] = password_hash
            self._users_mem[username]["updatedAt"] = datetime.now(timezone.utc)
            return True
        result = self._users.update_one(
            {"username": username},
            {"$set": {"passwordHash": password_hash, "updatedAt": datetime.now(timezone.utc)}},
        )
        return result.matched_count > 0

    def rename_user(self, old_username: str, new_username: str) -> bool:
        if old_username == new_username:
            return True
        if not self._mongo_available:
            if old_username not in self._users_mem or new_username in self._users_mem:
                return False
            document = dict(self._users_mem.pop(old_username))
            document["username"] = new_username
            document["updatedAt"] = datetime.now(timezone.utc)
            self._users_mem[new_username] = document
            for session in self._sessions_mem.values():
                if session.get("username") == old_username:
                    session["username"] = new_username
                    session["updatedAt"] = datetime.now(timezone.utc)
            for item in self._users_mem.values():
                if item.get("createdBy") == old_username:
                    item["createdBy"] = new_username
                    item["updatedAt"] = datetime.now(timezone.utc)
            return True

        if self.get_user_by_username(new_username):
            return False
        user = self.get_user_by_username(old_username)
        if not user:
            return False
        user["username"] = new_username
        user["updatedAt"] = datetime.now(timezone.utc)
        self._users.delete_one({"username": old_username})
        try:
            self._users.insert_one(user)
        except DuplicateKeyError:
            return False
        self._sessions.update_many(
            {"username": old_username},
            {"$set": {"username": new_username, "updatedAt": datetime.now(timezone.utc)}},
        )
        self._users.update_many(
            {"createdBy": old_username},
            {"$set": {"createdBy": new_username, "updatedAt": datetime.now(timezone.utc)}},
        )
        return True

    def delete_user(self, username: str) -> bool:
        self.delete_sessions_by_username(username)
        if not self._mongo_available:
            return self._users_mem.pop(username, None) is not None
        result = self._users.delete_one({"username": username})
        return result.deleted_count > 0

    def save_session(self, session_id: str, payload: dict[str, Any]) -> None:
        document = {
            **payload,
            "id": session_id,
            "updatedAt": datetime.now(timezone.utc),
        }
        if not self._mongo_available:
            self._sessions_mem[session_id] = document
            return
        self._sessions.update_one({"id": session_id}, {"$set": document}, upsert=True)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        if not self._mongo_available:
            return self._sessions_mem.get(session_id)
        return self._sessions.find_one({"id": session_id}, {"_id": 0})

    def delete_session(self, session_id: str) -> None:
        if not self._mongo_available:
            self._sessions_mem.pop(session_id, None)
            return
        self._sessions.delete_one({"id": session_id})

    def delete_sessions_by_username(self, username: str) -> None:
        if not self._mongo_available:
            self._sessions_mem = {
                sid: item
                for sid, item in self._sessions_mem.items()
                if item.get("username") != username
            }
            return
        self._sessions.delete_many({"username": username})


store = MemoryStore()
