def send_playlist(message, reciever):
    print('hello')
    print(message, reciever)


def get_command(command, message, reciever):
    command_message_function = {
        'playlist_update': send_playlist
    }
    func = command_message_function.get(command, lambda: 'nothing')
    return func(message, reciever)


get_command('playlist_update', 'bye', 'max')
