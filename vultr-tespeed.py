# -*- coding: utf-8 -*-
"""
Created on Thu Feb  7 01:53:07 2019

@author: 23867
"""

import os, sys, socket, struct, select, time, requests

if sys.platform == "win32":
    # On Windows, the best timer is time.clock()
    default_timer = time.clock
else:
    # On most other platforms the best timer is time.time()
    default_timer = time.time

# From /usr/include/linux/icmp.h; your milage may vary.
ICMP_ECHO_REQUEST = 8 # Seems to be the same on Solaris.


def checksum(source_string):
    """
    I'm not too confident that this is right but testing seems
    to suggest that it gives the same answers as in_cksum in ping.c
    """
    sum = 0
    countTo = (len(source_string)/2)*2
    count = 0
    while count<countTo:
        thisVal = ord(source_string[count + 1])*256 + ord(source_string[count])
        sum = sum + thisVal
        sum = sum & 0xffffffff # Necessary?
        count = count + 2

    if countTo<len(source_string):
        sum = sum + ord(source_string[len(source_string) - 1])
        sum = sum & 0xffffffff # Necessary?

    sum = (sum >> 16)  +  (sum & 0xffff)
    sum = sum + (sum >> 16)
    answer = ~sum
    answer = answer & 0xffff

    # Swap bytes. Bugger me if I know why.
    answer = answer >> 8 | (answer << 8 & 0xff00)

    return answer


def receive_one_ping(my_socket, ID, timeout):
    """
    receive the ping from the socket.
    """
    timeLeft = timeout
    while True:
        startedSelect = default_timer()
        whatReady = select.select([my_socket], [], [], timeLeft)
        howLongInSelect = (default_timer() - startedSelect)
        if whatReady[0] == []: # Timeout
            return

        timeReceived = default_timer()
        recPacket, addr = my_socket.recvfrom(1024)
        icmpHeader = recPacket[20:28]
        type, code, checksum, packetID, sequence = struct.unpack(
            "bbHHh", icmpHeader
        )
        # Filters out the echo request itself. 
        # This can be tested by pinging 127.0.0.1 
        # You'll see your own request
        if type != 8 and packetID == ID:
            bytesInDouble = struct.calcsize("d")
            timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
            return timeReceived - timeSent

        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return


def send_one_ping(my_socket, dest_addr, ID):
    """
    Send one ping to the given >dest_addr<.
    """
    dest_addr  =  socket.gethostbyname(dest_addr)

    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    my_checksum = 0

    # Make a dummy heder with a 0 checksum.
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1)
    bytesInDouble = struct.calcsize("d")
    data = (192 - bytesInDouble) * "Q"
    data = struct.pack("d", default_timer()) + data

    # Calculate the checksum on the data and the dummy header.
    my_checksum = checksum(header + data)

    # Now that we have the right checksum, we put that in. It's just easier
    # to make up a new header than to stuff it into the dummy.
    header = struct.pack(
        "bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1
    )
    packet = header + data
    my_socket.sendto(packet, (dest_addr, 1)) # Don't know about the 1


def do_one(dest_addr, timeout):
    """
    Returns either the delay (in seconds) or none on timeout.
    """
    icmp = socket.getprotobyname("icmp")
    try:
        my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
    except socket.error, (errno, msg):
        if errno == 1:
            # Operation not permitted
            msg = msg + (
                " - Note that ICMP messages can only be sent from processes"
                " running as root."
            )
            raise socket.error(msg)
        raise # raise the original error

    my_ID = os.getpid() & 0xFFFF

    send_one_ping(my_socket, dest_addr, my_ID)
    delay = receive_one_ping(my_socket, my_ID, timeout)

    my_socket.close()
    return delay


def verbose_ping(dest_addr, timeout = 2, count = 4, comment = 1):
    """
    Send >count< ping to >dest_addr< with the given >timeout< and display
    the result.
    """
    num_success = 0
    num_timeout = 0
    num_failed = 0
    average_time = 0
    sum_time = 0
    min_time = timeout
    max_time = 0
    for i in xrange(count):
        if comment is 1:
            print "ping %s..." % dest_addr,
        try:
            delay  =  do_one(dest_addr, timeout)
        except socket.gaierror, e:
            if comment is 1:
                print "failed. (socket error: '%s')" % e[1]
            num_failed = num_failed + 1
            break
        if delay  ==  None:
            if comment is 1:
                print "failed. (timeout within %ssec.)" % timeout
            num_timeout = num_timeout + 1
        else:
            delay  =  delay * 1000
            if delay > max_time: 
                max_time = delay 
            if delay < min_time: 
                min_time = delay
            sum_time = sum_time + delay
            num_success = num_success + 1
            if comment is 1:
                print "get ping in %0.4fms" % delay
    print "success: %d  failed: %d  timeout: %d ( %.2f%% loss)" %(num_success,num_failed,num_timeout,(1-num_success*1.0/count)*100.0)
    print "min_time: %s  max_time: %s  average_time: %s" %(min_time, max_time, average_time)

