#!/usr/bin/env python

import sys, codecs, json, time
import numpy as np
import pandas as pd
#from TwitterApplicationHandler import TwitterApplicationHandler
from twython import TwythonStreamer, Twython
from datetime import datetime
from dateutil.parser import parse as parse_date
import requests
import emoji
from skimage import io
import re, string, unicodedata

from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from stop_words import get_stop_words
from nltk.corpus import stopwords

import emoji
from emoji import UNICODE_EMOJI


SEARCHCOUNT = 100

class FilterAPI(TwythonStreamer):
	def on_success(self, data):  #KRC__this is the callback [event happens, this fires]
		dt = datetime.now()
		filename = "data/example_samp_-%s.txt" % (dt.strftime("%Y-%m-%d"),)  #KRC__store data in file, filename changes per day!
		#if 'text' in data:
		if data['text'].split()[0]=='RT':  #do not include retweets
			return

		print(data['text'])
		fp = codecs.open(filename, 'a', 'utf-8')
		fp.write(json.dumps(data))
		fp.write("\n")
		fp.close()

	def on_error(self, status_code, data):
		print("ERROR!")
		print(status_code)

class SampleAPI(TwythonStreamer):
	def on_success(self, data):  #KRC__this is the callback [event happens, this fires]

		#if the tweet is a 'non-oroginal' tweet..also, non-deleted tweet:
		if notOriginalTweet(data):
			return

		dt = datetime.now()
		filename = "data/example_sampFiltNew_again2_-%s.txt" % (dt.strftime("%Y-%m-%d"),)  #KRC__store data in file, filename changes per day!
		
		fp = codecs.open(filename, 'a', 'utf-8')
		fp.write(json.dumps(data))
		fp.write("\n")
		fp.close()

	def on_error(self, status_code, data):
		print("ERROR!")
		print(status_code)

def notOriginalTweet(tweet):
	if 'delete' in tweet:
		return True
	if 'retweeted_status' in tweet:
		return True
	if 'in_reply_to_status_id' in tweet:
		if tweet['in_reply_to_status_id']:
			return True
	if 'in_reply_to_status_id_str' in tweet:
		if tweet['in_reply_to_status_id_str']:
			return True
	if 'in_reply_to_user_id' in tweet:
		if tweet['in_reply_to_user_id']:
			return True
	if 'in_reply_to_user_id_str' in tweet:
		if tweet['in_reply_to_user_id_str']:
			return True
	if 'in_reply_to_screen_name' in tweet:
		if tweet['in_reply_to_screen_name']:
			return True
	return False
	#A BETTER WAY..have set(keys_to_check) then get tweet.keys() then check from there....

def printTweet(tweet):
	print(json.dumps(tweet,indent=2,sort_keys=False))
	return

#pass in stings with your keys
#initializes the twython api object [opens the twitter api]
#returns the api object
def initAPI(app_key,app_sec,user_key,user_sec):
	# Load in OAuth Tokens  #KRC__these are specific to me! [twitter dev]
	#app_key = "YOUR_API_KEY_HERE"  #KRC__api_key
	#app_sec = "YOUR_API_SECRETKEY_HERE"  #KRC__api_secretKey
	#user_key = "YOUR_ACCESS_TOKEN_HERE"  #KRC__access_token
	#user_sec = "YOUR_ACCESS_TOKEN_SECRET_HERE"  #KRC__access_token_secret

	api = Twython(app_key, app_sec, user_key, user_sec)  #KRC__this is the connection!

	return api

def initStreamAPI(streamType='default'):
	# Load in OAuth Tokens  #KRC__these are specific to me! [twitter dev]
	app_key = "YOUR_API_KEY_HERE"  #KRC__api_key
	app_sec = "YOUR_API_SECRETKEY_HERE"  #KRC__api_secretKey
	user_key = "YOUR_ACCESS_TOKEN_HERE"  #KRC__access_token
	user_sec = "YOUR_ACCESS_TOKEN_SECRET_HERE"  #KRC__access_token_secret

	if streamType == 'sample':
		stream = SampleAPI(app_key, app_sec, user_key, user_sec)
		return stream

	stream = FilterAPI(app_key, app_sec, user_key, user_sec)  #KRC__this is the connection!

	return stream


