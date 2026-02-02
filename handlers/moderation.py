import sqlite3

import aiohttp
import discord
from discord.ext import commands


class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("data/moderation.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS warnings (
                user_id INTEGER,
                count INTEGER DEFAULT 1
            )"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS warning_reasons (
                user_id INTEGER,
                message TEXT,
                score INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES warnings(user_id)
            )"""
        )
        self.conn.commit()

    async def check_profanity(self, message: str) -> bool:
        url = "https://vector.profanity.dev"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"message": message}) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("isProfanity", False), result.get("score", 0)

                return False

    def add_warning(self, user_id: int, message: str, score: int = 0) -> None:
        self.cursor.execute("SELECT count FROM warnings WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            self.cursor.execute(
                "UPDATE warnings SET count = count + 1 WHERE user_id = ?",
                (user_id,),
            )
        else:
            self.cursor.execute(
                "INSERT INTO warnings (user_id, count) VALUES (?, 1)",
                (user_id,),
            )

        self.cursor.execute(
            "INSERT INTO warning_reasons (user_id, message, score) VALUES (?, ?, ?)",
            (user_id, message, score),
        )
        self.conn.commit()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        check = await self.check_profanity(message.content)

        if check[0]:
            try:
                score = check[1]

                await message.delete()
                self.add_warning(message.author.id, message.content, score)

                embed = discord.Embed(
                    title="🚨 Inappropriate Content",
                    description=f"Your message was removed due to inappropriate content! Please refrain from using profanity.\n\nProfanity Score: {score}",
                    color=discord.Color.red(),
                )

                await message.channel.send(
                    f"{message.author.mention} you have been warned!",
                    embed=embed,
                    delete_after=5,
                )

                channel = self.bot.get_channel(1341480535519924347)
                self.cursor.execute(
                    "SELECT count FROM warnings WHERE user_id = ?", (message.author.id,)
                )
                row = self.cursor.fetchone()
                count = row[0] if row else 1

                embed = discord.Embed(
                    title="🚨 Inappropriate Content",
                    description=f"User: {message.author.mention}\nMessage: {message.content}\nWarnings: {count}\nScore: {score}",
                    color=discord.Color.red(),
                )

                await channel.send(embed=embed)
            except discord.Forbidden:
                print("Missing permissions to delete messages.")
            except discord.HTTPException:
                print("Failed to delete the message.")


def setup(bot: discord.Bot) -> None:
    bot.add_cog(ModerationCog(bot))
