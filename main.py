# To change this license header, choose License Headers in Project Properties.
# To change this template file, choose Tools | Templates
# and open the template in the editor.

# Blockchain For Securing Decentralized Cloud Storage
# COMP 8045 - Major Project

# This project’s overall goal is to create a working model for a decentralized, 
# distributed block chain based secure ‘cloud’ file storage application. 
# The addition of block chain transactions will allow for network storage 
# meta data, such as URLs and access rights, to be secured.

# See related project documents:
# A00246425_Gosse_Richard_btech_majorproject_Proposol_Oct1.pdf

import datetime as date
import time
import hashlib as hasher
import sys, traceback
import struct
import os.path
import uuid # for making random UUIDs
import json
import logging
import socket, pickle # ummm, must I use pickle? reconsider...
import threading

# Project Meta Variables
__author__ = "Richard W Gosse - A00246425"
__date__ = "$1-Oct-2018 1:02:27 PM$"
VERSION = "0.1"
OUTPUTFNAME = "./logfile.txt"
#MINER_ADDRESS = "q83jv93yfnf02f8n_first_miner_nf939nf03n88fnf92n" # made unique and loads from user.cfg
BLOCKCHAIN_DATA_DIR = 'chaindata'
NODE_LIST = "./nodes.cfg"
USER_SETTINGS = "./user.cfg"
HOST = '192.168.0.15'   # local address ** unused
PORT = 8000 # local port





# define a transaction
class Transaction:
    def __init__(self, user_data, data_url):
        self.user_data = user_data          # identify user and provide security. how exactly? TBD...
        self.data_url = data_url            # encrypted URL of user's data storage location.
            
# define a Block
class Block:
    
#    def __init__(self, index, version, timestamp, previous_hash, user_data, data_url):
#        self.index = index                  # unique identifier
#        self.version = version              # project version identifier
#        self.timestamp = timestamp          # date and time of block creation
#        self.previous_hash = previous_hash  # hash of previous block
#        self.user_data = user_data          # identify user and provide security. how exactly? TBD...
#        self.data_url = data_url            # encrypted URL of user's data storage location.
#        self.hash = self.new_hash()         # pseudo-random combined with previous hash 
    
    def __init__(self, dictionary):
        for k, v in dictionary.items():
            setattr(self, k, v)
        if not hasattr(self, 'hash'):
            self.hash = self.new_hash()  
            
        
        
    def __dict__(self):
        info = {}
        info['index'] = self.index
        info['version'] = str(self.version)
        info['timestamp'] = str(self.timestamp)
        info['previous_hash'] = str(self.previous_hash)
        info['user_data'] = str(self.user_data)
        info['data_url'] = str(self.data_url)
        info['proof'] = self.proof
        info['hash'] = str(self.hash)
        return info
    
    def new_hash(self):
        sha = hasher.sha256()
        update_input = str(self.index) + str(self.timestamp) + str(self.user_data) + str(self.data_url) + str(self.previous_hash) + str(self.proof)
        sha.update(update_input.encode("utf-8"))
        return sha.hexdigest()

class ChainServer(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))

    def listen(self):
        self.sock.listen(5)
        while True:
            client, address = self.sock.accept()
            #client.settimeout(2)
            threading.Thread(target = self.serve_chain,args = (client,address)).start()

    def serve_chain(self, client, address):
        print ('Chain Request by', address)
        try:
            # Pickle the chain and send it to the requesting client
            #data_string = pickle.dumps(blockchain)
            data_string = get_blocks()
            send_msg(client, data_string)
            
            client.close()
            print ('Chain Transmitted...')
        except Exception as ex:
            client.close()
            print ("but something happened...")
            raise ex
            return False      

# create a new block to be the first in a new chain.
# data here will be for the most place symbolic or otherwise meaningless.
def create_genesis_block():
    block_data = {}
    block_data['index'] = 0
    block_data['version'] = VERSION
    block_data['timestamp'] = date.datetime.now()
    block_data['previous_hash'] = "0"
    block_data['user_data'] = "none"
    block_data["proof"] = '00000048_GENESIS_BLOCKb16e9ac6cb' #use '9' when using pof1, for pof2 use 00000048_GENESIS_BLOCKb16e9ac6cb
    block_data['data_url'] = "0"
    first_block = Block(block_data)
    write_output("------NEW CHAIN-----")
    return first_block

def write_output(output):
    stamp = str(date.datetime.now()) + " - " +  " - "
    entry = stamp + str(output)
    #entry = output
    print(entry)
    if os.path.isfile(OUTPUTFNAME):
        with open(OUTPUTFNAME, "a") as f:
            f.write("\n" + entry)
    else:
        with open(OUTPUTFNAME, "a") as f:
            f.write(entry)
            
