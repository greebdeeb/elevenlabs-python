TODO:
- update readme
- add requirements.txt








audio file
use OpenAI whisper to convert audio to transcript
- open source git repo

prereqs:
- Install python

	# Install ffmpeg
	sudo apt update && sudo apt install ffmpeg
	
	# Instal python deps
	python -m pip install bs4 openai elevenlabs argparse PyYAML stable-ts argparse


DEV work:
- Create caption data with timestamps:
	# use the align method from https://github.com/jianfch/stable-ts
	text = 'Machines thinking, breeding. You were to bear us a new, promised land.'
	result = model.align('audio.mp3', text, language='en')