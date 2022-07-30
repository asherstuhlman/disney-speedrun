from cmath import isfinite
from datetime import datetime, timedelta
from time import sleep
import requests
import pandas as pd
import os
import pytz
import io
import ftplib
import math
from boto.s3.connection import S3Connection

import gm_format_csv #from this directory

#this is the version for the web
#it runs on a cronjob every 5 minutes
#but only triggers during park open hours
#We don't have a list of park open hours so we just run it 8 AM - midnight

def appendRides(df,json_file):
    for i in range(len(json_file["lands"])): 
        for j in range(len(json_file["lands"][i]["rides"])):
            id = json_file["lands"][i]["rides"][j]["id"]
            name = json_file["lands"][i]["rides"][j]["name"]
            df = df.append({'id':id,'name':name},ignore_index=True)
    return df

def addWaitTimes(df,json_file,next_col_name): #go through an update file and fill in the wait times for each ride 
    for i in range(len(json_file["lands"])):
        for j in range(len(json_file["lands"][i]["rides"])):
            id = json_file["lands"][i]["rides"][j]["id"]
            wait = json_file["lands"][i]["rides"][j]["wait_time"]
            df.loc[df.id==id,next_col_name] = wait   #set the latest wait time for a ride to the current wait time
            df.loc[df.id==id,"current_wait"] = wait #also update the current wait
            #This is the wrong way to do this! The correct way should be to generate a column of wait times and then append it.
    return df

