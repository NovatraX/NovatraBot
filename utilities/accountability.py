import os
import dotenv
import sqlite3
import discord
from groq import Groq
from discord.ext import commands
from discord import SlashCommandGroup
from datetime import datetime, timedelta, timezone

dotenv.load_dotenv()


class AccountabilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("accountability.db")
        self.cursor = self.conn.cursor()

        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS accountability (
                user_id INTEGER PRIMARY KEY, 
                novacoins INTEGER DEFAULT 0, 
                streak INTEGER DEFAULT 1, 
                last_logged TEXT
            )"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS accountability_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_id INTEGER, 
                task TEXT, 
                logged_date TEXT,
                logged_time TEXT,
                message_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES accountability(user_id)
            )"""
        )
        self.conn.commit()

        self.aiclient = Groq(api_key=os.getenv("API_KEY"))

    # ================================================================================================= #

    log = SlashCommandGroup(name="log", description="Accountability Commands")

    @log.command(name="add", description="Log Your Daily Tasks")
    async def add(self, ctx: discord.ApplicationContext, task: str):
        user_id = ctx.author.id
        today = datetime.now(timezone.utc).date()
        current_time = int(datetime.now(timezone.utc).timestamp())

        self.cursor.execute(
            "SELECT novacoins, streak, last_logged FROM accountability WHERE user_id = ?",
            (user_id,),
        )
        row = self.cursor.fetchone()

        if row:
            novacoins, streak, last_logged = row
            last_logged = (
                datetime.strptime(last_logged, "%Y-%m-%d").date()
                if last_logged
                else None
            )

            if last_logged == today:
                novacoins_updated = False
            else:
                streak = streak + 1 if last_logged == today - timedelta(days=1) else 1
                novacoins += 10
                novacoins_updated = True
                self.cursor.execute(
                    "UPDATE accountability SET novacoins = ?, streak = ?, last_logged = ? WHERE user_id = ?",
                    (novacoins, streak, today, user_id),
                )
        else:
            novacoins, streak = 10, 1
            novacoins_updated = True
            self.cursor.execute(
                "INSERT INTO accountability (user_id, novacoins, streak, last_logged) VALUES (?, ?, ?, ?)",
                (user_id, novacoins, streak, today),
            )

        self.cursor.execute(
            "INSERT INTO accountability_logs (user_id, task, logged_date, logged_time) VALUES (?, ?, ?, ?)",
            (user_id, task, today, current_time),
        )
        self.conn.commit()

        self.cursor.execute(
            "SELECT novacoins, streak FROM accountability WHERE user_id = ?", (user_id,)
        )
        novacoins, streak = self.cursor.fetchone()

        self.cursor.execute(
            "SELECT task FROM accountability_logs WHERE user_id = ? AND logged_date = ? ORDER BY logged_time ASC",
            (user_id, today),
        )
        tasks_today = [row[0] for row in self.cursor.fetchall()]
        formatted_tasks = "\n".join(f"- {t}" for t in tasks_today)

        motivation_prompt = f"""
        User has logged the following tasks today:
        {formatted_tasks}
        
        Provide a single-line, powerful motivational message based on these tasks.
        """

        response = self.aiclient.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You reply in single sentence as small as possible."
                        "You are a highly motivational and insightful assistant. "
                        "You spreak in english and use simple english terms so that all people can unserstand it. "
                        "Your role is to analyze a user's logged tasks and provide them with a single-line, impactful message "
                        "that fuels their determination, boosts their morale, and encourages them to keep going. "
                        "Make it personal, inspiring, and energizing. Keep it concise but powerful!"
                    ),
                },
                {"role": "user", "content": motivation_prompt},
            ],
            temperature=0.8,
            max_tokens=50,
            top_p=1,
        )
        motivation_message = response.choices[0].message.content.strip()

        response_msg = discord.Embed(
            title="📝 Task Logged",
            description=f"**{len(tasks_today)}.** {task}",
            color=0xAAB99A,
        )
        if novacoins_updated:
            response_msg.add_field(
                name="<a:NovaStreak:1340335713526222889> Streak",
                value=f"{streak} Days",
                inline=True,
            )
            response_msg.add_field(
                name="<a:NovaCoins:1340334508838490223> NovaCoins",
                value=f"{novacoins}",
            )

        response_msg.add_field(
            name="✨ Quick Motivation",
            value=f"*{motivation_message}*",
            inline=False,
        )

        await ctx.respond(embed=response_msg)

        self.cursor.execute(
            "SELECT task, message_id, logged_time FROM accountability_logs WHERE user_id = ? AND logged_date = ? ORDER BY logged_time ASC",
            (user_id, today),
        )
        rows = self.cursor.fetchall()

        tasks_today = []
        message_ids = []
        latest_logged_time = current_time
        for index, (task_entry, msg_id, log_time) in enumerate(rows, start=1):
            tasks_today.append(f"**{index}.** {task_entry}")
            if msg_id is not None:
                message_ids.append(msg_id)
            latest_logged_time = max(latest_logged_time, int(log_time))

        task_summary = "\n".join(tasks_today)

        channel = ctx.guild.get_channel(1340317410611429376)

        for message_id in message_ids:
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
            except discord.NotFound:
                print(f"+ Message With ID {message_id} Missing")
            except discord.Forbidden:
                print(f"+ Missing Permissions To Delete {message_id}")
            except Exception as e:
                print(f"+ Error Deleting {message_id} : {e}")

        tasks_embed = discord.Embed(
            title=f"📝 {ctx.author.display_name}'s Tasks For Today",
            description=task_summary,
            color=0xAAB99A,
        )
        tasks_embed.add_field(name="Last Logged", value=f"<t:{latest_logged_time}:F>")

        message = await channel.send(embed=tasks_embed)

        self.cursor.execute(
            "UPDATE accountability_logs SET message_id = ? WHERE user_id = ? AND logged_date = ?",
            (message.id, user_id, today),
        )
        self.conn.commit()

    # ================================================================================================= #

    @log.command(name="stats", description="Get Your Accountability Stats")
    async def stats(
        self, ctx: discord.ApplicationContext, member: discord.Member = None
    ):
        member = member or ctx.author
        user_id = member.id

        self.cursor.execute(
            "SELECT novacoins, streak FROM accountability WHERE user_id = ?", (user_id,)
        )
        row = self.cursor.fetchone()

        if row:
            novacoins, streak = row
        else:
            novacoins, streak = 0, 0

        stats_embed = discord.Embed(
            title=f"📊 {member.display_name}'s Stats", color=0xAAB99A
        )
        stats_embed.add_field(
            name="<a:NovaCoins:1340334508838490223> NovaCoins",
            value=f"{novacoins}",
            inline=True,
        )
        stats_embed.add_field(
            name="<a:NovaStreak:1340335713526222889> Streak",
            value=f"{streak} Days",
            inline=False,
        )

        await ctx.respond(embed=stats_embed)

    # ================================================================================================= #

    @log.command(name="leaderboard", description="Get Accountability Leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext):
        self.cursor.execute(
            "SELECT user_id, novacoins FROM accountability ORDER BY novacoins DESC LIMIT 10"
        )
        rows = self.cursor.fetchall()

        if not rows:
            await ctx.respond("🏆 No One Has Logged Any Taks Yet !", ephemeral=True)
            return

        leaderboard_text = "\n".join(
            [
                f"**{i + 1}. <@{row[0]}> - {row[1]} <a:NovaCoins:1340334508838490223>**"
                for i, row in enumerate(rows[:10])
            ]
        )

        leaderboard_embed = discord.Embed(
            title="🏆 Accountability Leaderboard 🏆 ",
            description=leaderboard_text,
            color=0xAAB99A,
        )

        await ctx.respond(embed=leaderboard_embed)

    # ================================================================================================= #

    @log.command(name="delete", description="Delete a logged task")
    async def log_delete(self, ctx: discord.ApplicationContext, task_number: int):
        user_id = ctx.author.id
        today = datetime.now(timezone.utc).date()

        self.cursor.execute(
            "SELECT id, task, message_id FROM accountability_logs WHERE user_id = ? AND logged_date = ? ORDER BY logged_time ASC",
            (user_id, today),
        )
        rows = self.cursor.fetchall()

        if not rows:
            await ctx.respond("❌ You have no logged tasks for today!")
            return

        if task_number < 1 or task_number > len(rows):
            await ctx.respond("❌ Invalid task number!")
            return

        task_id, task_text, message_id = rows[task_number - 1]

        self.cursor.execute("DELETE FROM accountability_logs WHERE id = ?", (task_id,))
        self.conn.commit()

        self.cursor.execute(
            "SELECT task, message_id, logged_time FROM accountability_logs WHERE user_id = ? AND logged_date = ? ORDER BY logged_time ASC",
            (user_id, today),
        )
        updated_rows = self.cursor.fetchall()

        response_embed = discord.Embed(
            title="🗑️ Task Deleted",
            description=f"❌ `{task_text}` has been removed from your logs!",
            color=0xE74C3C,
        )
        await ctx.respond(embed=response_embed)

        channel = ctx.guild.get_channel(1340317410611429376)

        if not updated_rows:
            if message_id:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                except discord.NotFound:
                    print(f"+ Message With ID {message_id} Missing")
                except discord.Forbidden:
                    print(f"+ Missing Permissions To Delete {message_id}")
                except Exception as e:
                    print(f"+ Error Deleting {message_id} : {e}")
            return

        updated_tasks = []
        latest_logged_time = 0
        message_ids = []

        for index, (task_entry, msg_id, log_time) in enumerate(updated_rows, start=1):
            updated_tasks.append(f"**{index}.** {task_entry}")
            if msg_id is not None:
                message_ids.append(msg_id)
            latest_logged_time = log_time

        task_summary = "\n".join(updated_tasks)

        for msg_id in message_ids:
            try:
                message = await channel.fetch_message(msg_id)
                await message.delete()
            except discord.NotFound:
                print(f"+ Message With ID {msg_id} Missing")
            except discord.Forbidden:
                print(f"+ Missing Permissions To Delete {msg_id}")
            except Exception as e:
                print(f"+ Error Deleting {msg_id} : {e}")

        tasks_embed = discord.Embed(
            title=f"📝 {ctx.author.display_name}'s Tasks For Today",
            description=task_summary,
            color=0xAAB99A,
        )
        tasks_embed.add_field(name="Last Logged", value=f"<t:{latest_logged_time}:F>")

        new_message = await channel.send(embed=tasks_embed)

        self.cursor.execute(
            "UPDATE accountability_logs SET message_id = ? WHERE user_id = ? AND logged_date = ?",
            (new_message.id, user_id, today),
        )
        self.conn.commit()

    def cog_unload(self):
        self.conn.close()


def setup(bot: discord.Bot) -> None:
    bot.add_cog(AccountabilityCog(bot))
