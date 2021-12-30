from csv import DictReader, DictWriter
from datetime import date
import csv
import pandas
import math

"""
TO USE: You will need to update the directory of the CSVs in line 34 and 37

Process:
0. Variable: Current time
1. Create a table of all rides
2. Loop until 9 PM: Go to the ride with the lowest adjusted wait time, wait the _actual_ wait time + walk distance.
Adjusted wait time = 2x wait time - max wait time + 2x walk time (to avoid walking back and forth)
This calculation is done in the CSV
"""

current_hour = 8 #Start time in the park
current_minute = 0 #easier to work with than a single number bc my chart uses hours... jeez
rides_done = []
zone = ""
nextride = 12 #first ride is always peter pan's flight
nextride_wait = 0
nextride_actual_wait = 0
nextride_walk = 0
time_walked = 0
time_waited = 0
time_on_rides = 0

print_full = 0

with open("C:/Users/Asher/Documents/disney_ride_waits.csv") as f:  
    rides_and_waits = pandas.read_csv(f).set_index('ride_key')

with open("C:/Users/Asher/Documents/disney_walks.csv") as f:
    walktimes = pandas.read_csv(f).set_index('zone_key')
    
#print(rides_and_waits.loc[rides_and_waits['ride_key'] == 7])

#for ride in rides_and_waits.iterrows():
#    print(ride[1]["Ridename"])

#print(rides_and_waits.loc[rides_and_waits['ride_key'] == nextride]["Ridename"])

def timeTaken(ride_num,hour_of_ride):
    if hour_of_ride == 8:
        return rides_and_waits.loc[ride_num]["8H"]
    elif hour_of_ride == 9:
        return rides_and_waits.loc[ride_num]["9H"]
    elif hour_of_ride == 10:
        return rides_and_waits.loc[ride_num]["10H"]
    elif hour_of_ride == 11:
        return rides_and_waits.loc[ride_num]["11H"]
    elif hour_of_ride == 12:
        return rides_and_waits.loc[ride_num]["12H"]
    elif hour_of_ride == 13:
        return rides_and_waits.loc[ride_num]["13H"]
    elif hour_of_ride == 14:
        return rides_and_waits.loc[ride_num]["14H"]
    elif hour_of_ride == 15:
        return rides_and_waits.loc[ride_num]["15H"]
    elif hour_of_ride == 16:
        return rides_and_waits.loc[ride_num]["16H"]
    elif hour_of_ride == 17:
        return rides_and_waits.loc[ride_num]["17H"]
    elif hour_of_ride == 18:
        return rides_and_waits.loc[ride_num]["18H"]
    elif hour_of_ride == 19:
        return rides_and_waits.loc[ride_num]["19H"]
    elif hour_of_ride == 20:
        return rides_and_waits.loc[ride_num]["20H"]
    else:
        return rides_and_waits.loc[ride_num]["21H"]

def timeExpected(ride_num,hour_of_ride):
    if hour_of_ride == 8:
        return rides_and_waits.loc[ride_num]["8CH"]
    elif hour_of_ride == 9:
        return rides_and_waits.loc[ride_num]["9CH"]
    elif hour_of_ride == 10:
        return rides_and_waits.loc[ride_num]["10CH"]
    elif hour_of_ride == 11:
        return rides_and_waits.loc[ride_num]["11CH"]
    elif hour_of_ride == 12:
        return rides_and_waits.loc[ride_num]["12CH"]
    elif hour_of_ride == 13:
        return rides_and_waits.loc[ride_num]["13CH"]
    elif hour_of_ride == 14:
        return rides_and_waits.loc[ride_num]["14CH"]
    elif hour_of_ride == 15:
        return rides_and_waits.loc[ride_num]["15CH"]
    elif hour_of_ride == 16:
        return rides_and_waits.loc[ride_num]["16CH"]
    elif hour_of_ride == 17:
        return rides_and_waits.loc[ride_num]["17CH"]
    elif hour_of_ride == 18:
        return rides_and_waits.loc[ride_num]["18CH"]
    elif hour_of_ride == 19:
        return rides_and_waits.loc[ride_num]["19CH"]
    elif hour_of_ride == 20:
        return rides_and_waits.loc[ride_num]["20CH"]
    else:
        return rides_and_waits.loc[ride_num]["21CH"]