def updateWaitRatio(df):
    #wait ratio has three factors:
    #1. Highest wait in the last 45 minutes / current wait (Is the current wait time going down? Good)
    #2. Predicted wait / current wait (Is the predicted wait higher than the actual wait right now? Good)
    #3. Predicted wait in 30 minutes / predicted wait (Is the predicted wait now better than the wait in 30 minutes? Good. We use predicted weight as the denominator because this is a ratio, and past days might not be representative of current absolute values for wait)
    last_col = len(df.columns)
    #print(df.itertuples())
    if last_col > 20: #if we have enough data points
        logFile = []
        for row in df.itertuples():
            #FIRST SECTION: Get #1, the highest wait in the last 45 minutes / current wait
            current_wait_time = df.iat[row[0],last_col-1]
            #print(current_wait_time)
            #last_6_column = df.iloc[[row[0]],-6:]
            recent_max = max(df.iat[row[0],last_col-1],df.iat[row[0],last_col-2],df.iat[row[0],last_col-3],df.iat[row[0],last_col-4],df.iat[row[0],last_col-5],df.iat[row[0],last_col-6],df.iat[row[0],last_col-7])   #should just be a slice of the df though
            recent_min = min(df.iat[row[0],last_col-1],df.iat[row[0],last_col-2],df.iat[row[0],last_col-3],df.iat[row[0],last_col-4],df.iat[row[0],last_col-5],df.iat[row[0],last_col-6],df.iat[row[0],last_col-7]) 
            #get the minimum (and maximum) of the last 50 minutes - this is terrible and there's a cleaner way to do it but righ now it just grabs the last entries individualy            

            try:
                if recent_max == 0:
                    waitTimeGoingDownRatio = 0
                elif current_wait_time > recent_min:
                    if recent_min == 0:
                        waitTimeGoingDownRatio = 1 #if a ride has had recent downtime, it's a good choice
                    elif current_wait_time == recent_max:
                        waitTimeGoingDownRatio = recent_max / recent_min #if the current value is the highest in the last 25 minutes, the waitRatio is highest/lowest
                    else:
                        waitTimeGoingDownRatio = 1 #if the current wait time isn't the highest or the lowest, or they're all the same, the wait ratio is 1
                else:
                    waitTimeGoingDownRatio = recent_min / recent_max #if the current value is the lowest in the last 25 minutes, the waitRatio is lowest/highest
            except ZeroDivisionError: #shouldn't happen anymore
                waitTimeGoingDownRatio = 0.9 #if it's a zero division, then we messed up somehow, but it happened because recent_min was 0

            #THIS SHOULS ONLY WORK FOR DISNEYLAND - NEED A SOL'N FOR DISNEYWORLD
            yesterday = datetime.now(pytz.timezone("US/Central")) - timedelta(days = 1)
            y_df = pd.read_csv('http://stuhlman.net/gminus/js/ride_data_cleaned_'+str(yesterday.month)+'-'+str(yesterday.day)+'.csv', encoding = "ISO-8859-1")
            
            #2. Predicted wait / current wait (Is the predicted wait higher than the actual wait right now? Good)
            #3. Predicted wait in 30 minutes / predicted wait (Is the predicted wait now better than the wait in 30 minutes? Good. We use predicted weight as the denominator because this is a ratio, and past days might not be representative of current absolute values for wait)
            #4. Current wait / How long you _should_ wait for the ride (average wait time over the course of the day? or personal scoring)
            #THESE WERE ALL UPSIDE DOWN OOPS
            #TO GET THE PREDICTED WAIT TIMES: Look at the last seven days of files and find all waits for this ride within 2 minutes
            #This currently just uses yesterday
            current_time = datetime.now(pytz.timezone("US/Pacific"))
            future_time = current_time + timedelta(minutes = 45)
            #format them
            current_time_label = str(current_time.hour).zfill(2)+':'+str(current_time.minute).zfill(2)
            future_time_label = str(future_time.hour).zfill(2)+':'+str(future_time.minute).zfill(2)
            if df.at[row[0],"park"] in ["DL","DCA"]:
                
                predictedVsCurrentWait = 1
                predictedFutureWaitTimeUp = 1
                currentVsAverage = 1

                waitSameTimeYesterday = int(y_df.loc[y_df['id'] == df.at[row[0],"id"],current_time_label])

                if math.isfinite(waitSameTimeYesterday) and waitSameTimeYesterday > 0: #is the current wait less than the average wait at this exact time?
                    predictedVsCurrentWait = current_wait_time / waitSameTimeYesterday
                if math.isfinite(predictedVsCurrentWait) == False:
                    predictedVsCurrentWait = 1
                
                waitYesterdayIn45Min = int(y_df.loc[y_df['id'] == df.at[row[0],"id"],future_time_label])

                if current_time.hour < 23 and math.isfinite(waitSameTimeYesterday) and math.isfinite(waitYesterdayIn45Min): #don't use this measure last hour of the day
                    try: #do we expect the ride to go up or down in time?
                        predictedFutureWaitTimeUp = waitSameTimeYesterday / waitYesterdayIn45Min
                    except (ValueError,ZeroDivisionError) as error:
                        predictedFutureWaitTimeUp = 1
                    if math.isfinite(predictedFutureWaitTimeUp) == False:
                        predictedFutureWaitTimeUp = 1
                
                averageWait = int(y_df.loc[y_df['id'] == df.at[row[0],"id"],"average_wait"])
                if math.isfinite(averageWait) and averageWait > 0:
                    try: #Is the current wait better than the average wait over the course of the day?
                        currentVsAverage = current_wait_time / averageWait
                    except (ValueError,ZeroDivisionError) as error:
                        currentVsAverage = 1
                
                waitRatio = waitTimeGoingDownRatio + predictedVsCurrentWait + predictedFutureWaitTimeUp + currentVsAverage 
                logFile.append(' ~ '.join([str(row[2]),str(row[1]),"average wait yesterday: " + averageWait,str(waitTimeGoingDownRatio),str(predictedVsCurrentWait),str(predictedFutureWaitTimeUp),str(currentVsAverage),"Sum: "+str(waitRatio)]))

                
                df.at[row[0],"wait_ratio"] = waitRatio
                save_js_remotely("logfile.txt",' | '.join(logFile))
            else:
                df.at[row[0],"wait_ratio"] = waitTimeGoingDownRatio
    else:
        for row in df.itertuples():
            waitRatio = 1
            df.at[row[0],"wait_ratio"] = waitRatio

    return df

#todo: use https://github.com/cubehouse/themeparks for park open/close times so i don't waste cycles

def addLatLon(df): #also correct ride names for formatting
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0"}
    lat_lon_csv = requests.get('http://stuhlman.net/gminus/disney_ride_lat_lon.csv',headers=headers).text
    lat_lon = pd.read_csv(io.StringIO(lat_lon_csv))
    for row in lat_lon.itertuples(): #import latitude and longitude
        df.loc[df.id==row.id,"name"] = row.truename
        df.loc[df.id==row.id,"lat"] = row.lat
        df.loc[df.id==row.id,"lon"] = row.lon
        df.loc[df.id==row.id,"park"] = row.park
        df.loc[df.id==row.id,"single_rider"] = row.single_rider
        df.loc[df.id==row.id,"lightning_lane"] = row.lightning_lane
        df.loc[df.id==row.id,"individual_lightning_lane"] = row.individual_lightning_lane
    return df

