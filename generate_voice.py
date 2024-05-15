from elevenlabs import play, save
from elevenlabs.client import ElevenLabs
from time import time
from os import mkdir
from os.path import join, exists
import sys
import csv


def print_format_error():
	print('ERROR: Please create an input file named inputs.csv')
	print('    Row Format: input text, input voice, input model')
	exit()


# Replace this with your API KEY!
API_KEY = 'a5269cd6362a53732210050b918545eb'

# Output directory for the generated audio files
OUTPUT_DIR = 'outputs'

if len(sys.argv) == 2:
	
	if not exists(OUTPUT_DIR):
		mkdir(OUTPUT_DIR)
	
	# create the elevenlabs client object
	client = ElevenLabs(
	  api_key = API_KEY, # Defaults to ELEVEN_API_KEY
	)
	
	input_file = str(sys.argv[1])
	with open(input_file, newline='') as csvfile:
		csvreader = csv.reader(csvfile, delimiter='\t', quotechar='|')
		for row in csvreader:
			if len(row) != 4:
				print_format_error()
			
			# store the input values 
			input_text = str(row[1]).strip()
			input_voice = str(row[2]).strip()
			input_model = str(row[3]).strip()
			
			# generate the audio
			audio = client.generate(
			  text=input_text,
			  voice=input_voice,
			  model=input_model
			)
			
			# save the audio to the output folder
			filename = str(row[0]).strip() + '.wav'
			save(audio, join(OUTPUT_DIR, filename))
else:
	print_format_error()

