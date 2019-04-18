#!/usr/bin/env python3

import socket
import json
import subprocess
import os
import pathlib
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

    def generate_files(self, files, file_list):
        for i in files:
            file_list.append(i)

    def print_hostname(self):
        print("My hostname is: ", self.hostname)

    def get_json(self, files, file_data):
        for _file in files:
            with _file.open() as json_file:
                file_data.append(json.load(json_file))
    
    def dump_json(self, file_data):
        file_data = json.dumps(file_data, indent=2)
        return file_data

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

    def send_playlists(self, values_to_send):
        for value in values_to_send:
            print('Value: ' + str(value))
            if type(value) == int:
                self.send_message_all(str(value))
            elif type(value) == dict:
                self.send_message_all(str(value))
            else:
                self.send_message_all(value)

    def send_message_all(self, message):
        for device in self.network_devices:
            self.local_xbee.send_data_async_64(device.get_64bit_addr(), message)


def main():
    fpp = FppSettings()
    for item in fpp.playlists:
        print(len(fpp.playlists))
        fpp.send_playlists(fpp.define_playlist_values(fpp.get_playlist(item)))
    fpp.local_xbee.close()

    
try:
    while True:
        main()
except:
    KeyboardInterrupt