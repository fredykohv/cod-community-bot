import discord
import time
from discord.ext import commands, tasks
from discord import Embed, ButtonStyle, ui

class QueueView(ui.View):
	def __init__(self, queue_cog):
		super().__init__(timeout=None)
		self.queue_cog = queue_cog

	async def interaction_check(self, interaction):
		return interaction.channel.id == self.queue_cog.queue_channel_id

	@ui.button(label="Join Queue", style=ButtonStyle.green, custom_id="join_queue")
	async def join_button_callback(self, interaction: discord.Interaction, button: ui.Button):
		await interaction.response.defer(ephemeral=True)
		if interaction.user.voice and interaction.user.voice.channel.name == 'Lobby':
			if interaction.user.id not in self.queue_cog.queue:
				self.queue_cog.queue.append(interaction.user.id)
				await self.queue_cog.update_queue_message()
				await interaction.followup.send(f'{interaction.user.display_name} joined the queue.', ephemeral=True)
			else:
				await interaction.followup.send('You are already in the queue.', ephemeral=True)
		else:
			await interaction.followup.send('You must be in a Lobby voice channel to join the queue.', ephemeral=True)

	@ui.button(label="Leave Queue", style=ButtonStyle.red, custom_id="leave_queue")
	async def leave_button_callback(self, interaction: discord.Interaction, button: ui.Button):
		await interaction.response.defer(ephemeral=True)
		if interaction.user.id in self.queue_cog.queue:
			self.queue_cog.queue.remove(interaction.user.id)
			await self.queue_cog.update_queue_message()
			await interaction.followup.send(f'{interaction.user.display_name} left the queue.', ephemeral=True)
		else:
			await interaction.followup.send('You are not in the queue.', ephemeral=True)

	@ui.button(label="Force Start", style=ButtonStyle.blurple, custom_id="force_start_queue")
	async def force_start_button_callback(self, interaction: discord.Interaction, button: ui.Button):
		await interaction.response.defer(ephemeral=True)
		if any(role.name in ['Founder', 'Admin'] for role in interaction.user.roles):
			if self.queue_cog.queue:
				await self.queue_cog.split_teams(interaction, force_start=True)
				await interaction.followup.send('Queue force started!', ephemeral=True)
			else:
				await interaction.followup.send('The queue is empty, unable to force start.', ephemeral=True)
		else:
			await interaction.followup.send('You do not have permission to force start the queue.', ephemeral=True)

class FinishQueueView(ui.View):
	def __init__(self, queue_cog, channel_id):
		super().__init__(timeout=None)
		self.queue_cog = queue_cog
		self.channel_id = channel_id
		self.votes = {'Yes': 0, 'No': 0}

	async def handle_vote(self, interaction, vote):
		self.votes[vote] += 1
		majority = len(self.queue_cog.queue) // 2 + 1

		if self.votes['Yes'] >= majority:
			await interaction.message.edit(content="Majority voted Yes. The match is finishing...", view=None)

			role_name = f"QueueRole-{self.channel_id}"
			await self.queue_cog.finish_queue(interaction.guild, self.channel_id, self.queue_cog.current_queue_role_name)
		elif self.votes['No'] + self.votes['Yes'] == len(self.queue_cog.queue):
			await interaction.message.edit(content="Voting completed. The match continues.", view=None)

	@ui.button(label="No", style=ButtonStyle.red, custom_id="vote_no")
	async def no_button_callback(self, interaction: discord.Interaction, button: ui.Button):
		await self.handle_vote(interaction, "No")

	@ui.button(label="Yes", style=ButtonStyle.green, custom_id="vote_yes")
	async def yes_button_callback(self, interaction: discord.Interaction, button: ui.Button):
		await self.handle_vote(interaction, "Yes")

class QueueCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.queue = []
		self.queue_message_id = None
		self.queue_channel_id = 1184070520736595989
		self.view = QueueView(self)
		self.current_queue_role_name = None
		self.init_message.start()

	@tasks.loop(count=1)
	async def init_message(self):
		await self.bot.wait_until_ready()
		channel = self.bot.get_channel(self.queue_channel_id)
		message = await channel.send(embed=Embed(title="Queue Status", description="0 / 8 players in queue."), view=self.view)
		self.queue_message_id = message.id

	async def split_teams(self, interaction, force_start=False):
		guild = interaction.guild
		queue_id = int(time.time())

		self.current_queue_role_name = f"QueueRole-{queue_id}"
		queue_role = await guild.create_role(name=self.current_queue_role_name)
		channel_name = f"queue-channel-{queue_id}"
		overwrites = {
			guild.default_role: discord.PermissionOverwrite(read_messages=False),
			guild.me: discord.PermissionOverwrite(read_messages=True),
			queue_role: discord.PermissionOverwrite(read_messages=True)
		}
		new_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)

		for user_id in self.queue:
			member = guild.get_member(user_id)
			if member:
				await member.add_roles(queue_role)

		team_a, team_b = self.divide_queue_into_teams(force_start)
		embed = Embed(title="Team Information", description="Details of the teams.")
		embed.add_field(name="Team A", value=", ".join([guild.get_member(uid).mention for uid in team_a]))
		embed.add_field(name="Team B", value=", ".join([guild.get_member(uid).mention for uid in team_b]))
		await new_channel.send(embed=embed)

		await self.move_members_to_teams(team_a, team_b, guild)
		self.queue.clear()
		await self.update_queue_message()

		finish_embed = Embed(title="Match Finished?", description="Vote to finish the match.")
		finish_view = FinishQueueView(self, new_channel.id)
		await new_channel.send(embed=finish_embed, view=finish_view)

	async def move_members_to_teams(self, team_a, team_b, guild):
		team_a_channel = discord.utils.get(guild.voice_channels, name='Team A')
		team_b_channel = discord.utils.get(guild.voice_channels, name='Team B')
		for user_id in team_a:
			member = guild.get_member(user_id)
			if member:
				await member.move_to(team_a_channel)
		for user_id in team_b:
			member = guild.get_member(user_id)
			if member:
				await member.move_to(team_b_channel)

	async def finish_queue(self, guild, channel_id, role_name):
		print(f"ROLE NAME: {role_name}")
		print("Finishing queue...")

		lobby_channel = discord.utils.get(guild.voice_channels, name='Lobby')
		if not lobby_channel:
			print("Lobby voice channel not found.")
			return
		else:
			print(f"Lobby channel found: {lobby_channel.name}")

		queue_role = discord.utils.get(guild.roles, name=role_name)
		if queue_role:
			print(f"Found role: {queue_role.name}, members count: {len(queue_role.members)}")
			for member in queue_role.members:
				try:
					print(f"Processing member: {member}")
					if member.voice:
						print(f"Moving {member} to Lobby.")
						await member.move_to(lobby_channel)
					else:
						print(f"{member} is not in a voice channel.")
					await member.remove_roles(queue_role)
				except discord.HTTPException as e:
					print(f"Failed to move or update member {member}: {e}")

			await queue_role.delete(reason="Queue finished")
		else:
			print("Queue Role not found.")

		channel = guild.get_channel(channel_id)
		if channel:
			await channel.delete(reason="Queue finished")

		self.queue.clear()
		await self.update_queue_message()

	def divide_queue_into_teams(self, force_start):
		team_size = len(self.queue) // 2 if force_start and len(self.queue) > 1 else len(self.queue)
		team_a = self.queue[:team_size]
		team_b = self.queue[team_size:team_size * 2]
		return team_a, team_b

	@commands.Cog.listener()
	async def on_voice_state_update(self, member, before, after):
		if before.channel and before.channel.name == 'Lobby' and (not after.channel or after.channel.name != 'Lobby'):
			if member.id in self.queue:
				self.queue.remove(member.id)
				await self.update_queue_message()

	async def update_queue_message(self):
		channel = self.bot.get_channel(self.queue_channel_id)
		message = await channel.fetch_message(self.queue_message_id)
		embed = Embed(title="Queue Status", description=f"{len(self.queue)} / 8 players in queue.")

		if self.queue:
			users_mentions = []
			for uid in self.queue:
				user = await self.bot.fetch_user(uid)
				if user:
					users_mentions.append(user.mention)
				else:
					users_mentions.append(f'Unknown Member (ID: {uid})')
			embed.add_field(name="Players in Queue", value="\n".join(users_mentions))

		await message.edit(embed=embed, view=self.view)

async def setup(bot):
	queue_cog = QueueCog(bot)
	await bot.add_cog(queue_cog)
