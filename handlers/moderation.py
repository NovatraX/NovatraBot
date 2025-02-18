import re
import sqlite3
import discord
from discord.ext import commands


class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("moderation.db")
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
                FOREIGN KEY (user_id) REFERENCES warnings(user_id)
            )"""
        )
        self.conn.commit()

        self.bad_words = [
            r"d[\W_]*i[\W_]*c[\W_]*k",
            r"p[\W_]*u[\W_]*s[\W_]*s[\W_]*y",
            r"f[\W_]*u[\W_]*c[\W_]*k",
            r"b[\W_]*i[\W_]*t[\W_]*c[\W_]*h",
            r"c[\W_]*u[\W_]*m",
            r"s[\W_]*e[\W_]*x",
            r"a[\W_]*s[\W_]*s",
            r"t[\W_]*i[\W_]*t[\W_]*s",
            r"t[\W_]*i[\W_]*t",
            r"b[\W_]*o[\W_]*o[\W_]*b",
            r"b[\W_]*o[\W_]*o[\W_]*b[\W_]*s",
        ]
        self.pattern = re.compile("|".join(self.bad_words), re.IGNORECASE)

    def add_warning(self, user_id: int, message: str):
        self.cursor.execute("SELECT count FROM warnings WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            self.cursor.execute(
                "UPDATE warnings SET count = count + 1 WHERE user_id = ?",
                (user_id,),
            )
            self.cursor.execute(
                "INSERT INTO warning_reasons (user_id, message) VALUES (?, ?)",
                (user_id, message),
            )
        else:
            self.cursor.execute(
                "INSERT INTO warnings (user_id, count) VALUES (?, 1)",
                (user_id,),
            )
            self.cursor.execute(
                "INSERT INTO warning_reasons (user_id, message) VALUES (?, ?)",
                (user_id, message),
            )
        self.conn.commit()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.pattern.search(message.content):
            try:
                await message.delete()
                self.add_warning(message.author.id, message.content)

                embed = discord.Embed(
                    title="🚨 Inappropriate Content",
                    description="Your message was removed due to inappropriate content!\nYup <@727012870683885578> added it, so curse him or wahtever.",
                    color=discord.Color.red(),
                )

                await message.channel.send(
                    f"{message.author.mention} you have been warned!",
                    embed=embed,
                    delete_after=5,
                )

                channel = self.bot.get_channel(1341480535519924347)

                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT count FROM warnings WHERE user_id = ?", (message.author.id,)
                )

                row = cursor.fetchone()
                count = row[0]

                embed = discord.Embed(
                    title="🚨 Inappropriate Content",
                    description=f"User: {message.author.mention}\nMessage: {message.content}\nWarnings: {count}",
                    color=discord.Color.red(),
                )

                await channel.send(embed=embed)

            except discord.Forbidden:
                print("Missing permissions to delete messages.")
            except discord.HTTPException:
                print("Failed to delete the message.")


def setup(bot: discord.Bot) -> None:
    bot.add_cog(ModerationCog(bot))
