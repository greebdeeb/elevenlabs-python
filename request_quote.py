from os.path import exists, join, isfile
from os import makedirs, listdir
from bs4 import BeautifulSoup
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips
from random import choice
import argparse
import requests
import re
import yaml
from moviepy.audio.fx.all import audio_fadeout

# compile regex once only
CLEANR = re.compile('<.*?>') 

# map numbers to words (ex. First, Second, ...)
number_dict = {
	'1' : 'First ',
	'2' : 'Second ',
	'3' : 'Third ',
	'4' : 'Fourth ',
}


#### Helper functions

def cleanhtml(raw_html):
	cleantext = re.sub(CLEANR, '', str(raw_html))
	return cleantext

def get_bible_filename(bible_verse_name):
	bible_verse_name = bible_verse_name.replace(' ', '_')
	bible_verse_name = bible_verse_name.replace(':', '.')
	return bible_verse_name

def get_bible_name(bible_verse_name):
	# change leading numbers to words (ex. First Corinthians)
	first_two_chars = bible_verse_name[:2]
	if first_two_chars in number_dict:
		bible_verse_name = number_dict[first_two_chars] + bible_verse_name[2:]
	bible_verse_name = bible_verse_name.replace(':', ', ')
	return bible_verse_name

def print_format_error():
	print('ERROR: Please create an input file named inputs.csv')
	print('    Row Format: output filename, input text, input voice, input model')
	exit()


#### Generation Routines

# Get a number of bible verses from dailyverses.net
# num_verses (INT)         :   number of bible verses to fetch
# output     (dictionary)  :  { verse1_name : verse1_text, verse2_name : verse2_text, ...}
def fetch_bible_verses(num_verses):
	data = {}
	for i in range(num_verses):
		print('fetch request: ' + str(i+1))
		
		# Initiate webpage request from URL
		response = requests.get('https://dailyverses.net/random-bible-verse') 
		contents = BeautifulSoup(response.content, 'html.parser') 
		
		# Parse the bible verse data
		bible_verse_name = cleanhtml(contents.find('div', class_='vr').find('a', class_='vc'))
		bible_verse_text = cleanhtml(contents.find('span', class_='v1'))
		
		# Generate key which can be used for filenames
		key = get_bible_filename(bible_verse_name)
		
		# Add the bible verse to the data dictionary
		data[key] = [ get_bible_name(bible_verse_name), bible_verse_text ]
		
	return data

# Use local LLM to generate commentary about the bible verse
# data    (dictionary)  :  { verse1_name : verse1_text, verse2_name : verse2_text, ...}
# output  (dictionary)  :  { verse1_name : [ verse1_text, verse1_commentary ] , verse2_name : [ verse2_text, verse2_commentary ] , ...}
def generate_commentary(data):
	for key, values in data.items():
		print('generate commentary: ' + key)
		
		# Connect to the LLM on localhost
		client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
		
		# Extract the bible text from the dictionary
		bible_verse_name = values[0]
		bible_verse_text = values[1]
		
		# TODO: add this config to the config YAML
		# Send request to the LLM server
		completion = client.chat.completions.create(
			model="lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF",
			messages=[
				{"role": "system", "content": "You are a priest who provides breif commentary about how bible verses apply to our lives."},
				{"role": "user", "content": "Describe this bible verse using two sentences in the context of the holy bible: " + bible_verse_name + ', ' + bible_verse_text},
			],
			temperature=0.7,
		)
		
		# Extract the commentary from the response and remove the quotation marks
		commentary = completion.choices[0].message.content
		
		# Add the commentary to the data dictionary
		data[key] = [ bible_verse_name, bible_verse_text, commentary]
		
	return data

# Use ElevenLabs remote API to generate audio files for the bible verse
# input   (dictionary)  :  { verse1_name : [ verse1_text, verse1_commentary ] , verse2_name : [ verse2_text, verse2_commentary ] , ...}
# output  (audio file)  :  writes audio files to the local filesystem
def generate_audio(data, config):
	# create the elevenlabs client object
	client = ElevenLabs(
		api_key = config['elevenlabs_api_key'], # Defaults to ELEVEN_API_KEY
	)

	# Generate audio for each bible verse
	for key, values in data.items():
		print('generate audio: ' + key)
		
		# Call to the ElevenLabs API
		audio = client.generate(
		  text='... '.join(values),
		  voice=config['elevenlabs_voice'],
		  model=config['elevenlabs_model']
		)
		
		# save the audio to the output folder
		save(audio, join(config['output_audio_dir'], key + '.wav'))

