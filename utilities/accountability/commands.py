import discord
import random
from discord.ext import commands
from discord import SlashCommandGroup
from datetime import datetime, timedelta, timezone
from .database import AccountabilityDB
from .helpers import AccountabilityHelpers


class AccountabilityCommands:
    def __init__(self, bot):
        self.bot = bot
        self.db = AccountabilityDB()
        self.helpers = AccountabilityHelpers()
        self.admin_ids = [727012870683885578]
        self.accountability_channel_id = 1340317410611429376

    async def _update_accountability_channel(self, ctx, user_id, today):
        """Update the accountability channel with the user's tasks."""
        channel = ctx.guild.get_channel(self.accountability_channel_id)
        if not channel:
            return

        rows = self.db.get_tasks_for_day(user_id, today)

        tasks_today = []
        message_ids = set()
        latest_logged_time = self.helpers.get_current_timestamp()

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
            title=f"📝 {ctx.author.display_name}'s Completed Tasks",
            description=task_summary or "No tasks logged yet today. Use `/log add [task]` to log your first task!",
            color=0xAAB99A,
        )
        tasks_embed.add_field(name="Last Logged", value=f"<t:{latest_logged_time}:F>")

        message = await channel.send(embed=tasks_embed)

        
        self.db.update_task_message_id(user_id, today, message.id)
        
    async def add_command(self, ctx: discord.ApplicationContext, task: str):
        """Log a task for the user."""
        await ctx.defer()

        user_id = ctx.author.id
        today = self.helpers.get_today()
        current_time = self.helpers.get_current_timestamp()

        
        try:
            
            user_stats = self.db.get_user_stats(user_id)

            if user_stats:
                novacoins, streak, last_logged, highest_streak, total_tasks, weekly_target = user_stats
                last_logged = (
                    datetime.strptime(last_logged, "%Y-%m-%d").date()
                    if last_logged
                    else None
                )

                
                if last_logged != today:
                    streak_change = self.helpers.calculate_streak(last_logged, today)
                    
                    if streak_change == 1:
                        
                        streak += 1
                        
                    else:
                        
                        streak = 1
                        
                    
                    daily_bonus = self.helpers.calculate_novacoins_bonus(streak)
                    novacoins += daily_bonus

                    
                    self.db.update_user_stats(user_id, novacoins, streak, today, highest_streak)
            else:
                
                novacoins, streak = 10, 1
                highest_streak = 1
                self.db.create_user(user_id, novacoins, streak, today)

            
            tasks_today = self.db.get_tasks_for_day(user_id, today)
            task_count = len(tasks_today) + 1  
            
            
            task_reward = self.helpers.calculate_task_reward(task, task_count, streak)
            novacoins += task_reward
            
            
            self.db.log_task(user_id, task, today, current_time, task_reward)
            self.db.update_user_stats(user_id, novacoins, streak, today, highest_streak)

        except Exception as e:
            await ctx.respond(f"Error logging task: {str(e)}", ephemeral=True)
            return

        
        tasks = self.db.get_tasks_for_day(user_id, today)
        tasks_today = [row[0] for row in tasks]

        
        motivation_message = self.helpers.generate_motivation(tasks_today)

        
        weekly_count = self.db.get_weekly_tasks_count(user_id)
        weekly_target_message = ""
        if user_stats:
            weekly_target = user_stats[5]
            weekly_progress = min(weekly_count / weekly_target * 100, 100)
            weekly_target_message = f"\n📊 Weekly Progress: {weekly_count}/{weekly_target} tasks ({weekly_progress:.1f}%)"
        
        
        response_msg = discord.Embed(
            title="📝 Task Logged",
            description=f"**{len(tasks_today)}.** {task}",
            color=0xAAB99A,
        )
        response_msg.add_field(
            name="<a:NovaStreak:1340335713526222889> Streak",
            value=f"{streak} Days" + (f" (Record: {highest_streak})" if highest_streak > streak else ""),
            inline=True,
        )
        response_msg.add_field(
            name="<a:NovaCoins:1340334508838490223> NovaCoins",
            value=f"{int(novacoins)} (+{task_reward} for this task)",
            inline=True,
        )
        
        response_msg.add_field(
            name="✨ Quick Motivation",
            value=f"*{motivation_message}*" + weekly_target_message,
            inline=False,
        )

        await ctx.respond(embed=response_msg)

        
        await self._update_accountability_channel(ctx, user_id, today)

    async def delete_command(self, ctx: discord.ApplicationContext, task_number: int):
        """Delete a logged task."""
        await ctx.defer()

        user_id = ctx.author.id
        today = self.helpers.get_today()

        task_info = self.db.get_task_by_number(user_id, today, task_number)
        if not task_info:
            await ctx.respond("❌ Invalid task number or you have no logged tasks for today!")
            return

        task_id, task_text, message_id = task_info

        self.db.delete_task(task_id)

        
        user_stats = self.db.get_user_stats(user_id)
        if not user_stats:
            await ctx.respond("❌ Error: User stats not found!")
            return

        novacoins, streak = user_stats[0], user_stats[1]
        
        penalty = int(10 + 0.2 * streak)
        novacoins -= penalty

        self.db.update_user_stats(user_id, novacoins, streak, today)

        response_embed = discord.Embed(
            title="🗑️ Task Deleted",
            description=f"❌ `{task_text}` has been removed from your logs!",
            color=0xE74C3C,
        )

        response_embed.add_field(
            name="<a:NovaCoins:1340334508838490223> NovaCoins",
            value=f"{int(novacoins)} (-{penalty} coins)",
        )

        await ctx.respond(embed=response_embed)

        
        await self._update_accountability_channel(ctx, user_id, today)

    async def stats_command(self, ctx: discord.ApplicationContext, member: discord.Member = None):
        """Get a user's accountability stats."""
        await ctx.defer()

        member = member or ctx.author
        user_id = member.id

        user_stats = self.db.get_user_stats(user_id)
        if user_stats:
            novacoins, streak, _, highest_streak, total_tasks, weekly_target = user_stats
            weekly_count = self.db.get_weekly_tasks_count(user_id)
            weekly_progress = min(weekly_count / weekly_target * 100, 100) if weekly_target > 0 else 0
        else:
            novacoins, streak, highest_streak, total_tasks = 0, 0, 0, 0
            weekly_count, weekly_target, weekly_progress = 0, 5, 0

        stats_embed = discord.Embed(
            title=f"📊 {member.display_name}'s Stats", color=0xAAB99A
        )
        stats_embed.add_field(
            name="<a:NovaCoins:1340334508838490223> NovaCoins",
            value=f"{int(novacoins)}",
            inline=True,
        )
        stats_embed.add_field(
            name="<a:NovaStreak:1340335713526222889> Streak",
            value=f"{streak} Days" + (f" (Record: {highest_streak})" if highest_streak > streak else ""),
            inline=True,
        )
        
        stats_embed.add_field(
            name="📝 Total Tasks",
            value=f"{total_tasks}",
            inline=True,
        )
            
        stats_embed.add_field(
            name="📊 Weekly Progress",
            value=f"{weekly_count}/{weekly_target} tasks ({weekly_progress:.1f}%)",
            inline=False,
        )

        await ctx.respond(embed=stats_embed)

    async def history_command(self, ctx: discord.ApplicationContext):
        """Get a user's accountability history."""
        await ctx.defer()

        member = ctx.author
        user_id = member.id

        history = self.db.get_user_history(user_id)
        if not history:
            await ctx.respond("📜 No Tasks Logged Yet!", ephemeral=True)
            return

        history_text = "\n".join(
            [
                f"**{i + 1}.** {row[0]} - <t:{int(row[2])}:F>" + (f" (+{row[3]} coins)" if row[3] > 0 else "")
                for i, row in enumerate(history)
            ]
        )

        history_embed = discord.Embed(
            title=f"📜 {member.display_name}'s Tasks",
            description=history_text,
            color=0xAAB99A,
        )

        await ctx.respond(embed=history_embed)

    async def leaderboard_command(self, ctx: discord.ApplicationContext):
        """Get the accountability leaderboard."""
        await ctx.defer()

        leaderboard = self.db.get_leaderboard()
        streak_leaderboard = self.db.get_leaderboard(by_streak=True)
        
        if not leaderboard and not streak_leaderboard:
            await ctx.respond("🏆 No One Has Logged Any Tasks Yet!", ephemeral=True)
            return

        
        if leaderboard:
            coins_leaderboard_text = "\n".join(
                [
                    f"**{i + 1}. <@{row[0]}> - {int(row[1])} <a:NovaCoins:1340334508838490223>**"
                    for i, row in enumerate(leaderboard[:5])
                ]
            )
        else:
            coins_leaderboard_text = "No data available"
            
        
        if streak_leaderboard:
            streak_leaderboard_text = "\n".join(
                [
                    f"**{i + 1}. <@{row[0]}> - {row[1]} days <a:NovaStreak:1340335713526222889>**" + 
                    (f" (Record: {row[2]})" if row[2] > row[1] else "")
                    for i, row in enumerate(streak_leaderboard[:5])
                ]
            )
        else:
            streak_leaderboard_text = "No data available"

        
        leaderboard_embed = discord.Embed(
            title="🏆 Accountability Leaderboards 🏆",
            color=0xAAB99A,
        )
        
        leaderboard_embed.add_field(
            name="💰 NovaCoins Leaders",
            value=coins_leaderboard_text,
            inline=False,
        )
        
        leaderboard_embed.add_field(
            name="🔥 Streak Leaders",
            value=streak_leaderboard_text,
            inline=False,
        )

        await ctx.respond(embed=leaderboard_embed)

    async def reset_command(self, ctx: discord.ApplicationContext, member: discord.Member = None):
        """Reset a user's accountability stats."""
        await ctx.defer()

        if ctx.author.id not in self.admin_ids:
            await ctx.respond(
                "Brother / Sister this command is not for ya! Try contacting the users with GOD complexity (For eg: <@727012870683885578>)",
                ephemeral=True,
            )
            return

        member = member or ctx.author
        user_id = member.id

        self.db.reset_user(user_id)

        embed = discord.Embed(
            title="🔄 Accountability Reset",
            description=f"Accountability Stats For {member.mention} Have Been Reset!",
            color=0xE74C3C,
        )

        await ctx.respond(embed=embed)

    async def add_currency_command(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        novacoins: int = 0,
        streak: int = 0,
    ):
        """Add NovaCoins and streak to a user."""
        await ctx.defer()

        if ctx.author.id not in self.admin_ids:
            await ctx.respond(
                "Brother / Sister this command is not for ya! Try contacting the users with GOD complexity (For eg: <@727012870683885578>)",
                ephemeral=True,
            )
            return

        user_id = member.id
        user_stats = self.db.get_user_stats(user_id)

        if user_stats:
            current_novacoins, current_streak, _ = user_stats
            new_novacoins = current_novacoins + novacoins
            new_streak = current_streak + streak

            today = self.helpers.get_today()
            self.db.update_user_stats(user_id, new_novacoins, new_streak, today)
        else:
            new_novacoins = novacoins
            new_streak = streak
            today = self.helpers.get_today()
            self.db.create_user(user_id, new_novacoins, new_streak, today)

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

    async def remove_currency_command(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        novacoins: int = 0,
        streak: int = 0,
    ):
        """Remove NovaCoins and streak from a user."""
        await ctx.defer()

        if ctx.author.id not in self.admin_ids:
            await ctx.respond(
                "Brother / Sister this command is not for ya! Try contacting the users with GOD complexity (For eg: <@727012870683885578>)",
                ephemeral=True,
            )
            return

        user_id = member.id
        user_stats = self.db.get_user_stats(user_id)

        if user_stats:
            current_novacoins, current_streak, _ = user_stats
            new_novacoins = current_novacoins - novacoins
            new_streak = current_streak - streak

            today = self.helpers.get_today()
            self.db.update_user_stats(user_id, new_novacoins, new_streak, today)
        else:
            new_novacoins = -novacoins
            new_streak = -streak
            today = self.helpers.get_today()
            self.db.create_user(user_id, new_novacoins, new_streak, today)

        embed = discord.Embed(
            title="💰 Currency Removed",
            description=f"Successfully Removed Currency From {member.mention}",
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

    async def set_weekly_target_command(self, ctx: discord.ApplicationContext, target: int):
        """Set a weekly task target for the user."""
        await ctx.defer()
        
        if target <= 0 or target > 100:
            await ctx.respond("❌ Weekly target must be between 1 and 100 tasks.", ephemeral=True)
            return
            
        user_id = ctx.author.id
        self.db.update_weekly_target(user_id, target)
        
        embed = discord.Embed(
            title="🎯 Weekly Target Updated",
            description=f"Your weekly task target has been set to **{target}** tasks.",
            color=0xAAB99A,
        )
        
        await ctx.respond(embed=embed)

    async def store_command(self, ctx: discord.ApplicationContext):
        """Display available items in the store."""
        await ctx.defer()

        store_items = self.db.get_store_items()
        if not store_items:
            await ctx.respond("🏪 The store is currently empty. Check back later!", ephemeral=True)
            return

        store_embed = discord.Embed(
            title="🏪 NovaCoins Store",
            description="Use your NovaCoins to purchase rewards!",
            color=0xAAB99A,
        )

        for item_id, name, description, price in store_items:
            store_embed.add_field(
                name=f"{name} - {price} <a:NovaCoins:1340334508838490223>",
                value=f"ID: {item_id} | {description}",
                inline=False,
            )

        store_embed.set_footer(text="Use /log store buy <item_id> to purchase an item")
        await ctx.respond(embed=store_embed)

    async def buy_item_command(self, ctx: discord.ApplicationContext, item_id: int):
        """Buy an item from the store."""
        await ctx.defer()

        user_id = ctx.author.id
        
        
        self.cursor.execute("SELECT name, description, price FROM store_items WHERE id = ? AND is_active = 1", (item_id,))
        item = self.cursor.fetchone()
        
        if not item:
            await ctx.respond("❌ Invalid item ID or the item is no longer available.", ephemeral=True)
            return
            
        name, description, price = item
        
        
        user_stats = self.db.get_user_stats(user_id)
        if not user_stats or user_stats[0] < price:
            await ctx.respond(f"❌ You don't have enough NovaCoins to buy this item. You need {price} coins.", ephemeral=True)
            return
            
        
        novacoins = user_stats[0] - price
        today = self.helpers.get_today()
        
        
        self.db.update_user_stats(user_id, novacoins, user_stats[1], today)
        
        
        self.db.purchase_item(user_id, item_id)
        
        
        purchase_embed = discord.Embed(
            title="🛒 Item Purchased",
            description=f"You have purchased **{name}**!",
            color=0xAAB99A,
        )
        
        purchase_embed.add_field(
            name="Item Description",
            value=description,
            inline=False,
        )
        
        purchase_embed.add_field(
            name="Price Paid",
            value=f"{price} <a:NovaCoins:1340334508838490223>",
            inline=True,
        )
        
        purchase_embed.add_field(
            name="Remaining Balance",
            value=f"{novacoins} <a:NovaCoins:1340334508838490223>",
            inline=True,
        )
        
        purchase_embed.set_footer(text="View your items with /log inventory")
        
        await ctx.respond(embed=purchase_embed)
        
    async def inventory_command(self, ctx: discord.ApplicationContext):
        """Show a user's inventory."""
        await ctx.defer()
        
        user_id = ctx.author.id
        user_items = self.db.get_user_items(user_id)
        
        if not user_items:
            await ctx.respond("📦 Your inventory is empty. Buy items from the store with `/log store`!", ephemeral=True)
            return
            
        inventory_embed = discord.Embed(
            title=f"📦 {ctx.author.display_name}'s Inventory",
            description="Items you've purchased from the store",
            color=0xAAB99A,
        )
        
        unused_items = [item for item in user_items if not item[4]]  
        used_items = [item for item in user_items if item[4]]  
        
        if unused_items:
            unused_text = "\n".join([
                f"**{i+1}.** {item[1]} - Purchased {item[3]}"
                for i, item in enumerate(unused_items)
            ])
            inventory_embed.add_field(
                name="🆕 Unused Items",
                value=unused_text,
                inline=False,
            )
        
        if used_items:
            used_text = "\n".join([
                f"**{i+1}.** {item[1]} - Used"
                for i, item in enumerate(used_items)
            ])
            inventory_embed.add_field(
                name="✅ Used Items",
                value=used_text,
                inline=False,
            )
            
        inventory_embed.set_footer(text="Use /log use <item_id> to use an item")
        
        await ctx.respond(embed=inventory_embed)
        
    async def use_item_command(self, ctx: discord.ApplicationContext, item_number: int):
        """Use an item from your inventory."""
        await ctx.defer()
        
        user_id = ctx.author.id
        unused_items = self.db.get_user_items(user_id, unused_only=True)
        
        if not unused_items:
            await ctx.respond("❌ You don't have any unused items in your inventory.", ephemeral=True)
            return
            
        if item_number < 1 or item_number > len(unused_items):
            await ctx.respond("❌ Invalid item number. Check your inventory with `/log inventory`.", ephemeral=True)
            return
            
        selected_item = unused_items[item_number-1]
        item_id, name, description, _ = selected_item
        
        
        self.db.use_item(item_id)
        
        use_embed = discord.Embed(
            title="🎉 Item Used",
            description=f"You have used your **{name}**!",
            color=0xAAB99A,
        )
        
        use_embed.add_field(
            name="Item Description",
            value=description,
            inline=False,
        )
        
        use_embed.add_field(
            name="Next Steps",
            value="Contact a mod to redeem your reward if applicable.",
            inline=False,
        )
        
        await ctx.respond(embed=use_embed)
        
    async def add_item_command(
        self, 
        ctx: discord.ApplicationContext, 
        name: str, 
        price: int, 
        description: str
    ):
        """Add a new item to the store."""
        await ctx.defer()
        
        if ctx.author.id not in self.admin_ids:
            await ctx.respond(
                "Brother / Sister this command is not for ya! Try contacting the users with GOD complexity (For eg: <@727012870683885578>)",
                ephemeral=True,
            )
            return
            
        if price < 1:
            await ctx.respond("❌ Item price must be at least 1 NovaCoin.", ephemeral=True)
            return
            
        success = self.db.add_store_item(name, description, price)
        
        if success:
            item_embed = discord.Embed(
                title="🆕 Store Item Added",
                description=f"**{name}** has been added to the store!",
                color=0xAAB99A,
            )
            
            item_embed.add_field(
                name="Description",
                value=description,
                inline=False,
            )
            
            item_embed.add_field(
                name="Price",
                value=f"{price} <a:NovaCoins:1340334508838490223>",
                inline=True,
            )
            
            await ctx.respond(embed=item_embed)
        else:
            await ctx.respond("❌ An item with that name already exists in the store.", ephemeral=True)
            
    async def set_weekly_target_command(self, ctx: discord.ApplicationContext, target: int):
        """Set a weekly task target for the user."""
        await ctx.defer()
        
        if target <= 0 or target > 100:
            await ctx.respond("❌ Weekly target must be between 1 and 100 tasks.", ephemeral=True)
            return
            
        user_id = ctx.author.id
        self.db.update_weekly_target(user_id, target)
        
        embed = discord.Embed(
            title="🎯 Weekly Target Updated",
            description=f"Your weekly task target has been set to **{target}** tasks.",
            color=0xAAB99A,
        )
        
        await ctx.respond(embed=embed)

    async def on_member_remove(self, member):
        """Handle member leaving the server."""
        user_id = member.id
        try:
            self.db.reset_user(user_id)
            print(f"Removed Data For User {user_id} Who Left The Server")
        except Exception as e:
            print(f"Error Removing Data For The User {user_id}: {str(e)}")

    async def cleanup_missing_users(self):
        """Clean up data for users who are no longer in any server."""
        all_users = self.db.get_all_users()
        users_to_remove = []

        for user_id in all_users:
            user_found = False
            for guild in self.bot.guilds:
                if guild.get_member(user_id) is not None:
                    user_found = True
                    break

            if not user_found:
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            try:
                self.db.reset_user(user_id)
                print(f"Cleaned Up Data For User {user_id} Who Is No Longer In Any Server")
            except Exception as e:
                print(f"Error Cleaning Up Data For User {user_id}: {str(e)}")

    async def set_reminder_command(self, ctx: discord.ApplicationContext, time: str):
        """Set a daily reminder for task logging."""
        await ctx.defer()
        
        user_id = ctx.author.id
        
        
        import re
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time):
            await ctx.respond("❌ Please enter a valid time in 24-hour format (HH:MM), e.g., 09:00 or 18:30.", ephemeral=True)
            return
        
        
        self.db.set_reminder(user_id, time)
        
        
        hour, minute = map(int, time.split(':'))
        friendly_time = f"{hour if hour <= 12 else hour-12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
        
        embed = discord.Embed(
            title="⏰ Daily Reminder Set",
            description=f"You will receive a daily reminder to log your completed tasks at **{friendly_time}**.",
            color=0xAAB99A,
        )
        
        embed.add_field(
            name="How it works",
            value="The bot will send you a private message at your scheduled time each day as a reminder to log your tasks.",
            inline=False,
        )
        
        embed.add_field(
            name="Manage Reminders",
            value="Use `/log reminder delete` to remove your daily reminder.",
            inline=False,
        )
        
        await ctx.respond(embed=embed)
        
    async def delete_reminder_command(self, ctx: discord.ApplicationContext):
        """Delete your daily task logging reminder."""
        await ctx.defer()
        
        user_id = ctx.author.id
        
        
        reminder_time = self.db.get_user_reminder(user_id)
        if not reminder_time:
            await ctx.respond("⚠️ You don't have any active reminders to delete.", ephemeral=True)
            return
        
        
        self.db.delete_reminder(user_id)
        
        embed = discord.Embed(
            title="🔕 Reminder Deleted",
            description="Your daily task logging reminder has been turned off.",
            color=0xE74C3C,
        )
        
        await ctx.respond(embed=embed)
        
    async def check_reminder_command(self, ctx: discord.ApplicationContext):
        """Check your current reminder settings."""
        await ctx.defer()
        
        user_id = ctx.author.id
        
        
        reminder_time = self.db.get_user_reminder(user_id)
        
        if not reminder_time:
            await ctx.respond("ℹ️ You don't have any active reminders set. Use `/log reminder set` to create one!", ephemeral=True)
            return
        
        
        hour, minute = map(int, reminder_time.split(':'))
        friendly_time = f"{hour if hour <= 12 else hour-12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
        
        embed = discord.Embed(
            title="⏰ Your Daily Reminder",
            description=f"You have a reminder set for **{friendly_time}** each day.",
            color=0xAAB99A,
        )
        
        embed.add_field(
            name="Change Time",
            value="To change your reminder time, simply set a new one with `/log reminder set`.",
            inline=False,
        )
        
        await ctx.respond(embed=embed)
        
    async def send_reminders(self):
        """Send reminders to users who have set them for the current time."""
        
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        current_minute = now.minute
        
        
        reminders = self.db.get_all_active_reminders(current_hour, current_minute)
        
        
        for user_id, reminder_time in reminders:
            try:
                user = await self.bot.fetch_user(user_id)
                if not user:
                    continue
                
                
                embed = discord.Embed(
                    title="📝 Time to Log Your Completed Tasks!",
                    description="Have you completed any tasks today? Take a moment to log them and build your accountability streak!",
                    color=0xAAB99A,
                )
                
                embed.add_field(
                    name="🚀 How to Log Tasks",
                    value="Use `/log add [your task]` to log what you've accomplished today.",
                    inline=False,
                )
                
                
                motivational_messages = [
                    "Consistency builds success! 💪",
                    "Every task logged is progress made! ✨",
                    "Small steps lead to big achievements! 🏆",
                    "Your future self will thank you for your consistency today! 🌱",
                    "Building accountability makes goals achievable! 🎯"
                ]
                
                embed.add_field(
                    name="✨ Remember",
                    value=random.choice(motivational_messages),
                    inline=False,
                )
                
                
                await user.send(embed=embed)
                
            except Exception as e:
                print(f"Error sending reminder to user {user_id}: {str(e)}")
                
    async def schedule_reminders(self):
        """Task to check and send reminders every minute."""
        await self.bot.wait_until_ready()
        
        import asyncio
        while not self.bot.is_closed():
            try:
                await self.send_reminders()
            except Exception as e:
                print(f"Error in reminder scheduler: {str(e)}")
                
            
            await asyncio.sleep(60)
