
VI
Phần này đã quá cũ. Đợt này em chỉ làm cái component vinfast thôi 
<img width="598" height="808" alt="Image" src="https://github.com/user-attachments/assets/53954013-7439-473e-abe2-155474922ab6" />

<img width="545" height="937" alt="Image" src="https://github.com/user-attachments/assets/69b0f2e5-81d3-4a7e-8ef7-2f1a9b7b2688" />

<img width="572" height="997" alt="Image" src="https://github.com/user-attachments/assets/67153991-5ac8-42a9-9bdf-c2a7099051ac" />

<img width="587" height="1095" alt="Image" src="https://github.com/user-attachments/assets/2098ba0c-bc09-4508-b2ee-aeb413d5ae70" />

<img width="568" height="911" alt="Image" src="https://github.com/user-attachments/assets/e675088f-8285-4bf6-bd2f-fc9e509344f4" />

<img width="578" height="1049" alt="Image" src="https://github.com/user-attachments/assets/06e7758f-37bc-4874-8ae6-433a091be5ec" />

<img width="1002" height="1024" alt="Image" src="https://github.com/user-attachments/assets/b1dffe04-ced9-47f9-beb1-2a68c3f6f8ed" />


# home-assistant
Home-assistant custom addons and packages

Add this line to configuration.yaml, at the home-assistant, see below:

      homeassistant:
        name: Home
        latitude: (removed)
        longitude: (removed)
        elevation: 3
        unit_system: metric
        time_zone: Asia/Ho_Chi_Minh
        customize: !include customize.yaml
        whitelist_external_dirs:
          - /share
        packages: !include_dir_named packages

Put folder "custom_components" and "packages" to homeassistant config folder.

homeassistant
 
     -custom_components
  
           --youtube
           --lich_am
           --zing_mp3
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
Open your sensor section, add this:\

        - platform: lich_am

If you want to show text instead of show date in Lunar, open /custom component/lic_am/sensor.py
Go to line number 109, change 

        return lunar_text #Hiện chữ

To 

        return lunar_text2 #Hiện chữ

4. Automation for lunar calendar:

         - id: '1583945801552'
           alias: Nhắc mai rằm
           description: ''
           trigger:
           - at: 06:02:00
             platform: time
           condition:
           - condition: template
             value_template: '{{ states("sensor.am_lich_ngay_mai")|int == 15}}'
           action:
           - data:
               entity_id: media_player.mini
               message: Ngày mai rằm nhé.
             service: tts.google_translate_say
         - id: '1583945929918'
           alias: Nhắc hôm nay mùng 1
           description: ''
           trigger:
           - at: 06:02:00
             platform: time
           condition:
           - condition: template
             value_template: '{{ states("sensor.ngay_am")|int == 1}}'
           action:
           - data:
               entity_id: media_player.mini
               message: Hôm nay là mùng một.
             service: tts.google_translate_say
			 
5. Donate if you like my work using 
         
		 Momo, Airpay, ViettelPay (0985435 XXX) 
         Paypal: nducthang85@gmail.com

Donate Momo / Airpay / ViettelPay
![alt text](https://dummyimage.com/160x40/000/fff&text=0985435685)
