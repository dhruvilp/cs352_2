# CS 352 : Internet Tech : Project 1

## Group Members:  
Dhruvil Patel & Kabir Kuriyan

We will be using python3.  On the ilab machines add the python environments to your path and then activate python 3.6

```
export PATH="$PATH:/koko/system/anaconda/bin"
source activate python36
```

The structure follows the instructions.  The connection is established by connect on the client and accept on the server.  This performs the three way handshake of sending the SYN, SYN+ACK, and ACK with the sequence number to establish a connection.  This is also where the sockets are assigned and bound.  

Then the send and recieve functions handle sending the data.  In send() a thread is spawnned off for each packet and monitors if the packet has been acknowledged by the server.  If it hasn't, the client will initiate the go-back-n protocol to resend n packets.  

On close, another three way handshake is performed, where a FIN, FIN+ACK, ACK exchange occurs and then closes the sockets.  

The socket class contains the following fields:  
- The server address maintains where the packets should go. 
- Socket is used to hold the socket declaration used to call the UDP methods.  
- Sequence and acknowledge number are used to maintain the order of packets and keep track of which ones have been recevied.  
- is_server_established is used to maintain if this is currently running on the server or on the client.  
- The lock is used to maintain data that is accessed in all the threads. 