#returns all results that were returned for the api call passed as func.
#returns list of objects [each entry was a return from the api]
#this helper function wraps rate limit checking around subsequent calls to avoid lockout/abusing rate limits
def rateLimitWrapper(api,func,kwargs,willingToWait=False,maxExecTime=10):
	#status = api.get_application_rate_limit_status()  #twitters rate limit status response..good for checking before start
	#numLeft = api.get_lastfunction_header('x-rate-limit-remaining')  #this is better b/c it does not make an extra api call just to get info
	#resetTime = api.get_lastfunction_header('x-rate-limit-reset')
	#func(args)
	print('entering rateLimitWrapper')
	results = []
	status = api.get_application_rate_limit_status()  #twitters rate limit status response..good for checking before start
	resetTime = int(status['resources']['search']['/search/tweets']['reset'])  #reset time
	remainingRequests = int(status['resources']['search']['/search/tweets']['remaining'])  #remaining calls available in this time windowq

	if remainingRequests == 0:  #already hit rate limit, either wait or return False
		if willingToWait == True:
			timeToWait = resetTime - time.time()
			time.sleep(timeToWait)
		else:
			print('You have hit rate limit and are not willing to wait. Canceling this call\n')
			return []

	#run first request here
	timeStart = time.time()
	response = func(**kwargs)
	results.append(response)
	print('1st response done')
	
	while ('next_results' in response['search_metadata'].keys()) and ((time.time() - timeStart) < maxExecTime):  #if a query returns empty status list, assume we are done. also done if time > maxExecTime
		#process previous request
		print('entering while loop')

		nextMax = int(response['search_metadata']['next_results'].split('=')[1].split('&')[0])  #we want tweets older than this one!
		kwargs['max_id'] = nextMax  #actually update the parameter

		resetTime = api.get_lastfunction_header('x-rate-limit-reset')
		remainingRequests = api.get_lastfunction_header('x-rate-limit-remaining')  #this is better b/c it does not make an extra api call just to get info
		
		if remainingRequests == 0:
			#need to wait
			print('waiting in while loop')
			timeToWait = resetTime - time.time()
			time.sleep(timeToWait)
		#make the request

		response = func(**kwargs)  #now include max_id
		results.append(response)
		
		print('while loop responce done')
	print('returning from rateLimitWrapper')
	return results

def rateLimitWrapperTimeline(api,func,kwargs,willingToWait=False,maxExecTime=10):
	#status = api.get_application_rate_limit_status()  #twitters rate limit status response..good for checking before start
	#numLeft = api.get_lastfunction_header('x-rate-limit-remaining')  #this is better b/c it does not make an extra api call just to get info
	#resetTime = api.get_lastfunction_header('x-rate-limit-reset')
	#func(args)
	#print('entering rateLimitWrapper')
	results = []
	status = api.get_application_rate_limit_status()  #twitters rate limit status response..good for checking before start
	resetTime = int(status['resources']['statuses']['/statuses/user_timeline']['reset'])  #reset time
	remainingRequests = int(status['resources']['statuses']['/statuses/user_timeline']['remaining'])  #remaining calls available in this time windowq

	#print('resetTime: %s'%resetTime)
	#print('remainingRequests: %s'%remainingRequests)

	if remainingRequests == 0:  #already hit rate limit, either wait or return False
		if willingToWait == True:
			timeToWait = resetTime - time.time()
			if timeToWait > 0:  #else, no wait needed
				print('rate limit, sleeping before while loop')
				time.sleep(timeToWait)
		else:
			print('You have hit rate limit and are not willing to wait. Canceling this call\n')
			return []

	#run first request here
	timeStart = time.time()
	try:
		response = func(**kwargs)
	except:
		print('ErrorCaught 1st')
		response = ['ErrorCaught']
		results.extend(response)
		return response

	if not response:  #i.e. the response was empty
		return []
	#results.append(response)
	results.extend(response)
	#print('1st response done')
	
	while ((time.time() - timeStart) < maxExecTime):  #if a query returns empty status list, assume we are done. also done if time > maxExecTime
		#process previous request
		#print('entering while loop')

		tweetIds = [status['id'] for status in response]
		nextMax = np.min(tweetIds)-1  #get the lowest id number for pagination next search
		##print('lowest_id: %s'%(nextMax+1))
		#print(kwargs)
		kwargs['max_id'] = int(nextMax)  #actually update the parameter


		resetTime = api.get_lastfunction_header('x-rate-limit-reset')
		remainingRequests = api.get_lastfunction_header('x-rate-limit-remaining')  #this is better b/c it does not make an extra api call just to get info
		
		if remainingRequests == 0:
			#need to wait
			#print('waiting in while loop')
			timeToWait = resetTime - time.time()
			if timeToWait > 0:  #else, we dont need to wait anymore
				print('rate limit, sleeping inside while loop')
				time.sleep(timeToWait)
		#make the request
		response = []  #reset
		try:
			response = func(**kwargs)  #now include max_id
		except:
			print('ErrorCaught in loop')
			response = ['ErrorCaught']
			results.extend(response)
			break
		##print('returned responses: %s'%len(response))
		if not response:  #i.e. the response was empty
			break
		#results.append(response)
		results.extend(response)
		
		#print('while loop responce done')
	print('returning from rateLimitWrapper')
	return results

