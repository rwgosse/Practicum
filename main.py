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
import socket, pickle # pickle for serializing binary and string data
import threading
import random
import signal
import configparser

# Project Meta Variables
__author__ = "Richard W Gosse - A00246425"
__date__ = "$26-Oct-2018 2:09:00 PM$"
VERSION = "0.2"
OUTPUTFNAME = "./logfile.txt"
#MINER_ADDRESS = "q83jv93yfnf02f8n_first_miner_nf939nf03n88fnf92n" # made unique and loads from user.cfg
BLOCKCHAIN_DATA_DIR = 'chaindata'
#NODE_LIST = "./nodes.cfg" # absored into settings.cfg and new parser
#USER_SETTINGS = "./user.cfg" # absored into settings.cfg and new parser
HOST = '192.168.0.15'   # local address ** unused
CHAIN_PORT = 8000 # local port for hosting of chain data
DATA_DIR = 'chunkdata'
FS_IMAGE = 'fs.img'
CONFIG_FILE = 'settings.cfg'


# signal handler to maintain local chunk file system
def int_handler(signal, frame):
    pickle.dump((storage_node_master.file_table, storage_node_master.chunk_mapping), open(FS_IMAGE, 'wb'))
    sys.exit(0)

def set_configuration():
    logging.basicConfig(filename=OUTPUTFNAME, filemode='a', format='%(name)s - %(levelname)s - %(message)s') # log errors to file
    conf = configparser.ConfigParser()
    conf.readfp(open(CONFIG_FILE))
    miner_address = get_miner_address(conf)
    block_size = int(conf.get('master', 'chunk_size'))
    replication_factor = int(conf.get('master', 'replication_factor'))
    foreign_nodes = sync_node_list(conf) # store urls of other nodes in a list
    blockchain = sync_local_chain() # create a list of the local blockchain
    blockchain = consensus(blockchain, foreign_nodes) # ensure that our blockchain is the longest



    if os.path.isfile(FS_IMAGE):
        storage_node_master.file_table, storage_node_master.chunk_mapping = pickle.load(open(FS_IMAGE, 'rb'))

    return blockchain, miner_address

# define a transaction
class Transaction:
    def __init__(self, user_data, data_url):
        self.user_data = user_data          # identify user and provide security. how exactly? TBD...
        self.data_url = data_url            # encrypted URL of user's data storage location.

# define a Block
class Block:

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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create socket
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # avoid common errors
        self.sock.bind((self.host, self.port)) # bind the socket

        thread = threading.Thread(target=self.listen, args=())
        thread.daemon = False                            # Daemonize thread
        thread.start()                                  # Start the execution

    def listen(self):
        # listen for incomming chain requests
        print ("Serving Chain Requests on port " + str(self.port))
        self.sock.listen(5) # on self.sock
        while True: #
            client, address = self.sock.accept() # accept incomming connection
            threading.Thread(target=self.serve_chain, args=(client, address)).start() # pass connection to a new thread

    def serve_chain(self, client, address):
        # we have accepted an incomming connection request
        print ('Chain Request by: ', address)
        try:

            # get our local chain of blocks
            if os.path.exists(BLOCKCHAIN_DATA_DIR): # assuming the folder exists...
                for filename in os.listdir(BLOCKCHAIN_DATA_DIR): # for every file...
                    if filename.endswith('.json'): # if it's a json file
                        filepath = '%s/%s' % (BLOCKCHAIN_DATA_DIR, filename) # get it
                        with open(filepath, 'r') as block_file: # and open it up
                            block_info = json.load(block_file) # load it's data

                            #print(type(block_info)) # should return dict
                            #print(block_info)



                            client.send(pickle.dumps(block_info))
                            time.sleep(0.05) ## jesus this is risky but effective in spliting the byte stream




            client.close()

            print ('Chain Transmitted to: ', address)
        except Exception as ex:
            client.close()
            print ("Critical Transmission Error") # hopeful doesn't happen. FIX later to avoid catch all
            raise ex
            return False

