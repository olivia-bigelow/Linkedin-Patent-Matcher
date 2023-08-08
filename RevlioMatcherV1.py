#this code needs to parse the USPTO data, and match it to the revelio data all of them can map patent id-> the rest 

#import necessary packages
import pandas as pd
from thefuzz import fuzz, process
import csv

#this function takes an input, and if its an instance of a string returns that, and if its a series, returns the first attribute in it.
def getStuff(object):
    if hasattr(object, '__iter__'):
        object = next(iter(object))
    return str(object)    

#this function determines if abbr is an abbreviation of original
def checkAbbreviation(original, abbr):
    for char in abbr:
        if(not (char in original)):
            return False        
    return True


#function to make the strings in a column lowercase
def lowercase_strings(col):
    if col.dtype == object:
        return col.str.lower()
    return col
#a function determining if a target date is inbetween a start and end range
#this function returns true if a date is missing
def dateBetween(dateTarget, dateStart, dateEnd):
    if isinstance(dateTarget, str):
        dateTarget = dateTarget.strip()
        if len(dateTarget) < 9:
            return True
    elif hasattr(dateTarget, '__iter__'):
        dateTarget = next(iter(dateTarget)).strip()
        if len(dateTarget) < 9:
            return True
    
    if isinstance(dateStart, str):
        dateStart = dateStart.strip()
        if len(dateStart) < 9:
            return True
    elif hasattr(dateStart, '__iter__'):
        dateStart = next(iter(dateStart)).strip()
        if len(dateStart) < 9:
            return True
    
    if isinstance(dateEnd, str):
        dateEnd = dateEnd.strip()
        if len(dateEnd) < 9:
            return True
    elif hasattr(dateEnd, '__iter__'):
        dateEnd = next(iter(dateEnd)).strip()
        if len(dateEnd) < 9:
            return True
    
    
    #the years position, its either out, in, equal  to start, or equal to end
    if ((int(dateTarget[0:4]) < int(dateStart[0:4])) | (int(dateTarget[0:4]) > int(dateEnd[0:4]))):
        return False
    if ((int(dateTarget[0:4]) > int(dateStart[0:4])) & (int(dateTarget[0:4]) < int(dateEnd[0:4]))):
        return True
    
    
    if int(dateTarget[0:4]) == int(dateStart[0:4]):
        #if equal to start, check if month is higher than startmonth
        if int(dateTarget[5:7]) < int(dateStart[5:7]):
            #if its not return false
            return False
        #if its equal check if day is higher or equal to than startday
        if ((int(dateTarget[5:7]) == int(dateStart[5:7])) & (int(dateTarget[8:10]) < int(dateStart[8:10]))):
            return False
    if int(dateTarget[0:4]) == int(dateEnd[0:4]):
    #if equal to end, check if month is smaller than endmonth
        if int(dateTarget[5:7]) > int(dateEnd[5:7]):
            return False
        #if its equal, check if day is less than or equal to end day
        if ((int(dateTarget[5:7]) == int(dateEnd[5:7])) & (int(dateTarget[8:10]) > int(dateEnd[8:10]))):
            return False
    return True
