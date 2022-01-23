from datetime import datetime, timedelta
from time import sleep
import requests
import pandas as pd
import os
import pytz

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
    last_col = len(df.columns)
    print(last_col)
    if last_col > 17: #if we have enough data points
        for row in df.itertuples():
            current_wait_time = df.iat[row[0],last_col-1]
            print(current_wait_time)
            #last_6_column = df.iloc[[row[0]],-6:]
            recent_max = max(df.iat[row[0],last_col-1],df.iat[row[0],last_col-2],df.iat[row[0],last_col-3],df.iat[row[0],last_col-4],df.iat[row[0],last_col-5],df.iat[row[0],last_col-6],df.iat[row[0],last_col-7])   #should just be a slice of the df though
            recent_min = min(df.iat[row[0],last_col-1],df.iat[row[0],last_col-2],df.iat[row[0],last_col-3],df.iat[row[0],last_col-4],df.iat[row[0],last_col-5],df.iat[row[0],last_col-6],df.iat[row[0],last_col-7]) 
            #get the minimum (and maximum) of the last 50 minutes - this is terrible and there's a cleaner way to do it but righ now it just grabs the last entries individualy            

            try:
                if recent_max == 0:
                    waitRatio = 0
                elif current_wait_time > recent_min:
                    if recent_min == 0:
                        waitRatio = 0.9 #if a ride has had recent downtime, it's a good choice
                    elif current_wait_time == recent_max:
                        waitRatio = recent_max / recent_min #if the current value is the highest in the last 25 minutes, the waitRatio is highest/lowest
                    else:
                        waitRatio = 1 #if the current wait time isn't the highest or the lowest, or they're all the same, the wait ratio is 1
                else:
                    waitRatio = recent_min / recent_max #if the current value is the lowest in the last 25 minutes, the waitRatio is lowest/highest
                df.at[row[0],"wait_ratio"] = waitRatio
            except ZeroDivisionError: #shouldn't happen anymore
                waitRatio = 0.9 #if it's a zero division, then we messed up somehow, but it happened because recent_min was 0
                df.at[row[0],"wait_ratio"] = waitRatio
            print(waitRatio)
    else:
        for row in df.itertuples():
            waitRatio = 1
            df.at[row[0],"wait_ratio"] = waitRatio
    return df
    """
    with pysftp.Connection('server90.web-hosting.com', username='stuhazjf', password='QXNoLW1hbjE=') as sftp:
        with sftp.cd('/public_html/images'):           # temporarily chdir 
            sftp.put('/filename')  	# upload file to images/filename
    """

#todo: use https://github.com/cubehouse/themeparks for park open/close times so i don't waste cycles

def addLatLon(df): #also correct ride names for formatting
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0"}
    lat_lon_csv = requests.get('http://stuhlman.net/genieminus/disney_ride_lat_lon.csv',headers=headers)
    print(lat_lon_csv)
    lat_lon = pd.read_csv(lat_lon_csv)
    for row in lat_lon.itertuples(): #import latitude and longitude
        df.loc[df.id==row.id,"name"] = row.truename
        df.loc[df.id==row.id,"lat"] = row.lat
        df.loc[df.id==row.id,"lon"] = row.lon
        df.loc[df.id==row.id,"park"] = row.park
        df.loc[df.id==row.id,"single_rider"] = row.single_rider
        df.loc[df.id==row.id,"lightning_lane"] = row.lightning_lane
        df.loc[df.id==row.id,"individual_lightning_lane"] = row.individual_lightning_lane
    return df

def main():
    now = datetime.now(pytz.timezone("US/Pacific")) #Disneyland timezone
    if (now.hour < 8) or (now.hour == 23 and now.minute > 55):
        exit() #Don't run except between 8-midnight

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0"}
    dis_waits_json = requests.get('https://queue-times.com/en-US/parks/16/queue_times.json',headers=headers).json()
    dca_waits_json = requests.get('https://queue-times.com/en-US/parks/17/queue_times.json',headers=headers).json()

    waits_csv_today = 'disney_waits_' + str(now.month) + "-" + str(now.day) + ".csv"
    waits_json_today = '/js/ride_data_x.js'
    date_js_today = '/js/update_date.js'

    if not os.path.exists(waits_csv_today): #Check if we already have a file. If we don't already have a file, make one.
        #This means that the Json gets overwritten even if it's a new day! We don't need yesterday's json.
        df = pd.DataFrame(columns = ['id','name','current_wait','wait_ratio','lat','lon','park','single_rider','lightning_lane','individual_lightning_lane'])
        df = appendRides(df,dis_waits_json)
        df = appendRides(df,dca_waits_json)
        df = addLatLon(df)
    else:
        df = pd.read_csv(waits_csv_today,encoding='latin1')

    print(df)

    try:    
        dis_waits_json = requests.get('https://queue-times.com/en-US/parks/16/queue_times.json').json()
        dca_waits_json = requests.get('https://queue-times.com/en-US/parks/17/queue_times.json').json()
    except: #should be a specific exception - it's an exception if the json doesn't load
        print("Oops - couldn't update wait times from API!")
    next_check = datetime.now()

    if (now.minute) < 10:
        minute_now = "0" + str(now.minute)
    else:
        minute_now = str(now.minute) #make sure the minute has two digits so we can sort by minute

    next_col_name = "z" + str(next_check.year) + "-" + str(next_check.month) + "-" + str(next_check.day) + "-" + str(next_check.hour) + "-" + minute_now #create a new column with the current time
    df[next_col_name] = ''
    #create a new column with the date/time

    df = addWaitTimes(df,dis_waits_json,next_col_name)
    df = addWaitTimes(df,dca_waits_json,next_col_name) #these two amend the latest wait times to the newest column

    df = updateWaitRatio(df)

    #wait until the next five minutes - should start at a given time for consistency
    with open (waits_csv_today,'w') as waitfile:
        waitfile.write(df.to_csv(index=False, line_terminator='\n',encoding='latin1'))
    with open (waits_json_today,'w') as waitfile:
        js_to_write = df.to_json()
        js_to_write = js_to_write.replace("'","")
        js_to_write = "rdata = '[" + js_to_write + "]';"
        waitfile.write(js_to_write) #needs to add " rdata = '[  " at the top, and end in "    ]';   ", and remove all apostrophes
    with open(date_js_today,'w') as datefile:
        datefile.write("updated = '" + str(next_check.hour) + ":" + minute_now + ", " + str(next_check.month) + "/" + str(next_check.day)+"'")

main()