class StorageNodeMaster():
    def __init__(self):
        file_table = {}
        chunk_mapping = {}
        minions = {}
        chunk_size = 0
        replication_factor = 0


    def master_read(self, fname):
        mapping = self.file_table[fname]
        return mapping

    def master_write(self, dest, size):
        if self.exists(dest):
            pass #ignore for now
        self.file_table[dest] = []
        num_chunks = self.calculate_number_of_chunks(size)
        chunks = self.allocate_chunks(dest, num_chunks)
        return chunks

    def get_file_table_entry(self, fname):
        if fname in self.file_table:
            return self.file_table[fname]
        else:
            return None

    def get_chunk_size(self):
        return self.chunk_size

    def get_minions(self):
        return self.minions

    def calculate_number_of_chunks(self, size):
        return int(math.ceil(float(size) / self.block_size))

    def exists(self, fname):
        return file in self.file_table

    def allocate_chunks(self, dest, num):
        chunks = []
        for i in range(0, num):
            chunk_uuid = uuid.uuid1()
            nodes_ids = random.sample(self.minions.keys(), self.replication_factor)
            chunks.append((block.uuid, nodes_ids))
            self.file_table[dest].append((block_uuid, nodes_ids))
            return chunks



class StorageNodeMinion():
    def __init__(self):
        chunks = {}


    def minion_put(self, chunk_uuid, data, minions):
        pass

    def minion_get(self, chunk_uuid):
        pass

    def forward(self, chunk_uuid, data, minions):
        pass

    def delete_block(self, uuid):
        pass


class Client:
    def __init__(self):
        pass

    def get(self, master, fname):
        pass

    def read_minion(self, block_uuid, minion):
        pass

    def put(self, master, source, dest):
        pass

    def send_to_minion(self, block_uuid, data, minions):
        pass

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
    stamp = str(date.datetime.now()) + " - " + " - "
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
    chain_to_send = json.dumps(chain_to_send)
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

def sync_node_list(conf):

    nodes = []
    #for line in open(NODE_LIST, 'r'): # every line in the node.cfg file represents a node
    #    parts = line.split() # return a list
    #    node = [parts[0], int(parts[1])]
    #    if is_ip(parts[0]): # does the address at least look like IPv4?
    #        nodes.append(node) # then add it to the node list
    node_list = conf.get('miner', 'peer_nodes').split(',')
    for n in node_list:
        host, port = n.split(':')
        if is_ip(host): # does the address at least look like IPv4?
            node = [host, int(port)]
            nodes.append(node) # then add it to the node list






    #print ("NODE LIST:" + str(settings)) # and advertise known nodes
    return nodes

def get_miner_address(conf):
    #for line in open(USER_SETTINGS, 'r'): # every line in the node.cfg file represents a node
        #   parts = line.split() # return a list
        #   miner_address = str([parts[0]])
    miner_address = conf.get('miner', 'miner_address')
    write_output("MINER ADDRESS:" + miner_address) # and advertise known nodes
    return miner_address


def sync_local_chain():

    write_output("Syncronizing Blockchain...")
    syncing_blocks = []
    if not os.path.exists(BLOCKCHAIN_DATA_DIR): # is there no local block folder?
        os.mkdir(BLOCKCHAIN_DATA_DIR)
    if os.listdir(BLOCKCHAIN_DATA_DIR) == []: # is the folder empty, ie no local genesis block?
        # try to find a remote chain to adopt before creating a new chain
        syncing_blocks = consensus(syncing_blocks)
        if os.listdir(BLOCKCHAIN_DATA_DIR) == []: # is it still empty?
            first_block = create_genesis_block() # add a genesis block to the local chain
            save_block(first_block) # save the genesis block locally


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
            json.dump(block.__dict__(), block_file)

def consensus(blockchain, foreign_nodes):
    new_chain = False # initial condition
    # Get the blocks from other nodes
    # If our chain isn't longest,
    # then we store the longest chain
    foreign_chains = findchains(foreign_nodes) # query peers in the list for their chains
    longest_chain = blockchain # set our blockchain as the initial longest
    for chain in foreign_chains: # check the list of foreign chains
        write_output("COMPARE: LOCAL: " + str(len(longest_chain)) + " <VS> REMOTE: " + str(len(chain)))
        if len(longest_chain) < len(chain): #if the incomming chain is longer than the present longest
            longest_chain = chain # set it as the longest_chain
            new_chain = True
    blockchain = longest_chain # set the longest list as our new local chain
    blockchain.sort(key=lambda x: x.index) # holy crap did this fix a big problem
    if new_chain: #check condition
        write_output("NEW LONG CHAIN")
        for block in blockchain:
            filename = '%s/%s.json' % (BLOCKCHAIN_DATA_DIR, block.index)
            if not os.path.isfile(filename): # do not write over existing block files until chain integrity check implemented
                with open(filename, 'w') as block_file:
                    write_output("ABOPTING BLOCK:: " + str(block.__dict__()))
                    json.dump(block.__dict__(), block_file)
    return blockchain

