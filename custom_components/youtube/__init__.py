# Declare variables
DOMAIN = 'youtube'
SERVICE_YOUTUBE_PLAY = 'play'
SERVICE_YOUTUBE_STOP = 'stop'

# data service
CONF_PLAYER_ID = 'entity_id'
CONF_MUSIC_KEYWORD = 'key_word'

# const data

default_type = 'nhac tre'

import requests, time, random, urllib, re
def get_codes(key_word):
    # Get saved cache if exist
#    info = hass.states.get('youtube_vn.info')
#    if (info is not None and str(info.state) == key_word): 
#    if (info is not None and 'VOV' in str(info.state)): 
#        return info.attributes
	key_word = key_word.lower()
	query_string = urllib.parse.urlencode({"search_query" : key_word})
	html_content = urllib.request.urlopen("http://www.youtube.com/results?" + query_string)
	search_results = re.findall(r'href=\"\/watch\?v=(.{11})', html_content.read().decode())
	random_song=random.randint(0,10)
	media = search_results[random_song]
#	hass.states.set('youtube.info', media, key_word)	
	return media

def turn_off_playing_media_player(hass):
    last_launch_time = hass.states.get('youtube.last_launch_time')
    if (last_launch_time is None or int(last_launch_time.state) == 0): 
        return
    playing_media_id = hass.states.get('youtube.playing_media_player').state
    hass.services.call('media_player', 'turn_off', {'entity_id': playing_media_id})
    return

def setup(hass, config):
    # play handler
    def play_youtube(data_call):
        # Get data service
        media_id = data_call.data.get(CONF_PLAYER_ID)
        key_word  = str(data_call.data.get(CONF_MUSIC_KEYWORD, 'mỹ tâm'))
        # Stop running player
#        turn_off_playing_media_player(hass)
        # start play process
#        launch_time = int(round(time.time() * 1000))
#        hass.states.set('youtube.last_launch_time', launch_time)
#        hass.states.set('youtube.playing_media_player', media_id)
        # get link of audio	
        url = get_codes(key_word)
        uri = "http://www.youtube.com/watch?v=" + url
        time.sleep(0.2)
        service_data = {'entity_id': media_id, 'media_content_id': uri, 'media_content_type': 'music'}
                    # Call service from Home Assistant
        hass.services.call('media_extractor', 'play_media', service_data)
                    # sleep while media_player is playing
    def stop_youtube(data_call):
#        turn_off_playing_media_player(hass)
        hass.services.call('media_extractor', 'stop_media')
        # stop play while loop
#        hass.states.set('youtube.last_launch_time', 0)
    hass.services.register(DOMAIN, SERVICE_YOUTUBE_PLAY, play_youtube)
    hass.services.register(DOMAIN, SERVICE_YOUTUBE_STOP, stop_youtube)
    return True

