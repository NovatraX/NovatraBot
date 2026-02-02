import re

import discord
from discord.ext import commands

LINK_FIXERS = [
    {
        "pattern": re.compile(
            r"https?://(?:www\.)?(?:twitter\.com|x\.com)/(\S+)", re.IGNORECASE
        ),
        "replacement": "https://fixupx.com/{path}",
    },
    {
        "pattern": re.compile(
            r"https?://(?:www\.)?instagram\.com/((?:p|reels?|stories|share)/\S+|\w+/p/\S+)",
            re.IGNORECASE,
        ),
        "replacement": "https://vxinstagram.com/{path}",
    },
]


class EmbedFixerCog(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        fixed_links = []
        for fixer in LINK_FIXERS:
            matches = fixer["pattern"].findall(message.content)
            for match in matches:
                fixed_links.append(fixer["replacement"].format(path=match))

        if not fixed_links:
            return

        webhook = await message.channel.create_webhook(name="EmbedFixer")
        try:
            await webhook.send(
                "\n".join(fixed_links),
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
            await message.delete()
        finally:
            await webhook.delete()


def setup(bot: discord.Bot):
    bot.add_cog(EmbedFixerCog(bot))
