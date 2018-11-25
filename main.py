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
import math
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
from Crypto.Cipher import AES
from Crypto import Random
import base64

# Project Meta Variables
__author__ = "Richard W Gosse - A00246425" # name, student number
__date__ = "$26-Nov-2018 9:51:00 AM$" # updated with each version change
VERSION = "0.4" # aibitrary version number, updated manually during development, does not relate to any commits
OUTPUTFNAME = "./logfile.txt" # output log file
#MINER_ADDRESS = "q83jv93yfnf02f8n_first_miner_nf939nf03n88fnf92n" # made unique and loads from user.cfg
BLOCKCHAIN_DATA_DIR = 'chaindata' # folder for json formatted blocks
#NODE_LIST = "./nodes.cfg" # absored into settings.cfg and new parser
#USER_SETTINGS = "./user.cfg" # absored into settings.cfg and new parser
#HOST = '192.168.0.15' # local address ** unused
CHAIN_PORT = 8000  # local port for hosting of chain data
MASTER_PORT = 8100 # local port for hosting of storage master
MINION_PORT = 8200 # local port for hosting of storage minion
DATA_DIR = 'chunkdata' # chunk data directory
FS_IMAGE = 'fs.img' # chunk file mapping system
CONFIG_FILE = 'settings.cfg' # local file with settings
SPLIT = '\n' # used to line break socket streams
TESTFILE = 'testfile.jpg' # file used for uploads & downloads during dev
RECEIVED_FILE_PREFIX = 'new_' # for demo purposes and so I don't loose orig files if i do something dumb
RECEIVED_FILE_SUFFIX = '_new'
PASSPHRASE = '8A0F8F3B1D0FA8720104C22E8A15CCDF' # default Passphrase er key.
BLOCK_SIZE = 32 # the block size for the cipher object; must be 16, 24, or 32 for AES
active_master = False # default to off. control in settings.cfg
active_minion = False # default to off. control in settings.cfg
active_miner = False # default to off. control in settings.cfg
active_client = False # default to off. control in settings.cfg
file_table = {} # represents the FS_IMAGE while in use. 
chunk_mapping = {} # maps filenames to their chunks and minion locations


def int_handler(signal, frame): # signal handler to maintain local chunk file system
    global file_table
    global chunk_mapping
    pickle.dump((file_table, chunk_mapping), open(FS_IMAGE, 'wb'))
    sys.exit(0)

def set_configuration(): # load settings from config file
    global active_master
    global active_minion
    global active_miner
    global active_client
    logging.basicConfig(filename=OUTPUTFNAME, filemode='a', format='%(name)s - %(levelname)s - %(message)s') # log errors to file
    conf = configparser.ConfigParser()
    conf.readfp(open(CONFIG_FILE))

    if (conf.get('master', 'active_master') == 'yes'):
        print ("active master")
        active_master = True

    if (conf.get('minion', 'active_minion') == 'yes'):
        print ("active minion")
        active_minion = True

    if (conf.get('miner', 'active_miner') == 'yes'):
        print ("active miner")
        active_miner = True

    if (conf.get('client', 'active_client') == 'yes'):
        print ("active client")
        active_client = True

    miner_address = get_miner_address(conf)
    chunk_size = int(conf.get('master', 'chunk_size'))
    replication_factor = int(conf.get('master', 'replication_factor'))
    master_address, master_port = get_master_address(conf)
    minions = {}
    minionslist = conf.get('master', 'minions').split(',')
    for m in minionslist:
        id, host, port = m.split(':')
        minions[id] = (host, port)
    blockchain = organise_chain()
    return blockchain, miner_address, master_address, master_port, minions, chunk_size, replication_factor

def organise_chain():
    conf = configparser.ConfigParser()
    conf.readfp(open(CONFIG_FILE))
    foreign_nodes = sync_node_list(conf) # store urls of other nodes in a list
    blockchain = sync_local_chain(foreign_nodes) # create a list of the local blockchain
    blockchain = consensus(blockchain, foreign_nodes) # ensure that our blockchain is the longest
    return blockchain

class Transaction: # define a transaction, which is a record of an uploaded chunk
    def __init__(self, user_data, data_hash, data_url):
        self.user_data = user_data          # identify user and provide security. how exactly? TBD...
        self.data_hash = data_hash
        self.data_url = data_url            # encrypted URL of user's data storage location.