def limits(api):
	return api.get_application_rate_limit_status()

def getTweetStats():
	print('NOT YET IMPLEMENTED...gwt likes, retweets, etc...other tweet metadata')


#input: none. hard coded the files that simple_top100_extract.script generated.
#output: top100_id_dictionary.json
def top100_raw_to_dict():
	#use ordered lists to get correct id's with correct names and usernames
	#final dict will be {id:[name,user_name]}
	#should have 100 entries
	ids = []
	with open('top100_ids_raw.txt','r') as f:
		for line in f:
			ids.append(int(line.split('"')[-2].replace('list-','')))
	if len(ids) != 100:
		print('Error extracting ids.\nids dump: \n%s'%ids)
		sys.exit()

	names = []
	with open('top100_name_raw.txt','r') as f:
		for line in f:
			names.append(line.split('"')[-2])
	if len(names) != 100:
		print('Error extracting ids.\nids dump: \n%s'%ids)
		sys.exit()

	usernames = []
	with open('top100_username_raw.txt','r') as f:
		for line in f:
			line = line.strip()
			if line.startswith('alt='):
				if line.startswith('alt="Friend or Follow"'):
					continue
				elif line.startswith('alt="verified"'):
					continue
				usernames.append(line.split('"')[-2])

	top100 = {}
	for i,uid in enumerate(ids):
		top100[uid] = [usernames[i],names[i]]

	jsonStr = json.dumps(top100)
	with open('top100_id_dictionary.json','w') as fn:
		fn.write(jsonStr)


#read in file filename [json encoded]
#return dict
def json_to_dict(filename):
	with open(filename,'r') as f:
		jstr = f.readlines()
	return json.loads(jstr[0])


###converting raw json twitter timeline data to dataframe
COLUMNS = ['tweet_id','date','user_id','text','text_noMentions','is_quote_status','is_reply_to_status','is_reply_to_user','numMentions',\
    'user_verified','user_description_text','user_followers_count','user_friends_count',\
    'user_listed_count','user_favourites_count','user_statuses_count','retweet_count','favorite_count']
COLUMNS_USER = ['user_id','user_verified','user_description_text','user_followers_count','user_friends_count',\
    'user_listed_count','user_favourites_count','user_statuses_count']

def handleMentions(tweet,textFieldName):
	numMentions = len(tweet['entities']['user_mentions'])
	if numMentions == 0:
		return numMentions,'NO_USER_MENTIONS'
	#else, strip the mentions!
	indexes = [mention['indices'] for mention in tweet['entities']['user_mentions']]
	indexes = np.flipud(indexes)  #remove from the back so indexes dont get messed up
	#textFieldName will be 'text' or 'full_text' depending if tweet collection was extended or not
	strippedText = tweet[textFieldName]
	for idx in indexes:
		strippedText = strippedText.replace(strippedText[idx[0]:idx[1]],'')
	strippedText = strippedText.strip()
	return numMentions,strippedText

def getReplyInfo(tweet):
	statusReply = False
	userReply = False
	if tweet['in_reply_to_status_id']:
		statusReply = True
	if tweet['in_reply_to_user_id']:
		userReply = True
	return statusReply,userReply