def save_js_remotely(filename,file):
    myHostname = "ftp.stuhlman.net"
    myUsername = 'stuhazjf'
    myPassword = os.environ['js_pw']

    ftp = ftplib.FTP(myHostname)
    ftp.set_debuglevel(2)
    ftp.login(myUsername,myPassword)

    ftpResponseMessage = ftp.cwd("/public_html/gminus/js");
    print(ftpResponseMessage)

    file_to_ftp = io.BytesIO(file.encode('utf-8'))
    
    ftpResponseMessage = ftp.storbinary("STOR "+filename,file_to_ftp)
    print(ftpResponseMessage)

    ftp.quit()

def save_html_remotely(filename,file): #it's stupid that I have two different functions for this when _actually_ these functions save to separate locations and not based on filetype
    myHostname = "ftp.stuhlman.net"
    myUsername = 'stuhazjf'
    myPassword = os.environ['js_pw']

    ftp = ftplib.FTP(myHostname)
    ftp.set_debuglevel(2)
    ftp.login(myUsername,myPassword)

    ftpResponseMessage = ftp.cwd("/public_html/gminus");
    print(ftpResponseMessage)

    file_to_ftp = io.BytesIO(file.encode('utf-8'))
    
    ftpResponseMessage = ftp.storbinary("STOR "+filename,file_to_ftp)
    print(ftpResponseMessage)

    ftp.quit()

def clean_waits(df):
    js_waitfile = df.to_json()
    js_waitfile = js_waitfile.replace("'","") #remove apostrophes
    js_waitfile = js_waitfile.replace(r"\u00c3\u0083\u00c2\u0083","") #idk why but this garbage data keeps getting added so let's cut it out
    js_waitfile = "rdata = '[" + js_waitfile + "]';"
    return js_waitfile

def rename_js_with_question_mark(htmlfile,datetxt): #TAKES IN AN HTML FILE and the date in text form to append
    htmlfile2 = htmlfile.replace('js/update_date.js', 'js/update_date.js?'+datetxt) 
    htmlfile3 = htmlfile2.replace('js/ride_data.js', 'js/ride_data.js?'+datetxt)
    return htmlfile3


