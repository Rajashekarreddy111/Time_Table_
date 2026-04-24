import os
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError
from services.env_config import load_backend_env

load_backend_env()


def is_mongo_required() -> bool:
    configured_uri = (os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "").strip()
    explicit_flag = os.getenv("REQUIRE_MONGODB")
    if explicit_flag is not None:
        return explicit_flag.strip().lower() in {"1", "true", "yes", "on"}
    return bool(configured_uri)


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
        try:
            self._db.command("ping")
        except PyMongoError as e:
            self._disable_mongo(e)
            raise RuntimeError(f"MongoDB unavailable: {self._mongo_error}") from e

    def _disable_mongo(self, error: Exception) -> None:
        self._mongo_available = False
        self._mongo_error = str(error)

    def _next_sequence(self, key: str) -> int:
        if not self._mongo_available:
            next_value = self._counters_mem.get(key, 0) + 1
            self._counters_mem[key] = next_value
            return next_value
        try:
            doc = self._counters.find_one_and_update(
                {"_id": key},
                {"$inc": {"seq": 1}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            seq = int(doc["seq"])
            self._counters_mem[key] = max(self._counters_mem.get(key, 0), seq)
            return seq
        except PyMongoError as e:
            self._disable_mongo(e)
            next_value = self._counters_mem.get(key, 0) + 1
            self._counters_mem[key] = next_value
            return next_value

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
        # Uploaded input files are intentionally kept in memory only.
        self._uploaded_files_mem[file_id] = document

    def get_file_map(self, file_id: str) -> dict[str, Any] | None:
        return self._uploaded_files_mem.get(file_id)

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
        key = (map_type, scope_key)
        if key in self._scoped_mappings_mem and not allow_overwrite:
            return False
        self._scoped_mappings_mem[key] = document
        return True

    def get_scoped_mapping(self, map_type: str, scope_key: str) -> dict[str, Any] | None:
        return self._scoped_mappings_mem.get((map_type, scope_key))

    def delete_scoped_mapping(self, map_type: str, scope_key: str) -> bool:
        return self._scoped_mappings_mem.pop((map_type, scope_key), None) is not None

    def save_timetable(self, timetable_id: str, payload: dict[str, Any]) -> None:
        document = {
            **payload,
            "id": timetable_id,
            "updatedAt": datetime.now(timezone.utc),
        }
        self._generated_timetables_mem[timetable_id] = document
        if not self._mongo_available:
            return
        try:
            self._generated_timetables.update_one({"id": timetable_id}, {"$set": document}, upsert=True)
        except PyMongoError as e:
            self._disable_mongo(e)

    def get_timetable(self, timetable_id: str) -> dict[str, Any] | None:
        if not self._mongo_available:
            return self._generated_timetables_mem.get(timetable_id)
        try:
            document = self._generated_timetables.find_one({"id": timetable_id}, {"_id": 0})
        except PyMongoError as e:
            self._disable_mongo(e)
            return self._generated_timetables_mem.get(timetable_id)
        if document:
            self._generated_timetables_mem[timetable_id] = document
        return document

    def list_timetables(self) -> list[dict[str, Any]]:
        if not self._mongo_available:
            return sorted(
                self._generated_timetables_mem.values(),
                key=lambda item: item.get("updatedAt", datetime.min.replace(tzinfo=timezone.utc)),
                reverse=True,
            )
        try:
            items = list(self._generated_timetables.find({}, {"_id": 0}).sort("updatedAt", -1))
        except PyMongoError as e:
            self._disable_mongo(e)
            return sorted(
                self._generated_timetables_mem.values(),
                key=lambda item: item.get("updatedAt", datetime.min.replace(tzinfo=timezone.utc)),
                reverse=True,
            )
        self._generated_timetables_mem = {str(item["id"]): item for item in items if item.get("id")}
        return items

    def delete_timetable(self, timetable_id: str) -> bool:
        existed = self._generated_timetables_mem.pop(timetable_id, None) is not None
        if not self._mongo_available:
            return existed
        try:
            res = self._generated_timetables.delete_one({"id": timetable_id})
            return res.deleted_count > 0 or existed
        except PyMongoError as e:
            self._disable_mongo(e)
            return existed

    def delete_all_timetables(self) -> int:
        """Delete all stored timetables and return the count of deleted documents."""
        count = len(self._generated_timetables_mem)
        self._generated_timetables_mem.clear()
        if not self._mongo_available:
            return count
        try:
            res = self._generated_timetables.delete_many({})
            return max(count, res.deleted_count)
        except PyMongoError as e:
            self._disable_mongo(e)
            return count

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
        # Keep memory in sync so a mid-request Mongo disconnect does not lose the generated result.
        for idx, item in enumerate(self._faculty_occupancy_mem):
            if (
                item["faculty"] == faculty
                and item["day"] == day
                and item["period"] == period
                and item["sourceId"] == source_id
            ):
                self._faculty_occupancy_mem[idx] = document
                break
        else:
            self._faculty_occupancy_mem.append(document)
        if not self._mongo_available:
            return
        try:
            self._faculty_occupancy.update_one(
                {"faculty": faculty, "day": day, "period": int(period), "sourceId": source_id},
                {"$set": document},
                upsert=True,
            )
        except PyMongoError as e:
            self._disable_mongo(e)

    def delete_occupancy_by_source(self, source_id: str) -> None:
        self._faculty_occupancy_mem = [item for item in self._faculty_occupancy_mem if item["sourceId"] != source_id]
        if not self._mongo_available:
            return
        try:
            self._faculty_occupancy.delete_many({"sourceId": source_id})
        except PyMongoError as e:
            self._disable_mongo(e)

    def get_global_faculty_occupancy_details(self) -> list[dict[str, Any]]:
        if not self._mongo_available:
            return [item.copy() for item in self._faculty_occupancy_mem]
        try:
            items = list(self._faculty_occupancy.find({}, {"_id": 0}))
        except PyMongoError as e:
            self._disable_mongo(e)
            return [item.copy() for item in self._faculty_occupancy_mem]
        self._faculty_occupancy_mem = [item.copy() for item in items]
        return items

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
        self._users_mem[username] = document
        if not self._mongo_available:
            return
        try:
            self._users.update_one({"username": username}, {"$set": document}, upsert=True)
        except PyMongoError as e:
            self._disable_mongo(e)

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
        except PyMongoError as e:
            self._disable_mongo(e)
            if username in self._users_mem:
                return False
            self._users_mem[username] = document
            return True

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        if not self._mongo_available:
            return self._users_mem.get(username)
        try:
            user = self._users.find_one({"username": username}, {"_id": 0})
        except PyMongoError as e:
            self._disable_mongo(e)
            return self._users_mem.get(username)
        if user:
            self._users_mem[username] = user
        return user

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return None
        if not self._mongo_available:
            for item in self._users_mem.values():
                if str(item.get("id", "")).strip() == normalized_user_id:
                    return item
            return None
        try:
            user = self._users.find_one({"id": normalized_user_id}, {"_id": 0})
        except PyMongoError as e:
            self._disable_mongo(e)
            for item in self._users_mem.values():
                if str(item.get("id", "")).strip() == normalized_user_id:
                    return item
            return None
        if user:
            username = str(user.get("username", "")).strip()
            if username:
                self._users_mem[username] = user
        return user

    def list_users_by_creator(self, created_by: str, role: str | None = None) -> list[dict[str, Any]]:
        if not self._mongo_available:
            items = [item for item in self._users_mem.values() if item.get("createdBy") == created_by]
            if role:
                items = [item for item in items if item.get("role") == role]
            return sorted(items, key=lambda item: item.get("username", ""))
        query: dict[str, Any] = {"createdBy": created_by}
        if role:
            query["role"] = role
        try:
            items = list(self._users.find(query, {"_id": 0}).sort("username", 1))
        except PyMongoError as e:
            self._disable_mongo(e)
            items = [item for item in self._users_mem.values() if item.get("createdBy") == created_by]
            if role:
                items = [item for item in items if item.get("role") == role]
            return sorted(items, key=lambda item: item.get("username", ""))
        for item in items:
            username = str(item.get("username", "")).strip()
            if username:
                self._users_mem[username] = item
        return items

    def update_user_password(self, username: str, password_hash: str) -> bool:
        if not self._mongo_available:
            if username not in self._users_mem:
                return False
            self._users_mem[username]["passwordHash"] = password_hash
            self._users_mem[username]["authVersion"] = int(self._users_mem[username].get("authVersion", 0)) + 1
            self._users_mem[username]["updatedAt"] = datetime.now(timezone.utc)
            return True
        next_auth_version = int(self._users_mem.get(username, {}).get("authVersion", 0)) + 1
        self._users_mem.setdefault(username, {})["passwordHash"] = password_hash
        self._users_mem[username]["authVersion"] = next_auth_version
        self._users_mem[username]["updatedAt"] = datetime.now(timezone.utc)
        try:
            result = self._users.update_one(
                {"username": username},
                {
                    "$set": {"passwordHash": password_hash, "updatedAt": datetime.now(timezone.utc)},
                    "$inc": {"authVersion": 1},
                },
            )
            return result.matched_count > 0
        except PyMongoError as e:
            self._disable_mongo(e)
            return username in self._users_mem

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
        try:
            self._users.delete_one({"username": old_username})
            self._users.insert_one(user)
        except DuplicateKeyError:
            return False
        except PyMongoError as e:
            self._disable_mongo(e)
            document = dict(self._users_mem.pop(old_username, {}))
            document.update(user)
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
        existed = self._users_mem.pop(username, None) is not None
        if not self._mongo_available:
            return existed
        try:
            result = self._users.delete_one({"username": username})
            return result.deleted_count > 0 or existed
        except PyMongoError as e:
            self._disable_mongo(e)
            return existed

    def save_session(self, session_id: str, payload: dict[str, Any]) -> None:
        document = {
            **payload,
            "id": session_id,
            "updatedAt": datetime.now(timezone.utc),
        }
        self._sessions_mem[session_id] = document
        if not self._mongo_available:
            return
        try:
            self._sessions.update_one({"id": session_id}, {"$set": document}, upsert=True)
        except PyMongoError as e:
            self._disable_mongo(e)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        if not self._mongo_available:
            return self._sessions_mem.get(session_id)
        try:
            session = self._sessions.find_one({"id": session_id}, {"_id": 0})
        except PyMongoError as e:
            self._disable_mongo(e)
            return self._sessions_mem.get(session_id)
        if session:
            self._sessions_mem[session_id] = session
        return session

    def delete_session(self, session_id: str) -> None:
        self._sessions_mem.pop(session_id, None)
        if not self._mongo_available:
            return
        try:
            self._sessions.delete_one({"id": session_id})
        except PyMongoError as e:
            self._disable_mongo(e)

    def delete_sessions_by_username(self, username: str) -> None:
        self._sessions_mem = {
            sid: item
            for sid, item in self._sessions_mem.items()
            if item.get("username") != username
        }
        if not self._mongo_available:
            return
        try:
            self._sessions.delete_many({"username": username})
        except PyMongoError as e:
            self._disable_mongo(e)


store = MemoryStore()
