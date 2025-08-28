import pickle
from datetime import datetime
from dateutil.relativedelta import relativedelta
import calendar
import pandas as pd

with open('.credentials/analytics.pkl', 'rb') as file:
	analytics_service = pickle.load(file)

ageGroup = ["age13-17","age18-24","age25-34","age35-44","age45-54","age55-64","age65-"]
b_cols = ['year_month', 'view', 'averageViewPercentage', 'subscribersGained', 'subscribersLost', 'estimatedRevenue',
          'monetizedPlaybacks', 'playbackBasedCpm', 'adImpressions', 'cpm']
vid_cols = ['video_id', 'view', 'averageViewPercentage', 'subscribersGained', 'subscribersLost', 'estimatedRevenue',
          'monetizedPlaybacks', 'playbackBasedCpm', 'adImpressions', 'cpm']

agegen = []
for age in ageGroup:
    for gender in ['male', 'female']:
        agegen.append([age,gender])
blank_agegen = pd.DataFrame(agegen, columns=['ageGroup','gender'])

def lastMonth(Date):
	return (datetime.strptime(Date, '%Y-%m') - relativedelta(months=1)).strftime("%Y-%m")

def endMonth(year, month):
	endDay = calendar.monthrange(year, month)[1]
	return str(endDay)

def str_endMonth(date):
	endDay = calendar.monthrange(int(date[:4]), int(date[5:7]))[1]
	return date[:7] + '-' + str(endDay)

def monthly_channelreport_tosql(ch_id, startDate, endDate):
	request = analytics_service.reports().query(
		dimensions="month",
		startDate=f"{startDate}-01",
		endDate=f"{endDate}-01",
		filters=f"channel=={ch_id};",
		ids="contentOwner==gRKGrdXpuJU_NvauhuOD9A",
		maxResults=200,
		metrics="views,averageViewPercentage,subscribersGained,subscribersLost,estimatedRevenue,monetizedPlaybacks,playbackBasedCpm,adImpressions,cpm",
		sort="month"
	)
	response = request.execute()

	df1 = pd.DataFrame(response['rows'], columns=b_cols)

	request = service.reports().query(
		dimensions="subscribedStatus,month",
		startDate=f"{startDate}-01",
		endDate=f"{endDate}-01",
		filters=f"channel=={ch_id};",
		ids="contentOwner==gRKGrdXpuJU_NvauhuOD9A",
		maxResults=200,
		metrics="views,averageViewPercentage",
		sort="month"
	)
	response_sub = request.execute()

	df_subreport = pd.DataFrame(response_sub['rows'],
	                            columns=['subscribedStatus', 'year_month', 'view', 'averageViewPercentage'])
	df_sub = df_subreport.loc[df_subreport.subscribedStatus == 'SUBSCRIBED'].rename(
		columns={'view': 'subscribed_view', 'averageViewPercentage': 'subscribed_averageViewPercentage'}).drop(
		'subscribedStatus', axis=1)
	df_unsub = df_subreport.loc[df_subreport.subscribedStatus == 'UNSUBSCRIBED'].rename(
		columns={'view': 'unsubscribed_view', 'averageViewPercentage': 'unsubscribed_averageViewPercentage'}).drop(
		'subscribedStatus', axis=1)
	df2 = pd.merge(df_sub, df_unsub, on='year_month')
	df3 = pd.merge(df1, df2, on='year_month')
	df3['channel_id'] = ch_id
	df3['year_month'] = df3.apply(lambda x: x['year_month'] + "-01", axis=1)
	df3.to_sql('report_monthlychannelreport', con=engine, schema='public', if_exists='append', index=False)

