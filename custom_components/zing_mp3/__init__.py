'''=== Play Top 100 or song name from Zing MP3 ===
   === Copy right 2019 by ttvtien
'''
import json, requests, time, random, datetime, hmac, hashlib, urllib, gzip, logging, os.path
import numpy as np
import json
import os
from os import listdir
from os import path
import sys
import random
import time
import requests
import json
import urllib
import re
import random
import datetime
from urllib.request import urlretrieve

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'zing_mp3'

COMPONENT_ABS_DIR = os.path.dirname(
    os.path.abspath(__file__))


SERVICE_ZING_PLAY = 'play'
SERVICE_ZING_STOP = 'stop'                   

#service data
CONF_PLAYER_ID = 'entity_id'
CONF_NAME = 'name'
CONF_CATEGORY= 'category'
CONF_REPEAT = 'repeat'
CONF_SHUFFLE = 'shuffle'

# const data
TOP100 = {'pop':'ZWZB96AB', 'country': 'ZWZB96AE', 'rock': 'ZWZB96AC', 'dance': 'ZWZB96C7', 'r&b': 'ZWZB96C8', 'rap': 'ZWZB96AD', 'soundtrack': 'ZWZB96C9',
          'nhac tre':'ZWZB969E', 'tru tinh': 'ZWZB969F', 'que huong': 'ZWZB96AU', 'cach mang': 'ZWZB96AO', 'rock viet': 'ZWZB96A0', 'rap viet': 'ZWZB96AI', 'dance viet': 'ZWZB96AW', 'thieu nhi': 'ZWZB96A6', 'khong loi':'ZWZB96A7', 'guitar':'ZWZB96EZ'}
url_list = 'https://mp3.zing.vn/xhr/media/get-list?op=top100&start=0&length=20&id='
url_audio = 'https://mp3.zing.vn/xhr/media/get-source?type=audio&key='
url_search  = "https://zingmp3.vn/api/search?"

prefix_url = 'https:'

API_KEY     = '38e8643fb0dc04e8d65b99994d3dafff'
SECRET_KEY  = b'10a01dcf33762d3a204cb96429918ff6'


#This function will get top 100 list
def get_codes_list(type_TOP):
    type_TOP = type_TOP.lower()
    uri = url_list + TOP100.get(type_TOP)
    re = requests.get(uri).json()
    items = re['data']['items']
    audio_codes = []
    for item in items:
        code = item['code']
        audio_codes.append(code)
    return audio_codes

def get_song_info(song_code):
    song_info = {}
    #codes = get_codes(type_TOP)
    #for code in codes:
    uri = url_audio + song_code
    re = requests.get(uri).json()['data']
    duration = int(re['duration'])
    source = re['source']
    link = prefix_url + source['128']
    song_info['duration'] = duration
    song_info['link'] = link
    return song_info
def turn_off_playing_media_player(hass):
    last_launch_time = hass.states.get('zing_mp3.last_launch_time')
    if (last_launch_time is None or int(last_launch_time.state) == 0): 
        return
    playing_media_id = hass.states.get('zing_mp3.playing_media_player').state
    hass.services.call('media_player', 'turn_off', {'entity_id': playing_media_id})
    return

def setup(hass, config):
# Play top 100
    def play_top100(data_call):
        # Get data service
        media_id = data_call.data.get(CONF_PLAYER_ID)
        music_type  = data_call.data.get(CONF_CATEGORY, 'tru tinh')
        repeat = data_call.data.get(CONF_REPEAT, False)
        shuffle = data_call.data.get(CONF_SHUFFLE, False)
        # get playlist as code_list
        codes_list = get_codes_list(music_type)
        if (shuffle):
            codes_list = random.choices(codes_list, k=len(codes_list))
        # force stop media player
        # hass.services.call('media_player', 'media_stop', {'entity_id': media_id})
        ''' play '''
        continue_play = True
        i = 0
        while (continue_play):
            song_code = codes_list[i]
            song_info = get_song_info(song_code)
            # Call service from Home Assistant
            service_data = {'entity_id': media_id, 'media_content_id': song_info['link'], 'media_content_type': 'music'}
            hass.services.call('media_player', 'play_media', service_data)
            # sleep while media_player is playing
            time.sleep(song_info['duration'] - 2)
            if (hass.states.get(media_id).state == 'playing'):
                if (i < len(codes_list) - 1):
                    i = i + 1
                elif (repeat):
                    i = 0
                else:
                    continue_play = False
            else:
                continue_play = False