class Block: # define a Block, this is what it's all about

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
        info['data_hash'] = str(self.data_hash)
        info['data_url'] = str(self.data_url)
        info['proof'] = self.proof
        info['hash'] = str(self.hash)
        return info

    def new_hash(self): # hash for the new block
        sha = hasher.sha256()
        update_input = str(self.index) + str(self.timestamp) + str(self.user_data) + str(self.data_hash) + str(self.data_url) + str(self.previous_hash) + str(self.proof)
        sha.update(update_input.encode("utf-8"))
        return sha.hexdigest()

class ChainServer(object): # provides the means to share the blockchain with clients
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create socket
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # avoid common errors
        self.sock.bind((self.host, self.port)) # bind the socket
        thread = threading.Thread(target=self.listen, args=())
        thread.daemon = False                            # Daemonize thread
        thread.start()                                  # Start the execution

    def listen(self): # listen for incomming chain requests
        write_output("CHAINSERVER: PORT# " + str(self.port))
        self.sock.listen(5) # on self.sock
        while True: #
            chain_client_socket, chain_client_address = self.sock.accept() # accept incomming connection
            threading.Thread(target=self.serve_chain, args=(chain_client_socket, chain_client_address)).start() # pass connection to a new thread

    def serve_chain(self, chain_client_socket, chain_client_address): # incomming connection request
        chain_client_socket.settimeout(2)
        try: # get our local chain of blocks
            if os.path.exists(BLOCKCHAIN_DATA_DIR): # assuming the folder exists...
                for filename in os.listdir(BLOCKCHAIN_DATA_DIR): # for every file...
                    #time.sleep(0.25)
                    if filename.endswith('.json'): # and if it's a json file
                        filepath = '%s/%s' % (BLOCKCHAIN_DATA_DIR, filename) # grab it
                        with open(filepath, 'r') as block_file: # and open it up
                            block_info = json.load(block_file) # load it's data
                            thing = pickle.dumps(block_info)
                            go = chain_client_socket.recv(1024).decode()
                            if(go == "go"):
                                time.sleep(0.05)
                                chain_client_socket.send(thing) # package and send it, * windows has trouble with pickle perhaps??
                            
                            
                            
                msg = "done".encode('utf-8')            
                chain_client_socket.send(msg)
                
                chain_client_socket.close()
                write_output("CHAINSERVER: Chain Transmitted to: " + str(chain_client_address))
        except Exception as ex:
            #chain_client_socket.close()
            write_output("CHAINSERVER: Transmission Error") # hopeful doesn't happen. 
            raise ex
            return False