"""
Maps user timeline to DataFrame. Includes user metadata features and tweet features.

Args:
    uid: The user_id of the current user
    data: Dict with two keys. 'user_info' and 'user_timeline'

Returns:
    DataFrame with rows = single tweet instance. columns = features [combined user and tweet]
    columns = ['text','text_noMentions','is_quote_status','is_reply','numMentions',\
    'user_verified','user_description_text','user_followers_count','user_friends_count',\
    'user_listed_count','user_favourites_count','user_statuses_count','retweet_count','favorite_count']
    
    column info[type:[range]:info]:
    'text':str:string:the raw text of the tweet, unchanged
    'text_noMentions':str:string:the text of the tweet with @mentions removed [='NO_USER_MENTIONS if 0 mentions']
    'is_quote_status':bool:T/F:denotes if the tweet is a quote status of another tweet
    'is_reply_to_status':bool:T/F:denotes if the tweet is a reply to someone elses tweet
    'is_reply_to_user':bool:T/F:denotes if the tweet is a reply to a user
    'numMentions':int:int:number of mentions found in the tweet
    'user_verified':bool:T/F:denotes if the user is a verified user
    'user_description_text':str:string:raw text of the user's profile description
    'user_followers_count':int:int:number of followers the user has
    'user_friends_count':int:int:number of people the user follows
    'user_listed_count':int:int:number of lists the user is a part of
    'user_favourites_count':int:int:number of tweets the user has liked to date
    'user_statuses_count':int:int:number of tweets this user has authored to date [note that timeline acquisition is limited to 3200 latest tweets]
    'retweet_count':int:int:number of times this tweet has been retweeted [at time of collection]
    'favorite_count':int:int:number of times this tweet has been liked [at time of collection]
"""
def rawTimelineToTrainingInstances(uid,data):
    outData = pd.DataFrame(columns=COLUMNS)
    userData = pd.DataFrame(columns=COLUMNS_USER)
    userData = userData.append({'user_verified':data['user_info']['verified']},ignore_index=True)  #need to do for the first one...
    #userData['user_verified'] = data['user_info']['verified']
    userData['user_id'] = int(uid)
    userData['user_description_text'] = data['user_info']['description']
    userData['user_followers_count'] = data['user_info']['followers_count']
    userData['user_friends_count'] = data['user_info']['friends_count']
    userData['user_listed_count'] = data['user_info']['listed_count']
    userData['user_favourites_count'] = data['user_info']['favourites_count']
    userData['user_statuses_count'] = data['user_info']['statuses_count']
    #print(len(data['user_timeline']))
    #print(userData)
    for tweet in data['user_timeline']:
        if 'ErrorCaught' in tweet:
            print('Handled Tweet ErrorCaught')
            continue
        if 'delete' in tweet:
            print('Handled deleted tweet')
            continue
        tweetData = pd.DataFrame(columns=COLUMNS)  #this is a data instance
        tweetData = tweetData.append(userData,sort=False)  #user data is constant for a single call to this function
        tweetData['tweet_id'] = int(tweet['id'])
        tweetData['date'] = tweet['created_at']
        tweetData['text'] = tweet['text']
        numMentions,strippedText = handleMentions(tweet)
        tweetData['text_noMentions'] = strippedText
        tweetData['is_quote_status'] = tweet['is_quote_status']
        statusReply,userReply = getReplyInfo(tweet)
        tweetData['is_reply_to_status'] = statusReply
        tweetData['is_reply_to_user'] = userReply
        tweetData['numMentions'] = numMentions
        tweetData['retweet_count'] = tweet['retweet_count']
        tweetData['favorite_count'] = tweet['favorite_count']
        outData = outData.append(tweetData,sort=False)
        #print(tweetData)
    outData.set_index('user_id')
    outData = outData.infer_objects()
    return outData

"""
Returns the number of months between two dates.

Args:
	d_old: string [format used in twitter 'created_at' fields]

PRE:
	- assumes d_old is a date BEFORE date_today. This should be the case for our dataset as is.
	- not an exact calculation, but we don't need finer granularity.
"""
def diff_dates_month(d_old):
	date_today = 'Thu Nov 08 2018'
	date_today = parse_date(date_today)
	date_old = parse_date(d_old)
	return (date_today.year - date_old.year)*12 + (date_today.month - date_old.month)

'''
get the value of the key for iten in data [dict]. handles non-existing keys

Args:
	data: a dict
	keyy: the key for which we want an attribute
'''
def getAttribute(data,keyy):
	sources = {'Twitter for iPhone':'iphone', 'Twitter for Android':'android', 'Twitter Web Client':'web',
       'Facebook':'facebook', 'IFTTT':'ifttt', 'twittbot.net':'twittbot', 'Instagram':'instagram', 'Twitter Lite':'twitterlite',
       'Google':'google', 'TweetDeck':'tweetdeck', 'Twitter for iPad':'ipad','Twitter for BlackBerry®':'blackberry'}  #top10 sources, plus 2 others [ipad and blackberry] based on 15mil tweets. top10 represent ~82%of tweets. and any other single source is < 1% of tweets
	ret = None
	try:
		ret = data[keyy]
		if (ret == ''):
			ret = None
		if keyy == 'source': #special parsing for source...
			ret = (ret.split('>')[-2]).split('<')[0]  #parse source out of raw anchor
			if ret in sources.keys():
				ret = sources[ret]  #convert to simple
			else:
				ret = 'other'
		if keyy == 'coordinates':
			if ret is not None:
				ret = ret['coordinates']
	except:
		ret = None
	return ret