def get_blocks():
    chain_to_send = blockchain
    for i in range(len(chain_to_send)):
        block = chain_to_send[i]
        block_index = str(block.index)
        block_version = str(block.version)
        block_timestamp = str(block.timestamp)
        block_user_data = str(block.user_data)
        block_data_url = str(block.data_url)
        block_hash = str(block.hash)
        block_proof = str(block.proof)
        block_previous_hash = str(block.previous_hash)
        
        chain_to_send[i] = {
            "index": block_index,
            "version": block_version,
            "timestamp": block_timestamp,
            "user_data": block_user_data,
            "data_url": block_data_url,
            "hash": block_hash,
            "proof": block_proof,
            "previous_hash": block_previous_hash
        }
        
    write_output("--------------------\n"
              "index:" + block_index
              + "\nversion:" + block_version
              + "\ntimestamp:" + block_timestamp
              + "\nuser_data:" + block_user_data
              + "\ndata_url:" + block_data_url
              + "\nhash:" + block_hash
              + "\nproof of work:"  + block_proof
              + "\nprevious hash:" + block_previous_hash
              )
    chain_to_send = ßjson.dumps(chain_to_send)
    return chain_to_send
        
        
        
              
        

# add a new transaction to the list       POST       
def add_transaction(user_data, data_url):
    # get incomming transaction
    # add it to the list
    write_output("New Transaction: " + user_data + " " + data_url)
    local_transactions.append(Transaction(user_data, data_url))
    

        
    

    

def proof_of_work(last_proof):  # from snakecoin server example. More research here!!!
    #gets slower over time. +3 hrs for blocks after 24
    #print("PROOF OF WORK - NOT YET FULLY IMPLEMENTED")
    # Create a variable that we will use to find
    # our next proof of work
    incrementor = last_proof + 1
     # Keep incrementing the incrementor until
     # it's equal to a number divisible by 9
     # and the proof of work of the previous
     # block in the chain
    while not (incrementor % 9 == 0 and incrementor % last_proof == 0):
        incrementor += 1
    # Once that number is found,
    # we can return it as a proof
     # of our work
    return incrementor

def proof_of_work2(last_proof): # tdjsnelling, 
    # each block is a lot slower on average. But the time required to mine each block
    # does not increase over time
    # also seems to be better at utilizing available memory. than pof1
    # tried using sha256 rather than md5. is this smart?. took alot longer duh. reverted back
    string = str(last_proof) # cast as string to be safe. Account for older versions had pof1 as an int.

    complete = False
    n = 0

    while complete == False:
            curr_string = string + str(n) # error with genblock starting with an int...
          
            curr_hash = hasher.md5(curr_string.encode()).hexdigest()
            n = n + 1

            # slows performance drastically
            # print (curr_hash)

            if curr_hash.startswith('000000'):
                    #print (curr_hash)
                    #print (curr_string)
                    complete = True
                    return curr_hash

def is_ip(addr):
    # simple check as to if a string looks like a valid IPv4 address
    # OMFG forget the string checks, just ask the hardware!
    try:
        socket.inet_aton(addr)
        return True
    except socket.error:
        return False

def mine():
    # gather the data required to mine the block
    if local_transactions: # check if list is empty, very pythonic
        #print("# of local transactions:" + str(len(local_transactions)))
        current_transaction = local_transactions.pop(0) # first in, first out
        new_block_user_data = current_transaction.user_data
        new_block_data_url = current_transaction.data_url
        
        # Get the last mined block
        # Q? what happens if we come across our own transaction? tbd
    
        length = len(blockchain)
        #print("last block:" + str(length - 1)) ## correct feeds 6        
        last_block = blockchain[length - 1]
        #print ("last block index:" + str(last_block.index)) ## incorrect feeds 5
        #print (last_block.index + 1)
        new_block_index = last_block.index + 1
        #print("new block index:" + str(new_block_index))
    
        last_block_hash = last_block.hash
        
        ### ----- PROOF OF WORK
        #proof = proof_of_work(last_block.proof) #snakecoin method. gets slower over time. +3 hrs for blocks after 24
        proof = proof_of_work2(last_block.proof) # tdjsnelling
        ### ----- END PROOF OF WORK
        
        
        #new_block = Block(new_block_index,VERSION,date.datetime.now(),last_block_hash,new_block_user_data, new_block_data_url)
        block_data = {}
        block_data['index'] = new_block_index
        block_data['version'] = VERSION
        block_data['timestamp'] = date.datetime.now()
        block_data['previous_hash'] = last_block_hash
        block_data['user_data'] = new_block_user_data
        block_data['proof'] = proof
        block_data['data_url'] = new_block_data_url
        
        new_block = Block(block_data)
        
        blockchain.append(new_block)
        save_block(new_block)

def sync_node_list():
    settings = []
    for line in open(NODE_LIST, 'r'): # every line in the node.cfg file represents a node
        parts = line.split() # return a list
        node = [parts[0], int(parts[1])]
        if is_ip(parts[0]): # does the address at least look like IPv4?
            settings.append(node) # then add it to the node list
    print ("NODE LIST:" + str(settings)) # and advertise known nodes
    return settings

def miner_address():
    for line in open(USER_SETTINGS, 'r'): # every line in the node.cfg file represents a node
        parts = line.split() # return a list
        miner_address = str([parts[0]])
    print ("MINER ADDRESS:" + miner_address) # and advertise known nodes
    return miner_address