class StorageNodeMaster(): # controller for storage master node
    def __init__(self, host, port, minions, chunk_size, replication_factor):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create socket
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # avoid common errors
        self.sock.bind((self.host, self.port)) # bind the socket
        self.chunk_size = chunk_size
        self.replication_factor = replication_factor
        global file_table
        global chunk_mapping
        if not os.path.isfile(FS_IMAGE):
            pickle.dump((file_table, chunk_mapping), open(FS_IMAGE, 'wb'))

        file_table, chunk_mapping = pickle.load(open(FS_IMAGE, 'rb'))

        self.minions = minions
        thread = threading.Thread(target=self.listen, args=())
        thread.daemon = False                            # Daemonize thread
        thread.start()                                  # Start the execution


    def listen(self): # we will receive either a read command or a write command
        write_output("MASTER: Port # " + str(self.port))
        self.sock.listen(5) # on self.sock
        incomming = ''
        while True: #
            client_socket, client_address = self.sock.accept() # accept incomming connection
            incomming = (client_socket.recv(4096).decode())
            if not incomming:
                break
            incomming = incomming.split(SPLIT) # determine nature of request

            if incomming[0].startswith("P"): # put request
                write_output("MASTER: incomming put request" + str(client_address))
                dest = incomming[1]
                size = incomming[2]
                threading.Thread(target=self.master_write, args=(client_socket, client_address, dest, size)).start() # pass connection to a new thread

            if incomming[0].startswith("G"): #get request:
                write_output("MASTER: incomming get request" + str(client_address))
                fname = incomming[1]
                threading.Thread(target=self.master_read, args=(client_socket, client_address, fname)).start() # pass connection to a new thread

            if incomming[0].startswith("M"): #map request:
                write_output("MASTER: incomming map request" + str(client_address))
                #node_ids = incomming[1]
                threading.Thread(target=self.get_minions, args=(client_socket, client_address, node_ids)).start() # pass connection to a new thread

    def master_read(self, client_socket, client_address, filename):
        try:
            mapping = file_table[filename]
        except:
            write_output("MASTER: requested file not found")
            return
        mapping = pickle.dumps(mapping)
        client_socket.send(mapping)
        msg = client_socket.recv(1096).decode()
        if (msg == "M"):
            minions2send = pickle.dumps(self.get_minions())
            client_socket.send(minions2send)

    def master_write(self, client_socket, client_address, dest, size):
        
        if self.exists(dest):
            pass #do nothing for now
        
        file_table[dest] = []

        request = client_socket.recv(2048).decode()
        if (request == 'get minions'):
            reply = (self.minions)
            reply = pickle.dumps(reply)
            client_socket.send(reply)

        request = client_socket.recv(2048).decode()
        if (request == 'get data'):
            num_chunks = self.calculate_number_of_chunks(size)
            chunks, nodes_ids = self.allocate_chunks(dest, num_chunks)
            chunks = pickle.dumps(chunks)
            client_socket.send(chunks)

        request = client_socket.recv(2048).decode()
        if (request == 'get nodes_ids'):
            nodes_ids = pickle.dumps(nodes_ids)
            client_socket.send(nodes_ids)


    def get_file_table_entry(self, fname):

        if fname in file_table:
            return file_table[fname]
        else:
            return None

    def get_chunk_size(self):
        return self.chunk_size

    def get_minions(self):
        return self.minions

    def calculate_number_of_chunks(self, size):
        return int(math.ceil(float(size) / self.chunk_size))

    def exists(self, file):
        return file in file_table

    def allocate_chunks(self, dest, num):
        chunks = []
        for i in range(0, num):
            chunk_uuid = uuid.uuid1()
            nodes_ids = random.sample(self.minions.keys(), self.replication_factor) # do ensure more minions than replication factor
            print("MASTER: " + chunk_uuid.hex + " -> " + str(nodes_ids))
            chunks.append((chunk_uuid.hex, nodes_ids))
            file_table[dest].append((chunk_uuid.hex, nodes_ids))
            pickle.dump((file_table, chunk_mapping), open(FS_IMAGE, 'wb'))
        return chunks, nodes_ids # i noticed this was shifted right an extra tab, correction nov 9th YEA!

