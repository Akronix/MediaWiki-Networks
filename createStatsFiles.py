import networkTools as nT
import csv
import yaml
import datetime as dt

with open('config.yaml', 'rb') as f:
    config = yaml.load(f)

nodeList = '/home/jeremy/Programming/WeRelate/DataFiles/WatchAndLearn/watchAndLearnNodes.csv'
saveLocation = '/home/jeremy/Programming/WeRelate/DataFiles/WatchAndLearn/'
startDate = config['startDate']
endDate = config['endDate']
delta = dt.timedelta(days=config['timeDelta']) # Time between networks, in days
behavior = config['behavior']
categories = config['editCats']
otherStats = ['start_date','end_date','active_days','all_edits','user_id']

print categories

dateList = []
currStart = startDate
while currStart <= endDate - delta:
    dateList.append(currStart)
    currStart += delta


with open(nodeList, 'rb') as i:
    nl = [int(x[0]) for x in csv.reader(i)]
    behavTotal = []
    attributeTotal = {c:[] for c in categories}
    for user in nl:
        print user
        behaviorStats = []
        attributeStats = {c:[] for c in categories}
        for date in dateList:
            stats = nT.getStats(user, date, categories, otherStats)
            if not stats:
                print "no stats for {}".format(user)
            for stat in stats:
                if stat == behavior:
                    behaviorStats.append(stats[stat])
                elif stat in categories:
                    attributeStats[stat].append(stats[stat])
                else:
                    continue
        behavTotal.append(behaviorStats)
        for att in attributeStats:
            attributeTotal[att].append(attributeStats[att])

with open("{}_behavior.csv".format(saveLocation), 'wb') as b:
    bFile = csv.writer(b, delimiter=' ')
    bFile.writerows(behavTotal)

for c in categories:
    with open("{}{}_attributes.csv".format(saveLocation, c), 'wb') as a:
        aFile = csv.writer(a, delimiter = ' ')
        aFile.writerows(attributeTotal[c])
