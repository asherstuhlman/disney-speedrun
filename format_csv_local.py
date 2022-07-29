from datetime import datetime, timedelta
from time import sleep
import requests
import pandas as pd
import numpy as np
import os
import pytz
import io
import ftplib
from boto.s3.connection import S3Connection
#just for now - importing the same things as the main gminus_v3 file. We probably won't use all of these.

#2. Predicted wait / current wait (Is the predicted wait higher than the actual wait right now? Good)
#3. Predicted wait in 30 minutes / predicted wait (Is the predicted wait now better than the wait in 30 minutes? Good. We use predicted weight as the denominator because this is a ratio, and past days might not be representative of current absolute values for wait)
#4. Current wait / How long you _should_ wait for the ride (average wait time over the course of the day? or personal scoring)
#TO GET THE PREDICTED WAIT TIMES: Look at the last seven days of files and find all waits for this ride within 2 minutes

#Let's start by using one CSV and getting all relevant data from it.
#First we need to figure out the average wait time over the course of the day.
#We do this by taking the first nonzero value and the last nonzero value and removing all the rest.
#It is true that we don't evenly sample a day - but we sample it close enough to evenly that taking the mean is sufficient.

def find_nth(haystack, needle, n):
    start = haystack.find(needle)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start+len(needle))
        n -= 1
    return start

"""last_week_file_array = []
for i in range(7):
    last_week_file_array.append[datetime.now(pytz.timezone("US/Central")) - timedelta(days = i+1)]
    past_dfs = pd.read_csv('C:/Users/Asher/Documents/ride_data_'+str(last_week_file_array[i].month)+'-'+str(last_week_file_array[i].day)+'.csv')
"""#UNCOMMENT THIS WHEN I HAVE MULTIPLE DAYS OF DATA!!!
def format_csv_for_predictions(prediction_time_delta = 1):
    yesterday = datetime.now(pytz.timezone("US/Central")) - timedelta(days = prediction_time_delta)

    y_df = pd.read_csv('C:/Users/Asher/Documents/ride_data_'+str(yesterday.month)+'-'+str(yesterday.day)+'.csv')
    out_df = pd.read_csv('C:/Users/Asher/Documents/GitHub/disney-speedrun/rides_and_ids.csv', encoding = "ISO-8859-1").sort_values(by=['id'])

    y_df = pd.merge(y_df,out_df,how="outer",on=["id","id"]).sort_values(by=['id'])
    y_df["name_x"] = y_df["name_y"]
    y_df = y_df.drop(columns="name_y")

    average_waits = []

    for row,rowdata in y_df.iterrows(): 
        #add each nonzero value 
        time_sum = 0
        time_count = 0
        for i in range(len(rowdata)):
            if i > 9:
                if rowdata[i] > 0:
                    time_sum += rowdata[i]
                    time_count += 1
        try:
            average_waits.append(time_sum/time_count)
        except ZeroDivisionError:
            average_waits.append(0)

    out_df['average_wait'] = average_waits

    #"normalize" the array to have minute by minute wait time data
    #get a list of column names
    #make a list derived from that that's the minutes from the column names
    #look up minutes and cross-reference that with the list of column names to find the column(s) with data closest to the minute
    #colnames = y_df.head()
    for i in range(8, 24):
        for j in range (0,60):
            out_df[str(i).zfill(2)+":"+str(j).zfill(2)] = np.nan
    pass

    a = 0
    for row,rowdata in y_df.iterrows(): #first we add the data that we have for minutes - which is incomplete. THIS IS WHERE THE ERROR IS BEING CREATED!!! We should just match on ID and labelDate
        for i in range(len(y_df.keys())):
            t = y_df.keys()[i]
            hour = t[find_nth(t,"-",3)+1:find_nth(t,"-",4)]
            minute = t[find_nth(t,"-",4)+1:].zfill(2)
            if t[0] == "z" and int(hour) >= 8:
                labelDate = hour.zfill(2)+":"+minute
                try: 
                    out_df.loc[out_df['id']  == rowdata['id'],labelDate] = int(y_df.loc[y_df['id'] == rowdata['id'],t])
                except ValueError:
                    out_df.loc[out_df['id']  == rowdata['id'],labelDate] = 0
                pass
        pass

    out_df.to_csv('C:/Users/Asher/Documents/ride_data_cleaned_'+str(yesterday.month)+'-'+str(yesterday.day)+'a.csv', encoding = "ISO-8859-1", index = False)

    for row,rowdata in out_df.iterrows(): #Then we extrapolate 
        for i in range(3,len(rowdata)): 
            labelDate = out_df.keys()[i]
            if pd.isnull(rowdata[i]):
                check_forward = i
                next_value = -1
                limit = 0
                try:
                    while next_value == -1 and limit < 10:
                        check_forward += 1
                        if np.isfinite(rowdata[check_forward]):
                            next_value = rowdata[check_forward]
                        limit += 1
                except IndexError:
                    check_forward = i
                    limit = 0
                    while next_value == -1 and limit < 10:
                        check_forward -= 1 #check backwards instead if we reach the end!
                        if np.isfinite(rowdata[check_forward]):
                            next_value = rowdata[check_forward]
                        limit += 1
                out_df.loc[out_df['id']  == rowdata['id'],labelDate] = next_value
                    
    print(out_df)

    out_df.to_csv('C:/Users/Asher/Documents/ride_data_cleaned_'+str(yesterday.month)+'-'+str(yesterday.day)+'.csv', encoding = "ISO-8859-1", index = False)
    #Great! Now we have a full wait time chart.

    #Repeat for every day of the last week???