# controller for chunk storage node
class StorageNodeMinion():
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create socket
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # avoid common errors
        self.sock.bind((self.host, self.port)) # bind the socket
        chunks = {}
        thread = threading.Thread(target=self.listen, args=())
        thread.daemon = False                            # Daemonize thread
        thread.start()                                  # Start the execution
        mining_thread = threading.Thread(target=self.mining, args=())
        mining_thread.daemon = False                            # Daemonize thread
        mining_thread.start()
        
    def mining(self):
        while True:
            if local_transactions:
                mine()

    def listen(self):
        # we will receive either a read command or a write command
        if not os.path.exists(DATA_DIR): # is there no local chunk folder?
            os.mkdir(DATA_DIR) # if not make one
        write_output("MINION: Port # " + str(self.port))
        self.sock.listen(5) # on self.sock
        while True: #
            storage_client_socket, storage_client_address = self.sock.accept() # accept incomming connection
            threading.Thread(target=self.incoming, args=(storage_client_socket, storage_client_address)).start()
        sock.close()

    def incoming(self, storage_client_socket, storage_client_address):
        incomming = ''
        while True:
            incomming = (storage_client_socket.recv(2048).decode())
            if not incomming:
                break
            incomming = incomming.split(SPLIT) # determine nature of request
            if incomming[0].startswith("P"): # put request
                # RECEIVE META
                chunk_uuid = incomming[1]
                chunksize = int(incomming[2])
                # RECEIVE MINIONS
                storage_client_socket.send(('get minions').encode('utf-8'))
                incomming_minions = storage_client_socket.recv(4096)
                incomming_minions = pickle.loads(incomming_minions)

                # RECEIVE THE CHUNK
                storage_client_socket.send(('get data').encode('utf-8'))
                rec = True
                data = b''
                while rec:
                    stream = storage_client_socket.recv(1024)
                    data += stream
                    if (chunksize == len(data)):
                        rec = False
                # WRITE THE CHUNK TO STORAGE
                chunkpath = '%s/%s' % (DATA_DIR, chunk_uuid)
                if os.path.exists(DATA_DIR):
                    with open(chunkpath, 'wb') as chunk_to_write: # open the local file
                        chunk_to_write.write(data)
                        chunk_to_write.close()
                        storage_client_socket.send(('done').encode('utf-8'))
                        write_output("MINION: Received Chunk from:" + str(storage_client_address))
                if len(incomming_minions) > 0: # are there additional minions to carry the chunk?
                    self.forward(chunk_uuid, data, incomming_minions) # then forward the chunk!

                storage_client_socket.close()


                write_output("MINION: create transaction...")
                sha = hasher.sha256()
                sha.update(data)
                hashed_data = sha.hexdigest()
                add_transaction(miner_address, hashed_data, chunk_uuid) # attach the user dat
                break

            if incomming[0].startswith("G"): #get request:
                chunk_uuid = incomming[1]
                chunk_addr = DATA_DIR + "/" + chunk_uuid
                if not os.path.isfile(chunk_addr):
                    chunk = None
                with open(chunk_addr, 'rb') as f:
                    chunk = f.read()
                chunk = pickle.dumps(chunk)
                chunksize = len(chunk)
                chunksize = str(chunksize)
                storage_client_socket.send(chunksize.encode('utf-8'))
                time.sleep(0.1)
                incomming = storage_client_socket.recv(1096).decode()
                if incomming == 'go':
                    storage_client_socket.sendall(chunk)
                reply = storage_client_socket.recv(1024).decode()
                if (reply == 'done'):
                    write_output("MINION: CHUNK SENT TO CLIENT " + str(storage_client_address))

                else:
                    write_output("MINION: FAILED TO SEND CHUNK " + str(storage_client_address))


    def forward(self, chunk_uuid, data, incomming_minions):
        minion = incomming_minions[0]
        incomming_minions = incomming_minions[1:]
        minion_host, minion_port = minion
        forwarding_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Create a socket connection.
        try:
            timeout = 5
            forwarding_socket.settimeout(timeout)
            forwarding_socket.connect((minion_host, int(minion_port)))


            # START META DATA
            msg = "P" + SPLIT + str(chunk_uuid) + SPLIT + str(len(data)) #str(sys.getsizeof(data)) # get sizeof adds 33 extra :(
            msg = msg.encode('utf-8') # string to bytewise
            forwarding_socket.send(msg)

            request = forwarding_socket.recv(2048).decode()
            if (request == 'get minions'):
                minions = pickle.dumps(incomming_minions)
                forwarding_socket.send(minions)

            request = forwarding_socket.recv(2048).decode()
            if (request == 'get data'):
                # START ACTUAL CHUNK DATA
                forwarding_socket.sendall(data)

            request = forwarding_socket.recv(2048).decode()
            if (request == 'done'):
                write_output("MINION: Forwarded to: " + minion_host)


        except socket.error as er:
            write_output("MINION: no contact with minion: " + minion_host)
            #raise er

    def delete_block(self, uuid):
        pass