def main():
    for do_exactly_twice in range(2):
        print("Hello!")
        now = datetime.now(pytz.timezone("US/Pacific")) #Disneyland timezone
        if (now.hour < 5) or (now.hour == 23 and now.minute > 55):
            exit() #Don't run except while a park is open

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0"}
        dis_waits_json = requests.get('https://queue-times.com/en-US/parks/16/queue_times.json',headers=headers).json()
        dca_waits_json = requests.get('https://queue-times.com/en-US/parks/17/queue_times.json',headers=headers).json()
        epcot_waits_json = requests.get('https://queue-times.com/en-US/parks/5/queue_times.json',headers=headers).json()
        mk_waits_json = requests.get('https://queue-times.com/en-US/parks/6/queue_times.json',headers=headers).json()
        dhs_waits_json = requests.get('https://queue-times.com/en-US/parks/7/queue_times.json',headers=headers).json()
        ak_waits_json = requests.get('https://queue-times.com/en-US/parks/8/queue_times.json',headers=headers).json()
        last_updated = requests.get('http://stuhlman.net/gminus/js/update_date.txt').content[3:5] #get the day

        if int(last_updated) != now.day:
            #create a new file with formatted minute-by-minute data
            yesterday = datetime.now(pytz.timezone("US/Pacific")) - timedelta(days = 1)
            save_js_remotely('http://stuhlman.net/gminus/js/ride_data_formatted_'+str(yesterday.month)+'-'+str(yesterday.day)+'.csv',gm_format_csv.format_csv_for_predictions(1))
            #create a new dataframe for rides
            df = pd.DataFrame(columns = ['id','name','current_wait','wait_ratio','lat','lon','park','single_rider','lightning_lane','individual_lightning_lane','average_wait','wait_yesterday','wait_in_30'])
            df = appendRides(df,dis_waits_json)
            df = appendRides(df,dca_waits_json)
            df = addLatLon(df)
            df_dw = pd.DataFrame(columns = ['id','name','current_wait','wait_ratio','lat','lon','park','single_rider','lightning_lane','individual_lightning_lane','average_wait','wait_yesterday','wait_in_30'])
            df_dw = appendRides(df_dw,epcot_waits_json)
            df_dw = appendRides(df_dw,mk_waits_json)
            df_dw = appendRides(df_dw,dhs_waits_json)
            df_dw = appendRides(df_dw,ak_waits_json)
            df_dw = addLatLon(df_dw)
        else:
            df = pd.read_csv('http://stuhlman.net/gminus/js/ride_data.csv', encoding='utf-8')
            df_dw = pd.read_csv('http://stuhlman.net/gminus/js/ride_data_dw.csv', encoding='utf-8')

        if (now.minute) < 10:
            minute_now = "0" + str(now.minute)
        else:
            minute_now = str(now.minute) #make sure the minute has two digits so we can sort by minute

        next_col_name = "z" + str(now.year) + "-" + str(now.month) + "-" + str(now.day) + "-" + str(now.hour) + "-" + minute_now #create a new column with the current time
        df[next_col_name] = ''
        df_dw[next_col_name] = ''
        #create a new column with the date/time

        #amend the latest wait times to the newest column
        df = addWaitTimes(df,dis_waits_json,next_col_name)
        df = addWaitTimes(df,dca_waits_json,next_col_name)
        df = updateWaitRatio(df)

        df_dw = addWaitTimes(df_dw,epcot_waits_json,next_col_name)
        df_dw = addWaitTimes(df_dw,mk_waits_json,next_col_name)
        df_dw = addWaitTimes(df_dw,dhs_waits_json,next_col_name)
        df_dw = addWaitTimes(df_dw,ak_waits_json,next_col_name)
        df_dw = updateWaitRatio(df_dw)

        #convert the dataframe to json
        waitfile = (df.to_csv(index=False, line_terminator='\n',encoding='utf-8'))
        waitfile_dw = (df_dw.to_csv(index=False, line_terminator='\n',encoding='utf-8'))

        js_waitfile = clean_waits(df)
        js_waitfile_dw = clean_waits(df_dw)
        #create a javascript text with wait times

        #create a json w/ date
        datefile = "updated = '" + str(now.hour) + ":" + minute_now + ", " + str(now.month) + "/" + str(now.day)+"'"

        #generate a text file for last day updated
        if (now.month) < 10:
            month_now = "0" + str(now.month)
        else:
            month_now = str(now.month)
        if (now.day) < 10:
            day_now = "0" + str(now.day)
        else:
            day_now = str(now.day)
        date_txt = month_now + "/" + day_now
        date_append_js = str(now.hour) + "-" + minute_now + "-" + str(now.month) + "-" + str(now.day)+"-"

        #open gminus_html_template and add ?date_txt to js/update_date.js and js/ride_data.js
        gminus_html = requests.get("http://stuhlman.net/gminus/gminus_template.html").text #GET THIS FILE FROM TEMPLATE
        gminus_dw_html = requests.get("http://stuhlman.net/gminus/gminus_dw_template.html").text #GET THIS FILE
        gminus_html = rename_js_with_question_mark(gminus_html,date_append_js)
        gminus_dw_html = rename_js_with_question_mark(gminus_dw_html,date_append_js)
        save_html_remotely("gminus.html",gminus_html)
        save_html_remotely("gminus_dw.html",gminus_dw_html) 

        save_js_remotely("ride_data.csv",waitfile) 
        save_js_remotely("ride_data_"+str(now.month)+"-"+str(now.day)+".csv",waitfile)
        save_js_remotely("ride_data_dw.csv",waitfile_dw) 
        save_js_remotely("update_date.js",datefile)
        save_js_remotely("ride_data.js",js_waitfile)
        save_js_remotely("ride_data_dw.js",js_waitfile_dw)
        save_js_remotely("update_date.txt",date_txt)
        print("Files saved, sleeping")
        if (do_exactly_twice==0):
            sleep(297) #we do this every 5 minutes, but it's scheduled for every 10 minutes, so we do it twice instead

main()