#this method returns an array containing
#a matching score 
#6: exact name and location, 5: exact name, fuzzy location, 4: exact location, fuzzy name, 3: fuzzy name and location, 
#2: exact name no location, 1: fuzzy name no location, 0: no match
#a number of matches
#a dataframe of the position data of the best match
def match(firstName, LastName, city, state, country, date, usersDF, posDfs):
    
    exactName = True
    exactLoc = True
    #get users of the first name and last name
    ids = usersDF.loc[(usersDF['firstname'] == firstName) & (usersDF['lastname'] == LastName), 'user_id']

    #if there are no found names, try a fuzzy match
    if len(ids) == 0:
        exactName = False
        names = process.extract(firstName + " " + LastName, usersDF['fullname'], scorer=fuzz.partial_ratio, limit = 50)
        first = True
        for name in names:
            if name[1] > 60:
                if first :
                    ids = usersDF.loc[usersDF['fullname'] == name[0], 'user_id']
                    first = False
                else :
                    ids = pd.concat((ids, (usersDF.loc[usersDF['fullname'] == name[0], 'user_id'])), axis=0)
    #if no viable names are found with fuzzy matching, there is no pairing
    if len(ids) == 0:
        return [0]
    #go through the userids, find exact location on position and date. 
    posDateMatch = []
    for id in ids: #id is a dataframe
        for df in posDfs:
            #find any matches 
            tempLoc = df[df["user_id"] == id].loc[(lambda x: x.apply(lambda row: dateBetween(date, row['startdate'], row['enddate']), axis=1)).iloc[:,0]]
            if len(tempLoc) > 0:
                posDateMatch.append(tempLoc)

    #posdatematch contains all jobs of name matched possible linkedin users during the time of the patent application
    #if no matches were found, then return 0
    if len(posDateMatch) == 0:
        return [0]

    #attempt to make exact location matches
    exactLocMatch = []
    for pos in posDateMatch:
        if state == 'nan' or not state.strip():
        #an exact match on location is not possible with this data, instead I've opted for an "exact" match
        #country is 2 letters, and pos["country"] is a full word, I use a partial ratio match with a threshold of 100 which only flags true
        #if both letters are contained in the full word. pos does not contain city infromation. rather is has a raw location and a metropolitan statistical area
        #if either one of those contain the city with 95% accuracy on a partial ratio match, then it is considered an "exact match" 
            if (checkAbbreviation(getStuff(pos["country"]), country)) & ((fuzz.partial_ratio(getStuff(pos["location_raw"]), city) > 95) | (fuzz.partial_ratio(getStuff(pos["msa"]), city) > 95)):
                exactLocMatch.append(pos)
        else:
            if ((checkAbbreviation(getStuff(pos["country"]), country))) & (checkAbbreviation(getStuff(pos["state"]), state)) & ((fuzz.partial_ratio(getStuff(pos["location_raw"]), city) > 95) | (fuzz.partial_ratio(getStuff(pos["msa"]), city) > 95)):
                exactLocMatch.append(pos)

    bestLocMatch = pd.DataFrame()
    #if no exact match, attempt to find a fuzzy location above a threshold (currnetly 60)
    if len(exactLocMatch) == 0:
        exactLoc = False
        maxFuzzAmt = 0
        for pos in posDateMatch:
            if state == None or not state.strip():
                tempFuzzAmt = fuzz.partial_ratio(country + " " + city, getStuff(pos["country"]) + " " + getStuff(pos["location_raw"]) + " " +getStuff(pos["msa"]))
                if ((tempFuzzAmt > 60) & (tempFuzzAmt > maxFuzzAmt)):
                    maxFuzzAmt = tempFuzzAmt
                    bestLocMatch = pos
            else:
                tempFuzzAmt = fuzz.partial_ratio(country + " " + state + " " + city, getStuff(pos["country"]) + " " + getStuff(pos["state"]) + " " + getStuff(pos["location_raw"]) + " " +getStuff(pos["msa"]))
                if ((tempFuzzAmt > 60) & (tempFuzzAmt > maxFuzzAmt)):
                    maxFuzzAmt = tempFuzzAmt
                    bestLocMatch = pos
    #save the best match found 
    else:
        bestLocMatch = bestLocMatch.add(exactLocMatch[0])
    #if no location was found at threshold of 60, then return the best name match
    if (bestLocMatch.empty):
        if exactName:
            return[2, len(posDateMatch), posDateMatch[0]]
        else:
            return[1,len(posDateMatch), posDateMatch[0]]
    
    exactLocMatch.append(bestLocMatch)    
    #if locations were found, return the approriate match
    if exactName:
        if exactLoc:
            return [6, len(exactLocMatch), exactLocMatch[0]]
        else:
            return [5, len(exactLocMatch), exactLocMatch[0]]
    else:
        if exactLoc:
            return [4, len(exactLocMatch), exactLocMatch[0]]
        else:
            return [3, len(exactLocMatch), exactLocMatch[0]]

