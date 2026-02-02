import os
from typing import Dict, List, Optional

import discord
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from utilities.tasks.utils import normalize_priority


class LinearIntegration:
    def __init__(self):
        self.client = None
        self.team_id = os.getenv("LINEAR_TEAM_ID")

        project_id = (os.getenv("LINEAR_PROJECT_ID") or "").strip()
        self.project_id = project_id or None

        self.api_key = os.getenv("LINEAR_API_KEY")
        self.state_todo_id = os.getenv("LINEAR_STATE_TODO_ID")
        self.state_backlog_id = os.getenv("LINEAR_STATE_BACKLOG_ID")
        self.label_urgent_id = os.getenv("LINEAR_LABEL_URGENT_ID")
        self.label_high_priority_id = os.getenv("LINEAR_LABEL_HIGH_PRIORITY_ID")
        self.label_medium_priority_id = os.getenv("LINEAR_LABEL_MEDIUM_PRIORITY_ID")
        self.label_low_priority_id = os.getenv("LINEAR_LABEL_LOW_PRIORITY_ID")

        if self.api_key:
            transport = RequestsHTTPTransport(
                url="https://api.linear.app/graphql",
                headers={"Authorization": self.api_key},
            )
            self.client = Client(transport=transport, fetch_schema_from_transport=True)

    def _priority_mapping(self, priority: str) -> Dict[str, Optional[str]]:
        normalized = normalize_priority(priority)
        mapping = {
            "urgent": {
                "state_id": self.state_todo_id,
                "label_id": self.label_urgent_id,
            },
            "high_priority": {
                "state_id": self.state_todo_id,
                "label_id": self.label_high_priority_id,
            },
            "medium_priority": {
                "state_id": self.state_todo_id,
                "label_id": self.label_medium_priority_id,
            },
            "low_priority": {
                "state_id": self.state_backlog_id,
                "label_id": self.label_low_priority_id,
            },
        }

        resolved = mapping.get(
            normalized, {"state_id": self.state_todo_id, "label_id": None}
        )

        if not resolved.get("state_id") and self.state_todo_id:
            resolved["state_id"] = self.state_todo_id

        return resolved

    async def create_issues_from_todo(
        self, todo_text: str, user: discord.User, channel: discord.TextChannel
    ) -> List[Dict]:
        if not self.client or not self.team_id:
            return []

        categories = self._parse_todo_text(todo_text)

        created_issues = []

        for category, tasks in categories.items():
            for task in tasks:
                issue_data = await self.create_single_issue(
                    task, category, user, channel
                )
                if issue_data:
                    created_issues.append(issue_data)

        return created_issues

    def _parse_todo_text(self, todo_text: str) -> Dict[str, List[str]]:
        categories = {}
        lines = todo_text.split("\n")
        current_category = None
        for line in lines:
            line = line.strip()
            if line.startswith("**") and line.endswith(":**"):
                current_category = line.replace("**", "").replace(":", "").strip()
                categories[current_category] = []
            elif line.startswith("- ") and current_category:
                categories[current_category].append(line[2:])
        return categories

    async def create_single_issue(
        self, task: str, category: str, user: discord.User, channel: discord.TextChannel
    ) -> Optional[Dict]:
        return await self.create_issue_for_task(
            {
                "text": task,
                "priority": category,
            },
            user,
            channel,
        )

    async def create_issue_for_task(
        self, task: Dict, user: discord.User, channel: discord.TextChannel
    ) -> Optional[Dict]:
        if not self.client:
            return None

        if not self.team_id:
            return None

        mapping = self._priority_mapping(task.get("priority", ""))
        if not mapping.get("state_id"):
            return None

        desc = (task.get("text") or "").strip()
        message_link = task.get("source_message_link") or ""

        create_issue_mutation = gql(
            """
            mutation CreateIssue($input: IssueCreateInput!) {
                issueCreate(input: $input) {
                    success
                    issue {
                        id
                        number
                        title
                        url
                    }
                }
            }
            """
        )

        title = desc if len(desc) <= 80 else f"{desc[:77]}..."
        description = f"Generated from Discord by {user.display_name}.\n\n{desc}"
        if message_link:
            description += f"\n\nSource: {message_link}"
        description += f"\n\nChannel: {channel.mention}"

        input_data = {
            "title": title,
            "description": description,
            "teamId": self.team_id,
            "stateId": mapping["state_id"],
        }

        if self.project_id:
            input_data["projectId"] = self.project_id

        if mapping.get("label_id"):
            input_data["labelIds"] = [mapping["label_id"]]

        try:
            result = self.client.execute(
                create_issue_mutation, variable_values={"input": input_data}
            )
            if result.get("issueCreate", {}).get("success"):
                issue = result["issueCreate"]["issue"]
                return {
                    "id": issue["id"],
                    "number": issue["number"],
                    "title": issue["title"],
                    "url": issue["url"],
                    "priority": normalize_priority(task.get("priority")),
                }
        except Exception:
            return None
        return None

    async def get_issue_states_and_labels(self):
        if not self.client:
            return None

        query = gql(
            """
            query GetTeamData($teamId: String!) {
                team(id: $teamId) {
                    states {
                        nodes {
                            id
                            name
                        }
                    }
                    labels {
                        nodes {
                            id
                            name
                        }
                    }
                }
            }
            """
        )

        try:
            result = self.client.execute(
                query, variable_values={"teamId": self.team_id}
            )
            return result["team"]
        except Exception:
            return None
