import pickle
import calendar
import pandas as pd
from datetime import datetime
from pathlib import Path

# my_file = Path('.credentials/data.pkl')
# if my_file.is_file():
# 	with open(my_file, 'rb') as file:
# 		data_service = pickle.load(file)


def endMonth(year, month):
	endDay = calendar.monthrange(year, month)[1]
	return endDay


def CMS_All_channel(contentOwnerID, CMS, pkl_file):
	with open(pkl_file, 'rb') as file:
		data_service = pickle.load(file)
	channel_col = ['channel_id', 'channel_title', 'channel_logo_url', 'channel_banner_url', 'location']
	channel_stat_col = ['channel_id', 'viewCount', 'subscriberCount', 'videoCount']
	full_list_channel = []
	full_list_stats = []
	# ch_infos = data_service.channels().list(part='id,snippet,brandingSettings,statistics',managedByMe=True,maxResults=50,onBehalfOfContentOwner=contentOwnerID).execute()
	# nextPageToken = ch_infos['nextPageToken']
	# for i in range(len(ch_infos['items'])):
	# 	tmp_channel = []
	# 	tmp_stats = []
	# 	tmp_channel.append(ch_infos['items'][i]['id'])
	# 	tmp_channel.append(ch_infos['items'][i]['snippet']['title'])
	# 	tmp_channel.append(ch_infos['items'][i]['snippet']['thumbnails']['high']['url'])
	# 	tmp_channel.append(ch_infos['items'][i]['brandingSettings']['image']['bannerImageUrl'])
	# 	try:
	# 		tmp_channel.append(ch_infos['items'][i]['snippet']['country'])
	# 	except:
	# 		tmp_channel.append('NO_LOC')
	# 	tmp_stats.append(ch_infos['items'][i]['id'])
	# 	tmp_stats.append(ch_infos['items'][i]['statistics']['viewCount'])
	# 	tmp_stats.append(ch_infos['items'][i]['statistics']['subscriberCount'])
	# 	tmp_stats.append(ch_infos['items'][i]['statistics']['videoCount'])
	#
	# 	full_list_channel.append(tmp_channel)
	# 	full_list_stats.append(tmp_stats)
	nextPageToken = None
	while True:
		try:
			ch_infos = data_service.channels().list(part='id,snippet,brandingSettings,statistics', managedByMe=True,
			                                        maxResults=50, onBehalfOfContentOwner=contentOwnerID,
			                                        pageToken=nextPageToken).execute()
			nextPageToken = ch_infos['nextPageToken']
			for i in range(len(ch_infos['items'])):
				tmp_channel = []
				tmp_stats = []
				tmp_channel.append(ch_infos['items'][i]['id'])
				tmp_channel.append(ch_infos['items'][i]['snippet']['title'])
				tmp_channel.append(ch_infos['items'][i]['snippet']['thumbnails']['high']['url'])
				tmp_channel.append(ch_infos['items'][i]['brandingSettings']['image']['bannerImageUrl'])
				try:
					tmp_channel.append(ch_infos['items'][i]['snippet']['country'])
				except:
					tmp_channel.append('NO_LOC')
				tmp_stats.append(ch_infos['items'][i]['id'])
				tmp_stats.append(ch_infos['items'][i]['statistics']['viewCount'])
				tmp_stats.append(ch_infos['items'][i]['statistics']['subscriberCount'])
				tmp_stats.append(ch_infos['items'][i]['statistics']['videoCount'])

				full_list_channel.append(tmp_channel)
				full_list_stats.append(tmp_stats)
		except:
			break
	df_ch_full = pd.DataFrame(full_list_channel, columns=channel_col)
	df_ch_full['CMS'] = CMS
	df_ch_full.to_csv(f'CMS_{CMS}_ch_full_list.csv', index=False)
	df_stat_full = pd.DataFrame(full_list_stats, columns=channel_stat_col)
	df_stat_full['updatedOn'] = datetime.now()
	df_stat_full.to_csv(f'CMS_{CMS}_stat_full.csv', index=False)

