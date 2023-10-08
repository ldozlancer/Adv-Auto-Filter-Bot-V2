import re
import motor.motor_asyncio # pylint: disable=import-error
from bot import DB_URI # pylint: disable=import-error

class Singleton(type):
    __instances__ = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances__:
            cls.__instances__[cls] = super(Singleton, cls).__call__(*args, **kwargs)

        return cls.__instances__[cls]


class Database(metaclass=Singleton):

    def __init__(self):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
        self.db = self._client["Adv_Auto_Filter"]
        self.col = self.db["Main"]
        self.acol = self.db["Active_Chats"]
        self.fcol = self.db["Filter_Collection"]
        
        self.cache = {}
        self.acache = {}


    async def create_index(self):
        """
        Create text index if not in db
        """
        await self.fcol.create_index([("file_name", "text")])


    def new_chat(self, group_id, channel_id, channel_name):
        """
        Create a document in db if the chat is new
        """
        try:
            group_id, channel_id = int(group_id), int(channel_id)
        except:
            pass
        
        return dict(
            _id = group_id,
            chat_ids = [{
                "chat_id": channel_id,
                "chat_name": channel_name
                }],
            types = dict(
                audio=False,
                document=True,
                video=True
            ),
            configs = dict(
                accuracy=0.80,
                max_pages=5,
                max_results=50,
                max_per_page=10,
                pm_fchat=True,
                show_invite_link=True
            )
        )


    async def status(self, group_id: int):
        """
        Get the total filters, total connected
        chats and total active chats of a chat
        """
        group_id = int(group_id)
        
        total_filter = await self.tf_count(group_id)
        
        chats = await self.find_chat(group_id)
        chats = chats.get("chat_ids")
        total_chats = len(chats) if chats is not None else 0
        
        achats = await self.find_active(group_id)
        if achats not in (None, False):
            achats = achats.get("chats")
            if achats == None:
                achats = []
        else:
            achats = []
        total_achats = len(achats)
        
        return total_filter, total_chats, total_achats


    async def find_group_id(self, channel_id: int):
        """
        Find all group id which is connected to a channel 
        for add a new files to db
        """
        data = self.col.find({})
        group_list = []

        for group_id in await data.to_list(length=50): # No Need Of Even 50
            for y in group_id["chat_ids"]:
                if int(y["chat_id"]) == int(channel_id):
                    group_list.append(group_id["_id"])
                else:
                    continue
        return group_list

    # Related TO Finding Channel(s)
    async def find_chat(self, group_id: int):
        """
        A funtion to fetch a group's settings
        """
        connections = self.cache.get(str(group_id))
