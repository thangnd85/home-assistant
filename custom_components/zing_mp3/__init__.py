'''
=== Play TOP100 of Zing MP3 by exlab Modified by HungNH===
=== version 1.1.1 05/04/2019 ===
=== Change log: Fix bug, add stop service
--------
# Config in configuration.yaml file for Home Assistant
zing_mp3:

# Code in script
play_zing_mp3:
  sequence:
    - service: zing_mp3.play
      data:
        entity_id: media_player.room_player 
		# Need to change your working  mediaplayer here		
        music_type: 'Nhac tre'
        # optional, default: 'Nhac tre' #list music_type: Pop, Country, Rock, Dance, R&B, Rap, Soundtrack, Nhac tre, Tru tinh, Que huong, Cach mang, Rock Viet, Rap Viet, Dance Viet
        repeat: 'on'
        # optional, default: 'off'
        shuffle: 'on'
        # optional, default: 'off'
stop_zing_mp3:
  sequence:
    - service: zing_mp3.stop
--------        
'''

# Declare variables
DOMAIN = 'zing_mp3'
SERVICE_ZING_PLAY = 'play'
SERVICE_ZING_STOP = 'stop'

# data service
CONF_PLAYER_ID = 'entity_id'
CONF_MUSIC_TYPE= 'music_type'
CONF_REPEAT = 'repeat'
CONF_SHUFFLE = 'shuffle'

# const data
TOP100 = {'pop':'ZWZB96AB', 'country': 'ZWZB96AE', 'rock': 'ZWZB96AC', 'dance': 'ZWZB96C7', 'r&b': 'ZWZB96C8', 'rap': 'ZWZB96AD', 'soundtrack': 'ZWZB96C9',
          'nhac tre':'ZWZB969E', 'tru tinh': 'ZWZB969F', 'que huong': 'ZWZB96AU', 'cach mang': 'ZWZB96AO', 'rock viet': 'ZWZB96A0', 'rap viet': 'ZWZB96AI', 'dance viet': 'ZWZB96AW', 'thieu nhi': 'ZWZB96A6', 'khong loi':'ZWZB96A7', 'guitar':'ZWZB96EZ'}
url_list = 'https://mp3.zing.vn/xhr/media/get-list?op=top100&start=0&length=20&id='
url_audio = 'https://mp3.zing.vn/xhr/media/get-source?type=audio&key='
prefix_url = 'https:'
default_type = 'nhac tre'

import requests, time, random
def get_codes(type_TOP):
    type_TOP = type_TOP.lower()
    uri = url_list + TOP100.get(type_TOP)
    re = requests.get(uri).json()
    items = re['data']['items']
    audio_codes = []
    for item in items:
        code = item['code']
        audio_codes.append(code)
    return audio_codes

def get_audio_links(hass, type_TOP):

    # Get saved cache if exist
    info = hass.states.get('zing_mp3.info')
    if (info is not None and str(info.state) == type_TOP): 
        return info.attributes
    # Get data from Zing
    codes = get_codes(type_TOP)
    audio_links = {}
    for code in codes:
        uri = url_audio + code
        json = requests.get(uri).json()
        if 'data' not in json :
            continue
        re = json['data']
        if '128' not in re['source'] :
            continue
        link = prefix_url + re['source']['128']
        duration =  int(re['duration'])
        audio_links[link] = duration
    #save cache to attribute
    hass.states.set('zing_mp3.info', type_TOP, audio_links)
    return audio_links

def turn_off_playing_media_player(hass):
    last_launch_time = hass.states.get('zing_mp3.last_launch_time')
    if (last_launch_time is None or int(last_launch_time.state) == 0): 
        return
    playing_media_id = hass.states.get('zing_mp3.playing_media_player').state
    hass.services.call('media_player', 'turn_off', {'entity_id': playing_media_id})
    return

def setup(hass, config):
    # play handler
    def play_zing(data_call):
        # Get data service
        media_id = data_call.data.get(CONF_PLAYER_ID)
        music_type  = data_call.data.get(CONF_MUSIC_TYPE, default_type)
        repeat = data_call.data.get(CONF_REPEAT, 'off')
        shuffle = data_call.data.get(CONF_SHUFFLE, 'off')
        # Stop running player
        turn_off_playing_media_player(hass)
        # start play process
        launch_time = int(round(time.time() * 1000))
        hass.states.set('zing_mp3.last_launch_time', launch_time)
        hass.states.set('zing_mp3.playing_media_player', media_id)
        # get link of audio		
        mp3_links = get_audio_links(hass, music_type)
        time.sleep(0.2)
        flag = True
        while (flag == True):
            if (shuffle == 'off'):
                for uri in mp3_links:
                    if (int(hass.states.get('zing_mp3.last_launch_time').state) != launch_time): 
                        return
                    # service data for 'CALL SERVICE' in Home Assistant
                    service_data = {'entity_id': media_id, 'media_content_id': uri, 'media_content_type': 'music'}
                    # Call service from Home Assistant
                    hass.services.call('media_player', 'play_media', service_data)
                    # sleep while media_player is playing
                    time_sleep = mp3_links.get(uri)
                    time.sleep(time_sleep)
            else:
                for idez in range(0, len(mp3_links)):
                    if (int(hass.states.get('zing_mp3.last_launch_time').state) != launch_time): 
                        return
                    uri, time_sleep = random.choice(list(mp3_links.items()))
                    #hass.services.call('system_log', 'write', {'message': "zing_mp3_shuffle:" + uri})
                    # service data for 'CALL SERVICE' in Home Assistant
                    service_data = {'entity_id': media_id, 'media_content_id': uri, 'media_content_type': 'music'}
                    # Call service from Home Assistant
                    hass.services.call('media_player', 'play_media', service_data)
                    # sleep while media_player is playing
                    time.sleep(time_sleep)
            if (repeat == 'off'): 
                flag = False
    def stop_zing(data_call):
        turn_off_playing_media_player(hass)
        # stop play while loop
        hass.states.set('zing_mp3.last_launch_time', 0)
    hass.services.register(DOMAIN, SERVICE_ZING_PLAY, play_zing)
    hass.services.register(DOMAIN, SERVICE_ZING_STOP, stop_zing)
    return True
