import pickle
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import logging

scopes = ["https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/youtubepartner",
          "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]

API_REFERENCES = {
	'analytics': {
		'build': 'youtubeAnalytics',
		'version': 'v2'},
	'data': {
		'build': 'youtube',
		'version': 'v3'},
}

file = '.credentials/client_secret.json'

def get_service(service_type, file=file):
	service=None
	# Get credentials and create an API client
	flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
		file, scopes)
	credentials = flow.run_console()
	service = googleapiclient.discovery.build(
		API_REFERENCES[service_type]['build'], API_REFERENCES[service_type]['version'], credentials=credentials)
	logging.info('Using credentials found in ' + file)
	save_path = f'.credentials/{service_type}.pkl'
	with open(save_path, 'wb') as f:
		pickle.dump(service, f)
	logging.info(f'Created {service_type}.pkl in ' + save_path)
	if not service:
		logging.error(' UNABLE TO RETRIEVE CREDENTIALS | Expected credential paths: ' + ', '.join(
			file) + ' | More info in project Documentation folder setup_credentials.md file')