# controller for client node
class Client:
    def __init__(self):
        pass

    def get(self, fname):
        global master_address
        global master_port

        try:
            socket_to_master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)# Create a socket connection.
            socket_to_master.settimeout(1)
            socket_to_master.connect((master_address, master_port))
        except socket.error as er:
            write_output("CLIENT: failed to connect with master")
            #raise er
        
        try:
            msg = "G" + SPLIT + str(fname) # get file by name
            msg = msg.encode('utf-8') # string to bytewise
            socket_to_master.send(msg)
            table = socket_to_master.recv(4096)
            table = pickle.loads(table)

            msg = "M" # get minions from the master
            msg = msg.encode('utf-8') # string to bytewise
            socket_to_master.send(msg)
            minion_list = socket_to_master.recv(4096)
            minion_list = pickle.loads(minion_list)
        except socket.error as er:
            write_output("CLIENT: NETWORK FILE NOT FOUND")
            return
            #raise er

        if (os.path.isfile(fname)):
            ask = True
            while ask:
                choice = input("File Exists... Overwrite? y/n:")
                if (choice == "y" or choice == "yes" or choice =="Y"):
                    newfilename = fname
                    ask = False
                elif (choice == 'n' or choice == "no" or choice == "N"):
                    newfilename = fname + RECEIVED_FILE_SUFFIX   
                    ask = False
                else:
                    print("y/n")
        else: 
            newfilename = fname

        
        
        
        with open(newfilename, "wb") as f:
            for chunk in table:
                for m in [minion_list[_] for _ in chunk[1]]:
                    data = self.read_from_minion(chunk[0], m)
                    if data:
                        f.write(data)
                        break
                else:
                    print("no chunks found, corrupt file?") # something has messed with either the master or perhaps a single source minion
                    

        write_output("CLIENT: <---    DOWNLOADED FILE: " + newfilename)

    def read_from_minion(self, chunk_uuid, minion):
        host, port = minion
        try:
            socket_to_minion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)# Create a socket connection.
            socket_to_minion.settimeout(5)
            socket_to_minion.connect((host, int(port)))
            msg = "G" + SPLIT + chunk_uuid # get minions from the master
            msg = msg.encode('utf-8') # string to bytewise
            socket_to_minion.send(msg)
            chunksize = socket_to_minion.recv(32).decode()
            msg = "go"
            msg = msg.encode('utf-8') # string to bytewise
            socket_to_minion.send(msg)
            rec = True
            chunk = b''
            while rec:
                stream = socket_to_minion.recv(1024)
                chunk += stream
                if (len(chunk) == int(chunksize)):
                    rec = False
            msg = "done"
            msg = msg.encode('utf-8') # string to bytewise
            socket_to_minion.send(msg)
            chunk = pickle.loads(chunk)
            chunk = encrypter.decrypt(passphrase, chunk)
            return chunk

        except socket.error as er:
            write_output("CLIENT: failed to read from minion" + host)
            #raise er

    def put(self, source):
        if not (os.path.isfile(source)):
            write_output(source + " FILE NOT FOUND")
            return
            
        timeout = 20
        
        size = os.path.getsize(source)
        chunks = ''

        # SEND SOURCE AND DESTINATION TO MASTER
        # EXPECT RETURN OF CHUNK META

        global master_address
        global master_port

        dest = source ## ?? whats this for?

        try:
            # Create a socket connection.
            socket_to_master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_to_master.settimeout(5)
            socket_to_master.connect((master_address, master_port))

            msg = "P" + SPLIT + str(dest) + SPLIT + str(size) # squish the destination and file size together
            msg = msg.encode('utf-8') # string to bytewise
            socket_to_master.send(msg)
            time.sleep(0.1)
            socket_to_master.send(('get minions').encode('utf-8'))
            temp_minions = socket_to_master.recv(4096)
            temp_minions = pickle.loads(temp_minions)


            socket_to_master.send(('get data').encode('utf-8'))
            incomming = socket_to_master.recv(4096) # separate incomming stream to get chunk uuid and minion meta data
            chunks = pickle.loads(incomming) # Error may occur if master is windows (EOF related) or has differing python version


            socket_to_master.send(('get nodes_ids').encode('utf-8'))
            nodes_ids = socket_to_master.recv(4096)
            nodes_ids = pickle.loads(nodes_ids)


            # problem develops if there are not enough minions to carry the whole file - nov 7th
            if (chunks):
                write_output("CLIENT: # of chunks:" + str(len(chunks)))
                with open(source, "rb") as f:
                    for c in chunks:  # c[0] contains the uuid, c[1] contains the minion? no
                        data = f.read(chunk_size)
                        
                        chunk_uuid = c[0]
                        new_minions = [temp_minions[_] for _ in c[1]]
                        write_output("CLIENT: CHUNK: " + chunk_uuid)
                        self.send_to_minion(chunk_uuid, data, new_minions)
            write_output("CLIENT: --->   UPLOADED FILE: " + source)


        except socket.error as er:
            write_output("CLIENT: failed to connect with master")
            #raise er


    def send_to_minion(self, chunk_uuid, data, new_minions):
        minion = new_minions[0]
        new_minions = new_minions[1:]
        minion_host, minion_port = minion
        minion_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)# Create a socket connection.
        try:
            timeout = 5
            minion_socket.settimeout(timeout)
            minion_socket.connect((minion_host, int(minion_port)))
            data = encrypter.encrypt(passphrase, data) # encrypt the data prior to measurement & upload    
            # START META DATA
            msg = "P" + SPLIT + str(chunk_uuid) + SPLIT + str(len(data)) #str(sys.getsizeof(data)) # get sizeof adds 33 extra :(
            msg = msg.encode('utf-8') # string to bytewise
            minion_socket.send(msg)
            request = minion_socket.recv(2048).decode()
            if (request == 'get minions'):
                minions = pickle.dumps(new_minions)
                minion_socket.send(minions)
            request = minion_socket.recv(2048).decode()
            if (request == 'get data'):
                # START ACTUAL CHUNK DATA  
                minion_socket.sendall(data)
            request = minion_socket.recv(2048).decode()
            if (request == 'done'):
                write_output("CLIENT: Sent to minion: " + minion_host)
        except socket.error as er:
            write_output("CLIENT: no contact with minion - save likely failed: " + minion_host)
            #raise er

    def send_to_master(self):
        try:
            s.settimeout(timeout)
            s.connect((master_address, master_port))
            while True:
                incomming = s.recv(1024) # determine a decent byte size.
                if not incomming:
                    break
        except socket.error as er:
            raise er