def walktime(start,finish):
    return walktimes.loc[start][finish]

for startride in range(47):
        current_hour = 8 #Start time in the park
        current_minute = 0 #easier to work with than a single number bc my chart uses hours... jeez
        rides_done = []
        zone = ""
        nextride_wait = 0
        nextride_actual_wait = 0
        nextride_walk = 0
        time_walked = 0
        time_waited = 0
        time_on_rides = 0
        skip_flag = 0 #if any ride was skipped - run is invalid
        nextride = startride+1

    #try: 
        while current_hour < 21:
            #ride the queued ride
            if not math.isnan(timeTaken(nextride,current_hour)): #if the ride hasn't stopped for the day
                wait_time = round(timeTaken(nextride,current_hour))
                current_minute += wait_time
                
                ride_time = round(rides_and_waits.loc[nextride]["Duration"])
                current_minute += ride_time

                current_minute += nextride_walk

                while current_minute >= 60:
                    current_minute -= 60
                    current_hour += 1

                if print_full == 1 or  startride == 3:
                    print(rides_and_waits.loc[nextride]["Ridename"])
                    print("Walk: "+str(nextride_walk)+" minutes")
                    print("Wait: "+str(wait_time)+" minutes")
                    print("Ride time: "+str(ride_time)+" minutes")
                    if current_minute>9:
                        print("Current time: "+str(current_hour)+":"+str(current_minute))
                    else:
                        print("Current time: "+str(current_hour)+":0"+str(current_minute))

                time_walked += nextride_walk
                time_waited += nextride_actual_wait
                time_on_rides += ride_time
            else:  
                #print("Skipped "+rides_and_waits.loc[nextride]["Ridename"])
                skip_flag = 1

            #print ("Loop check "+str(startride)+" "+str(nextride)+" "+str(time_on_rides))

            rides_done.append(nextride)
            current_zone = rides_and_waits.loc[nextride]["zone_key"] #set a variable that holds the previous ride's zone
            nextride = -1 #figure out next ride
            nextride_wait_factor = 200 #used to decide which ride to go to - above the highest wait time
            nextride_wait = 200

            for ride in rides_and_waits.iterrows():
                ride_n = ride[0]
                if timeExpected(ride_n,current_hour) + walktime(current_zone,rides_and_waits.loc[ride_n]["zone_key"]) < nextride_wait_factor and not ride_n in rides_done and not (ride_n >= 30 and current_hour<13): #this last bit just says no DCA rides before 1 - 
                    nextride = ride_n
                    nextride_wait = timeExpected(ride_n,current_hour)
                    nextride_actual_wait = timeTaken(ride_n,current_hour)
                    nextride_walk = walktime(current_zone,rides_and_waits.loc[ride_n]["zone_key"])
                    nextride_wait_factor = nextride_wait + nextride_walk*3

            if nextride == -1:
                break
            
            if print_full == 1 or startride == 3:
                if current_zone != rides_and_waits.loc[nextride]["zone_key"]:
                    print("Walking from " + walktimes.loc[current_zone]["Zone"] + " to " +  walktimes.loc[rides_and_waits.loc[nextride]["zone_key"]]["Zone"]+"... ")
                print(" ")

            #print("Next ride is: " + rides_and_waits.loc[nextride]["Ridename"])
            #break
        print(startride)
        if skip_flag == 0:
            print("Started at "+rides_and_waits.loc[startride+1]["Ridename"])
            if current_hour >= 21:
                print("Ran out of time!")
            elif current_minute>9:
                print("Final time: "+str(current_hour)+":"+str(current_minute))
            else:
                print("Final time: "+str(current_hour)+":0"+str(current_minute))
            print ("Time walking: "+ str(time_walked))
            print ("Time waiting: " + str(round(time_waited)))
            print ("Time on rides: " + str(time_on_rides))
    #except: 
        #print("Can't start with that ride")
        #break