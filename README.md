How to run application.py flags 

The application.py script is used to transfer a file from a client to a server over a UDP connection. To run the script, you need to specify the IP address and port number of the server, the name and path of the file to be transferred, and the maximum size of the packet payload.

Stop and wait client as an example
First server:
python application.py -s -I 127.0.0.1 -port 8080 -f file.txt -r stop_and_wait
Then client:
python application.py -c -I 127.0.0.1 -port 8080 -f file.txt -r stop_and_wait

This command will transfer the file file.txt to a server with IP address 127.0.0.1 and port number 8080, using packets with a maximum payload size of 1472 bytes.

If you want to use selective repeat or gbn, you have to use SR or gbn respectively. 
If you don't give a file the code will give you an error message as a response.


If you want to skip an ack you can do it as such (SR as an example):
python3 application.py -s -I 127.0.0.1 -p 8080 -r SR -t skip_ack

If you want to test the packet_loss (GBN as an example):
python3 application.py -c -I 127.0.0.1 -p 8080 -f <file_to_transfer.jpg> -r gbn -t loss


