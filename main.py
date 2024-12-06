# Reference: https://github.com/Pycord-Development/pycord/blob/master/examples/audio_recording_merged.py

import io, discord, requests # pip install -U py-cord[voice] == 2.6.1
from discord.ext import commands
import pydub  # pip install pydub==0.25.1
from discord.sinks import MP3Sink
from dotenv import get_key

DISCORD_TOKEN = get_key(".env", "DISCORD_BOT_TOKEN")
COMMAND_PREFIX = get_key(".env", "COMMAND_PREFIX")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# https://stackoverflow.com/questions/64933979/discord-get-user-by-id
def get_user_info(user_id) -> dict:
    """
    Returns something similar to:
    ```
    {
        "id": "123456789",
        "username": "coolguy123",
        "avatar": None,
        "discriminator": "1234",
        "global_name": "The Cool Guy",
        "public_flags": 0,
        "banner": None,
        "banner_color": "#FFFFF",
        "accent_color": None,
        "clan": None,
        "flags": 123
        ...
    }
    ```
    """

    request_url = f"https://discord.com/api/v9/users/{user_id}"
    headers = {
        "Authorization": f"Bot {DISCORD_TOKEN}"
    }
    
    resp = requests.get(request_url, headers=headers)

    if resp.ok:
        return resp.json()
    return False

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


async def finished_callback(sink: MP3Sink, channel: discord.TextChannel):
    mention_strs = []
    audio_segs: list[pydub.AudioSegment] = []
    files: list[discord.File] = []

    longest = pydub.AudioSegment.empty()

    for user_id, audio in sink.audio_data.items():
        # Get more info on user
        user_info = get_user_info(user_id)
        print(user_info)
        username = user_info["username"]
        discriminator = user_info["discriminator"]
        full_name = f"{username}#{discriminator}"

        print(f"Processing {full_name} - {user_id}")

        # Make sure we can mention who was in the recording later on
        mention_strs.append(f"<@{user_id}>")

        # Get audio file
        audio_file_bytes_io: io.BytesIO = audio.file
        # Convert into AudioSegment object
        seg: pydub.AudioSegment = pydub.AudioSegment.from_file(audio_file_bytes_io, format="mp3")

        
        # Write audio to local file
        with open(f"user-{full_name}-{user_id}", "wb") as f:
            seg.export(f, format="mp3")

        # Determine the longest audio segment
        if len(seg) > len(longest):
            audio_segs.append(longest)
            longest = seg
        else:
            audio_segs.append(seg)
        
        audio_file_bytes_io.seek(0)

        # Add to list so it can be sent into discord channel
        files.append(discord.File(audio.file, filename=f"user-{full_name}-{user_id}.mp3"))

    # Combine everyone's audio into one
    for seg in audio_segs:
        longest = longest.overlay(seg)

    # Send all the mp3s to the discord channel
    with io.BytesIO() as f:
        longest.export(f, format="mp3")
        await channel.send(
            f"Finished! Recorded audio for {', '.join(mention_strs)}.",
            files=files + [discord.File(f, filename="all_recording.mp3")],
        )


@bot.command()
async def join(ctx: discord.ApplicationContext):
    """Join the voice channel!"""
    # Get author's voice object (so we can join the vc they're in)
    voice = ctx.author.voice

    if not voice:
        return await ctx.send("You're not in a vc right now")

    # Conenct to the channel
    await voice.channel.connect()

    await ctx.send("Joined!")


@bot.command()
async def start(ctx: discord.ApplicationContext):
    """Record the voice channel!"""

    # Get the message author's current VoiceState
    voice = ctx.author.voice

    # Get bot's VoiceClient
    vc: discord.VoiceClient = ctx.voice_client

    # Check if they are in a VC
    if not voice:
        await ctx.send("You're not in a vc right now")
        return

    if not vc:
        await ctx.send(f"I'm not in a vc right now. Use `{COMMAND_PREFIX}join` to make me join!")
        return
    
    # Start listening/recording to VC
    vc.start_recording(
        MP3Sink(),
        finished_callback,
        ctx.channel,
        # I'm not sure what this does but it seems to work fine commented out: # sync_start=True,  # WARNING: This feature is very unstable and may break at any time.
    )

    await ctx.send("The recording has started!")


@bot.command()
async def stop(ctx: discord.ApplicationContext):
    """Stop recording audio"""
    vc: discord.VoiceClient = ctx.voice_client

    if not vc: # If we don't check vc.stop_recording will raise a "RecordingException"
        await ctx.send("I am not currently recording")
        return 

    vc.stop_recording()

    await ctx.send("The recording has stopped!")


@bot.command()
async def leave(ctx: discord.ApplicationContext):
    """Leave the voice channel!"""
    vc: discord.VoiceClient = ctx.voice_client

    if not vc:
        return await ctx.send("I'm not in a vc right now")

    # Disconnect from voice channel
    await vc.disconnect()

    # Send info to channel
    await ctx.send("Exited VC!")


bot.run(DISCORD_TOKEN)