def findchains(foreign_nodes):
    timeout = 2
    global localhost
    # query other listed nodes in the network for copies of their blockchains
    list_of_chains = []
    for url in foreign_nodes:
        # get their chain using some sort of get request
        peer_address = url[0]
        if (peer_address != get_my_ip()):
            peer_port = url[1]

            # Create a socket connection.
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.settimeout(timeout)
                s.connect((peer_address, peer_port))

                #print (s)
                this_chain = []
                while True:

                    incomming = s.recv(1024) # determine a decent byte size.
                    # 4096 is pretty big considering our json files are ~397, genesis being 254
                    # 1024 seems reliable
                    if not incomming:
                        break
                    # determine break point between objects
                    # currently the server is just time.sleep(0.05) between breaks
                    #print (incomming)
                    dict = pickle.loads(incomming) # create a dictionary from the stream data
                    #print(type(dict)) # should return dict
                    block_object = Block(dict) # use the dictionary to create a block object
                    #print(type(block_object)) # should return block

                    # ____________________________________________________________________________________
                    # check for obsolete blocks in the incomming chain
                    # we want to discard those blocks that have an
                    # version # less than the current version
                    if (block_object.version == VERSION): # expected, normal
                        this_chain.append(block_object)
                    elif (block_object.version > VERSION): # incomming block from higher version #
                        this_chain.append(block_object)
                        write_output("!INCOMMING BLOCK HAS HIGHER VERSION # - UPDATE PROGRAM!")
                    else: # the incomming block is obsolete and will not be considered # chain of fools
                        write_output("!OBSOLETE INCOMMING BLOCK - DISCARDED!")
                    # ____________________________________________________________________________________

                s.close()
                write_output("Obtained Chain from Remote " + str(peer_address) + " : " + str(peer_port))






                list_of_chains.append(this_chain) # add incomming chain to the list of chain




            except socket.timeout as ex:
                write_output("NA:" + str(peer_address) + " : " + str(peer_port))

            except socket.error as ex:
                write_output("ERR:" + str(peer_address) + " : " + str(peer_port))

    return list_of_chains



def get_my_ip():
    # quick & lazy implement, query google for my ip
    #s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #s.connect(("8.8.8.8", 80)) # not reliable, there may not be an assumed Internet connection
    #ip = s.getsockname()[0]
    #s.close()

    # Better, and will function on those networks without an Internet connection
    ip = ((([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2]
          if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)),
          s.getsockname()[0], s.close())
          for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0])
    return ip











# Initial Setup

local_transactions = [] # store transactions in a list



global localhost
localhost = get_my_ip()







if __name__ == "__main__":

    try:
        signal.signal(signal.SIGINT, int_handler) # set up handler for chunk table image

        blockchain, miner_address = set_configuration()
        print ("Hello World")
        print ("UPLOAD DOWNLOAD DELETE SETTINGS")
        #1/0 #test exception log


        chainserver = ChainServer(localhost, CHAIN_PORT)
        write_output("start tests...")


        # Test Create 10 Blocks in a row - obsolete Oct 3rd
    #    for x in range(0, 10):
    #        last_block = blockchain[len(blockchain) - 1]
    #        new_block_index = last_block.index + 1
    #        last_block_hash = last_block.hash
    #        new_block = Block(new_block_index,VERSION,date.datetime.now(),last_block_hash,MINER_ADDRESS, "1")
    #        blockchain.append(new_block) # add test block to the local chain
    #    get_blocks()

        # test Create Transactions in a row
        for x in range(0, 1): # vary second variable to test
            u = uuid.uuid4() # create a bogus string to represent an encrypted url
            add_transaction(miner_address, u.hex) # attach the user dat


        # mine transactions into blocks
        if local_transactions:
            for x in range(0, 5):
                mine()
        #get_blocks()

    except BaseException as e:
        logging.error(e, exc_info=True) # ensure exceptions and such things are logged for prosperity
        raise e # but still crash the program naturally

    write_output("PROGRAM COMPLETE, SERVING UNTIL MANUAL ABORT...") # final command
    sys.exit()
