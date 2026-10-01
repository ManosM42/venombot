
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

load_dotenv()


def get_env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class AppReviewView(discord.ui.View):
    def __init__(self, user_id: int, app_id: int):
        super().__init__(timeout=None)

        self.user_id = user_id
        self.app_id = app_id

    async def is_staff(
        self,
        interaction: discord.Interaction
    ) -> bool:
        """Check whether the user has the configured staff role."""

        if interaction.guild is None:
            return False

        staff_role_id = get_env_int("STAFF_ROLE_ID")

        if staff_role_id == 0:
            return interaction.user.guild_permissions.administrator

        return any(
            role.id == staff_role_id
            for role in interaction.user.roles
        )

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="application:accept"
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not await self.is_staff(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to review applications.",
                ephemeral=True
            )
            return

        await database.update_application_status(
            self.app_id,
            "accepted"
        )

        user = interaction.guild.get_member(self.user_id)

        if user:
            try:
                await user.send(
                    "🎉 Your application has been **accepted**!"
                )
            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

        await interaction.response.edit_message(
            content=(
                f"✅ Application `{self.app_id}` accepted by "
                f"{interaction.user.mention}"
            ),
            view=None
        )

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="application:deny"
    )
    async def deny(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not await self.is_staff(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to review applications.",
                ephemeral=True
            )
            return

        await database.update_application_status(
            self.app_id,
            "denied"
        )

        user = interaction.guild.get_member(self.user_id)

        if user:
            try:
                await user.send(
                    "❌ Your application has been **denied**."
                )
            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

        await interaction.response.edit_message(
            content=(
                f"❌ Application `{self.app_id}` denied by "
                f"{interaction.user.mention}"
            ),
            view=None
        )


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = get_env_int("LOG_CHANNEL_ID")

    async def send_application_log(
        self,
        user: discord.User,
        app_id: int,
        content: str
    ):
        """Send an application to the configured log channel."""

        if not self.log_channel_id:
            return

        log_channel = self.bot.get_channel(self.log_channel_id)

        if log_channel is None:
            return

        embed = discord.Embed(
            title="📋 New Application",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="User",
            value=f"{user.mention} (`{user.id}`)",
            inline=False
        )

        # Discord field values have a maximum length.
        if len(content) > 1000:
            content = content[:997] + "..."

        embed.add_field(
            name="Application",
            value=content,
            inline=False
        )

        embed.set_footer(
            text=f"Application ID: {app_id}"
        )

        try:
            await log_channel.send(
                embed=embed,
                view=AppReviewView(user.id, app_id)
            )
        except discord.HTTPException:
            pass

    @commands.command(name="apply")
    async def apply(self, ctx):
        """Starts the application process through DMs."""

        user = ctx.author

        try:
            await user.send(
                "👋 Welcome to the application process!\n\n"
                "I will ask you a few questions. "
                "Please answer each one separately."
            )

            questions = [
                "1. What is your age?",
                "2. Why do you want to join?",
                "3. Do you have any previous experience?",
                "4. How many hours can you dedicate per week?"
            ]

            answers = []

            for question in questions:
                await user.send(question)

                def check(message):
                    return (
                        message.author.id == user.id
                        and isinstance(
                            message.channel,
                            discord.DMChannel
                        )
                    )

                try:
                    response = await self.bot.wait_for(
                        "message",
                        check=check,
                        timeout=600
                    )

                except TimeoutError:
                    await user.send(
                        "⌛ Your application timed out. "
                        "Please use `!apply` again if you want to restart."
                    )

                    await ctx.send(
                        f"{user.mention}, your application timed out."
                    )

                    return

                answers.append(response.content)

            full_content = "\n".join(
                f"**{questions[index]}**: {answers[index]}"
                for index in range(len(questions))
            )

            app_id = await database.save_application(
                user.id,
                full_content
            )

            await user.send(
                "✅ Thank you! Your application has been submitted "
                "for review."
            )

            await self.send_application_log(
                user,
                app_id,
                full_content
            )

            await ctx.send(
                f"✅ {user.mention}, your application was submitted "
                "successfully!"
            )

        except discord.Forbidden:
            await ctx.send(
                f"❌ {user.mention}, I couldn't DM you.\n"
                "Please enable DMs from server members and try again."
            )

        except discord.HTTPException:
            await ctx.send(
                "❌ Discord returned an error while processing "
                "your application."
            )


async def setup(bot):
    # Note:
    # Application review buttons created in previous bot sessions
    # require their app_id/user_id to be reconstructed from persistent
    # storage if you want them to survive a full restart.
    #
    # New applications created while the bot is running are fully
    # functional and persistent while the bot session is active.
    await bot.add_cog(Applications(bot))