# ----------------------------------------------------------------------------------------------------------------------
# Play by song name
    def get_hash256(string):
        return hashlib.sha256(string.encode('utf-8')).hexdigest()

    def get_hmac512(string):
        return hmac.new(SECRET_KEY, string.encode('utf-8'), hashlib.sha512).hexdigest()

    def get_request_path(data):

        def mapping(key, value):
            return urllib.parse.quote(key) + "=" + urllib.parse.quote(value)

        data = [mapping(k, v) for k, v in data.items()]
        data = "&".join(data)

        return data

    def get_json_data(link):
        f = urllib.request.urlopen(link)
        gzipFile = gzip.GzipFile(fileobj=f)
        return json.loads(gzipFile.read().decode('utf-8'))

    def get_song_by_id(id):
        url = f"https://zingmp3.vn/api/song/get-song-info?id={id}&"
        time = str(int(datetime.datetime.now().timestamp()))
        sha256 = get_hash256(f"ctime={time}id={id}")

        data = {
            'ctime': time,
            'api_key': API_KEY,
            'sig': get_hmac512(f"/song/get-song-info{sha256}")
        }

        return url + get_request_path(data)

    def search_song(name):
        resp = requests.get('http://ac.mp3.zing.vn/complete?type=artist,song,key,code&num=500&query='+urllib.parse.quote(name))
        resultJson = json.dumps(resp.json())
        obj = json.loads(resultJson)
        songs = obj['data'][0]['song']
        x=len(songs)
        song_id=[]
        for i in range (0,x):
            if str(songs[i]['name']).upper()==str(name).upper():
                song_id.append(songs[i]['id'])
            else:
                pass
        songID =  np.random.choice(song_id)
        songUrl= "https://mp3.zing.vn/bai-hat/"+songID+".html"
        # print(songUrl)
        resp = requests.get(songUrl)
        # print(resp.text)
        key = re.findall('data-xml="\/media\/get-source\?type=audio&key=([a-zA-Z0-9]{20,35})', resp.text)
        # key = re.findall('data-xml="\/media\/get-source\?type=video&key=([a-zA-Z0-9]{20,35})', resp.text)
        songApiUrl = "https://mp3.zing.vn/xhr/media/get-source?type=audio&key="+key[0]
        resp = requests.get(songApiUrl)
        resultJson = json.dumps(resp.json())
        obj = json.loads(resultJson)
        # print(str(obj))
        mp3Source = "https:"+obj["data"]["source"]["128"]
        realURLdata = requests.get(mp3Source,allow_redirects=False)
        # print(realURLdata)
        realURL = realURLdata.headers['Location']
        file_name, headers = urlretrieve(realURL)
        print(realURL)
        result=file_name            
    except (IndexError, ValueError):
        pass        
    return realURL
    
    
    
    async def play_song(data_call):
        media_id = data_call.data.get(CONF_PLAYER_ID,'media_player.apple_room_speaker')
        mediaUrl = search_song(data_call.data.get(CONF_NAME, '0').lower())
        #_LOGGER.warn("mediaUrl: ", mediaUrl)
        service_data = {'entity_id': media_id, 'media_content_id': mediaUrl, 'media_content_type': 'music'}
        hass.services.call('media_player', 'play_media', service_data)

    async def _check_update(service):
        await _update(hass)

    async def _update_component(service):
        await _update(hass, True)
        flag = False
    def stop_zing(data_call):
        turn_off_playing_media_player(hass)
        # stop play while loop
        hass.states.set('zing_mp3.last_launch_time', 0)
#    hass.services.register(DOMAIN, SERVICE_ZING_PLAY, play_zing)
    hass.services.register(DOMAIN, SERVICE_ZING_STOP, stop_zing)
    hass.services.register(DOMAIN, 'play_top100', play_top100)
    hass.services.async_register(DOMAIN, 'play', play_song)

    return True
