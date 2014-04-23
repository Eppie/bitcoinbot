import re

def readFile(f):
    lines = [line.replace("'", "").replace("[", "").replace("]", "").replace(" ", "").strip() for line in open(f)]    
    return lines

def average(lines):
    total = 0
    for line in lines:
        temp = line.split(',')
        total = total + float(temp[0])
    return total / len(lines)

def maximum(lines):
    maximum = 0.0
    for line in lines:
        temp = line.split(',')
        if float(temp[0]) > maximum:
            maximum = float(temp[0])
    return maximum

def minimum(lines):
    minimum = 99999999
    for line in lines:
        temp = line.split(',')
        if float(temp[0]) < minimum:
            minimum = float(temp[0])
    return minimum

lines = readFile('btc_log.txt')
average = average(lines)
maximum = maximum(lines)
minimum = minimum(lines)
print 'average: ' + str(average)
print 'maximum: ' + str(maximum)
print 'minimum: ' + str(minimum)