#function to pair data and write it to a file
def pairAndWrite(application, writer, inventorDF, locationDF,usersDF, posDfs):
    #get the patent id and date from the application 
    patentid = application.patent_id
    date = application.filing_date
    #get the inventor name from invetors
    invInfo = inventorDF.loc[inventorDF['patent_id'] == patentid]
    firstName = (invInfo['disambig_inventor_name_first'].to_string(index=False))
    lastName = (invInfo['disambig_inventor_name_last'].to_string(index=False))
    invID = (invInfo['inventor_id'].to_string(index=False))
    locID = (invInfo['location_id'].to_string(index=False))
    locInfo = locationDF.loc[locationDF['location_id'] == locID]
    city = getStuff(locInfo['disambig_city'])
    state = getStuff(locInfo['disambig_state'])
    country = getStuff(locInfo['disambig_country'])

    #find matches 
    matchInfo = match(firstName=firstName, LastName=lastName, city=city, state=state, country=country, date = date, usersDF=usersDF, posDfs=posDfs)

    print("writing")
    #parse the match info and make it wrtieable 
    if (matchInfo[0] == 0):
        writer.writerow([patentid, invID, firstName + " " + lastName, 0])
    else:
        writer.writerow([patentid, invID, firstName + " " + lastName, matchInfo[0], matchInfo[2]['user_id'].iloc[0]])


#start by making a data frame for g_patent
patentDF = pd.read_table("/uufs/chpc.utah.edu/common/home/fengj-group1/PatentGrant/g_application.tsv").apply(lambda col: lowercase_strings(col))
#patentDF = pd.read_table(r"M:/divin/ReposHard/vscode repos/revelio test datasets/application.txt").apply(lambda col: lowercase_strings(col))
#parse location data
locationDF = pd.read_table("/uufs/chpc.utah.edu/common/home/fengj-group1/PatentGrant/g_location_disambiguated.tsv").apply(lambda col: lowercase_strings(col))
#locationDF = pd.read_table("M:/divin/ReposHard/vscode repos/revelio test datasets/location.txt").apply(lambda col: lowercase_strings(col))

#parse inventor data
inventorDF = pd.read_table("/uufs/chpc.utah.edu/common/home/fengj-group1/PatentGrant/g_inventor_disambiguated.tsv").apply(lambda col: lowercase_strings(col))
#inventorDF = pd.read_table("M:/divin/ReposHard/vscode repos/revelio test datasets/inventor.txt").apply(lambda col: lowercase_strings(col))

#load in linkedin users
usersDF = pd.read_csv('/uufs/chpc.utah.edu/common/home/fengj-group1/Revelio/Individual User/user_0000_part_00.csv').apply(lambda col: lowercase_strings(col))
#usersDF = pd.read_csv("M:/divin/ReposHard/vscode repos/revelio test datasets/user.txt").apply(lambda col: lowercase_strings(col))
for i in range(1, 247):
    strnum = '0' + str(i)
    while len(strnum) < 4:
        strnum = '0' + strnum
    usersDF = pd.concat([usersDF, pd.read_csv('/uufs/chpc.utah.edu/common/home/fengj-group1/Revelio/Individual User/user_' + strnum +'_part_00.csv')], ignore_index=True)

#load in linkedin positions
posDfs = []
for i in range(0,5):
#for i in range(0,219):
    strnum = '0' + str(i)
    while len(strnum) < 4:
        strnum = '0' + strnum
    posDfs.append(pd.read_csv('/uufs/chpc.utah.edu/common/home/fengj-group1/Revelio/Individual Position/position_' + strnum +'_part_00.csv').apply(lambda col: lowercase_strings(col)))
#posDfs.append(pd.read_csv("M:/divin/ReposHard/vscode repos/revelio test datasets/position.txt").apply(lambda col: lowercase_strings(col)))


# open the file in the write mode
f = open('/scratch/general/vast/u1188824/revelio_output_1.csv', 'w')
#f = open("M:/divin/ReposHard/vscode repos/revelio test datasets/output.txt", 'w')

# create the csv writer
writer = csv.writer(f)
writer.writerow(["PatentID", "InventorID", "inventorName", "MatchScore", "UserID"])
#use df.apply 
patentDF.apply(pairAndWrite, axis = 1, args = [writer, inventorDF, locationDF, usersDF, posDfs])


# close the file
f.close()