class AESCipher():# Provide Capacity to Encrypt and Decrypt Messages Using AES

    def pad(self, s): # pad the text to be encrypted
        return s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * (chr(BLOCK_SIZE - len(s) % BLOCK_SIZE).encode('utf-8'))
    
    def unpad(self, s):
        return s[:-ord(s[len(s)-1:])]
   
    def encrypt(self, key, plaindata): # encrypt with AES 
        #key = self.padkey(key)
        cipher = AES.new(key)
        enc = cipher.encrypt(self.pad(plaindata))
        return base64.b64encode(enc)

    def decrypt(self, key, encodeddata):  # decrypt with AES 
        #key = self.padkey(key)
        cipher = AES.new(key)
        b64 = base64.b64decode(encodeddata)
        return self.unpad(cipher.decrypt(b64))




def create_genesis_block(): # create a new block to be the first in a new chain.
    block_data = {} # data here will be for the most place symbolic or otherwise meaningless.
    block_data['index'] = 0
    block_data['version'] = VERSION
    block_data['timestamp'] = date.datetime.now()
    block_data['previous_hash'] = "0"
    block_data['user_data'] = "none"
    block_data['data_hash'] = "none"
    block_data["proof"] = '00000048_GENESIS_BLOCKb16e9ac6cb' #use '9' when using pof1, for pof2 use 00000048_GENESIS_BLOCKb16e9ac6cb or similar
    block_data['data_url'] = "0"
    first_block = Block(block_data)
    write_output("------NEW CHAIN-----")
    return first_block

def write_output(output): # custom print method, timestamp for screen and log
    stamp = str(date.datetime.now()) + " - " + " - "
    entry = stamp + str(output)
    print(entry)
    if os.path.isfile(OUTPUTFNAME):
        with open(OUTPUTFNAME, "a") as f:
            f.write(SPLIT + entry)
    else:
        with open(OUTPUTFNAME, "a") as f:
            f.write(entry)

def get_blocks(): # ready local blockchain for transmission
    chain_to_send = blockchain
    for i in range(len(chain_to_send)):
        block = chain_to_send[i]
        block_index = str(block.index)
        block_version = str(block.version)
        block_timestamp = str(block.timestamp)
        block_user_data = str(block.user_data)
        block_data_hash = str(block.data_hash)
        block_data_url = str(block.data_url)
        block_hash = str(block.hash)
        block_proof = str(block.proof)
        block_previous_hash = str(block.previous_hash)

        chain_to_send[i] = {
            "index": block_index,
            "version": block_version,
            "timestamp": block_timestamp,
            "user_data": block_user_data,
            "data_hash": block_data_hash,
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
                 + "\ndata_hash:" + block_data_hash
                 + "\ndata_url:" + block_data_url
                 + "\nhash:" + block_hash
                 + "\nproof of work:"  + block_proof
                 + "\nprevious hash:" + block_previous_hash
                 )
    chain_to_send = json.dumps(chain_to_send)
    return chain_to_send


def add_transaction(user_data, data_hash, data_url):# add a new transaction to the list       POST
    # get incomming transaction
    # add it to the list
    write_output("New Transaction: " + user_data + " " + data_hash + " " + data_url)
    local_transactions.append(Transaction(user_data, data_hash, data_url))

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
        #print (curr_hash)

        if curr_hash.startswith('000000'):
            #print (curr_hash)
            #print (curr_string)
            complete = True
            return curr_hash

