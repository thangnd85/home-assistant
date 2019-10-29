""" @exlab247@gmail.com
radio_vn component
version 1.0 07/02/2019
update 16/08/2019 for Home Assistant version 0.95.x and above.

# [your_config]/custom_components/radio_vn
.homeassistant/
|-- custom_components/
|   |-- radio_vn/
|       |-- __init__.py
|       |-- manifest.json
|       |-- services.yaml

# Config in configuration.yaml file for Home Assistant
radio_vn:

# Code in script
radiovn_play:
  sequence:
    - service: radio_vn.play
      data:
        entity_id: media_player.room_player
        channel: 'VOV2' # optional, default: 'VOV3' #list channel: VOV1, VOV2, VOV3, VOVGT-HN, VOVGT-HCM
"""

# Declare variables
DOMAIN = 'radio_vn'
SERVICE_RADIO_PLAY = 'play'
SERVICE_RADIO_STOP = 'stop'
# data service
CONF_PLAYER_ID = 'entity_id'
CONF_CHANNEL= 'channel'

# const data
url = {'VOV1':'https://vov.vn/RadioPlayer.vov?c=vov1', 'VOV2':'https://vov.vn/RadioPlayer.vov?c=vov2', 'VOV3':'https://vov.vn/RadioPlayer.vov?c=vov3', 'VOVGT-HN':'https://vov.vn/RadioPlayer.vov?c=vovgt', 'VOVGT-HCM':'https://vov.vn/RadioPlayer.vov?c=vovgtsg'}
prefix_url = 'https://5a6872aace0ce.streamlock.net/'
match_text = 'MakeRadio'

import requests, time
def get_link_radio(hass, _channel):
    _channel = _channel.upper()
    # Get saved cache if exist
    info = hass.states.get('radio_vn.info')
    if (info is not None and str(info.state) == _channel): 
#    if (info is not None and 'VOV' in str(info.state)): 
        return info.attributes
    res = requests.get(url.get(_channel)).text
    i = res.find(match_text)
    ii = res.find(';', i)
    ext_url = (res[i:ii].split(',')[1].replace("'","").strip())
    radio_link = prefix_url + ext_url
    #save cache to attribute
    hass.states.set('radio_vn.info', _channel, radio_link)	
    return radio_link
def turn_off_playing_media_player(hass):
    last_launch_time = hass.states.get('radio_vn.last_launch_time')
    if (last_launch_time is None or int(last_launch_time.state) == 0): 
        return
    playing_media_id = hass.states.get('radio_vn.playing_media_player').state
    hass.services.call('media_player', 'turn_off', {'entity_id': playing_media_id})
    return

def setup(hass, config):

    def play_radio(data_call):
        # Get data service
        media_id = data_call.data.get(CONF_PLAYER_ID)
        channel  = str(data_call.data.get(CONF_CHANNEL, 'VOV3'))
        # get link of radio
        uri = get_link_radio(hass, channel)
        # service data for 'CALL SERVICE' in Home Assistant
        service_data = {'entity_id': media_id, 'media_content_id': uri, 'media_content_type': 'music'}
        # Call service from Home Assistant
        # Stop running player
        turn_off_playing_media_player(hass)
        # start play process
        launch_time = int(round(time.time() * 1000))
        hass.states.set('radio_vn.last_launch_time', launch_time)
        hass.states.set('radio_vn.playing_media_player', media_id)
#        hass.services.call('media_player', 'turn_off', {'entity_id': media_id})
        time.sleep(0.2)
        hass.services.call('media_player', 'play_media', service_data)
    def stop_radio(data_call):
        turn_off_playing_media_player(hass)
        # stop play while loop
        hass.states.set('radio_vn.last_launch_time', 0)
    hass.services.register(DOMAIN, SERVICE_RADIO_PLAY, play_radio)
    hass.services.register(DOMAIN, SERVICE_RADIO_STOP, stop_radio)
    return True
