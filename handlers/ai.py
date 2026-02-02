import json
import os
import re
from typing import Dict, List

import discord
from discord.ext import commands
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from utilities.databases import TaskDatabase
from utilities.tasks import (
    LinearIntegration,
    TaskReviewView,
    clean_task_text,
    dedupe_key,
    extract_message_id,
    extract_message_link,
    normalize_priority,
    priority_rank,
)

ALLOWED_ROLE_ID = 1298971806593454080
DENIED_MESSAGE = "idk why i can't execute the command maybe ask <@727012870683885578>"


def has_allowed_role():
    async def predicate(ctx: discord.ApplicationContext) -> bool:
        if not ctx.guild:
            return False
        member = ctx.guild.get_member(ctx.author.id)
        if not member:
            return False
        if any(role.id == ALLOWED_ROLE_ID for role in member.roles):
            return True
        await ctx.respond(DENIED_MESSAGE, ephemeral=True)
        return False
    return commands.check(predicate)


class AIHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client, self.model, self.provider_label = self._build_ai_client()

        self.db = TaskDatabase()
        self.linear = LinearIntegration()

    def _build_ai_client(self) -> tuple[AsyncOpenAI, str, str]:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")

        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        headers = {}
        referer = os.getenv("OPENROUTER_HTTP_REFERER")
        if referer:
            headers["HTTP-Referer"] = referer
        title = os.getenv("OPENROUTER_APP_TITLE")
        if title:
            headers["X-Title"] = title

        client_kwargs = {"api_key": api_key, "base_url": base_url}
        if headers:
            client_kwargs["default_headers"] = headers

        return AsyncOpenAI(**client_kwargs), model, "OpenRouter"

    def _parse_task_list(self, content: str) -> List[Dict]:
        if not content:
            return []

        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                return []
            payload = json.loads(match.group(0))

        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        if not isinstance(tasks, list):
            return []

        parsed = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            description = (task.get("description") or "").strip()
            if not description:
                continue
            parsed.append(
                {
                    "description": description,
                    "priority": task.get("priority"),
                    "message_link": task.get("message_link"),
                }
            )
        return parsed

    async def fetch_recent_messages(
        self, channel: discord.TextChannel, limit: int = 250
    ) -> list[discord.Message]:
        messages = []
        last_message_id = self.db.get_last_message_id(channel.id)

        if last_message_id:
            history = channel.history(
                limit=limit, after=discord.Object(id=last_message_id)
            )
        else:
            history = channel.history(limit=limit)

        async for message in history:
            if message.author.bot:
                continue
            if not message.content and not message.attachments:
                continue
            messages.append(message)

        messages.sort(key=lambda msg: msg.created_at)
        return messages

    def filter_messages_for_user(
        self, messages: list[discord.Message], user: discord.User
    ) -> list[discord.Message]:
        filtered = []
        user_name = user.name.lower()
        display_name = user.display_name.lower()
        for message in messages:
            if user in message.mentions:
                filtered.append(message)
                continue
            if (
                user_name in message.content.lower()
                or display_name in message.content.lower()
            ):
                filtered.append(message)
                continue
            if message.author.id == user.id:
                filtered.append(message)
                continue
            if message.reference and message.reference.resolved:
                replied = message.reference.resolved
                if hasattr(replied, "author") and replied.author.id == user.id:
                    filtered.append(message)

        if not filtered:
            filtered = messages[: min(80, len(messages))]

        return filtered

    def _message_link(self, message: discord.Message) -> str:
        return f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"

    def _format_message(self, message: discord.Message) -> str:
        content = (message.content or "").strip()
        if not content and message.attachments:
            filenames = ", ".join(att.filename for att in message.attachments)
            content = f"Attachments: {filenames}"
        author = f"{message.author.display_name} ({message.author.name}#{message.author.discriminator})"
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M")
        link = self._message_link(message)
        return f"[{timestamp}] {author} [Message: {link}]: {content}"

    def _build_message_context(
        self, messages: list[discord.Message]
    ) -> tuple[str, Dict[str, Dict]]:
        message_lines = []
        message_index: Dict[str, Dict] = {}
        for msg in messages:
            link = self._message_link(msg)
            message_lines.append(self._format_message(msg))
            message_index[link] = {
                "id": msg.id,
                "ts": int(msg.created_at.timestamp()),
            }
        return "\n".join(message_lines), message_index

    async def generate_todo_list(
        self, message_text: str, user: discord.User
    ) -> List[Dict]:
        if not message_text:
            return []

        prompt = (
            "Analyze the Discord conversation and extract only tasks assigned to "
            f"{user.display_name} ({user.name}#{user.discriminator}).\n\n"
            "Rules:\n"
            "- Focus on clear, actionable tasks assigned to the user.\n"
            "- Ignore general chatter or tasks for other people.\n"
            "- Use concise, imperative phrasing.\n"
            "- Return a priority of URGENT, HIGH PRIORITY, MEDIUM PRIORITY, or LOW PRIORITY.\n"
            "- If a task is tied to a specific message, include its message_link.\n"
            "- Do not invent links.\n\n"
            f"Messages:\n{message_text}"
        )

        system_instruction = (
            "Respond with JSON only. Schema: "
            '{"tasks":[{"description":"string","priority":"URGENT|HIGH PRIORITY|MEDIUM PRIORITY|LOW PRIORITY","message_link":null|"string"}]}.'
        )

        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
            )
        except (APIStatusError, APIConnectionError, APITimeoutError):
            return []

        if not completion.choices:
            return []

        content = completion.choices[0].message.content or ""
        if not content:
            return []

        return self._parse_task_list(content)

    def _prepare_tasks(
        self,
        raw_tasks: List[Dict],
        message_index: Dict[str, Dict],
        user_id: int,
    ) -> List[Dict]:
        prepared = []
        for task in raw_tasks:
            text = clean_task_text(task.get("description", ""))
            if not text:
                continue

            priority = normalize_priority(task.get("priority"))
            message_link = extract_message_link(task.get("message_link"))
            source_message_id = extract_message_id(message_link)
            source_message_ts = None

            if message_link and message_link in message_index:
                source_message_id = message_index[message_link]["id"]
                source_message_ts = message_index[message_link]["ts"]

            prepared.append(
                {
                    "text": text,
                    "priority": priority,
                    "source_message_id": source_message_id,
                    "source_message_link": message_link,
                    "source_message_ts": source_message_ts,
                    "dedupe_key": dedupe_key(user_id, source_message_id, text),
                }
            )

        prepared.sort(
            key=lambda item: (
                priority_rank(item.get("priority")),
                item.get("source_message_ts") or 0,
            )
        )
        return prepared

    async def send_review_message(
        self,
        channel: discord.TextChannel,
        tasks: List[Dict],
        user: discord.User,
        batch_id: int,
    ):
        if not tasks:
            embed = discord.Embed(
                title=f"📋 No Tasks Found for {user.display_name}",
                description="No new tasks were identified in the recent messages.",
                color=0x0099FF,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text=f"Generated by {self.provider_label}")
            await channel.send(embed=embed)
            return

        view = TaskReviewView(
            self.linear,
            self.db,
            tasks,
            user,
            channel,
            batch_id,
            provider_label=self.provider_label,
        )
        embed = view.current_embed()
        message = await channel.send(embed=embed, view=view)
        view.message = message

    @discord.slash_command(
        name="todo", description="Generate a todo list from recent messages using AI"
    )
    @has_allowed_role()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def todo_command(
        self,
        ctx: discord.ApplicationContext,
        user: discord.User = None,
        output_channel: discord.TextChannel = None,
        message_limit: int = 250,
    ):
        await ctx.defer()

        target_user = user or ctx.user
        source_channel = ctx.channel
        target_channel = output_channel or source_channel

        if message_limit < 25 or message_limit > 500:
            await ctx.followup.send("Message limit must be between 25 and 500.")
            return

        try:
            messages = await self.fetch_recent_messages(source_channel, message_limit)
        except discord.Forbidden:
            await ctx.followup.send(
                "Bot does not have permission to read message history in this channel."
            )
            return
        except discord.HTTPException:
            await ctx.followup.send("Failed to fetch messages for analysis.")
            return

        if not messages:
            await ctx.followup.send("No new messages to analyze since last check.")
            return

        filtered_messages = self.filter_messages_for_user(messages, target_user)
        message_text, message_index = self._build_message_context(filtered_messages)

        raw_tasks = await self.generate_todo_list(message_text, target_user)
        prepared_tasks = self._prepare_tasks(raw_tasks, message_index, target_user.id)

        self.db.set_last_message_id(source_channel.id, messages[-1].id)

        batch_id = self.db.create_batch(
            user_id=target_user.id,
            source_channel_id=source_channel.id,
            target_channel_id=target_channel.id,
            message_start_id=messages[0].id,
            message_end_id=messages[-1].id,
            message_count=len(messages),
        )

        saved_tasks = self.db.save_tasks(
            prepared_tasks,
            batch_id,
            source_channel.id,
            target_user.id,
        )

        await self.send_review_message(
            target_channel, saved_tasks, target_user, batch_id
        )

        await ctx.followup.send(
            "📋 Scanned "
            f"{len(filtered_messages)} messages in {source_channel.mention} "
            f"and found {len(saved_tasks)} tasks for {target_user.mention}. "
            f"Review them in {target_channel.mention} and upload approved tasks to Linear."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.reference:
            return

        try:
            replied_to = await message.channel.fetch_message(
                message.reference.message_id
            )
        except Exception:
            return

        if replied_to.author.id != self.bot.user.id:
            return

        content_lower = message.content.lower()
        if "github.com" in content_lower and (
            "commit" in content_lower
            or "pull" in content_lower
            or "pr" in content_lower
        ):
            try:
                self.db.mark_channel_tasks_completed(message.channel.id)
            except Exception:
                pass

            try:
                await replied_to.add_reaction("✅")
            except Exception:
                pass


def setup(bot):
    bot.add_cog(AIHandlerCog(bot))