# Select a random input video from the video resource path
# input   (string)  :  specify the path to video resources
# output  (string)  :  path to a randomly selected video
def select_random_video(video_resource_path):
	# list all the videos in the resource directory
	video_files = listdir(video_resource_path)
	
	# remove directories from the list
	for filename in video_files:
		if not isfile(join(video_resource_path, filename)):
			video_files.remove(filename)
	
	# select a random video
	if video_files:
		return join(video_resource_path, choice(video_files))
	else:
		return None

# Create a video for each generated audio by combining it with a random video
# input   (dictionary)  :  { verse1_name : [ verse1_text, verse1_commentary ] , verse2_name : [ verse2_text, verse2_commentary ] , ...}
# output  (video file)  :  writes a video file to the local file system
def generate_video(data, config):
	for key in data.keys():
		# Locate the generated audio
		local_audio_path = join(config['output_audio_dir'], key + '.wav')
		
		# Select the resource video
		local_video_path = select_random_video(config['input_video_dir'])
		
		# Open the audio and video clip
		with AudioFileClip(local_audio_path) as audioclip, VideoFileClip(local_video_path) as videoclip:
		
			# Loop the video clip to match the voiceover length
			num_loops = int(audioclip.duration / videoclip.duration) + 1
			looped_video = concatenate_videoclips([videoclip] * num_loops)
			
			# Generate the final video
			looped_video = (
				looped_video
				.subclip(0, (audioclip.duration)) # Trim video length to match audio
				.set_audio(audioclip) # Add the voiceover to the video
			)
		
			# Save the video
			output_video_path = join(config['output_video_dir'], key + '.mp4')
			looped_video.write_videofile(output_video_path)
		
def main():
	parser = argparse.ArgumentParser(description='Description of your program')
	parser.add_argument('-n', '--num-verses', type=int, help="Specify the number of bible verses to query.", required=False, default=1)
	parser.add_argument('-o', '--output-suffix', type=int, help='Specify a suffix for the output files to prevent overwriting.', required=False, default='0')
	parser.add_argument('-c', '--config', type=str, help='Specify a configuration file for environment variables.', required=False, default='config.yaml')
	group = parser.add_mutually_exclusive_group()
	group.add_argument('-l', '--load', type=str, help="Load from a config file with pre-generated bible verses.")
	group.add_argument('-t', '--text-only', action='store_true', help="Text generation only, does not generate any text to speech audio.")
	args = parser.parse_args()
	
	# Load environment from config.yaml
	config_data = {}
	with open(args.config, 'r') as fp:
		config_data = yaml.safe_load(fp)
	
	# Make the output directories
	makedirs(config_data['output_text_dir'], exist_ok=True)
	makedirs(config_data['output_audio_dir'], exist_ok=True)
	makedirs(config_data['output_video_dir'], exist_ok=True)
	makedirs(config_data['input_video_dir'], exist_ok=True)
	
	data = {}
	if args.load:
		# Load bible verses from a save file
		with open(args.load, 'r', encoding='utf-8') as fp:
			data = yaml.safe_load(fp)
	else:
		# Request a number of bible verses and write them to the output file
		data = fetch_bible_verses(args.num_verses)
		
		# Generate commentary on the fetched bible verses
		data = generate_commentary(data)
		
		# Save the data in a YAML file
		with open(join(config_data['output_text_dir'], 'bible_verses_' + str(args.output_suffix) + '.yaml'), 'w', encoding='utf-8') as fp:
			yaml.dump(data, fp)
	
	# Read the bible verse using ElevenLabs API
	if not args.text_only:
		generate_audio(data, config_data)
	
		# Combine generated audio and random stock video
		if exists(config_data['input_video_dir']):
			generate_video(data, config_data)


if __name__ == '__main__':
	main()