"""
==============================================================================
"""
def download_file(url, timeout=30):
    """Downloads the specified url and prints out the max speed, average speed and time elapsed 
    Arguments: 
        url {[string]} -- [the url of the file to download] """
    start = time.clock()            #返回时间
    request = requests.get(url, stream=True) #原始相应内容
    #print request.headers
    size = int(request.headers.get('Content-Length')) #从headers中读到文件大小
    downloaded = 0.0
    total_mbps = 0.0
    maximum_speed = 0.0
    total_chunks = 0.0

    
    
    if size is not None:
        for chunk in request.iter_content(1024 * 1024):#分块下载,边下载边存硬盘
            if time.clock()-start < timeout: 
                downloaded += len(chunk)
                done = 50 * downloaded / size  #绘制下载的进度条,50个格格
                mbps = downloaded / (time.clock() - start) / (1024 * 1024)#下载量/时间/块大小
                maximum_speed = mbps if mbps > maximum_speed else maximum_speed
                total_chunks += 1   #统计下载的块大小
                total_mbps += mbps  #统计总的mbps
                sys.stdout.write("\r[%s%s] %.2f MBps" %
                                 ('=' * int(done), ' ' * int(50 - done), mbps))
            # Print result summary
            else:
                print("error: timeout %d "%timeout)
                break
        print("\nMaximum Speed: %.2f MBps" % (maximum_speed))
        if total_chunks is not 0.0:
            print total_chunks
            print("Average Speed: %.2f MBps" % (total_mbps / total_chunks))
        else:
            print("Average Speed: 0 MBps")
        print("Time Elapsed: %.2fs" % (time.clock() - start))
    else:
        print("Cannot calculate download speed")
        
        
if __name__ == '__main__':
    location = [
                "德国法兰克福",
                "荷兰阿姆斯特丹",
                "法国巴黎",
                "英国伦敦",
                "日本东京",
                "新加坡",
                "加拿大多伦多",
                "纽约（新泽西州）",
                "伊利诺伊州芝加哥",
                "华盛顿州西雅图市",
                "美国佐治亚州亚特兰大",
                "迈阿密，佛罗里达",
                "达拉斯，德克萨斯州",
                "加利福尼亚州硅谷",
                "加利福尼亚州洛杉矶",
                "悉尼，澳大利亚"]
    pingurl = [
            "fra-de-ping.vultr.com",
            "ams-nl-ping.vultr.com",
            "par-fr-ping.vultr.com",
            "lon-gb-ping.vultr.com",
            "hnd-jp-ping.vultr.com",
            "sgp-ping.vultr.com",
            "tor-ca-ping.vultr.com",
            "nj-us-ping.vultr.com",
            "il-us-ping.vultr.com",
            "wa-us-ping.vultr.com",
            "ga-us-ping.vultr.com",
            "fl-us-ping.vultr.com",
            "tx-us-ping.vultr.com",
            "sjo-ca-us-ping.vultr.com",
            "lax-ca-us-ping.vultr.com",
            "syd-au-ping.vultr.com"]
    v4100url = [
            "https://fra-de-ping.vultr.com/vultr.com.100MB.bin",
            "https://ams-nl-ping.vultr.com/vultr.com.100MB.bin",
            "https://par-fr-ping.vultr.com/vultr.com.100MB.bin",
            "https://lon-gb-ping.vultr.com/vultr.com.100MB.bin",
            "https://hnd-jp-ping.vultr.com/vultr.com.100MB.bin",
            "https://sgp-ping.vultr.com/vultr.com.100MB.bin",
            "https://tor-ca-ping.vultr.com/vultr.com.100MB.bin",
            "https://nj-us-ping.vultr.com/vultr.com.100MB.bin",
            "https://il-us-ping.vultr.com/vultr.com.100MB.bin",
            "https://wa-us-ping.vultr.com/vultr.com.100MB.bin",
            "https://ga-us-ping.vultr.com/vultr.com.100MB.bin",
            "https://fl-us-ping.vultr.com/vultr.com.100MB.bin",
            "https://tx-us-ping.vultr.com/vultr.com.100MB.bin",
            "https://sjo-ca-us-ping.vultr.com/vultr.com.100MB.bin",
            "https://lax-ca-us-ping.vultr.com/vultr.com.100MB.bin",
            "https://syd-au-ping.vultr.com/vultr.com.100MB.bin"
            ]
    j=0;
    
    for i in location:
        print j, i
        verbose_ping(pingurl[j],2,16,0)# url, timeout, count, comment{1|0}
        download_file(v4100url[j],30)# url, timeout
        print " "
        j=j+1;
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    