from pydub import AudioSegment

# Load .mpv file (treating it as generic audio/video format)
audio = AudioSegment.from_file("my-demo.mp4")

# Convert to mono, 16kHz, 16-bit
audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

# Export to WAV
audio.export("output.wav", format="wav")
