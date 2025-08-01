class DiscordMessage:

    def __init__(self, value: any = None):
        self.value = value

class DiscordMessageReply(DiscordMessage):

    def __init__(self, value: str):
        super().__init__(value)

class DiscordMessageTmp(DiscordMessageReply):
    pass

class DiscordMessageFile(DiscordMessage):

    def __init__(self, value: bytes, filename: str):
        super().__init__(value)
        self.filename = filename

class DiscordMessageEnd(DiscordMessage):
    pass