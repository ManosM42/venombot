import discord
from discord.ext import commands

from bot.services.economy_service import economy_service
from bot.config.settings import settings


class EconomyCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        try:
            await economy_service._ensure_user(member.guild.id, member.id)
        except Exception as e:
            print(f"[JOIN BONUS ERROR] {type(e).__name__}: {e}")

    @commands.command(name="balance")
    async def balance(self, ctx, member: discord.Member = None):
        user = member or ctx.author
        try:
            bal = await economy_service.get_balance(ctx.guild.id, user.id)
            embed = discord.Embed(
                title="💰 Wallet",
                description=f"{user.mention} has **{bal:,} coins**.",
                color=discord.Color.gold(),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"[BALANCE ERROR] {type(e).__name__}: {e}")
            await ctx.send("❌ An error occurred while checking the balance.")

    @commands.command(name="daily")
    async def daily(self, ctx):
        try:
            await economy_service.add_coins(
                ctx.guild.id, ctx.author.id, settings.DAILY_REWARD, "DAILY_REWARD"
            )
            await ctx.send(
                f"✅ {ctx.author.mention}, you received **{settings.DAILY_REWARD:,} coins**!"
            )
        except Exception as e:
            print(f"[DAILY ERROR] {type(e).__name__}: {e}")
            await ctx.send("❌ An error occurred while claiming your daily reward.")

    @commands.command(name="pay")
    async def pay(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("❌ The amount must be greater than 0.")
        if member.bot:
            return await ctx.send("❌ You cannot pay coins to a bot.")
        if member.id == ctx.author.id:
            return await ctx.send("❌ You cannot pay yourself.")

        try:
            success = await economy_service.spend_coins(
                ctx.guild.id, ctx.author.id, amount, "USER_PAY"
            )
            if not success:
                return await ctx.send("❌ You don't have enough coins.")

            await economy_service.add_coins(ctx.guild.id, member.id, amount, "USER_PAY")

            await ctx.send(
                f"✅ {ctx.author.mention} sent **{amount:,} coins** to {member.mention}."
            )
        except Exception as e:
            print(f"[PAY ERROR] {type(e).__name__}: {e}")
            await ctx.send("❌ An error occurred while transferring the coins.")

    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx):
        try:
            top_users = await economy_service.get_leaderboard(ctx.guild.id)
            if not top_users:
                return await ctx.send("📊 No economy data available yet.")

            description = ""
            for i, row in enumerate(top_users, 1):
                user = ctx.guild.get_member(row["user_id"])
                name = user.display_name if user else "Unknown User"
                description += f"**{i}.** {name} — **{row['balance']:,} coins**\n"

            embed = discord.Embed(
                title="🏆 Coin Leaderboard", description=description, color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"[LEADERBOARD ERROR] {type(e).__name__}: {e}")
            await ctx.send("❌ An error occurred while loading the leaderboard.")

    @commands.command(name="addcoins")
    @commands.has_permissions(administrator=True)
    async def addcoins(self, ctx, member: discord.Member = None, amount: int = None):
        """
        Admin-only: add coins to a member's balance.

        Usage:
            !addcoins @user 500
        """

        if member is None or amount is None:
            return await ctx.send(
                "🛠️ **ADD COINS** (admin only)\n\n"
                "Usage:\n`!addcoins @user amount`"
            )

        if member.bot:
            return await ctx.send("❌ You cannot add coins to a bot.")

        if amount <= 0:
            return await ctx.send("❌ The amount must be greater than 0.")

        try:
            await economy_service.add_coins(
                ctx.guild.id, member.id, amount, "ADMIN_ADD"
            )

            new_balance = await economy_service.get_balance(ctx.guild.id, member.id)

            embed = discord.Embed(
                title="🛠️ Coins Added",
                description=(
                    f"{ctx.author.mention} added **{amount:,} coins** to {member.mention}.\n\n"
                    f"💰 New balance: **{new_balance:,} coins**"
                ),
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[ADDCOINS ERROR] {type(e).__name__}: {e}")
            await ctx.send("❌ An error occurred while adding the coins.")

    @addcoins.error
    async def addcoins_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need **Administrator** permission to use this command.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ I couldn't find that member.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid member or amount. Usage: `!addcoins @user amount`")        

    @balance.error
    async def balance_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ I couldn't find that member.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid member.")

    @pay.error
    async def pay_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!pay @user amount`")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ I couldn't find that member.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid amount or member.")


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))