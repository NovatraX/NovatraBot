import discord
from discord.ext import commands


class EmojiReact(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_emoji = "😶"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if any(
            word in message.content.lower()
            for word in ["bidhle", "bidh le", "bhidle", "bhid le"]
        ):
            try:
                emoji = discord.utils.get(message.guild.emojis, name="bhidle")
                if emoji:
                    await message.add_reaction(emoji)
                else:
                    await message.add_reaction(self.target_emoji)
                    print("Emoji Not Found")

            except discord.Forbidden:
                print("Bot Lacks Permission For Reaction")
            except discord.HTTPException as e:
                print(f"Failed To React : {e}")


def setup(bot: discord.Bot) -> None:
    bot.add_cog(EmojiReact(bot))
