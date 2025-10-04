import discord
from discord.ext import commands

feedback_channel_id = 1340318888143093836


class FeedbackCog(commands.Cog):
    def __init__(
        self, bot: discord.Bot, feedback_channel_id: int = feedback_channel_id
    ) -> None:
        self.bot = bot
        self.feedback_channel_id = feedback_channel_id

    @commands.slash_command(name="feedback", description="Submit Your Feedback")
    async def feedback(self, ctx: discord.ApplicationContext):
        await ctx.send_modal(FeedbackModal(self.bot, self.feedback_channel_id))


class FeedbackModal(discord.ui.Modal):
    def __init__(self, bot: discord.Bot, feedback_channel_id: int):
        super().__init__(title="User Feedback")
        self.bot = bot
        self.feedback_channel_id = feedback_channel_id

        self.add_item(
            discord.ui.InputText(
                label="How was your overall experience ?",
                style=discord.InputTextStyle.short,
                placeholder="⭐ Rating : 1 - 10",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Would you recommend this app to others ?",
                style=discord.InputTextStyle.short,
                placeholder="Yes / No / Maybe",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Any issues while using the app ?",
                style=discord.InputTextStyle.long,
                placeholder="Write about the issues you faced while using the app ! ",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Any suggestions for improvement ?",
                style=discord.InputTextStyle.long,
                placeholder="Write your suggestions that we can use to improve the app !",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        experience = self.children[0].value
        would_recommend = self.children[1].value
        issues = self.children[2].value
        suggestions = self.children[3].value

        embed_user = discord.Embed(
            title="Feedback Submitted Successfully",
            description="Thank you for submitting your feedback!",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed_user, ephemeral=True)

        embed_admin = discord.Embed(
            title="New Feedback Received",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        embed_admin.add_field(name="User", value=str(interaction.user), inline=False)
        embed_admin.add_field(
            name="User ID", value=f"<@{interaction.user.id}>", inline=False
        )
        embed_admin.add_field(name="Experience", value=experience, inline=False)
        embed_admin.add_field(name="Recommend?", value=would_recommend, inline=False)
        embed_admin.add_field(
            name="Suggestions", value=suggestions or "No suggestions", inline=False
        )
        embed_admin.add_field(
            name="Issues", value=issues or "No issues reported", inline=False
        )

        try:
            avatar_url = interaction.user.display_avatar.url
        except Exception:
            avatar_url = None

        if avatar_url:
            embed_admin.set_footer(text="Feedback Received", icon_url=avatar_url)
        else:
            embed_admin.set_footer(text="Feedback Received")

        channel = self.bot.get_channel(self.feedback_channel_id)

        if channel is None and interaction.guild is not None:
            channel = interaction.guild.get_channel(self.feedback_channel_id)

        if channel is None:
            print(
                f"Warning : Admin Channel With ID {self.feedback_channel_id} Not FOund. Feedback From {interaction.user} Could Not Posted."
            )

            return

        await channel.send(embed=embed_admin)


def setup(bot: discord.Bot) -> None:
    bot.add_cog(FeedbackCog(bot))
