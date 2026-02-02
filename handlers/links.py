import asyncio
from datetime import datetime
from typing import List, Optional

import aiohttp
import discord
from discord.ext import commands

from utilities.databases import LinkDatabase
from utilities.links import (
    LINK_CATEGORIES,
    classify_link,
    domain_for_url,
    extract_urls,
    is_media_url,
    normalize_url,
    parse_metadata,
)

PAGE_SIZE = 5
ALLOWED_ROLE_ID = 1298971806593454080
LINK_CATEGORY_ID = 1295622870981939248
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


class LinkResultsView(discord.ui.View):
    def __init__(
        self,
        db: LinkDatabase,
        query: Optional[str],
        user_id: Optional[int],
        category_id: Optional[int],
        category: Optional[str] = None,
    ):
        super().__init__(timeout=300)
        self.db = db
        self.query = query
        self.user_id = user_id
        self.category_id = category_id
        self.category = category
        self.page = 0
        self.total = self.db.count_links(
            query=self.query,
            user_id=self.user_id,
            category_id=self.category_id,
            category=self.category,
        )
        self.page_size = PAGE_SIZE
        self.message: Optional[discord.Message] = None
        self._sync_buttons()

    def _sync_buttons(self):
        total_pages = max(1, (self.total + self.page_size - 1) // self.page_size)
        self.page = max(0, min(self.page, total_pages - 1))
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == "links_prev":
                item.disabled = self.page <= 0
            if isinstance(item, discord.ui.Button) and item.custom_id == "links_next":
                item.disabled = self.page >= total_pages - 1

    def _build_embed(self) -> discord.Embed:
        if self.total == 0:
            embed = discord.Embed(
                title="Saved Links",
                description="No links found.",
                color=0x2F3136,
                timestamp=discord.utils.utcnow(),
            )
            return embed

        entries = self.db.get_links(
            query=self.query,
            user_id=self.user_id,
            category_id=self.category_id,
            category=self.category,
            limit=self.page_size,
            offset=self.page * self.page_size,
        )
        embed = discord.Embed(
            title="Saved Links",
            color=0x2F3136,
            timestamp=discord.utils.utcnow(),
        )
        total_pages = max(1, (self.total + self.page_size - 1) // self.page_size)
        embed.set_footer(
            text=f"Page {self.page + 1}/{total_pages} • Total {self.total}"
        )

        for idx, entry in enumerate(entries, start=self.page * self.page_size + 1):
            title = entry.get("title") or entry.get("site_name") or entry.get("domain")
            title = title or entry.get("url")
            title = title[:250] if title else "Untitled"
            description = entry.get("description") or ""
            if len(description) > 240:
                description = description[:237] + "..."
            created_at = entry.get("created_at")
            created_str = created_at
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at)
                    created_str = created_dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    created_str = created_at

            value_lines = [
                f"[Open]({entry['url']})",
                f"[Message]({entry['message_link']})",
            ]
            if entry.get("category"):
                value_lines.append(f"📁 {entry['category'].capitalize()}")
            if entry.get("context"):
                value_lines.append(f"💡 {entry['context']}")
            elif entry.get("site_name"):
                value_lines.append(f"Site: {entry['site_name']}")
            if description and not entry.get("context"):
                value_lines.append(description)
            if created_str:
                value_lines.append(f"Saved: {created_str}")

            value = "\n".join(value_lines)
            if len(value) > 1000:
                value = value[:997] + "..."
            embed.add_field(name=f"{idx}. {title}", value=value, inline=False)

        return embed

    async def _update(self, interaction: discord.Interaction):
        self._sync_buttons()
        embed = self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Prev", style=discord.ButtonStyle.secondary, custom_id="links_prev"
    )
    async def prev_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.page > 0:
            self.page -= 1
        await self._update(interaction)

    @discord.ui.button(
        label="Next", style=discord.ButtonStyle.secondary, custom_id="links_next"
    )
    async def next_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        total_pages = max(1, (self.total + self.page_size - 1) // self.page_size)
        if self.page < total_pages - 1:
            self.page += 1
        await self._update(interaction)

    @discord.ui.button(
        label="Close", style=discord.ButtonStyle.red, custom_id="links_close"
    )
    async def close_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class LinkSaverCog(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.db = LinkDatabase()
        self._session: Optional[aiohttp.ClientSession] = None
        self._meta_semaphore = asyncio.Semaphore(3)

    def cog_unload(self):
        if self._session and not self._session.closed:
            asyncio.create_task(self._session.close())

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={"User-Agent": "NovatraBot/1.0"},
        )
        return self._session

    def _message_link(self, message: discord.Message) -> str:
        return f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"

    async def _fetch_and_store_metadata(self, link_id: int, url: str, domain: str):
        metadata = {}
        async with self._meta_semaphore:
            try:
                session = await self._get_session()
                async with session.get(url, allow_redirects=True) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    if "text/html" in content_type:
                        raw = await resp.content.read(200000)
                        html = raw.decode("utf-8", errors="ignore")
                        metadata = parse_metadata(html)
            except Exception:
                pass

        category, context = await classify_link(
            url=url,
            domain=domain,
            title=metadata.get("title"),
            description=metadata.get("description"),
            site_name=metadata.get("site_name"),
        )
        self.db.update_metadata(
            link_id,
            metadata.get("title"),
            metadata.get("description"),
            metadata.get("site_name"),
            metadata.get("image_url"),
            category,
            context,
        )

    def _prepare_links(self, message: discord.Message, urls: List[str]) -> List[dict]:
        prepared = []
        for url in urls:
            prepared.append(
                {
                    "url": url,
                    "normalized_url": normalize_url(url),
                    "domain": domain_for_url(url),
                    "message_id": message.id,
                    "message_link": self._message_link(message),
                    "channel_id": message.channel.id,
                    "category_id": message.channel.category_id,
                    "author_id": message.author.id,
                }
            )
        return prepared

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.channel.category_id != LINK_CATEGORY_ID:
            return
        if not message.content:
            return

        urls = extract_urls(message.content)
        urls = [url for url in urls if not is_media_url(url)]
        if not urls:
            return

        prepared = self._prepare_links(message, urls)
        saved = self.db.save_links(prepared)
        for entry in saved:
            domain = domain_for_url(entry["url"])
            asyncio.create_task(
                self._fetch_and_store_metadata(entry["id"], entry["url"], domain)
            )

    @commands.slash_command(
        name="links", description="View saved links from the link category"
    )
    @has_allowed_role()
    async def links(
        self,
        ctx: discord.ApplicationContext,
        query: Optional[str] = None,
        user: Optional[discord.User] = None,
        category: discord.Option(
            str,
            description="Filter by link category",
            choices=LINK_CATEGORIES,
            required=False,
            default=None,
        ) = None,
    ):
        await ctx.defer()
        view = LinkResultsView(
            self.db,
            query=query,
            user_id=user.id if user else None,
            category_id=LINK_CATEGORY_ID,
            category=category,
        )
        embed = view._build_embed()
        message = await ctx.followup.send(embed=embed, view=view)
        view.message = message


def setup(bot: discord.Bot):
    bot.add_cog(LinkSaverCog(bot))