def sync_local_chain():
    write_output("Syncronizing Blockchain...")
    if not os.path.exists(BLOCKCHAIN_DATA_DIR):
        os.mkdir(BLOCKCHAIN_DATA_DIR)
    if os.listdir(BLOCKCHAIN_DATA_DIR) == []:
        first_block = create_genesis_block() # add a genesis block to the local chain
        save_block(first_block) # save the genesis block locally    
    syncing_blocks = []
    if os.path.exists(BLOCKCHAIN_DATA_DIR):
        for filename in os.listdir(BLOCKCHAIN_DATA_DIR):
            if filename.endswith('.json'):
                filepath = '%s/%s' % (BLOCKCHAIN_DATA_DIR, filename)
                with open(filepath, 'r') as block_file:
                    block_info = json.load(block_file)
                    block_object = Block(block_info) # umm maybe need dict?
                    #print("SYNC:BLOCK:" + str(block_object.index))
                    syncing_blocks.append(block_object)
    syncing_blocks.sort(key=lambda x: x.index) # holy crap did this fix a big problem
    return syncing_blocks


def save_block(block):
    if os.path.exists(BLOCKCHAIN_DATA_DIR):
        filename = '%s/%s.json' % (BLOCKCHAIN_DATA_DIR, block.index)
        with open(filename, 'w') as block_file:
            write_output("NEW BLOCK:: " + str(block.__dict__()))
            json.dump(block.__dict__(),block_file)

def consensus(blockchain):
    # Get the blocks from other nodes
    # If our chain isn't longest,
    # then we store the longest chain
    foreign_chains = findchains()
    longest_chain = blockchain # set our blockchain as the longest
    for chain in foreign_chains: # check the list of foreign chains
        if len(longest_chain) < len(chain): # for which is the longest
            longest_chain = chain  
    blockchain = longest_chain # set the longest list as our new local chain
    return blockchain

def send_msg(sock, msg):
    # Prefix each message with a 4-byte length (network byte order)
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)

def recv_msg(rsock):
    # Read message length and unpack it into an integer
    raw_msglen = recvall(rsock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return recvall(rsock, msglen)

def recvall(rcsock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = b''
    while len(data) < n:
        packet = rcsock.recv(n - len(data))
        if not packet:
            return None
        data += packet # knows this is a byte object WTF!!!
    return data


def findchains():
    timeout=2
    global localhost
    # query other listed nodes in the network for copies of their blockchains
    foreign_chains = []
    for url in foreign_nodes:
        # get their chain using some sort of get request
        peer_address = url[0]
        if (peer_address != get_my_ip()):
            peer_port = url[1]

            # Create a socket connection.
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect((peer_address, peer_port))
                print (s)
                total_data = recv_msg(s)
                chain = json.loads(total_data)
                
                foreign_chains.append(chain)
                s.close()
                print ("Obtained Chain from peer " + str(peer_address) +" : "+ str(peer_port))
            except socket.error:
                print ("socket error Couldn't connect with peer " + str(peer_address) +" : "+ str(peer_port))
            except Exception as ex:
                print ("Couldn't connect with peer " + str(peer_address) +" : "+ str(peer_port))
                raise ex
   
        
        #print("NOT YET IMPLEMENTED")
    return foreign_chains



def get_my_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    print(ip)
    s.close()
    return ip


# Initial Setup
logging.basicConfig(filename=OUTPUTFNAME, filemode='a', format='%(name)s - %(levelname)s - %(message)s') # log errors to file
blockchain = sync_local_chain() # create a list of the local blockchain
local_transactions = [] # store transactions in a list
foreign_nodes = sync_node_list() # store urls of other nodes in a list 
blockchain = consensus(blockchain)
miner_address = miner_address()
global localhost
localhost = get_my_ip()





if __name__ == "__main__":
    
    try:
        print ("Hello World")
        print ("UPLOAD DOWNLOAD DELETE SETTINGS")
        #1/0 #test exception log
        
        
        
        print ("Listening on port " + str(PORT))
        num_connections = 0

        threading.Thread(target = ChainServer(localhost,PORT).listen(),args = (client,address)).start()
        



        # Test Create 10 Blocks in a row - obsolete Oct 3rd
    #    for x in range(0, 10):
    #        last_block = blockchain[len(blockchain) - 1]
    #        new_block_index = last_block.index + 1
    #        last_block_hash = last_block.hash
    #        new_block = Block(new_block_index,VERSION,date.datetime.now(),last_block_hash,MINER_ADDRESS, "1")
    #        blockchain.append(new_block) # add test block to the local chain
    #    get_blocks()

        # test Create Transactions in a row
        for x in range(0, 0): # vary second variable to test
            u = uuid.uuid4() # create a bogus string to represent an encrypted url 
            add_transaction(miner_address,u.hex) # attach the user dat
            
        
        # mine transactions into blocks
        if local_transactions:
            for x in range(0, 5):
                mine()
        #get_blocks()
        

    
        
        
    except BaseException as e:
        logging.error(e, exc_info=True)
        raise e
        
    print("PROGRAM COMPLETE, EXITING...") # final command