def is_ip(addr): # simple check as to if a string looks like a valid IPv4 address
    try:
        socket.inet_aton(addr) # OMFG forget the string checks, just ask the hardware!
        return True
    except socket.error:
        return False

def mine():
    # gather the data required to mine the block
    if local_transactions: # check if list is empty, very pythonic
        print('mining...')
        #print("# of local transactions:" + str(len(local_transactions)))
        current_transaction = local_transactions.pop(0) # first in, first out
        new_block_user_data = current_transaction.user_data
        new_block_data_url = current_transaction.data_url
        new_data_hash = current_transaction.data_hash

        # Get the last mined block
        # Q? what happens if we come across our own transaction? tbd
        blockchain = organise_chain()

        length = len(blockchain)
        #print("last block:" + str(length - 1)) ## correct feeds 6
        last_block = blockchain[length - 1]
        #print ("last block index:" + str(last_block.index)) ## incorrect feeds 5
        #print (last_block.index + 1)
        new_block_index = last_block.index + 1
        #print("new block index:" + str(new_block_index))

        last_block_hash = last_block.hash

        ### ----- PROOF OF WORK
        #proof = proof_of_work(last_block.proof) #gets real slow over time. +3 hrs for blocks after 24
        proof = proof_of_work2(last_block.proof) # tdjsnelling based method, more in line with common block chains
        ### ----- END PROOF OF WORK

        block_data = {}
        block_data['index'] = new_block_index
        block_data['version'] = VERSION
        block_data['timestamp'] = date.datetime.now()
        block_data['previous_hash'] = last_block_hash
        block_data['user_data'] = new_block_user_data
        block_data['data_hash'] = new_data_hash
        block_data['proof'] = proof
        block_data['data_url'] = new_block_data_url
        new_block = Block(block_data)
        blockchain.append(new_block)
        save_block(new_block)

def sync_node_list(conf): # read list of nodes from settings 
    nodes = []
    node_list = conf.get('miner', 'peer_nodes').split(',')
    for n in node_list:
        host, port = n.split(':')
        if is_ip(host): # does the address at least look like IPv4?
            node = [host, int(port)]
            nodes.append(node) # then add it to the node list
    return nodes

def get_miner_address(conf): # read miner_address from settings
    miner_address = conf.get('miner', 'miner_address')
    write_output("MINER ADDRESS:" + miner_address) # and advertise known nodes
    return miner_address

def get_master_address(conf): # get the IP address of the master from settings 
    master_address = conf.get('client', 'master_address')
    num, master_address, master_host = master_address.split(':')
    write_output("MASTER ADDRESS:" + master_address) # and advertise known nodes
    return master_address, int(master_host)

def sync_local_chain(foreign_nodes): # read local block JSON files 
    write_output("Syncronizing Blockchain...")
    syncing_blocks = []
    if not os.path.exists(BLOCKCHAIN_DATA_DIR): # is there no local block folder?
        os.mkdir(BLOCKCHAIN_DATA_DIR)
    if os.listdir(BLOCKCHAIN_DATA_DIR) == []: # is the folder empty, ie no local genesis block?
        # try to find a remote chain to adopt before creating a new chain
        syncing_blocks = consensus(syncing_blocks, foreign_nodes)
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

def save_block(block): # save a block as a local JSON file
    if os.path.exists(BLOCKCHAIN_DATA_DIR):
        filename = '%s/%s.json' % (BLOCKCHAIN_DATA_DIR, block.index)
        with open(filename, 'w') as block_file:
            write_output("NEW BLOCK:: " + str(block.__dict__()))
            json.dump(block.__dict__(), block_file)

def consensus(blockchain, foreign_nodes): # Get the blockchain from other nodes
    new_chain = False # initial condition
        # If our chain isn't longest, then we store the longest chain
        # would also like to check for chains with non-current version numbers
        # and force the adoption, since the blocks are newer than anything that
        # could be produced locally. This may be a fringe use case.
        # unsure as to how to treat them as of yet.
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
            else:
                # existing block json should be handled here
                # they shouldn't be overwritten but tagged somehow to show orphaned status
                write_output("block " + str(block.index) + " already exists - abort write") # consider intregrity checks
    return blockchain

