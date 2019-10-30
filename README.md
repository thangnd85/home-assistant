# home-assistant
Home-assistant custom addons and packages

Add this line to configuration.yaml, at the home-assistant, see below:

homeassistant:
  # Name of the location where Home Assistant is running
  name: Home
  # Location required to calculate the time the sun rises and sets
  latitude: (removed)
  longitude: (removed)
  # Impacts weather/sunrise data (altitude above sea level in meters)
  elevation: 3
  # metric for Metric, imperial for Imperial
  unit_system: metric
  # Pick yours from here: http://en.wikipedia.org/wiki/List_of_tz_database_time_zones
  time_zone: Asia/Ho_Chi_Minh
  # Customization file
  customize: !include customize.yaml
  whitelist_external_dirs:
#    - /tmp
    - /share
#    - /www
  packages: !include_dir_named packages

Put folder "custom_components" and "packages" to homeassistant config folder.
homeassistant
-custom_components
--youtube
--lich_am
--zing_mp3
--
-packages

Before use Zing MP3 and Youtube component, open youtube.yaml and zingmp3.yaml inside packages folder, replace media_player entity to your right entity. 
Example: media_player.speaker to media_player.chromecast etc. 

1. To use Zing Mp3, add this to lovelace code editor
entities:
  - entity: input_boolean.zing_mp3
  - entity: input_boolean.zing_repeat
  - entity: input_boolean.zing_shuffle
  - entity: input_select.zing_mp3
  - entity: input_number.volume_music
  - entity: automation.phat_nhac_da_chon
  - entity: automation.tat_zing
show_header_toggle: false
title: Zing MP3
type: entities

2. To use Youtube, add this
entities:
  - entity: input_boolean.play_music
  - entity: input_text.nhac1
  - entity: script.play_music_keyword
  - entity: input_select.music
show_header_toggle: false
title: 'Youtube '
type: entities


3. To use Lunar calendar as a sensor.
Open your sensor section, add this:
- platform: lich_am

If you want to show text instead of show date in Lunar, open /custom component/lic_am/sensor.py
Go to line number 109, change 
        return lunar_text #Hiện chữ
#        return lunar_text #Hiện ngày
To 
        return lunar_text2 #Hiện chữ
#        return lunar_text #Hiện ngày