'''
very similar to rawTimelineToTrainingInstances. instead, however, build a list of lists, THEN convert to DF [likely faster]
also, just selecting subset of attributes we didn't already get

Args:
    uid: The user_id of the current user
    data: Dict with two keys. 'user_info' and 'user_timeline'
'''
def extractAttributes(uid,data):
	COLUMNS_TWEET = ['tweet_id','tweet_source','tweet_coord','tweet_place']
	COLUMNS_USERinfo = ['user_location','user_created_at','user_geo_enabled']
	infos = []
	#get user info, will be part of every tweet instance
	user_info = []
	user_info.append(getAttribute(data['user_info'],'location'))
	user_info.append(getAttribute(data['user_info'],'created_at'))
	user_info.append(getAttribute(data['user_info'],'geo_enabled'))
	#print(user_info)
	tweet_infos = []  #list of list will turn to dataframe
	for tweet in data['user_timeline']:
		#tweet is a tweet object
		tweet_info = []
		try:
			tweet_info.append(int(getAttribute(tweet,'id')))
		except:
			tweet_info.append(getAttribute(tweet,'id'))
		tweet_info.append(getAttribute(tweet,'source'))
		tweet_info.append(getAttribute(tweet,'coordinates'))
		tweet_info.append(getAttribute(tweet,'place'))
		tweet_infos.append(tweet_info)
	tweetdata = pd.DataFrame(tweet_infos,columns=COLUMNS_TWEET)
	userdata = pd.DataFrame([user_info for _ in range(len(tweet_infos))],columns=COLUMNS_USERinfo)
	finaldata = pd.concat([tweetdata,userdata],axis=1)
	return finaldata

#returns list of image urls found in the tweet. if non, returns None
def getImageUrls(tweet):
	image_urls = []
	image_urls = []
	if 'media' in tweet['entities']:
		if len(tweet['entities']['media']) > 0:
			media = tweet['entities']['media'][0]
			if media['type'] == 'photo':
				url = media['media_url']
				image_urls.append(url)
	if 'extended_entities' in tweet:
		if 'media' in tweet['extended_entities']:
			if len(tweet['extended_entities']['media']) > 0:
				for media in tweet['extended_entities']['media']:
					if media['type'] == 'photo':
						url = media['media_url']
						if url not in image_urls:
							image_urls.append(url)
	if len(image_urls) == 0:
		image_urls = None
	return image_urls

