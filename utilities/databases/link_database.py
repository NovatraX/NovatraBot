import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse


class LinkDatabase:
    def __init__(self, db_path: str = "data/links.json"):
        self.db_path = db_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.db_path):
            self._save_data({"links": [], "next_id": 1})

    def _load_data(self) -> Dict:
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"links": [], "next_id": 1}

    def _save_data(self, data: Dict):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_links(self, links: List[Dict]) -> List[Dict]:
        saved = []
        data = self._load_data()

        existing_keys = {(link["message_id"], link["url"]) for link in data["links"]}

        for link in links:
            key = (link["message_id"], link["url"])
            if key in existing_keys:
                continue

            link_entry = {
                "id": data["next_id"],
                "url": link["url"],
                "normalized_url": link.get("normalized_url"),
                "domain": link.get("domain"),
                "title": None,
                "description": None,
                "site_name": None,
                "image_url": None,
                "context": None,
                "category": None,
                "message_id": link["message_id"],
                "message_link": link["message_link"],
                "channel_id": link["channel_id"],
                "category_id": link["category_id"],
                "author_id": link["author_id"],
                "created_at": datetime.utcnow().isoformat(),
            }
            data["links"].append(link_entry)
            data["next_id"] += 1
            saved.append({"id": link_entry["id"], "url": link["url"]})
            existing_keys.add(key)

        self._save_data(data)
        return saved

    def update_metadata(
        self,
        link_id: int,
        title: Optional[str],
        description: Optional[str],
        site_name: Optional[str],
        image_url: Optional[str],
        category: Optional[str] = None,
        context: Optional[str] = None,
    ):
        data = self._load_data()
        for link in data["links"]:
            if link["id"] == link_id:
                link["title"] = title
                link["description"] = description
                link["site_name"] = site_name
                link["image_url"] = image_url
                link["category"] = category
                link["context"] = context
                break
        self._save_data(data)

    def count_links(
        self,
        query: Optional[str] = None,
        user_id: Optional[int] = None,
        category_id: Optional[int] = None,
        category: Optional[str] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> int:
        return len(
            self._filter_links(
                query, user_id, category_id, category, exclude_domains=exclude_domains
            )
        )

    def get_links(
        self,
        query: Optional[str] = None,
        user_id: Optional[int] = None,
        category_id: Optional[int] = None,
        category: Optional[str] = None,
        exclude_domains: Optional[List[str]] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> List[Dict]:
        filtered = self._filter_links(
            query, user_id, category_id, category, exclude_domains=exclude_domains
        )
        filtered.sort(key=lambda x: (x.get("created_at") or "", x["id"]), reverse=True)
        return filtered[offset : offset + limit]

    def _filter_links(
        self,
        query: Optional[str],
        user_id: Optional[int],
        category_id: Optional[int],
        category: Optional[str],
        exclude_domains: Optional[List[str]],
    ) -> List[Dict]:
        data = self._load_data()
        results = []
        normalized_excludes = [
            domain.lstrip(".").lower()
            for domain in (exclude_domains or [])
            if domain
        ]

        for link in data["links"]:
            if normalized_excludes and self._is_excluded_domain(
                link.get("domain"), link.get("url"), normalized_excludes
            ):
                continue
            if user_id and link.get("author_id") != user_id:
                continue
            if category_id and link.get("category_id") != category_id:
                continue
            if category and link.get("category") != category:
                continue
            if query:
                query_lower = query.lower()
                searchable = " ".join(
                    str(v or "").lower()
                    for v in [
                        link.get("url"),
                        link.get("title"),
                        link.get("description"),
                        link.get("site_name"),
                        link.get("domain"),
                        link.get("context"),
                    ]
                )
                if query_lower not in searchable:
                    continue
            results.append(link)

        return results

    @staticmethod
    def _is_excluded_domain(
        domain: Optional[str],
        url: Optional[str],
        exclude_domains: List[str],
    ) -> bool:
        host = (domain or "").lower()
        if not host and url:
            host = urlparse(url).netloc.lower()
        host = host.split(":", 1)[0]
        if not host:
            return False
        for excluded in exclude_domains:
            if host == excluded or host.endswith(f".{excluded}"):
                return True
        return False
