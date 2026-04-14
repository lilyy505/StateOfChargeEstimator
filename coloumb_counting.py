import logging
from message import Message
from processors.processor import Processor
from utils import ArgumentSource
import json

log = logging.getLogger(__name__)

class Coloumb_Counting(Processor): 
    def __init__(self, arg_source: ArgumentSource):

        try:
            with open("saved_coulomb_count.json", "r") as f:
                data = json.load(f)
                
            self.savedvalue = data['coulomb_count'] #update to read from saved json file 
        except FileNotFoundError:
            log.warning("The file saved_coulomb_count.json was not found. Creating it.")
            self.savedvalue = 0
        self.lastvalue = 0 #last coulomb count before the current 

        pass 

    def check_outlier(self, current_coulomb_count: int) -> int:

        # check if coloumb count is 1000 times more than the previous output 

        if (current_coulomb_count > self.savedvalue + 50 or current_coulomb_count < self.savedvalue - 50):
            return self.savedvalue
        else:
            return current_coulomb_count

        
    
    def get_count_shutoff(self, current_coulomb_count: int) -> int:

        # get the last saved coloumb counting

        with open('saved_coulomb_count.json', 'r') as file:
            data = json.load(file)

        self.savedvalue = data['coulomb_count']

        return self.savedvalue

    def shift_coulomb_count(self, current_coulomb_count: int) -> int:

        #shifts the coulomb count based on last saved value, for when the car restarts

        return current_coulomb_count + self.savedvalue

    def save_coulomb_count(self, current_coulomb_count: int):
        data = {"coulomb_count": current_coulomb_count}
        file_path = "saved_coulomb_count.json"
        with open(file_path, "w") as f:
           json.dump(data, f, indent=4)
        self.savedvalue = current_coulomb_count

    def handle(self, messages: list[Message]) -> list[Message]:
        for message in messages:
            if message.telem_name == 'riedon.riedon_coulomb_count':

                if 'value' not in message.data:
                    log.warning("Not converting to updated coulomb count, because the coulomb count data didn't have a 'value' field")
                    continue
                current_coulomb_count = message.data['value']

                if not isinstance(current_coulomb_count, int):
                    log.warning("Not converting to updated coulumb count, because the coulomb count data wasn't an integer") 
                    continue

                # if statement checking if I need to shift the coulomb count

                '''if current_coulomb_count == 0:
                    updated_coulomb_count: int = self.shift_coulomb_count(current_coulomb_count)
                else:
                    updated_coulomb_count: int = self.check_outlier(current_coulomb_count)
                    self.lastvalue = updated_coulomb_count
                '''
                # updated_coulomb_count: int = self.check_outlier(current_coulomb_count)
                #self.lastvalue = updated_coulomb_count

                if self.savedvalue == 0:
                    updated_coulomb_count = current_coulomb_count
                elif current_coulomb_count < 100:
                    updated_coulomb_count = self.savedvalue + current_coulomb_count
                else:
                    updated_coulomb_count = current_coulomb_count

                self.save_coulomb_count(updated_coulomb_count)
                messages.append(Message(0x3F2,{"value": updated_coulomb_count},message.timestamp,'calculated_values.adjusted_coulomb_count'))
        return messages 