"""
refactored to get ALL tweets attributes as fast as possible
same as extractAttributes() but this gathers ALL the attributes [basically combines extractAttributes and rawTimelineToTrainingInstances]
"""
def extractAllAttributes(uid,data,globalTweets,extended=False):
	COLUMNS_ALL_TWEET = ['tweet_id','tweet_truncated','date','tweet_source','tweet_lang','tweet_coord','tweet_place','text','text_noMentions','is_quote_status',\
	'is_reply_to_status','is_reply_to_user','numMentions','retweet_count','favorite_count']
	COLUMNS_ALL_USER = ['user_id','user_name','user_screen','user_verified','user_lang','user_description_text','user_followers_count','user_friends_count',\
	'user_listed_count','user_favourites_count','user_statuses_count','user_location','user_created_year','user_created_month',\
	'user_geo_enabled','user_img_url','user_banner_url']
	if extended:  #extended tweet has slightly different attributes]
		COLUMNS_ALL_TWEET = ['tweet_id','tweet_truncated','date','tweet_source','tweet_lang','tweet_coord','tweet_place','text','text_noMentions','is_quote_status',\
			'is_reply_to_status','is_reply_to_user','numMentions','image_urls','retweet_count','favorite_count']
		COLUMNS_ALL_USER = ['user_id','user_name','user_screen','user_verified','user_lang','user_description_text','user_followers_count','user_friends_count',\
			'user_listed_count','user_favourites_count','user_statuses_count','user_location','user_created_year','user_created_month',\
			'user_geo_enabled','user_img_url','user_banner_url']
	infos = []
	#get user info, will be part of every tweet instance
	user_info = []
	try:
		uid = int(uid)  #uid is now int
	except:
		print('bad user_id found in extractAllAttributes()')
		return None,globalTweets  #bad user id
	user_info.append(uid)
	user_info.append(getAttribute(data['user_info'],'name'))
	user_info.append(getAttribute(data['user_info'],'screen_name'))
	user_info.append(getAttribute(data['user_info'],'verified'))
	user_info.append(getAttribute(data['user_info'],'lang'))
	user_info.append(getAttribute(data['user_info'],'description'))
	user_info.append(getAttribute(data['user_info'],'followers_count'))
	user_info.append(getAttribute(data['user_info'],'friends_count'))
	user_info.append(getAttribute(data['user_info'],'listed_count'))
	user_info.append(getAttribute(data['user_info'],'favourites_count'))
	user_info.append(getAttribute(data['user_info'],'statuses_count'))
	user_info.append(getAttribute(data['user_info'],'location'))
	#user_info.append(getAttribute(data['user_info'],'created_at'))
	user_year = None
	user_month = None
	try:
		user_created_at = parse_date(getAttribute(data['user_info'],'created_at'))
		user_year = user_created_at.year
		user_month = user_created_at.month
	except:
		user_year = None
		user_month = None
	user_info.append(user_year)
	user_info.append(user_month)
	user_info.append(getAttribute(data['user_info'],'geo_enabled'))
	user_info.append(getAttribute(data['user_info'],'profile_image_url'))
	user_info.append(getAttribute(data['user_info'],'profile_banner_url'))
	#print(user_info)
	tweet_infos = []  #list of list will turn to dataframe
	for tweet in data['user_timeline']:
		if 'ErrorCaught' in tweet:
			print('Handled Tweet ErrorCaught')
			continue
		if 'delete' in tweet:
			print('Handled deleted tweet')
			continue
		#tweet is a tweet object
		tweet_info = []
		tid = getAttribute(tweet,'id')
		TID_0 = False
		try:
			tid = int(tid)
			if tid == 0:
				print('tweet_id was 0. no good. skip.')
				TID_0 = True
		except:
			print('bad tweet_id found in extractAllAttributes(). Skipping tweet')
			continue
		if TID_0:
			continue
		if tid in globalTweets:
			print('tweet_id %s already in set. Skipping.'%tid)
			continue
		tweet_info.append(tid)
		tweet_info.append(getAttribute(tweet,'truncated'))
		tweet_info.append(getAttribute(tweet,'created_at'))
		tweet_info.append(getAttribute(tweet,'source'))
		tweet_info.append(getAttribute(tweet,'lang'))
		tweet_info.append(getAttribute(tweet,'coordinates'))
		tweet_info.append(getAttribute(tweet,'place'))
		textFieldName = 'text'
		if extended:
			textFieldName = 'full_text'
		tweet_info.append(getAttribute(tweet,textFieldName))
		numMentions,strippedText = handleMentions(tweet,textFieldName)
		tweet_info.append(strippedText)
		tweet_info.append(getAttribute(tweet,'is_quote_status'))
		statusReply,userReply = getReplyInfo(tweet)
		tweet_info.append(statusReply)
		tweet_info.append(userReply)
		tweet_info.append(numMentions)
		if extended:
			image_urls = getImageUrls(tweet)
			tweet_info.append(image_urls)	
		tweet_info.append(getAttribute(tweet,'retweet_count'))
		tweet_info.append(getAttribute(tweet,'favorite_count'))
		tweet_infos.append(tweet_info)
		globalTweets[tid] = None  #add successful tid to globalTweets
	tweetdata = pd.DataFrame(tweet_infos,columns=COLUMNS_ALL_TWEET)
	userdata = pd.DataFrame([user_info for _ in range(len(tweet_infos))],columns=COLUMNS_ALL_USER)
	finaldata = pd.concat([tweetdata,userdata],axis=1)
	finaldata = finaldata.infer_objects()
	if finaldata.shape[0] == 0:
		return None,globalTweets
	return finaldata,globalTweets