def findchains(foreign_nodes):
    
    timeout = 2
    global localhost
    list_of_chains = []# query other listed nodes in the network for copies of their blockchains
    for url in foreign_nodes:# get their chain using some sort of get request
        peer_address = url[0]
        if (peer_address != get_my_ip()):
            peer_port = url[1]
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)# Create a socket connection.
            try:
                s.settimeout(timeout)
                s.connect((peer_address, peer_port))
                this_chain = []
                getting_blocks = True
                while getting_blocks:
                    msg = "go".encode('utf-8')
                    s.send(msg)
                    incomming = s.recv(1024) # determine a decent byte size.
                    # 4096 is pretty big considering our json files are ~397, genesis being 254
                    # 1024 seems reliable
                    if not incomming:
                        break
                    try:
                        if incomming.decode() == "done":
                            getting_blocks = False
                            break
                    except: 
                        pass
                    # determine break point between objects
                    # currently the server is just time.sleep(0.05) between breaks
                    
                    dict = pickle.loads(incomming) # create a dictionary from the stream data # ** blocks coming in too fast? or OCCASIONAL WINDOWS ERROR: _pickle.UnpicklingError: invalid load key, '5'
                    block_object = Block(dict) # use the dictionary to create a block object
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
                #raise ex
            except socket.error as ex:
                write_output("ERR:" + str(peer_address) + " : " + str(peer_port))
                #raise ex # raising ex here will crash the program

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

def promptUser(): ## take input from a prompt
    global incomming_file
    go = True
    while True:
        command = input("CMD> ") # changed raw_input to input as per python3 changes
        #print command
        if len(str(command)) > 0:
            if (command == "quit" or command == "exit"):		
                return command
            if (command.startswith("get")):
                try:
                    a, b = command.split(" ")
                    client.get(b)
                    return 'done get'
                except ValueError:
                    print("bad path")
                    go = False				
                if (go):
                    return command 
            if (command.startswith("put")):
                try:
                    a, b = command.split(" ") 
                    client.put(b)
                    return 'done put'   
                except ValueError:
                    print("bad path")
                    go = False
                if (go):
                    return command
                
            if (command.startswith("sync")):
                blockchain = organise_chain()
                
            if (command.startswith("mine")):
                mine()
                
            if (command.startswith("delete")):
                try:
                    a, b = command.split(" ")
                    print("not yet implemented")
                    return 'done delete'
                except ValueError:
                    print("bad path")
                    go = False



            else:
                return command
        else:
            print("String cannot be empty...")
            continue

# Initial Setup
global localhost
localhost = get_my_ip()
local_transactions = [] # store transactions in a list


if __name__ == "__main__":
    try:
        global master_address
        global master_port


        passphrase = PASSPHRASE
        encrypter = AESCipher()
        blockchain, miner_address, master_address, master_port, all_minions, chunk_size, replication_factor = set_configuration()
        print ("Hello World")
        print ("(p)ut  (g)et  (m)ine  e(x)it")
        #1/0 #test exception log

        
        
        # -----START SERVICES--------------------------------------------------

        chainserver = ChainServer(localhost, CHAIN_PORT)
        
        time.sleep(0.5)

        if active_master:
            storage_master = StorageNodeMaster(localhost, MASTER_PORT, all_minions, chunk_size, replication_factor)

        if active_minion:
            storage_minion = StorageNodeMinion(localhost, MINION_PORT)

        if (active_master or active_minion):
            signal.signal(signal.SIGINT, int_handler) # set up handler for chunk table image


        if active_client:
            client = Client()
            #time.sleep(1)
            #client.put(TESTFILE)
            #time.sleep(1)
            #client.get(TESTFILE)
            active = True
            while active:
                command = promptUser()
                if (command == 'quit' or command == 'exit'):
                    active = False
                    
            


        # ---------------------------------------------------------------------
        if active_miner:
            # mining tests -------------------------
            #add_transaction(miner_address, 'datahash', 'c6efb084e37d11e8bd44001a92daf3f8') # test with known uuid url
            # mine transactions into blocks
            if local_transactions:
                for x in range(0, 5):
                    mine()
            # end mining tests ---------------------

        #time.sleep(1)
        #client.put(TESTFILE)
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
            add_transaction(miner_address, u.hex) # attach the user dat

        #get_blocks()

    except BaseException as e:
        logging.error(e, exc_info=True) # ensure exceptions and such things are logged for prosperity
        raise e # but still raise the exception naturally

    write_output("PROGRAM COMPLETE, SERVING UNTIL MANUAL ABORT...") # final command
    sys.exit()
