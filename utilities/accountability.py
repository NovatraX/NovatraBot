import os
import random
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

        self.admin = [727012870683885578]

    # ================================================================================================= #

    log = SlashCommandGroup(name="log", description="Accountability Commands")

    @log.command(name="add", description="Log Your Daily Tasks")
    async def add(self, ctx: discord.ApplicationContext, task: str):
        await ctx.defer()

        user_id = ctx.author.id
        today = datetime.now(timezone.utc).date()
        current_time = int(datetime.now(timezone.utc).timestamp())

        # Transaction TO Ensure Data Consistency
        try:
            self.conn.execute("BEGIN TRANSACTION")

            # Process User Streak And NovaCoins In One Go
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

                # Update Srteak And NovaCoins If User Logs Daily
                if last_logged != today:
                    if last_logged == today - timedelta(days=1):
                        streak += 1

                    # Calculate And Update NovaCoins
                    daily_bonus = int(10 * (0.02 * streak))
                    novacoins += daily_bonus

                    self.cursor.execute(
                        "UPDATE accountability SET novacoins = ?, streak = ?, last_logged = ? WHERE user_id = ?",
                        (novacoins, streak, today, user_id),
                    )
            else:
                # First Time User
                novacoins, streak = 10, 1
                self.cursor.execute(
                    "INSERT INTO accountability (user_id, novacoins, streak, last_logged) VALUES (?, ?, ?, ?)",
                    (user_id, novacoins, streak, today),
                )

            # Add Task To Logs
            self.cursor.execute(
                "INSERT INTO accountability_logs (user_id, task, logged_date, logged_time) VALUES (?, ?, ?, ?)",
                (user_id, task, today, current_time),
            )

            # Add Random NovaCoins Bonus
            random_bonus = random.randint(1, 5)
            novacoins += random_bonus
            self.cursor.execute(
                "UPDATE accountability SET novacoins = ? WHERE user_id = ?",
                (novacoins, user_id),
            )

            # Commit Transaction
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            await ctx.respond(f"Error logging task: {str(e)}", ephemeral=True)
            return

        # Fetch All Tasks For The Day And Generate Motivation Message
        self.cursor.execute(
            "SELECT task FROM accountability_logs WHERE user_id = ? AND logged_date = ? ORDER BY logged_time ASC",
            (user_id, today),
        )
        tasks_today = [row[0] for row in self.cursor.fetchall()]
        formatted_tasks = "\n".join(f"- {t}" for t in tasks_today)

        # Generate Motivation Message
        motivation_prompt = f"User has logged the following tasks today:\n{formatted_tasks}\n\nProvide a single-line, powerful motivational message based on these tasks."
        try:
            response = self.aiclient.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You reply in single sentence as small as possible. You are a highly motivational and insightful assistant. You speak in English and use simple terms so that all people can understand it. Your role is to analyze a user's logged tasks and provide them with a single-line, impactful message that fuels their determination, boosts their morale, and encourages them to keep going. Make it personal, inspiring, and energizing. Keep it concise but powerful!",
                    },
                    {"role": "user", "content": motivation_prompt},
                ],
                temperature=0.8,
                max_tokens=50,
                top_p=1,
            )
            motivation_message = response.choices[0].message.content.strip()
        except Exception:
            fallback_messages = [
                "Every task completed brings you closer to your goals!",
                "Your consistency is building something amazing!",
                "Small steps today, giant leaps tomorrow!",
                "Your dedication is truly inspiring!",
                "Keep pushing forward, you're doing great!",
            ]
            motivation_message = random.choice(fallback_messages)

        # Create Response Embed
        response_msg = discord.Embed(
            title="📝 Task Logged",
            description=f"**{len(tasks_today)}.** {task}",
            color=0xAAB99A,
        )
        response_msg.add_field(
            name="<a:NovaStreak:1340335713526222889> Streak",
            value=f"{streak} Days",
            inline=True,
        )
        response_msg.add_field(
            name="<a:NovaCoins:1340334508838490223> NovaCoins",
            value=f"{int(novacoins)}",
        )
        response_msg.add_field(
            name="✨ Quick Motivation",
            value=f"*{motivation_message}*",
            inline=False,
        )

        await ctx.respond(embed=response_msg)

        # Update Accountability Channel
        await self._update_accountability_channel(ctx, user_id, today, current_time)

    async def _update_accountability_channel(self, ctx, user_id, today, current_time):
        channel = ctx.guild.get_channel(1340317410611429376)
        if not channel:
            return

        self.cursor.execute(
            "SELECT task, message_id, logged_time FROM accountability_logs WHERE user_id = ? AND logged_date = ? ORDER BY logged_time ASC",
            (user_id, today),
        )
        rows = self.cursor.fetchall()

        tasks_today = []
        message_ids = set()
        latest_logged_time = current_time

        for index, (task_entry, msg_id, log_time) in enumerate(rows, start=1):
            tasks_today.append(f"**{index}.** {task_entry}")
            if msg_id is not None:
                message_ids.add(msg_id)
            if log_time:
                latest_logged_time = max(latest_logged_time, int(log_time))

        task_summary = "\n".join(tasks_today)

        for message_id in message_ids:
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
            except (discord.NotFound, discord.Forbidden, Exception) as e:
                print(f"+ Error with message {message_id}: {type(e).__name__}: {e}")

        tasks_embed = discord.Embed(
            title=f"📝 {ctx.author.display_name}'s Tasks For Today",
            description=task_summary,
            color=0xAAB99A,
        )
        tasks_embed.add_field(name="Last Logged", value=f"<t:{latest_logged_time}:F>")

        message = await channel.send(embed=tasks_embed)

        # Update All Logged Tasks With New Message ID
        self.cursor.execute(
            "UPDATE accountability_logs SET message_id = ? WHERE user_id = ? AND logged_date = ?",
            (message.id, user_id, today),
        )
        self.conn.commit()

    # ================================================================================================= #

    @log.command(name="delete", description="Delete a logged task")
    async def log_delete(self, ctx: discord.ApplicationContext, task_number: int):
        await ctx.defer()

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

        self.cursor.execute(
            "SELECT novacoins, streak FROM accountability WHERE user_id = ?", (user_id,)
        )

        novacoins, streak = self.cursor.fetchone()
        novacoins -= 10 + 0.2 * streak

        self.cursor.execute(
            "UPDATE accountability SET novacoins = ? WHERE user_id = ?",
            (novacoins, user_id),
        )

        response_embed = discord.Embed(
            title="🗑️ Task Deleted",
            description=f"❌ `{task_text}` has been removed from your logs!",
            color=0xE74C3C,
        )

        response_embed.add_field(
            name="<a:NovaCoins:1340334508838490223> NovaCoins",
            value=f"{int(novacoins)}",
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

    # ================================================================================================= #

    @log.command(name="stats", description="Get Your Accountability Stats")
    async def stats(
        self, ctx: discord.ApplicationContext, member: discord.Member = None
    ):
        await ctx.defer()

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

    @log.command(name="history", description="Get Your Accountability History")
    async def history(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        member = ctx.author
        user_id = member.id

        self.cursor.execute(
            "SELECT task, logged_date, logged_time FROM accountability_logs WHERE user_id = ? ORDER BY logged_time DESC LIMIT 10",
            (user_id,),
        )
        rows = self.cursor.fetchall()

        if not rows:
            await ctx.respond("📜 No Tasks Logged Yet!", ephemeral=True)
            return

        history_text = "\n".join(
            [
                f"**{i + 1}.** {row[0]} - <t:{int(row[2])}:F>"
                for i, row in enumerate(rows)
            ]
        )

        history_embed = discord.Embed(
            title=f"📜 {member.display_name}'s Tasks",
            description=history_text,
            color=0xAAB99A,
        )

        await ctx.respond(embed=history_embed)

    # ================================================================================================= #

    @log.command(name="leaderboard", description="Get Accountability Leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext):
        await ctx.defer()

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

    log_admin = log.create_subgroup(
        name="admin", description="Accountability Admin Commands"
    )

    @log_admin.command(name="reset", description="Reset Accountability Stats")
    async def reset(
        self, ctx: discord.ApplicationContext, member: discord.Member = None
    ):
        await ctx.defer()

        if ctx.author.id not in self.admin:
            await ctx.respond(
                "Bother / Sister this command is not for ya! Try contacting the users with GOD complexity ( For eg : <@727012870683885578> ) ",
                ephemeral=True,
            )
            return

        if member is None:
            member = ctx.author

        user_id = member.id

        self.cursor.execute("DELETE FROM accountability WHERE user_id = ?", (user_id,))

        self.cursor.execute(
            "DELETE FROM accountability_logs WHERE user_id = ?", (user_id,)
        )

        self.conn.commit()

        embed = discord.Embed(
            title="🔄 Accountability Reset",
            description=f"Accountability Stats For {member.mention} Have Been Reset!",
            color=0xE74C3C,
        )

        await ctx.respond(embed=embed)

    # ================================================================================================= #

    @log_admin.command(name="add", description="Add NovaCoins And Streak To A User")
    async def add_currency(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        novacoins: int = 0,
        streak: int = 0,
    ):
        await ctx.defer()

        if ctx.author.id not in self.admin:
            await ctx.respond(
                "Bother / Sister this command is not for ya! Try contacting the users with GOD complexity ( For eg : <@727012870683885578> ) ",
                ephemeral=True,
            )
            return

        user_id = member.id

        self.cursor.execute(
            "SELECT novacoins, streak FROM accountability WHERE user_id = ?", (user_id,)
        )
        row = self.cursor.fetchone()

        if row:
            current_novacoins, current_streak = row
            new_novacoins = current_novacoins + novacoins
            new_streak = current_streak + streak

            self.cursor.execute(
                "UPDATE accountability SET novacoins = ?, streak = ? WHERE user_id = ?",
                (new_novacoins, new_streak, user_id),
            )
        else:
            new_novacoins = novacoins
            new_streak = streak
            today = datetime.now(timezone.utc).date()
            self.cursor.execute(
                "INSERT INTO accountability (user_id, novacoins, streak, last_logged) VALUES (?, ?, ?, ?)",
                (user_id, new_novacoins, new_streak, today),
            )

        self.conn.commit()

        embed = discord.Embed(
            title="💰 Currency Added",
            description=f"Successfully Added Currency To {member.mention}",
            color=0xAAB99A,
        )

        embed.add_field(
            name="Updated NovaCoins",
            value=f"{new_novacoins}",
            inline=True,
        )
        embed.add_field(
            name="Updated Streak",
            value=f"{new_streak} Days",
            inline=False,
        )

        await ctx.respond(embed=embed)

    # ================================================================================================= #

    @log_admin.command(
        name="remove", description="Remove NovaCoins And Streak From A User"
    )
    async def remove_currency(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        novacoins: int = 0,
        streak: int = 0,
    ):
        await ctx.defer()

        if ctx.author.id not in self.admin:
            await ctx.respond(
                "Bother / Sister this command is not for ya! Try contacting the users with GOD complexity ( For eg : <@727012870683885578> ) ",
                ephemeral=True,
            )
            return

        user_id = member.id

        self.cursor.execute(
            "SELECT novacoins, streak FROM accountability WHERE user_id = ?", (user_id,)
        )
        row = self.cursor.fetchone()

        if row:
            current_novacoins, current_streak = row
            new_novacoins = current_novacoins - novacoins
            new_streak = current_streak - streak

            self.cursor.execute(
                "UPDATE accountability SET novacoins = ?, streak = ? WHERE user_id = ?",
                (new_novacoins, new_streak, user_id),
            )
        else:
            new_novacoins = novacoins
            new_streak = streak
            today = datetime.now(timezone.utc).date()
            self.cursor.execute(
                "INSERT INTO accountability (user_id, novacoins, streak, last_logged) VALUES (?, ?, ?, ?)",
                (user_id, new_novacoins, new_streak, today),
            )

        self.conn.commit()

        embed = discord.Embed(
            title="💰 Currency Removed",
            description=f"Successfully Remove Currency From {member.mention}",
            color=0xAAB99A,
        )

        embed.add_field(
            name="Updated NovaCoins",
            value=f"{new_novacoins}",
            inline=True,
        )
        embed.add_field(
            name="Updated Streak",
            value=f"{new_streak} Days",
            inline=False,
        )

        await ctx.respond(embed=embed)

    # ================================================================================================= #

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        user_id = member.id

        try:
            self.cursor.execute(
                "DELETE FROM accountability WHERE user_id = ?", (user_id,)
            )

            self.cursor.execute(
                "DELETE FROM accountability_logs WHERE user_id = ?", (user_id,)
            )

            self.conn.commit()
            print(f"Removed Data For User {user_id} Who Left The Server")
        except Exception as e:
            print(f"Error Removing Data For The User {user_id}: {str(e)}")

    async def cog_load(self):
        await self.bot.wait_until_ready()

        self.cursor.execute("SELECT DISTINCT user_id FROM accountability")
        db_users = [row[0] for row in self.cursor.fetchall()]

        users_to_remove = []

        for user_id in db_users:
            user_found = False
            for guild in self.bot.guilds:
                if guild.get_member(user_id) is not None:
                    user_found = True
                    break

            if not user_found:
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            try:
                self.cursor.execute(
                    "DELETE FROM accountability WHERE user_id = ?", (user_id,)
                )
                self.cursor.execute(
                    "DELETE FROM accountability_logs WHERE user_id = ?", (user_id,)
                )
                print(
                    f"Cleaned Up Data For User {user_id} Who Is No Longer In Any Server"
                )
            except Exception as e:
                print(f"Error Cleaning Up Data For User {user_id}: {str(e)}")

        self.conn.commit()


def setup(bot: discord.Bot) -> None:
    bot.add_cog(AccountabilityCog(bot))