def captionCleaner(text):
	emojimap = {':beaming_face_with_smiling_eyes:':' happy',':neutral_face:':' neutral',':flushed_face:':' unclear',':loudly_crying_face:':' sad',':hushed_face:':'amazed'}
	preList = ["I think it's","I can't really describe the picture but I do see","I am not really confident, but I think it's","I really can't describe the picture"]
	#replace emoji with textual emoji, textual emoji replaced with word
	try:
		text = emoji.demojize(text)
	except:
		pass
	for key,value in emojimap.items():
	  if key in text:
	      text = text.replace(key,value)
	for pre in preList:
	  if text.startswith(pre):
	      text = text.replace(pre,'').replace('he/she','they')
	return text


#input is request session [helps keepalive for many requests] and image url list ['url1','url2']!
#returns str of caption, or None if bad response
def imageCaption(session,image_urls):
	captions = []
	for image_url in image_urls:
		data = {"Content": image_url,"Type": "CaptionRequest"}
		headers = {"Content-Type": "application/json; charset=utf-8"}
		MESSAGES_URL = 'https://captionbot.azurewebsites.net/api/messages'
		resp = session.post(MESSAGES_URL, data=json.dumps(data), headers=headers)
		if not resp.ok:
			res = None  # bad response
		else:
			res = resp.text[1:-1].replace('\\"', '"').replace('\\n', '\n').strip()
			#res = captionCleaner(res)  # better to do this later, return raw responses
			captions.append(res)
	if captions:  # not empty
		res = '. '.join(captions)  #builds sentance for each caption found
	else:
		res = None
	return res

def imageColorStats(image_urls):
	if not image_urls:
		return pd.Series([None,None,None])
	try:
		if np.isnan(image_urls):
			return pd.Series([None,None,None])
	except:
		pass
	imgAves = np.zeros((3,),dtype=np.float64)
	for image_url in image_urls:
		try:
			image = io.imread(image_url)
			avg = image.mean(axis=(0,1))[0:3]
			#print(image.shape)
			imgAves += avg
		except:
			return pd.Series([None,None,None])  # HTTP error
	try:
		imgAves = pd.Series(imgAves/len(image_urls))
	except:
		return pd.Series([None,None,None])  # some other error
	return imgAves  # average red pixels in all images, average green, average blue


# input str. returns str with links removed
def strip_links(text):
    link_regex    = re.compile('((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)', re.DOTALL)
    links         = re.findall(link_regex, text)
    for link in links:
        text = text.replace(link[0], ', ')    
    return text

#global
cList = {
  "ain't": "am not",
  "aren't": "are not",
  "can't": "cannot",
  "can't've": "cannot have",
  "'cause": "because",
  "could've": "could have",
  "couldn't": "could not",
  "couldn't've": "could not have",
  "didn't": "did not",
  "doesn't": "does not",
  "don't": "do not",
  "hadn't": "had not",
  "hadn't've": "had not have",
  "hasn't": "has not",
  "haven't": "have not",
  "he'd": "he would",
  "he'd've": "he would have",
  "he'll": "he will",
  "he'll've": "he will have",
  "he's": "he is",
  "how'd": "how did",
  "how'd'y": "how do you",
  "how'll": "how will",
  "how's": "how is",
  "I'd": "I would",
  "I'd've": "I would have",
  "I'll": "I will",
  "I'll've": "I will have",
  "i'm": "i am",
  "I've": "I have",
  "isn't": "is not",
  "it'd": "it had",
  "it'd've": "it would have",
  "it'll": "it will",
  "it'll've": "it will have",
  "it's": "it is",
  "let's": "let us",
  "ma'am": "madam",
  "mayn't": "may not",
  "might've": "might have",
  "mightn't": "might not",
  "mightn't've": "might not have",
  "must've": "must have",
  "mustn't": "must not",
  "mustn't've": "must not have",
  "needn't": "need not",
  "needn't've": "need not have",
  "o'clock": "of the clock",
  "oughtn't": "ought not",
  "oughtn't've": "ought not have",
  "shan't": "shall not",
  "sha'n't": "shall not",
  "shan't've": "shall not have",
  "she'd": "she would",
  "she'd've": "she would have",
  "she'll": "she will",
  "she'll've": "she will have",
  "she's": "she is",
  "should've": "should have",
  "shouldn't": "should not",
  "shouldn't've": "should not have",
  "so've": "so have",
  "so's": "so is",
  "that'd": "that would",
  "that'd've": "that would have",
  "that's": "that is",
  "there'd": "there had",
  "there'd've": "there would have",
  "there's": "there is",
  "they'd": "they would",
  "they'd've": "they would have",
  "they'll": "they will",
  "they'll've": "they will have",
  "they're": "they are",
  "they've": "they have",
  "to've": "to have",
  "wasn't": "was not",
  "we'd": "we had",
  "we'd've": "we would have",
  "we'll": "we will",
  "we'll've": "we will have",
  "we're": "we are",
  "we've": "we have",
  "weren't": "were not",
  "what'll": "what will",
  "what'll've": "what will have",
  "what're": "what are",
  "what's": "what is",
  "what've": "what have",
  "when's": "when is",
  "when've": "when have",
  "where'd": "where did",
  "where's": "where is",
  "where've": "where have",
  "who'll": "who will",
  "who'll've": "who will have",
  "who's": "who is",
  "who've": "who have",
  "why's": "why is",
  "why've": "why have",
  "will've": "will have",
  "won't": "will not",
  "won't've": "will not have",
  "would've": "would have",
  "wouldn't": "would not",
  "wouldn't've": "would not have",
  "y'all": "you all",
  "y'alls": "you alls",
  "y'all'd": "you all would",
  "y'all'd've": "you all would have",
  "y'all're": "you all are",
  "y'all've": "you all have",
  "you'd": "you had",
  "you'd've": "you would have",
  "you'll": "you will",
  "you'll've": "you will have",
  "you're": "you are",
  "you've": "you have"
}

