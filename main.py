#!/usr/bin/env python3

import socket
import json
import subprocess
import time

import requests
from digi.xbee.devices import DigiMeshDevice


playlist_dict = {"name": "play",
    "repeat": 0,
    "loopCount": 0,
    "mainPlaylist": [
        {
            "type": "sequence",
            "enabled": 1,
            "playOnce": 0,
            "sequenceName": "2.25.19notes2f-G1f--.fseq"
        },
    ],
    "playlistInfo": {
        "total_duration": 90,
        "total_items": 3
    }
}



class FppSettings:
    def __init__(self, xbee_com='/dev/ttyUSB0', xbee_baud=9600):
        self.local_xbee = DigiMeshDevice(xbee_com, xbee_baud)
        self.local_xbee.open()
        self.xbee_network = self.local_xbee.get_network()
        self.network_devices = self.get_devices()
    hostname = "http://" + socket.gethostname()
    playlists = requests.get(hostname+'/api/playlists').json()
    number_of_playlist = {'number_of_playlist': len(playlists)}

    def get_command(self, command, address):
        if hasattr(self, command):
            method = getattr(self, command, lambda: 'nothing')
            return method(address)
        elif command == 'quit':
            pass
        elif '{' in command and command.endswith('}'):
            print(json.loads(command.replace("'", '"')))
        else:
            print('Unhandled Command: ' + command)


    def get_devices(self):
        self.xbee_network.start_discovery_process()
        while self.xbee_network.is_discovery_running():
            time.sleep(0.5)
        return self.xbee_network.get_devices()

    
    def list_devices(self):
        for device in self.network_devices:
            print(device.get_64bit_addr())
    
    def get_playlist(self, playlist):
        # GET /playlist/:PlaylistName
        r = requests.get(self.hostname+'/api/playlist/'+playlist).json()
        return r
    
    def dump_json(self, json_data):
        stringify = json.dumps(json_data, indent=2)
        return stringify

    def define_playlist_values(self, playlist_json):
        """ Dictonary of only the values we need to transmit to slave players
            'playlistInfo': dict{
                total_duration: int*
                total_items: int*
            }

            'mainPlaylist': list of dicts [{
                sequenceName: str*
            }]
            'name': str
        """
        values_to_send = [{'total_duration': playlist_json['playlistInfo']['total_duration']}, {'total_items':playlist_json['playlistInfo']['total_items']}]
        for value in playlist_json['mainPlaylist']:
            values_to_send.append({'sequenceName': value['sequenceName']})
        return values_to_send

    def send_playlists(self, address):
        number_of_playlist_sent = 0
        for item in self.playlists:
            values_to_send = self.define_playlist_values(self.get_playlist(item))
            if number_of_playlist_sent == 0:
                self.send_message_to(str(self.number_of_playlist), address)
            for value in values_to_send:
                if type(value) == int:
                    self.send_message_to(str(value), address)
                elif type(value) == dict:
                    self.send_message_to(str(value), address)
                else:
                    self.send_message_to(value, address)
            number_of_playlist_sent += 1

    def send_message_all(self, message):
        for device in self.network_devices:
            self.local_xbee.send_data_async_64(device.get_64bit_addr(), message)

    

    def send_message_to(self, message, address):
        self.local_xbee.send_data_async_64(address, message)

def check_for_message(xbee_message):
    return xbee_message.data.decode()




def main():
    try:
        fpp = FppSettings()
        print('Waiting for data....')
        while True:
            xbee_message = fpp.local_xbee.read_data()
            if xbee_message:
                new_message = xbee_message.data.decode()
                sender_address = xbee_message.remote_device.get_64bit_addr()
                fpp.get_command(new_message, sender_address)
                if new_message == 'quit':
                    print('Exiting.....')
                    break
    finally:
        if fpp.local_xbee is not None and fpp.local_xbee.is_open():
            fpp.local_xbee.close()
    

main()