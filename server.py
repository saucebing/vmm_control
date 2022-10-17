#!/usr/bin/python
from socket import *
import time, os, sys
from time import ctime

class SERVER:
    HOST = ''
    PORT = 12345
    BUFSIZE = 1024 *1024
    ADDR = None
    tcpCliSock = None

    def __init__(self):
        self.ADDR = (self.HOST,self.PORT)

    def set_port(self, port):
        self.PORT = port
        self.ADDR = (self.HOST,self.PORT)

    def b2s(self, s):
        return str(s, encoding = 'utf-8')

    def build(self):
        global tcpSerSock
        global tcpCliSock
        tcpSerSock = socket(AF_INET,SOCK_STREAM)
        tcpSerSock.bind(self.ADDR)
        tcpSerSock.listen(5)
        print('Test Server: waiting for connection')
        sys.stdout.flush()
        sys.stderr.flush()
        tcpCliSock, addr = tcpSerSock.accept()
        print('Connnecting from: ', addr)
        sys.stdout.flush()
        sys.stderr.flush()
        
    def recv(self):
        global tcpCliSock
        data = self.b2s(tcpCliSock.recv(self.BUFSIZE))
        print('Recv: ', data)
        sys.stdout.flush()
        sys.stderr.flush()
        return data

    def send(self, data):
        global tcpCliSock
        print('Send: ', data)
        sys.stdout.flush()
        sys.stderr.flush()
        tcpCliSock.send(data.encode())

    def client_close(self):
        global tcpCliSock
        tcpCliSock.close()

    def server_close(self):
        global tcpSerSock
        tcpSerSock.close()