c_re = re.compile('(%s)' % '|'.join(cList.keys()))

#input str. return str with contractions expanded
def expandContractions(text, c_re=c_re):
    def replace(match):
        return cList[match.group(0)]
    text = c_re.sub(replace, text)
    return text

#input str. return str with @mentions removed
def strip_mentions(text):
    entity_prefixes = ['@']
    words = []
    for word in text.split():
        word = word.strip()
        if word:
            if word[0] not in entity_prefixes:
                words.append(word)
    return ' '.join(words)

#input str. return str with hashtags removed
def strip_hashtags(text):
    entity_prefixes = ['#']
    words = []
    for word in text.split():
        word = word.strip()
        if word:
            if word[0] not in entity_prefixes:
                words.append(word)
    return ' '.join(words)

#input str. return str with special chars removed
def remove_special_characters(text, remove_digits=False):
    pattern = r'[^a-zA-z0-9\s]' if not remove_digits else r'[^a-zA-z\s]'
    text = re.sub(pattern, '', text)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8', 'ignore')
    return text

#not sure
def seperate_emoji(text):
    entity_prefixes = ['@']
    for separator in  string.punctuation:
        if separator not in entity_prefixes :
            text = text.replace(separator,' ')
    words = []
    for word in text.split():
        word = word.strip()
        if word:
            if word[0] not in entity_prefixes:
                words.append(word)
    return ' '.join(words)


#input str. return pd.Series([polarity,subjectivity])
def textBlobFeatures(text):
	snt = TextBlob(text)
	p = snt.sentiment.polarity
	s = snt.sentiment.subjectivity
	return pd.Series([p,s])

#input str. return pd.Series([comp,pos,neu,neg])
def vaderFeatures(text):
	analyser = SentimentIntensityAnalyzer()
	snt = analyser.polarity_scores(text)
	res = [snt['compound'],snt['pos'],snt['neu'],snt['neg']]
	return pd.Series(res)


#input str and captiopn or tweet type text. return str with all preprocessing done
def textProcessPipeline(text,textType='caption'):
	text = text.lower()
	text = strip_links(text)
	text = expandContractions(text)
	if 'tweet' in textType:
		text = strip_mentions(text)
		text = strip_hashtags(text)
	return text

#input str. return tokenized list.
def tokenizeTextblob(text):
	return TextBlob(text).words.lemmatize()

#global
stop_words = list(get_stop_words('en'))         #About 900 stopwords
nltk_words = list(stopwords.words('english')) #About 150 stopwords
stop_words.extend(nltk_words)

def remove_stop_words(word_list):
    output = [w for w in word_list if not w in stop_words]
    return output


#emoji presence for a few emojis
def eggplant_presence(text):
	if ':eggplant:' in text:
		return 1
	return 0

def mfinger_presence(text):
	if ':middle_finger:' in text:
		return 1
	return 0

def cursing_presence(text):
	if ':cursing:' in text:
		return 1
	return 0

def fuck_presence(text):
	if ':point_right::ok_hand:' in text:
		return 1
	return 0


#more text processing
def textProcessPipelineMore(text,textType='caption'):
	text = remove_special_characters(text)
	if 'tweet' in textType:
		text = seperate_emoji(text)
	return text

