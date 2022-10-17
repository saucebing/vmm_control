#!/usr/bin/python
from socket import *

class CLIENT:
    #self.HOST = '127.0.0.1' # or 'localhost'
    HOST = '200.201.119.35' # or 'localhost'
    PORT = 12345
    BUFSIZE = 1024
    ADDR = None
    tcpCliSock = None

    def __init__(self):
        self.ADDR = (self.HOST,self.PORT)

    def b2s(self, s):
        return str(s, encoding = 'utf-8')

    def set_ip(self, ip):
        self.HOST = ip
        self.ADDR = (self.HOST, self.PORT)

    def set_port(self, port):
        self.PORT = port
        self.ADDR = (self.HOST, self.PORT)

    def connect(self):
        print('ADDR: ', self.ADDR)
        self.tcpCliSock = socket(AF_INET,SOCK_STREAM)
        self.tcpCliSock.connect(self.ADDR)

    def recv(self):
        data = self.b2s(self.tcpCliSock.recv(self.BUFSIZE))
        print('Recv: ', data)
        return data

    def send(self, data):
        print('Send: ', data)
        self.tcpCliSock.send(data.encode())

    def client_close(self):
        self.tcpCliSock.close()
